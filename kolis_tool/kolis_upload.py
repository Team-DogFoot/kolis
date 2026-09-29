"""원문일괄등록(폴더) — 가이드 3.4-나. 팝업 열기 → 폴더 올리기 → 전송 → 일괄정보입력 → 원문등록 → 닫기.

폴더 올리기(2026-09-29 업로더 스크립트 분석): 업로더(DEXT5)는 IE 모드에서 설치형 부품으로 돈다. 폴더를 끌어다 놓으면 업로더 스크립트가
부품의 `AddLocalFileDirectly(경로)` 를 부른다. 그래서 마우스로 끌지 않고 **팝업 화면 안에서 그 함수를 직접 부른다**(add_folders).
부품을 찾지 못해 하나도 부르지 못했을 때만 마우스로 끌어다 놓는다(drop_folders). 전송 시작도 같은 식으로 업로더의 `Transfer` 를 부른다.

전제: 납본자료접수에서 접수번호 찾기 → 전체 선택 → '원문일괄등록(폴더)' 팝업을 열고, CNTS 폴더들을 끌어다 놓아 목록에 올라온 상태.
순서(2026-09-18 실제 1회 수행한 절차 그대로, 단계마다 상태를 읽어 확인하고 어긋나면 멈춘다):
  ① 올라온 폴더 확인(CNTS 폴더만, 개수 = 기대 개수) → ② '전송하기' → 전송 끝(결과표에 폴더 행이 생김)
  → ③ 결과표 전체 선택 → ④ '일괄정보입력'(확인창) → 정보입력결과 채워짐 → ⑤ '원문등록'(확인창) → 알림 "원문이 등록되었습니다"

실측 메모: 전송 2.3GB 33분(1.1~1.2MB/초), 일괄정보입력 ~0.5초/건(완료 알림 없음), 원문등록 ~2초/건.
결과표는 가상 스크롤이라 화면에 보이는 행(약 11행)만 읽힌다 → 전체 검증은 끝난 뒤 '전체출력'의 원문갯수로 한다.
원고 폴더 안에 이미지 외 파일이 있으면 전송이 33% 에서 멈춘다 → 시작 전에 로컬 폴더를 검사한다(check_local).
"""
from __future__ import annotations
import re, time
from collections import Counter
from pathlib import Path
from . import kolis_ui as k, ie_dom
from .common import IMAGE_EXT_ACCEPTED, migrate_legacy

T_UPLOAD_MIN = 120          # 전송 최소 대기 한도(초)
SEC_PER_MB = 1.6            # 전송 한도 계산용(실측 1.1MB/초보다 넉넉히)
INFO_DONE = "정보입력이 되었습니다"
PROGRESS_RE = re.compile(r"\d+\s*/\s*\d+|MB/초|남은 시간|^\d+%")


class Stop(Exception):
    """사람이 봐야 하는 상황. 화면은 그대로 둔다."""


def check_local(root: Path) -> dict:
    """끌어다 놓을 원고 상위 폴더 검사: 하위 폴더가 전부 CNTS-… 이고, 그 안에 이미지 외 파일·하위 폴더가 없어야 한다."""
    root = Path(root)
    migrate_legacy(root)       # 납품 폴더 안의 예전 기록 폴더를 비운다(끌어다 놓을 때 같이 올라가지 않게)
    dirs = [p for p in root.iterdir() if p.is_dir()]
    stray = [p.name for p in root.iterdir() if p.is_file()]
    bad_name = [p.name for p in dirs if not re.fullmatch(r"CNTS-\d+", p.name)]
    junk, files, size = [], 0, 0
    for d in dirs:
        for p in d.iterdir():
            if p.is_dir() or p.suffix.lower() not in IMAGE_EXT_ACCEPTED:
                junk.append(f"{d.name}/{p.name}")
            else:
                files += 1; size += p.stat().st_size
    problems = []
    if stray:
        problems.append(f"원고 상위 폴더에 파일이 있음: {stray[:3]}")
    if bad_name:
        problems.append(f"CNTS 이름이 아닌 폴더: {bad_name[:3]}")
    if junk:
        problems.append(f"이미지가 아닌 항목: {junk[:3]}")
    return {"folders": len(dirs), "files": files, "mb": round(size / 1048576, 1), "names": sorted(p.name for p in dirs), "problems": problems}


def _texts(ie, kind: str) -> list[str]:
    out = []
    for e in ie.descendants(control_type=kind):
        try:
            t = e.window_text().strip()
        except Exception:  # noqa: BLE001
            continue
        if t:
            out.append(t)
    return out


def _dialog_text() -> tuple[object, str]:
    d = k.confirm_dialog_now()
    return (d, " ".join(t.window_text() for t in d.descendants(class_name="Static") if t.window_text())) if d else (None, "")


def _confirm(expect: str, sec: float, log) -> str:
    """기대 문구의 확인창·알림창을 기다려 '확인'. 다른 문구면 누르지 않고 멈춘다."""
    t0 = time.time()
    while time.time() - t0 < sec:
        d, t = _dialog_text()
        if d:
            if expect not in t:
                raise Stop(f"예상과 다른 알림창: '{t[:80]}' (기대 '{expect}')")
            d.child_window(title="확인", class_name="Button").click_input()
            t1 = time.time()
            while time.time() - t1 < 5:
                d2, t2 = _dialog_text()
                if d2 is None or t2 != t:
                    break
                time.sleep(0.15)
            log(f"알림창 확인: {t[:60]}")
            return t
        time.sleep(0.3)
    raise Stop(f"알림창이 뜨지 않음(기대 '{expect}')")


def _focus(pop):
    try:
        k.edge_window(lambda m: None).set_focus(); time.sleep(0.15)
    except Exception:  # noqa: BLE001
        pass
    pop.set_focus(); time.sleep(0.3)


def open_popup(receipt: str, log=None):
    """어느 화면에서든: 납본자료접수 이동 → 접수번호 찾기 → 목록 전체 선택(픽셀로 확인) → '원문일괄등록(폴더)' → 팝업. 이미 열려 있으면 그대로 쓴다."""
    from pywinauto import mouse
    from .kolis_thumbs import checked
    from . import ie_dom
    log = k._aslog(log)
    ie_dom.recorder(log)
    pop = k.upload_popup_window()
    if pop:
        log("원문일괄등록 팝업이 이미 열려 있음")
        return pop
    k.cleanup_stray_dialogs(log)
    k.close_leftover_popup(log)
    win = k.edge_window(log)
    k.goto_recet(win, log)
    k.search_receipt(win, receipt, log)
    k.ensure_visible(win, k._button(k.ie_content(win), "원문일괄등록(폴더)"), log)
    hdr = [c for c in k.ie_content(win).descendants(control_type="CheckBox") if c.rectangle().width() > 0]
    if not hdr:
        raise Stop("목록 헤더 체크박스를 찾지 못함")
    cb = min(hdr, key=lambda c: (c.rectangle().top, c.rectangle().left))   # 목록 맨 위·왼쪽 = 전체 선택
    r = cb.rectangle(); cx, cy = (r.left + r.right) // 2, (r.top + r.bottom) // 2
    win.set_focus(); time.sleep(0.3)
    for _ in range(3):
        if checked(cx, cy):
            break
        mouse.click(coords=(cx, cy)); time.sleep(0.6)
    if not checked(cx, cy):
        raise Stop("전체 선택 체크가 되지 않음")
    log("목록 전체 선택")
    pop = k._act(log, "'원문일괄등록(폴더)' 클릭 → 팝업", lambda: k._button(k.ie_content(win), "원문일괄등록(폴더)").click_input(),
                 lambda: k.upload_popup_window() or (_dialog_text()[0] and "알림"), k.T_PAGE)
    if pop == "알림":
        raise Stop(f"'원문일괄등록(폴더)' 클릭 후 알림창: '{_dialog_text()[1][:80]}'")
    ie_dom.tick("원문일괄등록 팝업 열림")
    log("원문일괄등록 팝업 열림")
    return pop


def _dialog_frame():
    """원문일괄등록 팝업의 실제 창(웹 페이지 대화 상자). 놓을 자리에 이 창이 있는지 확인하는 데 쓴다."""
    from pywinauto import Desktop
    ws = [w for w in Desktop(backend="win32").windows() if w.class_name() == "Internet Explorer_TridentDlgFrame"]
    return ws[0] if ws else None


def drop_folders(root: Path, log=None) -> dict:
    """원고 폴더(CNTS-…)들을 탐색기에서 팝업으로 끌어다 놓는다(2026-09-29: 사람이 하던 일을 마우스 조작으로).
    놓기 전에 확인한다: 탐색기에 CNTS 폴더만 있는가, 전부 선택됐는가, 집을 자리와 놓을 자리에 다른 창이 끼어 있지 않은가.
    하나라도 어긋나면 놓지 않고 멈춘다(다른 창에 떨어뜨리면 그 프로그램에 경로가 입력된다)."""
    import ctypes, subprocess
    from ctypes import wintypes
    from pywinauto import Desktop, mouse, keyboard
    log = k._aslog(log)
    root = Path(root)
    local = check_local(root)
    if local["problems"]:
        raise Stop("원고 폴더 문제: " + "; ".join(local["problems"]))
    dlg = _dialog_frame()
    if not dlg or not k.upload_popup_window():
        raise Stop("원문일괄등록 팝업이 없습니다")
    user32 = ctypes.windll.user32
    def top_of(x, y):
        return user32.GetAncestor(user32.WindowFromPoint(wintypes.POINT(x, y)), 2)
    def explorer():
        ws = [w for w in Desktop(backend="uia").windows() if w.class_name() == "CabinetWClass" and root.name in w.window_text()]
        return ws[0] if ws else None
    ex = explorer()
    if not ex:
        subprocess.Popen(["explorer.exe", str(root)])
        t0 = time.time()
        while time.time() - t0 < 15 and not explorer():
            time.sleep(0.5)
        ex = explorer()
        if not ex:
            raise Stop("탐색기 창을 열지 못했습니다")
        time.sleep(1.5)
    # 팝업의 놓을 자리(왼쪽 위 파일 목록 영역)와 겹치지 않게 탐색기를 팝업의 오른쪽 아래에 둔다
    d = dlg.rectangle()
    user32.MoveWindow(ex.handle, d.left + 1060, d.top + 400, 575, 440, True); time.sleep(1.2)
    tx, ty = d.left + 320, d.top + 230
    try:
        ex.set_focus(); time.sleep(0.6)
        items = [e for e in ex.descendants(control_type="ListItem")]
        names = sorted(e.window_text() for e in items)
        if names != local["names"]:
            raise Stop(f"탐색기에 보이는 항목이 원고 폴더와 다릅니다: {names[:5]}")
        r0 = items[0].rectangle()
        sx, sy = r0.left + 40, (r0.top + r0.bottom) // 2
        mouse.click(coords=(sx, sy)); time.sleep(0.4)
        keyboard.send_keys("^a"); time.sleep(0.6)
        if not all(e.is_selected() for e in items):
            raise Stop("탐색기에서 폴더를 전부 선택하지 못했습니다")
        if top_of(sx, sy) != ex.handle or top_of(tx, ty) != dlg.handle:
            raise Stop("집을 자리나 놓을 자리를 다른 창이 가리고 있어 끌어다 놓지 않았습니다. 팝업을 가리는 창을 치운 뒤 다시 실행하세요")
        mouse.press(coords=(sx, sy)); time.sleep(0.4)
        for i in range(1, 41):
            mouse.move(coords=(int(sx + (tx - sx) * i / 40), int(sy + (ty - sy) * i / 40))); time.sleep(0.03)
        time.sleep(0.8)
        mouse.move(coords=(tx + 3, ty + 3)); time.sleep(0.6)
        if top_of(tx + 3, ty + 3) != dlg.handle:
            keyboard.send_keys("{ESC}"); mouse.release(coords=(sx, sy))
            raise Stop("놓기 직전에 다른 창이 끼어들어 취소했습니다")
        mouse.release(coords=(tx + 3, ty + 3))
        n = local["folders"]
        t0 = time.time()
        while time.time() - t0 < 120:        # 파일이 많으면 목록에 올라오는 데 시간이 걸린다
            st = state()
            if any(re.search(rf"(?<!\d){n}\s*항목", s_) for s_ in st["summary"]):
                break
            time.sleep(1)
        else:
            raise Stop(f"끌어다 놓았지만 팝업에 {n}개 항목으로 올라오지 않았습니다(표시 {state()['summary']})")
        log(f"폴더 {n}개를 팝업에 끌어다 놓음")
        return {"folders": n}
    finally:
        try:
            ex.close()
        except Exception:  # noqa: BLE001
            pass


UPLOADER = "dext5upload"          # 팝업 스크립트의 new Dext5Upload("dext5upload")
ADD_JS = r"""
(function(paths){
  var out = {ok: false, called: 0, mode: '', before: null, after: null, error: ''};
  try {
    out.mode = '' + DEXT5UPLOAD.GetUserRuntimeMode('%(id)s');
    var f = document.getElementById('dext5uploader_frame_%(id)s');
    if (!f) throw new Error('업로더 프레임이 없음');
    var pl = f.contentWindow.Dext5PL;
    if (!pl) throw new Error('업로더 부품(Dext5PL)이 없음');
    try { out.before = pl.GetFileCount(); } catch (e1) {}
    pl.nNotAllowIfOpen = '0';
    for (var i = 0; i < paths.length; i++) { pl.AddLocalFileDirectly(paths[i]); out.called++; }
    try { out.after = pl.GetFileCount(); } catch (e2) {}
    out.ok = true;
  } catch (e) { out.error = '' + (e.message || e); }
  document.documentElement.setAttribute('data-kolis-add', JSON.stringify(out));
})(%(paths)s);
"""
START_JS = r"""
(function(){
  var out = {ok: false, error: ''};
  try {
    if (typeof DEXT5UPLOAD === 'undefined' || !DEXT5UPLOAD.Transfer) throw new Error('업로더가 없음');
    window.setTimeout(function(){ DEXT5UPLOAD.Transfer('%(id)s'); }, 50);      // 전송 창이 뜨는 동안 이 호출이 붙잡히지 않게 나중에 실행
    out.ok = true;
  } catch (e) { out.error = '' + (e.message || e); }
  document.documentElement.setAttribute('data-kolis-start', JSON.stringify(out));
})();
"""


def _popup_doc():
    """원문일괄등록 팝업의 문서."""
    for _title, _cls, top in ie_dom._documents():
        try:
            if "contentsTextRegPop.do" in str(top.URL):
                return top
        except Exception:  # noqa: BLE001
            continue
    return None


def _script(js: str, attr: str, wait: float) -> dict:
    """팝업 화면 안에서 스크립트를 실행하고 결과를 읽는다. wait 초 안에 돌아오지 않으면 Stop."""
    import json, threading
    box: dict = {}
    def work():
        try:
            doc = _popup_doc()
            if doc is None:
                box["error"] = "팝업 문서를 찾지 못함"; return
            doc.documentElement.setAttribute(attr, "")
            doc.parentWindow.execScript(js, "JavaScript")
            box["raw"] = str(doc.documentElement.getAttribute(attr) or "")
        except Exception as e:  # noqa: BLE001
            box["error"] = f"{type(e).__name__}: {str(e)[:160]}"
    th = threading.Thread(target=work, daemon=True, name="kolis-upload-script")
    th.start(); th.join(wait)
    if th.is_alive():
        raise Stop(f"팝업 화면이 {int(wait)}초 동안 응답하지 않습니다. 화면을 확인하세요")
    if box.get("error"):
        return {"ok": False, "called": 0, "error": box["error"]}
    try:
        return json.loads(box.get("raw") or "{}") or {"ok": False, "called": 0, "error": "결과 없음"}
    except json.JSONDecodeError:
        return {"ok": False, "called": 0, "error": f"결과를 읽지 못함: {box.get('raw', '')[:80]}"}


def add_folders(root: Path, log=None) -> dict:
    """원고 폴더(CNTS-…)를 팝업의 업로더에 올린다(마우스를 쓰지 않음). 올라온 수는 팝업의 표시("N 항목")로 확인한다.
    돌려주는 값의 called 가 0 이면 아무것도 올리지 못한 것이다(이때만 끌어다 놓기로 바꿔도 된다)."""
    import json
    log = k._aslog(log)
    local = check_local(Path(root))
    if local["problems"]:
        raise Stop("원고 폴더 문제: " + "; ".join(local["problems"]))
    paths = [str((Path(root) / name).resolve()) for name in local["names"]]
    n = local["folders"]
    ie_dom.tick("폴더 올리기 (전)")
    r = _script(ADD_JS % {"id": UPLOADER, "paths": json.dumps(paths)}, "data-kolis-add", max(120, local["files"] * 0.5))
    log(f"폴더 올리기(스크립트): 업로더 방식 {r.get('mode')!r}, 부른 횟수 {r.get('called')}/{n}, 파일 수 {r.get('before')} → {r.get('after')}"
        + (f", 오류 {r.get('error')}" if r.get("error") else ""))
    if not r.get("called"):
        return {**r, "folders": 0}
    if r.get("called") != n or not r.get("ok"):
        raise Stop(f"폴더 {n}개 중 {r.get('called')}개만 올렸습니다({r.get('error')}). 팝업의 목록을 비운 뒤 다시 실행하세요")
    t0 = time.time()
    while time.time() - t0 < 120:
        st = state()
        if any(re.search(rf"(?<!\d){n}\s*항목", s_) for s_ in st["summary"]):
            break
        time.sleep(1)
    else:
        raise Stop(f"폴더를 올렸지만 팝업에 {n}개 항목으로 표시되지 않습니다(표시 {state()['summary']}). 팝업을 확인하세요")
    ie_dom.tick("폴더 올리기 (후)")
    log(f"폴더 {n}개를 팝업에 올림({int(time.time() - t0)}초 뒤 표시 확인)")
    return {**r, "folders": n}


def start_transfer(log=None) -> bool:
    """업로더의 전송을 시작한다(화면의 '전송하기' 버튼과 같은 함수). 시작하지 못하면 False."""
    log = k._aslog(log)
    r = _script(START_JS % {"id": UPLOADER}, "data-kolis-start", 20)
    log("전송 시작(스크립트)" + ("" if r.get("ok") else f" 실패: {r.get('error')}"))
    return bool(r.get("ok"))


def _close(pop, log) -> None:
    """팝업을 닫고 닫혔는지 확인한다. 떠 있으면 뒤의 본화면을 쓸 수 없다."""
    def do():
        _focus(pop)
        [b for b in k.ie_content(pop).descendants(control_type="Button") if k._norm(b.window_text()) == "닫기"][-1].click_input()
    k._act(log, "원문일괄등록 팝업 '닫기'", do, lambda: not _dialog_frame(), k.T_DIALOG)
    log("원문일괄등록 팝업 닫음")


def state(pop=None) -> dict:
    """팝업을 읽기만 한다(클릭 없음): 버튼, 체크박스, 올라온 폴더, 결과표 값 분포, 진행 글자, 열린 알림창."""
    pop = pop or k.upload_popup_window()
    if not pop:
        return {"open": False}
    ie = k.ie_content(pop)
    items = _texts(ie, "DataItem")
    texts = _texts(ie, "Text")
    cnts = [t for t in items + texts if re.fullmatch(r"CNTS-\d+", t)]
    results = Counter(t for t in items if t in ("정보입력", "원문등록") or "실패" in t or "오류" in t)
    checks = []
    for c in ie.descendants(control_type="CheckBox"):
        r = c.rectangle()
        try:
            on = bool(c.get_toggle_state())
        except Exception:  # noqa: BLE001
            on = None
        checks.append({"name": c.window_text(), "left": r.left, "top": r.top, "on": on})
    rows = list(dict.fromkeys(t for t in items if re.fullmatch(r"CNTS-\d+", t)))      # 결과표(전송이 끝나야 생기는 표)에 올라온 폴더
    return {"open": True, "buttons": _texts(ie, "Button"), "checkboxes": checks, "cnts": list(dict.fromkeys(cnts)), "cnts_cells": len(cnts), "rows": rows,
            "results": dict(results), "summary": [t for t in texts if "항목" in t or "추가됨" in t][:3],
            "progress": [t for t in texts if PROGRESS_RE.search(t)][:6], "dialog": _dialog_text()[1]}


def run(root: Path, log=None, handle: dict | None = None, yes: str = "", receipt: str = "") -> dict:
    """팝업 열기 → 폴더 끌어다 놓기 → 전송 → 일괄정보입력 → 원문등록. yes 가 'YES' 일 때만(직원 동의). handle['cancel'] 로 단계 사이에서 중단.
    이미 된 단계는 건너뛴다(팝업이 열려 있으면 그대로, 폴더가 올라와 있으면 놓지 않고, 전송이 끝났으면 전송하지 않는다)."""
    log = k._aslog(log)
    handle = handle or {}
    if yes != "YES":
        raise Stop("원문일괄등록은 직원 동의 후 YES 를 넘겨야 합니다")
    local = check_local(Path(root))
    if local["problems"]:
        raise Stop("원고 폴더 문제: " + "; ".join(local["problems"]))
    n = local["folders"]
    log(f"=== 원문일괄등록 시작: 폴더 {n}개, 파일 {local['files']}개, {local['mb']} MB")
    ie_dom.recorder(log)
    pop = k.upload_popup_window()
    if not pop:
        if not receipt:
            raise Stop("원문일괄등록(폴더) 팝업이 없습니다. 접수번호를 넣으면 프로그램이 팝업을 엽니다")
        pop = open_popup(receipt, log)
    d, t = _dialog_text()
    if d and INFO_DONE in t:          # 앞 실행이 일괄정보입력 완료 알림에서 멈춘 경우: 확인하고 이어 간다
        _confirm(INFO_DONE, 5, log)
    elif d:
        raise Stop(f"알림창이 열려 있습니다: '{t[:80]}'")
    st = state(pop)
    log(f"팝업 상태(시작): 표시 {st['summary']}, 결과표 {len(st['rows'])}행, 결과 {st['results']}, 버튼 {st['buttons']}")
    how = "이미 올라와 있음"
    if not st["rows"] and not any(re.search(r"(?<!\d)[1-9]\d*\s*항목", s_) for s_ in st["summary"]):
        how = "스크립트"
        if not add_folders(Path(root), log).get("folders"):
            log("스크립트로 올리지 못함 → 마우스로 끌어다 놓기로 바꿉니다")
            how = "끌어다 놓기"
            drop_folders(Path(root), log)
        st = state(pop)
    log(f"팝업 상태(폴더 올린 뒤, 방법: {how}): 표시 {st['summary']}, 올라온 폴더 {st['cnts']}")
    unknown = [c for c in st["cnts"] if c not in local["names"]]
    if unknown:
        raise Stop(f"팝업에 이 작품 것이 아닌 폴더가 있습니다: {unknown[:3]}")

    def cancelled():
        if handle.get("cancel"):
            raise Stop("사용자가 중단함")

    ie = lambda: k.ie_content(pop)   # noqa: E731
    done = st["results"]
    shown = min(n, 11)          # 결과표는 가상 스크롤이라 화면에 보이는 행(약 11행)만 읽힌다
    # ② 전송. 끝났는지는 결과표에 폴더 행이 생겼는지로 판정한다(2026-09-29: 안내 글자 '추가됨'은 항상 있어 판정에 못 씀)
    if len(st["rows"]) >= shown:
        log(f"이미 전송된 상태(결과표에 폴더 {len(st['rows'])}행) — 전송 건너뜀")
    else:
        if not any(re.search(rf"(?<!\d){n}\s*항목", s_) for s_ in st["summary"]):
            raise Stop(f"팝업에 올라온 항목 수를 확인하지 못했습니다(기대 {n}개, 표시 {st['summary']}). 끌어다 놓기가 끝났는지 확인하세요")
        limit = max(T_UPLOAD_MIN, local["mb"] * SEC_PER_MB + 120)
        ie_dom.tick("전송하기 (전)")
        if not start_transfer(log):
            _focus(pop)
            k._button(ie(), "전송하기").click_input()
            log("'전송하기' 버튼 클릭")
        log(f"전송 대기(한도 {int(limit)}초)")
        t0, last = time.time(), ""
        while True:
            cancelled()
            s = state(pop)
            if s["dialog"]:
                raise Stop(f"전송 중 알림창: '{s['dialog'][:80]}'")
            if len(s["rows"]) >= shown:
                break
            if s["progress"]:
                line = " | ".join(s["progress"])[:120]
                if line != last:
                    log(f"  전송 중 {int(time.time() - t0)}초: {line}"); last = line
            if time.time() - t0 > limit:
                raise Stop(f"전송이 {int(limit)}초 안에 끝나지 않았습니다(결과표에 폴더 {len(s['rows'])}행). 화면을 확인하세요")
            time.sleep(2)
        ie_dom.tick("전송 끝")
        log(f"전송 끝 ({int(time.time() - t0)}초). 결과표에 폴더 {len(s['rows'])}행")
    cancelled()
    # ③ 결과표 전체 선택: 표 머리글의 체크박스(UIA CheckBox). 여러 개면 가장 아래쪽(결과표) 것
    if done.get("정보입력", 0) == 0:
        boxes = [c for c in ie().descendants(control_type="CheckBox") if c.rectangle().width() > 0]
        if not boxes:
            raise Stop("결과표 전체 선택 체크박스를 찾지 못했습니다. 직접 체크한 뒤 다시 실행하세요")
        box = max(boxes, key=lambda c: c.rectangle().top)
        _focus(pop)
        for _ in range(3):
            try:
                if box.get_toggle_state():
                    break
            except Exception:  # noqa: BLE001
                pass
            box.click_input(); time.sleep(0.6)
        else:
            raise Stop("결과표 전체 선택이 체크되지 않았습니다")
        log("결과표 전체 선택 확인")
        # ④ 일괄정보입력
        _focus(pop)
        ie_dom.tick("일괄정보입력 (전)")
        k._button(ie(), "일괄정보입력").click_input()
        _confirm("정보입력을 하시겠습니까", 15, log)
        t0 = time.time(); limit = n * 3 + 60
        while True:
            cancelled()
            d, t = _dialog_text()
            if d and INFO_DONE in t:      # 끝나면 알림 "정보입력이 되었습니다."가 뜬다(2026-09-29 실측)
                _confirm(INFO_DONE, 5, log)
                s = state(pop)
                if s["results"].get("정보입력", 0) < shown:
                    raise Stop(f"완료 알림은 떴지만 정보입력결과가 채워지지 않았습니다(보이는 행 {s['results']})")
                break
            if d:
                raise Stop(f"정보입력 중 알림창: '{t[:80]}'")
            s = state(pop)
            if s["results"].get("정보입력", 0) >= shown and time.time() - t0 >= n * 0.7:
                break
            if time.time() - t0 > limit:
                raise Stop(f"정보입력결과가 {limit}초 안에 채워지지 않았습니다(보이는 행 {s['results']})")
            time.sleep(2)
        ie_dom.tick("일괄정보입력 끝")
        log(f"일괄정보입력 끝 ({int(time.time() - t0)}초, 보이는 행 {s['results']})")
    cancelled()
    # ⑤ 원문등록
    _focus(pop)
    ie_dom.tick("원문등록 (전)")
    k._button(ie(), "원문등록").click_input()
    _confirm("원문등록하시겠습니까", 15, log)
    msg = _confirm("원문이 등록되었습니다", n * 6 + 120, log)
    ie_dom.tick("원문등록 끝")
    s_last = state(pop)["results"]
    if s_last.get("원문등록", 0) < shown:
        raise Stop(f"완료 알림은 떴지만 원문등록결과가 채워지지 않았습니다(보이는 행 {s_last}). 팝업을 닫지 않았습니다 → 화면 확인")
    _close(pop, log)
    s = {"results": s_last}
    log(f"=== 원문일괄등록 완료: {msg} (보이는 행 {s['results']})")
    return {"folders": n, "files": local["files"], "mb": local["mb"], "message": msg, "visible": s["results"]}
