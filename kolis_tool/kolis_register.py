"""등록대상처리 → 등록원부작성(가원부번호 발급) → 등록원부관리 전체출력. 가이드 3.4 끝 ~ 3.5.

2026-09-29 타임머신 대소동(접수번호 939 → 가원부번호 2026-1615)으로 실제 화면에서 한 절차 그대로다.
단계마다 상태를 읽어 확인하고, 예상하지 못한 알림창이면 누르지 않고 멈춘다(Stop).

  target_process(receipt)      납본자료접수: 접수번호 찾기 → 전체 선택 → '등록대상처리' → 대화 상자 '전체자료' → 확인 2번 → "등록대상처리가 완료되었습니다"
  make_record(receipt)         등록 › 온라인 › 단행 › 등록원부작성: 접수번호 찾기 → 전체 선택 → '원부작성' → 원문서비스구분 '07 | 납본뷰어'
                               → '가원부번호부여' → "성공했습니다" → 가원부번호를 읽어 돌려준다
  export_record(no, receipt)   등록 › 온라인 › 단행 › 등록원부관리: 등록구분 FTX, 가원부번호로 찾기 → 전체 선택 → 전체출력
                               → 'work/가원부번호 <연도>-<번호>(접수번호 <접수번호>).xlsx' (주무관에게 보내는 파일. 열 구성은 직원 파일과 같게)

실측 메모
  - 대화 상자(웹 페이지 대화 상자)는 창 클래스 `Internet Explorer_TridentDlgFrame`. 그 안의 요소는 Edge 의 보조 창(`Alternate Modal Top Most`)에서 읽힌다.
  - 등록원부작성 목록에 뜨는 자료는 콘텐츠유형·장르·이용대상·서비스범위가 반입 값대로 이미 들어 있다(텍스트·만화·일반·국립중앙도서관 공개).
    가이드는 "이용대상자·서비스범위가 같은 자료만 선택해 원부작성"이라고 하므로, 섞여 있으면 멈춘다(사람이 나눠서 한다).
  - 메뉴는 상단 '등록'을 누르면 펼쳐지고, 온라인 › 단행 열은 왼쪽에서 세 번째 묶음이다(같은 이름의 링크가 여러 개).
"""
from __future__ import annotations
import glob, os, re, shutil, time
from pathlib import Path
from . import kolis_ui as k, ie_dom

WONMUN_SVC = ("07", "납본뷰어")
REG_CODE = "FTX"


class Stop(Exception):
    """사람이 봐야 하는 상황. 화면은 그대로 둔다."""


# ---------- 화면 읽기 도구 ----------
def _dialogs():
    from pywinauto import Desktop
    return [w for w in Desktop(backend="win32").windows() if w.class_name() == "Internet Explorer_TridentDlgFrame"]


def _dialog_ie():
    """떠 있는 대화 상자의 요소(UIA). 없으면 None."""
    from pywinauto import Desktop
    if not _dialogs():
        return None
    for w in Desktop(backend="uia").windows():
        if w.class_name() == "Alternate Modal Top Most":
            return k.ie_content(w)
    return None


def _alert() -> tuple[object, str]:
    d = k.confirm_dialog_now()
    return (d, " / ".join(t.window_text() for t in d.descendants(class_name="Static") if t.window_text())) if d else (None, "")


def _wait(fn, sec: float, what: str, step: float = 0.4):
    t0 = time.time()
    while time.time() - t0 < sec:
        r = fn()
        if r:
            return r
        time.sleep(step)
    raise Stop(f"기다리다 못 찾음: {what}")


def _answer(expect: tuple[str, ...], sec: float, log, final: tuple[str, ...] = ()) -> str:
    """알림창을 기다려, 문구에 expect 중 하나가 들어 있으면 '확인'. 다른 문구면 누르지 않고 멈춘다. 마지막 문구(final)를 확인하면 돌아온다."""
    t0, last = time.time(), ""
    while time.time() - t0 < sec:
        d, t = _alert()
        if d:
            if not any(e in t for e in expect + final):
                raise Stop(f"예상하지 못한 알림창: '{t[:100]}'")
            d.child_window(title="확인", class_name="Button").click_input()
            log(f"알림창 확인: {t[:70]}")
            last = t
            t1 = time.time()
            while time.time() - t1 < 5 and _alert()[1] == t:
                time.sleep(0.15)
            if not final or any(e in t for e in final):
                return t
        time.sleep(0.3)
    raise Stop(f"알림창이 뜨지 않음(기대 {final or expect}, 마지막 '{last[:40]}')")


def _doc(part: str):
    for _t, _c, top in ie_dom._documents(only_free=True):
        for d in ie_dom._walk(top):
            if part in str(d.URL):
                return d
    return None


def _field(doc, name: str):
    els = doc.forms.item(0).elements
    for j in range(int(els.length)):
        e = els.item(j)
        if str(getattr(e, "name", "") or "") == name or str(getattr(e, "id", "") or "") == name:
            return e
    return None


def _select_by_keys(combo, read, want, log, what: str, n: int = 20):
    """IE 의 선택칸은 값을 직접 넣을 수 없다 → 방향키로 옮기며 값을 읽어 맞춘다."""
    from pywinauto import keyboard
    combo.click_input(); time.sleep(0.4)
    keyboard.send_keys("{ESC}"); time.sleep(0.3)
    keyboard.send_keys("{HOME}"); time.sleep(0.3)
    for _ in range(n):
        if want(read()):
            break
        keyboard.send_keys("{DOWN}"); time.sleep(0.3)
    keyboard.send_keys("{TAB}"); time.sleep(0.4)
    if not want(read()):
        raise Stop(f"{what} 을(를) 맞추지 못했습니다(지금 값 {read()})")
    log(f"{what}: {read()}")


def _select_all(win, log) -> None:
    from pywinauto import mouse
    from .kolis_thumbs import checked
    hdr = [c for c in k.ie_content(win).descendants(control_type="CheckBox") if c.rectangle().width() > 0]
    if not hdr:
        raise Stop("목록 헤더 체크박스를 찾지 못함")
    cb = min(hdr, key=lambda c: (c.rectangle().top, c.rectangle().left))
    r = cb.rectangle(); cx, cy = (r.left + r.right) // 2, (r.top + r.bottom) // 2
    win.set_focus(); time.sleep(0.3)
    for _ in range(3):
        if checked(cx, cy):
            break
        mouse.click(coords=(cx, cy)); time.sleep(0.6)
    if not checked(cx, cy):
        raise Stop("전체 선택 체크가 되지 않음")
    log("목록 전체 선택")


def _close_dialog(log, what: str) -> None:
    ie = _dialog_ie()
    if not ie:
        return
    def do():
        _dialogs()[0].set_focus(); time.sleep(0.3)
        [b for b in _dialog_ie().descendants(control_type="Button") if k._norm(b.window_text()) == "닫기"][-1].click_input()
    k._act(log, f"{what} '닫기'", do, lambda: not _dialogs(), k.T_DIALOG)


def goto_menu(win, top: str, item: str, title_part: str, log):
    """상단 메뉴(top)를 펼쳐 온라인 › 단행 열의 item 으로 이동. 이미 그 화면이면 그대로. 이동한 뒤의 Edge 창을 돌려준다."""
    if title_part in win.window_text():
        log(f"이미 {item} 화면"); return win
    win.set_focus(); time.sleep(0.3)
    def links(name):
        return [e for e in k.ie_content(win).descendants(control_type="Hyperlink") if e.rectangle().width() > 0 and k._norm(e.window_text()) == k._norm(name)]
    def online_mono():
        ls = sorted(links(item), key=lambda e: (e.rectangle().left, e.rectangle().top))
        cols = sorted({e.rectangle().left for e in ls})
        if len(cols) < 3:
            return None
        col = cols[-2] if len(cols) >= 4 else cols[-1]      # 오프라인 단행·연속, 온라인 단행·연속 순 → 온라인 단행은 끝에서 두 번째 열
        return max((e for e in ls if e.rectangle().left == col), key=lambda e: e.rectangle().top)
    k._act(log, f"메뉴 '{top}' 클릭", lambda: [e for e in links(top) if e.rectangle().top < 260][0].click_input(), online_mono, k.T_FIND)
    target = online_mono()
    target.click_input()
    new = _wait(lambda: (lambda w: w if title_part in w.window_text() else None)(k.edge_window(lambda m: None)), k.T_PAGE, f"{item} 화면")
    time.sleep(1.5)
    ie_dom.tick(f"{item} 화면 이동")
    log(f"{item} 화면 이동 완료")
    return new


# ---------- 1. 등록대상처리 ----------
def target_process(receipt: str, log=None) -> dict:
    log = k._aslog(log)
    ie_dom.recorder(log)
    log(f"=== 등록대상처리 시작: 접수번호 {receipt}")
    k.cleanup_stray_dialogs(log); k.close_leftover_popup(log)
    win = k.edge_window(log)
    k.goto_recet(win, log)
    n = k.search_receipt(win, receipt, log)
    btn = k._button(k.ie_content(win), "등록대상처리")
    if not btn or not btn.is_enabled():
        raise Stop("'등록대상처리' 버튼을 누를 수 없습니다(목록이 비었거나 이미 처리된 접수번호)")
    k.ensure_visible(win, btn, log)
    _select_all(win, log)
    ie_dom.tick("등록대상처리 (전)")
    k._button(k.ie_content(win), "등록대상처리").click_input()
    _wait(lambda: _dialog_ie() or _alert()[0], 15, "등록대상처리 대화 상자")
    if _alert()[0]:
        raise Stop(f"'등록대상처리' 클릭 후 알림창: '{_alert()[1][:80]}'")
    radios = [(e.window_text(), e) for e in _dialog_ie().descendants(control_type="RadioButton")]
    if [t for t, _ in radios] != ["전체자료", "선정된 일부자료"]:
        raise Stop(f"대화 상자의 선택 항목이 예상과 다릅니다: {[t for t, _ in radios]}")
    ie_dom.tick("등록대상처리 대화 상자")
    _dialogs()[0].set_focus(); time.sleep(0.3)
    [b for b in _dialog_ie().descendants(control_type="Button") if k._norm(b.window_text()) == "확인"][0].click_input()   # 기본 선택 '전체자료'
    msg = _answer(("등록대상으로 처리하시겠습니까", "등록대상처리 하시겠습니까"), 90, log, final=("등록대상처리가 완료되었습니다",))
    ie_dom.tick("등록대상처리 (후)")
    _close_dialog(log, "등록대상처리 대화 상자")
    log(f"=== 등록대상처리 완료: {msg}")
    return {"receipt": receipt, "count": n, "message": msg}


# ---------- 2. 등록원부작성(가원부번호) ----------
def make_record(receipt: str, log=None) -> dict:
    log = k._aslog(log)
    ie_dom.recorder(log)
    log(f"=== 등록원부작성 시작: 접수번호 {receipt}")
    k.cleanup_stray_dialogs(log)
    win = goto_menu(k.edge_window(log), "등록", "등록원부작성", "등록원부작성]", log)
    win.set_focus(); time.sleep(0.4)
    e = k._edit(k.ie_content(win), "접수번호")
    e.click_input(); e.type_keys("^a{BACKSPACE}" + str(receipt)); time.sleep(0.5)
    ie_dom.tick("등록원부작성 찾기 (전)")
    k._button(k.ie_content(win), "찾기").click_input()
    def rows():
        return [t.window_text() for t in k.ie_content(win).descendants(control_type="DataItem") if re.fullmatch(rf"\d{{4}}-\d+-0*{receipt}-\d+", t.window_text().strip())]
    _wait(lambda: rows() or _alert()[0], k.T_PAGE, "등록원부작성 목록")
    if _alert()[0]:
        raise Stop(f"찾기 후 알림창: '{_alert()[1][:80]}'")
    ie_dom.tick("등록원부작성 찾기 (후)")
    n = len(rows())
    cells = [t.window_text().strip() for t in k.ie_content(win).descendants(control_type="DataItem") if t.window_text().strip()]
    audiences = {c for c in cells if c in ("일반", "성인", "아동", "청소년")}
    scopes = {c for c in cells if "공개" in c}
    log(f"목록 {n}건(화면에 보이는 행), 이용대상 {sorted(audiences)}, 서비스범위 {sorted(scopes)}")
    if len(audiences) > 1 or len(scopes) > 1:
        raise Stop(f"이용대상·서비스범위가 섞여 있습니다({sorted(audiences)}, {sorted(scopes)}). 같은 것끼리 나눠서 원부작성해야 합니다(가이드 3.5)")
    _select_all(win, log)
    ie_dom.tick("원부작성 (전)")
    k._button(k.ie_content(win), "원부작성").click_input()
    _wait(lambda: _doc("onlineAccRecMakeInput") or _alert()[0], 15, "원부작성 팝업")
    if _alert()[0]:
        raise Stop(f"'원부작성' 클릭 후 알림창: '{_alert()[1][:80]}'")
    time.sleep(1)
    def val(name):
        return str(_field(_doc("onlineAccRecMakeInput"), name).value)
    before = {x: val(x) for x in ("accession_rec_make_year", "reg_code", "book_cnt", "file_cnt", "temp_accession_rec_no")}
    log(f"원부작성 팝업: 작성년도 {before['accession_rec_make_year']}, 등록구분 {before['reg_code']}, 콘텐츠수 {before['book_cnt']}, 파일수 {before['file_cnt']}")
    if before["reg_code"] != REG_CODE:
        raise Stop(f"등록구분이 {REG_CODE} 가 아닙니다: {before['reg_code']}")
    if before["temp_accession_rec_no"]:
        raise Stop(f"가원부번호 칸에 이미 값이 있습니다: {before['temp_accession_rec_no']}")
    _dialogs()[0].set_focus(); time.sleep(0.4)
    combo = [c for c in _dialog_ie().descendants(control_type="ComboBox")][-1]
    _select_by_keys(combo, lambda: val("wonmunSvcGbnCd"), lambda v: v == WONMUN_SVC[0], log, f"원문서비스구분({WONMUN_SVC[0]} | {WONMUN_SVC[1]})")
    ie_dom.tick("가원부번호부여 (전)")
    _dialogs()[0].set_focus(); time.sleep(0.3)
    [b for b in _dialog_ie().descendants(control_type="Button") if k._norm(b.window_text()) == "가원부번호부여"][0].click_input()
    _answer((), 60, log, final=("성공했습니다",))
    time.sleep(1)
    no = val("temp_accession_rec_no")
    ie_dom.tick("가원부번호부여 (후)")
    if not re.fullmatch(r"\d+", no):
        raise Stop(f"가원부번호를 읽지 못했습니다(칸의 값 '{no}')")
    year = before["accession_rec_make_year"]
    _close_dialog(log, "원부작성 팝업")
    log(f"=== 가원부번호 발급: {year}-{no} (접수번호 {receipt}, 콘텐츠 {before['book_cnt']}건)")
    return {"receipt": receipt, "year": year, "no": no, "count": int(before["book_cnt"] or 0), "files": int(before["file_cnt"] or 0)}


# ---------- 3. 등록원부관리 전체출력 ----------
def export_record(no: str, receipt: str, year: str = "", work_dir: Path = Path("work"), log=None) -> dict:
    from .ids_from_export import export_table
    import openpyxl
    log = k._aslog(log)
    ie_dom.recorder(log)
    log(f"=== 등록원부관리 전체출력 시작: 가원부번호 {no}")
    k.cleanup_stray_dialogs(log)
    win = goto_menu(k.edge_window(log), "등록", "등록원부관리", "등록원부관리]", log)
    win.set_focus(); time.sleep(0.4)
    doc = lambda: _doc("onlineAccRecMng.do")      # noqa: E731
    combo = [c for c in k.ie_content(win).descendants(control_type="ComboBox") if c.window_text() == "등록구분"][0]
    _select_by_keys(combo, lambda: str(_field(doc(), "reg_code").value), lambda v: v == REG_CODE, log, f"등록구분({REG_CODE})")
    if str(_field(doc(), "rec_no_yn").value) != "N":
        raise Stop("번호 종류가 '가원부번호'가 아닙니다. 화면에서 가원부번호로 바꾼 뒤 다시 실행하세요")
    year = year or str(_field(doc(), "accession_rec_make_year").value)
    ed = k._edit(k.ie_content(win), "원부번호")
    ed.click_input(); ed.type_keys("^a{BACKSPACE}" + str(no)); time.sleep(0.5)
    if str(_field(doc(), "accession_rec_no").value) != str(no):
        raise Stop("가원부번호가 칸에 들어가지 않았습니다")
    ie_dom.tick("등록원부관리 찾기 (전)")
    k._button(k.ie_content(win), "찾기").click_input()
    def rows():
        return [t.window_text() for t in k.ie_content(win).descendants(control_type="DataItem") if re.fullmatch(r"CNTS-\d+", t.window_text().strip())]
    _wait(lambda: rows() or _alert()[0], k.T_PAGE, "등록원부관리 목록")
    if _alert()[0]:
        raise Stop(f"찾기 후 알림창: '{_alert()[1][:80]}'")
    ie_dom.tick("등록원부관리 찾기 (후)")
    _select_all(win, log)
    dl = Path(os.path.expanduser("~/Downloads"))
    before = set(glob.glob(str(dl / "ExcelDown*")))
    def bar():
        b = win.descendants(class_name="Frame Notification Bar")
        return b[0] if b else None
    def new_file():
        cand = [p for p in set(glob.glob(str(dl / "ExcelDown*"))) - before if not p.endswith((".partial", ".crdownload"))]
        return cand[0] if cand else None
    def click_export():
        win.set_focus(); time.sleep(0.3)
        b = [x for x in k.ie_content(win).descendants(control_type="Button") if k._norm(x.window_text()) == "전체출력"][0]
        k.ensure_visible(win, b, log); b.click_input()
    k._act(log, "'전체출력' 클릭 → 다운로드 알림 막대", click_export,
           lambda: new_file() or (bar() and [e for e in bar().descendants() if e.window_text() == "저장"]), k.T_DIALOG)
    def click_save():
        if not new_file():
            [e for e in bar().descendants() if e.window_text() == "저장"][0].click_input()
    path = Path(k._act(log, "알림 막대 '저장' → 파일", click_save, new_file, 40))
    time.sleep(1)
    ie_dom.tick("등록원부관리 전체출력 (후)")
    table = export_table(path)
    if not table:
        raise Stop(f"내려받은 파일을 읽지 못했습니다: {path.name}")
    cols = [c for c in table[0].keys() if c and c not in ("선정", "ㅁ")]      # 체크박스 열은 뺀다(직원이 보내는 파일에 없음)
    name = f"가원부번호 {year}-{no}(접수번호 {receipt})"
    work_dir = Path(work_dir); work_dir.mkdir(parents=True, exist_ok=True)
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = f"가원부번호 {year}-{no}"
    ws.append(cols)
    for r in table:
        ws.append([r.get(c, "") for c in cols])
    out = work_dir / f"{name}.xlsx"
    wb.save(out)
    shutil.copy(path, work_dir / f"{name}.xls")
    log(f"=== 등록원부관리 전체출력 저장: {out.name} ({len(table)}건)")
    return {"file": str(out), "count": len(table), "no": no, "year": year, "receipt": receipt, "ids": [r.get("콘텐츠ID", "") for r in table]}


def run(receipt: str, work_dir: Path = Path("work"), log=None, handle: dict | None = None, yes: str = "") -> dict:
    """세 단계를 이어서. yes 가 'YES' 일 때만(직원 동의). 단계 사이에서 handle['cancel'] 을 본다."""
    log = k._aslog(log)
    handle = handle or {}
    if yes != "YES":
        raise Stop("등록대상처리와 가원부번호 발급은 직원 동의 후 YES 를 넘겨야 합니다")
    a = target_process(receipt, log)
    if handle.get("cancel"):
        raise Stop("사용자가 중단함(등록대상처리까지 끝남)")
    b = make_record(receipt, log)
    if handle.get("cancel"):
        raise Stop(f"사용자가 중단함(가원부번호 {b['year']}-{b['no']} 발급까지 끝남)")
    c = export_record(b["no"], receipt, b["year"], work_dir, log)
    return {"receipt": receipt, "target": a, "record": b, "export": c, "record_no": f"{b['year']}-{b['no']}", "file": c["file"], "count": c["count"]}
