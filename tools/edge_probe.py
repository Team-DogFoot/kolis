"""개발용: 유저가 로그인해 둔 Edge 창(KOLIS)에 UIA 로 붙어 지금 화면의 제목·모드·보이는 링크·버튼·입력 칸을 읽는다(읽기만, 누르지 않음)."""
import sys, re
sys.stdout.reconfigure(encoding="utf-8")
from kolis_tool import kolis_ui as ui

win = ui.edge_window(print)
print("제목:", win.window_text())
ies = win.descendants(class_name="Internet Explorer_Server")
print("IE 모드:", "예" if ies else "아니오(일반 모드)")
root = ui.ie_content(win) if ies else win
def names(ct):
    out = []
    for e in root.descendants(control_type=ct):
        t = re.sub(r"\s+", " ", e.window_text() or "").strip()
        if t and e.rectangle().width() > 0: out.append(t)
    return out
for ct in ("Hyperlink", "Button", "Edit", "ComboBox", "Text"):
    n = names(ct); print(f"{ct} {len(n)}:", " | ".join(n[:80]))
