"""5.1 복본조사KEY설정: 버튼으로 팝업을 열고(읽기), 가이드 그림 21 대로 체크만 한다. 저장은 'save' 인자가 있을 때만."""
import sys, time; sys.stdout.reconfigure(encoding="utf-8")
from kolis_tool.kolis_browser import Browser
b = Browser(lambda m: None); p = b.page
do_save = "save" in sys.argv[1:]
pops = [pg for pg in b.ctx.pages if "dupexminkeyset" in pg.url]
main = next(pg for pg in b.ctx.pages if "onlineBundleDupExmin" in pg.url); b.page = main
if pops and "reopen" in sys.argv[1:]:
    pops[0].click("#btnClose"); b._rec("click", selector="닫기(KEY설정 팝업)", changes=False); b.wait(1.0); pops = []
if not pops:
    with b.ctx.expect_page(timeout=15000) as ev:
        b.click("#btnDupExminKeySet", changes=False)
    pop = ev.value
else:
    pop = pops[0]
pop.wait_for_load_state("domcontentloaded"); pop.wait_for_timeout(1500)
b._hook(pop)
print("팝업 주소:", pop.url)
WANT = {"on_use_yn": True, "media_code_use_yn": True, "digital_mat_type_use_yn": True, "author_use_yn": True}
if not do_save:
    for name, v in WANT.items():
        el = pop.locator(f"input[name={name}]").locator("visible=true").first
        if el.is_checked() != v:
            el.set_checked(v); b._rec("check", name=name, value=v)
    pop.locator("input[name=title_search_type][value=R]").locator("visible=true").first.set_checked(True)
state = pop.evaluate(r"Array.from(document.querySelectorAll('input[type=checkbox],input[type=radio]')).filter(e=>e.offsetParent!==null).map(e=>(e.checked?'[v] ':'[ ] ')+((e.closest('label')||e.parentElement).innerText||'').trim().split(/\s*\n/)[0]+' <'+e.name+'>')")
print("팝업 상태:"); [print("  ", x) for x in state]
pop.bring_to_front()
import datetime; from pathlib import Path
d = Path("work/captures/browser"); f = d / f"{datetime.datetime.now():%Y%m%d-%H%M%S}_keyset_popup.png"; pop.screenshot(path=str(f)); print("캡처:", f)
if do_save:
    b._rec("click", selector="저장(KEY설정 팝업)", approved=True, changes=True)
    pop.on("dialog", lambda dlg: (b._rec("dialog", message=dlg.message, action="accept"), print("확인창:", dlg.message), dlg.accept()))
    pop.click("#btnSave"); pop.wait_for_timeout(2000)
    print("저장 뒤 팝업 열려 있음:", not pop.is_closed())
b.close()
