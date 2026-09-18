"""플랫폼 페이지에서 회차별 공개일·가격 수집 (Playwright + 이 PC 의 Edge, 헤드리스). KOLIS 와 무관.

자바스크립트로 그려지는 페이지(네이버시리즈·카카오페이지·리디)는 requests 로는 회차 목록이 안 보여 브라우저를 쓴다.
모든 요청은 브라우저 페이지 안에서(goto / fetch) 한다 — Edge 가 윈도 인증서 저장소를 쓰므로 이 PC 의 DLP(Somansa) 인증서를
정상 경로로 신뢰한다. Playwright 의 Node 쪽 요청(APIRequestContext)은 그 루트 CA 키가 OpenSSL 기준에 못 미쳐("key too weak")
거부되므로 쓰지 않는다. 인증서 검증을 끄는 옵션(ignore_https_errors)은 쓰지 않는다.

각 어댑터는 {"platform": 이름, "url_work": 작품 URL, "url_main": 메인, "rating": 등급, "authors": [...],
            "episodes": [{"no": 1, "date": "YYYYMMDD", "title": "", "price": "", "free": "무료|유료"}]} 를 돌려준다.
"""
from __future__ import annotations
import re, urllib.parse
from contextlib import contextmanager

EP_RE = re.compile(r"(?<!\d)(\d{1,3})\s*화")
DATE_RE = re.compile(r"(\d{4})\.(\d{2})\.(\d{2})")
DATE2_RE = re.compile(r"(?<!\d)(\d{2})\.(\d{2})\.(\d{2})(?!\d)")


@contextmanager
def browser(headless: bool = True):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge", headless=headless)
        ctx = b.new_context(viewport={"width": 1280, "height": 2400}, locale="ko-KR")
        try:
            yield ctx
        finally:
            b.close()


def _ep_from_line(line: str) -> tuple[int, str] | None:
    """'죽고 못사는 연애 [BL] 12화 (2024.10.21.)' → (12, '20241021')"""
    if re.search(r"외전|프롤로그|에필로그|트레일러|예고|후기|특별편|번외", line):
        return None
    m = EP_RE.search(line)
    if not m:
        return None
    d = DATE_RE.search(line)
    if d:
        return int(m.group(1)), "".join(d.groups())
    d2 = DATE2_RE.search(line)
    if d2:
        return int(m.group(1)), "20" + "".join(d2.groups())
    return int(m.group(1)), ""


def naver_series(ctx, title: str, url: str | None = None, log=print) -> dict | None:
    pg = ctx.new_page()
    try:
        if not url:
            pg.goto("https://series.naver.com/search/search.series?t=all&q=" + urllib.parse.quote(title), wait_until="domcontentloaded", timeout=60000)
            links = pg.eval_on_selector_all("a[href*='/comic/detail.series']", "els => els.map(e => [e.href, e.innerText.trim()])")
            t = re.sub(r"\s", "", title)
            hit = next((l for l in links if l[1] and t in re.sub(r"\s", "", l[1])), None)
            if not hit:
                log("네이버시리즈: 검색 결과 없음"); return None
            url = hit[0]
        pn = re.search(r"productNo=(\d+)", url).group(1)
        out = {"platform": "네이버시리즈", "url_work": f"https://series.naver.com/comic/detail.series?productNo={pn}",
               "url_main": "https://series.naver.com/comic/home.series", "rating": "", "authors": [], "episodes": []}
        pg.goto(out["url_work"], wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_selector("#volumeList tr", timeout=20000)   # 회차 표가 그려질 때까지만 기다린다(networkidle 보다 훨씬 빠름)
        body = pg.inner_text("body")
        m = re.search(r"글\s*(\S+)\s*\n?\s*그림\s*(\S+)", body)
        if m:
            out["authors"] = [{"name": m.group(1), "role": "글"}, {"name": m.group(2), "role": "그림"}]
        # 등급: 작품 정보 블록('출판사' 다음 줄)에서만 읽는다. 상단 광고·안내문의 '19세' 에 속지 않도록
        g = re.search(r"출판사[^\n]*\n\s*(전체 이용가|\d{2}세 이용가|성인|19세 이용가)", body)
        out["rating"] = g.group(1) if g else ""
        # 가격·등급코드: volumeList JSON (페이지 안 fetch)
        prices: dict[int, dict] = {}
        page = 1
        while page < 40:
            js = pg.evaluate("u => fetch(u, {credentials:'include'}).then(r => r.json())",
                             f"https://series.naver.com/comic/volumeList.series?productNo={pn}&sortOrder=ASC&page={page}&pageSize=50")
            items = js.get("resultData") or []
            if not items:
                break
            if not out["rating"] and items[0].get("seeingGradeCodeTypeDescription"):
                out["rating"] = items[0]["seeingGradeCodeTypeDescription"]
            for it in items:
                e = _ep_from_line(str(it.get("volumnNameText") or ""))
                if e:
                    prices[e[0]] = {"price": str(int(it.get("salePrice") or 0) or ""), "free": "무료" if it.get("freeYn") == "Y" else "유료",
                                    "title": it.get("volumnNameText") or ""}
            if len(items) < 30:
                break
            page += 1
        # 날짜: 화면의 회차 표(#volumeList) 'N화 (YYYY.MM.DD.)'. 30건씩, 표 아래 쪽번호 링크(2, 3, …)를 눌러 넘긴다
        seen: dict[int, str] = {}

        def harvest():
            n = 0
            for line in pg.locator("#volumeList").inner_text().splitlines():
                e = _ep_from_line(line)
                if e and e[1] and e[0] not in seen:
                    seen[e[0]] = e[1]; n += 1
            return n
        harvest()
        for pno in range(2, 60):
            clicked = pg.evaluate("""n => { const t=document.querySelector('#volumeList').closest('table');
                const a=[...document.querySelectorAll('a')].find(e => (t.compareDocumentPosition(e) & 4) && (e.innerText||'').trim() === String(n));
                if (a) { a.click(); return true; } return false; }""", pno)
            if not clicked:
                break
            try:
                pg.wait_for_function("n => { const s=document.querySelector('#volumeList'); return s && s.innerText.includes(n + '화'); }", arg=(pno - 1) * 30 + 1, timeout=8000)
            except Exception:  # noqa: BLE001
                pg.wait_for_timeout(1000)
            if harvest() == 0:
                break
        for no in sorted(set(seen) | set(prices)):
            out["episodes"].append({"no": no, "date": seen.get(no, ""), **prices.get(no, {"price": "", "free": "", "title": f"{no}화"})})
        log(f"네이버시리즈: 회차 {len(out['episodes'])}건, 날짜 {len(seen)}건, 등급 '{out['rating']}'")
        return out
    finally:
        pg.close()


def ridi(ctx, title: str, url: str | None = None, log=print) -> dict | None:
    pg = ctx.new_page()
    try:
        if not url:
            pg.goto("https://ridibooks.com/search?q=" + urllib.parse.quote(title), wait_until="domcontentloaded", timeout=60000)
            pg.wait_for_timeout(2500)
            links = pg.eval_on_selector_all("a[href*='/books/']", "els => els.map(e => [e.href, e.innerText.trim()])")
            t = re.sub(r"\s", "", title)
            hit = next((l for l in links if l[1] and t in re.sub(r"\s", "", l[1])), None)
            if not hit:
                log("리디: 검색 결과 없음"); return None
            url = hit[0].split("?")[0]
        pg.goto(url, wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(3000)
        body = pg.inner_text("body")
        out = {"platform": "리디", "url_work": url, "url_main": "https://ridibooks.com/", "rating": "", "authors": [], "episodes": []}
        g = re.search(r"(성인|19세|15세 이용가|전체 이용가)", body)
        out["rating"] = g.group(1) if g else ""
        seen: dict[int, dict] = {}
        for line in body.splitlines():
            e = _ep_from_line(line)
            if e and e[0] not in seen:
                pm = re.search(r"(\d[\d,]*)\s*원", line)
                seen[e[0]] = {"no": e[0], "date": e[1], "title": line.strip()[:60], "price": pm.group(1).replace(",", "") if pm else "",
                              "free": "무료" if "무료" in line else ""}
        out["episodes"] = [seen[k] for k in sorted(seen)]
        log(f"리디: 회차 {len(out['episodes'])}건, 날짜 {sum(1 for e in seen.values() if e['date'])}건, 등급 '{out['rating']}'")
        return out
    finally:
        pg.close()


def kakao_page(ctx, title: str, url: str | None = None, log=print) -> dict | None:
    pg = ctx.new_page()
    try:
        if not url:
            pg.goto("https://page.kakao.com/search/result?keyword=" + urllib.parse.quote(title), wait_until="domcontentloaded", timeout=60000)
            pg.wait_for_timeout(2000)
            links = pg.eval_on_selector_all("a[href*='/content/']", "els => els.map(e => [e.href, e.innerText.trim()])")
            t = re.sub(r"\s", "", title)
            hit = next((l for l in links if l[1] and t in re.sub(r"\s", "", l[1])), None)
            if not hit:
                log("카카오페이지: 검색 결과 없음"); return None
            url = hit[0].split("?")[0]
        pg.goto(url + "?tab_type=episode", wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(2500)
        body = pg.inner_text("body")
        if "이용할 수 없습니다" in body:
            log("카카오페이지: 판매 중이 아닌 작품(회차 없음)"); return None
        for _ in range(30):
            pg.mouse.wheel(0, 5000); pg.wait_for_timeout(600)
        body = pg.inner_text("body")
        out = {"platform": "카카오페이지", "url_work": url, "url_main": "https://page.kakao.com/", "rating": "", "authors": [], "episodes": []}
        g = re.search(r"(전체 이용가|\d{2}세 이용가|19세)", body)
        out["rating"] = g.group(1) if g else ""
        lines = body.splitlines()
        seen: dict[int, dict] = {}
        for i, line in enumerate(lines):
            e = _ep_from_line(line)
            if e and e[0] not in seen:
                d = e[1]
                if not d:
                    for nxt in lines[i + 1:i + 4]:
                        d2 = DATE2_RE.search(nxt)
                        if d2: d = "20" + "".join(d2.groups()); break
                seen[e[0]] = {"no": e[0], "date": d, "title": line.strip()[:60], "price": "", "free": "무료" if "무료" in " ".join(lines[i:i + 3]) else ""}
        out["episodes"] = [seen[k] for k in sorted(seen)]
        log(f"카카오페이지: 회차 {len(out['episodes'])}건")
        return out
    finally:
        pg.close()


ADAPTERS = {"네이버시리즈": naver_series, "리디": ridi, "카카오페이지": kakao_page}


def gather(title: str, known_urls: dict[str, str] | None = None, log=print, headless: bool = True, handle: dict | None = None) -> list[dict]:
    """모든 어댑터를 돌려 플랫폼별 결과 목록을 돌려준다. known_urls: {'리디': url, ...} (LLM 리서치가 찾은 URL). handle['cancel'] 이면 중단."""
    known_urls = known_urls or {}
    results = []
    with browser(headless) as ctx:
        for name, fn in ADAPTERS.items():
            if handle and handle.get("cancel"):
                log("플랫폼 수집 중단"); break
            try:
                r = fn(ctx, title, known_urls.get(name), log)
                if r: results.append(r)
            except Exception as e:  # noqa: BLE001
                log(f"{name}: 실패 — {type(e).__name__}: {str(e)[:120]}")
    return results


def merge_into(info: dict, results: list[dict]) -> dict:
    """플랫폼 결과를 research JSON 에 합친다: 회차별 가장 이른 날짜, 플랫폼 URL, 등급(성인 표시가 하나라도 있으면 유지)."""
    eps: dict[int, dict] = {int(e["no"]): dict(e) for e in info.get("episodes", []) or [] if str(e.get("no", "")).isdigit()}
    plats = {p.get("name"): p for p in info.get("platforms", []) or []}
    for r in results:
        p = plats.setdefault(r["platform"], {"name": r["platform"], "url_main": "", "url_work": "", "start_date": ""})
        p["url_main"] = r["url_main"] or p.get("url_main", ""); p["url_work"] = r["url_work"] or p.get("url_work", "")   # 어댑터 값(완료 사례 표기) 우선
        dated = [e["date"] for e in r["episodes"] if e.get("date")]
        if dated and (not p.get("start_date") or min(dated) < p["start_date"]):
            p["start_date"] = min(dated)
        for e in r["episodes"]:
            cur = eps.get(e["no"])
            if cur is None:
                eps[e["no"]] = {**e, "source": r["platform"]}
            else:
                if e.get("date") and (not cur.get("date") or e["date"] < cur["date"]):
                    cur["date"] = e["date"]; cur["source"] = r["platform"]
                if e.get("price") and not cur.get("price"):
                    cur["price"] = e["price"]
        if r.get("rating") and ("19" in r["rating"] or "성인" in r["rating"]):
            info["adult"] = True; info["rating"] = r["rating"]
        elif r.get("rating") and not info.get("rating"):
            info["rating"] = r["rating"]
        info.setdefault("evidence", []).append(f"{r['url_work']} — 플랫폼 수집: 회차 {len(r['episodes'])}건, 등급 '{r.get('rating')}'")
        info.setdefault("rating_by_platform", {})[r["platform"]] = r.get("rating", "")
    info["platforms"] = list(plats.values())
    info["episodes"] = [eps[k] for k in sorted(eps)]
    dated = [p["start_date"] for p in info["platforms"] if p.get("start_date")]
    if dated and (not info.get("first_publish_date") or min(dated) < info["first_publish_date"]):
        info["first_publish_date"] = min(dated)
    return info
