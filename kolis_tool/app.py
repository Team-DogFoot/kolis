"""창 하나짜리 실행 프로그램 (pywebview). 기능은 하나씩 붙인다.  실행: python -m kolis_tool.app

화면(kolis_tool/ui/index.html)은 아래 Api 의 메서드를 window.pywebview.api.<이름>() 으로 부른다.
오래 걸리는 작업(웹 리서치)은 스레드로 돌리고 진행 로그를 화면에 밀어 넣는다(evaluate_js).
KOLIS 에는 접근하지 않는다.
"""
from __future__ import annotations
import json, re, threading, traceback
from pathlib import Path
import webview

HERE = Path(__file__).parent
TEMPLATE_83 = HERE / "templates" / "import_template_83.xlsx"


class Api:
    def __init__(self):
        self._window: webview.Window | None = None
        self._work_dir = Path("work").resolve()

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

    # ---------- 1. 작품 폴더 읽기 ----------
    def scan_folder(self, folder: str) -> dict:
        """납품 폴더 구조 파악: 기초메타데이터 xlsx, 원고 폴더(회차 하위폴더), 회차썸네일 폴더."""
        from .enrich import read_sheet
        from .common import list_images
        f = Path(folder)
        if not f.is_dir():
            return {"error": f"폴더 없음: {folder}"}
        xlsx = [p for p in f.glob("*.xlsx") if "기초메타데이터" in p.name and "반입용" not in p.name and not p.name.startswith("~$")]
        manuscripts = next((p for p in f.iterdir() if p.is_dir() and p.name in ("원고", "원문")), None)
        thumbs = next((p for p in f.iterdir() if p.is_dir() and "썸네일" in p.name), None)
        info = {"folder": str(f), "xlsx": str(xlsx[0]) if xlsx else "", "manuscripts": str(manuscripts) if manuscripts else "",
                "thumbs": str(thumbs) if thumbs else "", "episodes": 0, "images": 0, "thumb_files": 0, "rows": 0, "title": "", "empty_cols": []}
        if manuscripts:
            eps = [p for p in manuscripts.iterdir() if p.is_dir()]
            info["episodes"] = len(eps); info["images"] = sum(len(list_images(p)) for p in eps)
        if thumbs:
            info["thumb_files"] = len(list_images(thumbs))
        if xlsx:
            wb, ws, col, rows = read_sheet(xlsx[0])
            info["rows"] = len(rows)
            info["title"] = str(ws.cell(row=rows[0], column=col["제목(도서명)"]).value or "") if rows else ""
            empties = []
            for k, c in col.items():
                if k in ("No",):
                    continue
                if all(ws.cell(row=r, column=c).value in (None, "") for r in rows):
                    empties.append(k)
            info["empty_cols"] = empties
        return info

    # ---------- 2. 기초메타데이터 보완 ----------
    def enrich(self, xlsx: str, use_saved: bool = True, use_platforms: bool = True, runner: str = "claude") -> dict:
        from .enrich import research, apply, read_sheet
        src = Path(xlsx)
        out = self._work_dir / f"{re.sub(r'[^\w가-힣]+', '', src.stem)}_보완.xlsx"
        jpath = out.with_suffix(".work.json")

        def job():
            try:
                self._work_dir.mkdir(parents=True, exist_ok=True)
                if use_saved and jpath.exists():
                    info = json.loads(jpath.read_text(encoding="utf-8"))
                    self._log(f"저장된 작품 정보 재사용: {jpath}")
                else:
                    self._log(f"웹 리서치 시작({runner} -p 헤드리스, 보통 3~6분). KOLIS 접근 없음.")
                    info = research(src, jpath, runner)
                    self._log(f"작품 정보 JSON 저장: {jpath}")
                if use_platforms and not info.get("_platforms_done"):
                    from .platforms import gather, merge_into
                    wb, ws, col, rows = read_sheet(src)
                    title = str(ws.cell(row=rows[0], column=col["제목(도서명)"]).value or "")
                    known = {p.get("name", ""): p.get("url_work", "") for p in info.get("platforms", []) if p.get("url_work")}
                    self._log("플랫폼 페이지에서 회차별 공개일·가격 수집 시작(Edge 헤드리스)")
                    info = merge_into(info, gather(title, known, self._log))
                    info["_platforms_done"] = True
                    jpath.write_text(json.dumps({k: v for k, v in info.items() if k != "_raw"}, ensure_ascii=False, indent=1), encoding="utf-8")
                filled = apply(src, info, out)
                self._log("채운 칸: " + (", ".join(f"{k} {v}" for k, v in filled.items()) or "없음"))
                self._done("enrich", {"out": str(out), "json": str(jpath), "filled": filled, "info": {k: v for k, v in info.items() if k != "_raw"}})
            except Exception as e:  # noqa: BLE001
                self._log("오류: " + "".join(traceback.format_exception_only(type(e), e)).strip())
                self._done("enrich", {"error": str(e)})
        threading.Thread(target=job, daemon=True).start()
        return {"started": True, "out": str(out)}

    # ---------- 3. 썸네일 파일명 ----------
    def thumbs_preview(self, folder: str, title: str) -> list:
        from .enrich import rename_thumbs
        return rename_thumbs(Path(folder), title, dry_run=True)

    def thumbs_apply(self, folder: str, title: str) -> dict:
        from .enrich import rename_thumbs
        try:
            pairs = rename_thumbs(Path(folder), title)
            return {"count": len(pairs)}
        except SystemExit as e:
            return {"error": str(e)}

    def thumbs_undo(self, folder: str) -> dict:
        from .enrich import undo_thumbs
        return {"count": undo_thumbs(Path(folder))}

    # ---------- 4. 반입용 엑셀 ----------
    def convert(self, pub_xlsx: str, root: str, work_json: str, out_name: str, template: str = "") -> dict:
        from .convert_import import convert
        out = self._work_dir / out_name
        self._work_dir.mkdir(parents=True, exist_ok=True)
        try:
            n, flags = convert(Path(pub_xlsx), Path(template) if template else TEMPLATE_83, out,
                               Path(root) if root else None, None, Path(work_json) if work_json else None)
            return {"out": str(out), "rows": n, "flags": flags}
        except Exception as e:  # noqa: BLE001
            return {"error": "".join(traceback.format_exception_only(type(e), e)).strip()}

    def open_path(self, path: str) -> bool:
        import os
        os.startfile(path)  # noqa: S606
        return True


def main():
    api = Api()
    window = webview.create_window("KOLIS 웹툰 납본 도우미", str(HERE / "ui" / "index.html"), js_api=api, width=1100, height=820, text_select=True)
    api._window = window
    webview.start(debug=False)


if __name__ == "__main__":
    main()
