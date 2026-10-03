"""주제명 팝업에서 '만화' 더블클릭 → + → 확인 ; 장르 팝업에서 '웹툰' 검색 → 더블클릭 → + → 확인. 폼 값 확인. 저장 안 함."""
import sys, json, datetime; sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path
from kolis_tool.kolis_browser import Browser
b = Browser(print)
mods = next(pg for pg in b.ctx.pages if "onContentsDetailPop" in pg.url); b.page = mods
def shot(pg, name):
    f = Path("work/captures/browser") / f"{datetime.datetime.now():%Y%m%d-%H%M%S}_{name}.png"; pg.screenshot(path=str(f)); print("캡처:", f)
def pick(pop, control_no, label):
    rows = pop.evaluate("$('#jqxgrid1').jqxGrid('getrows').map(r=>({NAME:r.NAME,NO:r.TERM_CONTROL_NO,i:r.uid}))")
    hit = next((r for r in rows if r["NO"] == control_no), None)
    print(f"[{label}] 후보 {len(rows)}건, {control_no}:", hit); assert hit is not None
    pop.evaluate(f"$('#jqxgrid1').jqxGrid('ensurerowvisible', {hit['i']})"); pop.wait_for_timeout(500)
    cell = pop.locator("#jqxgrid1 [role=gridcell]", has_text=hit["NAME"]).first
    cell.dblclick(); pop.wait_for_timeout(1500)
    print("  용어 패널:", pop.evaluate("({term:$('#desc').val(), cat:$('#category').val(), arTag:$('#arTag').val(), arNo:$('#arTermControlNo').val()})"))
    pop.click("#btnDiv"); pop.wait_for_timeout(800)
    print("  + 뒤:", pop.evaluate("({arTag:$('#arTag').val(), arNo:$('#arTermControlNo').val()})"))
    b._rec("select-row", popup=label, id=control_no)
    pop.click("#btnConfirm"); b._rec("click", selector=f"확인({label} 팝업)", changes=False); mods.wait_for_timeout(1500)
    print("  팝업 닫힘:", pop.is_closed())
def form():
    return mods.evaluate("({topic:$('#_subject_topic188').val(), id:$('#_subject_ID182').val(), auth:$('#_subject_authority184').val(), authURI:$('[name=\"_subject@authorityURI\"]').val(), genre:$('#_subject_genre198').val(), genres:$('[name=\"_subject_genre\"]').map(function(){return this.value}).get(), topics:$('[name=\"_subject_topic\"]').map(function(){return this.value}).get(), ids:$('[name=\"_subject@ID\"]').map(function(){return this.value}).get()})")
print("폼(전):", form())
sp = next((pg for pg in b.ctx.pages if "subjNmPop" in pg.url), None)
if sp is None:
    with b.ctx.expect_page(timeout=20000) as ev:
        mods.evaluate("subjectSearchPop('_subject_topic188', '_subject_ID182', '_subject_topic', '_subject_authority184', '_subject180', '_subject_topic188')")
    sp = ev.value; sp.wait_for_load_state("domcontentloaded"); sp.wait_for_timeout(2500); b._hook(sp)
pick(sp, "KSH1998022212", "주제명 만화")
print("폼(만화 뒤):", form())
with b.ctx.expect_page(timeout=20000) as ev:
    mods.evaluate("subjectSearchPop('_subject_genre198', '_subject_ID182', '_subject_genre', '_subject_authority184', '_subject180', '_subject_topic188')")
gp = ev.value; gp.wait_for_load_state("domcontentloaded"); gp.wait_for_timeout(2500); b._hook(gp)
print("장르 팝업:", gp.url, "| 검색어:", gp.input_value("#keyword"))
if gp.input_value("#keyword") != "웹툰":
    gp.fill("#keyword", "웹툰"); gp.click("#btnSearch"); gp.wait_for_timeout(2500)
rows = gp.evaluate("$('#jqxgrid1').jqxGrid('getrows').map(r=>[r.NAME,r.TERM_CONTROL_NO,r.CATEGORY])"); print("웹툰 결과:", rows[:10])
json.dump(rows, open("work/captures/wonbu/subject_search_웹툰.json","w",encoding="utf-8"), ensure_ascii=False)
shot(gp, "genre_search_웹툰")
pick(gp, "KSH2016000049", "장르주제명 웹툰")
print("폼(웹툰 뒤):", form())
mods.evaluate("document.querySelector('#_subject_topic188').scrollIntoView({block:'center'})"); shot(mods, "mods_subject_filled")
b.close()
