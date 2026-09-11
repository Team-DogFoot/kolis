"""⑤ 점검: 펼친 MODS 표에 규칙 검사를 걸고 점검용 xlsx 를 만든다.

MODS_정리_V.2.0.xlsm 매크로가 하던 일 + 가이드 5.7~5.9:
  - 1행 한글 항목명, 2행 경로(원래 매크로: 1행 한글, 2행 경로)
  - 오류 셀: 노란 배경·빨간 글자·메모, 그 열 1행도 노란색
  - 확인 필요(파란 배경): 규칙상 걸리지만 정상일 수 있는 것(예: 필명 대문자)
  - 파일명: 2026-(원부번호) n차점검(오류없음|오류 N건).xlsx
"""
from __future__ import annotations
import json, re
from dataclasses import dataclass
from pathlib import Path
import openpyxl
from openpyxl.comments import Comment
from openpyxl.styles import PatternFill, Font
from .common import CODE_REGION, region_code_from_place, CORPORATE_HINTS

HERE = Path(__file__).parent
LABELS: dict[str, str] = json.load(open(HERE / "mods_labels.json", encoding="utf-8"))
YELLOW = PatternFill("solid", fgColor="FFFF00")
BLUE = PatternFill("solid", fgColor="CCE5FF")
RED = Font(color="FF0000")

@dataclass
class Finding:
    row: int          # 0-based data row
    col: str          # column name
    msg: str
    level: str = "error"   # error | check


def base_path(col: str) -> str:
    return re.sub(r"^\[\d+\] ", "", col)


def label_for(col: str) -> str:
    return LABELS.get(base_path(col)) or base_path(col).rsplit("/", 1)[-1]


def _cols_like(cols: list[str], path: str) -> list[str]:
    return [c for c in cols if base_path(c) == path]


def check_rows(cols: list[str], rows: list[dict[str, str]]) -> list[Finding]:
    F: list[Finding] = []
    for i, r in enumerate(rows):
        def v(c): return r.get(c, "")
        for c in cols:
            bp = base_path(c); val = v(c)
            if not val:
                continue
            # --- 매크로 검사 재현 ---
            if bp in ("/mods/titleInfo/title", "/mods/relatedItem/titleInfo/partName"):
                if re.search(r"[A-Za-z]", val) and val[0].isalpha() and val[0].islower():
                    F.append(Finding(i, c, "문장의 첫글자 소문자"))
            if bp in ("/mods/titleInfo/subTitle", "/mods/relatedItem/titleInfo/subTitle"):
                if re.search(r"[A-Za-z]", val) and val[0].isalpha() and val[0].isupper():
                    F.append(Finding(i, c, "문장의 첫글자 대문자"))
            if bp in ("/mods/name/namePart", "/mods/name/displayForm", "/mods/name/alternativeName/namePart", "/mods/relatedItem/name/namePart"):
                if re.search(r"[A-Za-z]", val):
                    if re.search(r",(?! )", val[:-1]): F.append(Finding(i, c, "콤마 뒤에 공백 미존재"))
                    if re.search(r" [a-z]", val): F.append(Finding(i, c, "공백 뒤 영문 소문자"))
                    if re.search(r"(?<=[^ ])[A-Z]", val[1:]): F.append(Finding(i, c, "영문 대문자 앞 공백 미존재", "check"))
            if bp == "/mods/name/alternativeName[@altType]" and val != "no specific type":
                F.append(Finding(i, c, "no specific type 이외의 값"))
            if bp == "/mods/originInfo/place/placeTerm[@authority]" and val != "kormarccountry":
                F.append(Finding(i, c, "kormarccountry 이외의 값"))
            # --- 공통(매크로에서는 꺼져 있던 CheckComm) ---
            if "  " in val: F.append(Finding(i, c, "2개 이상 공백"))
            # --- 가이드 5.8 ---
            if bp == "/mods/originInfo/dateIssued" and not re.fullmatch(r"[\d-]{8}", val):
                F.append(Finding(i, c, "발행일 8자리 아님"))
            if bp == "/mods/identifier":
                t = v(c.replace("/mods/identifier", "/mods/identifier[@type]"))
                if t == "isbn" and not _isbn_ok(val): F.append(Finding(i, c, "ISBN 형식/체크섬 오류"))
                if " " in val: F.append(Finding(i, c, "공백 존재"))
            if bp == "/mods/location/url" and " " in val:
                F.append(Finding(i, c, "공백 존재"))
            if bp == "/mods/classification" and len(re.sub(r"\D", "", val)) < 3:
                F.append(Finding(i, c, "분류기호 3자리 미만"))
            if bp == "/mods/physicalDescription/extent" and not re.fullmatch(r"이미지 파일 \d+개 \([\d.]+ MB\) : (천연색|단색)", val):
                F.append(Finding(i, c, "extent 문구 형식 확인", "check"))
        # --- 행 단위 대조 ---
        # 저자명 ↔ 개인명/단체명
        for nc in _cols_like(cols, "/mods/name/namePart"):
            tc = nc.replace("/mods/name/namePart", "/mods/name[@type]")
            name, typ = v(nc), v(tc)
            corp = any(h.lower() in name.lower() for h in CORPORATE_HINTS)
            if name and typ == "personal" and corp: F.append(Finding(i, tc, f"'{name}' 단체명으로 보이는데 personal", "check"))
            if name and typ == "corporate" and not corp: F.append(Finding(i, tc, f"'{name}' 개인명으로 보이는데 corporate", "check"))
            if name and not typ: F.append(Finding(i, nc, "저자 유형값 없음"))
            if name and re.search(r"[A-Z]{2,}", name): F.append(Finding(i, nc, "영문 대문자 연속(필명이면 정상)", "check"))
        # 발행지 텍스트 ↔ 코드
        pt = _cols_like(cols, "/mods/originInfo/place/placeTerm")
        ptype = _cols_like(cols, "/mods/originInfo/place/placeTerm[@type]")
        texts = [v(c) for c, t in zip(pt, ptype) if v(t) == "text"]
        codes = [v(c) for c, t in zip(pt, ptype) if v(t) == "code"]
        for text, code in zip(texts, codes):
            exp = region_code_from_place(text) if text else None
            if text and code and exp and exp != code:
                F.append(Finding(i, pt[0], f"발행지 '{text}' 코드 '{code}' 불일치(예상 {exp} {CODE_REGION.get(exp,'')})"))
            if code and code not in CODE_REGION:
                F.append(Finding(i, pt[0], f"발행지 코드 '{code}' 국내 코드표에 없음", "check"))
        if len(texts) != len(codes):
            F.append(Finding(i, pt[0] if pt else cols[0], "발행지 text/code 개수 불일치"))
        # 주기 ↔ 유형
        for nc in _cols_like(cols, "/mods/note"):
            tc = nc.replace("/mods/note", "/mods/note[@type]")
            note, typ = v(nc), v(tc)
            if not note: continue
            if re.search(r"이용가|세 이상|청소년", note) and typ != "target audience":
                F.append(Finding(i, tc, f"주기 '{note}' 는 target audience 여야 함"))
            if "수집한 자료" in note and typ != "acquisition":
                F.append(Finding(i, tc, f"주기 '{note}' 는 acquisition 여야 함"))
        # 주제명: 만화·웹툰
        topics = [v(c) for c in _cols_like(cols, "/mods/subject/topic")]
        genres = [v(c) for c in _cols_like(cols, "/mods/subject/genre")]
        if not any("만화" in t for t in topics): F.append(Finding(i, cols[0], "일반주제명 '만화' 없음"))
        if not any("웹툰" in g for g in genres): F.append(Finding(i, cols[0], "장르주제명 '웹툰' 없음"))
        # 필수 상수
        for path, expect in [("/mods/genre", "만화"), ("/mods/typeOfResource", "텍스트"), ("/mods/extension/regionOfPublishing", "한국"),
                             ("/mods/classification", "810"), ("/mods/originInfo/issuance", "단행자료"), ("/mods/language/languageTerm", "kor")]:
            for c in _cols_like(cols, path):
                if v(c) and v(c) != expect: F.append(Finding(i, c, f"'{expect}' 아님"))
        for path in ("/mods/titleInfo/title", "/mods/originInfo/dateIssued", "/mods/originInfo/publisher", "/mods/physicalDescription/extent"):
            if not any(v(c) for c in _cols_like(cols, path)):
                F.append(Finding(i, cols[0], f"{LABELS.get(path, path)} 없음"))
    return F


def _isbn_ok(s: str) -> bool:
    s = re.sub(r"[\s-]", "", s)
    if not re.fullmatch(r"\d{13}", s): return False
    total = sum(int(d) * (1 if k % 2 == 0 else 3) for k, d in enumerate(s[:12]))
    return (10 - total % 10) % 10 == int(s[12])


def write_check_xlsx(cols: list[str], rows: list[dict[str, str]], findings: list[Finding], out_path: Path,
                     move_genre_before_classification: bool = True) -> Path:
    cols = list(cols)
    if move_genre_before_classification:   # 가이드 5.7: 장르주제명 열을 분류기호 앞으로
        g = [c for c in cols if base_path(c) == "/mods/subject/genre"]
        for c in g: cols.remove(c)
        k = next((i for i, c in enumerate(cols) if base_path(c) == "/mods/classification"), len(cols))
        cols[k:k] = g
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "점검"
    ws.append(["컨텐츠 아이디"] + [label_for(c) for c in cols])
    ws.append(["컨텐츠 아이디"] + cols)
    id_col = next((c for c in cols if base_path(c) == "/mods/recordInfo/recordIdentifier"), None)
    for r in rows:
        ws.append([r.get(id_col, "") if id_col else ""] + [r.get(c, "") for c in cols])
    col_idx = {c: i + 2 for i, c in enumerate(cols)}
    hdr_msgs: dict[int, set[str]] = {}
    for f in findings:
        ci = col_idx.get(f.col, 1); rn = f.row + 3
        cell = ws.cell(row=rn, column=ci)
        if f.level == "error":
            cell.fill = YELLOW; cell.font = RED
        elif cell.fill != YELLOW:
            cell.fill = BLUE
        prev = cell.comment.text + "\n" if cell.comment else ""
        cell.comment = Comment(prev + f.msg, "kolis_tool")
        hdr_msgs.setdefault(ci, set()).add(f.msg)
    for ci, msgs in hdr_msgs.items():
        h = ws.cell(row=1, column=ci); h.fill = YELLOW
        h.comment = Comment("\n".join(sorted(msgs)), "kolis_tool")
    ws.freeze_panes = "D3"
    ws.auto_filter.ref = f"A2:{ws.cell(row=2, column=len(cols)+1).column_letter}{ws.max_row}"
    wb.save(out_path)
    return out_path


def output_name(year: str, wonbu: str, nth: int, findings: list[Finding]) -> str:
    errs = [f for f in findings if f.level == "error"]
    if not errs:
        tag = "오류없음"
    else:
        by = {}
        for f in errs: by[f.msg] = by.get(f.msg, 0) + 1
        top, cnt = max(by.items(), key=lambda kv: kv[1])
        tag = f"{top} {cnt}건" if cnt / len(errs) > 0.6 else f"오류 {len(errs)}건"
    return f"{year}-{wonbu} {nth}차점검({tag}).xlsx"
