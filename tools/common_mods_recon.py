"""개발용 조사(열기만, 저장 없음): 디지털콘텐츠관리 → 원부 검색 → 전체 체크 → 「공용사항관리」(#btnCommonMods) 팝업을 열어
화면 HTML·스크립트·입력 칸·요청 기록을 work/captures/pages/5-3_공용사항관리/ 에 남긴다. 저장 단추는 누르지 않는다.
실행: .venv/Scripts/python.exe -X utf8 tools/common_mods_recon.py 1614"""
import sys, json, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from kolis_tool.kolis_browser import Browser
from kolis_tool import mods_build as mb

OUT = Path("work/captures/pages/5-3_공용사항관리"); OUT.mkdir(parents=True, exist_ok=True)

def main(wonbu):
    b = Browser(print); b.login()
    try:
        main, n = mb.open_digitalcont(b, wonbu)
        print("종 수", n)
        main.evaluate("(function(){for(var i=0;i<grid.getRowsCount();i++){$('#jqxgrid').jqxGrid('setcellvalue',i,'_chk',true);}})()")
        # 단추가 부르는 함수 본문
        fn = main.evaluate("(()=>{const h=$._data($('#btnCommonMods')[0],'events'); const f=h&&h.click&&h.click[0]&&h.click[0].handler; return f? f.toString():'(핸들러 없음)';})()")
        (OUT / "button_handler.js").write_text(fn, encoding="utf-8"); print("핸들러:", fn[:600])
        n0 = b.n
        with b.ctx.expect_page(timeout=20000) as ev:
            b.page = main; b.click("#btnCommonMods", changes=False)
        pop = ev.value; pop.wait_for_load_state("domcontentloaded"); pop.wait_for_timeout(3000); b._hook(pop)
        print("팝업:", pop.url)
        (OUT / "popup.html").write_text(pop.content(), encoding="utf-8")
        fields = pop.evaluate("""Array.from(document.querySelectorAll('input,select,textarea,button')).map(e=>({tag:e.tagName,type:e.type,id:e.id,name:e.name,value:(e.value||'').slice(0,60),text:(e.innerText||e.textContent||'').trim().slice(0,40),hidden:e.offsetParent===null}))""")
        (OUT / "fields.json").write_text(json.dumps(fields, ensure_ascii=False, indent=1), encoding="utf-8")
        vis = [f for f in fields if not f["hidden"]]
        print("보이는 칸", len(vis)); [print(" ", f) for f in vis[:80]]
        labels = pop.evaluate("Array.from(document.querySelectorAll('th,label,td')).map(e=>(e.innerText||'').trim()).filter(t=>t&&t.length<30)")
        (OUT / "labels.txt").write_text("\n".join(dict.fromkeys(labels)), encoding="utf-8"); print("라벨:", list(dict.fromkeys(labels))[:80])
        scripts = pop.evaluate("Array.from(document.scripts).filter(s=>!s.src).map(s=>s.textContent).join('\\n\\n')")
        (OUT / "inline_scripts.js").write_text(scripts, encoding="utf-8")
        urls = sorted(set(re.findall(r"https?://kolis\.nl\.go\.kr/[^'\"\s]+\.do[^'\"\s]*", scripts)))
        print("스크립트가 부르는 주소:", urls)
        (OUT / "urls.txt").write_text("\n".join(urls), encoding="utf-8")
        pop.screenshot(path=str(OUT / "popup.png"), full_page=True)
        print("요청 수(팝업 열고 난 뒤)", b.n - n0)
        pop.close()
    finally:
        b.close()

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "1614")
