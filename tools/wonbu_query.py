"""개발용 조회: 원부번호로 디지털콘텐츠관리 목록을 읽는다(조회만. 저장·변경 요청 없음).
쓰는 법: python tools/wonbu_query.py <원부번호> [작성년도]
결과: work/captures/wonbu/<원부번호>_digitalcont.json (요청 본문 + 응답 그대로)"""
import sys, json, time
from pathlib import Path
from urllib.parse import urlencode
sys.stdout.reconfigure(encoding="utf-8")
from kolis_tool import kolis_http

no = sys.argv[1]; yr = sys.argv[2] if len(sys.argv) > 2 else "2026"
out = Path("work/captures/wonbu"); out.mkdir(parents=True, exist_ok=True)
fields = dict(har_type_cd="", bus_id="", coll_id="", key_arr="", acc_rec_key="", type="mo",
              work_status_list_start="DS_3200", work_status_list_end="DS_3400", har_stat_cd="30", tran_stat_cd="40",
              list_menu_id="F1131200", init_dcms_yn="", use_limit_code="", reg_code="FTX", acquisit_yr=yr,
              accession_rec_no_start=no, accession_rec_no_end=no, accession_no_start="", accession_no_end="",
              searchSpecCnt="", searchContCnt="")
body = urlencode(fields)
c = kolis_http.Client(log=print); c.login()
t0 = time.time()
r = c.send("POST", "/online/cata/bocata/digitalcont/digitalcontmng/onlineDigitalContMngList.do", body,
           "application/x-www-form-urlencoded; charset=UTF-8", wait=120)
res = {"at": time.strftime("%Y-%m-%d %H:%M:%S"), "seconds": round(time.time() - t0, 2), "body": body, "response": r}
(out / f"{no}_digitalcont.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: r.get(k) for k in ("sttus", "cnt", "contentsCnt")}, ensure_ascii=False))
lst = r.get("list") or []
print("행 수:", len(lst))
if lst:
    print("칸 이름:", list(lst[0].keys()))
    for row in lst:
        print({k: row.get(k) for k in row if k in ("SPECIES_KEY", "ACC_REC_NO", "ACCESSION_REC_NO", "TITLE", "MAIN_TITLE", "VOL", "VOLUMN", "AUTHOR", "PUBLISHER", "CONTENTS_CNT", "WORK_STATUS", "DUP_YN")} or row)
c.close()
