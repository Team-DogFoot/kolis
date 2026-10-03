"""③구간 반자동 한 단계를 유저 Edge 창에서 '버튼 직전까지' 진행한다(개발 중 수동 실행용. 뒤에 프로그램 창으로 옮긴다).
쓰는 법: python tools/build_step.py dupexmin-open <원부번호>   → 5.1 일괄복본조사 화면, 등록구분 FTX·원부번호 입력까지. 누르지 않음.
        python tools/build_step.py keyset-open                 → 복본조사KEY설정 팝업을 열어 현재 값을 읽는다.
"""
import sys, json, time
sys.stdout.reconfigure(encoding="utf-8")
from kolis_tool.kolis_browser import Browser

cmd = sys.argv[1]; args = sys.argv[2:]
b = Browser(print)
b.login()
if cmd == "dupexmin-open":
    no = args[0]
    b.open("/online/cata/bocata/digitalcont/dupexmin/bundledupexmin/onlineBundleDupExmin.do", wait=3)
    b.select("#reg_code", "FTX")
    b.fill("#accession_rec_no_start", no)
    vals = b.eval("({yr: $('#acquisit_yr').val(), reg: $('#reg_code').val(), no: $('#accession_rec_no_start').val()})")
    print("화면 값:", vals)
    print("캡처:", b.shot(f"dupexmin_{no}_before"))
    print("멈춤: '복본조사' 버튼은 누르지 않았습니다. 기록:", b.rec_path)
elif cmd == "keyset-open":
    b.open("/cmmn/dupexminkeyset/main.do?type=A&screen_code=F1131110", wait=2)   # 일괄복본조사 화면의 버튼이 여는 주소 그대로
    print("저장된 설정:", b.eval("(function(){try{return JSON.stringify(rtn)}catch(e){return 'rtn 없음'}})()"))
    allv = b.eval("Array.from(document.querySelectorAll('input[type=checkbox],input[type=radio]')).filter(e=>e.offsetParent!==null).map(e=>(e.checked?'[v] ':'[ ] ')+((e.closest('label')||e.parentElement).innerText||'').trim().split(/\\s*\\n/)[0]+' <'+e.name+'='+e.value+(e.disabled?' 고정':'')+'>')")
    print("선택지(보이는 것):"); [print("  ", x) for x in allv]
    print("캡처:", b.shot("keyset"))

def menu_dupexmin(b):
    """가이드 순서대로 메뉴를 눌러 일괄복본조사 화면으로: 정리 → 디지털콘텐츠 → (온라인 › 단행 › 복본조사) 일괄복본조사."""
    p = b.page
    p.goto("http://kolis.nl.go.kr/main/gohome.do", wait_until="domcontentloaded"); time.sleep(1.5)
    b._rec("menu", step="정리"); p.get_by_role("link", name="정리", exact=True).first.click(); time.sleep(1.5)
    print("캡처:", b.shot("menu_정리"))
    b._rec("menu", step="디지털콘텐츠"); p.get_by_text("디지털콘텐츠", exact=True).first.click(); time.sleep(1.5)
    print("캡처:", b.shot("menu_디지털콘텐츠"))
    b._rec("menu", step="일괄복본조사"); p.get_by_text("일괄복본조사", exact=True).first.click()
    p.wait_for_selector("#reg_code", timeout=30000); time.sleep(2)
    print("화면 제목:", p.title(), "| 주소:", p.url)

if cmd == "menu-dupexmin":
    no = args[0]
    menu_dupexmin(b)
    b.select("#reg_code", "FTX"); b.fill("#accession_rec_no_start", no)
    print("화면 값:", b.eval("({yr: $('#acquisit_yr').val(), reg: $('#reg_code').val(), no: $('#accession_rec_no_start').val()})"))
    print("캡처:", b.shot(f"dupexmin_{no}_menu"))
    print("멈춤: 버튼은 누르지 않음. 기록:", b.rec_path)
b.close()
