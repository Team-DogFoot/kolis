"""5.1-④ 복본조사 완료(유저 승인 뒤에만). '완 료' 버튼 → 확인창 '예' → 알림 확인. 그 뒤 조회로 상태 변화를 확인한다."""
import sys, json; sys.stdout.reconfigure(encoding="utf-8")
from urllib.parse import urlencode
from kolis_tool.kolis_browser import Browser
b = Browser(print)
main = next(pg for pg in b.ctx.pages if "onlineBundleDupExmin" in pg.url); b.page = main
vals = b.eval("({yr: $('#acquisit_yr').val(), reg: $('#reg_code').val(), no: $('#accession_rec_no_start').val()})")
print("화면 값:", vals); assert vals == {"yr": "2026", "reg": "FTX", "no": "1607"}
msgs = []
def on_dialog(d):
    msgs.append((d.type, d.message))
    if d.type == "confirm":
        ok = "복본조사완료" in d.message
        b._rec("dialog", type=d.type, message=d.message, action="accept" if ok else "dismiss"); (d.accept() if ok else d.dismiss())
    else:
        b._rec("dialog", type=d.type, message=d.message, action="accept(알림)"); d.accept()
main.remove_listener("dialog", b._on_dialog); main.on("dialog", on_dialog)
b._rec("click", selector="#btnComplete(완료)", approved=True, changes=True)
main.click("#btnComplete"); b.wait(4.0)
print("확인창:", msgs)
print("캡처:", b.shot("dupexmin_1607_complete"))
# 확인 조회 (Edge 의 쿠키로, 로그인 다시 안 함)
import requests
s = requests.Session(); s.cookies.update(b.cookies()); H = {"X-Requested-With": "XMLHttpRequest", "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}
BASE = "http://kolis.nl.go.kr"
r = s.post(BASE + "/online/reg/bo/accrecmng/onlineAccRecMng/selectAccRecMngListWithParam.do", headers=H, data=urlencode({"acc_rec_key":"","key_arr":"","har_stat_cd":"20","use_limit_code":"","reg_code":"FTX","accession_rec_make_year":"2026","rec_no_yn":"Y","accession_rec_no":"1607","species":"","book":"","missingregnocnt":""}), timeout=60).json()
st = {(x["WORKING_STATUS"], x.get("WORKING_STATUS_NAME")) for x in r.get("list", [])}
print("등록원부관리 1607:", len(r.get("list", [])), "건, 작업상태:", st)
b._rec("verify", what="등록원부관리 작업상태", count=len(r.get("list", [])), status=sorted(map(str, st)))
f = dict(har_type_cd="", bus_id="", coll_id="", key_arr="", acc_rec_key="", type="mo", work_status_list_start="DS_3200", work_status_list_end="DS_3400", har_stat_cd="30", tran_stat_cd="40", list_menu_id="F1131200", init_dcms_yn="", use_limit_code="", reg_code="FTX", acquisit_yr="2026", accession_rec_no_start="1607", accession_rec_no_end="1607", accession_no_start="", accession_no_end="", searchSpecCnt="", searchContCnt="")
r2 = s.post(BASE + "/online/cata/bocata/digitalcont/digitalcontmng/onlineDigitalContMngList.do", headers=H, data=urlencode(f), timeout=60).json()
print("디지털콘텐츠관리 1607:", r2.get("cnt"), "종,", r2.get("contentsCnt"), "콘텐츠")
b._rec("verify", what="디지털콘텐츠관리 조회", cnt=r2.get("cnt"), contentsCnt=r2.get("contentsCnt"))
json.dump(r2, open("work/captures/wonbu/1607_digitalcont_after_complete.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
b.close()
