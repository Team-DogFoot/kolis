"""B 단계(원부번호 이후) — 2026-10-04 새 설계. 반입값(1단계 import.json)이 정본이다.

흐름(작품 탭의 B):
  B-1 상태   : 원부번호 → 등록원부관리·디지털콘텐츠관리를 요청으로 읽어 건수·작업상태·종·콘텐츠 목록. 복본조사·일괄변경이 끝났는지(과장님 탭에서 함).
  B-2 대조   : 콘텐츠마다 MODS XML(요청) → 트리 → 반입값과 경로 단위 대조. KOLIS 가 스스로 바꾸는 값은 '다름'이 아니다.
  B-3 보정   : 다른 칸마다 직원이 값을 고른다(반입값 / KOLIS 값 / 직접 입력). 고른 것만 KOLIS 화면에 넣고(Edge, 가이드 메뉴 순서) 화면의 저장 함수를 가로채
               저장 본문을 만들어 보낸 뒤 전·후 XML 을 대조한다(의도한 칸 밖이 바뀌면 멈춤). 저장은 사람이 누른다.
  B-4 이용제한: 1단계가 성인물로 판단했으면 종마다 「청소년 유해매체물」(브라우저 사실 층 build_prep.use_limit_adult).
사실 층(실서버에서 확인된 요청·화면 조작)은 dup_request·mods_build·build_prep 에 있고, 여기서는 그것만 쓴다. 흐름·판단·기록은 이 파일이 새로 한다.
기록: work/wonbu/<원부>/ (state.json, contents.json, xml/<CNTS>.xml, compare.json, fixes.json, fix_log.jsonl)
"""
from __future__ import annotations
import datetime, json, re
from pathlib import Path
from urllib.parse import urlencode

from . import kolis_http, dup_request, mods_xml, mods_sheet as ms

WORK = Path("work") / "wonbu"
FORM = "application/x-www-form-urlencoded; charset=UTF-8"


def wdir(wonbu: str) -> Path:
    d = WORK / str(wonbu); d.mkdir(parents=True, exist_ok=True); return d


def _now() -> str:
    return f"{datetime.datetime.now():%Y-%m-%d %H:%M}"


def _rd(p: Path, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {} if default is None else default


def _wr(p: Path, data) -> None:
    p.write_text(json.dumps(data, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


def state(wonbu: str) -> dict:
    return _rd(wdir(wonbu) / "state.json") or {"wonbu": wonbu}


def _patch(wonbu: str, **kw) -> dict:
    st = state(wonbu); st.update(kw); _wr(wdir(wonbu) / "state.json", st); return st


def _log(wonbu: str, **row) -> None:
    with (wdir(wonbu) / "fix_log.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"time": _now(), **row}, ensure_ascii=False, default=str) + "\n")


# ---------------------------------------------------------------- 1단계 결과 찾기(작업 폴더 ↔ 원부번호는 탭 상태)
def import_for(wonbu: str, work_dir: Path = Path("work")) -> dict | None:
    """{"folder", "import": 트리 결과, "rows": 직렬화기용 행, "observations_dir", "adult", "job_dir"} 또는 None."""
    from . import prepare, import_check
    d = _rd(work_dir / "tabs.json")
    for t in d.get("tabs") or []:
        if str(t.get("wonbu") or "").strip() == str(wonbu) and t.get("folder"):
            w = prepare.load(Path(t["folder"]), work_dir)
            if not w or not w.get("import"):
                continue
            imp = w["import"]
            jd = Path((w.get("run") or {}).get("job_dir") or "")
            try:
                rows = import_check.materialize(imp, Path(t["folder"]) if Path(t["folder"]).is_dir() else None)
            except Exception:  # noqa: BLE001
                rows = import_check.materialize(imp, None)
            return {"folder": t["folder"], "import": imp, "rows": rows, "adult": bool(imp.get("adult")), "adult_reason": imp.get("adult_reason") or "",
                    "observations_dir": str(jd / "observations") if (jd / "observations").is_dir() else None, "job_dir": str(jd) if jd.is_dir() else None, "title": w.get("title")}
    return None


# ---------------------------------------------------------------- B-1 상태(요청만)
def status(wonbu: str, log=print, work_dir: Path = Path("work")) -> dict:
    """등록원부관리 + 디지털콘텐츠관리 + 종/권/콘텐츠 목록. 바꾸지 않는다."""
    c = kolis_http.Client(log)
    try:
        c.login()
        ls = dup_request.ledger_status(c, wonbu)
        contents, species = [], []
        batch_ok = None; batch_values = {}
        if ls["acc_count"]:
            dc = dup_request.digitalcont(c, wonbu)
            for sp in dc.get("list") or []:
                sk = sp.get("SPECIES_KEY")
                species.append({"species_key": sk, "title": sp.get("TITLE"), "author": sp.get("AUTHOR"), "publisher": sp.get("PUBLISHER"), "use_limit": sp.get("USE_LIMIT_CODE"), "mods_updated": sp.get("MODS_UPDATE_DT") or sp.get("MODS_UPD_DT")})
                for v in dup_request.volumes(c, sk):
                    r = c.send("POST", "/online/contents/listVolContents.do", urlencode({"species_key": str(sk), "vol_key": str(v.get("VOL_KEY")), "har_stat_cd": "30", "issuance": "MO"}), FORM)
                    for x in r.get("list") or []:
                        contents.append({"species_key": sk, "vol_key": v.get("VOL_KEY"), "vol": x.get("VOL") or v.get("VOL"), "title": x.get("CONTENTS_NM") or sp.get("TITLE"), "contents_id": x.get("CONTENTS_ID"), "isbn": x.get("IDEN_ID")})
            if species:
                v0 = dup_request.spec_view(c, species[0]["species_key"])
                batch_values = {k: v0.get(k) for k in ("OFFER_DBCODE_1S", "OFFER_DBCODE_2S", "PUBLISHER_CODE", "KOGL_CODE", "USE_LIMIT_CODE", "USE_OBJ_CODE")}
                batch_ok = batch_values["OFFER_DBCODE_1S"] == "CH1" and batch_values["OFFER_DBCODE_2S"] == "CH11" and batch_values["PUBLISHER_CODE"] == "PE"
        contents.sort(key=lambda x: (len(str(x.get("vol") or "")), str(x.get("vol") or "")))
    finally:
        c.close()
    imp = import_for(wonbu, work_dir)
    _wr(wdir(wonbu) / "contents.json", {"species": species, "contents": contents})
    st = _patch(wonbu, title=ls.get("title") or (imp or {}).get("title"), acc_count=ls["acc_count"], kolis_status=ls["status"], dup_done=ls["dup_done"],
                batch_done=batch_ok, batch_values=batch_values, species=len(species), contents=len(contents), status_at=_now(),
                has_import=bool(imp), import_rows=len((imp or {}).get("rows") or []), adult=bool((imp or {}).get("adult")), adult_reason=(imp or {}).get("adult_reason") or "")
    log(f"원부 {wonbu}: 등록원부관리 {ls['acc_count']}건 {', '.join(ls['status'])} · 종 {len(species)} · 콘텐츠 {len(contents)} · 복본조사 {'끝' if ls['dup_done'] else '전'} · 일괄변경 {'끝' if batch_ok else ('전' if batch_ok is False else '모름')} · 반입값 {'있음' if imp else '없음'}")
    return {**st, "contents_list": contents}


# ---------------------------------------------------------------- B-2 대조(요청만)
def fetch_xml(c: kolis_http.Client, cnts: str) -> str:
    r = c.send("POST", "/online/contents/popup/getHarContentsXml.do", urlencode({"contentsId": cnts}), FORM)
    return r.get("mods_xml") or ""


def fetch_all(wonbu: str, log=print, client: kolis_http.Client | None = None) -> list[dict]:
    """콘텐츠마다 MODS XML 을 받아 work/wonbu/<원부>/xml/ 에 둔다(KOLIS 가 주는 그대로). 돌려주는 것: [{contents_id, vol, title, xml, path}]."""
    cj = _rd(wdir(wonbu) / "contents.json")
    items = cj.get("contents") or []
    if not items:
        raise SystemExit("콘텐츠 목록이 없습니다. 먼저 「원부 상태 읽기」를 하십시오")
    own = client is None
    c = client or kolis_http.Client(log)
    xd = wdir(wonbu) / "xml"; xd.mkdir(exist_ok=True)
    out = []
    try:
        if own:
            c.login()
        for i, it in enumerate(items, 1):
            x = fetch_xml(c, it["contents_id"])
            p = xd / f"{it['contents_id']}.xml"
            p.write_text(x, encoding="utf-8")
            out.append({**it, "xml": x, "path": str(p)})
            if i % 10 == 0 or i == len(items):
                log(f"  MODS 받기 {i}/{len(items)}")
    finally:
        if own:
            c.close()
    _patch(wonbu, xml_fetched_at=_now(), xml_count=len(out))
    return out


def _match_rows(rows: list[dict], items: list[dict]) -> dict[str, dict | None]:
    """콘텐츠 ↔ 반입 행 짝: ISBN → 권차 → 순서."""
    def isbn_of(r):
        for i in ms._lst((r.get("mods") or {}).get("identifier")):
            d = ms._node(i)
            if str(d.get("@type") or "").lower() == "isbn":
                return re.sub(r"\D", "", ms._text(d))
        return ""
    def part_of(r):
        t = ms._lst((r.get("mods") or {}).get("titleInfo"))
        return ms._text(ms._node(t[0]).get("partNumber")) if t else ""
    by_isbn = {isbn_of(r): r for r in rows if isbn_of(r)}
    by_part = {part_of(r): r for r in rows if part_of(r)}
    out = {}
    used = set()
    for k, it in enumerate(items):
        r = by_isbn.get(re.sub(r"\D", "", str(it.get("isbn") or ""))) or by_part.get(str(it.get("vol") or ""))
        if r is None and k < len(rows) and id(rows[k]) not in used:
            r = rows[k]
        if r is not None:
            used.add(id(r))
        out[it["contents_id"]] = r
    return out


def compare(wonbu: str, log=print, work_dir: Path = Path("work")) -> dict:
    """반입값(정본) ↔ KOLIS MODS. 반입값이 없으면(다른 담당자 반입) 회차끼리 공통 칸 대조."""
    imp = import_for(wonbu, work_dir)
    items = fetch_all(wonbu, log)
    trees = {it["contents_id"]: mods_xml.tree_from_xml(it["xml"]) for it in items}
    diffs, per = [], {}
    if imp:
        match = _match_rows(imp["rows"], items)
        for it in items:
            r = match.get(it["contents_id"])
            if r is None:
                diffs.append({"contents_id": it["contents_id"], "vol": it.get("vol"), "path": "(짝)", "label": "반입 행", "import": "", "kolis": str(it.get("vol") or ""), "kind": "diff", "note": "반입 행을 찾지 못했습니다"})
                continue
            d = mods_xml.diff(r.get("mods") or {}, trees[it["contents_id"]])
            for x in d:
                diffs.append({"contents_id": it["contents_id"], "vol": it.get("vol"), **x})
            per[it["contents_id"]] = {"diff": sum(1 for x in d if x["kind"] == "diff"), "auto": sum(1 for x in d if x["kind"] == "auto")}
        mode = "import"
    else:
        # 회차끼리 같아야 하는 최상위 요소
        common = ("titleInfo[0].title", "name", "originInfo[0].publisher", "originInfo[0].place", "targetAudience", "note", "subject", "accessCondition")
        flats = {k: mods_xml.flat(v) for k, v in trees.items()}
        for key in common:
            vals: dict[str, list[str]] = {}
            for cid, f in flats.items():
                sig = json.dumps({p: v for p, v in f.items() if p == key or p.startswith(key + ".") or p.startswith(key + "[")}, ensure_ascii=False, sort_keys=True)
                vals.setdefault(sig, []).append(cid)
            if len(vals) > 1:
                major = max(vals.items(), key=lambda kv: len(kv[1]))
                for sig, cids in vals.items():
                    if sig == major[0]:
                        continue
                    for cid in cids:
                        it = next(x for x in items if x["contents_id"] == cid)
                        diffs.append({"contents_id": cid, "vol": it.get("vol"), "path": key, "label": mods_xml.label_for(key.split("[")[0]), "import": "", "kolis": sig[:200], "kind": "diff", "note": f"다른 회차 {len(major[1])}건과 다름"})
        mode = "consistency"
    real = [d for d in diffs if d["kind"] == "diff"]
    out = {"wonbu": wonbu, "mode": mode, "count": len(items), "import_rows": len((imp or {}).get("rows") or []), "diffs": diffs, "diff_count": len(real), "auto_count": len(diffs) - len(real), "per_contents": per, "at": _now()}
    _wr(wdir(wonbu) / "compare.json", out)
    _patch(wonbu, compared_at=_now(), diff_count=len(real), compare_mode=mode)
    log(f"대조: {len(items)}건 · 다른 칸 {len(real)} · KOLIS 자동 변경 {len(diffs) - len(real)}")
    return out


# ---------------------------------------------------------------- B-3 보정(직원이 고른 값만)
def fixes_set(wonbu: str, choices: list[dict]) -> dict:
    """choices: [{"contents_id", "path", "value", "source": "import|kolis|staff", "reason"}]. value 가 KOLIS 값과 같으면 보정 대상에서 뺀다."""
    cmp = _rd(wdir(wonbu) / "compare.json")
    kolis_now = {(d["contents_id"], d["path"]): d.get("kolis", "") for d in cmp.get("diffs") or []}
    fixes = _rd(wdir(wonbu) / "fixes.json") or {}
    for ch in choices:
        key = f"{ch['contents_id']}|{ch['path']}"
        if (ch.get("value") or "") == kolis_now.get((ch["contents_id"], ch["path"]), ""):
            fixes.pop(key, None)
        else:
            fixes[key] = {"contents_id": ch["contents_id"], "path": ch["path"], "xpath": mods_xml.xpath_of(ch["path"]), "value": ch.get("value") or "", "source": ch.get("source") or "staff", "reason": ch.get("reason") or "", "at": _now()}
    _wr(wdir(wonbu) / "fixes.json", fixes)
    _patch(wonbu, fixes=len(fixes))
    return {"fixes": list(fixes.values())}


def fixes_list(wonbu: str) -> list[dict]:
    return list((_rd(wdir(wonbu) / "fixes.json") or {}).values())


def _form_field_name(xpath: str) -> tuple[str, str | None]:
    """'/mods/name/namePart' → '_name_namePart', '/mods/name[@ID]' → ('_name', '@ID') (화면 칸 이름 규칙, RECON 4-1)."""
    m = re.fullmatch(r"(.*)\[@(\w+)\]", xpath)
    attr = None
    if m:
        xpath, attr = m.group(1), "@" + m.group(2)
    base = "_" + xpath.replace("/mods/", "").replace("/", "_")
    return (base + attr) if attr else base, attr


def _occurrence(tree: dict, path: str) -> int:
    """트리 경로(name[1].alternativeName[0].namePart)가 같은 xpath 의 몇 번째 등장인지(0부터) — 화면의 같은 이름 칸 순서와 같다."""
    xp = mods_xml.xpath_of(path)
    f = mods_xml.flat(tree)
    n = 0
    for p in f:
        if mods_xml.xpath_of(p) == xp:
            if p == path:
                return n
            n += 1
    return n


def fix_apply(wonbu: str, contents_ids: list[str], log=print, approved: bool = False, handle: dict | None = None) -> dict:
    """고른 보정값을 콘텐츠마다 KOLIS 화면에 넣고 → 저장 본문 가로채기 → (approved 일 때만) 보내기 → 전·후 XML 대조. 의도 밖 변화가 있으면 멈춘다.
    브라우저 사실 층: mods_build.open_mods / read_form / capture_save_body."""
    from . import mods_build as mb
    from .kolis_browser import Browser, BASE
    mb._LOG[0] = log
    fixes = fixes_list(wonbu)
    cj = _rd(wdir(wonbu) / "contents.json"); items = cj.get("contents") or []
    order = {it["contents_id"]: i for i, it in enumerate(items)}
    b = Browser(log); b.login()
    out = []
    try:
        for cid in contents_ids:
            if (handle or {}).get("cancel"):
                break
            my = [f for f in fixes if f["contents_id"] == cid]
            if not my:
                out.append({"contents_id": cid, "ok": False, "error": "보정값이 없습니다"}); continue
            row = order.get(cid)
            if row is None:
                out.append({"contents_id": cid, "ok": False, "error": "콘텐츠 목록에 없습니다"}); continue
            for part in ("onContentsDetailPop", "onSpecViewPop"):
                for pg in mb._pages(b, part):
                    pg.close()
            mods, info = mb.open_mods(b, wonbu, row)
            if mb.contents_id(mods) != cid:
                raise RuntimeError(f"열린 화면이 {mb.contents_id(mods)} 입니다(기대 {cid})")
            pg0 = b.ctx.pages[0]
            before_xml = pg0.request.post(BASE + "/online/contents/popup/getHarContentsXml.do", form={"contentsId": cid}).json().get("mods_xml") or ""
            tree_before = mods_xml.tree_from_xml(before_xml)
            changed = []
            for f in my:
                name, attr = _form_field_name(f["xpath"])
                idx = _occurrence(tree_before, f["path"])
                ok = mods.evaluate("""(a)=>{const els=[...document.querySelectorAll('#harContentsUpdateForm [name="'+a.name+'"]')]; const el=els[a.idx]; if(!el) return false; el.value=a.value; el.dispatchEvent(new Event('change',{bubbles:true})); return true;}""",
                                   {"name": name, "idx": idx, "value": f["value"]})
                changed.append({"path": f["path"], "field": name, "index": idx, "value": f["value"], "set": bool(ok)})
                if not ok:
                    log(f"  {cid}: 칸 {name}[{idx}] 를 화면에서 찾지 못했습니다(경로 {f['path']})")
            body = mb.capture_save_body(b, mods)
            _wr(wdir(wonbu) / f"save_body_{cid}.json", {"contents_id": cid, "fields": body, "changed": changed, "at": _now()})
            rec = {"contents_id": cid, "row": row, "changed": changed, "ok": all(x["set"] for x in changed), "sent": False}
            if approved and rec["ok"]:
                flat_body = {k: (v[0] if isinstance(v, list) else v) for k, v in body.items()}
                r = pg0.request.post(BASE + "/online/contents/updateHarContents.do", form=flat_body, headers={"X-Requested-With": "XMLHttpRequest"})
                txt = r.text(); sent_ok = r.ok and '"sttus":"success"' in txt
                after_xml = pg0.request.post(BASE + "/online/contents/popup/getHarContentsXml.do", form={"contentsId": cid}).json().get("mods_xml") or ""
                (wdir(wonbu) / "xml").mkdir(exist_ok=True)
                (wdir(wonbu) / "xml" / f"{cid}.before.xml").write_text(before_xml, encoding="utf-8")
                (wdir(wonbu) / "xml" / f"{cid}.xml").write_text(after_xml, encoding="utf-8")
                d = mods_xml.diff(tree_before, mods_xml.tree_from_xml(after_xml))
                intended = {f["path"] for f in my}
                other = [x for x in d if x["kind"] == "diff" and x["path"] not in intended]
                rec.update({"sent": True, "saved": sent_ok, "status": r.status, "diff_total": len(d), "other": other})
                _log(wonbu, step="fix_apply", contents_id=cid, saved=sent_ok, changed=changed, other=len(other))
                log(f"  {cid}: 저장 {'성공' if sent_ok else '실패'} · 바뀐 경로 {len(d)} · 의도 밖 {len(other)}")
                if not sent_ok or other:
                    out.append(rec); log("!!! 멈춥니다: " + ("저장 실패" if not sent_ok else f"의도하지 않은 변화 {len(other)}곳 {[o['path'] for o in other][:3]}")); break
            out.append(rec)
            if not mods.is_closed():
                mods.close()
        return {"wonbu": wonbu, "rows": out, "approved": approved}
    finally:
        b.close()


# ---------------------------------------------------------------- B-4 이용제한(성인물)
def use_limit(wonbu: str, log=print, approved: bool = True) -> dict:
    from . import build_prep
    r = build_prep.use_limit_adult(wonbu, log, approved)
    _patch(wonbu, use_limit_done=bool(r.get("done") == r.get("species")) or all(x.get("ok") or x.get("skipped") for x in r.get("results") or []), use_limit=r.get("results"), use_limit_at=_now())
    return r
