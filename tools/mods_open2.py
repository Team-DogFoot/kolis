"""5.3-1b: 종·콘텐츠 화면에서 MODS수정 → MODS 수정 화면 열고 현재 값 읽기. 저장 없음."""
import sys, json, datetime, re; sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path
from kolis_tool.kolis_browser import Browser
b = Browser(print)
spec = next(pg for pg in b.ctx.pages if "onSpecViewPop" in pg.url); b.page = spec
def shot(pg, name, full=False):
    f = Path("work/captures/browser") / f"{datetime.datetime.now():%Y%m%d-%H%M%S}_{name}.png"; pg.screenshot(path=str(f), full_page=full); print("캡처:", f); return f
mods = [pg for pg in b.ctx.pages if "onContentsDetailPop" in pg.url]
if not mods:
    with b.ctx.expect_page(timeout=20000) as ev:
        b.click("#btnModCnts", changes=False)
    mods = ev.value
else:
    mods = mods[0]
mods.wait_for_load_state("domcontentloaded"); mods.wait_for_timeout(4000); b._hook(mods)
print("MODS 수정 화면:", mods.url)
vals = mods.evaluate("""Array.from(document.querySelectorAll('#harContentsUpdateForm input:not([type=hidden]):not([type=button]), #harContentsUpdateForm select, #harContentsUpdateForm textarea')).filter(e=>e.offsetParent!==null && (e.value||'').trim()!=='').map(e=>e.name+' = '+e.value)""")
print("값이 든 칸:", len(vals)); [print("  ", v[:120]) for v in vals]
Path("work/captures/wonbu/mods_form_1_values.json").write_text(json.dumps(vals, ensure_ascii=False, indent=1), encoding="utf-8")
Path("work/captures/wonbu/mods_form_1.html").write_text(mods.content(), encoding="utf-8")
btns = mods.evaluate("Array.from(document.querySelectorAll('input[type=button],button')).filter(e=>e.offsetParent!==null).map(e=>(e.value||e.innerText).trim()+'<'+(e.id||e.getAttribute('onclick')||'')+'>').slice(0,60)")
print("버튼:", btns)
shot(mods, "mods_edit_1", full=True)
b.close()
