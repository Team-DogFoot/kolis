"""③구간 5.3 MODS 구축 — 작품 단위 판단(2026-10-03 유저 확정: "작품 하나 = AI 판단 한 번").
흐름: collect_work(원부) — 유저 Edge 창에서 디지털콘텐츠관리 목록의 회차마다 MODS 수정 화면을 열어 값만 읽고 닫는다(바꾸지 않음) → 작업 파일 하나(work/build/wonbu_<번호>/job.json)
      run_work_agent — 스킬 build-mods-work 로 AI 판단 한 번 → build.json(공통 판단 + 회차별 판단)
      episode_build — 회차 하나의 판단을 mods_build.apply 가 쓰는 꼴로 뽑는다(채우기는 회차별, 저장은 사람).
      status — 원부의 전체 회차 상태(판단 전 / 판단 끝 / 채움 / 저장).
동시성은 작품 단위: 여러 원부의 run_work_agent 를 동시에 돌린다(에이전트 한도는 agent.MAX 가 아니라 app 의 세마포어). Edge 를 쓰는 collect 는 한 번에 하나.
기록: wonbu_<번호>/batch.jsonl 에 단계마다 시작·끝·걸린 시간·결과 요약.
"""
from __future__ import annotations
import datetime, json, time
from pathlib import Path

from .kolis_browser import Browser, BASE
from . import mods_build as mb

WORK = mb.WORK


def wdir(wonbu: str) -> Path:
    d = WORK / f"wonbu_{wonbu}"; d.mkdir(parents=True, exist_ok=True); return d


def _note(wonbu: str, **row):
    row = {"time": f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S}", **row}
    with open(wdir(wonbu) / "batch.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


# ---------------------------------------------------------------- 1) 화면 값 읽기(전체 회차, 바꾸지 않음)
def _close_popups(b: Browser):
    keep = next((p for p in b.ctx.pages if "onlineDigitalContMng" in p.url and not p.is_closed()), None) or next((p for p in b.ctx.pages if not p.is_closed()), b.page)
    b.page = keep
    for part in ("onContentsDetailPop", "onSpecViewPop"):
        for pg in mb._pages(b, part):
            try:
                pg.close()
            except Exception:  # noqa: BLE001
                pass
    b.wait(0.4)


def _rd_json(p: Path) -> dict:
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _import_for(wonbu: str) -> dict | None:
    """탭 상태(작업 폴더 ↔ 원부번호)로 1단계 결과를 찾는다: {"path": import.json 경로, "observations_dir": …}. 2026-10-04 반입값이 정본."""
    d = _rd_json(Path("work/tabs.json"))
    for t in d.get("tabs") or []:
        if str(t.get("wonbu") or "").strip() == str(wonbu) and t.get("folder"):
            from . import prepare
            w = prepare.load(Path(t["folder"]), Path("work")) or {}
            jd = Path((w.get("run") or {}).get("job_dir") or "")
            if jd.is_dir() and (jd / "import.json").exists():
                return {"path": str(jd / "import.json"), "observations_dir": str(jd / "observations") if (jd / "observations").is_dir() else None}
    return None


def collect_work(wonbu: str, log=print, manuscript: str | None = None, instructions: str = "", rows: list[int] | None = None) -> Path:
    """디지털콘텐츠관리 목록의 회차 전부(또는 rows)를 돌며 MODS 수정 화면 값을 읽는다. 전거 후보는 저자 이름마다 한 번만 조회."""
    mb._LOG[0] = log
    t0 = time.time(); _note(wonbu, step="collect", status="start")
    b = Browser(log); b.login()
    try:
        _close_popups(b)
        main, n = mb.open_digitalcont(b, wonbu)
        if n <= 0:
            raise SystemExit(f"디지털콘텐츠관리에 원부 {wonbu} 가 없습니다(복본조사 완료 전이면 보이지 않음)")
        listing = main.evaluate("(()=>{var o=[];for(var i=0;i<grid.getRowsCount();i++){var r=$('#jqxgrid').jqxGrid('getrowdata',i);o.push({row:i,TITLE:r.TITLE,VOL:r.VOL,SPECIES_KEY:r.SPECIES_KEY,ACCESSION_NO:r.ACCESSION_NO});}return o;})()")
        (wdir(wonbu) / "episodes.json").write_text(json.dumps(listing, ensure_ascii=False, indent=1), encoding="utf-8")
        log(f"원부 {wonbu}: 회차 {n}건 — 화면 값을 하나씩 읽습니다(바꾸지 않음)")
        episodes, cand_cache, authors_all = [], {}, []
        for item in listing:
            i = item["row"]
            if rows is not None and i not in rows:
                continue
            t1 = time.time()
            _close_popups(b); b.page = main
            mods, info = mb.open_mods(b, wonbu, i)
            cnts = mb.contents_id(mods)
            form = mb.read_form(mods)
            d = WORK / cnts; d.mkdir(parents=True, exist_ok=True)
            (d / "form.json").write_text(json.dumps(form, ensure_ascii=False, indent=1), encoding="utf-8")
            val = {f["name"]: f["value"] for f in form if f["value"]}
            authors = mb.authors_from(form)
            for a in authors:
                if a["name"] not in cand_cache:
                    cand_cache[a["name"]] = mb.search_authority(b, mods, a["name"], cnts)
                    log(f"전거 후보 '{a['name']}': {len(cand_cache[a['name']])}건")
            ep = {"row": i, "contents_id": cnts, "title": val.get("_titleInfo_title", ""), "part": val.get("_titleInfo_partNumber", ""),
                  "date": val.get("_originInfo_dateIssued", ""), "isbn": val.get("_identifier", ""), "publisher": val.get("_originInfo_publisher", ""),
                  "place": val.get("_originInfo_place_placeTerm", ""), "urls": [f["value"] for f in form if f["name"] == "_location_url" and f["value"]],
                  "notes": [f["value"] for f in form if f["name"] == "_note" and f["value"]],
                  "authors": [{"name": a["name"], "role": a["role"], "type": a["type"], "current_id": a["current_id"]} for a in authors],
                  "subject_topics": [f["value"] for f in form if f["name"] == "_subject_topic" and f["value"]],
                  "form": [{"name": f["name"], "value": f["value"]} for f in form if f["value"]]}
            episodes.append(ep)
            for a in authors:
                if a["name"] not in [x["name"] for x in authors_all]:
                    authors_all.append({"name": a["name"], "role": a["role"], "type": a["type"], "current_id": a["current_id"], "candidates": cand_cache[a["name"]]})
            _note(wonbu, step="collect", status="episode", row=i, contents_id=cnts, seconds=round(time.time() - t1, 1))
            log(f"  {i + 1}/{n} {cnts} 읽음 ({time.time() - t1:.0f}초)")
        _close_popups(b)
        first = episodes[0] if episodes else {}
        imp = _import_for(wonbu)
        diffs = _rd_json(wdir(wonbu) / "compare.json").get("diffs") if (wdir(wonbu) / "compare.json").exists() else None
        job = {"wonbu": wonbu, "title": first.get("title", ""), "count": len(episodes), "project": mb.settings(), "instructions": instructions, "manuscript": manuscript,
               "import_json": imp.get("path") if imp else None, "observations_dir": imp.get("observations_dir") if imp else None, "diffs": diffs,
               "authors": authors_all,
               "common": {"publisher": first.get("publisher", ""), "place": first.get("place", ""), "dates": sorted({e["date"] for e in episodes if e["date"]}),
                          "subject_topics": first.get("subject_topics", []), "urls": first.get("urls", [])},
               "episodes": episodes}
        p = wdir(wonbu) / "job.json"; p.write_text(json.dumps(job, ensure_ascii=False, indent=1), encoding="utf-8")
        _note(wonbu, step="collect", status="done", episodes=len(episodes), seconds=round(time.time() - t0, 1))
        log(f"작업 파일: {p} (회차 {len(episodes)}, 저자 {[(a['name'], len(a['candidates'])) for a in authors_all]}, {time.time() - t0:.0f}초)")
        return p
    finally:
        b.close()


# ---------------------------------------------------------------- 2) 작품 단위 AI 판단
def run_work_agent(wonbu: str, log=print, model: str | None = None, handle: dict | None = None) -> tuple[dict, list[str], Path]:
    from . import agent, checks
    jp = wdir(wonbu) / "job.json"
    job = json.loads(jp.read_text(encoding="utf-8"))
    t0 = time.time(); _note(wonbu, step="agent", status="start", episodes=job.get("count"))
    result, fails, jd = agent.run_job("build-mods-work", f"work_{wonbu}", job, "build.json", lambda p: checks.check_build_work(p, p.with_name("job.json")), log=log, model=model, handle=handle, timeout=3000)
    out = jp.with_name("build.json"); out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    _note(wonbu, step="agent", status="done", seconds=round(time.time() - t0, 1), remaining=fails,
          authors=[(a.get("name"), a.get("decision"), a.get("confidence")) for a in result.get("authors") or []],
          episodes=len(result.get("episodes") or []))
    for e in result.get("episodes") or []:
        d = WORK / e.get("contents_id", "x"); d.mkdir(parents=True, exist_ok=True)
        st_p = d / "state.json"; st = json.loads(st_p.read_text(encoding="utf-8")) if st_p.exists() else {}
        st.update({"wonbu": wonbu, "contents_id": e.get("contents_id"), "part": e.get("part"), "title": result.get("title") or job.get("title"), "judged_at": f"{datetime.datetime.now():%Y-%m-%d %H:%M}", "work_build": str(out)})
        for ep in job.get("episodes") or []:
            if ep.get("contents_id") == e.get("contents_id"):
                st["row"] = ep.get("row")
        st_p.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"작품 판단 끝: {out} ({time.time() - t0:.0f}초) | 남은 걸린 항목 {len(fails)}건")
    return result, fails, out


# ---------------------------------------------------------------- 3) 회차 하나의 판단을 채우기용으로
def episode_build(work: dict, cnts: str) -> dict:
    ep = next((e for e in work.get("episodes") or [] if e.get("contents_id") == cnts), None)
    if ep is None:
        raise SystemExit(f"작품 판단에 {cnts} 회차가 없습니다")
    authors = []
    for a in work.get("authors") or []:
        alts = [x for x in (ep.get("alternative_names") or []) if x.get("author") == a.get("name")]
        authors.append({**a, "alternative_names": alts})
    return {"contents_id": cnts, "title": work.get("title"), "part": ep.get("part"), "authors": authors, "subjects": work.get("subjects") or [],
            "uci": ep.get("uci") or {}, "publisher": work.get("publisher") or {}, "place": work.get("place") or {},
            "issues": (work.get("issues") or []) + (ep.get("issues") or []), "notes_for_staff": (work.get("notes_for_staff") or []) + (ep.get("notes") or []),
            "review": work.get("review") or {}}


def fill(wonbu: str, row: int, log=print) -> dict:
    """회차 하나: 작품 판단에서 그 회차 판단을 꺼내 KOLIS 화면을 열고 채운다(저장 안 함)."""
    mb._LOG[0] = log
    work = json.loads((wdir(wonbu) / "build.json").read_text(encoding="utf-8"))
    job = json.loads((wdir(wonbu) / "job.json").read_text(encoding="utf-8"))
    b = Browser(log); b.login()
    try:
        _close_popups(b)
        mods, info = mb.open_mods(b, wonbu, row)
        cnts = mb.contents_id(mods)
        build = episode_build(work, cnts)
        ep_job = {"contents_id": cnts, "authors": [{**a, "index": i} for i, a in enumerate(job.get("authors") or [])]}
        # mods_build.apply 는 build.json / job.json 파일 경로를 받으므로 회차 폴더에 써 둔다
        d = WORK / cnts; d.mkdir(parents=True, exist_ok=True)
        (d / "build.json").write_text(json.dumps(build, ensure_ascii=False, indent=1), encoding="utf-8")
        (d / "job.json").write_text(json.dumps({**ep_job, "manuscript": job.get("manuscript"), "project": job.get("project")}, ensure_ascii=False, indent=1), encoding="utf-8")
        before = mb.read_form(mods)
        ap = mb.apply(b, mods, d / "build.json")
        after = mb.read_form(mods)
        # 입출력 기록(자동화·A-1 앞당기기 재료): 판단 입력(후보 전부와 고른 것) → 화면 전·후 값 → 바뀐 칸
        key = lambda f: (f.get("name"), f.get("id"))
        bm = {key(f): f for f in before}; changed = []
        for f in after:
            o = bm.get(key(f))
            if o is None or o.get("value") != f.get("value"):
                changed.append({"name": f.get("name"), "id": f.get("id"), "before": (o or {}).get("value"), "after": f.get("value")})
        io = {"contents_id": cnts, "wonbu": wonbu, "row": row, "at": f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S}",
              "decisions": {"authors": [{"name": a.get("name"), "decision": a.get("decision"), "chosen": a.get("ac_control_no"), "confidence": a.get("confidence"),
                                         "candidates": [{k: v for k, v in c.items() if v not in (None, "")} for c in (next((j.get("candidates") for j in job.get("authors") or [] if j.get("name") == a.get("name")), None) or [])]}
                                        for a in build.get("authors") or []],
                            "publisher": build.get("publisher"), "place": build.get("place"), "subjects": build.get("subjects"), "uci": build.get("uci"), "adult": work.get("adult")},
              "form_before": before, "form_after": after, "changed": changed, "apply": ap}
        (d / "fill_io.json").write_text(json.dumps(io, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        b._rec("fill_io", contents_id=cnts, changed=len(changed), file=str(d / "fill_io.json"))
        log(f"입출력 기록: 바뀐 칸 {len(changed)}개 → {d / 'fill_io.json'}")
        st_p = d / "state.json"; st = json.loads(st_p.read_text(encoding="utf-8")) if st_p.exists() else {}
        st.update({"wonbu": wonbu, "row": row, "contents_id": cnts, "title": build.get("title"), "part": build.get("part"), "applied_at": f"{datetime.datetime.now():%Y-%m-%d %H:%M}", "saved_at": st.get("saved_at")})
        st_p.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
        _note(wonbu, step="fill", status="done", row=row, contents_id=cnts)
        return {**mb.summary(build, {"authors": job.get("authors") or []}), "apply": ap, "build_path": str(d / "build.json"), "dir": str(d), "state": st}
    finally:
        b.close()


# ---------------------------------------------------------------- 4) 상태
def status(wonbu: str) -> list[dict]:
    """원부의 전체 회차(episodes.json 기준; 없으면 처리한 회차만)와 상태."""
    d = wdir(wonbu)
    listing = json.loads((d / "episodes.json").read_text(encoding="utf-8")) if (d / "episodes.json").exists() else []
    states = {}
    for f in WORK.glob("*/state.json"):
        try:
            st = json.loads(f.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if str(st.get("wonbu")) == str(wonbu) and st.get("contents_id"):      # 원부 폴더(wonbu_<n>)의 state.json 은 회차가 아니다
            states[st.get("contents_id")] = st
    work_build = (d / "build.json").exists()
    judged = {e.get("contents_id") for e in (json.loads((d / "build.json").read_text(encoding="utf-8")).get("episodes") or [])} if work_build else set()
    out = []
    if listing:
        job_eps = {e["row"]: e for e in (json.loads((d / "job.json").read_text(encoding="utf-8")).get("episodes") or [])} if (d / "job.json").exists() else {}
        for item in listing:
            cnts = (job_eps.get(item["row"]) or {}).get("contents_id") or next((c for c, s in states.items() if s.get("row") == item["row"]), None)
            st = states.get(cnts, {})
            stage = "saved" if st.get("saved_at") else "filled" if st.get("applied_at") else "judged" if (cnts in judged or st.get("judged_at")) else "todo"
            out.append({"row": item["row"], "title": item.get("TITLE"), "part": item.get("VOL"), "contents_id": cnts, "stage": stage, "body_ready": bool(cnts) and (WORK / str(cnts) / "save_body.json").exists(),
                        "applied_at": st.get("applied_at"), "saved_at": st.get("saved_at"), "judged_at": st.get("judged_at")})
    else:
        for cnts, st in states.items():
            stage = "saved" if st.get("saved_at") else "filled" if st.get("applied_at") else "judged" if st.get("judged_at") else "todo"
            out.append({"row": st.get("row", 0), "title": st.get("title"), "part": st.get("part"), "contents_id": cnts, "stage": stage,
                        "applied_at": st.get("applied_at"), "saved_at": st.get("saved_at"), "judged_at": st.get("judged_at")})
    return sorted(out, key=lambda x: x.get("row", 0))


def set_author_decision(wonbu: str, name: str, ac_control_no: str, signpost: str = "", reason: str = "") -> dict:
    """직원 결정: 작품 판단(build.json)의 저자 하나를 '연결(전거 번호)'로 바꾼다(source: staff). 빈 번호면 '연결 안 함'으로."""
    p = wdir(wonbu) / "build.json"
    w = json.loads(p.read_text(encoding="utf-8"))
    hit = None
    for a in w.get("authors") or []:
        if a.get("name") == name:
            hit = a
            if ac_control_no:
                a.update({"decision": "link", "ac_control_no": ac_control_no, "choice_signpost": signpost or name, "source": "staff", "confidence": "high", "staff_reason": reason or "직원이 확인해 연결"})
            else:
                a.update({"decision": "none", "ac_control_no": "", "source": "staff", "staff_reason": reason or "직원이 연결하지 않기로 함"})
    if hit is None:
        raise SystemExit(f"작품 판단에 저자 '{name}' 이 없습니다")
    p.write_text(json.dumps(w, ensure_ascii=False, indent=1), encoding="utf-8")
    _note(wonbu, step="staff_decision", author=name, ac_control_no=ac_control_no, reason=reason)
    return hit


def prepare_bodies(wonbu: str, rows: list[int], log=print, handle: dict | None = None) -> dict:
    """「한 번에 입력」의 앞 절반(보내지 않음): 회차마다 MODS 수정 화면을 열어 작품 판단대로 채우고, 화면의 저장 함수가 만드는 요청 본문을 가로채
    work/build/CNTS-…/save_body.json 에 둔다. 1화의 실제 저장 본문(기록)과 꼴을 견주어 확인한 뒤에야 보내는 단계를 만든다."""
    mb._LOG[0] = log
    work = json.loads((wdir(wonbu) / "build.json").read_text(encoding="utf-8"))
    job = json.loads((wdir(wonbu) / "job.json").read_text(encoding="utf-8"))
    b = Browser(log); b.login()
    out = []
    try:
        for row in rows:
            if (handle or {}).get("cancel"):
                break
            _close_popups(b)
            mods, info = mb.open_mods(b, wonbu, row)
            cnts = mb.contents_id(mods)
            build = episode_build(work, cnts)
            d = WORK / cnts; d.mkdir(parents=True, exist_ok=True)
            (d / "build.json").write_text(json.dumps(build, ensure_ascii=False, indent=1), encoding="utf-8")
            (d / "job.json").write_text(json.dumps({"contents_id": cnts, "authors": [{**a, "index": i} for i, a in enumerate(job.get("authors") or [])], "manuscript": job.get("manuscript"), "project": job.get("project")}, ensure_ascii=False, indent=1), encoding="utf-8")
            before_xml = mb.fetch_xml(mods, cnts); (d / "mods_before.xml").write_text(before_xml, encoding="utf-8")
            ap = mb.apply(b, mods, d / "build.json")
            body = mb.capture_save_body(b, mods)
            (d / "save_body.json").write_text(json.dumps({"contents_id": cnts, "row": row, "at": f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S}", "url": "/online/contents/updateHarContents.do", "fields": body, "apply": ap}, ensure_ascii=False, indent=1), encoding="utf-8")
            xp = str(body.get("inputedXpath", "")).split(","); vals = str(body.get("inputedElemValue", "")).split(",")
            summary = {"contents_id": cnts, "row": row, "fields": len(body), "xpaths": len(xp), "values": len(vals), "has_comma_mark": "▲COMMA▲" in str(body.get("inputedElemValue", "")),
                       "name_ids": [v for x, v in zip(xp, vals) if x == "/mods/name@ID" and v], "subject_ids": [v for x, v in zip(xp, vals) if x == "/mods/subject@ID" and v], "file": str(d / "save_body.json")}
            log(f"저장 본문 준비(보내지 않음) {cnts}: 칸 {summary['fields']} · 경로 {summary['xpaths']} · 전거 {summary['name_ids']} · 주제명 {summary['subject_ids']}")
            _note(wonbu, step="prepare_body", **summary)
            out.append(summary)
            mods.close()
        return {"wonbu": wonbu, "rows": out}
    finally:
        b.close()


# 저장 뒤 KOLIS 가 스스로 바꾸는 요소(10-01·10-03 관찰). 전·후 대조에서 "의도한 변화"로 친다.
AUTO_CHANGED = ("internetMediaType", "digitalOrigin", "accessCondition", "recordChangeDate", "recordIdentifier", "useObjCode", "dateIssued", "publisher", "typeOfResource", "genre", "reformattingQuality")
INTENDED = ("name", "subject", "identifier", "alternativeName", "displayForm", "namePart", "topic", "genre")


def _mods_sig(xml_text: str) -> dict:
    """XML → {경로+속성: 값} (대조용). 반복 요소는 순서 번호를 붙인다."""
    import xml.etree.ElementTree as ET
    out = {}
    if not xml_text:
        return out
    root = ET.fromstring(xml_text)
    def walk(e, path, counts):
        tag = e.tag.split("}")[1]
        n = counts.get((path, tag), 0); counts[(path, tag)] = n + 1
        here = f"{path}/{tag}[{n}]"
        for k, v in e.attrib.items():
            out[f"{here}@{k}"] = v
        if (e.text or "").strip():
            out[here] = e.text.strip()
        sub = {}
        for c in e:
            walk(c, here, sub)
    walk(root, "", {})
    return out


def diff_xml(before: str, after: str) -> dict:
    a, b = _mods_sig(before), _mods_sig(after)
    changed = sorted(set(a) ^ set(b) | {k for k in a if k in b and a[k] != b[k]})
    intended = [k for k in changed if any(f"/{t}[" in k for t in INTENDED)]
    auto = [k for k in changed if k not in intended and any(f"/{t}[" in k or k.endswith(t) for t in AUTO_CHANGED)]
    other = [k for k in changed if k not in intended and k not in auto]
    return {"changed": len(changed), "intended": intended, "auto": auto, "other": [{"path": k, "before": a.get(k), "after": b.get(k)} for k in other]}


def send_bodies(wonbu: str, rows: list[int], log=print, handle: dict | None = None, stop_on_other: bool = True) -> dict:
    """「n건에 한 번에 넣기」(⑥): 미리 가로채 둔 저장 본문(save_body.json)을 콘텐츠마다 KOLIS 세션으로 보내고, 전·후 XML 을 대조한다.
    첫 1건을 보내고 대조해 **의도하지 않은 변화(other)가 있으면 멈춘다**(stop_on_other). 되돌릴 수 없으므로 사람이 단추를 눌렀을 때만 부른다."""
    from urllib.parse import urlencode
    mb._LOG[0] = log
    b = Browser(log); b.login()
    out = []
    try:
        pg = b.page
        for i, row in enumerate(rows, 1):
            if (handle or {}).get("cancel"):
                break
            ep = next((e for e in json.loads((wdir(wonbu) / "episodes.json").read_text(encoding="utf-8")) if e.get("row") == row), None)
            job_eps = {e["row"]: e for e in (json.loads((wdir(wonbu) / "job.json").read_text(encoding="utf-8")).get("episodes") or [])}
            cnts = (job_eps.get(row) or {}).get("contents_id")
            d = WORK / str(cnts)
            bp = d / "save_body.json"
            if not cnts or not bp.exists():
                out.append({"row": row, "ok": False, "error": "저장 본문이 준비되지 않았습니다(먼저 「저장 본문 준비」)"}); continue
            body = json.loads(bp.read_text(encoding="utf-8"))
            fields = body["fields"]
            before = pg.request.post(BASE + "/online/contents/popup/getHarContentsXml.do", form={"contentsId": cnts}).json().get("mods_xml") or ""
            (d / "mods_before.xml").write_text(before, encoding="utf-8")
            flat = {k: (v[0] if isinstance(v, list) else v) for k, v in fields.items()}
            log(f"── {cnts} ({i}/{len(rows)}) 저장 요청 보냄(updateHarContents, 칸 {len(flat)})")
            b._rec("http", method="POST", url="/online/contents/updateHarContents.do", post=urlencode(flat), approved=True, changes=True, note="한 번에 입력")
            r = pg.request.post(BASE + "/online/contents/updateHarContents.do", form=flat, headers={"X-Requested-With": "XMLHttpRequest"})
            txt = r.text(); ok = r.ok and '"sttus":"success"' in txt
            after = pg.request.post(BASE + "/online/contents/popup/getHarContentsXml.do", form={"contentsId": cnts}).json().get("mods_xml") or ""
            (d / "mods_after.xml").write_text(after, encoding="utf-8")
            dv = diff_xml(before, after)
            xml_ok = "KSH2016000049" in after and "KSH1998022212" in after
            st_p = d / "state.json"; st = json.loads(st_p.read_text(encoding="utf-8")) if st_p.exists() else {"wonbu": wonbu, "row": row, "contents_id": cnts}
            st.update({"saved_at": f"{datetime.datetime.now():%Y-%m-%d %H:%M}" if ok else st.get("saved_at"), "xml_ok": xml_ok, "save_mode": "request", "diff": {"changed": dv["changed"], "other": len(dv["other"])}})
            st_p.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
            rec = {"row": row, "contents_id": cnts, "ok": ok, "status": r.status, "response": txt[:200], "xml_ok": xml_ok, "diff": dv}
            _note(wonbu, step="send_body", **{k: v for k, v in rec.items() if k != "diff"}, changed=dv["changed"], other=len(dv["other"]))
            log(f"   응답 {r.status} {'성공' if ok else '실패'} · 바뀐 요소 {dv['changed']}(의도 {len(dv['intended'])} · KOLIS 자동 {len(dv['auto'])} · 그 밖 {len(dv['other'])}) · 주제명 2묶음 {'확인' if xml_ok else '없음!'}")
            out.append(rec)
            if not ok or (stop_on_other and dv["other"]):
                log("!!! 멈춥니다: " + ("저장 실패" if not ok else f"의도하지 않은 변화 {len(dv['other'])}곳 — {dv['other'][:3]}"))
                break
        return {"wonbu": wonbu, "rows": out}
    finally:
        b.close()

