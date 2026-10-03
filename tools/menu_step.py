"""유저 Edge 창에서 메뉴를 한 번에 하나씩 누르고 캡처한다(가이드 순서 확인용). 쓰는 법: python tools/menu_step.py <동작> ... 동작: close-notice | click <글자> | shot <이름> | value <선택자>"""
import sys, time; sys.stdout.reconfigure(encoding="utf-8")
from kolis_tool.kolis_browser import Browser
b = Browser(lambda m: None); p = b.page
a = sys.argv[1:]; i = 0
while i < len(a):
    op = a[i]; i += 1
    if op == "close-notice":
        n = p.evaluate("""(()=>{let c=0;document.querySelectorAll('.jqx-window').forEach(w=>{if(w.offsetParent!==null){const bt=[...w.querySelectorAll('input[type=button],button')].find(x=>(x.value||x.innerText||'').trim()=='닫기');if(bt){bt.click();c++;}}});return c;})()""")
        b._rec("close-notice", count=n); print("공지 닫음:", n); time.sleep(0.8)
    elif op == "click":
        t = a[i]; i += 1
        b._rec("menu", step=t); p.get_by_text(t, exact=True).locator("visible=true").first.click(timeout=10000); time.sleep(1.5); print("눌렀음:", t, "| 주소:", p.url)
    elif op == "shot":
        print("캡처:", b.shot(a[i])); i += 1
    elif op == "value":
        print(a[i], "=", p.input_value(a[i])); i += 1
    elif op == "select":
        b.select(a[i], a[i+1]); print("선택:", a[i], a[i+1]); i += 2
    elif op == "fill":
        b.fill(a[i], a[i+1]); print("입력:", a[i], a[i+1]); i += 2
    elif op == "wait":
        p.wait_for_selector(a[i], timeout=30000); time.sleep(2); print("화면 열림:", p.url); i += 1
    elif op == "modals":
        print("모달:", p.evaluate("Array.from(document.querySelectorAll('.jqx-window')).filter(e=>e.offsetParent!==null).map(e=>e.innerText.trim().slice(0,80))"))
b.close()
