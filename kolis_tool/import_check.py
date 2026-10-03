"""반입용 값(import.json, 트리 꼴)의 검사 — 판단하지 않는다(값 규칙·파일 증거·호출 기록 대조만). 2026-10-04 개선안 3-A.

import.json 꼴:
{
 "title", "unit", "publisher_xlsx", "manuscripts_root", "thumbs_dir", "observations_dir",
 "arrange": {...}, "reading": {"mapping": [...]}, "adult": false, "adult_reason": "",
 "common": {"mods": {…모든 행 공통…}, "extra": {…}},
 "rows": [{"no": 1, "folder": "…", "thumb_source": "", "thumb_file": "", "color": "천연색|흑백",
           "mods": {…이 행만 다른 값(최상위 요소 단위로 common 을 덮는다)…}, "extra": {…},
           "confirm": [{"path": "트리 경로", "reason", "publisher_says", "evidence", "ask"}],
           "sources": [{"path": "트리 경로", "from": "원문 <파일>|출판사 엑셀 <칸>|플랫폼 <이름> <주소>|전거 <번호>|직원 지시|직원 결정|관행", "quote": ""}]}],
 "issues": [], "review": {"done": false, "findings": [], "resolved": []}
}
값 규칙의 출처: 예시 88열 2행의 값 + 2026-10-03 반입 헤더 시험 값(개인명/단체명, BornDigital, JPG, kormarccountry, text/code, iso639-2b).
Sample 시트 선택값은 예시에 없는 열(표제 유형·이용대상자·식별기호 유형·접근제한·지역구분·다른이름 유형)에만 쓴다.
"""
from __future__ import annotations
import copy, json, re
from pathlib import Path
from . import arrange, mods_sheet as ms
from .common import REGION_CODE, extent_string

REPO = Path(__file__).resolve().parent.parent
AUTHORITY_CACHE = REPO / "work" / "authority"
AUDIENCES = ("고등학생", "성인용", "아동용", "일반이용자", "중학생", "초등학생", "취학전아동", "취학전 아동", "특수계층", "미상")
NAME_TYPES = ("개인명", "단체명")
ALT_TYPES = ("nickname", "formal name", "no specific type")
TITLE_TYPES = ("", "uniform", "title", "parallel", "translated", "original", "abbreviated", "alternative")
ID_TYPES = ("isbn", "uci", "issn", "doi", "hdl", "coi", "local", "uri", "upc", "isrc", "ismn", "sici", "lccn", "urn")
LICENSE = ("0", "1", "2")
NOTE_TYPES = ("", "target audience", "acquisition", "awards", "funding")
LANGS = ("kor", "eng", "chi", "jpn", "fre", "ger", "spa", "rus", "ita", "vie", "tha", "ind", "ara", "und")
ROLE_BAD = ("지은", "그린", "엮은", "옮긴", "쓴", "펴낸")
KNOWN_TOP = set(ms.ORDER_TOP)
EXTENT_RE = re.compile(r"^이미지 파일 \d+개 \([\d.]+ (bytes|KB|MB|GB)\) : (천연색|흑백)$")


# ---------------------------------------------------------------- 행 만들기(공통 + 행, 수량 계산)
def materialize(data: dict, folder: Path | None) -> list[dict]:
    """common 과 rows 를 합쳐 직렬화기가 받는 행 목록을 만든다. folder 가 있으면 수량·파일 형식을 센다(정리 뒤 모습 기준)."""
    common_m = (data.get("common") or {}).get("mods") or {}
    common_x = (data.get("common") or {}).get("extra") or {}
    vw = arrange.View(folder, data) if folder is not None else None
    out = []
    for r in data.get("rows") or []:
        mods = copy.deepcopy(common_m)
        for k, v in (r.get("mods") or {}).items():
            mods[k] = copy.deepcopy(v)
        extra = dict(common_x); extra.update(r.get("extra") or {})
        pd = mods.setdefault("physicalDescription", {})
        if isinstance(pd, list):
            pd = pd[0]; mods["physicalDescription"] = pd
        if vw is not None and r.get("folder"):
            imgs = vw.images(f"{data.get('manuscripts_root')}/{r['folder']}")
            pd["extent"] = extent_string(len(imgs), sum(p.stat().st_size for p in imgs), r.get("color") or "천연색")
            exts = {p.suffix.lower().lstrip(".") for p in imgs}
            pd["internetMediaType"] = "JPG" if exts <= {"jpg"} else "JPEG" if exts <= {"jpeg", "jpg"} else (sorted(exts)[0].upper() if exts else "")
        if r.get("thumb_file"):
            extra["thum_files"] = r["thumb_file"]
        out.append({**r, "mods": mods, "extra": extra})
    return out


# ---------------------------------------------------------------- 검사
def check(data: dict, folder: Path | None, reads: set[str] | None = None, notes: list[str] | None = None) -> list[str]:
    """걸린 항목 목록(비어 있으면 통과). notes 가 주어지면 막지 않는 알림(시험 전 열 등)을 거기에 적는다.
    reads = 실행기가 기록한 에이전트의 Read/look 호출 파일 경로(있으면 관찰 파일의 장마다 실제로 봤는지 대조)."""
    out: list[str] = []
    notes = notes if notes is not None else []
    rows = data.get("rows") or []
    if not rows:
        return ["rows 가 비어 있습니다"]
    # 파일 증거(정리 뒤 모습)
    subs: dict = {}
    thumb_names = None
    vw = None
    if folder is not None:
        pf = arrange.check(folder, data)
        if pf:
            return pf
        vw = arrange.View(folder, data)
        root = str(data.get("manuscripts_root") or "")
        if not root or not vw.is_dir(root):
            return [f"원고 폴더(manuscripts_root)가 없습니다: {data.get('manuscripts_root')!r}. 회차 폴더만 들어 있는 상위 폴더여야 합니다(없으면 arrange.moves 로 모으세요)"]
        kids = vw.children(root)
        subs = {n: p for n, p in kids if p.is_dir() and not n.startswith("_kolis")}
        if len(rows) != len(subs):
            out.append(f"자료 {len(rows)}행 ≠ 원고 하위 폴더 {len(subs)}개 {sorted(subs)[:15]}")
        stray = [n for n, p in kids if p.is_file()]
        if stray:
            out.append(f"원고 폴더 바로 아래에 파일이 있습니다(원문일괄등록이 멈춥니다): {stray[:3]}")
        th = str(data.get("thumbs_dir") or "")
        thumb_names = {n for n, p in vw.children(th) if p.is_file()} if th and vw.is_dir(th) else None
        if th and thumb_names is None:
            out.append(f"썸네일 폴더가 없습니다: {th}")
    try:
        mrows = materialize(data, folder)
    except Exception as e:  # noqa: BLE001
        return [f"행을 만들지 못했습니다(common/rows 꼴 확인): {type(e).__name__}: {e}"]
    try:
        cols = ms.layout(mrows)
    except Exception as e:  # noqa: BLE001
        return [f"트리를 열로 만들지 못했습니다: {type(e).__name__}: {e}"]
    unknown_tops = sorted({c.header.split("/")[2].split("[")[0] for c in cols if c.header.startswith("/mods/") and c.header.split("/")[2].split("[")[0] not in KNOWN_TOP})
    if unknown_tops:
        notes.append(f"시험 전 요소가 들어 있습니다(반입 확인 전, issues 에 적혀 있어야 합니다): {unknown_tops}")
        if not any(any(t in str(i) for t in unknown_tops) for i in data.get("issues") or []):
            out.append(f"시험 전 요소 {unknown_tops} 를 썼는데 issues 에 그 사실이 없습니다. 어느 요소를 왜 넣었는지 issues 에 적으세요")

    used_folders, parts, isbns = set(), [], []
    obs_dir = str(data.get("observations_dir") or "")
    for i, (r, mr) in enumerate(zip(rows, mrows), 1):
        m = mr["mods"]; x = mr["extra"]
        confirm_paths = {str(c.get("path") or "") for c in r.get("confirm") or [] if str(c.get("reason") or "").strip()}
        sources = {str(s.get("path") or ""): str(s.get("from") or "") for s in r.get("sources") or []}

        def src(path: str) -> str:
            return sources.get(path) or sources.get(re.sub(r"\[\d+\]", "", path)) or sources.get(path.split(".")[0]) or ""

        def confirmed(path: str) -> bool:
            return path in confirm_paths or re.sub(r"\[\d+\]", "", path) in confirm_paths or path.split(".")[0] in confirm_paths

        # confirm·sources 의 경로 표기
        for c in r.get("confirm") or []:
            p = str(c.get("path") or "")
            try:
                ci = ms.column_index(cols, p) if p else None
            except ValueError:
                ci = None
            if not ci:
                out.append(f"{i}행 confirm '{p}': 트리 경로가 열로 변환되지 않습니다(예: titleInfo[0].partNumber, name[1].alternativeName[0].namePart, identifier[1], extra.contents_price)")
            if not str(c.get("reason") or "").strip():
                out.append(f"{i}행 confirm '{p}': reason(왜 확인이 필요한지)이 없습니다")
            if not str(c.get("ask") or "").strip():
                out.append(f"{i}행 confirm '{p}': ask(직원이 무엇을 정해야 하는지)가 없습니다")
        for s in r.get("sources") or []:
            try:
                ms.parse_path(str(s.get("path") or ""))
            except ValueError:
                out.append(f"{i}행 sources '{s.get('path')}': 경로 표기가 틀렸습니다")

        # 폴더·이미지
        f = str(r.get("folder") or "")
        if folder is not None:
            if f not in subs:
                out.append(f"{i}행: folder '{f}' 에 해당하는 원고 하위 폴더가 없습니다")
            elif f in used_folders:
                out.append(f"{i}행: 폴더 '{f}' 가 두 번 쓰였습니다")
            else:
                used_folders.add(f)
                root = str(data.get("manuscripts_root") or "")
                if not vw.images(f"{root}/{f}"):
                    out.append(f"{i}행: 폴더 '{f}' 에 이미지가 없습니다")
                extra_files = vw.others(f"{root}/{f}")
                if extra_files:
                    out.append(f"{i}행: 폴더 '{f}' 에 이미지가 아닌 것이 있습니다(원문일괄등록이 멈춥니다): {extra_files[:3]}. arrange.set_aside 로 빼 두세요")
                # 관찰 파일: 회차마다, 본 이미지 = 폴더 이미지 전부
                if obs_dir:
                    op = Path(obs_dir) / f"{f}.json"
                    if not op.is_absolute():
                        op = (Path(data.get("_job_dir") or ".") / op)
                    if not op.exists():
                        out.append(f"{i}행: 관찰 파일이 없습니다: {op}. 회차 폴더의 이미지를 전부 보고 observations/<폴더>.json 을 만드세요")
                    else:
                        try:
                            ob = json.loads(op.read_text(encoding="utf-8"))
                        except json.JSONDecodeError as e:
                            out.append(f"{i}행: 관찰 파일이 JSON 으로 읽히지 않습니다: {op}: {e}"); ob = None
                        if ob is not None:
                            want = [p.name for p in vw.images(f"{root}/{f}")]
                            seen = [str(n) for n in ob.get("images_viewed") or []]
                            miss = [n for n in want if n not in seen]
                            if miss:
                                out.append(f"{i}행: 관찰 파일 {op.name} 의 images_viewed 에 폴더 이미지 {len(miss)}장이 없습니다(처음 {miss[:3]}). 전부 봐야 합니다")
                            pages = ob.get("pages") or []
                            if len(pages) < len(want):
                                out.append(f"{i}행: 관찰 파일 {op.name} 의 pages 가 {len(pages)}장뿐입니다(폴더 이미지 {len(want)}장). 장마다 기록하세요")
                            if reads is not None:
                                unread = [n for n in want if not _was_read(reads, n, f)]
                                if unread:
                                    out.append(f"{i}행: 관찰 파일에는 봤다고 적혔지만 실제 Read/look 호출 기록이 없는 이미지 {len(unread)}장(처음 {unread[:3]}). 목록만 적지 말고 실제로 열어 보세요")
                else:
                    out.append("observations_dir 가 없습니다. 회차마다 관찰 파일을 만들고 그 폴더를 적으세요")
        if r.get("color") not in ("천연색", "흑백"):
            out.append(f"{i}행: color 는 '천연색' 또는 '흑백'(매뉴얼 7.4)")

        # 표제
        ti = _lst(m.get("titleInfo"))
        t0 = _d(ti[0]) if ti else {}
        if not _t(t0.get("title")):
            out.append(f"{i}행: 본표제(titleInfo[0].title)가 비어 있습니다")
        for k, t in enumerate(ti):
            td = _d(t)
            tt = str(td.get("@type") or "")
            if tt not in TITLE_TYPES:
                out.append(f"{i}행: titleInfo[{k}].@type '{tt}' 는 Sample 선택값이 아닙니다(parallel 등)")
            if k > 0 and _t(td.get("title")) and not tt:
                out.append(f"{i}행: titleInfo[{k}] 에 표제가 있는데 @type 이 없습니다(대등표제는 parallel)")
        pn = _t(t0.get("partNumber"))
        if pn.isdigit() and not confirmed("titleInfo[0].partNumber") and "원문" not in src("titleInfo[0].partNumber"):
            out.append(f"{i}행: 권차 '{pn}' 는 단위 없는 숫자입니다. 가이드 1.3: 원문 표기 그대로('1화', '01회', '1권'). 원문에 정말 숫자만 있으면 sources 에 from '원문 <파일>' 을 적고, 아니면 표기를 맞추거나 confirm 에 넣으세요")
        parts.append((pn, _t(t0.get("partName"))))

        # 저자
        names = [_d(n) for n in _lst(m.get("name")) if _t(_d(n).get("namePart"))]
        if not names and not confirmed("name"):
            out.append(f"{i}행: 저자(name)가 없습니다")
        for k, n in enumerate(names):
            np_ = _t(n.get("namePart")); path = f"name[{k}]"
            if str(n.get("@type") or "") not in NAME_TYPES:
                out.append(f"{i}행 저자 '{np_}': @type 은 '개인명' 또는 '단체명'")
            if re.search(r"[\[\]]", np_) and "플랫폼" not in src(path):
                out.append(f"{i}행 저자 '{np_}': 각괄호는 플랫폼 화면에서만 확인한 저자에만 씁니다(가이드 2). sources 에 from '플랫폼 …' 이 없으면 각괄호를 빼세요")
            role = _t(_d(n.get("role")).get("roleTerm")) if n.get("role") is not None else ""
            if role and any(role == b or role.endswith(b) for b in ROLE_BAD):
                out.append(f"{i}행 저자 '{np_}': 역할어 '{role}' 는 관형형입니다. 명사형으로(가이드 2.3, 지은 → 지음)")
            acid = str(n.get("@ID") or "")
            if acid:
                if not re.fullmatch(r"KAC\d{9,}", acid):
                    out.append(f"{i}행 저자 '{np_}': @ID '{acid}' 는 전거 번호 꼴(KAC+숫자)이 아닙니다")
                if not str(n.get("@authority") or ""):
                    out.append(f"{i}행 저자 '{np_}': @ID 가 있으면 @authority(국립중앙도서관전거데이터)도 있어야 합니다")
                if "직원" not in src(path) and not _in_authority_cache(np_, acid, n):
                    out.append(f"{i}행 저자 '{np_}': 전거 번호 {acid} 가 전거 조회 결과(work/authority/<이름>.json)의 후보에 없습니다. authority 명령으로 조회한 후보 안의 번호만 쓸 수 있습니다(직원 결정이면 sources 의 from 을 '직원 결정'으로)")
            else:
                if not _authority_cache_exists(np_, n) and not confirmed(path) and "직원" not in src(path):
                    out.append(f"{i}행 저자 '{np_}': 전거 조회 기록(work/authority/<이름>.json)이 없습니다. authority 명령으로 조회하세요. 조회가 실패했으면 그 사실을 confirm({path}) 에 적으세요")
                if _t(n.get("displayForm")):
                    out.append(f"{i}행 저자 '{np_}': 전거를 연결하지 않았는데 디스플레이형식이 있습니다. 가이드 2.2: 전거형과 원문 표기가 다를 때만 씁니다")
            for a_k, a in enumerate(_lst(n.get("alternativeName"))):
                ad = _d(a)
                if not _t(ad.get("namePart")):
                    continue
                if str(ad.get("@type") or ad.get("@altType") or "") not in ALT_TYPES:
                    out.append(f"{i}행 저자 '{np_}' 다른이름[{a_k}]: @type 은 nickname / formal name / no specific type 중 하나")
                if "원문" not in src(f"{path}.alternativeName[{a_k}]") and "직원" not in src(f"{path}.alternativeName[{a_k}]"):
                    out.append(f"{i}행 저자 '{np_}' 다른이름 '{_t(ad.get('namePart'))}': 출처가 원문이 아닙니다(직원 답변 7·10: 다른이름은 원문에 있을 때만). sources 에 from '원문 <파일>' 과 quote 를 적거나 빼세요")

        # 출처정보
        oi = [_d(o) for o in _lst(m.get("originInfo"))]
        o0 = oi[0] if oi else {}
        pubs = [_t(p) for p in _lst(o0.get("publisher")) if _t(p)]
        if not pubs and not confirmed("originInfo[0].publisher[0]") and not confirmed("originInfo[0].publisher"):
            out.append(f"{i}행: 발행처(originInfo[0].publisher)가 비어 있습니다")
        for k, p in enumerate(pubs):
            if re.search(r"[\[\]]", p) and "[제작]" not in p:
                out.append(f"{i}행: 발행처 '{p}' 에 각괄호가 있습니다. 발행처에는 각괄호를 넣지 않습니다(직원 규칙 2026-10-01)")
            if re.search(r"\S\[제작\]", p):
                out.append(f"{i}행: '{p}' — 제작처 표기는 이름 뒤 한 칸 띄우고 [제작](가이드 5.2 예 '다온웹툰 [제작]')")
            if re.fullmatch(r"[A-Z][A-Z0-9&\s]{3,}", p) and not confirmed(f"originInfo[0].publisher[{k}]"):
                out.append(f"{i}행: 발행처 '{p}' 가 전부 대문자입니다. 가이드 5.2: 머리글자 약어가 아니면 각 단어 첫 글자만 대문자(KWBOOKS → Kwbooks). 약어가 맞으면 confirm 에 이유를 적으세요")
        if len(pubs) > 1:
            notes_text = " ".join(_t(_d(n).get("_")) if isinstance(n, dict) else _t(n) for n in _lst(m.get("note")))
            if not any(not str(_d(n).get("@type") or "") and _t(_d(n).get("_")) for n in _lst(m.get("note")) if isinstance(n, dict)) and not confirmed("note[0]"):
                out.append(f"{i}행: 발행처가 둘 이상({', '.join(pubs)})인데 관계를 설명하는 일반 주기(유형 없는 note)가 없습니다. 가이드 9: 임프린트·브랜드 관계는 일반 주기에(예 'A은 B의 임프린트임'). 모르면 confirm(note[0]) 에 넣으세요")
        d = _t(o0.get("dateIssued"))
        if d and not re.fullmatch(r"\d{8}|\d{6}-{2}|\d{4}-{4}", d):
            out.append(f"{i}행: 발행일 '{d}' 는 YYYYMMDD(모르는 자리는 -)")
        if not d and not confirmed("originInfo[0].dateIssued"):
            out.append(f"{i}행: 발행일(originInfo[0].dateIssued)이 비어 있습니다. 값을 넣거나 confirm 에 이유를 적으세요")
        pls = [_d(p) for p in _lst(o0.get("place"))]
        terms = [_d(p.get("placeTerm")) for p in pls if p.get("placeTerm") is not None]
        text_terms = [t for t in terms if str(t.get("@type") or "") == "text"]
        code_terms = [t for t in terms if str(t.get("@type") or "") == "code"]
        if not text_terms and not confirmed("originInfo[0].place[0].placeTerm"):
            out.append(f"{i}행: 발행지 글자(placeTerm @type text)가 없습니다")
        for t in code_terms:
            code = _t(t.get("_"))
            if code not in REGION_CODE.values():
                out.append(f"{i}행: 발행국 부호 '{code}' 는 부호표에 없습니다({', '.join(f'{k} {c}' for k, c in list(REGION_CODE.items())[:4])} …)")
            if str(t.get("@authority") or "") != "kormarccountry":
                out.append(f"{i}행: 발행국 부호 placeTerm 의 @authority 는 kormarccountry")
        if text_terms and not code_terms:
            out.append(f"{i}행: 발행지 글자는 있는데 발행국 부호(placeTerm @type code)가 없습니다")
        for k, o in enumerate(oi[1:], 1):
            if any(_t(p) for p in _lst(o.get("publisher"))) and not any(_d(p).get("placeTerm") for p in _lst(o.get("place"))):
                out.append(f"{i}행: 둘째 이후 출처정보[{k}] 에 발행처는 있는데 발행지가 없습니다. 가이드 5.2: 발행지가 다른 제작처를 따로 적는 묶음이므로 발행지를 넣으세요")
            if _t(o.get("dateIssued")):
                out.append(f"{i}행: 둘째 이후 출처정보[{k}] 에 발행일이 있습니다. 직원 답변 17: 발행일은 첫 출처정보에만")

        # 언어·형태
        lang = _d(_d(m.get("language")).get("languageTerm"))
        if _t(lang.get("_")) and _t(lang.get("_")) not in LANGS:
            out.append(f"{i}행: 언어 '{_t(lang.get('_'))}' 는 언어 부호가 아닙니다(kor, eng, jpn, chi …)")
        pd = _d(m.get("physicalDescription"))
        if _t(pd.get("extent")) and not EXTENT_RE.match(_t(pd.get("extent"))):
            out.append(f"{i}행: 수량 '{_t(pd.get('extent'))}' 꼴이 '이미지 파일 N개 (X MB) : 색' 이 아닙니다")
        if _t(pd.get("digitalOrigin")) and _t(pd.get("digitalOrigin")) not in ("BornDigital", "Born Digital", "born digital"):
            out.append(f"{i}행: digitalOrigin 은 BornDigital(예시 값)")
        ta = _t(m.get("targetAudience"))
        if ta and ta not in AUDIENCES:
            out.append(f"{i}행: 이용대상자 '{ta}' 는 양식의 선택값이 아닙니다({', '.join(AUDIENCES[:4])} …)")
        if not ta and not confirmed("targetAudience"):
            out.append(f"{i}행: 이용대상자(targetAudience)가 비어 있습니다")

        # 주기
        notes_l = [_d(n) for n in _lst(m.get("note"))]
        for k, n in enumerate(notes_l):
            nt = str(n.get("@type") or "")
            if nt not in NOTE_TYPES:
                out.append(f"{i}행: 주기[{k}] 유형 '{nt}' 는 쓰는 유형이 아닙니다(없음·target audience·acquisition·awards·funding)")
        if not any(str(n.get("@type") or "") == "acquisition" and _t(n.get("_")) for n in notes_l) and not confirmed("note"):
            out.append(f"{i}행: 입수처 주기(@type acquisition)가 없습니다")
        if not any(str(n.get("@type") or "") == "target audience" and _t(n.get("_")) for n in notes_l) and not confirmed("note"):
            out.append(f"{i}행: 이용대상자 주기(@type target audience)가 없습니다")

        # 주제명
        subs_l = [_d(s) for s in _lst(m.get("subject")) if _d(s)]
        if not subs_l:
            out.append(f"{i}행: 주제명(subject)이 하나도 없습니다. 일반주제명 만화[漫畵] KSH1998022212 + 장르주제명 웹툰[webtoon] KSH2016000049")
        for k, s in enumerate(subs_l):
            sid = str(s.get("@ID") or "")
            term = _t(s.get("topic")) or _t(s.get("genre"))
            if sid and not re.fullmatch(r"KSH\d{10}", sid):
                out.append(f"{i}행: 주제명[{k}] @ID '{sid}' 는 주제명 번호 꼴(KSH+숫자 10자리)이 아닙니다")
            if sid and not str(s.get("@authority") or ""):
                out.append(f"{i}행: 주제명[{k}] @ID 가 있으면 @authority(국립중앙도서관주제명표목표)도 있어야 합니다")
            pair = {"KSH1998022212": "만화[漫畵]", "KSH2016000049": "웹툰[webtoon]"}
            if sid in pair and term != pair[sid]:
                out.append(f"{i}행: 주제명[{k}] {sid} 의 표목은 '{pair[sid]}' 입니다(지금 '{term}')")
            if not term:
                out.append(f"{i}행: 주제명[{k}] 에 topic 또는 genre 글자가 없습니다")

        # 식별기호
        ids = [_d(x) for x in _lst(m.get("identifier")) if _t(_d(x).get("_"))]
        isbn_vals = [_t(x.get("_")) for x in ids if str(x.get("@type") or "").lower() == "isbn"]
        for k, idn in enumerate(ids):
            typ = str(idn.get("@type") or "").lower(); val = _t(idn.get("_"))
            if typ not in ID_TYPES:
                out.append(f"{i}행: 식별기호[{k}] @type '{typ}' 는 Sample 선택값이 아닙니다(isbn, uci …)")
            if typ == "isbn":
                if not val.isdigit():
                    out.append(f"{i}행: ISBN '{val}' 는 붙임표·공백·괄호 없이 숫자만")
                elif not _isbn13_ok(val) and not confirmed(f"identifier[{k}]"):
                    out.append(f"{i}행: ISBN '{val}' 의 검증 숫자가 맞지 않습니다. 확인하거나 confirm 에 넣으세요")
            if typ == "uci" and "http" not in src(f"identifier[{k}]") and "seoji" not in src(f"identifier[{k}]"):
                out.append(f"{i}행: UCI '{val}' 의 출처(서지정보유통지원시스템 검색 주소)가 sources 에 없습니다")
        if not isbn_vals and not confirmed("identifier[0]") and not confirmed("identifier"):
            out.append(f"{i}행: ISBN(identifier @type isbn)이 없습니다. 값을 넣거나 confirm 에 이유를 적으세요")
        for v in isbn_vals:
            isbns.append((v, confirmed("identifier[0]") or confirmed("identifier")))

        # 원문주소·접근제한
        urls = [_t(u) for u in _lst(_d(m.get("location")).get("url")) if _t(u)]
        if len(urls) < 2 and not confirmed("location.url"):
            out.append(f"{i}행: 원문주소가 {len(urls)}개입니다. 가이드 14.1: 연재처 메인(그 작품이 들어 있는 목록 페이지)과 작품 상세 둘 다. 연재처가 사라졌으면 비우고 confirm 에 이유")
        if urls and re.fullmatch(r"https?://[^/]+/?", urls[0]) and not confirmed("location.url[0]"):
            out.append(f"{i}행: 원문주소 1번 '{urls[0]}' 은 사이트 첫 화면입니다. 가이드 14.1: 그 작품이 들어 있는 목록 페이지(예 https://www.mrblue.com/comic)")
        lt = _t(_d(m.get("accessCondition")).get("licenseType"))
        if lt and lt not in LICENSE:
            out.append(f"{i}행: 접근제한 '{lt}' 는 0·1·2 중 하나")
        if ta == "성인용" and lt == "1" and not confirmed("accessCondition.licenseType"):
            out.append(f"{i}행: 성인물 접근제한 1 은 완료 사례 근거뿐이라 직원 확인 전입니다. confirm(accessCondition.licenseType) 에 넣으세요")

        # 양식 고유 칸(정가·보상)
        price, comp, yn = (str(x.get(k) if x.get(k) is not None else "").strip() for k in ("contents_price", "compensation", "reward_yn"))
        if price and not re.fullmatch(r"\d+", price):
            out.append(f"{i}행: 정가 '{price}' 는 숫자만")
        if not price and not confirmed("extra.contents_price"):
            out.append(f"{i}행: 정가(extra.contents_price)가 비어 있습니다")
        if yn not in ("", "Y", "N"):
            out.append(f"{i}행: 보상여부는 Y 또는 N")
        if price.isdigit():
            if comp.isdigit() and int(comp) != int(price):
                out.append(f"{i}행: 보상금 {comp} ≠ 정가 {price}. 보상금은 정가와 같습니다")
            if int(price) > 0 and comp.isdigit() and int(comp) > 0 and yn != "Y":
                out.append(f"{i}행: 정가와 보상금이 둘 다 있으면 보상여부는 Y")
            if int(price) > 0 and not comp and not confirmed("extra.compensation"):
                out.append(f"{i}행: 유료(정가 {price})인데 보상금이 비어 있습니다. 보상금 = 정가")
            if int(price) == 0 and yn != "N":
                out.append(f"{i}행: 무료 회차(정가 0)의 보상여부는 N")
        if str(x.get("currency_code") or "") not in ("", "\\"):
            out.append(f"{i}행: 통화는 '\\\\'(예시 값)")

        # 썸네일
        t = str(r.get("thumb_file") or "")
        if thumb_names is None and t and folder is not None:
            out.append(f"{i}행: 썸네일 폴더가 없는 납품인데 thumb_file 에 값이 있습니다(반입하면 0 Bytes 자리표시자 행이 생깁니다). 비우세요")
        tsrc = str(r.get("thumb_source") or "")
        if thumb_names is not None and t and t not in thumb_names and tsrc not in thumb_names:
            out.append(f"{i}행: 썸네일 파일이 썸네일 폴더에 없습니다(thumb_source '{tsrc}', thumb_file '{t}')")
        if thumb_names is not None and not t and not confirmed("extra.thum_files"):
            out.append(f"{i}행: 썸네일 폴더가 있는데 thumb_file 이 비어 있습니다")

    dup = sorted({p for p in parts if any(p) and parts.count(p) > 1})
    if dup:
        out.append(f"권차·권차표제가 같은 행이 있습니다: {dup[:5]}")
    shared = sorted({v for v, _ in isbns if sum(1 for y, _ in isbns if y == v) > 1})
    if shared and not all(c for v, c in isbns if v in shared):
        out.append(f"같은 ISBN 이 여러 행에 쓰였습니다: {shared[:3]}. 권·회차별 ISBN 을 찾아 넣거나, 끝내 세트 ISBN 뿐이면 그 행들 전부의 confirm(identifier[0]) 에 어디를 찾아봤는지 적으세요")
    if data.get("adult") not in (True, False, None):
        out.append("adult 는 true/false")
    if data.get("adult") and not str(data.get("adult_reason") or "").strip():
        out.append("adult 가 true 인데 adult_reason(근거)이 없습니다")
    if not out:
        rv = data.get("review") or {}
        if not rv.get("done"):
            out.append("검수를 아직 받지 않았습니다: reviewer 에이전트에게 맡기고, 지적을 처리한 뒤 review.done 을 true 로 하세요")
        elif len(rv.get("findings") or []) != len(rv.get("resolved") or []):
            out.append(f"검수 지적 {len(rv.get('findings') or [])}건 중 처리 기록이 {len(rv.get('resolved') or [])}건입니다")
    return out


# ---------------------------------------------------------------- 보조
def _lst(v) -> list:
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def _d(v) -> dict:
    if v is None:
        return {}
    return v if isinstance(v, dict) else {"_": v}


def _t(v) -> str:
    if v is None:
        return ""
    if isinstance(v, dict):
        return "" if v.get("_") is None else str(v["_"]).strip()
    if isinstance(v, list):
        return _t(v[0]) if v else ""
    return str(v).strip()


def _isbn13_ok(s: str) -> bool:
    if not re.fullmatch(r"\d{13}", s):
        return False
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(s[:12]))
    return (10 - total % 10) % 10 == int(s[12])


def _cache_file(name: str) -> Path:
    return AUTHORITY_CACHE / (re.sub(r"[\\/:*?\"<>|]+", "_", name) + ".json")


def _authority_cache_exists(name: str, node: dict) -> bool:
    for cand in (name, str(node.get("displayForm") or "")):
        if cand and _cache_file(cand).exists():
            try:
                d = json.loads(_cache_file(cand).read_text(encoding="utf-8"))
                if not d.get("error"):
                    return True
            except Exception:  # noqa: BLE001
                continue
    return False


def _in_authority_cache(name: str, acid: str, node: dict) -> bool:
    for cand in (name, str(node.get("displayForm") or "")):
        p = _cache_file(cand) if cand else None
        if p and p.exists():
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                continue
            if any(str(c.get("AC_CONTROL_NO") or "") == acid for c in d.get("candidates") or []):
                return True
    return False


def _was_read(reads: set[str], image_name: str, folder: str) -> bool:
    """실행기가 모은 Read/look 호출 경로에 그 이미지가 있는가(경로 끝 두 조각으로 대조)."""
    tail = f"{folder}/{image_name}".replace("\\", "/").lower()
    for p in reads:
        q = p.replace("\\", "/").lower()
        if q.endswith(tail) or q.endswith(image_name.lower()) and f"/{folder.lower()}/" in q:
            return True
    return False


def confirm_text(c: dict) -> str:
    parts = [str(c.get("reason") or "").strip()]
    for label, k in (("출판사 엑셀", "publisher_says"), ("근거", "evidence"), ("직원이 정할 것", "ask")):
        if str(c.get(k) or "").strip():
            parts.append(f"{label}: {str(c[k]).strip()}")
    return "\n".join(p for p in parts if p)


def write_xlsx(data: dict, folder: Path | None, out_xlsx: Path) -> dict:
    rows = materialize(data, folder)
    return ms.write({"rows": rows}, out_xlsx, confirm_text=confirm_text)


def main(import_json: str, reads_file: str | None = None) -> int:
    """에이전트용 명령 write-import: 검사하고, 막는 항목이 없으면 반입용 엑셀을 쓴다. job.json 에서 납품 폴더와 출력 경로를 읽는다."""
    p = Path(import_json)
    job = json.loads(p.with_name("job.json").read_text(encoding="utf-8"))
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"걸린 항목 1건:\n- import.json 을 읽지 못했습니다: {e}")
        return 1
    data["_job_dir"] = str(p.parent)
    reads = None
    if reads_file and Path(reads_file).exists():
        reads = set(json.loads(Path(reads_file).read_text(encoding="utf-8")))
    notes: list[str] = []
    fails = check(data, Path(job["folder"]), reads, notes)
    blocking = [f for f in fails if not f.startswith("검수")]
    if not blocking:
        r = write_xlsx(data, Path(job["folder"]), Path(job["output_xlsx"]))
        print(f"반입용 엑셀을 썼습니다: {r['out']} ({r['rows']}행, {r['columns']}열, 사람이 확인할 칸 {r['confirm']}개)")
    for n in notes:
        print(f"알림: {n}")
    if not fails:
        print("통과")
        return 0
    print(f"걸린 항목 {len(fails)}건:")
    for f in fails:
        print(f"- {f}")
    return 1
