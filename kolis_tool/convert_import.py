"""③ 반입용 기초메타데이터 작성(규칙 부분).

입력: 출판사용 기초메타데이터 xlsx('작성' 시트, 23열), 원문 폴더(선택, extent 계산·폴더 매칭용)
출력: KOLIS 반입용 xlsx (예시 양식을 템플릿으로 복사해 Contents 시트 3행부터 채움)

규칙으로 확정되는 열은 채우고, 사람이나 LLM이 봐야 하는 열은 비우거나 노란색으로 표시한다.
노란색 = 확인 필요. 셀 메모에 이유를 적는다.
LLM 보완 단계(agent)는 이 파일의 노란 셀만 대상으로 한다.
"""
from __future__ import annotations
import json, re, shutil
from dataclasses import dataclass, field
from pathlib import Path
import openpyxl
from openpyxl.comments import Comment
from openpyxl.styles import PatternFill
from .common import ROLE_WORDS, CORPORATE_HINTS, region_code_from_place, list_images, extent_string, resolve_folder

HERE = Path(__file__).parent
YELLOW = PatternFill("solid", fgColor="FFFF00")

# 열 키 = (경로, n번째 등장). 실제 열 위치는 템플릿 파일 1행에서 읽는다(예시 양식 77열, 완료 사례 88열로 다름).
Key = tuple[str, int]

def K(path: str, n: int = 0) -> Key:
    return (path, n)

NAME_BLOCKS = [
    {"namePart": K("/mods/name/namePart", 0), "type": K("/mods/name[@type]", 0), "role": K("/mods/name/role/roleTerm", 0), "usage": K("/mods/name[@usage]", 0)},
    {"namePart": K("/mods/name/namePart", 1), "type": K("/mods/name[@type]", 1), "role": K("/mods/name/role/roleTerm", 1)},
    {"namePart": K("/mods/name/namePart", 2), "type": K("/mods/name[@type]", 2), "role": K("/mods/name/role/roleTerm", 2)},
]

# 웹툰 사업 고정값(예시 양식·완료 사례 두 곳에서 동일하게 확인된 값)
CONSTANTS: dict[Key, str] = {
    K("/mods/originInfo[@eventType]"): "publication",
    K("/mods/originInfo/place/placeTerm[@type]", 0): "text",
    K("/mods/originInfo/place/placeTerm[@authority]", 0): "kormarccountry",
    K("/mods/originInfo/place/placeTerm[@type]", 1): "code",
    K("/mods/originInfo/issuance", 0): "단행자료",
    K("/mods/language/languageTerm"): "kor",
    K("/mods/language/languageTerm[@authority]"): "iso639-2b",
    K("/mods/language/languageTerm[@type]"): "code",
    K("/mods/physicalDescription/form"): "전자자료(Image)",
    K("/mods/physicalDescription/reformattingQuality"): "access",
    K("/mods/physicalDescription/digitalOrigin"): "BornDigital",
    K("/mods/targetAudience"): "일반이용자",
    K("/mods/note", 0): "전체이용가",
    K("/mods/note[@type]", 0): "target audience",
    K("/mods/note", 1): "한국웹툰산업협회를 통해 수집한 자료임",   # 완료 사례·추출 예시 모두 동일. 수집 경로가 다르면 현장에서 바꿀 것
    K("/mods/note[@type]", 1): "acquisition",
    K("/mods/subject/topic"): "만화",
    K("/mods/classification"): "810",
    K("/mods/classification[@authority]"): "KDC",
    K("/mods/classification[@edition]"): "6",
    K("/mods/location/physicalLocation"): "국립중앙도서관",
    K("/mods/accessCondition/licenseType"): "2",
    K("/mods/extension/regionOfPublishing"): "한국",
    K("/mods/typeOfResource"): "텍스트",
    K("/mods/genre"): "만화",
    K("currency_code"): "\\",
}

def C(path: str, n: int = 0) -> Key:   # 이전 이름 호환
    return K(path, n)

PUB_COLS = ["No", "ISBN/UCI", "제목(도서명)", "권차", "출판사", "기본설정자료유형", "기본설정\n장르", "주제 구분", "저자",
            "발행연월일", "파일형식", "기본설정\n언어", "이용대상", "형태사항\n(컬러/흑백)", "총 파일갯수", "정가", "보상여부",
            "파일명", "도서정보 및 소개", "목차", "표지파일명", "썸네일", "비고"]


@dataclass
class Flag:
    col: Key
    reason: str


@dataclass
class Row:
    values: dict = field(default_factory=dict)      # Key → value
    flags: list[Flag] = field(default_factory=list)
    source: dict = field(default_factory=dict)

    def set(self, col: Key, v):
        self.values[col] = v

    def flag(self, col: Key, reason: str):
        self.flags.append(Flag(col, reason))


def norm_key(k) -> str:
    return re.sub(r"\s+", "", str(k or ""))


def read_publisher_sheet(path: Path) -> list[dict]:
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb["작성"] if "작성" in wb.sheetnames else wb.worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    # 헤더 행 찾기: 'No' 와 '제목' 이 있는 행
    hi = next(i for i, r in enumerate(rows) if r and any(norm_key(c) == "No" for c in r))
    header = [norm_key(c) for c in rows[hi]]
    out = []
    for r in rows[hi + 1:]:
        if not r or all(v is None or str(v).strip() == "" for v in r):
            continue
        d = {header[i]: r[i] for i in range(min(len(header), len(r)))}
        if not d.get("제목(도서명)"):
            continue
        out.append(d)
    return out


def parse_authors(raw) -> list[tuple[str, str]]:
    """'MUSK 그림\\n이상 글' / '강구' / '글 홍길동, 그림 김철수' → [(이름, 역할)]"""
    if raw is None:
        return []
    text = str(raw).replace("／", "/").replace("：", ":").strip()
    parts = re.split(r"[\n,;/]+", text)
    out = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        role = None
        m = re.match(r"^\s*(" + "|".join(map(re.escape, sorted(ROLE_WORDS, key=len, reverse=True))) + r")\s*:\s*(.+)$", p)   # '글: 기범' (enrich 형식)
        if m:
            out.append((m.group(2).strip(), m.group(1))); continue
        for rw in sorted(ROLE_WORDS, key=len, reverse=True):
            if p.endswith(" " + rw) or p.endswith(rw) and len(p) > len(rw) and p[-len(rw) - 1] in " ":
                role = rw; p = p[: -len(rw)].strip(); break
            if p.startswith(rw + " "):
                role = rw; p = p[len(rw):].strip(); break
        out.append((p, role or ""))
    return out


def name_type(name: str) -> str:
    low = name.lower()
    return "단체명" if any(h.lower() in low for h in CORPORATE_HINTS) else "개인명"


def guess_place(publisher: str, place_hint: str | None, lookup: dict[str, str]) -> tuple[str | None, str | None]:
    place = place_hint or lookup.get(publisher)
    if not place:
        return None, None
    return place, region_code_from_place(place)


def build_row(pub: dict, folder: Path | None, publisher_place: dict[str, str], work: dict | None = None,
              n_notes: int = 2, n_topics: int = 1, n_urls: int = 1) -> Row:
    """work: enrich 가 만든 작품 정보 JSON(URL·이용등급·발행지). 템플릿마다 note/subject/url 열 수가 달라 위치를 맞춘다.
    완료 사례(83열, 5차-190/201/206): note#0 기타(한자표제 등), note#1 이용대상, note#2 수집처 / subject/topic 2개(만화, 웹툰) / url 2개(플랫폼 메인, 작품)."""
    work = work or {}
    r = Row(); r.source = pub
    ta = 1 if n_notes >= 3 else 0          # target audience 주기 위치
    for col, v in CONSTANTS.items():
        if col[0] == "/mods/note" or col[0] == "/mods/note[@type]":
            continue
        r.set(col, v)
    r.set(K("/mods/note", ta), "전체이용가"); r.set(K("/mods/note[@type]", ta), "target audience")
    r.set(K("/mods/note", ta + 1), CONSTANTS[K("/mods/note", 1)]); r.set(K("/mods/note[@type]", ta + 1), "acquisition")
    if n_topics >= 2:
        r.set(K("/mods/subject/topic", 1), "웹툰")
    # 원문주소: 플랫폼 메인 + 작품 페이지(매뉴얼 14.1). enrich JSON 의 최초 연재 플랫폼 항목 우선
    plats = [p for p in (work.get("platforms") or []) if p.get("url_work")]
    # 원문주소는 지금 서비스 중인 페이지여야 한다(매뉴얼 14.1: 연재처 소멸 시 기재하지 않음).
    # 우선순위: 회차 목록을 실제로 수집한 플랫폼 > 최초 연재 플랫폼 > 첫 항목
    live = {e.get("source") for e in (work.get("episodes") or []) if e.get("source")}
    first = (next((p for p in plats if p["name"] in live), None)
             or next((p for p in plats if p.get("name") == work.get("platform_first")), None) or (plats[0] if plats else {}))
    if first.get("url_main"):
        r.set(K("/mods/location/url", 0), first["url_main"])
    if first.get("url_work") and n_urls >= 2:
        r.set(K("/mods/location/url", 1), first["url_work"])
    if first and first.get("name") != work.get("platform_first"):
        r.flag(K("/mods/location/url", 0), f"최초 연재 플랫폼 '{work.get('platform_first')}' 은 현재 접속 불가로 보여 '{first.get('name')}' 주소를 씀. 확인")
    # 성인용: 이용대상자 성인용 + 주기 '19세 미만 구독불가' + 공개여부 1 (완료 사례 5-190, 가이드 이용대상자 절)
    adult = bool(work.get("adult")) or str(work.get("rating", "")).startswith("19") or "성인" in str(work.get("rating", ""))
    if adult:
        r.set(K("/mods/targetAudience"), "성인용"); r.set(K("/mods/note", ta), "19세 미만 구독불가")
        r.set(K("/mods/accessCondition/licenseType"), "1")
        by = ", ".join(f"{k}={v or '?'}" for k, v in (work.get("rating_by_platform") or {}).items())
        r.flag(K("/mods/targetAudience"), f"플랫폼 이용등급 '{work.get('rating')}' 로 성인용 처리(공개여부 1, 주기 '19세 미만 구독불가'). "
                                          f"출판사 기재 '{pub.get('이용대상')}', 플랫폼별 {by or '미확인'} — 엇갈리면 직원 확인")
    if work.get("publisher_place") and not publisher_place.get(str(pub.get("출판사") or "").strip()):
        publisher_place = dict(publisher_place, **{str(pub.get("출판사") or "").strip(): f"[{work['publisher_place']}]"})
    title = str(pub.get("제목(도서명)") or "").strip()
    r.set(C("/mods/titleInfo/title", 0), title)
    r.flag(C("/mods/titleInfo/title", 0), "표제: 원문 표지/크레딧과 대조. 시즌·외전 문구는 표제관련정보로, 부제는 subTitle로 분리(가이드 1.1~1.2)")
    vol = pub.get("권차")
    fname_part = part_from_filename(str(pub.get("파일명") or ""))
    if fname_part and re.search(r"외전|프롤로그|에필로그|특별편|번외", fname_part):
        r.set(C("/mods/titleInfo/partName", 0), fname_part)
        r.flag(C("/mods/titleInfo/partName", 0), f"파일명 기준 '{fname_part}' → 권차 대신 권차표제(가이드 1.3~1.4). 원문 표기(회/화, 최종회)로 확정")
    elif fname_part:
        r.set(C("/mods/titleInfo/partNumber", 0), fname_part)
        # 완료 사례: 파일명은 '07화'인데 원문 표기는 '07회', 마지막 회차는 '최종회 (완결)'. 파일명은 힌트일 뿐 원문이 으뜸정보원.
        r.flag(C("/mods/titleInfo/partNumber", 0), f"파일명 기준 '{fname_part}'. 원문 타이틀컷 표기(회/화, 최종회 등)로 확정")
    elif vol is not None and str(vol).strip() != "":
        v = str(vol).strip()
        r.set(C("/mods/titleInfo/partNumber", 0), f"{v}화" if v.isdigit() else v)   # 완료 사례 5-201: '1화'. 5-190 은 '1' — 원문 표기로 확정
        r.flag(C("/mods/titleInfo/partNumber", 0), "권차는 원문 타이틀컷 표기로 확정('1화'/'01회'/'최종화'). 외전·프롤로그는 권차 비우고 권차표제(partName)에")
    else:
        r.flag(C("/mods/titleInfo/partNumber", 0), "권차 비어 있음: 원문에서 회차 확인(프롤로그·에필로그는 권차 대신 권차표제)")
    # 저자
    authors = parse_authors(pub.get("저자"))
    if not authors:
        r.flag(NAME_BLOCKS[0]["namePart"], "저자 없음: 원문 크레딧면에서 확인")
    for i, (name, role) in enumerate(authors[:3]):
        b = NAME_BLOCKS[i]
        r.set(b["namePart"], name); r.set(b["type"], name_type(name)); r.set(b["role"], role or None)
        if i == 0:
            r.set(b["usage"], "primary")
        if not role:
            r.flag(b["role"], "역할어 없음: 원문 크레딧면에서 글/그림/원작 확인")
        if re.search(r"[A-Z]{2,}", name):
            r.flag(b["namePart"], "영문 대문자 연속: 필명이면 정상, 아니면 대소문자 규칙 확인")
        if name_type(name) == "단체명":
            r.flag(b["type"], "단체명으로 추정: 확인")
    if len(authors) > 3:
        r.flag(NAME_BLOCKS[2]["namePart"], f"저자 {len(authors)}명: 반입 양식은 3명까지, 나머지는 구축 단계에서 추가")
    # 발행
    publisher = str(pub.get("출판사") or "").strip()
    r.set(C("/mods/originInfo/publisher", 0), publisher)
    if not publisher:
        r.flag(C("/mods/originInfo/publisher", 0), "발행처 없음")
    place, code = guess_place(publisher, None, publisher_place)
    r.set(C("/mods/originInfo/place/placeTerm", 0), place)
    r.set(C("/mods/originInfo/place/placeTerm", 1), code)
    if not place:
        r.flag(C("/mods/originInfo/place/placeTerm", 0), "발행지 미상: 판권면/출판사 홈페이지/플랫폼에서 확인. 플랫폼 출처면 [각괄호]")
    elif not code:
        r.flag(C("/mods/originInfo/place/placeTerm", 1), f"발행지 '{place}' 의 KORMARC 코드 미확정")
    date = re.sub(r"\D", "", str(pub.get("발행연월일") or ""))
    if hasattr(pub.get("발행연월일"), "strftime"):
        date = pub["발행연월일"].strftime("%Y%m%d")
    r.set(C("/mods/originInfo/dateIssued", 0), date or None)
    if len(date) != 8:
        r.flag(C("/mods/originInfo/dateIssued", 0), f"발행일 8자리 아님: '{pub.get('발행연월일')}' (빈 자리는 - 로)")
    # 형태
    fmt = str(pub.get("파일형식") or "").strip().upper()
    r.set(C("/mods/physicalDescription/internetMediaType"), fmt or None)
    if fmt not in ("JPG", "JPEG"):
        r.flag(C("/mods/physicalDescription/internetMediaType"), f"파일형식 '{fmt}': 지침은 JPG/JPEG")
    color_raw = str(pub.get("형태사항(컬러/흑백)") or "")
    color = "단색" if "흑백" in color_raw else "천연색"
    count = pub.get("총파일갯수")
    if folder is not None:
        imgs = list_images(folder)
        nbytes = sum(p.stat().st_size for p in imgs)
        r.set(C("/mods/physicalDescription/extent"), extent_string(len(imgs), nbytes, color))
        if count and int(count) != len(imgs):
            r.flag(C("/mods/physicalDescription/extent"), f"출판사 기재 {count}개 vs 실제 {len(imgs)}개 불일치")
    else:
        r.set(C("/mods/physicalDescription/extent"), f"이미지 파일 {count or ''}개 ( MB) : {color}")
        r.flag(C("/mods/physicalDescription/extent"), "원문 폴더 미연결: 용량(MB) 계산 못함")
    # 이용대상
    aud = str(pub.get("이용대상") or "").strip()
    if aud and aud not in ("일반", "전체", "전체이용가", "전연령") and not adult:
        m = re.search(r"(\d{2})", aud)
        r.set(C("/mods/note", ta), f"{m.group(1)}세 이용가" if m else aud)   # 완료 사례: '15세' → '15세 이용가'
        r.flag(C("/mods/note", ta), f"이용대상 '{aud}': 주기 문구 확인(완료 사례 표기 '15세 이용가')")
    r.flag(C("/mods/location/url"), "원문주소: 플랫폼 메인 + 작품 페이지(매뉴얼 14.1). enrich JSON 값이면 플랫폼 페이지에서 확인")
    # 식별기호
    ident = re.sub(r"[\s-]", "", str(pub.get("ISBN/UCI") or ""))
    if re.fullmatch(r"97[89]\d{10}", ident):
        r.set(C("/mods/identifier"), ident); r.set(C("/mods/identifier[@type]"), "isbn")
        if not isbn13_ok(ident):
            r.flag(C("/mods/identifier"), "ISBN-13 체크섬 불일치")
    elif ident:
        r.flag(C("/mods/identifier"), f"'{ident}': ISBN 아님. UCI면 반입 시 등록 불가, 구축 단계에서 직접 입력(가이드 5.3)")
    else:
        r.flag(C("/mods/identifier"), "식별기호 없음")
    # 주제
    subj = pub.get("주제구분")
    # 완료 사례(BL 작품 5-190 포함) 모두 topic = 만화 / 웹툰. 출판사 '주제 구분'(BL·로맨스 등)은 반입 값이 아니라 메모로만
    r.flag(C("/mods/subject/topic"), f"주제명: 완료 사례는 '만화'+'웹툰'. 출판사 주제 구분 '{subj or ''}' 은 구축 단계 주제명표목표 연결 때 참고")
    # 가격·보상
    price_raw = pub.get("정가")
    price = int(re.sub(r"\D", "", str(price_raw))) if price_raw not in (None, "") and re.sub(r"\D", "", str(price_raw)) else None
    if price is None and price_raw not in (None, ""):
        r.flag(C("contents_price"), f"정가 '{price_raw}': 숫자 아님(무료면 플랫폼 유통가 확인, 완료 사례는 무료 회차도 500 기재)")
    r.set(C("contents_price"), price)
    reward_raw = str(pub.get("보상여부") or "")
    reward = "N" if ("안함" in reward_raw or "무보상" in reward_raw or reward_raw.strip().upper() == "N") else ("Y" if reward_raw else None)
    if reward == "N" and price:
        # 완료 사례 5-190/201/206(케나즈 '보상안함')도 반입용은 보상여부 Y·보상금=정가 로 반입돼 가원부 발급됨. 그 관행을 따르되 사람 확인
        r.set(C("reward_yn"), "Y"); r.set(C("compensation"), price)
        r.flag(C("reward_yn"), f"출판사 기재 '{reward_raw}' 이지만 완료 사례는 Y·보상금=정가. 규칙 확정 필요(FIELD-CHECKLIST C)")
    else:
        r.set(C("reward_yn"), reward)
        r.set(C("compensation"), price if reward == "Y" else 0 if reward == "N" else None)
    if price is None:
        r.flag(C("contents_price"), "정가 없음: 플랫폼 유통가 확인")
    if reward is None:
        r.flag(C("reward_yn"), "보상여부 없음")
    thumb = pub.get("썸네일") or pub.get("표지파일명")
    r.set(C("thum_files"), str(thumb).strip() if thumb else None)
    if not thumb:
        r.flag(C("thum_files"), "썸네일 파일명 없음(하이웨어/개별등록 시 필요)")
    return r


def part_from_filename(fname: str) -> str | None:
    """'로맨스 낫 로맨틱_S1_01회' → '01회', '…_외전[개정판]_11화' → '외전 11화', 없으면 None."""
    base = re.split(r"[\\/]", fname)[-1].rsplit(".", 1)[0]
    m = re.search(r"(외전|프롤로그|에필로그|특별편|번외)?[^_]*_?(\d{1,3}(?:회|화))\s*#?$", base)
    if not m:
        m2 = re.search(r"(프롤로그|에필로그)\s*#?$", base)
        return m2.group(1) if m2 else None
    return (m.group(1) + " " + m.group(2)) if m.group(1) else m.group(2)


def isbn13_ok(s: str) -> bool:
    if not re.fullmatch(r"\d{13}", s):
        return False
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(s[:12]))
    return (10 - total % 10) % 10 == int(s[12])


def match_folder(pub: dict, root: Path | None, index: int = 0, total: int = 0) -> tuple[Path | None, str]:
    if root is None:
        return None, ""
    fname = re.split(r"[\\/]", str(pub.get("파일명") or ""))[-1].rsplit(".", 1)[0]
    return resolve_folder(root, str(pub.get("제목(도서명)") or ""), str(pub.get("권차") or ""), fname, index, total)


def convert(pub_xlsx: Path, template_xlsx: Path, out_xlsx: Path, root: Path | None = None,
            publisher_place_json: Path | None = None, work_json: Path | None = None) -> tuple[int, int]:
    publisher_place = json.load(open(publisher_place_json, encoding="utf-8")) if publisher_place_json else {}
    work = json.load(open(work_json, encoding="utf-8")) if work_json else {}
    pubs = read_publisher_sheet(Path(pub_xlsx))
    shutil.copy(template_xlsx, out_xlsx)
    wb = openpyxl.load_workbook(out_xlsx)
    ws = wb["Contents"]
    header = [(c.value or "").strip() if isinstance(c.value, str) else "" for c in ws[1]]
    col_of: dict[Key, int] = {}
    seen: dict[str, int] = {}
    for i, h in enumerate(header):
        col_of[(h, seen.get(h, 0))] = i; seen[h] = seen.get(h, 0) + 1
    # 데이터 시작 행: 2행이 한글 안내 라벨(예시 양식)이면 3행부터, 완료 사례처럼 2행부터 데이터면 2행부터
    title_col = col_of.get(("/mods/titleInfo/title", 0), 1)
    start_row = 3 if str(ws.cell(row=2, column=title_col + 1).value or "").strip() == "제목" else 2
    if ws.max_row >= start_row:
        ws.delete_rows(start_row, ws.max_row - start_row + 1)
    nflags = 0; missing: set[str] = set()
    n_notes, n_topics, n_urls = seen.get("/mods/note", 0), seen.get("/mods/subject/topic", 0), seen.get("/mods/location/url", 0)
    for idx, pub in enumerate(pubs):
        folder, how = match_folder(pub, root, idx, len(pubs))
        row = build_row(pub, folder, publisher_place, work, n_notes, n_topics, n_urls)
        if root is not None and folder is None:
            row.flag(C("/mods/physicalDescription/extent"), "원문 폴더를 찾지 못함(파일명/제목 불일치)")
        elif how.startswith("순서"):
            row.flag(C("/mods/physicalDescription/extent"), f"폴더를 이름이 아니라 순서로 맞춤({folder.name}) — 회차 순서 확인")
        vals = [None] * len(header)
        for k, v in row.values.items():
            if k in col_of: vals[col_of[k]] = v
            elif v not in (None, ""): missing.add(f"{k[0]}#{k[1]}")
        ws.append(vals)
        rn = ws.max_row
        for f in row.flags:
            if f.col not in col_of:
                missing.add(f"{f.col[0]}#{f.col[1]}"); continue
            c = ws.cell(row=rn, column=col_of[f.col] + 1)
            c.fill = YELLOW
            prev = c.comment.text + "\n" if c.comment else ""
            c.comment = Comment(prev + f.reason, "kolis_tool")
            nflags += 1
    if missing:
        print("템플릿에 없는 열(값/표시 건너뜀):", ", ".join(sorted(missing)))
    # 출판사 원본 행을 _source 시트에 보존(agent 단계 근거용). KOLIS 는 2번째 시트(Contents)만 읽는다고 안내되어 있으나
    # 반입 전 이 시트를 지워야 하는지 현장에서 확인할 것.
    src = wb.create_sheet("_source")
    keys = list(dict.fromkeys(k for pub in pubs for k in pub))
    src.append(keys)
    for pub in pubs: src.append([pub.get(k) for k in keys])
    wb.save(out_xlsx)
    return len(pubs), nflags
