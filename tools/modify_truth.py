"""개발용 측정: 수정 팝업을 화면 없는 Edge 에 띄워, 그 화면의 스크립트가 만드는 저장 본문(getParam)을 떠 둔다. 저장 요청은 보내지 않는다."""
import sys, json
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright
from kolis_tool import kolis_http, kolis_request as kr
out = Path("work/captures/pages/수정팝업")
items = json.loads((out / "list_item_982.json").read_text(encoding="utf-8"))
c = kolis_http.Client(log=lambda m: None); c.login()
cookies = [{"name": k.name, "value": k.value, "domain": k.domain or "kolis.nl.go.kr", "path": k.path or "/"} for k in c.s.cookies]
keys = ",".join(str(i["SPECIES_KEY"]) for i in items); it = items[0]
url = f"{kr.BASE}/online/acq/bodepst/depstrecet/onlineDepstRecet/popupModify.do?receiptNoHasFlag=Y&receiptNoVal=982&receiptKeyVal={it['RECEIPT_KEY']}&arrSpeciesKey={keys}&workCode={it['WORK_CODE']}&update=Y"
with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge", headless=True)
    ctx = b.new_context(user_agent=kolis_http.AGENT.replace("Trident/7.0; rv:11.0) like Gecko", "Chrome/120 Safari/537.36)"))
    ctx.add_cookies(cookies)
    parent = ctx.new_page()
    parent.goto(kr.BASE + "/jscript/json/json2.js")
    parent.evaluate("""rows => { let sel = 0; window.grid = {getCheckedIndexList: () => rows.map((_, i) => i), getRowsCount: () => rows.length, getSelectedIndexList: () => [sel],
        getselectedrowindex: () => sel, selectRow: i => { sel = i; }, getCellValue: (i, name) => rows[i][name]};
        window.$ = () => ({val: () => '2026'}); window.bindDataToGrid = () => {}; }""", items)
    errs = []
    with parent.expect_popup() as pi:
        parent.evaluate("u => { window.open(u, 'pop'); }", url)
    pop = pi.value
    pop.on("dialog", lambda d: (errs.append("dialog: " + d.message), d.dismiss()))
    pop.on("pageerror", lambda e: errs.append("error: " + str(e)[:200]))
    pop.wait_for_load_state("load"); pop.wait_for_timeout(4000)
    print("제목:", pop.title(), "| 오류:", errs[:8])
    print("편/권차:", pop.evaluate("$('#ipt_part_name_contents_main').val()"), "| 파일 표 행:", pop.evaluate("grid.getRowsCount()"))
    param = pop.evaluate("getParam()")
    (out / "truth_param_1.json").write_text(json.dumps(param, ensure_ascii=False, indent=1), encoding="utf-8")
    print("본문 항목", len(param), "| 값 있는 항목", sum(1 for v in param.values() if v not in (None, "")))
    print({k: (v if len(str(v)) < 50 else str(v)[:30] + "…") for k, v in param.items() if v not in (None, "")})
    print("파일 표:", pop.evaluate("grid.getJsonAllData()")[:1500])
    for s in ("sel_typeofresource", "sel_genre", "sel_access_condition_license_contents", "sel_working_status", "sel_kogl_code", "sel_publisher_code", "sel_use_obj_code"):
        print(s, pop.evaluate(f"Array.from(document.querySelectorAll('#{s} option')).map(o => o.value + '=' + o.text).join(' / ')")[:400])
    b.close()
c.close()
