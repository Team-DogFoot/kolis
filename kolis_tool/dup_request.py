"""5.1 복본조사 · 완료 · 5.2 일괄변경을 **브라우저 없이 요청만으로**(2026-10-03 유저 지시: 요청 방식이 기본, 화면 방식은 대체).
요청 형식은 10-03 화면 방식 실행 기록(work/logs/browser-20261003.jsonl, 원부 1607·1610·1608)과 화면 스크립트(work/captures/pages/5-1_일괄복본조사/page.html)에서 그대로 옮겼다.

흐름(화면 스크립트와 같다):
  getDupExminList.do(원부) → REC_KEY 목록 → 건마다 dupExminProcBoCata.do(rec_key_arr 전부 + rec_key + ident_mark, 앞 응답의 ident_mark 를 이어 넘김) → 결과 행(우리 행 ORIGIN_YN=V, 후보 N)
  완료: getDropAccNoCnt.do(0 이어야 함) → dupExminComplete.do?type=A(검색 폼 그대로). 화면의 복본 체크(_chk)는 서버로 가지 않는다(화면 안에서만 쓰임).
  일괄변경: onlineDigitalContMngList.do → SPECIES_KEY 전부 → updateCode.do(publisher_code=PE, kogl_code=, offerDbcode1s=CH1, offerDbcode2s=CH11, speciesKey_list=…) → getOnSpecView.do 로 확인.
KEY 설정 팝업(그림 21)은 요청으로 읽는 법을 아직 못 봤다(팝업 본문이 기록에 안 남음). 계정마다 한 번 맞추면 되므로 여기서는 읽지 않고 기록에 "확인 못 함"을 남긴다. 화면 방식 대체 경로가 확인한다."""
from __future__ import annotations
import datetime, json
from pathlib import Path
from urllib.parse import urlencode

from . import kolis_http, dup_judge
from . import mods_build as mb
from .build_prep import _year, BATCH_WANT

WORK = mb.WORK
FORM = "application/x-www-form-urlencoded; charset=UTF-8"
P = "/online/cata/bocata/digitalcont/dupexmin/bundledupexmin/"


def _post(c: kolis_http.Client, path: str, form: dict | list, wait: float = 120.0) -> dict:
    return c.send("POST", path, urlencode(form, doseq=True), FORM, wait=wait)


def _search_form(wonbu: str) -> dict:
    return {"accession_rec_no": wonbu, "acquisit_yr": _year(), "reg_code": "FTX", "accession_rec_no_start": wonbu, "accession_no_from": "", "accession_no_to": ""}


def _state(wonbu: str, patch: dict) -> dict:
    d = WORK / f"wonbu_{wonbu}"; d.mkdir(parents=True, exist_ok=True)
    p = d / "state.json"
    st = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"wonbu": wonbu}
    st.update(patch); p.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    return st


def ledger_status(c: kolis_http.Client, wonbu: str) -> dict:
    r = _post(c, "/online/reg/bo/accrecmng/onlineAccRecMng/selectAccRecMngListWithParam.do",
              {"acc_rec_key": "", "key_arr": "", "har_stat_cd": "20", "use_limit_code": "", "reg_code": "FTX", "accession_rec_make_year": _year(), "rec_no_yn": "Y", "accession_rec_no": wonbu, "species": "", "book": "", "missingregnocnt": ""})
    lst = r.get("list", [])
    st = sorted({f"{x.get('WORKING_STATUS')} {x.get('WORKING_STATUS_NAME')}" for x in lst})
    return {"acc_count": len(lst), "status": st, "dup_done": bool(lst) and all(str(x.get("WORKING_STATUS") or "") >= "DS_3300" for x in lst),
            "title": next((x.get("TITLE") for x in lst if x.get("TITLE")), None)}


def digitalcont(c: kolis_http.Client, wonbu: str) -> dict:
    f = dict(har_type_cd="", bus_id="", coll_id="", key_arr="", acc_rec_key="", type="mo", work_status_list_start="DS_3200", work_status_list_end="DS_3400", har_stat_cd="30", tran_stat_cd="40", list_menu_id="F1131200", init_dcms_yn="", use_limit_code="", reg_code="FTX", acquisit_yr=_year(), accession_rec_no_start=wonbu, accession_rec_no_end="", accession_no_start="", accession_no_end="", searchSpecCnt="", searchContCnt="")
    return _post(c, "/online/cata/bocata/digitalcont/digitalcontmng/onlineDigitalContMngList.do", f)


def spec_view(c: kolis_http.Client, key, har_stat_cd: str = "30") -> dict:
    r = _post(c, "/online/cmmn/getOnSpecView.do", {"species_key": str(key), "har_stat_cd": har_stat_cd})
    return (r.get("data") or {}) if isinstance(r, dict) else {}


def volumes(c: kolis_http.Client, key) -> list[dict]:
    r = _post(c, "/online/cmmn/listVolumn.do", {"species_key": str(key), "har_stat_cd": "30"})
    return r.get("list") or []


def dupexmin(wonbu: str, log=print, client: kolis_http.Client | None = None) -> dict:
    """복본조사(요청): 상태 확인 → 목록 → 건마다 조사 → 후보 있으면 에이전트 판정. 완료는 하지 않는다. 돌려주는 꼴은 build_prep.dupexmin 과 같다."""
    own = client is None
    c = client or kolis_http.Client(log)
    try:
        c.login()
        ls = ledger_status(c, wonbu)
        d = WORK / f"wonbu_{wonbu}"; d.mkdir(parents=True, exist_ok=True)
        if ls["acc_count"] == 0:
            return {"mode": "request", "no_ledger": True, **ls, "message": f"등록원부관리에 원부 {wonbu} 가 없습니다. 원부번호를 확인하십시오."}
        if ls["dup_done"]:
            _state(wonbu, {"dupexmin_done": True, "acc_count": ls["acc_count"], "status": ls["status"], "title": ls.get("title")})
            return {"mode": "request", "already_done": True, **ls, "message": f"이 원부는 복본조사가 이미 끝났습니다(등록원부관리 {ls['acc_count']}건, 상태 {', '.join(ls['status'])}). 다시 돌릴 것이 없습니다."}
        log("복본조사 KEY 설정은 요청으로 읽는 법을 아직 몰라 확인하지 않습니다(계정마다 한 번 맞추면 됨. 10-03 화면 확인: 그림 21 과 같음)")
        keys = [x.get("REC_KEY") for x in _post(c, P + "getDupExminList.do", _search_form(wonbu)).get("list") or []]
        log(f"복본조사 대상 {len(keys)}건(원부 {wonbu} {ls.get('title') or ''}) — 건마다 조사 요청")
        rows, ident = [], "0"
        for i, k in enumerate(keys, 1):
            form = [("rec_key_arr", kk) for kk in keys] + [("rec_key", k), ("screen_code", "F1131110"), ("reg_code", "FTX"), ("accession_rec_no", wonbu), ("accession_rec_make_year", _year()), ("ident_mark", str(ident))]
            r = _post(c, P + "dupExminProcBoCata.do", form)
            lst = r.get("list") or []
            if lst:
                rows.extend(lst); ident = r.get("ident_mark") or ident
            if i % 10 == 0 or i == len(keys):
                log(f"  {i}/{len(keys)}건 조사, 결과 행 {len(rows)}")
        (d / "dupexmin_result.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        judged, counts, summary, out, dups = [], {"dup": 0, "not": 0, "unsure": 0}, "", None, []
        if rows:
            def post(path, form):
                try:
                    return _post(c, path, form)
                except Exception:  # noqa: BLE001
                    return {}
            dup_judge.gather(wonbu, rows, log, post=post)
            result, fails, out = dup_judge.run(wonbu, log)
            judged = result.get("pairs") or []; summary = str(result.get("summary") or "")
            counts = {k: sum(1 for p in judged if p.get("verdict") == k) for k in ("dup", "not", "unsure")}
            dups = dup_judge.dup_rows(result, rows)
        _state(wonbu, {"dupexmin_run": True, "dupexmin_at": f"{datetime.datetime.now():%Y-%m-%d %H:%M}", "dupexmin_rows": len(rows), "dup_counts": counts, "dup_checked_rows": dups, "acc_count": ls["acc_count"], "status": ls["status"], "title": ls.get("title"), "mode": "request"})
        msg = ("복본 후보가 없습니다. " if not rows else f"후보 {len(judged)}짝 — 복본 {counts['dup']} · 아님 {counts['not']} · 판단 불가 {counts['unsure']}. ") + "완료 처리는 하지 않았습니다."
        log(msg)
        return {"mode": "request", "duplicates": rows, "judged": judged, "counts": counts, "summary": summary, "dup_file": str(out) if out else None, "completed": False, "message": msg, **ls}
    finally:
        if own:
            c.close()


def dup_complete(wonbu: str, log=print, client: kolis_http.Client | None = None) -> dict:
    """완료(요청): 복본조사를 다시 돌려(결과 같음) → getDropAccNoCnt 0 확인 → dupExminComplete → 재조회. 화면의 복본 체크는 서버로 가지 않으므로 보낼 것이 없다."""
    own = client is None
    c = client or kolis_http.Client(log)
    try:
        c.login()
        keys = [x.get("REC_KEY") for x in _post(c, P + "getDupExminList.do", _search_form(wonbu)).get("list") or []]
        ident = "0"
        for k in keys:
            r = _post(c, P + "dupExminProcBoCata.do", [("rec_key_arr", kk) for kk in keys] + [("rec_key", k), ("screen_code", "F1131110"), ("reg_code", "FTX"), ("accession_rec_no", wonbu), ("accession_rec_make_year", _year()), ("ident_mark", str(ident))])
            if r.get("list"):
                ident = r.get("ident_mark") or ident
        drop = _post(c, P + "getDropAccNoCnt.do", _search_form(wonbu)).get("drop_acc_no_cnt") or 0
        if int(drop) > 0:
            raise RuntimeError(f"이 원부에 삭제된 등록번호가 {drop}건 있어 완료 처리할 수 없습니다(화면도 막음)")
        log(f"완료 요청(dupExminComplete) — 원부 {wonbu}, {len(keys)}건")
        _post(c, P + "dupExminComplete.do?type=A", _search_form(wonbu))
        ls = ledger_status(c, wonbu); dc = digitalcont(c, wonbu)
        v = {"acc_count": ls["acc_count"], "status": ls["status"], "dc_species": dc.get("cnt"), "dc_contents": dc.get("contentsCnt")}
        log(f"재조회: 등록원부관리 {v['acc_count']}건 상태 {v['status']} / 디지털콘텐츠관리 {v['dc_species']}종 {v['dc_contents']}콘텐츠")
        _state(wonbu, {"dupexmin_done": True, "dup_completed_at": f"{datetime.datetime.now():%Y-%m-%d %H:%M}", "title": ls.get("title"), **v})
        return {"mode": "request", "completed": True, **v}
    finally:
        if own:
            c.close()


def batch_change(wonbu: str, log=print, client: kolis_http.Client | None = None) -> dict:
    """일괄변경(요청): 디지털콘텐츠관리 종 전부 → 이미 사업 값이면 건너뜀 → updateCode → 종마다 다시 읽어 확인."""
    own = client is None
    c = client or kolis_http.Client(log)
    try:
        c.login()
        dc = digitalcont(c, wonbu); keys = [x.get("SPECIES_KEY") for x in dc.get("list") or []]
        if not keys:
            raise RuntimeError(f"디지털콘텐츠관리에 원부 {wonbu} 가 없습니다(복본조사 완료 전이면 보이지 않음)")
        def read_all():
            got = []
            for k in keys:
                d0 = spec_view(c, k); got.append({"key": k, **{f: d0.get(f) for f in ("OFFER_DBCODE_1S", "OFFER_DBCODE_2S", "PUBLISHER_CODE", "KOGL_CODE")}})
            return got
        before = read_all()
        same = [g for g in before if g["OFFER_DBCODE_1S"] == "CH1" and g["OFFER_DBCODE_2S"] == "CH11" and g["PUBLISHER_CODE"] == "PE"]
        if len(same) == len(keys):
            _state(wonbu, {"batch_change_done": True, "species": len(keys), "batch_values": {"OFFER_DBCODE_1S": "CH1", "OFFER_DBCODE_2S": "CH11", "PUBLISHER_CODE": "PE"}})
            return {"mode": "request", "already_done": True, "species": len(keys), "ok": True, "values": {"OFFER_DBCODE_1S": "CH1", "OFFER_DBCODE_2S": "CH11", "PUBLISHER_CODE": "PE"}, "message": f"{len(keys)}종 모두 이미 사업 값입니다."}
        log(f"일괄변경 요청(updateCode) — {len(keys)}종에 CH1 / CH11 / PE / 공공누리 적용안함")
        c.send("POST", "/online/cata/bocata/digitalcont/digitalcontmng/updateCode.do",
               urlencode([("publisher_code", BATCH_WANT["publisher_code"]), ("kogl_code", BATCH_WANT["kogl_code"]), ("offerDbcode1s", BATCH_WANT["offer_dbcode_1s"]), ("offerDbcode2s", BATCH_WANT["offer_dbcode_2s"])] + [("speciesKey_list", k) for k in keys]), FORM)
        after = read_all()
        bad = [g for g in after if not (g["OFFER_DBCODE_1S"] == "CH1" and g["OFFER_DBCODE_2S"] == "CH11" and g["PUBLISHER_CODE"] == "PE")]
        ok = not bad
        log(f"확인({len(keys)}종 다시 읽음): {'전부 맞음' if ok else f'{len(bad)}종 다름 — ' + str(bad[:3])}")
        _state(wonbu, {"batch_change_done": ok, "species": len(keys), "batch_values": {k: after[0].get(k) for k in ("OFFER_DBCODE_1S", "OFFER_DBCODE_2S", "PUBLISHER_CODE", "KOGL_CODE")}, "batch_verified_at": f"{datetime.datetime.now():%Y-%m-%d %H:%M} (요청 방식, {len(keys)}종 전부 재조회)", "batch_at": f"{datetime.datetime.now():%Y-%m-%d %H:%M}"})
        return {"mode": "request", "ok": ok, "species": len(keys), "values": {k: after[0].get(k) for k in ("OFFER_DBCODE_1S", "OFFER_DBCODE_2S", "PUBLISHER_CODE", "KOGL_CODE")}, "bad": bad}
    finally:
        if own:
            c.close()
