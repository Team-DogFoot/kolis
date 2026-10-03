"""개발용: 작품 단위 판단의 동시성 시험. 원부 여러 개의 회차 화면 값을 순서대로 읽고(Edge, 하나씩), AI 판단은 작품마다 동시에 돌린다(Edge 안 씀).
쓰는 법: .venv/Scripts/python.exe -X utf8 -u tools/batch_drive.py 1607 1610 1614 [--skip-collect]
기록: work/build/batch_drive.log(이 실행), 원부별 work/build/wonbu_<번호>/batch.jsonl, 에이전트 로그는 각 줄 앞에 [원부] 표시."""
import sys, time, threading, json, traceback
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from kolis_tool import mods_batch

LOG = Path("work/build/batch_drive.log")
lock = threading.Lock()
def log(prefix):
    def f(m):
        line = f"{time.strftime('%H:%M:%S')} [{prefix}] {m}"
        with lock:
            print(line, flush=True)
            with open(LOG, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
    return f

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    skip_collect = "--skip-collect" in sys.argv
    if not skip_collect:
        for w in args:
            t0 = time.time()
            try:
                mods_batch.collect_work(w, log(w))
                log(w)(f"화면 읽기 끝 {time.time() - t0:.0f}초")
            except Exception as e:
                log(w)(f"!!! 화면 읽기 실패: {e}"); traceback.print_exc()
    results = {}
    def run(w):
        t0 = time.time()
        try:
            result, fails, out = mods_batch.run_work_agent(w, log(w))
            results[w] = {"seconds": round(time.time() - t0), "remaining": fails, "episodes": len(result.get("episodes") or []),
                          "authors": [(a.get("name"), a.get("decision"), a.get("confidence")) for a in result.get("authors") or []], "adult": result.get("adult")}
        except Exception as e:
            results[w] = {"error": str(e), "seconds": round(time.time() - t0)}; log(w)(f"!!! 판단 실패: {e}"); traceback.print_exc()
    t0 = time.time()
    log("동시")(f"AI 판단 {len(args)}개 동시 시작: {args}")
    ths = [threading.Thread(target=run, args=(w,), daemon=True) for w in args]
    for t in ths: t.start()
    for t in ths: t.join()
    log("동시")(f"전부 끝 {time.time() - t0:.0f}초: " + json.dumps(results, ensure_ascii=False))

if __name__ == "__main__":
    main()
