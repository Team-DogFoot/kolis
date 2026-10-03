"""원부 일괄 처리(과장님용, 2026-10-03 설계서 1절): 원부번호 여러 개 → 상태 조회 → 복본조사(원부마다, 지금은 하나씩) → 후보 판정 → 완료·일괄변경.
원부 하나짜리 함수(build_prep.dupexmin / dup_complete / batch_change)를 그대로 쓰고, 이 모듈은 목록을 돌며 기록만 얹는다.
기록: work/logs/ledger-batch-<시각>.jsonl(한 실행에 하나) + 원부별 work/build/wonbu_<n>/ + 브라우저 기록."""
from __future__ import annotations
import datetime, json, re
from pathlib import Path

from . import build_prep, dup_request, kolis_http
from . import mods_build as mb
from .kolis_browser import Browser


def _try(name: str, wonbu: str, req, scr, log, note, on_browser=None):
    """요청 방식을 먼저 쓰고, 실패하면 화면 방식(Edge)으로 다시 한다(2026-10-03 유저 지시). 어느 쪽으로 됐는지 기록에 남긴다."""
    try:
        r = req()
        note(step=name, wonbu=wonbu, mode="request", ok=True)
        return r
    except Exception as e:  # noqa: BLE001
        msg = f"{type(e).__name__}: {e}"
        log(f"요청 방식 {name} 실패 → 화면 방식으로 다시 합니다: {msg}")
        note(step=name, wonbu=wonbu, mode="request", ok=False, error=msg)
        if on_browser:
            try:
                on_browser()      # 화면 방식으로 넘어갈 때만(프로그램 창 내리기). 요청 방식은 창을 건드리지 않는다
            except Exception:  # noqa: BLE001
                pass
        r = scr()
        note(step=name, wonbu=wonbu, mode="browser", ok=True)
        return r

WORK = mb.WORK
LOGS = Path("work/logs")
LAST = Path("work/ledger_batch.json")      # 마지막으로 넣은 원부 목록(화면 복원용)


def parse(text: str) -> list[str]:
    """원부번호 목록. 엑셀 한 열 붙여 넣기(줄바꿈)·쉼표·공백·탭·세미콜론·범위(1607-1616, 1607~1616) 전부. 숫자가 아닌 토큰(머리글 '원부번호' 등)은 버린다. 순서 유지, 중복 제거."""
    out: list[str] = []
    for tok in re.split(r"[\s,;、，]+", text or ""):
        tok = tok.strip()
        if not tok:
            continue
        m = re.fullmatch(r"(\d+)\s*[-~–]\s*(\d+)", tok)
        if m:
            a, b_ = int(m.group(1)), int(m.group(2))
            if a > b_:
                a, b_ = b_, a
            if b_ - a > 500:
                continue
            out.extend(str(i) for i in range(a, b_ + 1))
        elif tok.isdigit():
            out.append(tok)
    seen, uniq = set(), []
    for w in out:
        if w not in seen:
            seen.add(w); uniq.append(w)
    return uniq


def _journal():
    LOGS.mkdir(parents=True, exist_ok=True)
    p = LOGS / f"ledger-batch-{datetime.datetime.now():%Y%m%d-%H%M%S}.jsonl"
    def note(**kw):
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"time": f"{datetime.datetime.now():%H:%M:%S}", **kw}, ensure_ascii=False, default=str) + "\n")
    class J:                      # 요청 클라이언트가 요청·응답 본문을 같은 파일에 적게 하는 어댑터(자동화 재료)
        def write(self, kind, **row):
            note(kind=kind, **row)
    return p, note, J()


def _rd(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def prep_info(wonbu: str) -> dict:
    """원부 하나의 로컬 상태(state.json + 복본 판정)를 화면용으로. app.build_status 와 원부 일괄 처리 표가 같이 쓴다."""
    d = WORK / f"wonbu_{wonbu}"
    st, dj, jb = _rd(d / "state.json"), _rd(d / "dup_build.json"), _rd(d / "dup_job.json")
    def brief(x):
        det = (x or {}).get("detail") or {}; vols = (x or {}).get("volumes") or []
        return {"title": det.get("TITLE"), "subtitle": det.get("SUBTITLE") or det.get("SUB_TITLE1"), "vol": det.get("VOL") or (vols[0].get("VOL") if vols else None), "author": det.get("AUTHOR"),
                "publisher": det.get("PUBLISHER"), "prod_day": det.get("PROD_DAY") or (vols[0].get("PROD_DAY") if vols else None), "isbn": det.get("EA_ISBN"), "acq_year": det.get("ACQUISIT_YR"), "species_gbn": det.get("SPECIES_GBN"), "use_obj": det.get("USE_OBJ_CODE")}
    rows = []
    if dj and jb:
        ours = {o.get("row_key"): o for o in jb.get("ours") or []}; cands = {c.get("rec_key"): c for c in jb.get("candidates") or []}
        by: dict = {}
        for pr in dj.get("pairs") or []:
            by.setdefault(pr.get("our_key"), []).append({**pr, "cand": brief(cands.get(pr.get("cand_key")))})
        for k, o in ours.items():
            rows.append({"our": brief(o), "ident": o.get("ident"), "pairs": by.get(k, [])})
    return {"dupexmin_done": st.get("dupexmin_done"), "dupexmin_run": st.get("dupexmin_run"), "dupexmin_rows": st.get("dupexmin_rows"), "dupexmin_at": st.get("dupexmin_at"), "mode": st.get("mode"), "acc_count": st.get("acc_count"), "status": st.get("status"),
            "title": st.get("title"), "dc_species": st.get("dc_species"), "dc_contents": st.get("dc_contents"),
            "dup": {"pairs": len(dj.get("pairs") or []), "counts": dj.get("counts"), "summary": dj.get("summary"), "file": str(d / "dup_build.json") if dj else None, "note": st.get("dup_note"),
                    "ours": len(jb.get("ours") or []), "candidates": len(jb.get("candidates") or []), "rows": rows, "review": dj.get("review")},
            "batch_change_done": st.get("batch_change_done"), "batch_values": st.get("batch_values"), "species": st.get("species"), "batch_verified_at": st.get("batch_verified_at"),
            "use_limit_done": st.get("use_limit_done"), "use_limit": st.get("use_limit"), "completed_at": st.get("dup_completed_at"), "batch_at": st.get("batch_at"), "error": st.get("last_error")}


def table(wonbus: list[str]) -> list[dict]:
    return [{"wonbu": w, **prep_info(w)} for w in wonbus]


def _save_state(wonbu: str, patch: dict):
    d = WORK / f"wonbu_{wonbu}"; d.mkdir(parents=True, exist_ok=True)
    p = d / "state.json"; st = _rd(p) or {"wonbu": wonbu}; st.update(patch)
    p.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")


def status(wonbus: list[str], log=print) -> dict:
    """「화면 열어 확인」: 원부마다 등록원부관리 조회(읽기만). 작품명·건수·상태를 state.json 에 적어 둔다. 복본조사 화면은 열지 않는다."""
    LAST.parent.mkdir(parents=True, exist_ok=True); LAST.write_text(json.dumps({"wonbus": wonbus}, ensure_ascii=False), encoding="utf-8")
    jp, note, J = _journal(); note(step="status", wonbus=wonbus)
    c = kolis_http.Client(log, J)
    try:
        c.login(); log("요청 방식으로 원부 상태를 읽습니다(브라우저 없음)")
        out = []
        for w in wonbus:
            ls = dup_request.ledger_status(c, w)
            title = ls.get("title")
            patch = {"acc_count": ls["acc_count"], "status": ls["status"], "title": title, **({"dupexmin_done": True} if ls["dup_done"] else {})}
            if ls["dup_done"]:
                # 완료된 원부는 일괄변경 상태도 KOLIS 에서 읽는다(첫 종 값). 프로그램 기록이 아니라 지금 값.
                try:
                    dc = dup_request.digitalcont(c, w); keys = [x.get("SPECIES_KEY") for x in dc.get("list") or []]
                    if keys:
                        v = dup_request.spec_view(c, keys[0])
                        vals = {k: v.get(k) for k in ("OFFER_DBCODE_1S", "OFFER_DBCODE_2S", "PUBLISHER_CODE", "KOGL_CODE")}
                        ok = vals["OFFER_DBCODE_1S"] == "CH1" and vals["OFFER_DBCODE_2S"] == "CH11" and vals["PUBLISHER_CODE"] == "PE"
                        patch.update({"batch_change_done": ok, "batch_values": vals, "species": len(keys), "dc_species": dc.get("cnt"), "dc_contents": dc.get("contentsCnt"), "batch_checked_from_kolis": True})
                        ls["batch_ok"] = ok
                except Exception as e:  # noqa: BLE001
                    log(f"원부 {w}: 일괄변경 값 읽기 실패({type(e).__name__})")
            _save_state(w, patch)
            note(step="status", wonbu=w, **ls)
            log(f"원부 {w}: {ls['acc_count']}건 · {', '.join(ls['status']) or '없음'}{' · ' + title if title else ''}{' · 복본조사 이미 완료' if ls['dup_done'] else ''}")
            out.append({"wonbu": w, **ls})
        return {"rows": out, "journal": str(jp), "mode": "request"}
    finally:
        c.close()


def run_dup(wonbus: list[str], log=print, handle: dict | None = None, on_browser=None) -> dict:
    """「복본조사 실행」: 원부마다 build_prep.dupexmin(approved=True) — 조사·판정·복본 체크까지. 완료 처리는 하지 않는다. 이미 끝난 원부는 건너뛴다."""
    LAST.parent.mkdir(parents=True, exist_ok=True); LAST.write_text(json.dumps({"wonbus": wonbus}, ensure_ascii=False), encoding="utf-8")
    jp, note, J = _journal(); note(step="dup", wonbus=wonbus)
    out = []
    c = kolis_http.Client(log, J)
    for i, w in enumerate(wonbus, 1):
        if (handle or {}).get("cancel"):
            note(step="dup", wonbu=w, cancelled=True); break
        log(f"── 원부 {w} ({i}/{len(wonbus)}) 복본조사")
        try:
            r = _try("dup", w, lambda: dup_request.dupexmin(w, log, client=c), lambda: build_prep.dupexmin(w, log, approved=True), log, note, on_browser)
            _save_state(w, {"last_error": None})
            note(step="dup", wonbu=w, already=r.get("already_done"), no_ledger=r.get("no_ledger"), rows=len(r.get("duplicates") or []), counts=r.get("counts"), completed=r.get("completed"))
            out.append({"wonbu": w, "ok": True, "already_done": r.get("already_done"), "no_ledger": r.get("no_ledger"), "counts": r.get("counts"), "rows": len(r.get("duplicates") or []), "message": r.get("message")})
        except Exception as e:  # noqa: BLE001
            msg = f"{type(e).__name__}: {e}"
            _save_state(w, {"last_error": msg}); note(step="dup", wonbu=w, error=msg); log(f"!!! 원부 {w} 실패: {msg}")
            out.append({"wonbu": w, "ok": False, "error": msg})
    c.close()
    return {"rows": out, "journal": str(jp)}


def complete(wonbus: list[str], log=print, handle: dict | None = None, on_browser=None) -> dict:
    """「고른 원부 완료 처리 + 일괄변경」: 원부마다 dup_complete → batch_change. 되돌릴 수 없다(사람이 골라 눌렀을 때만)."""
    jp, note, J = _journal(); note(step="complete", wonbus=wonbus)
    out = []
    c = kolis_http.Client(log, J)
    for i, w in enumerate(wonbus, 1):
        if (handle or {}).get("cancel"):
            break
        log(f"── 원부 {w} ({i}/{len(wonbus)}) 완료 처리 → 일괄변경")
        rec = {"wonbu": w}
        try:
            info = prep_info(w)
            if info.get("dupexmin_done"):
                log(f"원부 {w}: 복본조사 완료 상태라 완료 처리는 건너뜁니다"); rec["complete"] = "skip"
            else:
                r = _try("complete", w, lambda: dup_request.dup_complete(w, log, client=c), lambda: build_prep.dup_complete(w, log, approved=True), log, note, on_browser); rec["complete"] = r
                _save_state(w, {"dup_completed_at": f"{datetime.datetime.now():%Y-%m-%d %H:%M}"})
            note(step="complete", wonbu=w, result=rec["complete"])
            if info.get("batch_change_done"):
                log(f"원부 {w}: 일괄변경이 이미 끝나 있어 건너뜁니다"); rec["batch"] = "skip"
            else:
                r2 = _try("batch", w, lambda: dup_request.batch_change(w, log, client=c), lambda: build_prep.batch_change(w, log, approved=True), log, note, on_browser); rec["batch"] = r2
                _save_state(w, {"batch_at": f"{datetime.datetime.now():%Y-%m-%d %H:%M}"})
            note(step="batch", wonbu=w, result=rec["batch"]); rec["ok"] = True
        except Exception as e:  # noqa: BLE001
            msg = f"{type(e).__name__}: {e}"
            _save_state(w, {"last_error": msg}); note(step="complete", wonbu=w, error=msg); log(f"!!! 원부 {w} 실패: {msg}"); rec.update({"ok": False, "error": msg})
        out.append(rec)
    c.close()
    return {"rows": out, "journal": str(jp)}


def process(wonbus: list[str], force: list[str] | None = None, log=print, handle: dict | None = None, on_browser=None) -> dict:
    """「선택한 원부 처리」 — 원부마다 다음 할 일을 프로그램이 정해서 한다(2026-10-03 유저: 조회·실행·완료를 한 흐름으로).
    안 돌린 원부 → 복본조사(+후보 판정). 후보가 없으면 → 완료 → 일괄변경. 후보가 있으면 → 멈추고 보고(force 에 든 원부만 완료까지).
    이미 완료된 원부 → 일괄변경이 안 됐으면 그것만. 전부 끝났으면 건너뜀."""
    force = set(force or [])
    LAST.parent.mkdir(parents=True, exist_ok=True); LAST.write_text(json.dumps({"wonbus": wonbus}, ensure_ascii=False), encoding="utf-8")
    jp, note, J = _journal(); note(step="process", wonbus=wonbus, force=sorted(force))
    c = kolis_http.Client(log, J)
    out = []
    for i, w in enumerate(wonbus, 1):
        if (handle or {}).get("cancel"):
            note(step="process", wonbu=w, cancelled=True); break
        rec = {"wonbu": w, "did": []}
        try:
            info = prep_info(w)
            if not info.get("dupexmin_run") and not info.get("dupexmin_done"):
                log(f"── 원부 {w} ({i}/{len(wonbus)}) 복본조사")
                r = _try("dup", w, lambda: dup_request.dupexmin(w, log, client=c), lambda: build_prep.dupexmin(w, log, approved=True), log, note, on_browser)
                rec["did"].append("dup"); rec["dup"] = {k: r.get(k) for k in ("already_done", "no_ledger", "counts", "message")}; rec["rows"] = len(r.get("duplicates") or [])
                if r.get("no_ledger"):
                    rec["stop"] = "no_ledger"; out.append(rec); continue
                info = prep_info(w)
            pairs = (info.get("dup") or {}).get("pairs") or 0
            if not info.get("dupexmin_done"):
                if pairs and w not in force:
                    c0 = (info.get("dup") or {}).get("counts") or {}
                    log(f"원부 {w}: 복본 후보 {pairs}짝(복본 {c0.get('dup',0)}·아님 {c0.get('not',0)}·판단 불가 {c0.get('unsure',0)}) — 완료 처리하지 않고 멈춥니다. 판정을 보고 결정하십시오")
                    rec["stop"] = "candidates"; rec["counts"] = c0; out.append(rec); continue
                log(f"── 원부 {w} 완료 처리" + (" (후보 있음, 사람이 결정)" if pairs else ""))
                r = _try("complete", w, lambda: dup_request.dup_complete(w, log, client=c), lambda: build_prep.dup_complete(w, log, approved=True), log, note, on_browser)
                _save_state(w, {"dup_completed_at": f"{datetime.datetime.now():%Y-%m-%d %H:%M}", **({"completed_with_candidates": True} if pairs else {})})
                rec["did"].append("complete"); info = prep_info(w)
            if not info.get("batch_change_done"):
                log(f"── 원부 {w} 일괄변경")
                r2 = _try("batch", w, lambda: dup_request.batch_change(w, log, client=c), lambda: build_prep.batch_change(w, log, approved=True), log, note, on_browser)
                _save_state(w, {"batch_at": f"{datetime.datetime.now():%Y-%m-%d %H:%M}"})
                rec["did"].append("batch"); rec["batch_ok"] = r2.get("ok")
            if not rec["did"]:
                rec["stop"] = "nothing"
            _save_state(w, {"last_error": None}); rec["ok"] = True
        except Exception as e:  # noqa: BLE001
            msg = f"{type(e).__name__}: {e}"
            _save_state(w, {"last_error": msg}); note(step="process", wonbu=w, error=msg); log(f"!!! 원부 {w} 실패: {msg}"); rec.update({"ok": False, "error": msg})
        note(step="process", wonbu=w, **{k: v for k, v in rec.items() if k != "wonbu"})
        out.append(rec)
    c.close()
    return {"rows": out, "journal": str(jp)}

