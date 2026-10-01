"""개발용 측정: 같은 파일 묶음을 접속 1·2·4개로 동시에 임시 위치에 전송해 합계 속도를 잰다. KOLIS 자료는 바뀌지 않는다(임시 위치에 파일만 올라간다).
쓰는 법: python tools/upload_speed.py <이미지가 든 폴더> [묶음 크기 MB=40]"""
import sys, time, uuid, datetime, threading
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
from kolis_tool import kolis_http, kolis_request as kr
root, want = Path(sys.argv[1]), float(sys.argv[2]) * 1048576 if len(sys.argv) > 2 else 40 * 1048576
files, size = [], 0
for p in sorted(root.rglob("*.jpg")):
    if size >= want: break
    files.append(p); size += p.stat().st_size
blobs = [(p.name, p.read_bytes()) for p in files]
print(f"묶음: 파일 {len(blobs)}개, {size / 1048576:.1f}MB")
for k in ([int(x) for x in sys.argv[3].split(",")] if len(sys.argv) > 3 else (1, 2, 4, 1)):
    clients = [kolis_http.Client(log=lambda m: None) for _ in range(k)]
    for c in clients: c.login()
    stamp = datetime.datetime.now().strftime("%Y%m%d") + str(int(time.time() * 1000))
    errs, sent = [], [0] * k
    def work(i):
        for j, (name, data) in enumerate(blobs):
            if j % k != i: continue
            rule = f"/Upload1/tmp/wonmun/{stamp}/speed{k}"
            try:
                a = kr.uploader_answer(clients[i].upload(kr.U_HANDLER, kr.upload_fields(str(uuid.uuid4()).upper(), f"{j:03d}_{name}", str(j), rule), f"{j:03d}_{name}", data, "image/jpeg")).split("|")
                if a[0] != "success": errs.append(a)
                else: sent[i] += len(data)
            except Exception as e:
                errs.append(str(e)[:150])
    t0 = time.time(); th = [threading.Thread(target=work, args=(i,)) for i in range(k)]
    [t.start() for t in th]; [t.join() for t in th]; sec = time.time() - t0
    print(f"접속 {k}개: {sum(sent) / 1048576:.1f}MB, {sec:.1f}초, 합계 {sum(sent) / 1048576 / sec:.2f} MB/s ({sum(sent) * 8 / 1e6 / sec:.1f} Mbps), 실패 {len(errs)} {errs[:2]}")
    for c in clients: c.close()
