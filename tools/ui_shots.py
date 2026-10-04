"""개발용: index.html 을 가짜 pywebview.api(Proxy)로 띄워 상태별·너비별로 캡처한다(UI 리뷰·회귀 확인).
실행: python -X utf8 tools/ui_shots.py [--out 폴더] → work/captures/ui_review/ (저장소 기준 상대 경로. 어느 PC 에서나 돈다. playwright + chromium 필요: pip install playwright && playwright install chromium)
work/build/<CNTS>/build.json 이 없으면 작은 가짜 판단으로 대신한다."""
import json, sys, argparse
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
_ap = argparse.ArgumentParser(); _ap.add_argument("--out", default=str(ROOT / "work" / "captures" / "ui_review")); _ns = _ap.parse_args()
html = (ROOT / "kolis_tool" / "ui" / "index.html").resolve().as_uri()
OUT = Path(_ns.out); OUT.mkdir(parents=True, exist_ok=True)
_bp = ROOT / "work" / "build" / "CNTS-00135368140"
build = json.loads((_bp / "build.json").read_text(encoding="utf-8")) if (_bp / "build.json").exists() else {"authors": [{"name": "김성모", "role": "글", "decision": "link", "ac_control_no": "KAC201418251", "confidence": "high", "reason": "시험용"}], "subjects": [{"term": "만화[漫畵]"}, {"term": "웹툰[webtoon]"}], "publisher": {"current": "KOCN"}, "place": {"current": "[서울]"}, "adult": False, "episodes": [], "review": {"done": True}}
job = json.loads((_bp / "job.json").read_text(encoding="utf-8")) if (_bp / "job.json").exists() else {"title": "시험 작품", "authors": []}
work = {"title": "옆집 기러기 아빠 구워 먹기", "output_xlsx": r"C:\Users\User\dataclip\kolis\work\기초메타데이터(26웹툰대행5차-484)_코리스 반입용_옆집기러기아빠구워먹기.xlsx", "rows": 11, "confirm_cells": 68,
        "manuscripts": r"C:\Users\User\Downloads\484_미스터블루_옆집 기러기 아빠 구워먹기\원고", "thumbs": "", "run": {"seconds": 640}, "finalize": {"manuscript_files": 192},
        "confirmed": None, "remaining": [], "columns": 91, "unknown_columns": [], "adult": False, "adult_reason": "",
        "authors": [{"index": 0, "name": "김작가", "role": "글·그림", "ac_control_no": "KAC201418251", "display_form": "", "alt": ["Kim, Jakga"], "staff": False, "sources": [{"from": "전거 KAC201418251", "quote": "만화가, 1970년생, 데뷔작 …"}, {"from": "원문 00000001.jpg", "quote": "글·그림 김작가 (Kim, Jakga)"}]}],
        "summary": [["제목", "옆집 기러기 아빠 구워 먹기", ""], ["저자", "글·그림: 김작가 [전거 KAC201418251]", ""], ["발행처 / 발행지", "미스터블루 / [서울] ulk", ""], ["발행일", "20240409", "미스터블루 등록일"], ["주제명", "만화[漫畵] · 웹툰[webtoon]", ""], ["UCI", "0/11건에 있음", ""]],
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
    "tabs_save": True, "set_author": {"error": "가짜 백엔드"},
    "wb_state": {"state": {"wonbu": "1607", "title": "마음휴가", "acc_count": 25, "kolis_status": ["DS_3300 정리중"], "dup_done": True, "batch_done": True, "species": 25, "contents": 25, "status_at": "2026-10-04 12:00", "has_import": True, "import_rows": 25, "adult": True, "adult_reason": "플랫폼 표기 19세", "compared_at": "2026-10-04 12:05", "diff_count": 2, "use_limit_done": False, "check_nth": 1, "check_errors": 1, "check_checks": 2},
                 "compare": {"mode": "import", "count": 25, "import_rows": 25, "at": "2026-10-04 12:05", "diffs": [{"contents_id": "CNTS-00135368140", "vol": "1", "path": "name[0].@ID", "label": "저자 전거 번호", "import": "KAC201418251", "kolis": "", "kind": "diff"}, {"contents_id": "CNTS-00135368141", "vol": "2", "path": "originInfo[0].dateIssued", "label": "발행일", "import": "20240409", "kolis": "20240410", "kind": "diff"}, {"contents_id": "CNTS-00135368140", "vol": "1", "path": "physicalDescription.internetMediaType", "label": "디지털자료유형", "import": "JPG", "kolis": "image/jpg", "kind": "auto"}]},
                 "fixes": [{"contents_id": "CNTS-00135368140", "path": "name[0].@ID", "xpath": "/mods/name[@ID]", "value": "KAC201418251", "source": "import"}],
                 "contents": [{"contents_id": "CNTS-00135368140", "vol": "1"}, {"contents_id": "CNTS-00135368141", "vol": "2"}],
                 "check": {"nth": 1, "at": "2026-10-04 12:30", "errors": 1, "checks": 2, "file": "work/wonbu/1607/check/1차/점검.xlsx", "confirmed": False, "delivered_name": None, "decisions": {},
                           "findings": [{"row": 0, "col": "/mods/name[@type]", "msg": "'웹툰창고'는 단체명으로 보이는데 personal 입니다.", "level": "check", "by": "agent", "basis": "지침 2"}, {"row": 1, "col": "/mods/originInfo/dateIssued", "msg": "발행일 8자리 아님(가이드 5.3)", "level": "error", "by": "rule"}, {"row": 1, "col": "/mods/name/namePart", "msg": "영문 대문자 연속(필명이면 정상)", "level": "check", "by": "rule"}]}},
    "wb_fix_set": {"fixes": []}, "build_status": {"items": [{"row": 0, "title": "마음휴가", "part": "1", "contents_id": "CNTS-00135368140", "applied_at": "2026-10-03 13:22", "saved_at": None}]},
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
    try:
        b = p.chromium.launch(channel="msedge", headless=True)
    except Exception:  # noqa: BLE001 — 맥북 등 Edge 가 없는 PC
        b = p.chromium.launch(headless=True)
    for W in (1280, 1024):
        pg = b.new_page(viewport={"width": W, "height": 900})
        pg.add_init_script(MOCK); pg.goto(html); pg.wait_for_timeout(1800)
        shot(pg, OUT / f"{W}_01_tabA_top.png")
        pg.evaluate("setOpen('c-1', true, true)"); shot(pg, OUT / f"{W}_02_card1_result.png", "result")
        shot(pg, OUT / f"{W}_03_card2.png", "c-2")
        pg.evaluate("appendLog('■ 반입용 엑셀 만들기 시작', 't1'); appendLog('  [12s] 에이전트 › 검수 맡김: 관찰 924', 't1'); appendLog('  [40s] 하위 › 파일 보기: …/_look/CNTS-00135310924_00000001/00000001_tile001.jpg', 't1'); start(CUR,'prepare'); CUR.started.prepare = Date.now()-200000; setOut(CUR,'run-out','<span class=\"spin\"></span> 원고를 보고 조사해 만드는 중'); phaseState(CUR)")
        shot(pg, OUT / f"{W}_04_card1_running.png", "ph-a")
        pg.evaluate("onDone('prepare', {error:'클로드 실행 실패(코드 1): network error: fetch failed'}, 't1')")
        shot(pg, OUT / f"{W}_05_card1_error.png", "ph-a")
        pg.evaluate("switchTab('t2')"); pg.wait_for_timeout(1200)
        pg.evaluate("setOpen('ph-b', true, true); ['c-b1','c-b2','c-b3','c-b4'].forEach(i=>setOpen(i,true,true))")
        shot(pg, OUT / f"{W}_06_B_status.png", "c-b1")
        shot(pg, OUT / f"{W}_07_B_compare.png", "c-b2")
        shot(pg, OUT / f"{W}_08_B_fix.png", "c-b3")
        pg.evaluate("setOpen('ph-c', true, true); ['c-c1','c-c2'].forEach(i=>setOpen(i,true,true))")
        shot(pg, OUT / f"{W}_09_C_check.png", "c-c1")
        shot(pg, OUT / f"{W}_10_C_confirm.png", "c-c2")
        pg.evaluate("diagnose()"); pg.wait_for_timeout(400)
        shot(pg, OUT / f"{W}_11_diag.png", "ph-a")
        pg.evaluate("dlgClose('dlg-diag'); addTab()"); pg.wait_for_timeout(300)
        shot(pg, OUT / f"{W}_12_new_tab.png")
        pg.evaluate("switchTab('t1'); toggleLog()"); pg.wait_for_timeout(400)
        shot(pg, OUT / f"{W}_13_log_hidden.png")
        pg.evaluate("toggleLog()")
        pg.close()
    b.close()
print("\n".join(str(x) for x in sorted(OUT.iterdir())))
