"""지금 유저 Edge 창의 KOLIS 화면을 캡처하고 보이는 알림창·버튼을 읽는다(읽기만)."""
import sys; sys.stdout.reconfigure(encoding="utf-8")
from kolis_tool.kolis_browser import Browser
b = Browser(lambda m: None)
p = b.page
print("주소:", p.url)
print("캡처:", b.shot("look"))
print("모달:", p.evaluate("Array.from(document.querySelectorAll('.jqx-window:not([style*=\"display: none\"])')).map(e=>e.innerText.trim().slice(0,200))"))
b.close()
