"""MODS 입력가이드 docx → docs/rulebook/mods-input-guide.md (LLM 규칙집).
사용: python scripts/build_rulebook.py "<docx 경로>"
표는 마크다운 표로, 그림(캡처)은 [그림] 표시로 남긴다. 클라이언트 원문 문서 자체는 저장소에 넣지 않는다.
"""
import sys, re
from pathlib import Path
import docx
from docx.table import Table
from docx.text.paragraph import Paragraph

src = Path(sys.argv[1]); out = Path(__file__).resolve().parent.parent / "docs/rulebook/mods-input-guide.md"
d = docx.Document(src)
lines = [f"# 웹툰사업 MODS 태그별 메타데이터 입력 가이드 (규칙집)", "",
         f"원본: `{src.name}` 를 텍스트로 변환한 것. 표는 마크다운 표, 화면 캡처는 [그림]으로 표시.", ""]

def iter_block_items(parent):
    body = parent.element.body
    for child in body.iterchildren():
        if child.tag.endswith('}p'): yield Paragraph(child, parent)
        elif child.tag.endswith('}tbl'): yield Table(child, parent)

for b in iter_block_items(d):
    if isinstance(b, Paragraph):
        t = b.text.strip()
        has_img = bool(b._p.xpath('.//pic:pic'))
        if has_img: lines.append("[그림]")
        if not t: continue
        st = (b.style.name or "").lower()
        if st.startswith("heading"):
            lvl = int(re.sub(r"\D", "", st) or 1)
            lines += ["", "#" * min(lvl + 1, 6) + " " + t, ""]
        elif re.match(r"^\d+(\.\d+)*\.?\s", t) and len(t) < 60:
            lvl = t.split()[0].count(".") + 2
            lines += ["", "#" * min(lvl, 6) + " " + t, ""]
        else:
            lines.append(t)
    else:
        rows = []
        for r in b.rows:
            cells = []
            for c in r.cells:
                cells.append(c.text.strip().replace("\n", "<br>").replace("|", "\\|"))
            # 병합 셀 중복 제거
            dedup = []
            for c in cells:
                if not dedup or dedup[-1] != c: dedup.append(c)
            rows.append(dedup)
        w = max(len(r) for r in rows)
        rows = [r + [""] * (w - len(r)) for r in rows]
        lines.append("")
        lines.append("| " + " | ".join(rows[0]) + " |")
        lines.append("|" + "---|" * w)
        for r in rows[1:]: lines.append("| " + " | ".join(r) + " |")
        lines.append("")
out.write_text("\n".join(lines), encoding="utf-8")
print(out, len(lines), "lines")
