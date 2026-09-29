"""반입용 엑셀(83열) 쓰기와 검사 — 형태가 정해진 부분이라 코드가 한다.

칸에 들어갈 **값은 에이전트가 정한다**(`import.json`). 이 파일이 하는 일:
  - 값을 양식의 정해진 열에 옮겨 쓴다(열 위치는 템플릿 1행에서 읽는다).
  - 웹툰 사업 고정값을 채운다(CONSTANTS: 양식과 완료 사례에서 항상 같은 값).
  - 이미지 수·용량을 실제 폴더에서 세어 수량(extent) 문구를 만든다.
  - 에이전트가 "사람이 확인할 칸"으로 지정한 칸을 노란색으로 칠하고 이유를 메모로 단다.
  - 검사한다: 파일 증거와 맞는가(행 수 = 폴더 수, 폴더·썸네일 파일이 실제로 있는가), 형식이 맞는가(날짜 8자리, 필수 칸).
    판단은 검사하지 않는다.
시트는 양식에 있는 Sample, Contents 둘뿐이다. 다른 시트를 덧붙이지 않는다(유저 확정 2026-09-29).
"""
from __future__ import annotations
import json, re, shutil
from pathlib import Path
import openpyxl
from openpyxl.comments import Comment
from openpyxl.styles import PatternFill
from .common import REGION_CODE, list_images, extent_string

HERE = Path(__file__).parent
TEMPLATE_83 = HERE / "templates" / "import_template_83.xlsx"
YELLOW = PatternFill("solid", fgColor="FFFF00")
Key = tuple[str, int]      # (열 이름, 같은 이름 중 몇 번째)

# 웹툰 사업 고정값(예시 양식·완료 사례에서 동일하게 확인된 값)
CONSTANTS: dict[Key, str] = {
    ("/mods/originInfo[@eventType]", 0): "publication",
    ("/mods/originInfo/place/placeTerm[@type]", 0): "text",
    ("/mods/originInfo/place/placeTerm[@authority]", 0): "kormarccountry",
    ("/mods/originInfo/place/placeTerm[@type]", 1): "code",
    ("/mods/originInfo/issuance", 0): "단행자료",
    ("/mods/language/languageTerm", 0): "kor",
    ("/mods/language/languageTerm[@authority]", 0): "iso639-2b",
    ("/mods/language/languageTerm[@type]", 0): "code",
    ("/mods/physicalDescription/form", 0): "전자자료(Image)",
    ("/mods/physicalDescription/reformattingQuality", 0): "access",
    ("/mods/physicalDescription/digitalOrigin", 0): "BornDigital",
    ("/mods/note[@type]", 1): "target audience",
    ("/mods/note[@type]", 2): "acquisition",
    ("/mods/subject/topic", 0): "만화",
    ("/mods/subject/topic", 1): "웹툰",
    ("/mods/classification", 0): "810",
    ("/mods/classification[@authority]", 0): "KDC",
    ("/mods/classification[@edition]", 0): "6",
    ("/mods/location/physicalLocation", 0): "국립중앙도서관",
    ("/mods/extension/regionOfPublishing", 0): "한국",
    ("/mods/typeOfResource", 0): "텍스트",
    ("/mods/genre", 0): "만화",
    ("currency_code", 0): "\\",
}

# 에이전트가 쓰는 항목 이름 → 양식의 열. 완료 사례(83열): 주기 1번째=기타, 2번째=이용대상, 3번째=수집처 / 원문주소 1번째=플랫폼 메인, 2번째=작품
FIELDS: dict[str, Key] = {
    "title": ("/mods/titleInfo/title", 0), "subTitle": ("/mods/titleInfo/subTitle", 0),
    "partNumber": ("/mods/titleInfo/partNumber", 0), "partName": ("/mods/titleInfo/partName", 0),
    "place": ("/mods/originInfo/place/placeTerm", 0), "place_code": ("/mods/originInfo/place/placeTerm", 1),
    "publisher": ("/mods/originInfo/publisher", 0), "dateIssued": ("/mods/originInfo/dateIssued", 0),
    "targetAudience": ("/mods/targetAudience", 0), "other_note": ("/mods/note", 0), "audience_note": ("/mods/note", 1),
    "acquisition_note": ("/mods/note", 2), "identifier": ("/mods/identifier", 0), "identifier_type": ("/mods/identifier[@type]", 0),
    "url_main": ("/mods/location/url", 0), "url_work": ("/mods/location/url", 1), "licenseType": ("/mods/accessCondition/licenseType", 0),
    "price": ("contents_price", 0), "compensation": ("compensation", 0), "reward_yn": ("reward_yn", 0),
}
NAME_KEYS = [{"name": ("/mods/name/namePart", i), "type": ("/mods/name[@type]", i), "role": ("/mods/name/role/roleTerm", i)} for i in range(3)]
COMPUTED = {"extent": ("/mods/physicalDescription/extent", 0), "format": ("/mods/physicalDescription/internetMediaType", 0), "thumb_file": ("thum_files", 0)}
REQUIRED = ["title", "publisher", "place", "place_code", "dateIssued", "targetAudience", "audience_note", "acquisition_note", "identifier",
            "url_main", "url_work", "licenseType", "price", "reward_yn"]
AUDIENCES = ("고등학생", "성인용", "아동용", "일반이용자", "중학생", "초등학생", "취학전아동", "취학전 아동", "특수계층", "미상")


KOREAN = {"title": "본표제", "subTitle": "표제관련정보", "partNumber": "권차", "partName": "권차표제", "place": "발행지", "place_code": "발행국 부호",
          "publisher": "발행처", "dateIssued": "발행일", "targetAudience": "이용대상자", "other_note": "주기", "audience_note": "이용대상자 주기",
          "acquisition_note": "입수처 주기", "identifier": "식별기호", "identifier_type": "식별기호 유형", "url_main": "원문주소(플랫폼 메인)",
          "url_work": "원문주소(작품)", "licenseType": "접근제한유형", "price": "정가", "compensation": "보상금", "reward_yn": "보상여부",
          "names": "저자명", "color": "수량(크기)의 색", "thumb_file": "썸네일 파일명", "extent": "수량(크기)", "format": "디지털 자료유형"}


def column_label(name: str) -> str:
    """사람에게 보여 줄 칸 이름: 반입용 엑셀의 열 이름(MODS) 기준, 한글은 괄호 안. 같은 열 이름이 여러 번 나오면 몇 번째인지 붙인다."""
    key = FIELDS.get(name) or COMPUTED.get(name) or {"names": NAME_KEYS[0]["name"], "color": COMPUTED["extent"]}.get(name)
    if not key:
        return name
    repeated = sum(1 for k in list(FIELDS.values()) + list(COMPUTED.values()) + [n["name"] for n in NAME_KEYS] if k[0] == key[0]) > 1
    head = key[0] + (f" #{key[1] + 1}" if repeated else "")
    return f"{head} ({KOREAN.get(name, name)})"


def _columns(ws) -> dict[Key, int]:
    header = [(c.value or "").strip() if isinstance(c.value, str) else "" for c in ws[1]]
    out, seen = {}, {}
    for i, h in enumerate(header):
        out[(h, seen.get(h, 0))] = i + 1
        seen[h] = seen.get(h, 0) + 1
    return out


def field_names() -> list[str]:
    return [*FIELDS, "names", "color", "thumb_file"]


def check(data: dict, folder: Path) -> list[str]:
    """import.json 을 파일 증거·형식과 대조한다. 걸린 항목 목록(비어 있으면 통과)."""
    out = []
    rows = data.get("rows") or []
    if not rows:
        return ["rows 가 비어 있습니다"]
    ms = folder / str(data.get("manuscripts_root") or "")
    if not data.get("manuscripts_root") or not ms.is_dir():
        return [f"원고 폴더(manuscripts_root)가 없습니다: {data.get('manuscripts_root')!r}"]
    subs = {p.name: p for p in ms.iterdir() if p.is_dir() and not p.name.startswith("_kolis")}
    if len(rows) != len(subs):
        out.append(f"자료 {len(rows)}행 ≠ 원고 하위 폴더 {len(subs)}개")
    stray = [p.name for p in ms.iterdir() if p.is_file()]
    if stray:
        out.append(f"원고 폴더 바로 아래에 파일이 있습니다(원문일괄등록이 멈춥니다): {stray[:3]}")
    th = str(data.get("thumbs_dir") or "")
    names = {p.name for p in (folder / th).iterdir() if p.is_file()} if th and (folder / th).is_dir() else None
    if th and names is None:
        out.append(f"썸네일 폴더가 없습니다: {th}")
    used, parts = set(), []
    for i, r in enumerate(rows, 1):
        v = r.get("values") or {}
        confirm = {str(c.get("field")) for c in r.get("confirm") or [] if str(c.get("reason") or "").strip()}
        for c in r.get("confirm") or []:
            if str(c.get("field")) not in field_names():
                out.append(f"{i}행 confirm: '{c.get('field')}' 는 없는 항목 이름입니다. 쓸 수 있는 이름: {', '.join(field_names())}")
            if not str(c.get("reason") or "").strip():
                out.append(f"{i}행 confirm '{c.get('field')}': 이유가 없습니다")
        unknown = [k for k in v if k not in field_names()]
        if unknown:
            out.append(f"{i}행 values: 없는 항목 이름 {unknown}. 쓸 수 있는 이름: {', '.join(field_names())}")
        f = str(r.get("folder") or "")
        if f not in subs:
            out.append(f"{i}행: folder '{f}' 에 해당하는 원고 하위 폴더가 없습니다")
        elif f in used:
            out.append(f"{i}행: 폴더 '{f}' 가 두 번 쓰였습니다")
        else:
            used.add(f)
            if not list_images(subs[f]):
                out.append(f"{i}행: 폴더 '{f}' 에 이미지가 없습니다")
        for k in REQUIRED:
            if str(v.get(k) if v.get(k) is not None else "").strip() == "" and k not in confirm:
                out.append(f"{i}행: '{k}' 가 비어 있습니다. 값을 넣거나, 정할 수 없으면 confirm 에 이유와 함께 넣으세요")
        ns = [n for n in v.get("names") or [] if str(n.get("name") or "").strip()]
        if not ns and "names" not in confirm:
            out.append(f"{i}행: 저자(names)가 없습니다")
        if len(ns) > 3:
            out.append(f"{i}행: 저자가 {len(ns)}명입니다. 반입 양식은 3명까지입니다(나머지는 구축 단계에서 추가하도록 confirm 에 적으세요)")
        for n in ns:
            if n.get("type") not in ("개인명", "단체명"):
                out.append(f"{i}행 저자 '{n.get('name')}': type 은 '개인명' 또는 '단체명'")
        d = str(v.get("dateIssued") or "")
        if d and not re.fullmatch(r"\d{8}", d):
            out.append(f"{i}행: dateIssued '{d}' 는 숫자 8자리(YYYYMMDD)여야 합니다")
        if v.get("color") not in ("천연색", "흑백"):
            out.append(f"{i}행: color 는 '천연색' 또는 '흑백'(매뉴얼 7.4)")
        if str(v.get("targetAudience") or "") and v.get("targetAudience") not in AUDIENCES:
            out.append(f"{i}행: targetAudience '{v.get('targetAudience')}' 는 양식의 선택값이 아닙니다({', '.join(AUDIENCES[:4])} …)")
        code = str(v.get("place_code") or "")
        if code and code not in REGION_CODE.values():
            out.append(f"{i}행: place_code '{code}' 는 발행국 부호 표에 없습니다({', '.join(f'{k} {c}' for k, c in list(REGION_CODE.items())[:4])} …)")
        if str(v.get("price") or "").strip() and not re.fullmatch(r"\d+", str(v.get("price")).strip()):
            out.append(f"{i}행: price '{v.get('price')}' 는 숫자만")
        if str(v.get("reward_yn") or "") not in ("", "Y", "N"):
            out.append(f"{i}행: reward_yn 은 Y 또는 N")
        ident = re.sub(r"[\s-]", "", str(v.get("identifier") or ""))
        if str(v.get("identifier_type") or "").lower() == "isbn" and ident and not _isbn13_ok(ident) and "identifier" not in confirm:
            out.append(f"{i}행: ISBN '{v.get('identifier')}' 의 검증 숫자가 맞지 않습니다. 확인하거나 confirm 에 넣으세요")
        t = str(r.get("thumb_file") or "")
        if names is None and t:
            out.append(f"{i}행: 썸네일 폴더가 없는 납품인데 thumb_file 에 값이 있습니다(반입하면 0 Bytes 자리표시자 행이 생깁니다). 비우세요")
        src = str(r.get("thumb_source") or "")
        if names is not None and t and t not in names and src not in names:
            out.append(f"{i}행: 썸네일 파일이 썸네일 폴더에 없습니다(thumb_source '{src}', thumb_file '{t}')")
        if names is not None and not t and "thumb_file" not in confirm:
            out.append(f"{i}행: 썸네일 폴더가 있는데 thumb_file 이 비어 있습니다")
        parts.append((str(v.get("partNumber") or ""), str(v.get("partName") or "")))
    dup = sorted({p for p in parts if any(p) and parts.count(p) > 1})
    if dup:
        out.append(f"권차·권차표제가 같은 행이 있습니다: {dup[:5]}")
    if not out:
        rv = data.get("review") or {}
        if not rv.get("done"):
            out.append("검수를 아직 받지 않았습니다: reviewer 에이전트에게 맡기고, 지적을 처리한 뒤 review.done 을 true 로 하세요")
        elif len(rv.get("findings") or []) != len(rv.get("resolved") or []):
            out.append(f"검수 지적 {len(rv.get('findings') or [])}건 중 처리 기록이 {len(rv.get('resolved') or [])}건입니다")
    return out


def _isbn13_ok(s: str) -> bool:
    if not re.fullmatch(r"\d{13}", s):
        return False
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(s[:12]))
    return (10 - total % 10) % 10 == int(s[12])


def write(data: dict, folder: Path, out_xlsx: Path, template: Path = TEMPLATE_83) -> dict:
    """반입용 엑셀을 쓴다. 돌려주는 것: {'rows', 'confirm'(노란 칸 수), 'out'}."""
    out_xlsx = Path(out_xlsx)
    out_xlsx.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(template, out_xlsx)
    wb = openpyxl.load_workbook(out_xlsx)
    ws = wb["Contents"]
    col = _columns(ws)
    if ws.max_row >= 2:
        ws.delete_rows(2, ws.max_row - 1)
    ms = folder / str(data["manuscripts_root"])
    nconfirm = 0
    for r in data["rows"]:
        v = r.get("values") or {}
        cells: dict[Key, object] = dict(CONSTANTS)
        for name, key in FIELDS.items():
            val = v.get(name)
            if val is not None and str(val).strip() != "":
                cells[key] = int(val) if name in ("price", "compensation") and re.fullmatch(r"\d+", str(val).strip()) else str(val).strip()
        for i, n in enumerate([n for n in v.get("names") or [] if str(n.get("name") or "").strip()][:3]):
            cells[NAME_KEYS[i]["name"]] = str(n["name"]).strip()
            cells[NAME_KEYS[i]["type"]] = n.get("type") or "개인명"
            if str(n.get("role") or "").strip():
                cells[NAME_KEYS[i]["role"]] = str(n["role"]).strip()
            if i == 0:
                cells[("/mods/name[@usage]", 0)] = "primary"
        imgs = list_images(ms / str(r["folder"]))
        cells[COMPUTED["extent"]] = extent_string(len(imgs), sum(p.stat().st_size for p in imgs), v.get("color") or "천연색")
        exts = {p.suffix.lower().lstrip(".") for p in imgs}
        cells[COMPUTED["format"]] = "JPG" if exts <= {"jpg"} else "JPEG" if exts <= {"jpeg", "jpg"} else sorted(exts)[0].upper()
        if str(r.get("thumb_file") or "").strip():
            cells[COMPUTED["thumb_file"]] = str(r["thumb_file"]).strip()
        ws.append([None] * ws.max_column)
        rn = ws.max_row
        for key, val in cells.items():
            if key in col:
                ws.cell(row=rn, column=col[key]).value = val
        for c in r.get("confirm") or []:
            name = str(c.get("field"))
            key = FIELDS.get(name) or COMPUTED.get(name) or {"names": NAME_KEYS[0]["name"], "color": COMPUTED["extent"]}.get(name)
            if key in col:
                cell = ws.cell(row=rn, column=col[key])
                cell.fill = YELLOW
                prev = cell.comment.text + "\n" if cell.comment else ""
                cell.comment = Comment((prev + str(c.get("reason")))[:2000], "kolis_tool")
                nconfirm += 1
    for name in wb.sheetnames:
        if name not in ("Sample", "Contents"):
            del wb[name]
    wb.save(out_xlsx)
    return {"rows": len(data["rows"]), "confirm": nconfirm, "out": str(out_xlsx)}


def main(import_json: str) -> int:
    """에이전트용 명령: 검사하고, 통과한 형식이면 반입용 엑셀을 쓴다. job.json 에서 납품 폴더와 출력 경로를 읽는다."""
    p = Path(import_json)
    job = json.loads(p.with_name("job.json").read_text(encoding="utf-8"))
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"걸린 항목 1건:\n- import.json 을 읽지 못했습니다: {e}")
        return 1
    fails = check(data, Path(job["folder"]))
    blocking = [f for f in fails if not f.startswith("검수")]
    if not blocking:
        r = write(data, Path(job["folder"]), Path(job["output_xlsx"]))
        print(f"반입용 엑셀을 썼습니다: {r['out']} ({r['rows']}행, 사람이 확인할 칸 {r['confirm']}개)")
    if not fails:
        print("통과")
        return 0
    print(f"걸린 항목 {len(fails)}건:")
    for f in fails:
        print(f"- {f}")
    return 1
