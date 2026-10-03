"""5.3-1: 디지털콘텐츠관리 표의 1행 선택 → MODS정리(종·콘텐츠 화면) → MODS수정(MODS 수정 화면). 저장 없음."""
import sys, json, datetime; sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path
from kolis_tool.kolis_browser import Browser
b = Browser(print)
main = next(pg for pg in b.ctx.pages if "onlineDigitalContMng.do" in pg.url); b.page = main
def shot(pg, name):
    f = Path("work/captures/browser") / f"{datetime.datetime.now():%Y%m%d-%H%M%S}_{name}.png"; pg.screenshot(path=str(f)); print("캡처:", f); return f
# 1행만 체크
main.evaluate("(function(){for(var i=0;i<grid.getRowsCount();i++){$('#jqxgrid').jqxGrid('setcellvalue',i,'_chk',i==0);}})()")
b._rec("check", rows=[0])
print("1행:", main.evaluate("(()=>{var r=$('#jqxgrid').jqxGrid('getrowdata',0);return {TITLE:r.TITLE,VOL:r.VOL,SPECIES_KEY:r.SPECIES_KEY,ACCESSION_NO:r.ACCESSION_NO}})()"))
spec = [pg for pg in b.ctx.pages if "onSpecViewPop" in pg.url]
if not spec:
    with b.ctx.expect_page(timeout=20000) as ev:
        b.click("#btnModsArrange", changes=False)
    spec = ev.value
else:
    spec = spec[0]
spec.wait_for_load_state("domcontentloaded"); spec.wait_for_timeout(3000); b._hook(spec)
print("종·콘텐츠 화면:", spec.url)
print("종 화면 값:", spec.evaluate("({title:$('#title').val(), author:$('input[name=author]').val(), publisher:$('input[name=publisher]').val(), isbn:$('input[name=ea_isbn]').val(), o1:$('#offer_dbcode_1s').val(), o2:$('#offer_dbcode_2s').val()})"))
shot(spec, "specview_1")
b.close()
