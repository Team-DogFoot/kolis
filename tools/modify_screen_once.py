"""개발용 실험: 접수 982 의 N 번째 건에 화면과 같은 절차로 썸네일을 등록한다(화면 없는 Edge 가 수정 팝업의 스크립트를 그대로 실행). 보낸 저장 본문을 기록한다."""
import sys, json, time, uuid, datetime
from pathlib import Path
from urllib.parse import urlencode, parse_qsl
sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright
from kolis_tool import kolis_http, kolis_request as kr
N = int(sys.argv[1]) if len(sys.argv) > 1 else 1          # 0 부터
out = Path("work/captures/pages/수정팝업")
items = json.loads((out / "list_item_982.json").read_text(encoding="utf-8"))
it = items[N]; cid = it["CONTENTS_ID"]
thumb = Path(r"C:\Users\User\Downloads\484_미스터블루_옆집 기러기 아빠 구워먹기\썸네일") / f"옆집기러기아빠구워먹기{N + 1:02d}.jpg"
c = kolis_http.Client(log=lambda m: None); c.login()
def files(): return c.send("POST", kr.U_FILE_LIST, urlencode({"contents_id": cid}), kr.FORM)["list"]
def show(tag): print(tag, [(x["TEXT_GBN"], x["FILE_NAME"][:40], x["FILE_SIZE"], x["REG_DT"], x["FILE_ID"]) for x in files()])
show("전:")
rule = "/Upload1/tmp/wonmun/" + datetime.datetime.now().strftime("%Y%m%d") + str(int(time.time() * 1000))
data = thumb.read_bytes()
ans = kr.uploader_answer(c.upload(kr.U_HANDLER, kr.upload_fields(str(uuid.uuid4()).upper(), thumb.name, "0z", rule), thumb.name, data, "image/jpeg", note={"rule": rule})).split("|")
temp = ans[1].split("::", 1)[-1].replace("//", "/"); print("전송:", ans[0], temp, ans[3])
cookies = [{"name": k.name, "value": k.value, "domain": k.domain or "kolis.nl.go.kr", "path": k.path or "/"} for k in c.s.cookies]
keys = ",".join(str(i["SPECIES_KEY"]) for i in items)
url = f"{kr.BASE}/online/acq/bodepst/depstrecet/onlineDepstRecet/popupModify.do?receiptNoHasFlag=Y&receiptNoVal=982&receiptKeyVal={it['RECEIPT_KEY']}&arrSpeciesKey={keys}&workCode={it['WORK_CODE']}&update=Y"
with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge", headless=True)
    ctx = b.new_context(); ctx.add_cookies(cookies)
    parent = ctx.new_page(); parent.goto(kr.BASE + "/jscript/json/json2.js")
    parent.evaluate("""([rows, n]) => { let sel = n; window.grid = {getCheckedIndexList: () => [n], getRowsCount: () => rows.length, getSelectedIndexList: () => [sel],
        getselectedrowindex: () => sel, selectRow: i => { sel = i; }, getCellValue: (i, name) => rows[i][name]};
        window.$ = () => ({val: () => '2026'}); window.bindDataToGrid = () => {}; }""", [items, N])
    with parent.expect_popup() as pi:
        parent.evaluate("u => { window.open(u, 'pop'); }", url)
    pop = pi.value; msgs, sent = [], []
    pop.on("dialog", lambda d: (msgs.append(d.message), d.accept()))
    pop.on("pageerror", lambda e: msgs.append("오류: " + str(e)[:200]))
    def on_req(r):
        if "popupUpdateOnlineDepstRecet" in r.url: sent.append(r.post_data or "")
    pop.on("request", on_req)
    pop.wait_for_load_state("load"); pop.wait_for_timeout(3000)
    print("열린 건:", pop.evaluate("$('#contents_id').val()"), pop.evaluate("$('#ipt_part_number_contents_main').val() + '/' + $('#ipt_part_name_contents_main').val()"))
    assert pop.evaluate("$('#contents_id').val()") == cid
    rows = json.loads(pop.evaluate("grid.getJsonAllData()"))
    hold = [i for i, r in enumerate(rows) if r["TEXT_GBN_CD"] == "06" and not str(r["FILE_ID"]).startswith("FILE-")]
    if hold:      # 1) 자리 행만 체크 → 원문삭제 → 저장
        pop.evaluate("hold => { for (let i = 0; i < grid.getRowsCount(); i++) grid.setCellValue(i, '_chk', hold.includes(i)); }", hold)
        pop.click("#btnRemove"); pop.wait_for_timeout(500)
        pop.click("#btn_save"); pop.wait_for_timeout(4000)
        print("삭제·저장 뒤 알림:", msgs); msgs.clear(); show("삭제 뒤:")
    view = [r for r in json.loads(pop.evaluate("grid.getJsonAllData()")) if r["TEXT_GBN_CD"] == "01"][-1]
    pop.evaluate("""([cid, name, size, temp, fid]) => {
        const param = [{idx: 0, text_gbn: '06', text_gbn_desc: '썸네일', file_name: name, file_ext: 'jpg', file_size: size, temp_path: temp, folder_path: '', har_type_cd: '62'}];
        $("#frm_del_file").val(JSON.stringify({contents_id: cid, kolis_control_no: "", select_file_id: fid, data: param}));
        const n = grid.getRowsCount() + 1;
        grid.addRow(null, {_jqx_idx: n, _chk: '0', FILE_ID: '', FILE_LOCA: temp, NO: n, ACCESSION_NO: null, TEXT_GBN_CD: '06', TEXT_GBN: '썸네일', FILE_NAME: name, FILE_EXT: 'jpg',
            FOLDER_PATH: '', TEMP_PATH: temp, FILE_SIZE: size, SELECT_FILE_ID: fid, SEQ_NO: '0', REG_DT: '', DRM_YN: ''}); }""", [cid, thumb.name, str(len(data)), temp, view["FILE_ID"]])
    pop.click("#btn_save"); pop.wait_for_timeout(5000)
    print("등록·저장 뒤 알림:", msgs)
    for i, body in enumerate(sent):
        (out / f"sent_save_{N + 1}_{i + 1}.txt").write_text(body, encoding="utf-8")
        q = dict(parse_qsl(body, keep_blank_values=True))
        print(f"저장 {i + 1}: 항목 {len(q)} | frm_file {q.get('frm_file', '')[:700]} | frm_del_file {q.get('frm_del_file', '')[:500]}")
    b.close()
show("끝:")
c.close()
