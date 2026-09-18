"""창 하나짜리 실행 프로그램 (pywebview). 기능은 하나씩 붙인다.  실행: bin\\app.vbs (콘솔 없음) 또는 python -m kolis_tool.app

화면(kolis_tool/ui/index.html)은 아래 Api 의 메서드를 window.pywebview.api.<이름>() 으로 부른다.
오래 걸리는 작업(웹 리서치·플랫폼 수집)은 스레드로 돌리고 진행 로그를 화면에 밀어 넣는다(evaluate_js). 둘은 서로 독립이라 동시에 돈다.
KOLIS 에는 접근하지 않는다.
"""
from __future__ import annotations
import json, re, shutil, threading, traceback
from pathlib import Path
import webview

HERE = Path(__file__).parent
TEMPLATE_83 = HERE / "templates" / "import_template_83.xlsx"


class Api:
    def __init__(self):
        self._window: webview.Window | None = None
        self._work_dir = Path("work").resolve()
        self._job: dict = {}          # {'proc': Popen, 'cancel': bool}
        self._running: dict = {}      # kind → 시작 시각(진행 중인 스레드 작업)
        from .logutil import UiLog
        self.log = UiLog(self._ui_log, "kolis.app")

    # ---------- 공통 ----------
    def _ui_log(self, msg: str):
        if self._window:
            self._window.evaluate_js(f"appendLog({json.dumps(str(msg), ensure_ascii=False)})")

    def _log(self, msg: str):
        """화면 + 파일 로그(work/logs/app-날짜.log)."""
        self.log(msg)

    def _done(self, kind: str, payload: dict):
        if self._window:
            self._window.evaluate_js(f"onDone({json.dumps(kind)}, {json.dumps(payload, ensure_ascii=False, default=str)})")

    def _run(self, kind: str, fn, capture: bool = False) -> dict:
        """스레드 작업 공통 틀: 시작·종료·소요시간·예외 스택을 파일에 남기고 onDone(kind, 결과)로 알린다.
        fn() 은 결과 dict 를 돌려준다. Cancelled → {'cancelled': True}, 그 밖의 예외 → {'error': 문구}.
        capture=True(KOLIS 조작)면 실패 시 화면 캡처·창 목록을 저장한다."""
        import datetime, time
        from .enrich import Cancelled
        if kind in self._running:
            return {"error": f"'{kind}' 작업이 이미 진행 중입니다({self._running[kind]} 시작)"}
        def job():
            t0 = time.time()
            self._running[kind] = datetime.datetime.now().strftime("%H:%M:%S")
            self.log.debug(f"[{kind}] 시작")
            try:
                r = fn()
                self.log.debug(f"[{kind}] 완료 {time.time() - t0:.1f}초: {json.dumps(r, ensure_ascii=False, default=str)[:300]}")
                self._done(kind, r if isinstance(r, dict) else {"result": r})
            except Cancelled:
                self.log(f"[{kind}] 중단됨"); self._done(kind, {"cancelled": True})
            except SystemExit as e:
                self.log.error(f"[{kind}] {e}"); self._done(kind, {"error": str(e)})
            except Exception as e:  # noqa: BLE001
                self.log.exception(f"[{kind}] 실패 ({time.time() - t0:.1f}초)", e)
                msg = "".join(traceback.format_exception_only(type(e), e)).strip()
                if capture:
                    try:
                        from . import kolis_ui
                        cap = kolis_ui.capture_failure(kolis_ui.Log(self._ui_log), f"{kind}: {msg}")
                        if cap.get("shot"):
                            msg += f"  [캡처: {Path(cap['shot']).name}]"
                    except Exception:  # noqa: BLE001
                        pass
                self._done(kind, {"error": msg})
            finally:
                self._running.pop(kind, None)
        threading.Thread(target=job, daemon=True, name=f"job-{kind}").start()
        return {"started": True}

    def diagnose(self) -> dict:
        """진단: 환경, 진행 중 작업, KOLIS 창 상태(Edge·팝업·대화상자), 최근 로그."""
        from .logutil import tail, log_path
        out = {"env": self.check_env(), "running": dict(self._running), "log_path": str(log_path()), "log_tail": tail(40), "kolis": {}}
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
        """작품별 단계 현황: 파일 증거 + 상태 기록을 합쳐 단계마다 done/evidence/when."""
        from .rename_files import is_done as _rd
        from .enrich import thumbs_done
        from .common import find_manifest, list_images
        f = Path(folder); st = self.load_state(folder)
        steps = []
        def add(key, label, done, evidence="", when=""):
            steps.append({"key": key, "label": label, "done": bool(done), "evidence": evidence, "when": when or (st.get(key) or {}).get("done_at", "")})
        ms = next((p for p in f.iterdir() if p.is_dir() and p.name in ("원고", "원문")), None) if f.is_dir() else None
        th = next((p for p in f.iterdir() if p.is_dir() and "썸네일" in p.name), None) if f.is_dir() else None
        eps = [p for p in ms.iterdir() if p.is_dir()] if ms else []
        import re as _re
        def eight(p):   # 도구 기록이 없어도(직원 도구로 바꾼 경우) 파일이 전부 8자리 숫자면 완료로 본다
            imgs = list_images(p)
            return bool(imgs) and all(_re.fullmatch(r"\d{8}", q.stem) for q in imgs)
        n_ok = sum(1 for p in eps if _rd(p) or eight(p))
        add("manuscript", "원고 파일명", eps and n_ok == len(eps), f"{n_ok}/{len(eps)} 폴더")
        add("thumbs", "썸네일 파일명", th and thumbs_done(th), th.name if th else "썸네일 폴더 없음")
        xlsx = [p for p in f.glob("*.xlsx") if "기초메타데이터" in p.name and "반입용" not in p.name] if f.is_dir() else []
        en = self._paths(xlsx[0]) if xlsx else (None, None)
        add("enrich", "기초메타데이터 보완", en[0] and en[0].exists(), str(en[0]) if en[0] and en[0].exists() else "")
        cv = (st.get("convert") or {}).get("out", "")
        add("convert", "반입용 엑셀", cv and Path(cv).exists(), cv)
        add("kolis_submit", "KOLIS 반입", bool(st.get("kolis_submit")), (st.get("kolis_submit") or {}).get("message", ""))
        ex = (st.get("export") or {})
        add("export", "전체출력", ex.get("file") and Path(ex["file"]).exists(), f"접수번호 {ex.get('receipt', '')} {ex.get('count', '')}건" if ex else "")
        add("cnts", "폴더명 CNTS", ms and find_manifest(ms, "cnts", "cnts_manifest.json") is not None and eps and all(p.name.startswith("CNTS-") for p in eps),
            f"{sum(1 for p in eps if p.name.startswith('CNTS-'))}/{len(eps)} 폴더")
        warns = []
        if ex.get("count") and (st.get("convert") or {}).get("rows") and int(ex["count"]) != int(st["convert"]["rows"]):
            warns.append(f"반입 건수 {ex['count']} ≠ 반입용 행 수 {st['convert']['rows']}")
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

    def check_env(self) -> dict:
        """시작 시 전제 조건: 클로드코드 설치·로그인 흔적, Edge, Playwright."""
        from .enrich import claude_exe
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

    # ---------- 1. 작품 폴더 읽기 ----------
    def scan_folder_async(self, folder: str) -> dict:
        """폴더 읽기를 스레드로(원고 수백 장 세는 데 몇 초). 끝나면 onDone('scan', 결과)."""
        return self._run("scan", lambda: self.scan_folder(folder))

    def scan_folder(self, folder: str) -> dict:
        from .enrich import read_sheet
        from .common import list_images
        f = Path(folder)
        if not f.is_dir():
            return {"error": f"폴더 없음: {folder}"}
        xlsx = [p for p in f.glob("*.xlsx") if "기초메타데이터" in p.name and "반입용" not in p.name and not p.name.startswith("~$")]
        manuscripts = next((p for p in f.iterdir() if p.is_dir() and p.name in ("원고", "원문")), None)
        thumbs = next((p for p in f.iterdir() if p.is_dir() and "썸네일" in p.name), None)
        info = {"folder": str(f), "xlsx": str(xlsx[0]) if xlsx else "", "manuscripts": str(manuscripts) if manuscripts else "",
                "thumbs": str(thumbs) if thumbs else "", "episodes": 0, "images": 0, "thumb_files": 0, "rows": 0, "title": "",
                "empty_cols": [], "has_saved": False, "thumbs_done": bool(thumbs and __import__("kolis_tool.enrich", fromlist=["thumbs_done"]).thumbs_done(thumbs))}
        if manuscripts:
            eps = [p for p in manuscripts.iterdir() if p.is_dir()]
            info["episodes"] = len(eps); info["images"] = sum(len(list_images(p)) for p in eps)
            from .rename_files import is_done as _rd; info["manuscripts_done"] = any(_rd(p) for p in eps)
        if thumbs:
            info["thumb_files"] = len(list_images(thumbs))
        if xlsx:
            wb, ws, col, rows = read_sheet(xlsx[0])
            info["rows"] = len(rows)
            info["title"] = str(ws.cell(row=rows[0], column=col["제목(도서명)"]).value or "") if rows else ""
            info["empty_cols"] = [k for k, c in col.items() if k != "No" and all(ws.cell(row=r, column=c).value in (None, "") for r in rows)]
            info["has_saved"] = self._paths(xlsx[0])[1].exists()
        # 작업 상태 복원(파일로 알 수 없는 것: 완료 시각·결과 경로·비고·메모·KOLIS 진행)
        st = self.load_state(str(f))
        if info["title"] and st.get("title") != info["title"]:
            st = self.save_state(str(f), {"title": info["title"]})
        else:
            self._touch_recent(str(f), info["title"])
        info["state"] = st
        return info

    def get_prompt(self) -> dict:
        """고정 부분(역할·KOLIS 금지·출력 형식)은 보여만 주고, '볼 곳·찾을 것' 부분만 편집."""
        from .enrich import current_editable, PROMPT_OVERRIDE, build_prompt
        full = build_prompt("<작품>", "<출판사>", "<ISBN>", "<회차 수>", "<플랫폼 힌트>", "<이용대상 힌트>")
        return {"text": current_editable(), "is_default": not PROMPT_OVERRIDE.exists(), "full": full}

    def save_prompt(self, text: str) -> dict:
        from .enrich import save_editable, PROMPT_OVERRIDE
        try:
            t = save_editable(text)
            return {"ok": True, "is_default": not PROMPT_OVERRIDE.exists(), "text": t}
        except ValueError as e:
            return {"error": str(e)}

    def saved_info(self, xlsx: str) -> dict:
        """이 엑셀에 대한 지난 조사 결과가 있는지, 있으면 언제 것인지."""
        import datetime
        jp = self._paths(Path(xlsx))[1]
        if not jp.exists():
            return {"exists": False}
        ts = datetime.datetime.fromtimestamp(jp.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        try:
            info = json.loads(jp.read_text(encoding="utf-8"))
            summary = f"{info.get('platform_first') or '?'} · 저자 {len(info.get('authors') or [])}명 · 회차 {len(info.get('episodes') or [])}건"
        except Exception:  # noqa: BLE001
            summary = ""
        return {"exists": True, "when": ts, "summary": summary, "path": str(jp)}

    def _paths(self, xlsx: Path) -> tuple[Path, Path]:
        out = self._work_dir / f"{re.sub(r'[^\w가-힣]+', '', Path(xlsx).stem)}_보완.xlsx"
        return out, out.with_suffix(".work.json")

    # ---------- 2. 기초메타데이터 보완 ----------
    def enrich(self, xlsx: str, reuse: bool = False, extra: str = "", runner: str = "claude") -> dict:
        from .enrich import research, apply, read_sheet, Cancelled
        from .platforms import gather, merge_into
        src = Path(xlsx)
        out, jpath = self._paths(src)
        self._job = {"cancel": False}
        handle = self._job

        def job():
            try:
                self._work_dir.mkdir(parents=True, exist_ok=True)
                wb, ws, col, rows = read_sheet(src)
                title = str(ws.cell(row=rows[0], column=col["제목(도서명)"]).value or "")
                if reuse and jpath.exists():
                    info = json.loads(jpath.read_text(encoding="utf-8"))
                    self._log(f"지난 조사 결과 사용: {jpath}")
                else:
                    # 리서치(클로드)와 플랫폼 수집(Edge)은 독립 → 동시에
                    res: dict = {}
                    def t_research():
                        try:
                            res["info"] = research(src, jpath, runner, log=self._log, handle=handle, extra=extra)
                        except BaseException as e:  # noqa: BLE001
                            res["err"] = e
                    def t_platforms():
                        try:
                            res["plat"] = gather(title, {}, self._log, handle=handle)
                        except BaseException as e:  # noqa: BLE001
                            res["perr"] = e
                    self._log("① 클로드 웹 리서치 시작(판단: 플랫폼·저자·등급·소재지·근거)  ② 동시에 Edge 로 플랫폼 회차 수집 시작")
                    a, b = threading.Thread(target=t_research, daemon=True), threading.Thread(target=t_platforms, daemon=True)
                    a.start(); b.start(); a.join(); b.join()
                    if handle.get("cancel"):
                        raise Cancelled("중단됨")
                    if "err" in res:
                        raise res["err"]
                    info = res["info"]
                    if "perr" in res:
                        self._log(f"플랫폼 수집 실패(리서치 결과만 사용): {res['perr']}")
                    else:
                        info = merge_into(info, res["plat"])
                    info["_platforms_done"] = True
                    jpath.write_text(json.dumps({k: v for k, v in info.items() if k != "_raw"}, ensure_ascii=False, indent=1), encoding="utf-8")
                filled = apply(src, info, out)
                self._log("채운 칸: " + (", ".join(f"{k} {v}" for k, v in filled.items()) or "없음"))
                return {"out": str(out), "json": str(jpath), "filled": filled,
                        "info": {k: v for k, v in info.items() if k != "_raw"}, "review": self._review(info, filled)}
            finally:
                self._job = {}
        return self._run("enrich", job)

    def cancel(self) -> dict:
        self._job["cancel"] = True
        p = self._job.get("proc")
        if p and p.poll() is None:
            p.kill()
        self._log("중단 요청…")
        return {"ok": True}

    @staticmethod
    def _review(info: dict, filled: dict) -> dict:
        """화면 검토표: 채운 값·근거, 눈에 띄어야 할 경고."""
        from .enrich import authors_text, price_number
        eps = info.get("episodes") or []
        dated = sum(1 for e in eps if e.get("date"))
        rows = [
            ["최초 연재 플랫폼", info.get("platform_first", ""), ", ".join(p.get("name", "") for p in info.get("platforms", []))],
            ["저자", authors_text(info.get("authors", [])), "역할어: 글/그림/원작/작화/각색만"],
            ["주제 구분(장르)", info.get("genre", ""), ""],
            ["1회차 공개일", info.get("first_publish_date", ""), "가장 이른 플랫폼 기준"],
            ["회차별 공개일", f"{dated}/{len(eps)}건", "없는 회차는 노란 셀"],
            ["정가", price_number(info.get("price_per_episode")), str(info.get("price_per_episode", ""))],
            ["이용등급", info.get("rating", ""), ", ".join(f"{k}={v or '?'}" for k, v in (info.get("rating_by_platform") or {}).items())],
            ["출판사 소재지", info.get("publisher_place", ""), ""],
        ]
        warns = []
        rb = {v for v in (info.get("rating_by_platform") or {}).values() if v}
        if info.get("rating") and rb and len(rb | {info["rating"]}) > 1:
            warns.append("플랫폼마다 이용등급이 다릅니다. 직원 확인 필요.")
        if eps and dated < len(eps):
            warns.append(f"회차 {len(eps) - dated}건은 공개일을 찾지 못했습니다.")
        if not eps:
            warns.append("회차별 공개일을 하나도 찾지 못했습니다(1회차만 채움).")
        if info.get("notes"):
            warns.append("리서치 메모: " + str(info["notes"]))
        return {"rows": rows, "warns": warns, "evidence": info.get("evidence", [])[:8]}

    # ---------- 3-가. 원고 파일명(8자리 일련번호, 다크네이머 대체) ----------
    def manuscript_preview(self, root: str) -> dict:
        from .rename_files import plan, is_done
        from .common import list_images
        r = Path(root)
        folders = [p for p in sorted(r.iterdir()) if p.is_dir() and list_images(p)] or ([r] if list_images(r) else [])
        done = [p.name for p in folders if is_done(p)]
        sample = []
        for p in folders[:2]:
            pairs = plan(p)
            sample.append({"folder": p.name, "count": len(pairs), "first": [(a.name, b.name) for a, b in pairs[:2]], "last": [(a.name, b.name) for a, b in pairs[-1:]]})
        return {"folders": len(folders), "files": sum(len(list_images(p)) for p in folders), "already": done, "sample": sample}

    def manuscript_apply(self, root: str) -> dict:
        """폴더별로 진행 로그를 보내며 스레드에서 실행(파일 수백 장이라 몇 초~수십 초)."""
        from .rename_files import apply, is_done
        from .common import list_images
        r = Path(root)
        def job():
                folders = [p for p in sorted(r.iterdir()) if p.is_dir() and list_images(p)] or ([r] if list_images(r) else [])
                total = len(folders); nfiles = 0; skipped = 0
                for i, p in enumerate(folders, 1):
                    if is_done(p):
                        skipped += 1; self._log(f"  [{i}/{total}] {p.name}: 이미 변경됨, 건너뜀"); continue
                    done = apply(p)
                    nfiles += len(done)
                    if i % 5 == 0 or i == total:
                        self._log(f"  [{i}/{total}] {p.name}: {len(done)}장 변경 (누계 {nfiles}장)")
                return {"folders": total - skipped, "files": nfiles, "skipped": skipped}
        return self._run("manuscript", job)

    def manuscript_undo(self, root: str) -> dict:
        from .rename_files import undo, is_done
        r = Path(root)
        targets = [r] if is_done(r) else [p for p in r.iterdir() if p.is_dir() and is_done(p)]
        n = 0
        for t in targets:
            n += undo(t)
        return {"folders": len(targets), "files": n}

    # ---------- 3-나. 썸네일 파일명 ----------
    def thumbs_preview(self, folder: str, title: str) -> list:
        from .enrich import rename_thumbs
        return rename_thumbs(Path(folder), title, dry_run=True)

    def thumbs_apply(self, folder: str, title: str) -> dict:
        from .enrich import rename_thumbs
        try:
            return {"count": len(rename_thumbs(Path(folder), title))}
        except SystemExit as e:
            return {"error": str(e)}

    def thumbs_undo(self, folder: str) -> dict:
        from .enrich import undo_thumbs
        return {"count": undo_thumbs(Path(folder))}

    # ---------- 4. 반입용 엑셀 ----------
    def convert(self, pub_xlsx: str, root: str, work_json: str, out_name: str, template: str = "") -> dict:
        from .convert_import import convert
        out = Path(out_name) if Path(out_name).is_absolute() else self._work_dir / out_name   # 찾아보기로 고른 전체 경로도 허용
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            from .convert_import import verify
            n, flags = convert(Path(pub_xlsx), Path(template) if template else TEMPLATE_83, out,
                               Path(root) if root else None, None, Path(work_json) if work_json else None)
            v = verify(out, n)
            self.log(f"반입용 생성: {out.name} {n}행, 노란 셀 {flags}" + (" / 경고: " + "; ".join(v["warnings"]) if v["warnings"] else ""))
            return {"out": str(out), "rows": n, "flags": flags, "verify": v}
        except Exception as e:  # noqa: BLE001
            return {"error": "".join(traceback.format_exception_only(type(e), e)).strip()}

    # ---------- 5. KOLIS 일괄반입 준비 (직원 입회) ----------
    def kolis_prepare(self, xlsx: str, note: str) -> dict:
        """로그인된 Edge(IE 모드)에서 납본자료접수 → 일괄반입 → 확인 → 비고·첨부까지. '반입'은 누르지 않는다."""
        from . import kolis_ui
        return self._run("kolis", lambda: kolis_ui.prepare_batch_import(note, Path(xlsx), kolis_ui.Log(self._ui_log)), capture=True)

    def kolis_submit(self, yes: str) -> dict:
        """'반입' 클릭. 화면에서 YES 를 입력받아 넘긴다(직원 동의)."""
        from . import kolis_ui
        try:
            pop = kolis_ui.popup_window()
            if not pop:
                return {"error": "일괄반입 팝업이 열려 있지 않습니다"}
        except Exception as e:  # noqa: BLE001
            return {"error": str(e)}
        return self._run("kolis_submit", lambda: kolis_ui.submit(pop, yes, kolis_ui.Log(self._ui_log)), capture=True)

    # ---------- 6. 반입 결과 → 폴더명 CNTS ----------
    def export_download(self, receipt: str = "") -> dict:
        """KOLIS 로 이동 → (접수번호 찾기) → '전체출력' → 알림 막대 '저장' → work/접수번호 N.xls. 스레드, 끝나면 onDone('export')."""
        from . import kolis_ui
        return self._run("export", lambda: kolis_ui.download_export(kolis_ui.Log(self._ui_log), self._work_dir, receipt), capture=True)

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

    # ---------- 7. 썸네일 등록 반복 ----------
    def thumbs_register(self, import_xlsx: str, thumb_dir: str, count: int = 0) -> dict:
        from . import kolis_thumbs, kolis_ui
        self._job = {"cancel": False}; handle = self._job
        def prog(i, r):
            if self._window:
                self._window.evaluate_js(f"onThumbProgress({json.dumps({'i': i, **r}, ensure_ascii=False)})")
        def job():
            try:
                return kolis_thumbs.run(Path(import_xlsx), Path(thumb_dir), int(count or 0), kolis_ui.Log(self._ui_log), handle, prog)
            finally:
                self._job = {}
        return self._run("thumbs_register", job, capture=True)

    def open_path(self, path: str) -> bool:
        import os
        os.startfile(path)  # noqa: S606
        return True


def main():
    api = Api()
    window = webview.create_window("KOLIS 웹툰 납본 도우미", str(HERE / "ui" / "index.html"), js_api=api, width=1150, height=860, text_select=True)
    api._window = window
    webview.start(debug=False)


if __name__ == "__main__":
    main()
