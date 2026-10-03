"""5.2 일괄변경: 메뉴로 디지털콘텐츠관리 이동 → 1607 찾기 → 전체 선택 → 일괄변경 팝업 열기 → 값 맞추기. 저장은 'save' 인자가 있을 때만."""
import sys, json, datetime; sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path
from kolis_tool.kolis_browser import Browser
do_save = "save" in sys.argv[1:]
b = Browser(print)
main = next((pg for pg in b.ctx.pages if "kolis.nl.go.kr" in pg.url and "dupexminkeyset" not in pg.url), b.page); b.page = main; p = main
if "onlineDigitalContMng.do" not in p.url:
    p.goto("http://kolis.nl.go.kr/main/gohome.do", wait_until="domcontentloaded"); b.wait(1.5)
    p.evaluate("""document.querySelectorAll('.jqx-window').forEach(w=>{if(w.offsetParent!==null){const bt=[...w.querySelectorAll('input[type=button],button')].find(x=>(x.value||x.innerText||'').trim()=='닫기');if(bt)bt.click();}})"""); b.wait(0.5)
    b._rec("menu", step="정리"); p.get_by_text("정리", exact=True).locator("visible=true").first.click(); b.wait(1.5)
    b._rec("menu", step="디지털콘텐츠"); p.get_by_text("디지털콘텐츠", exact=True).locator("visible=true").first.click(); b.wait(1.5)
    b._rec("menu", step="디지털콘텐츠관리"); p.get_by_role("link", name="디지털콘텐츠관리", exact=True).locator("visible=true").first.click()
    p.wait_for_selector("#accession_rec_no_start", timeout=30000); b.wait(2)
print("화면:", p.url)
if b.eval("$('#accession_rec_no_start').val()") != "1607":
    b.select("#reg_code", "FTX"); b.fill("#accession_rec_no_start", "1607")
    print("캡처(검색 전):", b.shot("digitalcont_1607_before_search"))
    b.click("#btnSearch", changes=False, wait=4.0)
n = b.eval("(()=>{try{return grid.getRowsCount()}catch(e){return -1}})()")
print("표 행 수:", n, "| 종수/콘텐츠수:", b.eval("[$('#searchSpecCnt').val(), $('#searchContCnt').val()]"))
assert n == 25, "25행이 아님"
b.eval("$('#jqxgrid').jqxGrid('selectallrows'); (function(){for(var i=0;i<grid.getRowsCount();i++){grid.setCellValue?grid.setCellValue(i,'_chk',true):$('#jqxgrid').jqxGrid('setcellvalue',i,'_chk',true);}})()")
b._rec("check-all", rows=n)
checked = b.eval("(()=>{var c=0;for(var i=0;i<grid.getRowsCount();i++){if($('#jqxgrid').jqxGrid('getcellvalue',i,'_chk'))c++;}return c;})()")
print("체크된 행:", checked)
print("캡처(선택 뒤):", b.shot("digitalcont_1607_checked"))
pops = [pg for pg in b.ctx.pages if "codeMngPop" in pg.url]
if not pops:
    with b.ctx.expect_page(timeout=15000) as ev:
        b.click("#btnPubCode", changes=False)
    pop = ev.value
else:
    pop = pops[0]
pop.wait_for_load_state("domcontentloaded"); pop.wait_for_timeout(1500); b._hook(pop)
print("팝업:", pop.url)
sel = pop.evaluate("Array.from(document.querySelectorAll('select')).map(s=>({id:s.id,name:s.name,value:s.value,text:s.selectedOptions[0]?s.selectedOptions[0].text:'',options:Array.from(s.options).map(o=>o.value+'|'+o.text)}))")
for s in sel: print("  선택칸", s["id"] or s["name"], "=", s["value"], s["text"], "| 선택지:", s["options"][:12])
f = Path("work/captures/browser") / f"{datetime.datetime.now():%Y%m%d-%H%M%S}_codeMngPop.png"; pop.screenshot(path=str(f)); print("팝업 캡처:", f)
json.dump(sel, open("work/captures/wonbu/codeMngPop_selects.json","w",encoding="utf-8"), ensure_ascii=False, indent=1)
b.close()
