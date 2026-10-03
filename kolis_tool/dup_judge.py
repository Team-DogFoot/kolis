"""5.1 복본조사 결과 판정 — 에이전트가 한다(2026-10-03 유저 확정: 판단은 에이전트, 고정 규칙 금지).
흐름: gather(wonbu, rows) — 복본조사 결과 표(우리 자료 행 ORIGIN_YN=V 와 그 아래 후보 행들)에서 우리 종·후보 종의 상세(getOnSpecView, 조회)와 권 목록(listVolumn, 조회)을 모아
      work/build/wonbu_<번호>/dup_job.json 을 만든다 → run(wonbu) — 스킬 judge-duplicates 로 판정 → dup_build.json
결과: pairs[] 마다 verdict dup / not / unsure 와 근거. unsure 가 하나라도 있으면 완료 처리하지 않고 사람에게 넘긴다(build_prep.dupexmin 이 그렇게 한다).
"""
from __future__ import annotations
import json
from pathlib import Path

from .kolis_browser import Browser, BASE
from . import mods_build as mb

H = {"X-Requested-With": "XMLHttpRequest"}
DETAIL_KEYS = ("SPECIES_KEY", "TITLE", "SUBTITLE", "SUB_TITLE1", "SUB_TITLE2", "PAR_TITLE", "VOL", "VOL_TITLE", "AUTHOR", "PUBLISHER", "PUBLISH_PLACE", "PUBLISH_YEAR", "PROD_DAY", "END_PROD_DAY",
               "EA_ISBN", "SET_ISBN", "VOL_ISBN", "ISSUANCE", "ACQUISIT_YR", "ACQUISIT_CODE", "WORKING_STATUS", "SPECIES_GBN", "REG_CODE", "OFFER_DBCODE_1S", "OFFER_DBCODE_2S",
               "USE_OBJ_CODE", "USE_LIMIT_CODE", "GENRE", "TYPEOFRESOURCE", "CLASS_NO", "NOTE", "KOLIS_CONTROL_NO", "CONTROL_NO", "DUP_FLAG", "REG_DT", "LAST_MOD_DT")
VOL_KEYS = ("VOL_KEY", "VOL", "TITLE", "VOL_TITLE", "SUBTITLE", "PROD_DAY", "ISSUANCE", "CNTS_CNT", "TEXT_CNT", "ACQ_CONTENTS_CNT", "ACQUISIT_CODE", "ACQ_STATUS", "CLASS_NO", "REG_DT", "REG_ER_ID")


def wdir(wonbu: str) -> Path:
    d = mb.WORK / f"wonbu_{wonbu}"; d.mkdir(parents=True, exist_ok=True); return d


def _page_post(pg):
    def post(path, form):
        try:
            r = pg.request.post(BASE + path, headers=H, form=form)
            return (r.json() or {}) if r.ok else {}
        except Exception:  # noqa: BLE001
            return {}
    return post


def _detail(post, key) -> dict:
    for stat in ("30", "20", ""):
        d = (post("/online/cmmn/getOnSpecView.do", {"species_key": str(key), "har_stat_cd": stat}) or {}).get("data")
        if d and d.get("TITLE"):
            return {k: d.get(k) for k in DETAIL_KEYS if d.get(k) not in (None, "")}
    return {}


def _volumes(post, key) -> list[dict]:
    lst = (post("/online/cmmn/listVolumn.do", {"species_key": str(key), "har_stat_cd": "30"}) or {}).get("list") or []
    return [{k: v.get(k) for k in VOL_KEYS if v.get(k) not in (None, "")} for v in lst]


class _NoRec:
    def _rec(self, *a, **k):
        pass


def gather(wonbu: str, rows: list[dict], log=print, b: Browser | None = None, post=None) -> Path:
    """복본조사 결과 표 → 판정용 작업 파일. 조회 요청만 보낸다. post(path, form)->dict 를 주면(요청 방식) 브라우저 없이 한다."""
    own = b is None and post is None
    if own:
        b = Browser(log); b.login()
    if post is None:
        post = _page_post(b.page)
    rec = b if b is not None else _NoRec()
    try:
        ours, pairs, cur = [], [], None
        for r in rows:
            if str(r.get("ORIGIN_YN")) == "V":
                cur = r; ours.append(r); continue
            if cur is not None:
                pairs.append((cur, r))
        cand_keys = sorted({str(c.get("REC_KEY")) for _, c in pairs})
        log(f"복본 판정 자료 모으기: 우리 {len(ours)}종, 후보 종 {len(cand_keys)}개(짝 {len(pairs)}) — 종 상세·권 목록 조회")
        details = {}
        for k in cand_keys + [str(o.get("REC_KEY")) for o in ours]:
            if k not in details:
                details[k] = {"detail": _detail(post, k), "volumes": _volumes(post, k)}
        job = {
            "wonbu": wonbu,
            "title": (ours[0] or {}).get("TITLE") if ours else "",
            "ours": [{"row_key": str(o.get("REC_KEY")), "ident": o.get("IDENT_MARK"), "table_row": {k: o.get(k) for k in ("TITLE", "AUTHOR", "PUBLISHER", "PUBLISH_YEAR", "TYPEOFRESOURCE", "CNTS_COUNT", "ACCESSION_NO")},
                      **details.get(str(o.get("REC_KEY")), {})} for o in ours],
            "candidates": [{"rec_key": k, **details.get(k, {})} for k in cand_keys],
            "pairs": [{"our_key": str(o.get("REC_KEY")), "cand_key": str(c.get("REC_KEY")), "table_row": {k: c.get(k) for k in ("TITLE", "AUTHOR", "PUBLISHER", "PUBLISH_YEAR", "TYPEOFRESOURCE", "CNTS_COUNT")}} for o, c in pairs],
        }
        p = wdir(wonbu) / "dup_job.json"; p.write_text(json.dumps(job, ensure_ascii=False, indent=1), encoding="utf-8")
        rec._rec("gather", what="복본 판정 자료", ours=len(ours), candidates=len(cand_keys), pairs=len(pairs), file=str(p))
        return p
    finally:
        if own and b is not None:
            b.close()


def run(wonbu: str, log=print, model: str | None = None, handle: dict | None = None) -> tuple[dict, list[str], Path]:
    from . import agent, checks
    jp = wdir(wonbu) / "dup_job.json"
    job = json.loads(jp.read_text(encoding="utf-8"))
    result, fails, jd = agent.run_job("judge-duplicates", f"dup_{wonbu}", job, "dup_build.json", lambda p: checks.check_dup(p, p.with_name("job.json")), log=log, model=model, handle=handle, timeout=1800)
    out = jp.with_name("dup_build.json"); out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    v = [p.get("verdict") for p in result.get("pairs") or []]
    log(f"복본 판정 끝: 짝 {len(v)} — 복본 {v.count('dup')} · 아님 {v.count('not')} · 판단 불가 {v.count('unsure')} | 남은 걸린 항목 {len(fails)}")
    return result, fails, out


def dup_rows(result: dict, rows: list[dict]) -> list[int]:
    """판정 결과(복본)를 결과 표의 행 번호로 바꾼다(_chk 를 켤 행)."""
    dup_pairs = {(p.get("our_key"), p.get("cand_key")) for p in result.get("pairs") or [] if p.get("verdict") == "dup"}
    out, cur = [], None
    for i, r in enumerate(rows):
        if str(r.get("ORIGIN_YN")) == "V":
            cur = str(r.get("REC_KEY")); continue
        if (cur, str(r.get("REC_KEY"))) in dup_pairs:
            out.append(i)
    return out
