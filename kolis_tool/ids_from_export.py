"""KOLIS 전체출력 파일(ExcelDown….xls, 실제 내용은 HTML 표)에서 콘텐츠ID(CNTS-…) 목록을 뽑는다.
가이드 5.5: 다운로드 시 "파일 형식·확장자 불일치" 경고가 뜨는 파일이 이것. 순서를 유지하고 중복은 제거한다."""
from __future__ import annotations
import re
from pathlib import Path


def export_table(path: Path) -> list[dict]:
    """전체출력 파일을 표(행 = {열이름: 값})로. 2026-09-18 실측: 확장자는 .xls 지만 내용은 SpreadsheetML(Excel 2003 XML).
    진짜 xlsx 와 HTML 표도 받는다."""
    path = Path(path)
    raw = path.read_bytes()
    rows: list[list[str]] = []
    if raw[:2] == b"PK":
        import openpyxl
        ws = openpyxl.load_workbook(path, read_only=True).worksheets[0]
        rows = [["" if v is None else str(v) for v in r] for r in ws.iter_rows(values_only=True)]
    else:
        text = raw.decode("utf-8-sig", "ignore") if raw.lstrip()[:5] in (b"<?xml", b"\xef\xbb\xbf<") or b"urn:schemas-microsoft-com:office:spreadsheet" in raw[:2000] else ""
        if not text:
            for enc in ("utf-8", "cp949", "euc-kr", "utf-16"):
                try:
                    text = raw.decode(enc); break
                except UnicodeDecodeError:
                    continue
        if "urn:schemas-microsoft-com:office:spreadsheet" in text:
            # KOLIS 가 내보내는 XML 은 태그가 맞지 않는 곳이 있어(실측: 3019행) 정식 파서 대신 정규식으로 Row/Cell 을 읽는다
            import html
            for row_xml in re.findall(r"<(?:\w+:)?Row\b[^>]*>(.*?)</(?:\w+:)?Row>", text, re.S | re.I):
                cells: list[str] = []
                for attrs, inner in re.findall(r"<(?:\w+:)?Cell\b([^>]*)>(.*?)</(?:\w+:)?Cell>", row_xml, re.S | re.I):
                    m = re.search(r'Index="(\d+)"', attrs)
                    if m:
                        while len(cells) < int(m.group(1)) - 1:
                            cells.append("")
                    d = re.search(r"<(?:\w+:)?Data\b[^>]*>(.*?)</(?:\w+:)?Data>", inner, re.S | re.I)
                    v = d.group(1) if d else ""
                    cd = re.search(r"<!\[CDATA\[(.*?)\]\]>", v, re.S)
                    v = cd.group(1) if cd else html.unescape(re.sub(r"<[^>]+>", "", v))
                    cells.append(v.strip())
                rows.append(cells)
        else:   # HTML 표
            for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", text, re.S | re.I):
                rows.append([re.sub(r"<[^>]+>|&nbsp;", " ", td).strip() for td in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, re.S | re.I)])
    rows = [r for r in rows if any(r)]
    if not rows:
        return []
    hi = next((i for i, r in enumerate(rows) if any("콘텐츠ID" in c or "접수번호" in c for c in r)), 0)
    header = [h.strip() for h in rows[hi]]
    return [dict(zip(header, r + [""] * (len(header) - len(r)))) for r in rows[hi + 1:] if any(r)]


def receipt_map(path: Path) -> list[dict]:
    """접수번호(예 811-3) ↔ 콘텐츠ID ↔ 본표제·편권차. 접수번호 뒤 숫자 순으로 정렬."""
    out = []
    for r in export_table(path):
        no = r.get("접수번호", ""); cid = r.get("콘텐츠ID", "")
        if re.fullmatch(r"\d+-\d+", no) and cid.startswith("CNTS-"):
            out.append({"no": no, "seq": int(no.split("-")[1]), "cnts": cid, "title": r.get("본표제", ""), "part": r.get("편권차", "")})
    return sorted(out, key=lambda x: x["seq"])


def extract_ids(path: Path) -> list[str]:
    path = Path(path)
    raw = path.read_bytes()
    ids: list[str] = []
    if raw[:2] == b"PK":                      # 진짜 xlsx
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True)
        for ws in wb.worksheets:
            for row in ws.iter_rows(values_only=True):
                for v in row:
                    if isinstance(v, str) and re.fullmatch(r"CNTS-\d{11}", v.strip()):
                        ids.append(v.strip())
    else:
        for enc in ("utf-8", "cp949", "euc-kr", "utf-16"):
            try:
                text = raw.decode(enc); break
            except UnicodeDecodeError:
                continue
        else:
            text = raw.decode("utf-8", "ignore")
        ids = re.findall(r"CNTS-\d{11}", text)
    return list(dict.fromkeys(ids))
