"""KOLIS 화면 조작 (윈도 UI 자동화, pywinauto/UIA). 3.3 일괄반입 준비까지.

전제: 유저가 Edge 에서 KOLIS 에 로그인해 둔 상태(IE 모드). 이 모듈은 그 창 안의 요소를 **이름으로** 찾아 누른다(좌표 아님).
IE 모드 화면(Internet Explorer_Server)의 버튼·입력칸은 UIA 로 이름이 노출됨을 2026-09-18 확인.

단계(각각 함수): 화면 이동 → '일괄반입' → 확인창 '확인' → 팝업 비고 입력 → 첨부파일 선택 → (멈춤).
'반입' 클릭은 submit() 으로 분리하고, 호출자가 명시적으로 YES 를 넘겨야 한다. 직원 입회·동의가 전제.

신뢰성 규칙(2026-09-18 유저 요청):
  - 모든 클릭은 "누른다 → 기대 결과 확인 → 안 되면 재시도(RETRIES)" 로 통일(_act).
  - 파일 대화상자는 파일 이름 칸에 직접 값을 쓰고 읽어서 확인한 뒤 '열기' 버튼, 닫힘까지 확인. 실패 시 '취소'로 원상복구 후 재시도.
  - 시작 전에 남아 있는 파일 대화상자·확인창을 정리(cleanup_stray_dialogs).
  - 단계마다 파일 로그(work/logs/kolis-YYYYMMDD.log). 실패 시 화면 캡처 + 열린 창 목록 저장(capture_failure).
"""
from __future__ import annotations
import datetime, re, time, traceback
from pathlib import Path

RECET_URL = "http://kolis.nl.go.kr/online/acq/bodepst/depstrecet/onlineDepstRecet.do"
LOG_DIR = Path("work") / "logs"

# 조정 가능한 상수
RETRIES = 3            # 클릭 재시도 횟수
T_FIND = 15            # 요소·창 찾기 대기(초)
T_PAGE = 40            # 화면 전환 대기(초)
T_DIALOG = 12          # 대화상자 뜸/닫힘 대기(초)
STEP = 0.4             # 폴링 간격(초)
FILE_DIALOG_TITLE = "업로드할 파일 선택"


# ---------- 로그 ----------
class Log:
    """화면 로그(콜백) + 파일 로그. log(msg) 처럼 호출."""
    def __init__(self, ui=None):
        self.ui = ui or (lambda m: None)
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.path = LOG_DIR / f"kolis-{datetime.date.today():%Y%m%d}.log"

    def __call__(self, msg: str, level: str = "INFO"):
        line = f"{datetime.datetime.now():%H:%M:%S} {level:5} {msg}"
        try:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:  # noqa: BLE001
            pass
        self.ui(msg if level == "INFO" else f"[{level}] {msg}")

    def warn(self, msg): self(msg, "WARN")
    def error(self, msg): self(msg, "ERROR")


def _aslog(log) -> Log:
    return log if isinstance(log, Log) else Log(log if callable(log) else None)


# ---------- 기본 도구 ----------
def _desktop():
    from pywinauto import Desktop
    return Desktop(backend="uia")


def _win32():
    from pywinauto import Desktop
    return Desktop(backend="win32")


def _wait(fn, timeout: float = T_FIND, step: float = STEP, what: str = ""):
    t0 = time.time()
    last = None
    while True:
        try:
            r = fn()
            if r:
                return r
        except Exception as e:  # noqa: BLE001
            last = e
        if time.time() - t0 > timeout:
            raise TimeoutError(f"기다리다 못 찾음: {what}" + (f" (마지막 예외: {type(last).__name__}: {str(last)[:80]})" if last else ""))
        time.sleep(step)


def _act(log: Log, what: str, do, check, timeout: float = T_FIND, retries: int = RETRIES, recover=None):
    """do() 실행 → check() 가 참이 될 때까지 timeout 대기 → 실패하면 recover() 후 재시도. 마지막까지 실패하면 예외."""
    for i in range(1, retries + 1):
        try:
            do()
        except Exception as e:  # noqa: BLE001
            log.warn(f"{what}: 실행 예외({type(e).__name__}: {str(e)[:80]}) — {i}/{retries}")
        try:
            r = _wait(check, timeout, what=what)
            if i > 1:
                log(f"{what}: {i}번째 시도에 성공")
            return r
        except TimeoutError as e:
            log.warn(f"{what}: 확인 실패 — {i}/{retries} ({str(e)[:120]})")
            if recover:
                try:
                    recover()
                except Exception as re_:  # noqa: BLE001
                    log.warn(f"{what}: 복구 중 예외 {type(re_).__name__}")
            time.sleep(0.8)
    raise RuntimeError(f"{what}: {retries}번 시도했지만 실패")


def capture_failure(log: Log, what: str) -> dict:
    """실패 시점의 화면 캡처와 열린 창 목록을 work/logs 에 남긴다."""
    stamp = f"{datetime.datetime.now():%Y%m%d-%H%M%S}"
    out = {"shot": "", "windows": ""}
    try:
        from PIL import ImageGrab
        p = LOG_DIR / f"fail-{stamp}.png"
        ImageGrab.grab(all_screens=True).save(p); out["shot"] = str(p)
    except Exception as e:  # noqa: BLE001
        log.warn(f"화면 캡처 실패: {e}")
    try:
        lines = []
        for be, d in (("uia", _desktop()), ("win32", _win32())):
            for w in d.windows():
                try:
                    t = w.window_text(); c = w.class_name()
                    if t.strip() or c in ("#32770", "Alternate Modal Top Most"):
                        lines.append(f"[{be}] pid={w.process_id()} class={c} title={t[:80]!r}")
                except Exception:  # noqa: BLE001
                    pass
        p = LOG_DIR / f"fail-{stamp}-windows.txt"
        p.write_text(f"{what}\n" + "\n".join(dict.fromkeys(lines)), encoding="utf-8"); out["windows"] = str(p)
    except Exception as e:  # noqa: BLE001
        log.warn(f"창 목록 저장 실패: {e}")
    log.error(f"{what} — 캡처 {out['shot'] or '없음'}, 창 목록 {out['windows'] or '없음'}")
    return out


# ---------- 창·요소 찾기 ----------
def edge_window(log=None):
    log = _aslog(log)
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


def _norm(s: str) -> str:
    return re.sub(r"\s|\*", "", s or "")


def _button(container, name: str):
    key = _norm(name)
    for b in container.descendants(control_type="Button"):
        if _norm(b.window_text()) == key:
            return b
    return None


def _edit(container, name: str):
    key = _norm(name)
    for e in container.descendants(control_type="Edit"):
        if _norm(e.window_text()) == key:
            return e
    return None


def _link(container, name: str, pick: str = "first"):
    key = _norm(name)
    els = [e for e in container.descendants(control_type="Hyperlink") if _norm(e.window_text()) == key and e.rectangle().width() > 0]
    if not els:
        return None
    return max(els, key=lambda e: e.rectangle().left) if pick == "right" else els[0]


def _value(el) -> str:
    try:
        return el.get_value() or ""
    except Exception:  # noqa: BLE001
        try:
            return el.window_text() or ""
        except Exception:  # noqa: BLE001
            return ""


# ---------- 대화상자 ----------
def file_dialog():
    d = _win32().window(title=FILE_DIALOG_TITLE, class_name="#32770")
    return d if d.exists() else None


def confirm_dialog_now():
    d = _win32().window(title="웹 페이지 메시지", class_name="#32770")
    return d if d.exists() else None


def popup_window():
    for w in _desktop().windows():
        try:
            if w.class_name() == "Alternate Modal Top Most" and "납본자료접수" in w.window_text():
                return w
        except Exception:  # noqa: BLE001
            continue
    return None


def cleanup_stray_dialogs(log=None) -> int:
    """이전 실행이 남긴 파일 대화상자(취소)와 확인창(취소)을 정리. 팝업 자체는 남긴다(재사용)."""
    log = _aslog(log); n = 0
    d = file_dialog()
    if d:
        try:
            d.child_window(title_re="취소.*", class_name="Button").click(); n += 1; log("남아 있던 파일 대화상자 취소")
        except Exception as e:  # noqa: BLE001
            log.warn(f"파일 대화상자 취소 실패: {e}")
    c = confirm_dialog_now()
    if c:
        txt = " ".join(t.window_text() for t in c.descendants(class_name="Static") if t.window_text())
        try:
            c.child_window(title="취소", class_name="Button").click(); n += 1; log(f"남아 있던 확인창 취소: {txt[:40]}")
        except Exception as e:  # noqa: BLE001
            log.warn(f"확인창 취소 실패: {e}")
    return n


# ---------- 화면 이동 ----------
def goto_recet(win, log=None):
    """메뉴를 눌러 납본자료접수 화면으로 이동: 수집 → 납본 → (온라인 › 단행) 납본자료접수.
    주소를 직접 입력하면 로그인이 풀리므로(2026-09-18 확인) 반드시 메뉴 경로로 간다."""
    log = _aslog(log)
    try:
        if _button(ie_content(win), "일괄반입"):
            log("이미 납본자료접수 화면"); return
    except RuntimeError:
        pass
    win.set_focus(); time.sleep(0.3)
    dismiss_notices(log)
    _act(log, "메뉴 '수집' 클릭", lambda: _link(ie_content(win), "수집").click_input(),
         lambda: _link(ie_content(win), "납본"), T_FIND)
    _act(log, "메뉴 '납본' 클릭", lambda: _link(ie_content(win), "납본").click_input(),
         lambda: _online_recet_link(win), T_FIND)
    _act(log, "'납본자료접수'(온라인) 클릭", lambda: _online_recet_link(win).click_input(),
         lambda: _button(ie_content(win), "일괄반입"), T_PAGE)
    log("납본자료접수 화면 이동 완료")


def _online_recet_link(win):
    """수집>납본 화면: 왼쪽 오프라인, 오른쪽 온라인 패널에 같은 이름 '납본자료접수' → 오른쪽 것. 둘 다 보일 때만."""
    ie = ie_content(win)
    links = [x for x in ie.descendants(control_type="Hyperlink") if _norm(x.window_text()) == "납본자료접수" and x.rectangle().width() > 0]
    return max(links, key=lambda e: e.rectangle().left) if len(links) >= 2 else None


def dismiss_notices(log=None) -> int:
    """공지 팝업 닫기: (1) 홈 화면 안 고정 공지 레이어(fixedNotice) (2) 별도 창 IE 공지. 납본자료접수 팝업은 건드리지 않는다."""
    log = _aslog(log); n = 0
    try:
        ie = ie_content(edge_window(Log()))
        for pane in ie.descendants(control_type="Pane"):
            if pane.element_info.automation_id == "fixedNotice" and pane.rectangle().width() > 0:
                for cb in pane.descendants(control_type="CheckBox"):
                    if "보지 않기" in cb.window_text():
                        cb.click_input(); time.sleep(0.2); break
                b = _button(pane, "닫기")
                if b:
                    b.click_input(); n += 1; log(f"공지 레이어 닫음(24시간 보지 않기): {pane.window_text().strip()[:40]}"); time.sleep(0.5)
    except Exception as e:  # noqa: BLE001
        log.warn(f"공지 레이어 확인 건너뜀: {e}")
    for w in _desktop().windows():
        try:
            c = w.class_name(); t = w.window_text()
            if c == "Chrome_WidgetWin_1" or "납본자료접수" in t or not w.descendants(class_name="Internet Explorer_Server"):
                continue
            b = next((b for nm in ("닫기", "확인", "close", "Close") for b in [_button(w, nm)] if b), None)
            if b:
                b.click_input()
            else:
                w.close()
            n += 1; log(f"공지 팝업 닫음: {t[:40]}"); time.sleep(0.5)
        except Exception:  # noqa: BLE001
            continue
    return n


# ---------- 일괄반입 ----------
def open_batch_import(win, log=None):
    """'일괄반입' → 확인창(신규 접수번호 생성) '확인' → 팝업. 팝업 창 객체를 돌려준다."""
    log = _aslog(log)
    def click_batch():
        b = _button(ie_content(win), "일괄반입")
        if not b:
            raise RuntimeError("'일괄반입' 버튼이 없습니다")
        b.click_input()
    dlg = _act(log, "'일괄반입' 클릭 → 확인창", click_batch, confirm_dialog_now, T_FIND)
    txt = " ".join(t.window_text() for t in dlg.descendants(class_name="Static") if t.window_text())
    log(f"확인창: {txt[:80]}")
    if "접수번호" not in txt:
        dlg.child_window(title="취소", class_name="Button").click()
        raise RuntimeError(f"예상과 다른 확인창(취소함): {txt[:80]}")
    pop = _act(log, "확인창 '확인' → 팝업", lambda: dlg.child_window(title="확인", class_name="Button").click(), popup_window, T_FIND)
    log("팝업 열림")
    return pop


def fill_popup(pop, note: str, xlsx: Path, log=None) -> dict:
    """팝업의 비고 입력 + 첨부파일 선택. '반입'은 누르지 않는다."""
    log = _aslog(log)
    xlsx = Path(xlsx)
    if not xlsx.exists():
        raise FileNotFoundError(f"첨부할 파일이 없습니다: {xlsx}")
    import pyperclip  # type: ignore
    pop.set_focus(); time.sleep(0.3)

    def put_note():
        memo = _edit(ie_content(pop), "비고")
        pyperclip.copy(note); memo.click_input(); memo.type_keys("^a^v")   # IE 입력칸은 한글 type_keys 불안정 → 클립보드
    _act(log, "비고 입력", put_note, lambda: _norm(_value(_edit(ie_content(pop), "비고"))) == _norm(note), 5)
    log(f"비고 입력 확인: {note}")

    def click_browse():
        b = _button(ie_content(pop), "첨부파일") or _button(ie_content(pop), "찾아보기...")
        if not b:
            raise RuntimeError("'찾아보기' 버튼이 없습니다")
        b.click_input()
    def attached():
        return xlsx.name in _value(_edit(ie_content(pop), "첨부파일") or _edit(ie_content(pop), "x"))
    def one_round():
        if not file_dialog():
            _act(log, "'찾아보기' 클릭 → 파일 대화상자", click_browse, file_dialog, T_DIALOG)
        select_file_dialog(xlsx, log)
    _act(log, "첨부파일 선택", one_round, attached, 5, recover=lambda: cleanup_stray_dialogs(log))
    fields = {}
    for e in ie_content(pop).descendants(control_type="Edit"):
        fields[e.window_text()] = _value(e)
    log(f"팝업 값: 비고='{fields.get('비고', '')}', 첨부='{Path(fields.get('첨부파일', '')).name}'")
    return {"popup_fields": fields, "attached": True}


def select_file_dialog(path: Path, log=None, title: str = FILE_DIALOG_TITLE) -> None:
    """윈도 표준 '열기' 대화상자: 파일 이름 칸에 직접 값 쓰기 → 읽어서 확인 → '열기' 클릭 → 닫힘 확인. 실패하면 취소하고 예외."""
    log = _aslog(log)
    d = _wait(lambda: _win32().window(title=title, class_name="#32770") if _win32().window(title=title, class_name="#32770").exists() else None,
              T_DIALOG, what=f"파일 선택 대화상자 '{title}'")
    edit = d.child_window(class_name="Edit", found_index=0)   # 파일 이름(N) 칸
    def put():
        edit.set_focus(); edit.set_edit_text(str(path))
    _act(log, "파일 이름 칸 입력", put, lambda: edit.window_text().strip() == str(path), 3)
    def open_():
        btn = d.child_window(title_re="열기.*", class_name="Button")
        btn.click() if btn.exists() else edit.type_keys("{ENTER}")
    try:
        _act(log, "'열기' 클릭 → 대화상자 닫힘", open_, lambda: not file_dialog(), T_DIALOG, retries=2)
    except RuntimeError:
        try:
            d.child_window(title_re="취소.*", class_name="Button").click()
        except Exception:  # noqa: BLE001
            pass
        raise
    log(f"파일 선택: {path.name}")


T_IMPORT = 900   # 반입 처리 대기(초). 2026-09-18 실측: 수 분 걸림


def submit(pop, yes: str, log=None, wait: bool = True) -> dict:
    """'반입' 클릭 → "일괄반입이 진행됩니다. 진행하시겠습니까?" 확인 → (wait) "반입이 완료되었습니다" 까지 대기 → 확인.
    yes 가 정확히 'YES' 일 때만. KOLIS 에 실제 반입되는 동작.
    2026-09-18 실측: 팝업이 앞에 있지 않으면 클릭이 먹지 않음 → set_focus 후 클릭, 확인창이 뜰 때까지 재시도."""
    log = _aslog(log)
    if yes != "YES":
        raise RuntimeError("반입은 직원 동의 후 YES 를 넘겨야 합니다")
    def click_import():
        pop.set_focus(); time.sleep(0.4)
        b = _button(ie_content(pop), "반입")
        if not b:
            raise RuntimeError("'반입' 버튼이 없습니다")
        b.click_input()
    dlg = _act(log, "'반입' 클릭 → 진행 확인창", click_import, confirm_dialog_now, T_DIALOG)
    txt = " ".join(t.window_text() for t in dlg.descendants(class_name="Static") if t.window_text())
    log(f"확인창: {txt[:80]}")
    if "진행" not in txt:
        dlg.child_window(title="취소", class_name="Button").click()
        raise RuntimeError(f"예상과 다른 확인창(취소함): {txt[:80]}")
    dlg.child_window(title="확인", class_name="Button").click()
    log("'확인' 클릭 — KOLIS 가 반입 처리 중(수 분 걸릴 수 있음)")
    if not wait:
        return {"submitted": True, "message": ""}
    t0 = time.time()
    while time.time() - t0 < T_IMPORT:
        d = confirm_dialog_now()
        if d:
            msg = " ".join(t.window_text() for t in d.descendants(class_name="Static") if t.window_text())
            log(f"결과 메시지: {msg[:120]} ({int(time.time() - t0)}초)")
            d.child_window(title="확인", class_name="Button").click()
            time.sleep(1.5)
            return {"submitted": True, "message": msg, "ok": "완료" in msg, "popup_open": bool(popup_window())}
        if not popup_window():
            log("팝업이 닫힘(결과 메시지 없이)"); return {"submitted": True, "message": "", "ok": None, "popup_open": False}
        if int(time.time() - t0) % 30 == 0:
            log(f"  반입 처리 대기 중… {int(time.time() - t0)}초")
        time.sleep(1)
    raise TimeoutError(f"반입 결과 메시지가 {T_IMPORT}초 안에 뜨지 않음")


def close_popup(pop, log=None) -> None:
    log = _aslog(log)
    b = _button(ie_content(pop), "닫기")
    if b:
        b.click_input(); log("팝업 닫음")


def download_export(log=None, work_dir: Path = Path("work")) -> dict:
    """납본자료접수 화면 '전체출력' → IE 알림 막대(Frame Notification Bar) '저장' → Downloads 에 ExcelDown….xls.
    2026-09-18 실측: 알림 막대 버튼은 이름('저장')으로 잡히지만 control_type 이 Button 이 아니라 descendants 전체에서 이름으로 찾는다."""
    import glob, os, re as _re, shutil
    log = _aslog(log)
    from .ids_from_export import receipt_map
    win = edge_window(log)
    if not _button(ie_content(win), "전체출력"):
        raise RuntimeError("납본자료접수 화면이 아닙니다('전체출력' 버튼 없음)")
    dl = Path(os.path.expanduser("~/Downloads"))
    before = set(glob.glob(str(dl / "ExcelDown*")))
    def click_export():
        win.set_focus(); time.sleep(0.3); _button(ie_content(win), "전체출력").click_input()
    def bar():
        bars = win.descendants(class_name="Frame Notification Bar")
        return bars[0] if bars else None
    b = _act(log, "'전체출력' 클릭 → 다운로드 알림 막대", click_export, bar, T_DIALOG)
    def click_save():
        s = [e for e in bar().descendants() if e.window_text() == "저장"]
        if not s:
            raise RuntimeError("알림 막대에 '저장' 없음")
        s[0].click_input()
    def new_file():
        cand = [p for p in set(glob.glob(str(dl / "ExcelDown*"))) - before if not p.endswith(".partial") and not p.endswith(".crdownload")]
        return cand[0] if cand else None
    path = Path(_act(log, "알림 막대 '저장' → 파일 내려받기", click_save, new_file, 40))
    time.sleep(1)
    m = receipt_map(path)
    if not m:
        raise RuntimeError(f"내려받은 파일에서 접수번호·콘텐츠ID 를 찾지 못함: {path.name}")
    receipt = m[0]["no"].split("-")[0]
    work_dir.mkdir(parents=True, exist_ok=True)
    dst = work_dir / f"접수번호 {receipt}.xls"
    shutil.copy(path, dst)
    log(f"전체출력 저장: {dst} ({len(m)}건, 접수번호 {receipt})")
    return {"file": str(dst), "receipt": receipt, "count": len(m), "first": m[0]["cnts"], "last": m[-1]["cnts"], "title": m[0]["title"]}


def prepare_batch_import(note: str, xlsx: Path, log=None) -> dict:
    """전체 준비 시퀀스(반입 전까지). 실패하면 화면 캡처·창 목록을 남기고 예외."""
    log = _aslog(log)
    log(f"=== 일괄반입 준비 시작: 비고='{note}', 파일='{Path(xlsx).name}' (로그 {log.path})")
    try:
        cleanup_stray_dialogs(log)
        win = edge_window(log)
        goto_recet(win, log)
        pop = popup_window()
        if pop:
            log("열려 있는 일괄반입 팝업 재사용(새 접수번호 생성 안 함)")
        else:
            pop = open_batch_import(win, log)
        r = fill_popup(pop, note, Path(xlsx), log)
        log("=== 준비 완료(반입 버튼은 누르지 않음)")
        return r
    except Exception as e:  # noqa: BLE001
        log.error("".join(traceback.format_exception_only(type(e), e)).strip())
        r = capture_failure(log, f"일괄반입 준비 실패: {e}")
        raise RuntimeError(f"{e}  [캡처: {Path(r['shot']).name if r['shot'] else '없음'}]") from e
