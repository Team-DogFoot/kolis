"""개발용: 가짜 백엔드로 index.html 을 띄워 왼쪽 열의 스크롤 높이와 접힘 상자 높이를 잰다(스크롤이 막히는 문제 재현용). 실행: .venv/Scripts/python.exe -X utf8 tools/ui_measure.py"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from playwright.sync_api import sync_playwright
src = Path(__file__).with_name("ui_shots.py").read_text(encoding="utf-8")
ns = {}
exec(src[:src.index("with sync_playwright()")], ns)       # MOCK, html 정의만 가져온다
with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge", headless=True); pg = b.new_page(viewport={"width": 1362, "height": 860})
    pg.add_init_script(ns["MOCK"]); pg.goto(ns["html"]); pg.wait_for_timeout(1500)
    m = pg.evaluate("""(()=>{const l=document.getElementById('left'); const fb=document.querySelector('#ph-b > .fb');
      return {scrollH:l.scrollHeight, clientH:l.clientHeight, tabBody:document.getElementById('tab-body').offsetHeight, phB:document.getElementById('ph-b').offsetHeight,
              c32:document.getElementById('c-32').offsetHeight, fbH:fb.offsetHeight, fbRows:getComputedStyle(fb).gridTemplateRows, innerH:fb.firstElementChild.scrollHeight}})()""")
    print(json.dumps(m))
    pg.evaluate("document.getElementById('left').scrollTop=99999"); pg.wait_for_timeout(300)
    print("scrollTop after:", pg.evaluate("document.getElementById('left').scrollTop"))
    pg.screenshot(path=str(Path(__file__).resolve().parent.parent / "work/captures/ui_review/scroll_test.png"))
    b.close()
