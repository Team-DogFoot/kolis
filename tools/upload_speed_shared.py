"""개발용 측정: 로그인은 한 번만 하고, 그 쿠키를 연결 N개가 같이 써서 동시에 전송했을 때의 합계 속도. (tools/upload_speed.py 는 연결마다 따로 로그인)
쓰는 법: python tools/upload_speed_shared.py <이미지 폴더> [묶음 MB=60] [연결 수 목록=1,4,8]"""
import sys, time, uuid, datetime, threading
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
import requests
from kolis_tool import kolis_http, kolis_request as kr
root, want = Path(sys.argv[1]), float(sys.argv[2]) * 1048576 if len(sys.argv) > 2 else 60 * 1048576
ks = [int(x) for x in sys.argv[3].split(",")] if len(sys.argv) > 3 else [1, 4, 8]
blobs, size = [], 0
for p in sorted(root.rglob("*.jpg")):
    if size >= want: break
    blobs.append((p.name, p.read_bytes())); size += p.stat().st_size
c = kolis_http.Client(log=lambda m: None); c.login()
print(f"묶음: 파일 {len(blobs)}개, {size / 1048576:.1f}MB | 로그인 1번, 쿠키 {len(c.s.cookies)}개")
def session():
    s = requests.Session(); s.trust_env = False; s.headers.update(c.s.headers); s.cookies.update(c.s.cookies); return s
for k in ks:
    ss = [session() for _ in range(k)]
    stamp = datetime.datetime.now().strftime("%Y%m%d") + str(int(time.time() * 1000)); errs, sent = [], [0] * k
    def work(i):
        for j, (name, data) in enumerate(blobs):
            if j % k != i: continue
            rule = f"/Upload1/tmp/wonmun/{stamp}/shared{k}"
            try:
                r = ss[i].post(kr.BASE + kr.U_HANDLER, data=kr.upload_fields(str(uuid.uuid4()).upper(), f"{j:03d}_{name}", str(j), rule), files={"fileToUpload": (f"{j:03d}_{name}", data, "image/jpeg")},
                               timeout=(30, 300), headers={"Referer": kr.BASE + "/online/cmmn/contentsTextRegPop.do?har_type_cd=62&directory="})
                a = kr.uploader_answer(r.text).split("|")
                if r.status_code != 200 or a[0] != "success" or a[3] != str(len(data)): errs.append((r.status_code, a[:2]))
                else: sent[i] += len(data)
            except Exception as e:
                errs.append(str(e)[:150])
    t0 = time.time(); th = [threading.Thread(target=work, args=(i,)) for i in range(k)]
    [t.start() for t in th]; [t.join() for t in th]; sec = time.time() - t0
    print(f"연결 {k}개(로그인 하나): {sum(sent) / 1048576:.1f}MB, {sec:.1f}초, 합계 {sum(sent) / 1048576 / sec:.2f} MB/s, 실패 {len(errs)} {errs[:2]}")
r = c.send("POST", kr.U_DIR, "har_type_cd=62", kr.FORM); print("측정 뒤 원래 접속이 살아 있음:", bool(r.get("direPath")))
c.close()
