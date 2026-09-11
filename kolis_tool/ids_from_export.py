"""KOLIS 전체출력 파일(ExcelDown….xls, 실제 내용은 HTML 표)에서 콘텐츠ID(CNTS-…) 목록을 뽑는다.
가이드 5.5: 다운로드 시 "파일 형식·확장자 불일치" 경고가 뜨는 파일이 이것. 순서를 유지하고 중복은 제거한다."""
from __future__ import annotations
import re
from pathlib import Path


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
