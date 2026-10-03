"""③구간(구축·점검) 반자동: 유저가 보는 Edge 창에 Playwright 로 붙어 KOLIS 화면을 조작한다(2026-10-03 유저 확정).
- Edge 는 제어 포트(기본 9222)를 연 채 별도 프로필로 띄운다(`bin/edge_kolis.bat`). 떠 있지 않으면 여기서 띄운다.
- 로그인은 프로그램이 그 창에서 계정(.env / 환경변수)으로 한다. 유저가 따로 로그인하지 않는다(세션 겹침 방지).
- 오가는 요청·응답을 전부 기록한다(`work/logs/browser-<시각>.jsonl` 과 Journal). 뒤에 자동(요청 방식)을 만들 때의 근거.
- 저장·실행·완료 같은 바꾸는 버튼은 호출자가 승인(approved=True)을 넘길 때만 누른다. 조회·열기·값 넣기는 그냥 한다.
①구간(kolis_http/kolis_request)은 손대지 않는다. HTTP 조회가 필요하면 이 창의 쿠키를 꺼내 쓴다(cookies()).
"""
from __future__ import annotations
import datetime, json, os, re, subprocess, time, urllib.request
from pathlib import Path

BASE = "http://kolis.nl.go.kr"
PORT = int(os.environ.get("KOLIS_EDGE_PORT", "9222"))
PROFILE = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "kolis_tool" / "edge"
SKIP = (".js", ".css", ".png", ".gif", ".jpg", ".ico", ".woff", "sessionDelay", "StaffGridInfo", "listUserAuthMenu", "crownix")


class NotApproved(Exception):
    """바꾸는 버튼을 승인 없이 누르려 함."""


def _port_open() -> bool:
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version", timeout=2)
        return True
    except Exception:  # noqa: BLE001
        return False


def _edge_exe() -> str:
    for p in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"):
        if Path(p).exists():
            return p
    return "msedge"


def launch_edge(log=print) -> None:
    """제어 포트를 연 Edge 를 별도 프로필로 띄운다. 이미 떠 있으면 아무것도 안 한다."""
    if _port_open():
        return
    PROFILE.mkdir(parents=True, exist_ok=True)
    subprocess.Popen([_edge_exe(), *edge_args(), BASE + "/main/login.do"], creationflags=0x00000008)
    for _ in range(60):
        if _port_open():
            log(f"Edge 띄움(제어 포트 {PORT}, 프로필 {PROFILE})")
            return
        time.sleep(0.5)
    raise RuntimeError(f"Edge 가 제어 포트 {PORT} 를 열지 않았습니다")


def edge_args() -> list[str]:
    """Edge 실행 인자. 창은 화면 오른쪽 절반(왼쪽은 터미널, 2026-10-03 유저 요청). http→https 자동 승격을 끈다(KOLIS 는 http 이고 승격되면 세션이 끊김)."""
    import ctypes
    u = ctypes.windll.user32
    sw, sh = u.GetSystemMetrics(0), u.GetSystemMetrics(1)
    left = int(os.environ.get("KOLIS_EDGE_LEFT", str(sw // 2)))
    return [f"--remote-debugging-port={PORT}", f"--user-data-dir={PROFILE}", "--no-first-run", "--no-default-browser-check",
            f"--window-position={left},0", f"--window-size={sw - left},{sh - 48}",
            "--disable-features=AutomaticHttpsDefault,HttpsUpgrades,HttpsFirstBalancedMode,HttpsFirstModeV2"]


class Browser:
    def __init__(self, log=print, journal=None, work_dir: Path = Path("work")):
        from playwright.sync_api import sync_playwright
        self.log, self.journal = log, journal
        self.rec_path = Path(work_dir) / "logs" / f"browser-{datetime.datetime.now():%Y%m%d}.jsonl"   # 하루 한 파일에 이어 쓴다(실행이 나뉘어도 한 흐름)
        self.rec_path.parent.mkdir(parents=True, exist_ok=True)
        launch_edge(log)
        self._pw = sync_playwright().start()
        self.b = self._pw.chromium.connect_over_cdp(f"http://127.0.0.1:{PORT}")
        self.ctx = self.b.contexts[0] if self.b.contexts else self.b.new_context()
        # 조작용 탭: 팝업(…Pop.do)·수정 화면은 건드리지 않는다. 2026-10-03 18:50 저장 경로가 채워 둔 MODS 수정 화면 탭에 붙어 로그인 확인으로 첫 화면으로 이동시켜 채운 값이 날아갔다.
        kolis = [p for p in self.ctx.pages if "kolis.nl.go.kr" in p.url]
        main = [p for p in kolis if "Pop.do" not in p.url and "/contents/" not in p.url]
        self.page = main[0] if main else (self.ctx.new_page() if kolis else (self.ctx.pages[0] if self.ctx.pages else self.ctx.new_page()))
        if kolis and not main:
            self.log("열려 있는 KOLIS 탭이 전부 팝업·수정 화면이라 새 탭을 엽니다(채운 화면은 건드리지 않음)")
        self.n = 0
        self._rec("attach", url=self.page.url)
        for pg in self.ctx.pages:
            self._hook(pg)
        self.ctx.on("page", self._on_page)
        log(f"Edge 에 붙음: {self.page.url}")

    # ---------- 기록 ----------
    def _on_page(self, page):
        """새 창(팝업). 팝업 문서 자체의 응답은 창이 생기기 전에 끝나 받을 수 없으므로 주소를 따로 적는다. 그 뒤의 요청은 전부 기록된다."""
        self._hook(page)
        try:
            page.wait_for_load_state("domcontentloaded", timeout=15000)
        except Exception:  # noqa: BLE001
            pass
        self._rec("popup", url=page.url.replace(BASE, ""))
        self.log(f"  팝업: {page.url.replace(BASE, '')}")

    def _hook(self, page):
        page.on("response", self._on_response)
        page.on("dialog", self._on_dialog)

    def _rec(self, kind: str, **row):
        row = {"time": f"{datetime.datetime.now():%H:%M:%S.%f}"[:-3], "kind": kind, **row}
        with open(self.rec_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
        if self.journal:
            self.journal.write("browser", **row)

    def _on_response(self, r):
        u = r.url
        if "kolis.nl.go.kr" not in u or any(s in u for s in SKIP):
            return
        try:
            body = r.text()
        except Exception:  # noqa: BLE001
            body = ""
        self.n += 1
        post = r.request.post_data or ""
        self._rec("http", n=self.n, method=r.request.method, url=u.replace(BASE, ""), post=post[:20000], status=r.status, chars=len(body), response=body[:50000])
        if r.request.method == "POST":
            self.log(f"  [{self.n}] {r.request.method} {u.replace(BASE, '')} → {r.status} {len(body):,}자")

    def _on_dialog(self, d):
        self._rec("dialog", type=d.type, message=d.message, action="pending")
        self.log(f"  확인창: {d.message}")
        if d.type == "alert":          # 알림창은 읽고 닫는 것뿐(선택지 없음)
            d.accept(); self._rec("dialog", message=d.message, action="accept(알림)")
        elif self._dialog_answer is None:
            d.dismiss(); self._rec("dialog", message=d.message, action="dismiss(승인 없음)")
        else:
            (d.accept() if self._dialog_answer else d.dismiss()); self._rec("dialog", message=d.message, action="accept" if self._dialog_answer else "dismiss")
    _dialog_answer = None

    # ---------- 로그인 ----------
    def login(self) -> None:
        from .kolis_http import credentials
        p = self.page
        if "Pop.do" in p.url or "/contents/" in p.url:
            raise RuntimeError(f"로그인 확인을 팝업·수정 화면 탭에서 하려 했습니다({p.url}). 프로그램 오류")
        p.goto(BASE + "/main/gohome.do", wait_until="domcontentloaded"); p.wait_for_timeout(800)
        if p.url.startswith("https://"):
            raise RuntimeError(f"Edge 가 https 로 승격했습니다({p.url}). 이 Edge 를 닫고 다시 띄우세요(bin/edge_kolis.bat)")
        if "login" not in p.url and 'name="pwd"' not in p.content():
            self.log("이미 로그인됨"); return
        if 'name="pwd"' not in p.content():
            p.goto(BASE + "/main/login.do", wait_until="domcontentloaded"); p.wait_for_timeout(500)
        uid, pw = credentials()
        p.fill("#uid", uid); p.fill("#pwd", pw)
        self._rec("login", step="제출")
        p.press("#pwd", "Enter")
        p.wait_for_load_state("domcontentloaded"); p.wait_for_timeout(1000)
        if 'name="pwd"' in p.content():
            m = re.search(r'var\s+msg\s*=\s*"([^"]*)"', p.content())
            raise RuntimeError("로그인하지 못했습니다: " + (m.group(1) if m else "로그인 화면이 다시 나옴") + " (다시 시도하지 않음)")
        self.log("KOLIS 로그인됨(유저 Edge 창)")

    def cookies(self) -> dict:
        return {c["name"]: c["value"] for c in self.ctx.cookies(BASE)}

    # ---------- 화면 ----------
    def open(self, path: str, wait: float = 2.0):
        self._rec("open", path=path)
        self.page.goto(BASE + path, wait_until="domcontentloaded"); self.page.wait_for_timeout(int(wait * 1000))
        if 'name="pwd"' in self.page.content():
            raise RuntimeError("로그인이 풀렸습니다")
        return self.page

    def fill(self, selector: str, value: str) -> None:
        self.page.fill(selector, value); self._rec("fill", selector=selector, value=value)
        got = self.page.input_value(selector)
        if got != value:
            raise RuntimeError(f"{selector} 에 '{value}' 를 넣었는데 '{got}' 로 읽힘")

    def select(self, selector: str, value: str) -> None:
        self.page.select_option(selector, value); self._rec("select", selector=selector, value=value)
        self.page.evaluate(f"document.querySelector({json.dumps(selector)}).dispatchEvent(new Event('change', {{bubbles:true}}))")

    def eval(self, js: str):
        v = self.page.evaluate(js); self._rec("eval", js=js[:2000], result=str(v)[:5000]); return v

    def click(self, selector: str, approved: bool = False, changes: bool = True, confirm: bool | None = None, wait: float = 2.0) -> None:
        """changes=True(저장·실행·완료 등) 인 버튼은 approved=True 일 때만 누른다. confirm: 확인창에 할 대답(None 이면 닫음)."""
        if changes and not approved:
            raise NotApproved(f"'{selector}' 는 자료를 바꾸는 버튼입니다. 승인 없이 누르지 않습니다")
        self._dialog_answer = confirm
        self._rec("click", selector=selector, approved=approved, changes=changes)
        self.page.click(selector); self.page.wait_for_timeout(int(wait * 1000))
        self._dialog_answer = None

    def shot(self, name: str, work_dir: Path = Path("work")) -> Path:
        d = Path(work_dir) / "captures" / "browser"; d.mkdir(parents=True, exist_ok=True)
        p = d / f"{datetime.datetime.now():%Y%m%d-%H%M%S}_{name}.png"
        self.page.screenshot(path=str(p), full_page=False); return p

    def grid_rows(self, grid_js: str = "grid") -> list[dict]:
        """화면 표(jqxGrid 대역 객체 `grid`)의 행을 읽는다."""
        return self.eval(f"(()=>{{try{{var g={grid_js};var n=g.getRowsCount();var out=[];for(var i=0;i<n;i++){{out.push(g.getRowData?g.getRowData(i):$('#jqxgrid').jqxGrid('getrowdata',i));}}return out;}}catch(e){{return [{{error:String(e)}}];}}}})()")

    def wait(self, sec: float) -> None:
        """대기. time.sleep 은 Playwright 의 이벤트(응답 기록)를 멈추므로 쓰지 않는다."""
        self.page.wait_for_timeout(int(sec * 1000))

    def close(self) -> None:
        try:
            if self.page.is_closed():          # 마지막으로 쓰던 팝업이 닫혔으면 남은 창으로
                self.page = next((p for p in self.ctx.pages if not p.is_closed()), self.page)
            self.wait(0.5)   # 남은 응답 기록을 받는다
        except Exception:  # noqa: BLE001
            pass
        try:
            self._pw.stop()
        except Exception:  # noqa: BLE001
            pass
