"""KOLIS 구축 화면의 브라우저 사실 층(2026-10-03 실서버에서 확인한 조작만. 2026-10-04 B 단계 보정 `wonbu.fix_apply` 가 쓴다).
  open_digitalcont  가이드 메뉴 순서: 정리 → 디지털콘텐츠 → 디지털콘텐츠관리 → 등록구분 FTX·원부번호 → 찾기 (조회 요청으로 표를 대조)
  open_mods         n번째 행 선택 → MODS정리(종 화면) → MODS수정(MODS 수정 화면)
  read_form         MODS 수정 화면의 칸 전부(이름·값)
  capture_save_body 화면의 저장 함수(lf_update)를 돌리되 보내는 부분만 가로채 저장 본문을 돌려준다(보내지 않음)
  fetch_xml / save  MODS XML 받기 / 저장 단추(승인 때만)
설정(settings)은 사업 고정값(입수처 주기 문장).
"""
from __future__ import annotations
import argparse, datetime, json, re, sys, urllib.parse
from pathlib import Path

from .kolis_browser import Browser, BASE

sys.stdout.reconfigure(encoding="utf-8")
WORK = Path("work") / "build"
_LOG = [print]


def _p(*a):
    """print 대신. 프로그램 창에서 돌 때는 run()/save_run() 이 탭 로그로 바꿔 끼운다."""
    _LOG[0](" ".join(str(x) for x in a))
SUBJECTS = [("topic", "만화[漫畵]", "KSH1998022212"), ("genre", "웹툰[webtoon]", "KSH2016000049")]
AUTHORITY_SUBJ = "국립중앙도서관주제명표목표"
DROP_CAND = ("MARC", "SIGNPOSTS", "_chk", "REC_KEY", "TAG373")
SETTINGS = Path("work") / "build_settings.json"
DEFAULT_SETTINGS = {"acquisition_note": "한국웹툰산업협회를 통해 수집한 자료임"}   # 사업마다 다르다(유저 2026-10-03). 프로그램 창에서 바꾼다.


def settings() -> dict:
    try:
        return {**DEFAULT_SETTINGS, **json.loads(SETTINGS.read_text(encoding="utf-8"))}
    except Exception:  # noqa: BLE001
        return dict(DEFAULT_SETTINGS)


def save_settings(patch: dict) -> dict:
    cur = settings(); cur.update({k: v for k, v in patch.items() if k in DEFAULT_SETTINGS})
    SETTINGS.parent.mkdir(parents=True, exist_ok=True); SETTINGS.write_text(json.dumps(cur, ensure_ascii=False, indent=1), encoding="utf-8")
    return cur


def shot(pg, name: str) -> Path:
    d = Path("work/captures/browser"); d.mkdir(parents=True, exist_ok=True)
    f = d / f"{datetime.datetime.now():%Y%m%d-%H%M%S}_{name}.png"
    pg.screenshot(path=str(f)); return f


def _pages(b: Browser, part: str):
    return [pg for pg in b.ctx.pages if part in pg.url and not pg.is_closed()]


# ---------------------------------------------------------------- open
def close_notice(p):
    p.evaluate("""document.querySelectorAll('.jqx-window').forEach(w=>{if(w.offsetParent!==null){const bt=[...w.querySelectorAll('input[type=button],button')].find(x=>(x.value||x.innerText||'').trim()=='닫기');if(bt)bt.click();}})""")


def open_digitalcont(b: Browser, wonbu: str):
    """가이드 메뉴 순서: 정리 → 디지털콘텐츠 → 온라인 › 단행 › 디지털콘텐츠관리 → 등록구분 FTX·원부번호 → 찾기."""
    p = b.page
    if "onlineDigitalContMng.do" not in p.url:
        p.goto(BASE + "/main/gohome.do", wait_until="domcontentloaded"); b.wait(1.5); close_notice(p); b.wait(0.5)
        b._rec("menu", step="정리"); p.get_by_text("정리", exact=True).locator("visible=true").first.click(); b.wait(1.5)
        b._rec("menu", step="디지털콘텐츠"); p.get_by_text("디지털콘텐츠", exact=True).locator("visible=true").first.click(); b.wait(1.5)
        b._rec("menu", step="디지털콘텐츠관리"); p.get_by_role("link", name="디지털콘텐츠관리", exact=True).locator("visible=true").first.click()
        p.wait_for_selector("#accession_rec_no_start", timeout=30000); b.wait(2)
    if b.eval("$('#accession_rec_no_start').val()") != wonbu or b.eval("(()=>{try{return grid.getRowsCount()}catch(e){return 0}})()") == 0:
        b._dialog_answer = True        # "검색 조건을 변경하면 그리드가 초기화 됩니다. 계속하시겠습니까?" → 예 (아니오면 조건이 되돌아가 이전 원부가 조회된다, 2026-10-03)
        b.select("#reg_code", "FTX"); b.fill("#accession_rec_no_start", wonbu)
        b.click("#btnSearch", changes=False, wait=4.0)
        b._dialog_answer = None
    n = b.eval("(()=>{try{return grid.getRowsCount()}catch(e){return -1}})()")
    # 조회된 표가 정말 이 원부인지 요청으로 대조한다(화면 조건이 되돌아간 적이 있어서)
    f = dict(har_type_cd="", bus_id="", coll_id="", key_arr="", acc_rec_key="", type="mo", work_status_list_start="DS_3200", work_status_list_end="DS_3400", har_stat_cd="30", tran_stat_cd="40", list_menu_id="F1131200", init_dcms_yn="", use_limit_code="", reg_code="FTX", acquisit_yr=str(datetime.date.today().year), accession_rec_no_start=wonbu, accession_rec_no_end=wonbu, accession_no_start="", accession_no_end="", searchSpecCnt="", searchContCnt="")
    expect = {str(x.get("SPECIES_KEY")) for x in p.request.post(BASE + "/online/cata/bocata/digitalcont/digitalcontmng/onlineDigitalContMngList.do", headers={"X-Requested-With": "XMLHttpRequest"}, form=f).json().get("list", [])}
    shown = set(map(str, b.eval("(()=>{var o=[];try{for(var i=0;i<grid.getRowsCount();i++){o.push($('#jqxgrid').jqxGrid('getrowdata',i).SPECIES_KEY);}}catch(e){}return o;})()")))
    if expect and shown != expect:
        raise RuntimeError(f"디지털콘텐츠관리 표가 원부 {wonbu} 와 다릅니다(표 {len(shown)}종, 조회 {len(expect)}종). 화면 조건이 바뀌지 않았을 수 있습니다")
    if b.eval("$('#accession_rec_no_start').val()") != wonbu:
        raise RuntimeError(f"원부번호 칸이 {wonbu} 가 아닙니다")
    _p(f"디지털콘텐츠관리: 원부 {wonbu} → {n}행, 종수/콘텐츠수 {b.eval('[$(\"#searchSpecCnt\").val(), $(\"#searchContCnt\").val()]')}")
    return p, n


def open_mods(b: Browser, wonbu: str, row: int):
    """n번째 행만 체크 → MODS정리 → 종·콘텐츠 화면 → MODS수정 → MODS 수정 화면. 돌려주는 것: (MODS 수정 페이지, 행 정보)."""
    mods = _pages(b, "onContentsDetailPop")
    if mods:
        _p("MODS 수정 화면이 이미 열려 있음:", mods[0].url.replace(BASE, "")); return mods[0], None
    main, n = open_digitalcont(b, wonbu)
    assert 0 <= row < n, f"행 {row} 없음(총 {n})"
    # MODS정리 단추는 체크가 아니라 **선택된 행**(grid.getselectedrowindex, 없으면 0행)의 SPECIES_KEY 로 종 화면을 연다(화면 소스 확인 2026-10-03).
    main.evaluate(f"(function(){{for(var i=0;i<grid.getRowsCount();i++){{$('#jqxgrid').jqxGrid('setcellvalue',i,'_chk',i=={row});}} $('#jqxgrid').jqxGrid('clearselection'); $('#jqxgrid').jqxGrid('selectrow',{row}); $('#jqxgrid').jqxGrid('ensurerowvisible',{row});}})()")
    main.wait_for_timeout(300)
    info = main.evaluate(f"(()=>{{var r=$('#jqxgrid').jqxGrid('getrowdata',{row});return {{TITLE:r.TITLE,VOL:r.VOL,SPECIES_KEY:r.SPECIES_KEY,ACCESSION_NO:r.ACCESSION_NO,CONTENTS_ID:r.CONTENTS_ID,selected:$('#jqxgrid').jqxGrid('getselectedrowindex')}}}})()")
    if info.get("selected") != row:
        raise RuntimeError(f"행 {row} 선택이 안 됨(선택 행 {info.get('selected')})")
    b._rec("select", row=row, info=info); _p(f"{row + 1}번째 행 선택:", info)
    spec = _pages(b, "onSpecViewPop")
    if not spec:
        with b.ctx.expect_page(timeout=20000) as ev:
            b.page = main; b.click("#btnModsArrange", changes=False)
        spec = ev.value
    else:
        spec = spec[0]
    spec.wait_for_load_state("domcontentloaded"); spec.wait_for_timeout(3000); b._hook(spec)
    _p("종·콘텐츠 화면:", spec.url.replace(BASE, ""))
    if f"species_key={info['SPECIES_KEY']}" not in spec.url:
        raise RuntimeError(f"종 화면이 다른 종을 열었습니다: 기대 {info['SPECIES_KEY']}, 실제 {spec.url}")
    with b.ctx.expect_page(timeout=20000) as ev:
        b.page = spec; b.click("#btnModCnts", changes=False)
    mods = ev.value; mods.wait_for_load_state("domcontentloaded"); mods.wait_for_timeout(4000); b._hook(mods)
    _p("MODS 수정 화면:", mods.url.replace(BASE, ""))
    return mods, info


# ---------------------------------------------------------------- 화면 읽기
def read_form(mods) -> list[dict]:
    return mods.evaluate(FORM_JS)


def contents_id(mods) -> str:
    q = urllib.parse.parse_qs(urllib.parse.urlparse(mods.url).query)
    return (q.get("contents_id") or q.get("contentsId") or [""])[0]


def authors_from(form: list[dict]) -> list[dict]:
    """저자 묶음(_name)을 순서대로. 칸 이름이 같아 순서로 짝짓는다(묶음마다 namePart 는 하나라고 본다)."""
    names = [f["value"] for f in form if f["name"] == "_name_namePart" and not f["hidden"]]
    roles = [f["value"] for f in form if f["name"] == "_name_role_roleTerm"]
    types = [f["value"] for f in form if f["name"] == "_name@type"]
    ids = [f["value"] for f in form if f["name"] == "_name@ID"]
    out = []
    for i, nm in enumerate(names):
        if not nm.strip():
            continue
        out.append({"name": nm, "role": roles[i] if i < len(roles) else "", "type": types[i] if i < len(types) else "",
                    "current_id": ids[i] if i < len(ids) else "", "index": i})
    return out




# ---------------------------------------------------------------- save
def capture_save_body(b: Browser, mods) -> dict:
    """KOLIS 화면의 저장 함수(lf_update)를 그대로 돌리되, 보내는 부분($.ajax → updateHarContents.do)만 가로채 요청 본문을 돌려준다. **보내지 않는다.**
    화면 스크립트가 만드는 것과 같은 본문(평행 배열, 쉼표는 ▲COMMA▲, 칸 id 목록)을 얻는 가장 확실한 길이다(2026-10-03 계획 6절 7번)."""
    b._dialog_answer = True            # '필수 항목 중 입력하지 않은 값이 있습니다. 삭제?' 류 확인창은 화면과 같게 예
    cap = mods.evaluate("""(()=>{
        const orig = $.ajax; window.__cap = null;
        $.ajax = function(o){ if(o && typeof o.url === 'string' && o.url.indexOf('updateHarContents.do') > -1){ window.__cap = {url: o.url, data: o.data}; return {done(){}, fail(){}}; } return orig.apply(this, arguments); };
        try { lf_update(); } catch(e) { window.__cap = {error: String(e)}; }
        $.ajax = orig;
        return window.__cap;
    })()""")
    b._dialog_answer = None
    if not cap:
        raise RuntimeError("저장 본문을 가로채지 못했습니다(lf_update 가 요청을 만들기 전에 멈춤 — 필수 칸 비었거나 확인창)")
    if cap.get("error"):
        raise RuntimeError(f"lf_update 오류: {cap['error']}")
    data = cap.get("data") or {}
    b._rec("capture", what="저장 본문(보내지 않음)", url=cap.get("url"), fields=len(data), xpaths=len(str(data.get("inputedXpath", "")).split(",")))
    return data


def fetch_xml(mods, cnts: str) -> str:
    r = mods.request.post(BASE + "/online/contents/popup/getHarContentsXml.do", form={"contentsId": cnts})
    return (json.loads(r.text()).get("mods_xml") or "") if r.ok else ""


def save(b: Browser, mods, approved: bool) -> None:
    cnts = contents_id(mods); d = WORK / cnts; d.mkdir(parents=True, exist_ok=True)
    before = fetch_xml(mods, cnts); (d / "mods_before.xml").write_text(before, encoding="utf-8")
    b.page = mods
    b.click("#btnSaveCnts", approved=approved, changes=True, confirm=True, wait=3.0)
    after = fetch_xml(mods, cnts) if not mods.is_closed() else fetch_xml(b.ctx.pages[0], cnts)
    (d / "mods_after.xml").write_text(after, encoding="utf-8")
    _p(f"저장 요청 보냄. XML 전 {len(before)}자 → 후 {len(after)}자. {d}")


