"""5.3-1c: MODS 수정 화면의 찾기 팝업들(저자전거, 주제명)을 열어 검색 결과를 읽는다. 선택·저장 없음."""
import sys, json, datetime; sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path
from kolis_tool.kolis_browser import Browser
b = Browser(print)
mods = next(pg for pg in b.ctx.pages if "onContentsDetailPop" in pg.url); b.page = mods
def shot(pg, name):
    f = Path("work/captures/browser") / f"{datetime.datetime.now():%Y%m%d-%H%M%S}_{name}.png"; pg.screenshot(path=str(f)); print("캡처:", f)
def describe(pg, tag):
    print(f"[{tag}] 주소:", pg.url)
    print("  입력:", pg.evaluate("Array.from(document.querySelectorAll('input:not([type=hidden]):not([type=button]),select')).filter(e=>e.offsetParent!==null).map(e=>e.tagName+'#'+e.id+'['+e.name+']='+(e.value||'')).slice(0,30)"))
    print("  버튼:", pg.evaluate("Array.from(document.querySelectorAll('input[type=button],button')).filter(e=>e.offsetParent!==null).map(e=>(e.value||e.innerText).trim()+'<'+e.id+'>').slice(0,30)"))
    print("  표 머리:", pg.evaluate("Array.from(document.querySelectorAll('.jqx-grid-column-header')).map(e=>e.innerText.trim()).filter(Boolean).slice(0,30)"))
which = sys.argv[1] if len(sys.argv) > 1 else "author"
if which == "author":
    with b.ctx.expect_page(timeout=20000) as ev:
        mods.evaluate("popSearchNameKolis2('_name_namePart34', 34, '_name_ID26', '_name_authority28', '_name_type30')")
    pop = ev.value; pop.wait_for_load_state("domcontentloaded"); pop.wait_for_timeout(3000); b._hook(pop)
    describe(pop, "저자전거 찾기"); shot(pop, "author_search_popup")
    Path("work/captures/wonbu/author_search_popup.html").write_text(pop.content(), encoding="utf-8")
elif which == "subject":
    with b.ctx.expect_page(timeout=20000) as ev:
        mods.evaluate("subjectSearchPop('_subject_topic188', '_subject_ID182', '_subject_topic', '_subject_authority184', '_subject180', '_subject_topic188')")
    pop = ev.value; pop.wait_for_load_state("domcontentloaded"); pop.wait_for_timeout(3000); b._hook(pop)
    describe(pop, "주제명 찾기"); shot(pop, "subject_search_popup")
    Path("work/captures/wonbu/subject_search_popup.html").write_text(pop.content(), encoding="utf-8")
b.close()
