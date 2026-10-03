"""주제명 묶음 둘: 1번 = 일반주제명 만화 KSH1998022212, 2번 = 장르주제명 웹툰 KSH2016000049. 저장 안 함."""
import sys, json, datetime; sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path
from kolis_tool.kolis_browser import Browser
b = Browser(print)
mods = next(pg for pg in b.ctx.pages if "onContentsDetailPop" in pg.url); b.page = mods
def shot(name):
    f = Path("work/captures/browser") / f"{datetime.datetime.now():%Y%m%d-%H%M%S}_{name}.png"; mods.screenshot(path=str(f)); print("캡처:", f)
LIST = """(()=>{const g=n=>Array.from(document.querySelectorAll('[name="'+n+'"]')).map(e=>({id:e.id,v:e.value}));return {ID:g('_subject@ID'),auth:g('_subject@authority'),topic:g('_subject_topic'),genre:g('_subject_genre'),geo:g('_subject_geographic'),temp:g('_subject_temporal'),title:g('_subject_titleInfo_title')}})()"""
cur = mods.evaluate(LIST); print("전:", json.dumps(cur, ensure_ascii=False))
n = len(cur["ID"]); assert n == 2, f"주제명 묶음 {n}개"
assert len(cur["topic"]) == 2 and len(cur["genre"]) == 2, "주제명 하위 칸 수가 묶음 수와 다름"
mods.evaluate("""(()=>{const g=n=>Array.from(document.querySelectorAll('[name="'+n+'"]'));
 const ID=g('_subject@ID'), AU=g('_subject@authority'), T=g('_subject_topic'), G=g('_subject_genre');
 ID[0].value='KSH1998022212'; T[0].value='만화[漫畵]'; G[0].value='';
 ID[1].value='KSH2016000049'; T[1].value=''; G[1].value='웹툰[webtoon]';
 const setAu=(el,txt)=>{ if(!el) return; if(el.tagName=='SELECT'){ for(const o of el.options){ if(o.text.includes(txt)||o.value.includes(txt)){ el.value=o.value; return; } } } else el.value=txt; };
 setAu(AU[0],'국립중앙도서관주제명표목표'); setAu(AU[1],'국립중앙도서관주제명표목표');
})()""")
b._rec("form", action="주제명 묶음 1 = 만화[漫畵] KSH1998022212 / 묶음 2 = 장르 웹툰[webtoon] KSH2016000049, 전거 둘 다 국립중앙도서관주제명표목표")
after = mods.evaluate(LIST); print("후:", json.dumps(after, ensure_ascii=False))
mods.evaluate("document.querySelector('[name=\"_subject@ID\"]').scrollIntoView({block:'start'})"); mods.wait_for_timeout(400); shot("mods_subject_two_blocks")
b.close()
