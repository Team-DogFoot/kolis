"""③구간 5.3 MODS 구축(반자동, 2026-10-03): 유저 Edge 창(kolis_browser.Browser)에서 가이드 메뉴 순서대로 MODS 수정 화면을 열고,
화면 값과 전거 검색 후보를 떠서 헤드리스 에이전트(`build-mods` 스킬)에게 판단을 맡기고, 결과를 화면에 넣는다. **저장은 사람이 승인할 때만.**

단계(각각 따로 돌릴 수 있다. 화면이 이미 열려 있으면 그 화면을 쓴다):
  open     원부번호로 디지털콘텐츠관리 찾기 → n번째 행 체크 → MODS정리(종 화면) → MODS수정(MODS 수정 화면)
  collect  MODS 수정 화면의 칸 값 전부 + 저자마다 전거 검색(listACMat.do, 조회) → work/build/<콘텐츠ID>/job.json
  agent    에이전트 실행(읽기·조사·판단) → build.json (검사 check-build, 검수 포함)
  apply    build.json 을 화면에 넣는다(저자전거 연결·다른이름·주제명 두 묶음·UCI). 저장하지 않는다. 캡처.
  save     '저장' 버튼(승인). 뒤에 MODS XML(getHarContentsXml.do)을 받아 before/after 를 남긴다.

쓰는 법: python -m kolis_tool.mods_build <단계…> --wonbu 1607 --row 0  (예: open collect agent apply)
에이전트는 KOLIS 에 접근하지 않는다. 여기서 뜬 JSON 만 받는다.
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


# ---------------------------------------------------------------- collect
FORM_JS = r"""Array.from(document.querySelectorAll('#harContentsUpdateForm input:not([type=button]), #harContentsUpdateForm select, #harContentsUpdateForm textarea'))
 .filter(e=>e.name && !e.name.startsWith('tag_') && e.name!=='i_show_hide')
 .map(e=>({name:e.name, id:e.id, tag:e.tagName.toLowerCase(), type:e.type, value:e.value, hidden:(e.type==='hidden'||e.offsetParent===null)}))"""


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


def search_authority(b: Browser, mods, keyword: str, cnts: str) -> list[dict]:
    """전거 찾기 팝업이 보내는 조회(listACMat.do)와 같은 요청을 이 창의 쿠키로 보낸다(조회만)."""
    body = {"flag": "4", "type": "0", "targetid": "", "subdata": "", "contents_id": cnts, "species_key": "", "keyword": keyword, "exact_yn": "Y", "ac_class": "", "choice": "on"}
    r = mods.request.post(BASE + "/bocata/kormarcmatmng/kormarcmatmng/listACMat.do", form=body)
    txt = r.text()
    b._rec("http", method="POST", url="/bocata/kormarcmatmng/kormarcmatmng/listACMat.do", post=urllib.parse.urlencode(body), status=r.status, chars=len(txt), response=txt[:50000], note="전거 후보 조회(collect)")
    data = json.loads(txt)
    rows = data.get("list") or []
    return [{k: v for k, v in row.items() if k not in DROP_CAND} for row in rows]


def collect(b: Browser, mods, wonbu: str, row_info: dict | None, manuscript: str | None, instructions: str) -> Path:
    cnts = contents_id(mods)
    d = WORK / cnts; d.mkdir(parents=True, exist_ok=True)
    form = read_form(mods)
    (d / "form.json").write_text(json.dumps(form, ensure_ascii=False, indent=1), encoding="utf-8")
    (d / "form.html").write_text(mods.content(), encoding="utf-8")
    fn = mods.evaluate("['insertAcMat','gf_insertSubjNm','popSearchNameKolis2','subjectSearchPop','lf_update'].map(n=>n+': '+(typeof window[n]==='function'?window[n].toString().slice(0,1500):'없음')).join('\\n\\n')")
    (d / "page_functions.txt").write_text(fn, encoding="utf-8")
    val = {f["name"]: f["value"] for f in form if f["value"]}
    authors = authors_from(form)
    for a in authors:
        a["candidates"] = search_authority(b, mods, a["name"], cnts)
        _p(f"전거 후보 '{a['name']}': {len(a['candidates'])}건")
    job = {
        "contents_id": cnts, "wonbu": wonbu, "title": val.get("_titleInfo_title", ""), "part": val.get("_titleInfo_partNumber", ""),
        "row": row_info,
        "publisher_says": {"publisher": val.get("_originInfo_publisher", ""), "date": val.get("_originInfo_dateIssued", ""), "isbn": val.get("_identifier", ""),
                           "place": val.get("_originInfo_place_placeTerm", ""), "urls": [f["value"] for f in form if f["name"] == "_location_url" and f["value"]]},
        "form": [{"name": f["name"], "value": f["value"]} for f in form if f["value"]],
        "authors": authors,
        "manuscript": manuscript,
        "instructions": instructions,
        "project": settings(),
    }
    (d / "job.json").write_text(json.dumps(job, ensure_ascii=False, indent=1), encoding="utf-8")
    _p("작업 파일:", d / "job.json", "| 저자:", [(a["name"], a["role"], len(a["candidates"])) for a in authors])
    return d / "job.json"


# ---------------------------------------------------------------- agent
def run_agent(job_path: Path, log=print, model: str | None = None) -> tuple[dict, list[str], Path]:
    from . import agent, checks
    job = json.loads(job_path.read_text(encoding="utf-8"))
    name = f"build_{job['contents_id']}"
    result, fails, jd = agent.run_job("build-mods", name, job, "build.json", lambda p: checks.check_build(p, p.with_name("job.json")), log=log, model=model, timeout=2400)
    out = job_path.with_name("build.json"); out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"에이전트 결과: {out} | 남은 걸린 항목 {len(fails)}건")
    for f in fails:
        log("  - " + f)
    return result, fails, out


# ---------------------------------------------------------------- apply
SUBJ_LIST = """(()=>{const g=n=>Array.from(document.querySelectorAll('[name="'+n+'"]')).map(e=>({id:e.id,v:e.value}));return {ID:g('_subject@ID'),auth:g('_subject@authority'),topic:g('_subject_topic'),genre:g('_subject_genre')}})()"""


def apply_subjects(b: Browser, mods) -> dict:
    """주제명 묶음을 정확히 둘로 만들고 고정값을 넣는다(직원 확정 2026-10-03)."""
    cur = mods.evaluate(SUBJ_LIST)
    n = len(cur["ID"])
    if n < 2:
        first = mods.evaluate("document.querySelector('[name=\"_subject\"]').id")
        mods.evaluate(f"repeat('{first}', '_subject', '주제명', '_subject', '2')"); b._rec("form", action="주제명 묶음 추가(repeat)"); mods.wait_for_timeout(500)
    elif n > 2:
        raise RuntimeError(f"주제명 묶음이 {n}개 — 사람이 정리해야 함")
    mods.evaluate("""(()=>{const g=n=>Array.from(document.querySelectorAll('[name="'+n+'"]'));
      const ID=g('_subject@ID'), AU=g('_subject@authority'), T=g('_subject_topic'), G=g('_subject_genre');
      ID[0].value='KSH1998022212'; T[0].value='만화[漫畵]'; G[0].value='';
      ID[1].value='KSH2016000049'; T[1].value=''; G[1].value='웹툰[webtoon]';
      const setAu=(el,txt)=>{ if(!el) return; if(el.tagName=='SELECT'){ for(const o of el.options){ if(o.text.includes(txt)||o.value.includes(txt)){ el.value=o.value; return; } } } else el.value=txt; };
      setAu(AU[0],'국립중앙도서관주제명표목표'); setAu(AU[1],'국립중앙도서관주제명표목표'); })()""")
    b._rec("form", action="주제명 1 = 만화[漫畵] KSH1998022212 / 2 = 장르 웹툰[webtoon] KSH2016000049 / 전거 국립중앙도서관주제명표목표")
    return mods.evaluate(SUBJ_LIST)


def apply_authors(b: Browser, mods, build: dict, job: dict) -> list[str]:
    """연결(link)한 저자만 전거 번호를 넣는다. 화면의 찾기 팝업이 호출하는 insertAcMat 과 같은 함수를 쓴다(있을 때). 다른이름은 원문 근거가 있는 것만."""
    notes = []
    has_fn = mods.evaluate("typeof insertAcMat==='function'")
    for a in build.get("authors") or []:
        idx = next((j["index"] for j in job["authors"] if j["name"] == a["name"]), None)
        if idx is None:
            notes.append(f"{a['name']}: 화면의 저자와 짝이 안 맞음"); continue
        if a.get("decision") == "link":
            cand = next((c for c in next(j for j in job["authors"] if j["name"] == a["name"])["candidates"] if c["AC_CONTROL_NO"] == a["ac_control_no"]), None)
            if cand is None:
                notes.append(f"{a['name']}: 후보에 없는 전거 번호 {a.get('ac_control_no')} — 넣지 않음"); continue
            # 화면의 찾기 버튼(popSearchNameKolis2)이 숨은 칸 kolisBean.classCode/dataCode/dataCodeName/type 에 대상 칸 id 를 적어 두고,
            # 팝업의 선택이 insertAcMat 을 불러 그 칸들에 @ID·@authority("국립중앙도서관전거데이터")·@type 을 넣는다. 같은 순서로 한다.
            ids = mods.evaluate(f"""(()=>{{const q=n=>document.querySelectorAll('[name="'+n+'"]')[{idx}]; return {{part:q('_name_namePart').id, id:q('_name@ID').id, auth:q('_name@authority').id, type:q('_name@type').id}}}})()""")
            if has_fn:
                mods.evaluate("""([ids,idx,no,sp,chi,by,t])=>{const f=document.harContentsUpdateForm; f.elements['kolisBean.classCode'].value=ids.part; f.elements['kolisBean.classCodeIdx'].value=String(idx); f.elements['kolisBean.dataCode'].value=ids.id; f.elements['kolisBean.dataCodeName'].value=ids.auth; f.elements['kolisBean.type'].value=ids.type; insertAcMat(no,sp,chi,by,t,'');}""",
                              [ids, idx, cand["AC_CONTROL_NO"], cand["CHOICE_SIGNPOST"], cand.get("CHI_NAME") or "", "", cand.get("AC_TYPE") or "0"])
                b._rec("form", action=f"저자 {a['name']} 전거 연결 insertAcMat({cand['AC_CONTROL_NO']}, {cand['CHOICE_SIGNPOST']}) → {ids}")
            else:
                mods.evaluate(f"""(()=>{{const q=n=>document.querySelectorAll('[name="'+n+'"]')[{idx}]; q('_name@ID').value={json.dumps(cand['AC_CONTROL_NO'])}; q('_name@authority').value='국립중앙도서관전거데이터'; }})()""")
                b._rec("form", action=f"저자 {a['name']} 전거 번호 직접 입력 {cand['AC_CONTROL_NO']}(insertAcMat 없음)")
                notes.append(f"{a['name']}: insertAcMat 함수가 없어 @ID·@authority 를 직접 넣었음 — 확인 필요")
        for alt in a.get("alternative_names") or []:
            if "원문" not in str(alt.get("source") or ""):
                continue
            mods.evaluate(f"""(()=>{{const q=n=>document.querySelectorAll('[name="'+n+'"]')[{idx}]; q('_name_alternativeName_namePart').value={json.dumps(alt['name'])}; q('_name_alternativeName@altType').value={json.dumps(alt.get('alt_type') or 'no specific type')}; }})()""")
            b._rec("form", action=f"저자 {a['name']} 다른이름 {alt['name']} ({alt.get('alt_type')})")
    return notes


def apply_uci(b: Browser, mods, build: dict) -> str:
    u = (build.get("uci") or {}).get("value") or ""
    if not u.strip():
        return "UCI 없음(넣지 않음)"
    cur = mods.evaluate("Array.from(document.querySelectorAll('[name=\"_identifier\"]')).map(e=>e.value)")
    types = mods.evaluate("Array.from(document.querySelectorAll('[name=\"_identifier@type\"]')).map(e=>e.value)")
    if "uci" in types:
        i = types.index("uci"); mods.evaluate(f"document.querySelectorAll('[name=\"_identifier\"]')[{i}].value={json.dumps(u)}")
    else:
        first = mods.evaluate("document.querySelector('[name=\"_identifier\"]').id")
        mods.evaluate(f"repeat('{first}', '_identifier', '식별기호', '_identifier', '2')"); mods.wait_for_timeout(500)
        mods.evaluate(f"""(()=>{{const I=document.querySelectorAll('[name="_identifier"]'), T=document.querySelectorAll('[name="_identifier@type"]'); const k=I.length-1; I[k].value={json.dumps(u)}; T[k].value='uci'; }})()""")
    b._rec("form", action=f"식별기호 uci = {u}")
    return f"UCI {u} 넣음(저장 전)"


NOTE_LIST = """(()=>{const g=n=>Array.from(document.querySelectorAll('[name="'+n+'"]')).map(e=>e.value);return {note:g('_note'), type:g('_note@type')}})()"""


def apply_note(b: Browser, mods) -> str:
    """입수처 주기(@type acquisition)가 사업 설정값과 같게 한다. 없으면 묶음을 추가해 넣고, 다르면 고친다(사업별 임시 고정값, 유저 2026-10-03)."""
    want = settings().get("acquisition_note") or ""
    if not want.strip():
        return "입수처 주기 설정 없음(건드리지 않음)"
    cur = mods.evaluate(NOTE_LIST)
    idx = next((i for i, t in enumerate(cur["type"]) if t == "acquisition"), None)
    if idx is not None:
        if cur["note"][idx] == want:
            return f"입수처 주기 이미 있음: {want}"
        mods.evaluate(f"""document.querySelectorAll('[name="_note"]')[{idx}].value={json.dumps(want)}""")
        b._rec("form", action=f"입수처 주기 고침: {cur['note'][idx]!r} → {want!r}")
        return f"입수처 주기 고침: {cur['note'][idx]} → {want}"
    first = mods.evaluate("document.querySelector('[name=\"_note\"]').id")
    mods.evaluate(f"repeat('{first}', '_note', '주기사항', '_note', '2')"); mods.wait_for_timeout(500)
    mods.evaluate(f"""(()=>{{const N=document.querySelectorAll('[name="_note"]'), T=document.querySelectorAll('[name="_note@type"]'); const k=N.length-1; N[k].value={json.dumps(want)}; T[k].value='acquisition'; }})()""")
    b._rec("form", action=f"입수처 주기 추가: {want}")
    return f"입수처 주기 추가: {want}"


def apply(b: Browser, mods, build_path: Path) -> dict:
    build = json.loads(build_path.read_text(encoding="utf-8"))
    job = json.loads(build_path.with_name("job.json").read_text(encoding="utf-8"))
    subj = apply_subjects(b, mods)
    notes = apply_authors(b, mods, build, job)
    uci = apply_uci(b, mods, build)
    note = apply_note(b, mods)
    after = read_form(mods)
    (build_path.with_name("form_after_apply.json")).write_text(json.dumps(after, ensure_ascii=False, indent=1), encoding="utf-8")
    mods.evaluate("document.querySelector('[name=\"_name_namePart\"]').scrollIntoView({block:'start'})"); mods.wait_for_timeout(300)
    s1 = shot(mods, "mods_apply_authors")
    mods.evaluate("document.querySelector('[name=\"_subject@ID\"]').scrollIntoView({block:'start'})"); mods.wait_for_timeout(300)
    s2 = shot(mods, "mods_apply_subjects")
    _p(f"KOLIS 화면에 채웠습니다(저장 안 함) — 주제명 {len(subj['ID'])}묶음, {uci}, {note}" + (f", 저자 메모 {len(notes)}건" if notes else ""))
    return {"subjects": subj, "notes": notes, "uci": uci, "note": note, "shots": [str(s1), str(s2)]}


# ---------------------------------------------------------------- save
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


# ---------------------------------------------------------------- 프로그램 창용
def summary(build: dict, job: dict) -> dict:
    """화면에 보여 줄 요약(직원이 읽는 글)."""
    authors = []
    for a in build.get("authors") or []:
        authors.append({"name": a.get("name"), "role": a.get("role"), "decision": a.get("decision"), "ac": a.get("ac_control_no") or "", "signpost": a.get("choice_signpost") or "",
                        "confidence": a.get("confidence"), "reason": a.get("reason"), "candidates": len(next((j.get("candidates") or [] for j in job.get("authors") or [] if j.get("name") == a.get("name")), [])),
                        "alt": [f"{x.get('name')} ({x.get('alt_type')})" for x in a.get("alternative_names") or []], "not_verifiable": a.get("not_verifiable") or [],
                        "evidence": [e if isinstance(e, str) else f"{e.get('url')} — {e.get('quote')}" for e in a.get("evidence") or []]})
    u = build.get("uci") or {}; pub = build.get("publisher") or {}; pl = build.get("place") or {}
    return {"contents_id": build.get("contents_id"), "title": build.get("title"), "part": build.get("part"), "authors": authors,
            "subjects": [f"{s.get('term')} {s.get('id')}" for s in build.get("subjects") or []],
            "uci": u.get("value") or "", "uci_searched": [f"{x.get('where')} — {x.get('how')}" for x in u.get("searched") or []],
            "publisher": pub.get("current"), "publisher_change": pub.get("change"), "publisher_reason": pub.get("reason"),
            "place": f"{pl.get('current', '')} → 확인 {pl.get('verified', '')}/{pl.get('code', '')}",
            "issues": [x if isinstance(x, str) else f"{x.get('field')}: {x.get('note')}" for x in build.get("issues") or []],      # 작품 단위 판단은 글, 회차 단위 옛 형식은 항목·내용 쌍
            "notes": [x if isinstance(x, str) else str(x.get("note") or x) for x in build.get("notes_for_staff") or []], "review": build.get("review") or {}}


def run(wonbu: str, row: int, log=print, manuscript: str | None = None, instructions: str = "", model: str | None = None, handle: dict | None = None) -> dict:
    """프로그램 창의 '화면 열기 → 값 읽기 → 에이전트 판단 → 화면에 넣기'(저장 안 함). 돌려주는 것: 요약 + 파일 경로."""
    _LOG[0] = log
    b = Browser(log); b.login()
    mods, info = open_mods(b, wonbu, row)
    job_path = collect(b, mods, wonbu, info, manuscript, instructions)
    cnts = contents_id(mods)
    b.close()
    from . import agent, checks
    job = json.loads(job_path.read_text(encoding="utf-8"))
    result, fails, jd = agent.run_job("build-mods", f"build_{cnts}", job, "build.json", lambda p: checks.check_build(p, p.with_name("job.json")), log=log, model=model, handle=handle, timeout=2400)
    build_path = job_path.with_name("build.json"); build_path.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    b = Browser(log); mods = _pages(b, "onContentsDetailPop")[0]
    ap = apply(b, mods, build_path)
    b.close()
    st = {"wonbu": wonbu, "row": row, "contents_id": cnts, "title": job.get("title"), "part": job.get("part"), "applied_at": f"{datetime.datetime.now():%Y-%m-%d %H:%M}", "saved_at": None, "remaining": fails}
    (WORK / cnts / "state.json").write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    return {**summary(result, job), "remaining": fails, "apply": ap, "build_path": str(build_path), "dir": str(WORK / cnts), "state": st}


def save_run(wonbu: str, row: int, log=print) -> dict:
    """프로그램 창의 '저장'(직원 확인 뒤). 열려 있는 MODS 수정 화면을 저장하고 XML 전·후를 받는다."""
    _LOG[0] = log
    b = Browser(log); b.login()
    pages = _pages(b, "onContentsDetailPop")
    if not pages:
        b.close(); raise SystemExit("MODS 수정 화면이 열려 있지 않습니다. 먼저 '화면 열기·판단'을 실행하세요")
    mods = pages[0]; cnts = contents_id(mods)
    stp = WORK / cnts / "state.json"
    st = json.loads(stp.read_text(encoding="utf-8")) if stp.exists() else {}
    if not st.get("applied_at"):
        b.close(); raise SystemExit(f"{cnts}: 에이전트 판단을 화면에 넣은 기록이 없습니다. 먼저 '화면 열기·판단'을 실행하세요")
    save(b, mods, approved=True)
    after = (WORK / cnts / "mods_after.xml").read_text(encoding="utf-8")
    ok = "KSH2016000049" in after and "KSH1998022212" in after
    st["saved_at"] = f"{datetime.datetime.now():%Y-%m-%d %H:%M}"; st["xml_ok"] = ok
    stp.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    # 일이 끝난 KOLIS 창(MODS 수정 화면·종 화면)은 닫는다(2026-10-03 유저: 안 닫혀서 헷갈림). 디지털콘텐츠관리 본 탭은 남긴다.
    closed = 0
    for part in ("onContentsDetailPop", "onSpecViewPop"):
        for pg in _pages(b, part):
            try:
                pg.close(); closed += 1
            except Exception:  # noqa: BLE001
                pass
    b._rec("close", what="저장 뒤 팝업 닫기", count=closed)
    _p(f"저장 끝. 열려 있던 KOLIS 팝업 {closed}개를 닫았습니다.")
    b.close()
    return {"contents_id": cnts, "saved_at": st["saved_at"], "xml_ok": ok, "xml_chars": len(after), "dir": str(WORK / cnts)}


def status(wonbu: str) -> list[dict]:
    out = []
    for f in sorted(WORK.glob("*/state.json")):
        st = json.loads(f.read_text(encoding="utf-8"))
        if str(st.get("wonbu")) == str(wonbu):
            out.append(st)
    return sorted(out, key=lambda x: x.get("row", 0))


# ---------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("steps", nargs="+", choices=["open", "collect", "agent", "apply", "save"])
    ap.add_argument("--wonbu", required=True); ap.add_argument("--row", type=int, default=0)
    ap.add_argument("--manuscript", default=None, help="원문 폴더 또는 이전 단계 관찰 기록(없으면 null)")
    ap.add_argument("--instructions", default=""); ap.add_argument("--model", default=None)
    ap.add_argument("--approve-save", action="store_true", help="save 단계에서 실제로 저장(사람 승인)")
    ns = ap.parse_args(argv)
    b = Browser(print); b.login()
    mods, info = (None, None)
    if any(s in ns.steps for s in ("open", "collect", "apply", "save")):
        mods, info = open_mods(b, ns.wonbu, ns.row)
        shot(mods, "mods_open")
    job_path = None
    if "collect" in ns.steps:
        job_path = collect(b, mods, ns.wonbu, info, ns.manuscript, ns.instructions)
    if "agent" in ns.steps:
        job_path = job_path or next(iter(sorted(WORK.glob("*/job.json"), key=lambda p: p.stat().st_mtime, reverse=True)), None)
        if mods is not None:
            job_path = WORK / contents_id(mods) / "job.json"
        assert job_path and job_path.exists(), "job.json 이 없습니다(collect 먼저)"
        b.close(); b = None   # 에이전트가 도는 동안(수 분) CDP 연결을 붙잡고 있지 않는다
        run_agent(job_path, model=ns.model)
        if any(s in ns.steps for s in ("apply", "save")):
            b = Browser(print); mods = _pages(b, "onContentsDetailPop")[0]
    if "apply" in ns.steps:
        apply(b, mods, WORK / contents_id(mods) / "build.json")
    if "save" in ns.steps:
        save(b, mods, ns.approve_save)
    if b is not None:
        b.close()


if __name__ == "__main__":
    main()
