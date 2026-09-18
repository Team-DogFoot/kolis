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

    # ---------- 공통 ----------
    def _log(self, msg: str):
        if self._window:
            self._window.evaluate_js(f"appendLog({json.dumps(str(msg), ensure_ascii=False)})")

    def _done(self, kind: str, payload: dict):
        if self._window:
            self._window.evaluate_js(f"onDone({json.dumps(kind)}, {json.dumps(payload, ensure_ascii=False, default=str)})")

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
                "empty_cols": [], "has_saved": False, "thumbs_done": bool(thumbs and (thumbs / "thumbs_manifest.json").exists())}
        if manuscripts:
            eps = [p for p in manuscripts.iterdir() if p.is_dir()]
            info["episodes"] = len(eps); info["images"] = sum(len(list_images(p)) for p in eps)
            info["manuscripts_done"] = any((p / "rename_manifest.json").exists() for p in eps)
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
                self._done("enrich", {"out": str(out), "json": str(jpath), "filled": filled,
                                      "info": {k: v for k, v in info.items() if k != "_raw"}, "review": self._review(info, filled)})
            except Cancelled:
                self._log("중단했습니다."); self._done("enrich", {"cancelled": True})
            except SystemExit as e:
                self._log("오류: " + str(e)); self._done("enrich", {"error": str(e)})
            except Exception as e:  # noqa: BLE001
                self._log("오류: " + "".join(traceback.format_exception_only(type(e), e)).strip())
                self._done("enrich", {"error": str(e)})
            finally:
                self._job = {}
        threading.Thread(target=job, daemon=True).start()
        return {"started": True, "out": str(out)}

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
        from .rename_files import plan, MANIFEST
        from .common import list_images
        r = Path(root)
        folders = [p for p in sorted(r.iterdir()) if p.is_dir() and list_images(p)] or ([r] if list_images(r) else [])
        done = [p.name for p in folders if (p / MANIFEST).exists()]
        sample = []
        for p in folders[:2]:
            pairs = plan(p)
            sample.append({"folder": p.name, "count": len(pairs), "first": [(a.name, b.name) for a, b in pairs[:2]], "last": [(a.name, b.name) for a, b in pairs[-1:]]})
        return {"folders": len(folders), "files": sum(len(list_images(p)) for p in folders), "already": done, "sample": sample}

    def manuscript_apply(self, root: str) -> dict:
        """폴더별로 진행 로그를 보내며 스레드에서 실행(파일 수백 장이라 몇 초~수십 초)."""
        from .rename_files import apply, MANIFEST
        from .common import list_images
        r = Path(root)
        def job():
            try:
                folders = [p for p in sorted(r.iterdir()) if p.is_dir() and list_images(p)] or ([r] if list_images(r) else [])
                total = len(folders); nfiles = 0; skipped = 0
                for i, p in enumerate(folders, 1):
                    if (p / MANIFEST).exists():
                        skipped += 1; self._log(f"  [{i}/{total}] {p.name}: 이미 변경됨, 건너뜀"); continue
                    done = apply(p)
                    nfiles += len(done)
                    if i % 5 == 0 or i == total:
                        self._log(f"  [{i}/{total}] {p.name}: {len(done)}장 변경 (누계 {nfiles}장)")
                self._done("manuscript", {"folders": total - skipped, "files": nfiles, "skipped": skipped})
            except Exception as e:  # noqa: BLE001
                self._done("manuscript", {"error": str(e)})
        threading.Thread(target=job, daemon=True).start()
        return {"started": True}

    def manuscript_undo(self, root: str) -> dict:
        from .rename_files import undo, MANIFEST
        r = Path(root)
        targets = [r] if (r / MANIFEST).exists() else [p for p in r.iterdir() if p.is_dir() and (p / MANIFEST).exists()]
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
            n, flags = convert(Path(pub_xlsx), Path(template) if template else TEMPLATE_83, out,
                               Path(root) if root else None, None, Path(work_json) if work_json else None)
            return {"out": str(out), "rows": n, "flags": flags}
        except Exception as e:  # noqa: BLE001
            return {"error": "".join(traceback.format_exception_only(type(e), e)).strip()}

    # ---------- 5. KOLIS 일괄반입 준비 (직원 입회) ----------
    def kolis_prepare(self, xlsx: str, note: str) -> dict:
        """로그인된 Edge(IE 모드)에서 납본자료접수 → 일괄반입 → 확인 → 비고·첨부까지. '반입'은 누르지 않는다."""
        from . import kolis_ui
        def job():
            try:
                self._log("KOLIS 일괄반입 준비 시작(반입 버튼은 누르지 않음)")
                r = kolis_ui.prepare_batch_import(note, Path(xlsx), self._log)
                self._done("kolis", r)
            except Exception as e:  # noqa: BLE001
                self._log("오류: " + "".join(traceback.format_exception_only(type(e), e)).strip())
                self._done("kolis", {"error": str(e)})
        threading.Thread(target=job, daemon=True).start()
        return {"started": True}

    def kolis_submit(self, yes: str) -> dict:
        """'반입' 클릭. 화면에서 YES 를 입력받아 넘긴다(직원 동의)."""
        from . import kolis_ui
        try:
            pop = kolis_ui.popup_window()
            if not pop:
                return {"error": "일괄반입 팝업이 열려 있지 않습니다"}
            kolis_ui.submit(pop, yes, self._log)
            return {"ok": True}
        except Exception as e:  # noqa: BLE001
            return {"error": str(e)}

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
