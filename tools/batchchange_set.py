"""5.2 일괄변경 팝업에 가이드 그림 24 의 값을 넣는다(저장 안 함). 'save' 인자가 있을 때만 저장."""
import sys, json, datetime; sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path
from kolis_tool.kolis_browser import Browser
do_save = "save" in sys.argv[1:]
b = Browser(print)
main = next(pg for pg in b.ctx.pages if "onlineDigitalContMng.do" in pg.url); b.page = main
pop = next(pg for pg in b.ctx.pages if "codeMngPop" in pg.url); b._hook(pop)
WANT = {"offer_dbcode_1s": "CH1", "offer_dbcode_2s": "CH11", "publisher_code": "PE", "kogl_code": ""}
if not do_save:
    for sid, v in WANT.items():
        pop.select_option(f"#{sid}", v); b._rec("select", selector=f"팝업 #{sid}", value=v)
        pop.evaluate(f"document.querySelector('#{sid}').dispatchEvent(new Event('change', {{bubbles:true}}))"); pop.wait_for_timeout(500)
sel = pop.evaluate("Array.from(document.querySelectorAll('select')).map(s=>s.id+' = '+s.value+' ('+(s.selectedOptions[0]?s.selectedOptions[0].text:'')+')')")
print("팝업 값:"); [print("  ", x) for x in sel]
print("표 체크 수:", main.evaluate("(()=>{var c=0;for(var i=0;i<grid.getRowsCount();i++){if($('#jqxgrid').jqxGrid('getcellvalue',i,'_chk'))c++;}return c;})()"))
f = Path("work/captures/browser") / f"{datetime.datetime.now():%Y%m%d-%H%M%S}_codeMngPop_set.png"; pop.screenshot(path=str(f)); print("팝업 캡처:", f)
if do_save:
    msgs = []
    def on_dialog(d):
        msgs.append((d.type, d.message)); b._rec("dialog", type=d.type, message=d.message, action="accept"); d.accept()
    pop.remove_listener("dialog", b._on_dialog); pop.on("dialog", on_dialog)
    main.remove_listener("dialog", b._on_dialog); main.on("dialog", on_dialog)
    b._rec("click", selector="저장(일괄변경 팝업)", approved=True, changes=True)
    pop.click("#btnSave"); main.wait_for_timeout(4000)
    print("확인창:", msgs, "| 팝업 닫힘:", pop.is_closed())
    print("본화면 캡처:", b.shot("digitalcont_1607_after_batch"))
b.close()
