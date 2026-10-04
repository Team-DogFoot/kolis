"""개발용(맥북 임시): 프로그램 창 없이 1단계(납품 폴더 → 반입용 엑셀)를 돌린다. 유저 규칙 "시험은 프로그램 창으로"에는 맞지 않으므로 보고에 그대로 적는다.
실행: KOLIS_AGENT_HOME=/private/tmp/kolis_agent .venv-mac/bin/python -X utf8 tools/run_prepare_cli.py "<납품 폴더>" [--note "2026-납본-웹툰대행(5차)(100)"] [--instr "..."]
로그는 work/logs/prepare-cli-<시각>.log 에도 남는다."""
import sys, os, json, time, argparse, threading
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
from kolis_tool import prepare

ap = argparse.ArgumentParser(); ap.add_argument("folder"); ap.add_argument("--note", default=""); ap.add_argument("--instr", default=""); ap.add_argument("--timeout", type=int, default=3600)
ns = ap.parse_args()
work = ROOT / "work"; (work / "logs").mkdir(parents=True, exist_ok=True)
logp = work / "logs" / f"prepare-cli-{time.strftime('%Y%m%d-%H%M%S')}.log"
lock = threading.Lock()


def log(m):
    line = f"[{time.strftime('%H:%M:%S')}] {m}"
    with lock:
        print(line, flush=True)
        with open(logp, "a", encoding="utf-8") as f:
            f.write(line + "\n")


handle = {"cancel": False}
t0 = time.time()
try:
    r = prepare.run(Path(ns.folder), work, None, ns.instr, ns.note, log, handle, timeout=ns.timeout)
    log(f"끝: {r['output_xlsx']} · {r['rows']}행 · {r.get('columns')}열 · 확인할 칸 {r['confirm_cells']} · {int(time.time() - t0)}초 · 턴 {r['run'].get('turns')} · 토큰 {r['run'].get('usage_text')}")
except SystemExit as e:
    log(f"중단: {e} · 토큰 {prepare.agent.usage_line(handle)}")
    raise
