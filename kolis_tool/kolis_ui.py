"""KOLIS 화면 조작 (윈도 UI 자동화, pywinauto/UIA). 3.3 일괄반입 준비까지.

전제: 유저가 Edge 에서 KOLIS 에 로그인해 둔 상태(IE 모드). 이 모듈은 그 창 안의 요소를 **이름으로** 찾아 누른다(좌표 아님).
IE 모드 화면(Internet Explorer_Server)의 버튼·입력칸은 UIA 로 이름이 노출됨을 2026-09-18 확인.

단계(각각 함수): 화면 이동 → '일괄반입' → 확인창 '확인' → 팝업 비고 입력 → 첨부파일 선택 → (멈춤).
'반입' 클릭은 submit() 으로 분리하고, 호출자가 명시적으로 YES 를 넘겨야 한다. 직원 입회·동의가 전제.
"""
from __future__ import annotations
import re, time
from pathlib import Path

RECET_URL = "http://kolis.nl.go.kr/online/acq/bodepst/depstrecet/onlineDepstRecet.do"


def _desktop():
    from pywinauto import Desktop
    return Desktop(backend="uia")


def _wait(fn, timeout: float = 20, step: float = 0.5, what: str = ""):
    t0 = time.time()
    while True:
        try:
            r = fn()
            if r:
                return r
        except Exception:  # noqa: BLE001
            pass
        if time.time() - t0 > timeout:
            raise TimeoutError(f"기다리다 못 찾음: {what}")
        time.sleep(step)


def edge_window(log=print):
    """KOLIS 가 열린 Edge 메인 창(Chrome_WidgetWin_1, IE 모드 콘텐츠 포함)."""
    def find():
        for w in _desktop().windows():
            if w.class_name() == "Chrome_WidgetWin_1" and ("납본" in w.window_text() or "통합자료관리" in w.window_text() or "kolis" in w.window_text().lower()):
                return w
        return None
    w = _wait(find, 10, what="KOLIS 가 열린 Edge 창(로그인 후 KOLIS 탭을 띄워 두세요)")
    log(f"Edge 창: {w.window_text()[:60]}")
    return w


def ie_content(win):
    ies = win.descendants(class_name="Internet Explorer_Server")
    if not ies:
        raise RuntimeError("IE 모드 화면이 아닙니다(Internet Explorer_Server 없음). 이 화면은 IE 모드로 열어야 합니다.")
    return max(ies, key=lambda e: e.rectangle().width() * e.rectangle().height())


def _button(container, name: str):
    """이름의 공백 차이('반      입')를 무시하고 버튼 찾기."""
    key = re.sub(r"\s", "", name)
    for b in container.descendants(control_type="Button"):
        if re.sub(r"\s", "", b.window_text()) == key:
            return b
    return None


def _edit(container, name: str):
    key = re.sub(r"\s|\*", "", name)
    for e in container.descendants(control_type="Edit"):
        if re.sub(r"\s|\*", "", e.window_text()) == key:
            return e
    return None


def _link(container, name: str, pick: str = "first"):
    """이름의 하이퍼링크. pick='right' 면 같은 이름 중 가장 오른쪽(온라인 패널)."""
    key = re.sub(r"\s", "", name)
    els = [e for e in container.descendants(control_type="Hyperlink") if re.sub(r"\s", "", e.window_text()) == key and e.rectangle().width() > 0]
    if not els:
        return None
    return max(els, key=lambda e: e.rectangle().left) if pick == "right" else els[0]


def goto_recet(win, log=print):
    """메뉴를 눌러 납본자료접수 화면으로 이동: 수집 → 납본 → (온라인 › 단행) 납본자료접수.
    주소를 직접 입력하면 로그인이 풀리므로(2026-09-18 확인) 반드시 메뉴 경로로 간다."""
    try:
        if _button(ie_content(win), "일괄반입"):
            log("이미 납본자료접수 화면"); return
    except RuntimeError:
        pass
    win.set_focus(); time.sleep(0.3)
    dismiss_notices(log)
    ie = ie_content(win)
    top = _wait(lambda: _link(ie_content(win), "수집"), 15, what="상단 메뉴 '수집'")
    top.click_input(); log("메뉴 '수집' 클릭")
    sub = _wait(lambda: _link(ie_content(win), "납본"), 15, what="'수집' 하위 '납본'")
    sub.click_input(); log("메뉴 '납본' 클릭")
    # 수집>납본 화면: 왼쪽 오프라인, 오른쪽 온라인 패널에 같은 이름 '납본자료접수' 가 있음 → 오른쪽(온라인)
    def online_recet():
        e = _link(ie_content(win), "납본자료접수", pick="right")
        links = [x for x in ie_content(win).descendants(control_type="Hyperlink") if re.sub(r"\s", "", x.window_text()) == "납본자료접수" and x.rectangle().width() > 0]
        return e if len(links) >= 2 else None
    link = _wait(online_recet, 20, what="온라인 › 단행 › 납본접수 › '납본자료접수' 링크")
    link.click_input(); log("'납본자료접수'(온라인) 클릭")
    _wait(lambda: _button(ie_content(win), "일괄반입"), 40, what="납본자료접수 화면의 '일괄반입' 버튼")
    log("납본자료접수 화면 이동 완료")


def dismiss_notices(log=print) -> int:
    """로그인 직후 뜨는 공지 팝업 닫기. 납본자료접수 팝업은 건드리지 않는다.
    (1) 홈 화면 안의 고정 공지 레이어(Pane id=fixedNotice: 체크박스 '24시간동안 보지 않기' + 버튼 '닫기')
    (2) 별도 창으로 뜨는 IE 모드 공지."""
    n = 0
    try:
        win = edge_window(lambda m: None)
        ie = ie_content(win)
        for pane in ie.descendants(control_type="Pane"):
            if pane.element_info.automation_id == "fixedNotice" and pane.rectangle().width() > 0:
                for cb in pane.descendants(control_type="CheckBox"):
                    if "보지 않기" in cb.window_text():
                        cb.click_input(); time.sleep(0.2); break
                b = _button(pane, "닫기")
                if b:
                    b.click_input(); n += 1; log(f"공지 레이어 닫음(24시간 보지 않기): {pane.window_text().strip()[:40]}")
                    time.sleep(0.5)
    except Exception as e:  # noqa: BLE001
        log(f"공지 레이어 확인 건너뜀: {e}")
    for w in _desktop().windows():
        try:
            c = w.class_name(); t = w.window_text()
        except Exception:  # noqa: BLE001
            continue
        if c == "Chrome_WidgetWin_1" or "납본자료접수" in t:
            continue
        ies = w.descendants(class_name="Internet Explorer_Server") if c != "Chrome_WidgetWin_1" else []
        if not ies:
            continue
        closed = False
        for name in ("닫기", "확인", "close", "Close"):
            b = _button(w, name)
            if b:
                b.click_input(); closed = True; break
        if not closed:
            try:
                w.close()
                closed = True
            except Exception:  # noqa: BLE001
                pass
        if closed:
            n += 1; log(f"공지 팝업 닫음: {t[:40]}")
            time.sleep(0.5)
    return n


def open_batch_import(win, log=print):
    """'일괄반입' → 확인창(신규 접수번호 생성) '확인' → 팝업. 팝업 창 객체를 돌려준다."""
    btn = _button(ie_content(win), "일괄반입")
    if not btn:
        raise RuntimeError("'일괄반입' 버튼이 없습니다")
    btn.click_input()
    log("'일괄반입' 클릭 → 확인창 대기")
    dlg = confirm_dialog()
    txt = " ".join(t.window_text() for t in dlg.descendants(class_name="Static") if t.window_text())
    log(f"확인창: {txt[:80]}")
    if "접수번호" not in txt:
        raise RuntimeError(f"예상과 다른 확인창: {txt[:80]}")
    dlg.child_window(title="확인", class_name="Button").click()
    pop = _wait(lambda: popup_window(), 20, what="일괄반입 팝업")
    log("팝업 열림")
    return pop


def confirm_dialog(timeout: float = 15):
    """IE 모드 confirm() 창: Win32 대화상자(#32770, 제목 '웹 페이지 메시지'). UIA 최상위 목록에는 안 보여 win32 백엔드로 찾는다."""
    from pywinauto import Desktop
    def find():
        d = Desktop(backend="win32").window(title="웹 페이지 메시지", class_name="#32770")
        return d if d.exists() else None
    return _wait(find, timeout, what="'신규 접수번호를 생성하시겠습니까?' 확인창")


def popup_window():
    # IE 모드 팝업(웹 페이지 대화 상자)은 UIA 에서 class 'Alternate Modal Top Most', 제목은 메인 창과 같은 형식으로 노출됨
    for w in _desktop().windows():
        try:
            if w.class_name() == "Alternate Modal Top Most" and "납본자료접수" in w.window_text():
                return w
        except Exception:  # noqa: BLE001
            continue
    return None


def fill_popup(pop, note: str, xlsx: Path, log=print) -> dict:
    """팝업의 비고 입력 + 첨부파일 선택(표준 파일 대화상자). '반입'은 누르지 않는다."""
    import pyperclip  # type: ignore
    ie = ie_content(pop)
    memo = _edit(ie, "비고")
    pyperclip.copy(note); memo.click_input(); memo.type_keys("^a^v")   # IE 입력칸은 한글 type_keys 가 불안정 → 클립보드
    time.sleep(0.3)
    got = memo.get_value() if hasattr(memo, "get_value") else ""
    if re.sub(r"\s", "", got) != re.sub(r"\s", "", note):
        raise RuntimeError(f"비고 입력 확인 실패: '{got}'")
    log(f"비고 입력: {note}")
    browse = _button(ie, "첨부파일") or _button(ie, "찾아보기...")
    browse.click_input()
    select_file_dialog(xlsx, log)
    time.sleep(1.5)
    att = _edit(ie_content(pop), "첨부파일")
    val = ""
    try:
        val = att.get_value()
    except Exception:  # noqa: BLE001
        pass
    log(f"첨부파일 칸: {val[:80] or '(값 읽기 불가)'}")
    fields = {}
    for e in ie_content(pop).descendants(control_type="Edit"):
        try:
            fields[e.window_text()] = e.get_value()
        except Exception:  # noqa: BLE001
            fields[e.window_text()] = "?"
    return {"popup_fields": fields, "attached": bool(val) and xlsx.name in val}


def select_file_dialog(path: Path, log=print, title: str = "업로드할 파일 선택") -> None:
    """윈도 표준 '열기' 대화상자(#32770)에 경로를 넣고 열기. win32 백엔드가 가장 안정적."""
    from pywinauto import Desktop
    import pyperclip  # type: ignore
    def find():
        d = Desktop(backend="win32").window(title=title, class_name="#32770")
        return d if d.exists() else None
    d = _wait(find, 15, what=f"파일 선택 대화상자 '{title}'")
    edit = d.child_window(class_name="Edit", found_index=0)   # 파일 이름(N) 칸
    edit.set_focus()
    pyperclip.copy(str(path))
    edit.type_keys("^a^v")
    time.sleep(0.3)
    edit.type_keys("{ENTER}")
    _wait(lambda: not Desktop(backend="win32").window(title=title, class_name="#32770").exists(), 10, what="대화상자 닫힘")
    log(f"파일 선택: {Path(path).name}")


def submit(pop, yes: str, log=print) -> None:
    """'반입' 클릭. yes 가 정확히 'YES' 일 때만. KOLIS 에 실제 반입되는 동작."""
    if yes != "YES":
        raise RuntimeError("반입은 직원 동의 후 YES 를 넘겨야 합니다")
    b = _button(ie_content(pop), "반입")
    b.click_input(); log("'반입' 클릭함")


def close_popup(pop, log=print) -> None:
    b = _button(ie_content(pop), "닫기")
    if b:
        b.click_input(); log("팝업 닫음")


def prepare_batch_import(note: str, xlsx: Path, log=print) -> dict:
    """전체 준비 시퀀스(반입 전까지)."""
    win = edge_window(log)
    goto_recet(win, log)
    pop = popup_window() or open_batch_import(win, log)
    return fill_popup(pop, note, Path(xlsx), log)
