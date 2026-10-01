"""개발용 확인: 원문 파일을 연결 8개(로그인 하나의 쿠키를 같이 씀)로 동시에 보낸 뒤, 목록 등록 → 정보입력 → 원문등록이 정상인지 실제 접수 건으로 본다.
새 접수번호가 하나 생긴다(취소 요청 목록에 적는다). 썸네일·등록대상처리·가원부번호는 하지 않는다.
방법: upload_folders 는 그대로 두고, 접속 객체의 upload 만 바꾼다 — 예상 응답을 바로 돌려주고 실제 전송은 뒤에서 동시에 하며, 다음 요청(목록 등록)이 나가기 전에 전부 끝나기를 기다려 실제 응답이 예상과 같은지 본다."""
import sys, json, glob, time, base64, datetime, threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
import requests
from kolis_tool import kolis_http, kolis_request as kr, kolis_flow, cnts_folders
from kolis_tool.ids_from_export import receipt_map

N = int(sys.argv[1]) if len(sys.argv) > 1 else 8
work = json.load(open(glob.glob("work/484*재실행.작업.json")[0], encoding="utf-8"))
xlsx, root, note, year, wd = Path(work["output_xlsx"]), Path(work["manuscripts"]), "2026-납본-웹툰대행(5차)(484)", "2026", Path("work")

class Parallel:
    def __init__(self, c, n):
        self.c, self.pool, self.jobs, self.local, self.t0, self.bytes = c, ThreadPoolExecutor(n), [], threading.local(), None, 0
    def _session(self):
        if not hasattr(self.local, "s"):
            s = requests.Session(); s.trust_env = False; s.headers.update(self.c.s.headers); s.cookies.update(self.c.s.cookies); self.local.s = s
        return self.local.s
    def _post(self, path, fields, name, data, mime):
        r = self._session().post(kr.BASE + path, data=fields, files={"fileToUpload": (name, data, mime)}, timeout=(30, 300),
                                 headers={"Referer": kr.BASE + "/online/cmmn/contentsTextRegPop.do?har_type_cd=62&directory="})
        return r.status_code, kr.uploader_answer(r.text)
    def upload(self, path, fields, name, data, mime, wait=300.0, note=None):
        self.c.login(); self.t0 = self.t0 or time.time(); self.bytes += len(data)
        expect = f"success|{name}::/{note['rule']}/{name}|{name}|{len(data)}"
        self.jobs.append((name, expect, self.pool.submit(self._post, path, fields, name, data, mime)))
        return base64.b64encode(("R" + base64.b64encode(expect.encode()).decode()).encode()).decode()
    def drain(self):
        bad = []
        for name, expect, f in self.jobs:
            st, ans = f.result()
            if st != 200 or ans != expect: bad.append((name, st, ans[:120], expect[:120]))
        if self.jobs:
            sec = time.time() - self.t0
            print(f"  동시 전송 끝: 파일 {len(self.jobs)}개, {self.bytes / 1048576:.1f}MB, {sec:.1f}초, {self.bytes / 1048576 / sec:.2f} MB/s, 예상과 다른 응답 {len(bad)} {bad[:2]}")
        self.jobs = []
        if bad: raise kr.Stop(f"전송 응답이 예상과 다릅니다: {bad[:3]}")
    def send(self, *a, **k):
        self.drain(); return self.c.send(*a, **k)
    def __getattr__(self, k): return getattr(self.c, k)

c = kolis_http.Client(log=lambda m: None)
if any(p.name.startswith("CNTS-") for p in root.iterdir()): print("폴더 이름 되돌림", cnts_folders.undo(root))
info = kolis_flow._excel_rows(xlsx)
r = kr.import_excel(c, year, note, xlsx, info["rows"], "YES", print)
receipt = r["receipt"]
row = {"처리": kolis_flow.CANCEL, "작품": "옆집 기러기 아빠 구워 먹기", "접수번호": receipt, "가원부번호": "", "건수": r["count"], "콘텐츠ID": f"{r['ids'][0]} ~ {r['ids'][-1]}",
       "비고": note, "결과": "동시 전송 확인용(원문등록까지)", "반입 시각": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "실행 기록": "tools/parallel_flow_check.py"}
kolis_flow.ledger_put(wd, row)
print("접수번호", receipt, r["count"], "건")
ex = kr.export_receipt(c, year, receipt, wd, print)
ids = [x["cnts"] for x in receipt_map(Path(ex["file"]))]
cnts_folders.apply(Path(ex["file"]), root)
checks = []
def check(name, ok, value="", why=""):
    checks.append(ok)
    if not ok: print("  확인 ✗", name, value); raise SystemExit("멈춤: " + name)
t0 = time.time()
res = kr.upload_folders(Parallel(c, N), year, receipt, root, ids, lambda m: print(m) if "전송" in m or "등록" in m[:8] else None, {}, check)
print(f"원문일괄등록 전체 {time.time() - t0:.1f}초 | 확인 {len(checks)}개 통과 |", {k: res[k] for k in ("folders", "files", "mb")})
after = {i["CONTENTS_ID"]: i.get("CNT_FILES") for i in kr.receipt_items(c, year, receipt)}
print("건별 원문 수:", after)
from kolis_tool import kolis_modify as km
for cid in ids[:3] + ids[-1:]:
    v = [(x["TEXT_GBN"], x["FILE_SIZE"], x["REG_DT"]) for x in km.files(c, cid) if str(x.get("FILE_ID", "")).startswith("FILE-")]
    local = sum(p.stat().st_size for p in (root / cid).iterdir())
    print(" ", cid, v, "| PC 의 파일 합계", local)
c.close()
