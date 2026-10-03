"""개발용: 제어 포트(9333, bin/app_debug.bat)로 띄운 프로그램 창에 Playwright 로 붙어 실제 버튼을 누른다(프로그램 창 시험).
쓰는 법: .venv/Scripts/python.exe -X utf8 tools/ui_drive.py build <원부번호> <회차번호>   → 새 작품 탭 → B 단계 → 원부번호·회차 → 「값 채우기」 → 끝날 때까지 기다려 캡처
         .venv/Scripts/python.exe -X utf8 tools/ui_drive.py shot <이름>                    → 지금 화면 캡처만
저장 버튼은 누르지 않는다."""
import sys, time, json, datetime
from pathlib import Path
from playwright.sync_api import sync_playwright
OUT = Path(__file__).resolve().parent.parent / "work" / "captures" / "ui_review"; OUT.mkdir(parents=True, exist_ok=True)

def shot(pg, name):
    f = OUT / f"{datetime.datetime.now():%Y%m%d-%H%M%S}_{name}.png"; pg.screenshot(path=str(f)); print("캡처:", f); return f

def main():
    cmd = sys.argv[1]
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp("http://127.0.0.1:9333")
        pg = next(x for c in b.contexts for x in c.pages if "index.html" in x.url)
        pg.set_default_timeout(10000)
        if cmd == "shot":
            shot(pg, sys.argv[2] if len(sys.argv) > 2 else "app"); return
        wonbu, row = sys.argv[2], sys.argv[3]
        # 1) 새 작품 탭
        pg.evaluate("addTab()"); pg.wait_for_timeout(500)
        print("새 탭:", pg.evaluate("label(CUR)"), "| 작품 추가 패널 보임:", pg.evaluate("!document.getElementById('add-panel').hidden"))
        shot(pg, "drive_1_new_tab")
        # 2) B 단계 열고 원부번호 입력(사람이 치듯)
        pg.evaluate("openPhaseB()"); pg.wait_for_timeout(600)
        pg.fill("#b-wonbu", wonbu); pg.dispatch_event("#b-wonbu", "input"); pg.dispatch_event("#b-wonbu", "change"); pg.wait_for_timeout(1200)
        print("3-1 상태:", pg.inner_text("#c-31-state"), "| 현황 표:", pg.inner_text("#b-status")[:120].replace("\n", " / "))
        pg.evaluate("setOpen('c-32', true)"); pg.wait_for_timeout(400)
        pg.fill("#b-row", row); pg.fill("#b-manu", "")
        pg.evaluate("document.getElementById('c-32').scrollIntoView({block:'start'})"); pg.wait_for_timeout(300)
        shot(pg, "drive_2_before_build")
        # 3) 「값 채우기 — 저장하지 않음」 누르기
        assert not pg.is_disabled("#btn-build"), "값 채우기 단추가 꺼져 있음"
        pg.click("#btn-build"); pg.wait_for_timeout(1500)
        print("눌렀음. b-out:", pg.inner_text("#b-out")[:100], "| 카드 상태:", pg.get_attribute("#c-32", "data-state"))
        shot(pg, "drive_3_running")
        # 4) 끝날 때까지(최대 10분)
        t0 = time.time()
        while time.time() - t0 < 600:
            running = pg.evaluate("!!(CUR && CUR.running && CUR.running.build)")
            if not running: break
            pg.wait_for_timeout(5000)
        print(f"걸린 시간 {int(time.time()-t0)}초 | b-out:", pg.inner_text("#b-out")[:160].replace("\n", " "))
        pg.evaluate("document.getElementById('c-32').scrollIntoView({block:'start'})"); pg.wait_for_timeout(300)
        shot(pg, "drive_4_done_top")
        pg.evaluate("document.getElementById('b-result').scrollIntoView({block:'start'})"); pg.wait_for_timeout(300)
        shot(pg, "drive_5_result")
        print("저장 단추 상태: disabled =", pg.is_disabled("#btn-bsave"), "(체크 전이라 꺼져 있어야 정상)")
        print("3-2 상태:", pg.inner_text("#c-32-state"), "| B 상태:", pg.inner_text("#ph-b-state"))

if __name__ == "__main__":
    main()
