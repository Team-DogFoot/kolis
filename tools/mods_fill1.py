"""5.3-1d: 남우 전거 검색(조회) → 주제명 '만화' 선택·확인 → 장르주제명 '웹툰' 검색·선택·확인 → 폼 값 확인. 저장 안 함."""
import sys, json, datetime; sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path
from kolis_tool.kolis_browser import Browser
b = Browser(print)
mods = next(pg for pg in b.ctx.pages if "onContentsDetailPop" in pg.url); b.page = mods
def shot(pg, name):
    f = Path("work/captures/browser") / f"{datetime.datetime.now():%Y%m%d-%H%M%S}_{name}.png"; pg.screenshot(path=str(f)); print("캡처:", f)
def grid_rows(pg, gid):
    return pg.evaluate(f"(()=>{{var n=$('#{gid}').jqxGrid('getrows');return n?n.map(r=>Object.fromEntries(Object.entries(r).filter(([k,v])=>v!==null&&v!==''&&v!==false&&k!=='_chk'&&k!=='uid'&&k!=='boundindex'&&k!=='visibleindex'&&k!=='uniqueid'))):[]}})()")
# 1) 저자전거 팝업에서 남우 검색
ap = next((pg for pg in b.ctx.pages if "ACControl.do" in pg.url), None)
if ap:
    ap.fill("#keyword", "남우"); b._rec("fill", selector="전거 팝업 #keyword", value="남우")
    ap.click("#btnSearch"); ap.wait_for_timeout(3000)
    rows = grid_rows(ap, "jqxgrid1"); print("남우 전거 후보:", len(rows))
    for r in rows: print("  ", {k: str(v)[:40] for k, v in r.items() if k in ("CHOICE_SIGNPOST","AC_CONTROL_NO","BIRTH_YEAR","JOB","BRANCH","SUMMARY","SPECIESA_CNT")})
    json.dump(rows, open("work/captures/wonbu/author_search_남우.json","w",encoding="utf-8"), ensure_ascii=False, indent=1)
    shot(ap, "author_search_남우")
    ap.click("#btnClose"); b._rec("click", selector="닫기(전거 팝업, 선택 없음)", changes=False); mods.wait_for_timeout(800)
# 2) 주제명 팝업: 만화 1행 선택 → 확인
sp = next((pg for pg in b.ctx.pages if "subjNmPop" in pg.url), None)
if sp:
    sp.evaluate("$('#jqxgrid1').jqxGrid('selectrow',0); $('#jqxgrid1').jqxGrid('setcellvalue',0,'_chk',true);")
    r0 = sp.evaluate("$('#jqxgrid1').jqxGrid('getrowdata',0)"); print("선택한 주제명:", r0.get("NAME"), r0.get("TERM_CONTROL_NO"))
    b._rec("select-row", popup="주제명", row=r0.get("NAME"), id=r0.get("TERM_CONTROL_NO"))
    sp.click("#btnConfirm"); b._rec("click", selector="확인(주제명 팝업)", changes=False); mods.wait_for_timeout(1500)
    print("주제명 팝업 닫힘:", sp.is_closed())
print("폼 주제명 칸:", mods.evaluate("({topic:$('#_subject_topic188').val(), id:$('#_subject_ID182').val(), auth:$('#_subject_authority184').val(), genre:$('#_subject_genre198').val()})"))
# 3) 장르주제명: 웹툰 검색·선택·확인
with b.ctx.expect_page(timeout=20000) as ev:
    mods.evaluate("subjectSearchPop('_subject_genre198', '_subject_ID182', '_subject_genre', '_subject_authority184', '_subject180', '_subject_topic188')")
gp = ev.value; gp.wait_for_load_state("domcontentloaded"); gp.wait_for_timeout(2500); b._hook(gp)
print("장르 팝업 주소:", gp.url)
if gp.input_value("#keyword") != "웹툰":
    gp.fill("#keyword", "웹툰"); gp.click("#btnSearch"); gp.wait_for_timeout(2500)
rows = grid_rows(gp, "jqxgrid1"); print("웹툰 검색 결과:", [(r.get("NAME"), r.get("TERM_CONTROL_NO"), r.get("CATEGORY")) for r in rows[:10]])
json.dump(rows, open("work/captures/wonbu/subject_search_웹툰.json","w",encoding="utf-8"), ensure_ascii=False, indent=1)
idx = next((i for i, r in enumerate(rows) if r.get("TERM_CONTROL_NO") == "KSH2016000049"), None)
print("KSH2016000049 행:", idx)
shot(gp, "genre_search_웹툰")
if idx is not None:
    gp.evaluate(f"$('#jqxgrid1').jqxGrid('selectrow',{idx}); $('#jqxgrid1').jqxGrid('setcellvalue',{idx},'_chk',true);")
    b._rec("select-row", popup="장르주제명", row=rows[idx].get("NAME"), id="KSH2016000049")
    gp.click("#btnConfirm"); b._rec("click", selector="확인(장르 팝업)", changes=False); mods.wait_for_timeout(1500)
print("폼 주제명 칸(뒤):", mods.evaluate("({topic:$('#_subject_topic188').val(), id:$('#_subject_ID182').val(), auth:$('#_subject_authority184').val(), authURI:$('[name=\"_subject@authorityURI\"]').val(), genre:$('#_subject_genre198').val()})"))
mods.evaluate("document.querySelector('#_subject_topic188').scrollIntoView({block:'center'})"); shot(mods, "mods_subject_filled")
b.close()
