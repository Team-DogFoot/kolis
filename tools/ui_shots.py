"""개발용: index.html 을 가짜 pywebview.api(Proxy)로 띄워 상태별·너비별로 캡처한다(UI 리뷰·회귀 확인). 실행: .venv/Scripts/python.exe -X utf8 tools/ui_shots.py → work/captures/ui_review/"""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
html = Path(r"C:\Users\User\dataclip\kolis\kolis_tool\ui\index.html").resolve().as_uri()
OUT = Path(r"C:\Users\User\dataclip\kolis\work\captures\ui_review"); OUT.mkdir(parents=True, exist_ok=True)
build = json.loads(Path(r"C:\Users\User\dataclip\kolis\work\build\CNTS-00135368140\build.json").read_text(encoding="utf-8"))
job = json.loads(Path(r"C:\Users\User\dataclip\kolis\work\build\CNTS-00135368140\job.json").read_text(encoding="utf-8"))
import sys; sys.path.insert(0, r"C:\Users\User\dataclip\kolis")
from kolis_tool.mods_build import summary
summ = summary(build, job); summ.update({"remaining": [], "apply": {"shots": ["work/captures/browser/x.png"]}, "build_path": "work/build/CNTS-00135368140/build.json"})
work = {"title": "옆집 기러기 아빠 구워 먹기", "output_xlsx": r"C:\Users\User\dataclip\kolis\work\기초메타데이터(26웹툰대행5차-484)_코리스 반입용_옆집기러기아빠구워먹기.xlsx", "rows": 11, "confirm_cells": 68,
        "manuscripts": r"C:\Users\User\Downloads\484_미스터블루_옆집 기러기 아빠 구워먹기\원고", "thumbs": "", "run": {"seconds": 640}, "finalize": {"manuscript_files": 192},
        "confirmed": None, "remaining": [], "summary": [["제목", "옆집 기러기 아빠 구워 먹기", ""], ["저자", "글·그림 김작가", ""], ["발행처", "미스터블루", "출판사 엑셀"], ["발행일", "20240409", "미스터블루 등록일"]],
        "confirm": [{"field": "발행일", "rows": [1, 2, 3], "parts": ["1화", "2화", "3화"], "values": ["20240409"], "publisher_says": "E5 '20240410'", "reason": "출판사 엑셀의 발행일(20240410)과 플랫폼 공개일(20240409)이 하루 다릅니다.", "evidence": "https://www.mrblue.com/comic/C000075511 — 등록일 2024.04.09", "ask": "발행일을 플랫폼 공개일(20240409)로 둘까요, 출판사 엑셀 값(20240410)으로 바꿀까요?"}],
        "platforms": [{"name": "미스터블루", "status": "서비스 중", "start_date": "20240409", "url": "https://www.mrblue.com/comic/C000075511"}], "searched": 5, "conflicts": [], "not_found": [], "issues": [], "review": {"done": True, "findings": ["x"], "resolved": ["y"]}}
state = {"register": {"record_no": "2026-1687", "file": r"C:\...\가원부번호 2026-1687(접수번호 991).xlsx", "count": 11, "done_at": "2026-10-01 20:15", "receipt": "991"}, "export": {"file": "x.xls", "receipt": "991", "count": 11, "done_at": "2026-10-01 20:12"}}
MOCK = """
window.__M = %s;
window.pywebview = { api: new Proxy({}, { get: (_, name) => async (...a) => {
  const M = window.__M; const r = M[name]; return typeof r === 'function' ? r(...a) : (r === undefined ? {} : r); } }) };
document.addEventListener('DOMContentLoaded', () => setTimeout(() => window.dispatchEvent(new Event('pywebviewready')), 50));
""" % json.dumps({
    "tabs_load": {"tabs": [{"id": "t1", "title": "옆집 기러기 아빠 구워 먹기", "folder": r"C:\Users\User\Downloads\484_미스터블루_옆집 기러기 아빠 구워먹기", "wonbu": "", "fold": {}},
                           {"id": "t2", "title": "마음휴가", "folder": "", "wonbu": "1607", "manu": "", "fold": {"ph-a": False, "ph-b": True}}], "active": "t1"},
    "flow_steps": [["import", "일괄반입"], ["export", "전체출력"], ["cnts", "폴더명 CNTS"], ["upload", "원문 등록"], ["thumbs", "썸네일"], ["register", "가원부번호"]],
    "kolis_account": {"source": "file", "id": "", "checked": True}, "check_env": {"claude": True, "claude_login": True, "edge": True, "playwright": True},
    "get_prompt": {"text": "", "full": "…", "is_default": True}, "build_settings": {"acquisition_note": "한국웹툰산업협회를 통해 수집한 자료임"},
    "recent": [{"folder": "C:/x/3. 타임머신 대소동", "title": "타임머신 대소동", "when": "", "status": "가원부번호 2026-1685", "exists": True},
               {"folder": "C:/Users/User/Downloads/484_미스터블루_옆집 기러기 아빠 구워먹기", "title": "옆집 기러기 아빠 구워 먹기", "when": "", "status": "가원부번호 2026-1687", "exists": True},
               {"folder": "C:/x/2. 추풍낙엽", "title": "추풍낙엽", "when": "", "status": "반입용 엑셀 있음 · 확인 전", "exists": False}], "output_name": "기초메타데이터(26웹툰대행5차-484)_코리스 반입용_옆집기러기아빠구워먹기.xlsx",
    "flow_ledger": {"rows": [{"작품": "옆집 기러기 아빠 구워 먹기", "처리": "취소 요청", "접수번호": "990", "가원부번호": "", "건수": "11", "결과": "원문 등록에서 멈춤", "반입 시각": "2026-10-01 19:50"}, {"작품": "옆집 기러기 아빠 구워 먹기", "처리": "유지", "접수번호": "991", "가원부번호": "2026-1687", "건수": "11", "결과": "완료", "반입 시각": "2026-10-01 20:12"}], "file": "work/취소요청_목록.csv"},
    "tabs_save": True, "build_status": {"items": [{"row": 0, "title": "마음휴가", "part": "1", "contents_id": "CNTS-00135368140", "applied_at": "2026-10-03 13:22", "saved_at": None}]},
    "status": {"steps": [{"key": "prepare", "label": "반입용 엑셀", "done": True, "evidence": "11행, 사람이 확인할 칸 68개", "when": "2026-10-01 18:30"}, {"key": "manuscript", "label": "원고 파일명(8자리)", "done": True, "evidence": "11/11 폴더", "when": ""}, {"key": "kolis_submit", "label": "KOLIS 반입", "done": True, "evidence": "성공", "when": "2026-10-01 20:12"}, {"key": "export", "label": "전체출력", "done": True, "evidence": "접수번호 991 11건", "when": ""}, {"key": "cnts", "label": "폴더명 CNTS", "done": True, "evidence": "11/11 폴더", "when": ""}, {"key": "upload", "label": "원문일괄등록", "done": True, "evidence": "원문이 등록되었습니다.", "when": ""}, {"key": "register", "label": "가원부번호", "done": True, "evidence": "2026-1687", "when": "2026-10-01 20:15"}], "warnings": [], "memo": ""},
    "open_folder": {"folder": r"C:\Users\User\Downloads\484_미스터블루_옆집 기러기 아빠 구워먹기", "state": state, "work": work, "log": []},
    "load_state": state, "diagnose": {"env": {"claude": True, "claude_login": True, "edge": True, "playwright": True}, "running": {}, "max_agents": 3, "log_path": "C:/x/log.txt", "log_tail": []}, "save_state": state, "log_save": True,
})

def shot(pg, path, anchor=None):
    if anchor:
        pg.evaluate("(id)=>{const el=document.getElementById(id); if(el){ el.scrollIntoView({block:'start'}); }}", anchor)
    else:
        pg.evaluate("document.getElementById('left').scrollTop=0")
    pg.wait_for_timeout(150)
    pg.screenshot(path=str(path), full_page=False)

with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge", headless=True)
    for W in (1280, 1024):
        pg = b.new_page(viewport={"width": W, "height": 900})
        pg.add_init_script(MOCK); pg.goto(html); pg.wait_for_timeout(1800)
        shot(pg, OUT / f"{W}_01_tabA_top.png")
        shot(pg, OUT / f"{W}_02_card1_result.png", "result")
        shot(pg, OUT / f"{W}_03_card2.png", "c-2")
        pg.evaluate("document.getElementById('steps-box').open=true; ['c-21','c-22','c-23','c-24'].forEach(i=>setOpen(i,true))")
        shot(pg, OUT / f"{W}_04_steps_box.png", "steps-box")
        pg.evaluate("document.getElementById('steps-box').open=false")
        pg.evaluate("appendLog('■ 반입용 엑셀 만들기 시작', 't1'); appendLog('  [12s] 에이전트 › 검색: 옆집 기러기 아빠 구워 먹기 미스터블루', 't1'); appendLog('요청 336: POST /online/acq/… (본문 44바이트)', 't1'); appendLog('  [40s] 에이전트 › 페이지 읽기: https://www.mrblue.com/comic/C000075511', 't1'); start(CUR,'prepare'); CUR.started.prepare = Date.now()-200000; setOut(CUR,'run-out','<span class=\"spin\"></span> 에이전트가 작업 중… (오른쪽 로그 참고)'); phaseState(CUR)")
        shot(pg, OUT / f"{W}_05_card1_running.png", "ph-a")
        pg.evaluate("onDone('prepare', {error:'클로드 실행 실패(코드 1): network error: fetch failed'}, 't1')")
        shot(pg, OUT / f"{W}_06_card1_error.png", "ph-a")
        pg.evaluate("switchTab('t2')"); pg.wait_for_timeout(800)
        shot(pg, OUT / f"{W}_07_tabB_top.png")
        pg.evaluate("start(CUR,'build'); CUR.started.build = Date.now()-130000; phaseState(CUR)")
        shot(pg, OUT / f"{W}_08_card32_running.png", "c-32")
        pg.evaluate("onDone('build', %s, 't2')" % json.dumps(summ, ensure_ascii=False))
        pg.wait_for_timeout(300)
        shot(pg, OUT / f"{W}_09_card32_result.png", "b-result")
        pg.evaluate("onDone('prep_dupexmin', {needs_approval:'복본조사KEY설정을 저장해야 합니다(그림 21). YES 를 넣고 다시 실행하세요'}, 't2')")
        shot(pg, OUT / f"{W}_10_card31_wait.png", "c-31")
        pg.evaluate("setOpen('c-33',true)")
        shot(pg, OUT / f"{W}_11_card33.png", "c-33")
        pg.evaluate("diagnose()"); pg.wait_for_timeout(400)
        shot(pg, OUT / f"{W}_12_diag.png", "ph-a")
        pg.evaluate("dlgClose('dlg-diag'); addTab()"); pg.wait_for_timeout(300)
        shot(pg, OUT / f"{W}_13_new_tab.png")
        pg.evaluate("switchTab('t1'); toggleLog()"); pg.wait_for_timeout(400)
        shot(pg, OUT / f"{W}_14_log_hidden.png")
        pg.evaluate("toggleLog()")
        pg.close()
    b.close()
print("\n".join(str(x) for x in sorted(OUT.iterdir())))
