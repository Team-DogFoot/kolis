"""③구간 5.1 일괄복본조사 · 5.2 일괄변경 (반자동, 2026-10-03). 10-03 원부 1607 에서 tools/keyset_step.py·dupexmin_run.py·dupexmin_complete.py·
batchchange_step.py·batchchange_set.py 로 한 번 수행한 것을 프로그램용으로 묶었다. 유저 Edge 창(kolis_browser.Browser)에서 가이드 메뉴 순서대로 간다.

바꾸는 요청은 approved=True 일 때만 보낸다(프로그램 창에서 YES 를 받은 뒤). 단계마다 전 조건을 확인하고, 실행 뒤 KOLIS 를 다시 조회해 확인한다.
  dupexmin(wonbu, log, approved) : KEY 설정 저장(그림 21) → 복본조사 실행 → 복본 0건이면 완료(DS_3300) → 등록원부관리·디지털콘텐츠관리 재조회.
                                    복본이 있으면 완료하지 않고 표를 돌려준다(사람 판정).
  batch_change(wonbu, log, approved) : 디지털콘텐츠관리 찾기 → 전체 체크 → 일괄변경 팝업(CH1/CH11/PE/공공누리 없음, 그림 24) → 저장 → 종 화면 값으로 확인.
※ 1607 뒤로는 아직 실행한 적이 없다. 두 번째 원부에서 직원과 함께 처음 돌린다.
"""
from __future__ import annotations
import json, re, urllib.parse
from pathlib import Path

from .kolis_browser import Browser, BASE
from .mods_build import close_notice, open_digitalcont, shot, WORK

KEY_WANT = {"on_use_yn": True, "media_code_use_yn": True, "digital_mat_type_use_yn": True, "author_use_yn": True}   # 그림 21
BATCH_WANT = {"offer_dbcode_1s": "CH1", "offer_dbcode_2s": "CH11", "publisher_code": "PE", "kogl_code": ""}        # 그림 24
H = {"X-Requested-With": "XMLHttpRequest"}


class NeedsApproval(Exception):
    """바꾸는 요청 직전. 메시지에 다음에 할 일을 적는다."""


def _year() -> str:
    import datetime
    return str(datetime.date.today().year)


def open_dupexmin(b: Browser, wonbu: str):
    """메뉴: 정리 → 디지털콘텐츠 → 일괄복본조사. 등록구분 FTX, 원부번호."""
    p = b.page
    if "onlineBundleDupExmin" not in p.url:
        p.goto(BASE + "/main/gohome.do", wait_until="domcontentloaded"); b.wait(1.5); close_notice(p); b.wait(0.5)
        b._rec("menu", step="정리"); p.get_by_text("정리", exact=True).locator("visible=true").first.click(); b.wait(1.5)
        b._rec("menu", step="디지털콘텐츠"); p.get_by_text("디지털콘텐츠", exact=True).locator("visible=true").first.click(); b.wait(1.5)
        b._rec("menu", step="일괄복본조사"); p.get_by_text("일괄복본조사", exact=True).locator("visible=true").first.click()
        p.wait_for_selector("#reg_code", timeout=30000); b.wait(2)
    b.select("#reg_code", "FTX"); b.fill("#accession_rec_no_start", wonbu)
    vals = b.eval("({yr: $('#acquisit_yr').val(), reg: $('#reg_code').val(), no: $('#accession_rec_no_start').val()})")
    if vals != {"yr": _year(), "reg": "FTX", "no": wonbu}:
        raise RuntimeError(f"일괄복본조사 화면 값이 다릅니다: {vals}")
    return p


def keyset(b: Browser, main, log, approved: bool) -> dict:
    """복본조사KEY설정 팝업: 그림 21 대로 체크하고 저장. 이미 같으면 저장하지 않는다."""
    with b.ctx.expect_page(timeout=15000) as ev:
        b.page = main; b.click("#btnDupExminKeySet", changes=False)
    pop = ev.value; pop.wait_for_load_state("domcontentloaded"); pop.wait_for_timeout(1500); b._hook(pop)
    if "type=A" not in pop.url:
        raise RuntimeError(f"KEY 설정 팝업 주소가 다릅니다(온라인용이 아님): {pop.url}")
    changed = 0
    for name, v in KEY_WANT.items():
        el = pop.locator(f"input[name={name}]").locator("visible=true").first
        if el.is_checked() != v:
            el.set_checked(v); changed += 1; b._rec("check", name=name, value=v)
    r = pop.locator("input[name=title_search_type][value=R]").locator("visible=true").first
    if not r.is_checked():
        r.set_checked(True); changed += 1
    state = pop.evaluate(r"Array.from(document.querySelectorAll('input[type=checkbox],input[type=radio]')).filter(e=>e.offsetParent!==null&&e.checked).map(e=>e.name+'='+e.value)")
    log(f"KEY 설정: {state} (바꾼 것 {changed})")
    if changed:
        if not approved:
            pop.click("#btnClose"); raise NeedsApproval(f"복본조사 KEY 설정이 매뉴얼 그림 21 과 {changed}곳 다릅니다. 「복본조사 실행」을 누르면 그림 21 대로 저장한 뒤 복본조사를 돌립니다.")
        b._rec("click", selector="저장(KEY설정 팝업)", approved=True, changes=True)
        pop.on("dialog", lambda d: (b._rec("dialog", message=d.message, action="accept"), d.accept()))
        pop.click("#btnSave"); pop.wait_for_timeout(2000)
        log("KEY 설정 저장함")
    if not pop.is_closed():
        pop.click("#btnClose"); b.wait(0.8)
    return {"changed": changed, "state": state}


def ledger_status(b: Browser, page, wonbu: str) -> dict:
    """등록원부관리 조회(읽기만): 이 원부의 건수와 작업 상태(DS_3200 등록, DS_3300 복본조사완료 …)."""
    r = page.request.post(BASE + "/online/reg/bo/accrecmng/onlineAccRecMng/selectAccRecMngListWithParam.do", headers=H,
                          form={"acc_rec_key": "", "key_arr": "", "har_stat_cd": "20", "use_limit_code": "", "reg_code": "FTX", "accession_rec_make_year": _year(), "rec_no_yn": "Y", "accession_rec_no": wonbu, "species": "", "book": "", "missingregnocnt": ""}).json()
    lst = r.get("list", [])
    st = sorted({f"{x.get('WORKING_STATUS')} {x.get('WORKING_STATUS_NAME')}" for x in lst})
    done = bool(lst) and all(str(x.get("WORKING_STATUS") or "") >= "DS_3300" for x in lst)
    title = next((x.get("TITLE") for x in lst if x.get("TITLE")), None)
    b._rec("verify", what="원부 상태(복본조사 전)", acc_count=len(lst), status=st, dup_done=done, title=title)
    return {"acc_count": len(lst), "status": st, "dup_done": done, "title": title}


def dupexmin(wonbu: str, log=print, approved: bool = False) -> dict:
    """5.1 복본조사: 화면 열기 → 원부 상태 확인 → KEY 설정 → 복본조사 실행 → 후보가 있으면 에이전트 판정·복본 체크. **완료 처리는 하지 않는다**(사람이 버튼으로).
    approved=False(미리 보기)는 화면을 열어 원부 상태·KEY 상태만 보고 멈춘다(바꾸는 요청 없음)."""
    b = Browser(log); b.login()
    try:
        main = open_dupexmin(b, wonbu)
        ls = ledger_status(b, main, wonbu)
        d = WORK / f"wonbu_{wonbu}"; d.mkdir(parents=True, exist_ok=True)
        if ls["acc_count"] == 0:
            shot(main, f"dupexmin_{wonbu}_noledger")
            return {"preview": not approved, "no_ledger": True, **ls, "message": f"등록원부관리에 원부 {wonbu} 가 없습니다. 원부번호를 확인하십시오."}
        if ls["dup_done"]:
            shot(main, f"dupexmin_{wonbu}_already")
            st_p = d / "state.json"; st = json.loads(st_p.read_text(encoding="utf-8")) if st_p.exists() else {"wonbu": wonbu}
            st.update({"dupexmin_done": True, "acc_count": ls["acc_count"], "status": ls["status"], "title": ls.get("title")}); st_p.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
            return {"preview": not approved, "already_done": True, **ls, "message": f"이 원부는 복본조사가 이미 끝났습니다(등록원부관리 {ls['acc_count']}건, 상태 {', '.join(ls['status'])}). 다시 돌릴 것이 없습니다."}
        ks = keyset(b, main, log, approved)
        if not approved:
            shot(main, f"dupexmin_{wonbu}_before")
            return {"preview": True, **ls, "keyset": ks, "message": f"일괄복본조사 화면을 열었습니다. 등록원부관리 {ls['acc_count']}건, 상태 {', '.join(ls['status'])}. 복본조사 KEY 설정은 매뉴얼 그림 21 과 같습니다(저장할 것 없음). 다음은 「복본조사 실행」입니다. 후보를 찾아 판정하며, 완료 처리는 하지 않습니다."}
        msgs: list = []
        main.on("dialog", lambda d: msgs.append(d.message))        # 읽기만. 닫는 것은 Browser._on_dialog(알림 자동 확인)
        b._dialog_answer = True
        b._rec("click", selector="#btnDupExmin(복본조사)", approved=True, changes=True)
        main.click("#btnDupExmin")
        for _ in range(90):
            b.wait(1.0)
            if any("끝났습니다" in m for m in msgs):
                break
        # "끝났습니다" 알림은 마지막 건 응답보다 먼저 뜬다(1608: 41건 중 39번째 뒤에 알림, 그 뒤 2건 더 옴). 요청 수가 3초 동안 안 늘 때까지 더 기다린 뒤 표를 읽는다.
        quiet, last = 0, b.n
        for _ in range(60):
            b.wait(1.0)
            if b.n == last:
                quiet += 1
                if quiet >= 3:
                    break
            else:
                quiet, last = 0, b.n
        rows = b.eval("(()=>{var o=[];try{for(var i=0;i<grid.getRowsCount();i++){o.push($('#jqxgrid').jqxGrid('getrowdata',i));}}catch(e){}return o;})()")
        d = WORK / f"wonbu_{wonbu}"; d.mkdir(parents=True, exist_ok=True)
        (d / "dupexmin_result.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        log(f"복본조사 결과 {len(rows)}행, 확인창 {msgs}"); shot(main, f"dupexmin_{wonbu}_result")
        judged, counts, summary, dup_file, dups = [], {"dup": 0, "not": 0, "unsure": 0}, "", None, []
        if rows:
            # 복본 판정은 에이전트가 한다(유저 확정 2026-10-03). 완료 처리는 프로그램이 하지 않고 사람이 3-1 의 「복본조사 완료」 버튼으로 한다
            # (완료는 되돌릴 수 없고, 완료 안 함은 버튼으로 되돌릴 수 있으므로 — 유저 확정 2026-10-03).
            from . import dup_judge
            dup_judge.gather(wonbu, rows, log, b=b)
            result, fails, out = dup_judge.run(wonbu, log)
            judged = result.get("pairs") or []; summary = str(result.get("summary") or ""); dup_file = str(out)
            counts = {k: sum(1 for p in judged if p.get("verdict") == k) for k in ("dup", "not", "unsure")}
            b._rec("judge", what="복본(에이전트)", counts=counts, summary=summary, file=dup_file, remaining=fails)
            dups = dup_judge.dup_rows(result, rows)
            if dups:
                main.evaluate("(idx)=>{idx.forEach(i=>{try{$('#jqxgrid').jqxGrid('setcellvalue',i,'_chk',true);}catch(e){}})}", dups)
                b._rec("check", what="복본 체크(에이전트 판정)", rows=dups)
            shot(main, f"dupexmin_{wonbu}_judged")
        st_p = d / "state.json"; st = json.loads(st_p.read_text(encoding="utf-8")) if st_p.exists() else {"wonbu": wonbu}
        st.update({"dupexmin_run": True, "dupexmin_at": f"{__import__('datetime').datetime.now():%Y-%m-%d %H:%M}", "dupexmin_rows": len(rows), "dup_counts": counts, "dup_checked_rows": dups, "acc_count": ls["acc_count"], "status": ls["status"], "title": ls.get("title")})
        st_p.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
        msg = ("복본 후보가 없습니다. " if not rows else f"후보 {len(judged)}짝 — 복본 {counts['dup']} · 아님 {counts['not']} · 판단 불가 {counts['unsure']}. ") + "완료 처리는 하지 않았습니다. 판정을 확인하고 아래 「복본조사 완료」를 누르십시오."
        log(msg)
        return {"keyset": ks, "duplicates": rows, "judged": judged, "counts": counts, "summary": summary, "dup_file": dup_file, "completed": False, "message": msg}
    finally:
        b.close()


def dup_complete(wonbu: str, log=print, approved: bool = False) -> dict:
    """5.1 완료 처리(사람이 버튼으로). 일괄복본조사 화면을 다시 열어 복본조사를 돌리고(결과는 같다), 저장된 판정의 복본 짝을 체크한 뒤 「완료」를 누르고 재조회한다."""
    from . import dup_judge
    d = WORK / f"wonbu_{wonbu}"
    dj = json.loads((d / "dup_build.json").read_text(encoding="utf-8")) if (d / "dup_build.json").exists() else {}
    b = Browser(log); b.login()
    try:
        main = open_dupexmin(b, wonbu)
        ks = keyset(b, main, log, True)
        if not approved:
            raise NeedsApproval("복본조사 완료 처리를 합니다. 되돌릴 수 없습니다.")
        msgs: list = []
        main.on("dialog", lambda dlg: msgs.append(dlg.message))
        b._dialog_answer = True
        b._rec("click", selector="#btnDupExmin(복본조사, 완료 전 재실행)", approved=True, changes=True)
        main.click("#btnDupExmin")
        for _ in range(90):
            b.wait(1.0)
            if any("끝났습니다" in m for m in msgs):
                break
        # "끝났습니다" 알림은 마지막 건 응답보다 먼저 뜬다(1608: 41건 중 39번째 뒤에 알림, 그 뒤 2건 더 옴). 요청 수가 3초 동안 안 늘 때까지 더 기다린 뒤 표를 읽는다.
        quiet, last = 0, b.n
        for _ in range(60):
            b.wait(1.0)
            if b.n == last:
                quiet += 1
                if quiet >= 3:
                    break
            else:
                quiet, last = 0, b.n
        rows = b.eval("(()=>{var o=[];try{for(var i=0;i<grid.getRowsCount();i++){o.push($('#jqxgrid').jqxGrid('getrowdata',i));}}catch(e){}return o;})()")
        dups = dup_judge.dup_rows(dj, rows) if dj else []
        if dups:
            main.evaluate("(idx)=>{idx.forEach(i=>{try{$('#jqxgrid').jqxGrid('setcellvalue',i,'_chk',true);}catch(e){}})}", dups)
            b._rec("check", what="복본 체크(저장된 판정)", rows=dups)
        b._dialog_answer = True            # "복본조사완료 하시겠습니까?" → 예
        b._rec("click", selector="#btnComplete(완료)", approved=True, changes=True, dup_rows=dups)
        main.click("#btnComplete"); b.wait(4.0); b._dialog_answer = None; shot(main, f"dupexmin_{wonbu}_complete")
        v = verify_after_dupexmin(b, main, wonbu)
        log(f"재조회: 등록원부관리 {v['acc_count']}건 상태 {v['status']} / 디지털콘텐츠관리 {v['dc_species']}종 {v['dc_contents']}콘텐츠")
        st_p = d / "state.json"; st = json.loads(st_p.read_text(encoding="utf-8")) if st_p.exists() else {"wonbu": wonbu}
        st.update({"dupexmin_done": True, "dup_completed_rows": dups, **v}); st_p.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
        return {"keyset": ks, "completed": True, "dup_rows": dups, **v}
    finally:
        b.close()


def _norm(x) -> str:
    return re.sub(r"[\s\[\]()\-_.,:;·]+", "", str(x or "")).lower()


def judge_duplicates(rows: list[dict]) -> list[dict]:
    """복본조사 결과 표(2026-10-03 1610 에서 확인한 구조): 우리 자료 행(ORIGIN_YN='V', ACCESSION_NO 있음)과 그 아래 후보 행들(ORIGIN_YN='N')이
    IDENT_MARK 로 묶인다. 후보 행마다 우리 행과 표제·저작자·발행처·발행년을 비교해, 모두 같으면 복본, 하나라도 다르면 복본 아님.
    유저 위임(2026-10-03) 규칙. 발행처만 다른 경우는 '복본 아님'이지만 직원이 볼 수 있게 note 를 남긴다(같은 내용의 재유통일 수 있음)."""
    out, cur = [], None
    for i, r in enumerate(rows):
        if str(r.get("ORIGIN_YN")) == "V":      # 우리 자료 행. 그 아래 N 행들이 이 행의 후보(표는 순서대로 묶여 있다)
            cur = (i, r); continue
        o = cur
        values = {k: r.get(k) for k in ("REC_KEY", "TITLE", "AUTHOR", "PUBLISHER", "PUBLISH_YEAR", "TYPEOFRESOURCE", "CNTS_COUNT")}
        if not o:
            out.append({"row": i, "dup": False, "why": "짝이 되는 우리 자료 행(ORIGIN_YN=V)을 찾지 못해 판정 불가 → 복본 아님으로 둠", "values": values, "ours": None}); continue
        oi, orow = o
        same, diff = [], []
        for k, label in (("TITLE", "표제"), ("AUTHOR", "저작자"), ("PUBLISHER", "발행처"), ("PUBLISH_YEAR", "발행년")):
            a, c = _norm(orow.get(k)), _norm(r.get(k))
            if not a and not c:
                continue
            (same if a == c else diff).append(f"{label} {orow.get(k)!r} / {r.get(k)!r}")
        dup = bool(same) and not diff
        note = ""
        if not dup and all(d.startswith(("발행처", "발행년")) for d in diff) and same:
            note = "표제·저작자는 같고 발행처(또는 발행년)만 다릅니다. 같은 내용을 다른 곳에서 유통한 것일 수 있으니 직원 확인을 권합니다."
        out.append({"row": i, "ours_row": oi, "ident": r.get("IDENT_MARK"), "dup": dup, "why": ("모두 같음 — " if dup else "다름 — ") + "; ".join(diff or same), "note": note,
                    "values": values, "ours": {k: orow.get(k) for k in ("REC_KEY", "TITLE", "AUTHOR", "PUBLISHER", "PUBLISH_YEAR", "ACCESSION_NO")}})
    return out


def verify_after_dupexmin(b: Browser, page, wonbu: str) -> dict:
    yr = _year()
    r = page.request.post(BASE + "/online/reg/bo/accrecmng/onlineAccRecMng/selectAccRecMngListWithParam.do", headers=H,
                          form={"acc_rec_key": "", "key_arr": "", "har_stat_cd": "20", "use_limit_code": "", "reg_code": "FTX", "accession_rec_make_year": yr, "rec_no_yn": "Y", "accession_rec_no": wonbu, "species": "", "book": "", "missingregnocnt": ""}).json()
    st = sorted({f"{x.get('WORKING_STATUS')} {x.get('WORKING_STATUS_NAME')}" for x in r.get("list", [])})
    f = dict(har_type_cd="", bus_id="", coll_id="", key_arr="", acc_rec_key="", type="mo", work_status_list_start="DS_3200", work_status_list_end="DS_3400", har_stat_cd="30", tran_stat_cd="40", list_menu_id="F1131200", init_dcms_yn="", use_limit_code="", reg_code="FTX", acquisit_yr=yr, accession_rec_no_start=wonbu, accession_rec_no_end=wonbu, accession_no_start="", accession_no_end="", searchSpecCnt="", searchContCnt="")
    r2 = page.request.post(BASE + "/online/cata/bocata/digitalcont/digitalcontmng/onlineDigitalContMngList.do", headers=H, form=f).json()
    b._rec("verify", what="복본조사 뒤 재조회", acc_count=len(r.get("list", [])), status=st, dc=r2.get("cnt"))
    return {"acc_count": len(r.get("list", [])), "status": st, "dc_species": r2.get("cnt"), "dc_contents": r2.get("contentsCnt")}


def batch_change(wonbu: str, log=print, approved: bool = False) -> dict:
    """5.2 일괄변경(그림 24). 저장 뒤 첫 종의 값을 다시 읽어 확인."""
    b = Browser(log); b.login()
    try:
        main, n = open_digitalcont(b, wonbu)
        if n <= 0:
            raise RuntimeError(f"디지털콘텐츠관리에 원부 {wonbu} 가 없습니다(복본조사 완료 전이면 보이지 않음)")
        main.evaluate("(function(){for(var i=0;i<grid.getRowsCount();i++){$('#jqxgrid').jqxGrid('setcellvalue',i,'_chk',true);}})()")
        checked = main.evaluate("(()=>{var c=0;for(var i=0;i<grid.getRowsCount();i++){if($('#jqxgrid').jqxGrid('getcellvalue',i,'_chk'))c++;}return c;})()")
        if checked != n:
            raise RuntimeError(f"전체 체크 실패: {checked}/{n}")
        keys = main.evaluate("(()=>{var o=[];for(var i=0;i<grid.getRowsCount();i++){o.push($('#jqxgrid').jqxGrid('getrowdata',i).SPECIES_KEY);}return o;})()")
        # 종마다 지금 값을 읽어(조회만) 이미 사업 값이면 바꿀 것이 없다고 알린다
        cur = []
        for k in keys:
            r0 = main.request.post(BASE + "/online/cmmn/getOnSpecView.do", headers=H, form={"species_key": str(k), "har_stat_cd": "30"}).json()
            d0 = (r0.get("data") or {}) if isinstance(r0, dict) else {}
            cur.append({"key": k, "OFFER_DBCODE_1S": d0.get("OFFER_DBCODE_1S"), "OFFER_DBCODE_2S": d0.get("OFFER_DBCODE_2S"), "PUBLISHER_CODE": d0.get("PUBLISHER_CODE")})
        same = [c for c in cur if c["OFFER_DBCODE_1S"] == "CH1" and c["OFFER_DBCODE_2S"] == "CH11" and c["PUBLISHER_CODE"] == "PE"]
        b._rec("verify", what="일괄변경 전 종 값", total=n, already=len(same))
        if len(same) == n:
            dd = WORK / f"wonbu_{wonbu}"; dd.mkdir(parents=True, exist_ok=True)
            stp = dd / "state.json"; st = json.loads(stp.read_text(encoding="utf-8")) if stp.exists() else {"wonbu": wonbu}
            st.update({"batch_change_done": True, "species": n, "batch_values": {"OFFER_DBCODE_1S": "CH1", "OFFER_DBCODE_2S": "CH11", "PUBLISHER_CODE": "PE"}}); stp.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
            return {"preview": not approved, "already_done": True, "species": n, "message": f"디지털콘텐츠관리 {n}종 모두 이미 자료유형1 CH1 · 자료유형2 CH11 · 발행자구분 PE 입니다. 바꿀 것이 없습니다."}
        with b.ctx.expect_page(timeout=15000) as ev:
            b.page = main; b.click("#btnPubCode", changes=False)
        pop = ev.value; pop.wait_for_load_state("domcontentloaded"); pop.wait_for_timeout(1500); b._hook(pop)
        for sid, v in BATCH_WANT.items():
            pop.select_option(f"#{sid}", v); b._rec("select", selector=f"팝업 #{sid}", value=v)
            pop.evaluate(f"document.querySelector('#{sid}').dispatchEvent(new Event('change', {{bubbles:true}}))"); pop.wait_for_timeout(400)
        sel = pop.evaluate("Array.from(document.querySelectorAll('select')).map(s=>s.id+'='+s.value)")
        log(f"일괄변경 팝업 값: {sel} ({n}종 체크)")
        d = Path("work/captures/browser"); d.mkdir(parents=True, exist_ok=True)
        import datetime
        pop.screenshot(path=str(d / f"{datetime.datetime.now():%Y%m%d-%H%M%S}_codeMngPop_{wonbu}.png"))
        if not approved:
            raise NeedsApproval(f"디지털콘텐츠관리 화면을 열었습니다. {n}종 중 {n - len(same)}종이 사업 값과 다릅니다. 「일괄변경 실행」을 누르면 {n}종에 자료유형1 CH1 e-콘텐츠 / 자료유형2 CH11 기관수집 / 발행자구분 PE 일반 / 공공누리 적용안함 을 저장합니다. 되돌릴 수 없습니다.")
        b._dialog_answer = True
        b._rec("click", selector="저장(일괄변경 팝업)", approved=True, changes=True)
        pop.click("#btnSave"); main.wait_for_timeout(4000); b._dialog_answer = None
        r = main.request.post(BASE + "/online/cmmn/getOnSpecView.do", headers=H, form={"species_key": str(keys[0]), "har_stat_cd": "30"}).json()
        data = r.get("data") or r if isinstance(r, dict) else {}          # 응답은 {"sttus","data":{…}} (2026-10-03 확인)
        got = {k: data.get(k) for k in ("OFFER_DBCODE_1S", "OFFER_DBCODE_2S", "PUBLISHER_CODE", "KOGL_CODE")}
        ok = got.get("OFFER_DBCODE_1S") == "CH1" and got.get("OFFER_DBCODE_2S") == "CH11" and got.get("PUBLISHER_CODE") == "PE"
        b._rec("verify", what="일괄변경 뒤 첫 종", values=got, ok=ok)
        log(f"확인(첫 종 {keys[0]}): {got} → {'맞음' if ok else '다름!'}")
        dd = WORK / f"wonbu_{wonbu}"; dd.mkdir(parents=True, exist_ok=True)
        stp = dd / "state.json"; st = json.loads(stp.read_text(encoding="utf-8")) if stp.exists() else {"wonbu": wonbu}
        st.update({"batch_change_done": ok, "batch_values": got, "species": n}); stp.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
        return {"species": n, "values": got, "ok": ok}
    finally:
        b.close()


# ---------------------------------------------------------------- 성인물 이용제한 설정 (유저가 알려 준 절차, 2026-10-03)
# 디지털콘텐츠관리 → 행 체크 → MODS정리 → 종·콘텐츠 화면 → 이용제한구분 [변경] → 팝업(/cmmn/uselimitcode/useLimitCodeChangePop.do, 목록 listUseLimitCode.do)
# → 첫 행 "1. 청소년 유해매체물"(GM 일반, 변경코드 CD1) 선정 체크 → 알림 확인 → 팝업 확인 → 종 화면 저장. 종(회차)마다 반복.
# 지침: MODS 입력가이드 8 이용대상자 — 청소년유해매체물은 이용대상자 '성인용' + 서비스범위·이용제한 설정 + 주기 "19세 미만 구독불가".
USE_LIMIT_ROW_TEXT = "청소년 유해매체물"


def use_limit_adult(wonbu: str, log=print, approved: bool = False, rows: list[int] | None = None) -> dict:
    from . import mods_build as mb
    b = Browser(log); b.login()
    done, results = [], []
    try:
        for part in ("onContentsDetailPop", "onSpecViewPop", "useLimitCode"):
            for pg in mb._pages(b, part):
                pg.close()
        main, n = mb.open_digitalcont(b, wonbu)
        for i in range(n):
            if rows is not None and i not in rows:
                continue
            for part in ("onSpecViewPop", "useLimitCode"):
                for pg in mb._pages(b, part):
                    pg.close()
            b.page = main
            main.evaluate(f"(function(){{for(var k=0;k<grid.getRowsCount();k++){{$('#jqxgrid').jqxGrid('setcellvalue',k,'_chk',k=={i});}} $('#jqxgrid').jqxGrid('clearselection'); $('#jqxgrid').jqxGrid('selectrow',{i}); $('#jqxgrid').jqxGrid('ensurerowvisible',{i});}})()")
            main.wait_for_timeout(300)
            info = main.evaluate(f"(()=>{{var r=$('#jqxgrid').jqxGrid('getrowdata',{i});return {{TITLE:r.TITLE,VOL:r.VOL,SPECIES_KEY:r.SPECIES_KEY}}}})()")
            with b.ctx.expect_page(timeout=20000) as ev:
                b.click("#btnModsArrange", changes=False)
            spec = ev.value; spec.wait_for_load_state("domcontentloaded"); spec.wait_for_timeout(2500); b._hook(spec)
            if f"species_key={info['SPECIES_KEY']}" not in spec.url:
                raise RuntimeError(f"종 화면이 다른 종을 열었습니다: 기대 {info['SPECIES_KEY']}, 실제 {spec.url}")
            before = spec.input_value("#use_limit_code_display")
            if before.strip() and not before.strip().startswith("--"):      # 비어 있으면 "-- | " 로 표시된다
                log(f"{i + 1}/{n} {info['TITLE']} {info['VOL']}: 이미 이용제한 {before} — 건너뜀"); results.append({"row": i, "skipped": before}); spec.close(); continue
            with b.ctx.expect_page(timeout=20000) as ev:
                b.page = spec; b.click("#btn_use_limit_code", changes=False)
            pop = ev.value; pop.wait_for_load_state("domcontentloaded"); pop.wait_for_timeout(2500); b._hook(pop)
            rows_ = pop.evaluate("$('#jqxgrid').jqxGrid('getrows').map(r=>({i:r.uid, desc:r.USE_LIMIT_DESCRIPTION, code:r.USE_LIMIT_CODE, chg:r.USE_LIMIT_CHANGE_CODE}))")
            target = next((r for r in rows_ if USE_LIMIT_ROW_TEXT in str(r.get("desc") or "")), None)
            if target is None:
                raise RuntimeError(f"팝업에 '{USE_LIMIT_ROW_TEXT}' 행이 없습니다: {rows_[:5]}")
            if target["i"] != 0:
                log(f"주의: '{USE_LIMIT_ROW_TEXT}' 가 첫 행이 아니라 {target['i'] + 1}번째 행입니다(설명대로 첫 행이 아님). 그 행을 고릅니다.")
            cols = pop.evaluate("$('#jqxgrid').jqxGrid('columns').records.map(c=>({df:c.datafield, type:c.columntype, text:c.text}))")
            chk = next((c["df"] for c in cols if c.get("type") == "checkbox"), None) or "_chk"
            if not approved:
                shot(pop, f"uselimit_{wonbu}_popup")
                raise NeedsApproval(f"이용제한 팝업에서 '{target['desc']}'({target['code']}, {target['chg']}) 을 선정하고 종 화면을 저장합니다. 종 {n}개에 반복합니다.")
            b._dialog_answer = True        # 알림·확인창은 '확인'
            pop.evaluate(f"$('#jqxgrid').jqxGrid('setcellvalue', {target['i']}, {json.dumps(chk)}, true)"); pop.wait_for_timeout(600)
            b._rec("check", what="이용제한 선정", row=target["i"], desc=target["desc"], code=target["code"], change_code=target["chg"], column=chk)
            shot(pop, f"uselimit_{wonbu}_{i}_checked")
            b._rec("click", selector="#btnConfirm(이용제한 팝업 확인)", approved=True, changes=False)
            pop.click("#btnConfirm"); spec.wait_for_timeout(1500)
            after_pop = spec.input_value("#use_limit_code_display"); log(f"{i + 1}/{n} 팝업 확인 뒤 종 화면 이용제한구분: {before!r} → {after_pop!r}")
            if not after_pop.strip() or after_pop.strip().startswith("--"):
                raise RuntimeError("팝업 확인 뒤에도 종 화면의 이용제한구분이 비어 있습니다")
            b.page = spec
            b._rec("click", selector="#btnSave(종 화면 저장: 이용제한)", approved=True, changes=True)
            spec.click("#btnSave"); spec.wait_for_timeout(3000)
            b._dialog_answer = None
            r = main.request.post(BASE + "/online/cmmn/getOnSpecView.do", headers=H, form={"species_key": str(info["SPECIES_KEY"]), "har_stat_cd": "30"}).json()
            data = r.get("data") or {}
            ok = bool(data.get("USE_LIMIT_CODE")) and str(data.get("USE_LIMIT_CODE")) != "--"
            b._rec("verify", what="이용제한 저장 뒤 종 조회", species_key=info["SPECIES_KEY"], use_limit_code=data.get("USE_LIMIT_CODE"), use_limit_change_code=data.get("USE_LIMIT_CHANGE_CODE"), use_obj_code=data.get("USE_OBJ_CODE"), ok=ok)
            log(f"{i + 1}/{n} {info['TITLE']} {info['VOL']}: 저장 뒤 이용제한 {data.get('USE_LIMIT_CODE')} / 변경코드 {data.get('USE_LIMIT_CHANGE_CODE')} / 이용대상 {data.get('USE_OBJ_CODE')} → {'맞음' if ok else '다름!'}")
            results.append({"row": i, "species_key": info["SPECIES_KEY"], "use_limit_code": data.get("USE_LIMIT_CODE"), "change_code": data.get("USE_LIMIT_CHANGE_CODE"), "use_obj_code": data.get("USE_OBJ_CODE"), "ok": ok})
            if not ok:
                raise RuntimeError("저장 뒤 종 조회에서 이용제한이 비어 있습니다 — 멈춤")
            done.append(i)
            if not spec.is_closed():
                spec.close()
        b.page = main
        d = WORK / f"wonbu_{wonbu}"; d.mkdir(parents=True, exist_ok=True)
        stp = d / "state.json"; st = json.loads(stp.read_text(encoding="utf-8")) if stp.exists() else {"wonbu": wonbu}
        prev = {x.get("row"): x for x in st.get("use_limit") or []}
        for x in results: prev[x.get("row")] = x
        results = [prev[k] for k in sorted(prev)]
        st.update({"use_limit_done": len(done) + sum(1 for x in results if x.get("skipped")) == n, "use_limit": results}); stp.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
        return {"species": n, "done": len(done), "results": results}
    finally:
        b.close()


def show_dupexmin(wonbu: str, log=print) -> dict:
    """KOLIS 화면으로 가기(사람이 보려고): 유저 Edge 에서 메뉴로 일괄복본조사 화면을 열고 원부번호를 넣어 복본조사를 돌려 후보 목록을 띄운다. 완료는 누르지 않는다. 창은 열어 둔다."""
    b = Browser(log); b.login()
    main = open_dupexmin(b, wonbu)
    msgs: list = []
    main.on("dialog", lambda d: msgs.append(d.message)); b._dialog_answer = True
    b._rec("click", selector="#btnDupExmin(복본조사, 보기용)", approved=True, changes=True)
    main.click("#btnDupExmin")
    for _ in range(90):
        b.wait(1.0)
        if any("끝났습니다" in m for m in msgs):
            break
    quiet, last = 0, b.n
    for _ in range(60):
        b.wait(1.0)
        if b.n == last:
            quiet += 1
            if quiet >= 3:
                break
        else:
            quiet, last = 0, b.n
    n = main.evaluate("(()=>{try{return grid.getRowsCount();}catch(e){return -1}})()")
    try:
        main.bring_to_front()
    except Exception:  # noqa: BLE001
        pass
    b._pw.stop()        # 창은 두고 붙었던 것만 끊는다
    return {"rows": n, "message": f"KOLIS 일괄복본조사 화면에 원부 {wonbu} 의 결과 {n}행을 띄웠습니다. Edge 창을 보십시오."}


def show_species(species_key: str, log=print) -> dict:
    """등록 자료(종) 상세 화면을 유저 Edge 에 연다(읽기만). 화면이 쓰는 주소 그대로."""
    b = Browser(log); b.login()
    pg = b.ctx.new_page()
    pg.goto(BASE + f"/online/cmmn/onSpecViewPop.do?species_key={species_key}&har_stat_cd=30&menu_id=F1131200", wait_until="domcontentloaded")
    b.wait(1.5)
    title = pg.evaluate("(()=>{const e=document.querySelector('#title, input[name=title], [name=TITLE]'); return e ? (e.value||e.textContent||'').trim() : document.title;})()")
    try:
        pg.bring_to_front()
    except Exception:  # noqa: BLE001
        pass
    b._pw.stop()
    return {"message": f"KOLIS 종 상세 화면을 열었습니다: {title or species_key}"}

