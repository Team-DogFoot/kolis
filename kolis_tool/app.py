"""실행 프로그램 (pywebview).  실행: bin\\app.vbs (콘솔 없음) 또는 python -m kolis_tool.app

화면(kolis_tool/ui/index.html)은 아래 Api 의 메서드를 window.pywebview.api.<이름>() 으로 부른다.
작품마다 탭이 하나다. 오래 걸리는 작업은 스레드로 돌리고, 로그와 결과를 그 작품의 탭으로 보낸다(tab).
  - 1단계(에이전트)는 여러 작품을 동시에 돌릴 수 있다(동시 실행 한도 MAX_AGENTS).
  - KOLIS 단계는 KOLIS 창 하나를 직접 조작하므로 한 번에 한 작품만(_kolis_owner). 요청 방식으로 바뀐 단계는 이 잠금을 풀면 된다.
"""
from __future__ import annotations
import json, re, shutil, threading, traceback
from pathlib import Path
import webview

import os

HERE = Path(__file__).parent
MAX_AGENTS = max(1, int(os.environ.get("KOLIS_MAX_AGENTS", "3")))      # 에이전트 동시 실행 한도
KOLIS_KINDS = ("flow", "kolis", "kolis_submit", "export", "upload_open", "upload", "thumbs_register", "register", "register_export")


class Api:
    def __init__(self):
        self._window: webview.Window | None = None
        self._work_dir = Path("work").resolve()
        self._jobs: dict = {}         # 탭 → {'proc': Popen, 'cancel': bool}
        self._running: dict = {}      # "탭 이름 · 작업" → 시작 시각(진행 중인 스레드 작업)
        self._names: dict = {}        # 탭 → 작품 이름(안내 문구용)
        self._kolis_owner: tuple | None = None      # KOLIS 창을 쓰고 있는 (탭, 작업)
        self._agents = threading.Semaphore(MAX_AGENTS)
        self._lock = threading.Lock()
        from .logutil import UiLog
        self.log = UiLog(self._ui_log, "kolis.app")

    # ---------- 공통 ----------
    def _ui_log(self, msg: str, tab: str = ""):
        if self._window:
            self._window.evaluate_js(f"appendLog({json.dumps(str(msg), ensure_ascii=False)}, {json.dumps(tab)})")

    def _tab_log(self, tab: str):
        """그 작품의 탭으로 가는 로그(화면 + 파일). 파일에는 작품 이름을 앞에 붙인다."""
        from .logutil import UiLog
        name = self._names.get(tab, "")
        lg = UiLog(lambda m: self._ui_log(m, tab), "kolis.app")
        if not name:
            return lg
        class Tagged:
            path = lg.path
            def __call__(s, m, level="INFO"):
                lg.lg.log({"DEBUG": 10, "INFO": 20, "WARN": 30, "WARNING": 30, "ERROR": 40}.get(level, 20), f"<{name}> {m}")
                self._ui_log(m if level == "INFO" else f"[{level}] {m}", tab)
            def debug(s, m): lg.lg.debug(f"<{name}> {m}")
            def warn(s, m): s(m, "WARN")
            def error(s, m): s(m, "ERROR")
            def exception(s, m, e): lg.lg.error(f"<{name}> {m}", exc_info=e); self._ui_log(f"[ERROR] {m}: {e}", tab)
        return Tagged()

    def _kolis_log(self, tab: str):
        from . import kolis_ui
        return kolis_ui.Log(lambda m: self._ui_log(m, tab))

    def _done(self, kind: str, payload: dict, tab: str = ""):
        if self._window:
            self._window.evaluate_js(f"onDone({json.dumps(kind)}, {json.dumps(payload, ensure_ascii=False, default=str)}, {json.dumps(tab)})")

    def _run(self, kind: str, fn, capture: bool = False, tab: str = "", screen: bool | None = None) -> dict:
        """스레드 작업 공통 틀: 시작·종료·소요시간·예외 스택을 파일에 남기고 onDone(kind, 결과, 탭)으로 알린다.
        fn() 은 결과 dict 를 돌려준다. Cancelled → {'cancelled': True}, 그 밖의 예외 → {'error': 문구}.
        capture=True(KOLIS 조작)면 실패 시 화면 캡처·창 목록을 저장한다. KOLIS 작업은 한 번에 하나만 받는다.
        screen=False(요청 방식)면 KOLIS 창을 조작하지 않으므로 잠그지 않고 프로그램 창도 내리지 않는다. 다만 화면 방식 작업이 도는 동안에는
        그 작업이 화면을 옮길 수 있어(요청이 끊김) 받지 않는다."""
        import datetime, time
        from .agent import Cancelled
        log = self._tab_log(tab)
        key = f"{self._names.get(tab) or tab} · {kind}"
        with self._lock:
            if key in self._running:
                return {"error": f"이 작품의 '{kind}' 작업이 이미 진행 중입니다({self._running[key]} 시작)"}
            kolis = (kind in KOLIS_KINDS) if screen is None else screen
            if not kolis and screen is False and self._kolis_owner:
                who = self._names.get(self._kolis_owner[0]) or "다른 작품"
                return {"error": f"지금 '{who}' 작업({self._kolis_owner[1]})이 KOLIS 화면을 조작하고 있습니다. 끝난 뒤에 실행하세요"}
            if kolis:
                if self._kolis_owner:
                    who = self._names.get(self._kolis_owner[0]) or "다른 작품"
                    return {"error": f"KOLIS 창은 지금 '{who}' 작업({self._kolis_owner[1]})이 쓰고 있습니다. 끝난 뒤에 실행하세요(KOLIS 창은 하나라 한 번에 한 작품만)"}
                self._kolis_owner = (tab, kind)
            self._running[key] = datetime.datetime.now().strftime("%H:%M:%S")
        def job():
            t0 = time.time()
            log.debug(f"[{kind}] 시작")
            if kolis:      # 프로그램 창이 KOLIS 버튼·팝업을 덮으면 클릭이 프로그램 창에 떨어진다 → KOLIS 를 조작하는 동안 최소화(모든 KOLIS 단계)
                try:
                    self._window.minimize(); time.sleep(0.6)
                except Exception:  # noqa: BLE001
                    pass
            try:
                r = fn()
                log.debug(f"[{kind}] 완료 {time.time() - t0:.1f}초: {json.dumps(r, ensure_ascii=False, default=str)[:300]}")
                self._done(kind, r if isinstance(r, dict) else {"result": r}, tab)
            except Cancelled:
                log(f"[{kind}] 중단됨"); self._done(kind, {"cancelled": True}, tab)
            except SystemExit as e:
                log.error(f"[{kind}] {e}"); self._done(kind, {"error": str(e)}, tab)
            except Exception as e:  # noqa: BLE001
                log.exception(f"[{kind}] 실패 ({time.time() - t0:.1f}초)", e)
                msg = "".join(traceback.format_exception_only(type(e), e)).strip()
                if capture:
                    try:
                        from . import kolis_ui
                        cap = kolis_ui.capture_failure(self._kolis_log(tab), f"{kind}: {msg}")
                        if cap.get("shot"):
                            msg += f"  [캡처: {Path(cap['shot']).name}]"
                    except Exception:  # noqa: BLE001
                        pass
                self._done(kind, {"error": msg}, tab)
            finally:
                if kolis:
                    try:
                        self._window.restore()
                    except Exception:  # noqa: BLE001
                        pass
                with self._lock:
                    self._running.pop(key, None)
                    if self._kolis_owner == (tab, kind):
                        self._kolis_owner = None
        threading.Thread(target=job, daemon=True, name=f"job-{kind}").start()
        return {"started": True}

    # ---------- 탭(열어 둔 작품) 저장/복원 ----------
    def tabs_load(self) -> dict:
        p = self._work_dir / "tabs.json"
        if p.exists():
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
                for t in d.get("tabs") or []:
                    self._names[t.get("id")] = t.get("title") or Path(t.get("folder") or "").name
                return d
            except Exception:  # noqa: BLE001
                pass
        return {"tabs": [], "active": ""}

    def tabs_save(self, tabs: list, active: str = "") -> bool:
        self._work_dir.mkdir(parents=True, exist_ok=True)
        for t in tabs or []:
            self._names[t.get("id")] = t.get("title") or Path(t.get("folder") or "").name
        (self._work_dir / "tabs.json").write_text(json.dumps({"tabs": tabs, "active": active}, ensure_ascii=False, indent=1), encoding="utf-8")
        return True

    def diagnose(self) -> dict:
        """진단: 환경, 진행 중 작업, KOLIS 창 상태(Edge·팝업·대화상자), 최근 로그."""
        from .logutil import tail, log_path
        out = {"env": self.check_env(), "running": dict(self._running), "max_agents": MAX_AGENTS, "log_path": str(log_path()), "log_tail": tail(40), "kolis": {}}
        try:
            from . import kolis_ui
            from pywinauto import Desktop
            edge = [w.window_text()[:60] for w in Desktop(backend="uia").windows() if w.class_name() == "Chrome_WidgetWin_1" and ("납본" in w.window_text() or "통합자료관리" in w.window_text())]
            out["kolis"] = {"edge": edge, "popup": bool(kolis_ui.popup_window()), "file_dialog": bool(kolis_ui.file_dialog()),
                            "confirm": bool(kolis_ui.confirm_dialog_now()),
                            "upload_popup": any(w.class_name() == "Alternate Modal Top Most" for w in Desktop(backend="uia").windows())}
        except Exception as e:  # noqa: BLE001
            out["kolis"] = {"error": str(e)}
        return out

    def status(self, folder: str) -> dict:
        """작품별 현황: 파일 증거 + 상태 기록을 합쳐 단계마다 done/evidence/when."""
        from .rename_files import is_done as _rd
        from .common import find_manifest, list_images
        from . import prepare
        import re as _re
        f = Path(folder); st = self.load_state(folder)
        steps = []
        def add(key, label, done, evidence="", when=""):
            steps.append({"key": key, "label": label, "done": bool(done), "evidence": evidence, "when": when or (st.get(key) or {}).get("done_at", "")})
        w = prepare.load(f, self._work_dir) or {}
        out = w.get("output_xlsx", "")
        add("prepare", "반입용 엑셀", out and Path(out).exists(), f"{w.get('rows')}행, 사람이 확인할 칸 {w.get('confirm_cells')}개 → {Path(out).name}" if w else "")
        ms = Path(w["manuscripts"]) if w.get("manuscripts") and Path(w["manuscripts"]).is_dir() else None
        eps = [p for p in ms.iterdir() if p.is_dir() and not p.name.startswith("_kolis")] if ms else []
        def eight(p):   # 도구 기록이 없어도(직원 도구로 바꾼 경우) 파일이 전부 8자리 숫자면 완료로 본다
            imgs = list_images(p)
            return bool(imgs) and all(_re.fullmatch(r"\d{8}", q.stem) for q in imgs)
        n_ok = sum(1 for p in eps if _rd(p) or eight(p))
        add("manuscript", "원고 파일명(8자리)", eps and n_ok == len(eps), f"{n_ok}/{len(eps)} 폴더")
        add("kolis_submit", "KOLIS 반입", bool(st.get("kolis_submit")), (st.get("kolis_submit") or {}).get("message", ""))
        ex = (st.get("export") or {})
        add("export", "전체출력", ex.get("file") and Path(ex["file"]).exists(), f"접수번호 {ex.get('receipt', '')} {ex.get('count', '')}건" if ex else "")
        add("cnts", "폴더명 CNTS", ms and find_manifest(ms, "cnts", "cnts_manifest.json") is not None and eps and all(p.name.startswith("CNTS-") for p in eps),
            f"{sum(1 for p in eps if p.name.startswith('CNTS-'))}/{len(eps)} 폴더")
        add("upload", "원문일괄등록", bool(st.get("upload")), (st.get("upload") or {}).get("message", ""))
        rg = st.get("register") or {}
        add("register", "가원부번호", bool(rg.get("record_no")), f"{rg.get('record_no', '')} · {Path(rg.get('file', '')).name}" if rg else "")
        warns = []
        if ex.get("count") and w.get("rows") and int(ex["count"]) != int(w["rows"]):
            warns.append(f"반입 건수 {ex['count']} ≠ 반입용 행 수 {w['rows']}")
        return {"steps": steps, "warnings": warns, "memo": st.get("memo", "")}

    def pick_folder(self) -> str:
        r = self._window.create_file_dialog(webview.FOLDER_DIALOG)
        return r[0] if r else ""

    def pick_file(self, pattern: str = "Excel (*.xlsx)") -> str:
        r = self._window.create_file_dialog(webview.OPEN_DIALOG, file_types=(pattern, "All files (*.*)"))
        return r[0] if r else ""

    def pick_save(self, default_name: str = "") -> str:
        r = self._window.create_file_dialog(webview.SAVE_DIALOG, directory=str(self._work_dir), save_filename=default_name,
                                            file_types=("Excel (*.xlsx)",))
        return (r[0] if isinstance(r, (list, tuple)) else r) or ""

    # ---------- KOLIS 계정: 프로그램 창에서 로그인하면 이 프로그램의 환경변수에만 둔다(파일에 쓰지 않음, 프로그램을 닫으면 사라짐) ----------
    def kolis_account(self) -> dict:
        from . import kolis_http
        src = kolis_http.source()
        return {"source": src, "id": (os.environ.get("KOLIS_ID") or "") if src in ("login", "env") else "", "checked": bool(getattr(self, "_account_ok", False))}

    def kolis_login(self, uid: str, pw: str) -> dict:
        """아이디·비밀번호로 KOLIS 에 실제로 로그인해 보고, 되면 환경변수에 둔다. 한 번만 시도한다(5회 틀리면 계정이 잠긴다)."""
        from . import kolis_http, kolis_request
        uid, pw = (uid or "").strip(), pw or ""
        if not uid or not pw:
            return {"error": "아이디와 비밀번호를 넣으세요"}
        old = {k: os.environ.get(k) for k in ("KOLIS_ID", "KOLIS_PW", "KOLIS_ACCOUNT_FROM")}
        os.environ.update({"KOLIS_ID": uid, "KOLIS_PW": pw, "KOLIS_ACCOUNT_FROM": "login"})
        c = kolis_http.Client()
        try:
            c.login()
        except kolis_request.Stop as e:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
            self._account_ok = False
            self._tab_log("")(f"KOLIS 로그인 실패: {e}")
            return {"error": str(e)}
        finally:
            c.close()
        self._account_ok = True
        self._tab_log("")(f"KOLIS 로그인 확인됨: {uid} (프로그램을 닫을 때까지 이 계정을 씁니다)")
        return {"ok": True, **self.kolis_account()}

    def kolis_logout(self) -> dict:
        for k in ("KOLIS_ID", "KOLIS_PW", "KOLIS_ACCOUNT_FROM"):
            os.environ.pop(k, None)
        self._account_ok = False
        return self.kolis_account()

    def check_env(self) -> dict:
        """시작 시 전제 조건: 클로드코드 설치·로그인 흔적, Edge, Playwright."""
        from .agent import claude_exe
        out = {"claude": bool(claude_exe()), "claude_login": None, "edge": False, "playwright": False}
        cred = Path.home() / ".claude" / ".credentials.json"
        cfg = Path.home() / ".claude.json"
        out["claude_login"] = cred.exists() or (cfg.exists() and '"oauthAccount"' in cfg.read_text(encoding="utf-8", errors="ignore"))
        for p in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"):
            if Path(p).exists():
                out["edge"] = True
        try:
            import playwright  # noqa: F401
            out["playwright"] = True
        except ImportError:
            pass
        return out

    # ---------- 작업 상태 저장/복원 ----------
    def _state_path(self, folder: str) -> Path:
        return self._work_dir / (re.sub(r'[^\w가-힣]+', '', Path(folder).name) + ".상태.json")

    def load_state(self, folder: str) -> dict:
        p = self._state_path(folder)
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                return {}
        return {}

    def save_state(self, folder: str, patch: dict) -> dict:
        """단계별 결과를 병합 저장. patch 예: {"convert": {"out": "...", "flags": 350}} → done_at 자동 기록."""
        import datetime
        self._work_dir.mkdir(parents=True, exist_ok=True)
        st = self.load_state(folder)
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        for k, v in patch.items():
            if isinstance(v, dict):
                v = {**st.get(k, {}), **v, "done_at": v.get("done_at", now)}
            st[k] = v
        st["folder"] = folder; st["updated"] = now
        self._state_path(folder).write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
        self._touch_recent(folder, st.get("title", ""))
        return st

    def _touch_recent(self, folder: str, title: str):
        import datetime
        p = self._work_dir / "recent.json"
        items = []
        if p.exists():
            try:
                items = json.loads(p.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                items = []
        items = [i for i in items if i.get("folder") != folder]
        items.insert(0, {"folder": folder, "title": title, "when": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")})
        p.write_text(json.dumps(items[:15], ensure_ascii=False, indent=1), encoding="utf-8")

    def recent(self) -> list:
        p = self._work_dir / "recent.json"
        if not p.exists():
            return []
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return []

    # ---------- 1. 납품 폴더 → 반입용 엑셀 (에이전트가 한 번에) ----------
    def open_folder(self, folder: str) -> dict:
        """폴더를 고르면 지난 작업이 있는지 보고 되살린다. 에이전트는 돌리지 않는다."""
        from . import prepare
        f = Path(folder)
        if not f.is_dir():
            return {"error": f"폴더 없음: {folder}"}
        w = prepare.load(f, self._work_dir)
        st = self.load_state(str(f))
        self._touch_recent(str(f), (w or {}).get("title") or st.get("title", ""))
        lp = self._log_path(str(f))
        try:
            log = json.loads(lp.read_text(encoding="utf-8")) if lp.exists() else []
        except Exception:  # noqa: BLE001
            log = []
        return {"folder": str(f), "work": self._view(w) if w else None, "state": st, "log": log}

    def _log_path(self, folder: str) -> Path:
        return self._work_dir / (re.sub(r'[^\w가-힣]+', '', Path(folder).name) + ".로그.json")

    def log_save(self, folder: str, lines: list) -> bool:
        """그 작품 탭의 로그를 남긴다(프로그램을 다시 띄워도 보이게)."""
        self._work_dir.mkdir(parents=True, exist_ok=True)
        self._log_path(folder).write_text(json.dumps(lines, ensure_ascii=False), encoding="utf-8")
        return True

    def prepare(self, tab: str, folder: str, instructions: str = "", batch_note: str = "", out_name: str = "") -> dict:
        """실행 버튼: 읽기 → 조사 → 값 결정 → 반입용 엑셀 → 검사 → 검수. 끝나면 onDone('prepare', 결과, 탭).
        여러 작품을 동시에 돌릴 수 있다. 동시 실행 한도를 넘으면 자리가 날 때까지 기다린다."""
        import time
        from . import prepare
        from .agent import Cancelled
        f = Path(folder)
        if not f.is_dir():
            return {"error": f"폴더 없음: {folder}"}
        self._names[tab] = self._names.get(tab) or f.name
        out = None if not out_name else (Path(out_name) if Path(out_name).is_absolute() else self._work_dir / out_name)
        handle = self._jobs[tab] = {"cancel": False}
        log = self._tab_log(tab)
        def job():
            got = self._agents.acquire(blocking=False)
            if not got:
                log(f"다른 작품 {MAX_AGENTS}개가 작업 중이라 기다립니다(동시 실행 한도 {MAX_AGENTS}개). 자리가 나면 시작합니다.")
                while not got:
                    if handle.get("cancel"):
                        raise Cancelled("대기 중 중단")
                    got = self._agents.acquire(timeout=1)
                log("자리가 나서 시작합니다.")
            try:
                r = prepare.run(f, self._work_dir, out, instructions, batch_note, log, handle)
                self._names[tab] = r.get("title") or self._names[tab]
                self.save_state(str(f), {"title": r.get("title") or "", "memo": instructions,
                                         "prepare": {"out": r["output_xlsx"], "rows": r["rows"], "confirm": r["confirm_cells"],
                                                     "instructions": instructions, "batch_note": batch_note}})
                return self._view(r)
            finally:
                self._agents.release()
                self._jobs.pop(tab, None)
        return self._run("prepare", job, tab=tab)

    def output_name(self, title: str, batch_note: str) -> str:
        """작업 번호와 제목으로 만든 반입용 엑셀 파일명(관행)."""
        from . import prepare
        return prepare.output_name(title, batch_note)

    def rename_output(self, folder: str, new_name: str) -> dict:
        """만들어 둔 반입용 엑셀의 파일명(또는 위치)을 바꾼다."""
        from . import prepare
        f = Path(folder)
        w = prepare.load(f, self._work_dir)
        if not w or not Path(w.get("output_xlsx", "")).exists():
            return {"error": "바꿀 반입용 엑셀이 없습니다(먼저 실행하세요)"}
        new_name = (new_name or "").strip()
        if not new_name:
            return {"error": "파일명이 비어 있습니다"}
        old = Path(w["output_xlsx"])
        new = Path(new_name) if Path(new_name).is_absolute() else old.parent / new_name
        if new.suffix.lower() != ".xlsx":
            new = new.with_name(new.name + ".xlsx")
        if re.search(r'[\\/:*?"<>|]', new.name):
            return {"error": "파일명에 쓸 수 없는 글자가 있습니다: \\ / : * ? \" < > |"}
        if new == old:
            return {"out": str(old)}
        if new.exists():
            return {"error": f"같은 이름의 파일이 이미 있습니다: {new.name}"}
        try:
            new.parent.mkdir(parents=True, exist_ok=True)
            old.rename(new)
        except OSError as e:
            return {"error": f"이름을 바꾸지 못했습니다(엑셀에서 열려 있으면 닫으세요): {e}"}
        w["output_xlsx"] = str(new)
        prepare.result_path(f, self._work_dir).write_text(json.dumps(w, ensure_ascii=False, indent=1), encoding="utf-8")
        self.save_state(str(f), {"prepare": {"out": str(new)}})
        return {"out": str(new)}

    def undo_files(self, folder: str) -> dict:
        """마무리에서 바꾼 원고·썸네일 파일명을 되돌린다."""
        from . import prepare
        w = prepare.load(Path(folder), self._work_dir)
        if not w:
            return {"error": "이 폴더의 작업 기록이 없습니다"}
        try:
            return prepare.undo(Path(folder), w["import"])
        except Exception as e:  # noqa: BLE001
            return {"error": "".join(traceback.format_exception_only(type(e), e)).strip()}

    def confirm_import(self, folder: str) -> dict:
        """반입 전 확인 완료(사람 판정 지점): 직원이 반입용 엑셀을 다 봤다는 표시. 엑셀의 노란색·메모를 지우고 기록한다. 이걸 눌러야 KOLIS 등록을 할 수 있다."""
        import datetime
        from . import prepare, import_writer
        f = Path(folder)
        w = prepare.load(f, self._work_dir)
        if not w or not w.get("output_xlsx"):
            return {"error": "반입용 엑셀이 없습니다. 1단계를 먼저 실행하세요"}
        x = Path(w["output_xlsx"])
        if not x.is_file():
            return {"error": f"반입용 엑셀이 없습니다: {x}"}
        try:
            n = import_writer.clear_marks(x)
        except PermissionError:
            return {"error": "반입용 엑셀이 열려 있어 고칠 수 없습니다. 엑셀에서 저장하고 닫은 뒤 다시 누르세요"}
        except Exception as e:  # noqa: BLE001
            return {"error": "".join(traceback.format_exception_only(type(e), e)).strip()}
        w["confirmed"] = {"at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "cleared": n, "mtime": x.stat().st_mtime}
        prepare.result_path(f, self._work_dir).write_text(json.dumps(w, ensure_ascii=False, indent=1), encoding="utf-8")
        return self._view(w)

    def get_prompt(self) -> dict:
        """모든 작품에 적용할 직원 지시(편집 가능)와 에이전트가 따르는 방법 문서(보기 전용)."""
        from . import agent
        p = self._work_dir / "research_prompt.txt"
        skills = agent.HOME_SRC / ".claude" / "skills"
        full = "\n\n".join((skills / n / "SKILL.md").read_text(encoding="utf-8") for n in ("prepare-import", "research-work"))
        return {"text": p.read_text(encoding="utf-8") if p.exists() else "", "is_default": not p.exists(), "full": full}

    def save_prompt(self, text: str) -> dict:
        p = self._work_dir / "research_prompt.txt"
        if text and text.strip():
            p.parent.mkdir(parents=True, exist_ok=True); p.write_text(text, encoding="utf-8")
        elif p.exists():
            p.unlink()
        return {"ok": True, "is_default": not p.exists(), "text": text if p.exists() else ""}

    def cancel(self, tab: str) -> dict:
        j = self._jobs.get(tab)
        if not j:
            return {"ok": False}
        j["cancel"] = True
        p = j.get("proc")
        if p and p.poll() is None:
            p.kill()
        self._tab_log(tab)("중단 요청…")
        return {"ok": True}

    @staticmethod
    def _view(w: dict) -> dict:
        """화면에 보여 줄 요약: 값 표, 사람이 확인할 칸, 엇갈림, 찾지 못한 값, 검수."""
        from . import import_writer
        imp, res = w.get("import") or {}, w.get("research") or {}
        rows = imp.get("rows") or []
        v0 = (rows[0].get("values") or {}) if rows else {}
        names = "; ".join(f"{n.get('role') or ''}: {n.get('name')}".strip(": ") for n in v0.get("names") or [])
        dates = [str((r.get("values") or {}).get("dateIssued") or "") for r in rows]
        summary = [
            ["작품 / 건수", f"{imp.get('title') or ''} / {len(rows)}{imp.get('unit') or '건'}", ""],
            ["표제", v0.get("title", ""), ""],
            ["권차", ", ".join(str((r.get("values") or {}).get("partNumber") or "") for r in rows[:12]) + (" …" if len(rows) > 12 else ""), ""],
            ["저자", names, ""],
            ["발행처 / 발행지", f"{v0.get('publisher', '')} / {v0.get('place', '')} {v0.get('place_code', '')}", ""],
            ["발행일", f"{min(d for d in dates if d)} ~ {max(dates)}" if any(dates) else "", f"{sum(1 for d in dates if d)}/{len(rows)}건"],
            ["최초 연재 플랫폼", res.get("platform_first", ""), res.get("platform_first_reason", "")],
            ["이용대상", f"{v0.get('targetAudience', '')} / {v0.get('audience_note', '')}", ""],
            ["정가 / 보상", f"{v0.get('price', '')} / {v0.get('reward_yn', '')} {v0.get('compensation', '')}", ""],
            ["원문주소", v0.get("url_work", ""), ""],
            ["썸네일", "있음" if imp.get("thumbs_dir") else "없음(등록하지 않음)", ""],
        ]
        confirm = []
        for r in rows:
            for c in r.get("confirm") or []:
                v = r.get("values") or {}
                name = str(c.get("field"))
                special = {"names": "; ".join(f"{n.get('name')} ({n.get('type') or ''}, {n.get('role') or '역할 없음'})" for n in v.get("names") or []), "thumb_file": r.get("thumb_file")}
                val = special[name] if name in special else v.get(name)
                part = " ".join(str(v.get(k) or "") for k in ("partNumber", "partName")).strip()
                confirm.append({"no": r.get("no"), "part": part, "value": "(빈칸)" if val in (None, "") else str(val), "field": import_writer.column_label(name),
                                "reason": c.get("reason"), "ask": c.get("ask") or "", "evidence": c.get("evidence") or "", "publisher_says": c.get("publisher_says") or ""})
        grouped: dict = {}
        for c in confirm:      # 같은 칸·같은 내용은 행을 모아 한 묶음으로
            grouped.setdefault((c["field"], c["reason"], c["ask"], c["evidence"]), []).append(c)
        rv = imp.get("review") or {}
        return {"folder": w.get("folder"), "title": imp.get("title"), "output_xlsx": w.get("output_xlsx"), "rows": w.get("rows"), "confirmed": w.get("confirmed"),
                "confirm_cells": w.get("confirm_cells"), "manuscripts": w.get("manuscripts"), "thumbs": w.get("thumbs"),
                "summary": summary,
                "confirm": [{"field": k[0], "reason": k[1], "ask": k[2], "evidence": k[3], "rows": [c["no"] for c in v],
                             "publisher_says": (lambda ps: ps[0] if len(ps) == 1 else " / ".join(ps[:3]) + (f" … ({len(ps)}가지)" if len(ps) > 3 else ""))(list(dict.fromkeys(c["publisher_says"] for c in v if c["publisher_says"])) or [""]),
                             "parts": [c["part"] for c in v], "values": list(dict.fromkeys(c["value"] for c in v))} for k, v in grouped.items()],
                "conflicts": res.get("conflicts") or [], "not_found": res.get("not_found") or [], "issues": imp.get("issues") or [],
                "review": {"done": bool(rv.get("done")), "findings": rv.get("findings") or [], "resolved": rv.get("resolved") or []},
                "remaining": w.get("remaining") or [], "finalize": w.get("finalize") or {}, "run": w.get("run") or {},
                "platforms": [{"name": p.get("name"), "status": p.get("status"), "start_date": p.get("start_date"), "url": p.get("url_work")} for p in res.get("platforms") or []],
                "searched": len(res.get("searched") or [])}

    # ---------- 2. KOLIS 등록 전체(반입 → 원문 → 가원부번호)를 한 번에, 브라우저 없이 ----------
    def flow_run(self, tab: str, folder: str, note: str, yes: str) -> dict:
        """반입용 엑셀 확인(사람) 뒤의 KOLIS 단계를 처음부터 끝까지. 매번 새로 반입한다(지난 접수번호는 취소 요청 목록에 남는다)."""
        from . import kolis_flow, prepare
        w = prepare.load(Path(folder), self._work_dir) or {}
        if not w.get("output_xlsx"):
            return {"error": "반입용 엑셀이 없습니다. 1단계를 먼저 실행하세요"}
        if not w.get("confirmed"):
            return {"error": "반입용 엑셀 확인이 끝나지 않았습니다. 1번 결과의 '확인 완료' 버튼을 먼저 누르세요"}
        from . import kolis_http
        if not kolis_http.source():
            return {"error": "KOLIS 계정이 없습니다. 창 위쪽에서 KOLIS 아이디와 비밀번호로 로그인하세요"}
        handle = self._jobs[tab] = {"cancel": False}
        def send(fn, *args):
            if self._window:
                self._window.evaluate_js(f"{fn}({', '.join(json.dumps(a, ensure_ascii=False) for a in args)})")
        def save(patch):
            st = self.load_state(folder)
            gone = [k for k, v in patch.items() if v is None]
            if gone:
                for k in gone:
                    st.pop(k, None)
                self._state_path(folder).write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
            keep = {k: v for k, v in patch.items() if v is not None}
            if keep:
                self.save_state(folder, keep)
        def job():
            try:
                return kolis_flow.run(w, note.strip(), yes, self._work_dir, self._kolis_log(tab), handle,
                                      lambda key, status, text="": send("onFlowStep", key, status, text, tab),
                                      lambda i, r: send("onThumbProgress", {"i": i, **r}, tab), save)
            except kolis_flow.Stop as e:
                raise SystemExit(str(e)) from e
            finally:
                self._jobs.pop(tab, None)
        # 브라우저를 쓰지 않으므로 KOLIS 창 잠금을 걸지 않고 프로그램 창도 내리지 않는다(여러 작품 동시 실행 가능). 썸네일이 있는 납품만 Edge 를 쓴다
        return self._run("flow", job, tab=tab, screen=bool(w.get("thumbs")))

    def flow_ledger(self) -> dict:
        """실행한 접수번호 목록(work/취소요청_목록.csv). 처리 = 유지 / 취소 요청."""
        from . import kolis_flow
        return {"file": str(self._work_dir / kolis_flow.LEDGER), "rows": kolis_flow.ledger_read(self._work_dir)}

    def flow_steps(self) -> list:
        from . import kolis_flow
        return [list(s) for s in kolis_flow.STEPS]

    # ---------- 5. KOLIS 일괄반입 준비 (직원 입회) ----------
    def kolis_prepare(self, tab: str, xlsx: str, note: str) -> dict:
        """로그인된 Edge(IE 모드)에서 납본자료접수 → 일괄반입 → 확인 → 비고·첨부까지. '반입'은 누르지 않는다."""
        from . import kolis_ui
        return self._run("kolis", lambda: kolis_ui.prepare_batch_import(note, Path(xlsx), self._kolis_log(tab)), capture=True, tab=tab)

    def kolis_submit(self, tab: str, yes: str) -> dict:
        """'반입' 클릭. 화면에서 YES 를 입력받아 넘긴다(직원 동의)."""
        from . import kolis_ui
        try:
            pop = kolis_ui.popup_window()
            if not pop:
                return {"error": "일괄반입 팝업이 열려 있지 않습니다"}
        except Exception as e:  # noqa: BLE001
            return {"error": str(e)}
        return self._run("kolis_submit", lambda: kolis_ui.submit(pop, yes, self._kolis_log(tab)), capture=True, tab=tab)

    # ---------- 6. 반입 결과 → 폴더명 CNTS ----------
    def export_download(self, tab: str, receipt: str = "", mode: str = "screen") -> dict:
        """KOLIS 로 이동 → (접수번호 찾기) → '전체출력' → 알림 막대 '저장' → work/접수번호 N.xls. 스레드, 끝나면 onDone('export').
        mode=request: 화면을 누르지 않고 목록 요청으로 같은 표를 받는다(읽기만 함, 접수번호 필수)."""
        from . import kolis_ui
        if mode == "request":
            from . import kolis_request
            import datetime
            def job():
                try:
                    return kolis_request.export_receipt(kolis_request.Page(), str(datetime.date.today().year), receipt.strip(), self._work_dir, self._kolis_log(tab))
                except kolis_request.Stop as e:
                    raise SystemExit(str(e)) from e
            if not receipt.strip():
                return {"error": "요청 방식은 접수번호가 필요합니다"}
            return self._run("export", job, tab=tab, screen=False)
        return self._run("export", lambda: kolis_ui.download_export(self._kolis_log(tab), self._work_dir, receipt), capture=True, tab=tab)

    def cnts_preview(self, export_file: str, root: str) -> dict:
        from .cnts_folders import plan
        try:
            p = plan(Path(export_file), Path(root))
            return {**p, "pairs": p["pairs"][:3] + ([["…", "…", "…"]] if p["count"] > 3 else [])}
        except SystemExit as e:
            return {"error": str(e)}

    def cnts_apply(self, export_file: str, root: str) -> dict:
        from .cnts_folders import apply
        try:
            p = apply(Path(export_file), Path(root))
            return {"receipt": p["receipt"], "count": p["count"]}
        except SystemExit as e:
            return {"error": str(e)}

    def cnts_undo(self, root: str) -> dict:
        from .cnts_folders import undo
        try:
            return {"count": undo(Path(root))}
        except Exception as e:  # noqa: BLE001
            return {"error": str(e)}

    # ---------- 6-나. 원문일괄등록(폴더): 끌어다 놓기는 사람이, 그 뒤는 프로그램이 ----------
    def upload_check(self, root: str) -> dict:
        """로컬 원고 폴더 검사 + 팝업 상태 읽기(클릭 없음)."""
        from . import kolis_upload
        try:
            return {"local": kolis_upload.check_local(Path(root)), "popup": kolis_upload.state()}
        except Exception as e:  # noqa: BLE001
            return {"error": "".join(traceback.format_exception_only(type(e), e)).strip()}

    def upload_open(self, tab: str, receipt: str) -> dict:
        """원문일괄등록(폴더) 팝업 열기: 접수번호 찾기 → 목록 전체 선택 → 버튼 클릭."""
        from . import kolis_upload
        def job():
            try:
                kolis_upload.open_popup(receipt, self._kolis_log(tab))
                return {"opened": True, "popup": kolis_upload.state()}
            except kolis_upload.Stop as e:
                raise SystemExit(str(e)) from e
        return self._run("upload_open", job, capture=True, tab=tab)

    def upload_run(self, tab: str, root: str, yes: str, receipt: str = "") -> dict:
        from . import kolis_upload
        handle = self._jobs[tab] = {"cancel": False}
        def job():
            try:
                return kolis_upload.run(Path(root), self._kolis_log(tab), handle, yes, receipt)
            except kolis_upload.Stop as e:
                raise SystemExit(str(e)) from e
            finally:
                self._jobs.pop(tab, None)
        return self._run("upload", job, capture=True, tab=tab)

    # ---------- 5. 등록대상처리 → 가원부번호 → 등록원부관리 전체출력 ----------
    def register_run(self, tab: str, receipt: str, yes: str, mode: str = "screen") -> dict:
        """mode: screen(화면을 눌러서) / request(로그인된 KOLIS 화면 안에서 요청만 보냄 — 여러 작품을 동시에 할 수 있다)."""
        from . import kolis_register, kolis_request
        import datetime
        handle = self._jobs[tab] = {"cancel": False}
        request = mode == "request"
        def job():
            try:
                if request:
                    return kolis_request.run(receipt, str(datetime.date.today().year), self._work_dir, self._kolis_log(tab), handle, yes)
                return kolis_register.run(receipt, self._work_dir, self._kolis_log(tab), handle, yes)
            except (kolis_register.Stop, kolis_request.Stop) as e:
                raise SystemExit(str(e)) from e
            finally:
                self._jobs.pop(tab, None)
        return self._run("register", job, capture=not request, tab=tab, screen=not request)

    def register_export(self, tab: str, no: str, receipt: str, mode: str = "screen") -> dict:
        """가원부번호가 이미 있을 때: 가원부 파일만 다시 받는다(KOLIS 의 자료를 바꾸지 않음)."""
        from . import kolis_register, kolis_request
        import datetime
        request = mode == "request"
        num = no.split("-")[-1].strip()
        year = no.split("-")[0].strip() if "-" in no else str(datetime.date.today().year)
        def job():
            try:
                if request:
                    return kolis_request.export_record(kolis_request.Page(), year, num, receipt, self._work_dir, self._kolis_log(tab))
                return kolis_register.export_record(num, receipt, "", self._work_dir, self._kolis_log(tab))
            except (kolis_register.Stop, kolis_request.Stop) as e:
                raise SystemExit(str(e)) from e
        return self._run("register_export", job, capture=not request, tab=tab, screen=not request)

    # ---------- 4. 썸네일 등록 반복 ----------
    def thumbs_register(self, tab: str, import_xlsx: str, thumb_dir: str, count: int = 0, receipt: str = "") -> dict:
        from . import kolis_thumbs
        handle = self._jobs[tab] = {"cancel": False}
        def prog(i, r):
            if self._window:
                self._window.evaluate_js(f"onThumbProgress({json.dumps({'i': i, **r}, ensure_ascii=False)}, {json.dumps(tab)})")
        def job():
            try:
                return kolis_thumbs.run(Path(import_xlsx), Path(thumb_dir), int(count or 0), self._kolis_log(tab), handle, prog, receipt)
            finally:
                self._jobs.pop(tab, None)
        return self._run("thumbs_register", job, capture=True, tab=tab)

    def open_path(self, path: str) -> bool:
        import os
        os.startfile(path)  # noqa: S606
        return True


def main():
    api = Api()
    window = webview.create_window("KOLIS 웹툰 납본 도우미", str(HERE / "ui" / "index.html"), js_api=api, width=1280, height=900, text_select=True)
    api._window = window
    webview.start(debug=False)


if __name__ == "__main__":
    main()
