"""에이전트용 도구: 자바스크립트로 그려지는 페이지를 이 PC 의 Edge(헤드리스)로 열어 화면 글자를 출력한다.

  python -m kolis_tool render <주소> [--scroll N] [--links] [--find "단어1|단어2"] [--max 60000]

플랫폼을 가리지 않는다(어느 사이트를 볼지는 에이전트가 정한다). KOLIS 주소는 거부한다.
요청은 전부 브라우저 페이지 안에서 한다: Edge 는 윈도 인증서 저장소를 쓰므로 이 PC 의 DLP(Somansa) 인증서를 정상 경로로 신뢰한다.
Playwright 의 Node 쪽 요청은 그 루트 CA 키가 약해 거부되므로 쓰지 않는다. 인증서 검증을 끄는 옵션도 쓰지 않는다.
"""
from __future__ import annotations
import re
import urllib.parse

from contextlib import contextmanager

BLOCKED_HOSTS = ("kolis.nl.go.kr",)


@contextmanager
def browser(headless: bool = True):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        # 화면 있는 실행은 창을 화면 밖에 둔다(KOLIS 조작 중인 화면을 가리지 않게)
        try:
            b = p.chromium.launch(channel="msedge", headless=headless, args=[] if headless else ["--window-position=-2400,-2400"])
        except Exception:  # noqa: BLE001 — Edge 가 없는 PC(맥북 임시): 설치된 chromium 으로
            b = p.chromium.launch(headless=headless)
        ctx = b.new_context(viewport={"width": 1280, "height": 2400}, locale="ko-KR")
        try:
            yield ctx
        finally:
            b.close()


def allowed(url: str) -> bool:
    u = urllib.parse.urlparse(url)
    host = (u.hostname or "").lower()
    return u.scheme in ("http", "https") and bool(host) and not any(host == b or host.endswith("." + b) for b in BLOCKED_HOSTS)


CHALLENGE = ("just a moment", "잠시만 기다", "보안 확인", "checking your browser", "verify you are human", "사람인지 확인")


def _blocked(pg) -> bool:
    head = (pg.title() + " " + pg.inner_text("body")[:400]).lower()
    return any(c in head for c in CHALLENGE)


def render(url: str, scroll: int = 0, links: bool = False, limit: int = 60000, find: str = "") -> str:
    """화면 없는 Edge 로 먼저 열고, 접속 확인 화면(봇 차단)에 막히면 화면 있는 Edge(화면 밖 위치)로 한 번 더 연다.
    find: '단어1|단어2' — 그 단어가 든 줄과 앞뒤 2줄만 돌려준다(메뉴가 긴 페이지에서 필요한 줄만 보기)."""
    if not allowed(url):
        raise SystemExit(f"허용되지 않는 주소입니다: {url}")
    try:
        text = _render(url, scroll, links, limit if not find else 400000, headless=True)
    except _Blocked:
        text = _render(url, scroll, links, limit if not find else 400000, headless=False)
    if find:
        words = [w for w in find.split("|") if w.strip()]
        try:
            pat = re.compile(find)               # 정규식으로도 쓸 수 있다(예: \d{4}\.\d{2}\.\d{2})
        except re.error:
            pat = re.compile("|".join(re.escape(w) for w in words))
        lines = text.splitlines()
        keep = set()
        for i, l in enumerate(lines):
            if i < 2 or pat.search(l):
                keep.update(range(max(0, i - 2), min(len(lines), i + 3)))
        out, prev = [], -1
        for i in sorted(keep):
            if prev >= 0 and i > prev + 1:
                out.append("  …")
            out.append(lines[i]); prev = i
        text = "\n".join(out)[:limit] if len(keep) > 2 else text[:200] + f"\n(찾는 단어 {words} 가 든 줄이 없습니다)"
    return text


class _Blocked(Exception):
    pass


def _render(url: str, scroll: int, links: bool, limit: int, headless: bool) -> str:
    with browser(headless) as ctx:
        pg = ctx.new_page()
        pg.goto(url, wait_until="domcontentloaded", timeout=60000)
        try:
            pg.wait_for_load_state("networkidle", timeout=8000)
        except Exception:  # noqa: BLE001
            pass
        if _blocked(pg):
            if headless:
                raise _Blocked()
            for _ in range(20):                 # 화면 있는 브라우저는 접속 확인이 저절로 풀리는 경우가 많다
                pg.wait_for_timeout(1000)
                if not _blocked(pg):
                    break
            else:
                return f"# 주소: {pg.url}\n# 접속 확인 화면(봇 차단)에 막혀 내용을 읽지 못했습니다. 다른 경로(WebFetch, 다른 플랫폼)를 쓰세요."
        for _ in range(max(0, scroll)):
            pg.mouse.wheel(0, 5000); pg.wait_for_timeout(500)
        out = [f"# 주소: {pg.url}", f"# 제목: {pg.title()}", "", re.sub(r"\n{3,}", "\n\n", pg.inner_text("body"))[:limit]]
        if links:
            ls = pg.eval_on_selector_all("a[href]", "els => els.map(e => [e.href, (e.innerText||'').trim().slice(0,80)])")
            seen, rows = set(), []
            for href, text in ls:
                if href.startswith("http") and href not in seen and text:
                    seen.add(href); rows.append(f"{text} → {href}")
            out += ["", "# 링크", *rows[:300]]
        return "\n".join(out)
