"""개발용 수집: KOLIS 화면 하나를 화면 없는 Edge 에 띄워 소스·화면 요소·요청을 모은다(읽기만. 버튼은 --click 으로 지정한 것만 누른다).
쓰는 법: python tools/recon.py <이름> <주소(/로 시작)> [--fill id=값 ...] [--click 선택자 ...] [--wait 초] [--opener JSON파일]
결과: work/captures/pages/<이름>/ 에 page.html, shot.png, requests.jsonl, summary.txt. 저장·변경 버튼은 누르지 않는다."""
import sys, json, re
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright
from kolis_tool import kolis_http, kolis_request as kr

a = sys.argv[1:]; name, url = a[0], a[1]
def opt(flag):
    out, i = [], 2
    while i < len(a):
        if a[i] == flag:
            i += 1
            while i < len(a) and not a[i].startswith("--"): out.append(a[i]); i += 1
        else: i += 1
    return out
fills, clicks, wait = [x.split("=", 1) for x in opt("--fill")], opt("--click"), float((opt("--wait") or ["3"])[0])
out = Path("work/captures/pages") / name; out.mkdir(parents=True, exist_ok=True)
c = kolis_http.Client(log=lambda m: None); c.login()
cookies = [{"name": k.name, "value": k.value, "domain": k.domain or "kolis.nl.go.kr", "path": k.path or "/"} for k in c.s.cookies]
SKIP = (".js", ".css", ".png", ".gif", ".jpg", ".ico", ".woff", "sessionDelay", "StaffGridInfo")
with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge", headless=True)
    ctx = b.new_context(viewport={"width": 1600, "height": 1000}); ctx.add_cookies(cookies)
    pg = ctx.new_page(); reqs, msgs, pops = [], [], []
    def on_resp(r):
        u = r.url
        if any(s in u for s in SKIP) or "kolis.nl.go.kr" not in u: return
        try: body = r.text()[:200000]
        except Exception: body = ""
        reqs.append({"method": r.request.method, "url": u.replace(kr.BASE, ""), "post": r.request.post_data, "status": r.status, "response": body})
    def hook(page):
        page.on("response", on_resp); page.on("dialog", lambda d: (msgs.append(d.message), d.dismiss()))
        page.on("pageerror", lambda e: msgs.append("오류: " + str(e)[:200]))
    hook(pg); ctx.on("page", lambda np: (pops.append(np), hook(np)))
    pg.goto(kr.BASE + url); pg.wait_for_load_state("load"); pg.wait_for_timeout(wait * 1000)
    for fid, val in fills:
        pg.evaluate("([i, v]) => { const e = document.getElementById(i); e.value = v; if (window.$) $(e).trigger('change'); }", [fid, val])
    for sel in clicks:
        pg.evaluate("s => document.querySelector(s).click()", sel); pg.wait_for_timeout(wait * 1000)
    pages = [pg] + pops
    lines = []
    for n, page in enumerate(pages):
        try: html = page.content()
        except Exception: continue
        tag = "page" if n == 0 else f"popup{n}"
        (out / f"{tag}.html").write_text(html, encoding="utf-8")
        try: page.screenshot(path=str(out / f"{tag}.png"), full_page=True)
        except Exception: pass
        info = page.evaluate("""() => ({title: document.title, url: location.href,
            buttons: Array.from(document.querySelectorAll('input[type=button],button,a.btn')).filter(e => e.offsetParent).map(e => (e.id || '?') + '=' + (e.value || e.innerText || '').trim()).filter(s => s.length > 2),
            inputs: Array.from(document.querySelectorAll('input[type=text],input:not([type]),textarea')).filter(e => e.offsetParent && e.id).map(e => e.id + (e.value ? '=' + e.value : '')),
            selects: Array.from(document.querySelectorAll('select')).filter(e => e.id).map(e => e.id + '[' + e.value + ']: ' + Array.from(e.options).slice(0, 12).map(o => o.value + '=' + o.text.trim()).join(' / ')),
            grids: Array.from(document.querySelectorAll('[role=columnheader]')).map(e => e.innerText.trim()).filter(Boolean)})""")
        src = (out / f"{tag}.html").read_text(encoding="utf-8")
        lines += [f"## {tag}: {info['title']} — {info['url'].replace(kr.BASE, '')}", "버튼: " + " | ".join(info["buttons"]), "입력: " + " | ".join(info["inputs"]),
                  "선택: \n  " + "\n  ".join(info["selects"]), "표 머리: " + " | ".join(info["grids"]),
                  "소스의 주소: " + " ".join(sorted(set(re.findall(r"/(?:online|cmmn|main)/[\w/]+\.do", src)))), ""]
    lines += ["## 알림·오류", *msgs, "", "## 요청"] + [f"{r['method']} {r['url'][:160]} | 보냄 {(r['post'] or '')[:300]} | 받음 {r['status']} {len(r['response'])}자 {r['response'][:200]!r}" for r in reqs]
    (out / "requests.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in reqs), encoding="utf-8")
    (out / "summary.txt").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines)[:int((opt("--print") or ["6000"])[0])])
    b.close()
c.close()
