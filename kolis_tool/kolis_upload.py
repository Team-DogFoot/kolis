"""원문일괄등록(폴더) — 가이드 3.4-나. 폴더를 팝업에 끌어다 놓는 것은 사람이 하고, 그 뒤를 이 모듈이 한다.

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
from . import kolis_ui as k
from .common import IMAGE_EXT_ACCEPTED

T_UPLOAD_MIN = 120          # 전송 최소 대기 한도(초)
SEC_PER_MB = 1.6            # 전송 한도 계산용(실측 1.1MB/초보다 넉넉히)
PROGRESS_RE = re.compile(r"\d+\s*/\s*\d+|MB/초|남은 시간|^\d+%")


class Stop(Exception):
    """사람이 봐야 하는 상황. 화면은 그대로 둔다."""


def check_local(root: Path) -> dict:
    """끌어다 놓을 원고 상위 폴더 검사: 하위 폴더가 전부 CNTS-… 이고, 그 안에 이미지 외 파일·하위 폴더가 없어야 한다."""
    root = Path(root)
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
    return {"open": True, "buttons": _texts(ie, "Button"), "checkboxes": checks, "cnts": list(dict.fromkeys(cnts)), "cnts_cells": len(cnts),
            "results": dict(results), "summary": [t for t in texts if "항목" in t or "추가됨" in t][:3],
            "progress": [t for t in texts if PROGRESS_RE.search(t)][:6], "dialog": _dialog_text()[1]}


def run(root: Path, log=None, handle: dict | None = None, yes: str = "") -> dict:
    """끌어다 놓은 뒤의 전 과정. yes 가 'YES' 일 때만(직원 동의). handle['cancel'] 로 단계 사이에서 중단."""
    log = k._aslog(log)
    handle = handle or {}
    if yes != "YES":
        raise Stop("원문일괄등록은 직원 동의 후 YES 를 넘겨야 합니다")
    local = check_local(Path(root))
    if local["problems"]:
        raise Stop("원고 폴더 문제: " + "; ".join(local["problems"]))
    n = local["folders"]
    log(f"=== 원문일괄등록 시작: 폴더 {n}개, 파일 {local['files']}개, {local['mb']} MB")
    pop = k.upload_popup_window()
    if not pop:
        raise Stop("원문일괄등록(폴더) 팝업이 없습니다. 목록 전체 선택 → '원문일괄등록(폴더)' → 폴더를 끌어다 놓은 뒤 실행하세요")
    d, t = _dialog_text()
    if d:
        raise Stop(f"알림창이 열려 있습니다: '{t[:80]}'")
    st = state(pop)
    log(f"팝업 상태: {st['summary']} 버튼 {st['buttons']}")
    unknown = [c for c in st["cnts"] if c not in local["names"]]
    if unknown:
        raise Stop(f"팝업에 이 작품 것이 아닌 폴더가 있습니다: {unknown[:3]}")

    def cancelled():
        if handle.get("cancel"):
            raise Stop("사용자가 중단함")

    ie = lambda: k.ie_content(pop)   # noqa: E731
    done = st["results"]
    # ② 전송
    if not done:
        if not any(str(n) in s for s in st["summary"]):
            raise Stop(f"팝업에 올라온 항목 수를 확인하지 못했습니다(기대 {n}개, 표시 {st['summary']}). 끌어다 놓기가 끝났는지 확인하세요")
        limit = max(T_UPLOAD_MIN, local["mb"] * SEC_PER_MB + 120)
        _focus(pop)
        k._button(ie(), "전송하기").click_input()
        log(f"'전송하기' 클릭 — 전송 대기(한도 {int(limit)}초)")
        t0, last, seen_progress = time.time(), "", False
        while True:
            cancelled()
            s = state(pop)
            if s["dialog"]:
                raise Stop(f"전송 중 알림창: '{s['dialog'][:80]}'")
            if s["progress"]:
                seen_progress = True
                line = " | ".join(s["progress"])[:120]
                if line != last and int(time.time() - t0) % 20 < 3:
                    log(f"  전송 중 {int(time.time() - t0)}초: {line}"); last = line
            elif (seen_progress or time.time() - t0 > 15) and s["cnts_cells"] >= min(n, 1) and not s["summary"]:
                break
            elif time.time() - t0 > 15 and not seen_progress and s["summary"]:
                raise Stop("'전송하기' 를 눌렀지만 전송이 시작되지 않았습니다")
            if time.time() - t0 > limit:
                raise Stop(f"전송이 {int(limit)}초 안에 끝나지 않았습니다. 화면을 확인하세요")
            time.sleep(3)
        log(f"전송 끝 ({int(time.time() - t0)}초). 결과표에 폴더 행 표시")
    else:
        log(f"이미 전송된 상태로 보임(결과표 {done}) — 전송 건너뜀")
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
        k._button(ie(), "일괄정보입력").click_input()
        _confirm("정보입력을 하시겠습니까", 15, log)
        t0 = time.time(); limit = n * 3 + 60
        while True:
            cancelled()
            s = state(pop)
            if s["dialog"]:
                raise Stop(f"정보입력 중 알림창: '{s['dialog'][:80]}'")
            shown = min(n, max(1, len(s["cnts"])))
            if s["results"].get("정보입력", 0) >= shown and time.time() - t0 >= n * 0.7:
                break
            if time.time() - t0 > limit:
                raise Stop(f"정보입력결과가 {limit}초 안에 채워지지 않았습니다(보이는 행 {s['results']})")
            time.sleep(2)
        log(f"일괄정보입력 끝 ({int(time.time() - t0)}초, 보이는 행 {s['results']})")
    cancelled()
    # ⑤ 원문등록
    _focus(pop)
    k._button(ie(), "원문등록").click_input()
    _confirm("원문등록하시겠습니까", 15, log)
    msg = _confirm("원문이 등록되었습니다", n * 6 + 120, log)
    s = state(pop)
    log(f"=== 원문일괄등록 완료: {msg} (보이는 행 {s['results']})")
    return {"folders": n, "files": local["files"], "mb": local["mb"], "message": msg, "visible": s["results"]}
