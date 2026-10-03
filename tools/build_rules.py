"""도서관 지침 원본(docs/source/2_지침)을 에이전트가 찾아 읽을 수 있는 형태로 변환한다(2026-10-03, 유저 요청 "지침을 헤드리스 에이전트가 RAG 할 수 있게").
- PDF → docs/source/text/<이름>.md : 쪽마다 `## 쪽 N` 머리와 본문, 그 쪽에 든 그림(120px 이상)을 `![…](../images/<문서>/pNNN-k.png)` 로 링크. 그림 파일은 docs/source/images/<문서>/ 에 뺀다.
- DOCX(MODS 입력가이드) → docs/source/text/MODS_입력가이드.md : 머리글·단락·표(마크다운 표)·그림을 문서 순서대로. 그림은 docs/source/images/mods-guide/ 에 뺀다.
- docs/source/text/INDEX.md : 문서별 목차(쪽 번호 → 파일 안 위치)와 찾는 법.
에이전트 작업 공간에는 kolis_tool.agent.deploy() 가 text/*.md 와 images/ 를 knowledge/rules/ 로 복사한다.
다시 돌려도 같은 결과(결정적). 벡터 검색은 쓰지 않는다: 양이 작아(글 40만 자) Grep + Read(이미지 포함)로 충분하다.
"""
from __future__ import annotations
import re, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
import pymupdf, docx
from docx.table import Table
from docx.text.paragraph import Paragraph

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "docs" / "source" / "2_지침"
TEXT = REPO / "docs" / "source" / "text"
IMAGES = REPO / "docs" / "source" / "images"
MIN_PX = 120   # 이보다 작은 그림은 글머리표·아이콘이라 뺀다

PDFS = {  # 원본 파일 → (출력 이름, 그림 폴더, 설명)
    "2025 온라인 자료 정리 지침서_202412.pdf": ("정리지침서_2025", "guideline-2025", "국립중앙도서관 온라인자료과, 2024-12. 온라인 자료 메타데이터(MODS) 구축 지침. 3장 공통(전자책 기준), 5장 기타 자료에 웹툰(인쇄 쪽 84~86)."),
    "웹툰대행사업 매뉴얼(v.1.6).pdf": ("웹툰대행사업_매뉴얼_v1.6", "manual-v1.6", "웹툰 납본·수집 대행 사업 매뉴얼 v1.6 (2026-05). 수집·검수·등록·구축·점검 절차와 웹툰 전용 규칙."),
}
DOCX = ("웹툰사업_MODS_태그별_메타데이터_입력가이드.docx", "MODS_입력가이드", "mods-guide", "웹툰사업 MODS 태그별 메타데이터 입력 가이드(참고자료 정리본). 태그마다 무엇을 어디서 가져와 어떻게 적는지. 표와 입력 화면 캡처.")


def clean(t: str) -> str:
    t = t.replace("­", "").replace("\xa0", " ")
    t = re.sub(r"[ \t]+\n", "\n", t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def pdf_to_md(src: Path, name: str, imgdir: str, desc: str) -> list[tuple[int, str]]:
    d = pymupdf.open(src)
    out_img = IMAGES / imgdir; out_img.mkdir(parents=True, exist_ok=True)
    for old in out_img.glob("p*.png"):
        old.unlink()
    lines = [f"# {src.stem}", "", f"원본: `docs/source/2_지침/{src.name}` ({len(d)}쪽). {desc}", "",
             "쪽마다 `## 쪽 N` 로 나눴다(N 은 PDF 쪽 번호. 문서에 찍힌 쪽 번호는 본문 첫 줄 `- n -`). 그림은 같은 쪽 끝에 링크했다. 표는 글자만 남아 줄이 섞일 수 있으니 중요한 표는 그 쪽의 그림이나 원본 PDF 를 본다.", ""]
    heads = []
    n_img = 0
    for i, page in enumerate(d, start=1):
        txt = clean(page.get_text())
        printed = re.match(r"-\s*(\d+)\s*-", txt)
        lines.append(f"## 쪽 {i}" + (f" (인쇄 {printed.group(1)})" if printed else ""))
        lines.append("")
        lines.append(txt)
        for m in re.finditer(r"^\s*(\d{1,2}\.\s+\S.{0,40}|□\s+\S.{0,40})$", txt, re.M):
            heads.append((i, m.group(1).strip()))
        k = 0
        for im in page.get_images(full=True):
            info = d.extract_image(im[0])
            if info["width"] < MIN_PX or info["height"] < MIN_PX:
                continue
            k += 1; n_img += 1
            f = out_img / f"p{i:03d}-{k}.png"
            pix = pymupdf.Pixmap(d, im[0])
            if pix.n - pix.alpha >= 4:   # CMYK → RGB
                pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
            pix.save(f)
            lines.append(f"\n![쪽 {i} 그림 {k}](../images/{imgdir}/{f.name})")
        lines.append("")
    (TEXT / f"{name}.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"{src.name}: {len(d)}쪽, 그림 {n_img}장 → text/{name}.md, images/{imgdir}/")
    return heads


def iter_block_items(parent):
    """문서 본문의 단락과 표를 나온 순서대로."""
    from docx.oxml.ns import qn
    for child in parent.element.body.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, parent)
        elif child.tag == qn("w:tbl"):
            yield Table(child, parent)


def docx_to_md(src: Path, name: str, imgdir: str, desc: str) -> list[tuple[int, str]]:
    dd = docx.Document(src)
    out_img = IMAGES / imgdir; out_img.mkdir(parents=True, exist_ok=True)
    for old in out_img.glob("*.*"):
        old.unlink()
    rels = dd.part.rels
    counter = {"n": 0}
    heads = []

    def images_in(el) -> list[str]:
        refs = []
        for rid in el.xpath(".//a:blip/@r:embed"):
            part = rels[rid].target_part
            counter["n"] += 1
            ext = Path(part.partname).suffix.lower() or ".png"
            f = out_img / f"{counter['n']:02d}{ext}"
            f.write_bytes(part.blob)
            refs.append(f"![그림 {counter['n']}](../images/{imgdir}/{f.name})")
        return refs

    def para_md(p: Paragraph) -> str:
        t = p.text.strip()
        st = p.style.name
        imgs = images_in(p._p)
        if st.startswith("Heading"):
            last = st.split()[-1]
            lvl = int(last) if last.isdigit() else 2
            if t:
                heads.append((lvl, t))
            s = "#" * (lvl + 1) + " " + t
        elif st == "List Paragraph" and t:
            s = "- " + t
        else:
            s = t
        return "\n".join(x for x in [s, *imgs] if x)

    def cell_md(c) -> str:
        parts = [p.text.strip() for p in c.paragraphs if p.text.strip()]
        parts += images_in(c._tc)
        return "<br>".join(parts).replace("|", "\\|")

    lines = [f"# {src.stem}", "", f"원본: `docs/source/2_지침/{src.name}`. {desc}", "",
             "머리글 번호는 원본 그대로(0. 개요 ~ 14. 소장정보, 부록 A). 표는 마크다운 표, 캡처는 `![그림 n]` 링크(Read 로 열어 본다).", ""]
    for item in iter_block_items(dd):
        if isinstance(item, Paragraph):
            md = para_md(item)
            if md:
                lines.append(md); lines.append("")
        else:
            rows = [[cell_md(c) for c in r.cells] for r in item.rows]
            if not rows:
                continue
            w = max(len(r) for r in rows)
            rows = [r + [""] * (w - len(r)) for r in rows]
            for r in rows:                      # 병합된 칸은 같은 글이 되풀이되므로 연속 중복을 비운다
                for j in range(w - 1, 0, -1):
                    if r[j] == r[j - 1]:
                        r[j] = ""
            lines.append("| " + " | ".join(rows[0]) + " |")
            lines.append("|" + "---|" * w)
            for r in rows[1:]:
                lines.append("| " + " | ".join(r) + " |")
            lines.append("")
    (TEXT / f"{name}.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"{src.name}: 그림 {counter['n']}장 → text/{name}.md, images/{imgdir}/")
    return heads


def main():
    TEXT.mkdir(parents=True, exist_ok=True)
    idx = ["# 지침 원문 찾아보기 (에이전트용 색인)", "",
           "도서관이 준 지침 세 가지를 글로 바꾼 것이다. 판단 기준이 헷갈리면 **먼저 여기서 항목 이름으로 Grep** 하고, 걸린 파일의 그 자리를 Read 로 읽는다. 그림 링크(`![…](../images/…)`)는 Read 로 열면 화면 캡처가 보인다(입력 화면 예시는 대개 그림에 있다).", "",
           "우선순위: 직원 답변(`build-judgment-rules.md`, `corrections.md`) > 웹툰 전용(MODS 입력가이드, 매뉴얼 v1.6) > 공통(정리지침서 2025). 서로 다르면 더 구체적인 웹툰 전용 규칙을 따르고, 엇갈림을 보고한다.", "",
           "| 파일 | 내용 | 주로 찾는 것 |", "|---|---|---|"]
    rows = []
    toc_sections = []
    for fname, (name, imgdir, desc) in PDFS.items():
        heads = pdf_to_md(SRC / fname, name, imgdir, desc)
        what = "3장 공통 규칙(표제·저자·출처·주제명·식별기호), 5장 웹툰" if "정리지침서" in name else "복본조사·유통조사·가격·완결 판단, 구축 절차, 웹툰 규칙"
        rows.append(f"| `{name}.md` | {desc} | {what} |")
        toc_sections.append((name, heads))
    fname, name, imgdir, desc = DOCX
    heads = docx_to_md(SRC / fname, name, imgdir, desc)
    rows.append(f"| `{name}.md` | {desc} | 태그별 입력값·정보원·예시(다른이름, 발행처, 주제명, UCI 등) |")
    idx += rows + [""]
    idx += ["## MODS 입력가이드 목차", ""] + [("  " * (l - 1)) + "- " + t for l, t in heads] + [""]
    for name, heads in toc_sections:
        idx += [f"## {name} — 쪽별 머리글(`## 쪽 N` 으로 찾는다)", ""]
        seen = set()
        for pg, h in heads:
            if (pg, h) in seen or len(h) < 3:
                continue
            seen.add((pg, h)); idx.append(f"- 쪽 {pg}: {h}")
        idx.append("")
    idx += ["## 그 밖의 원문(글만)", "",
            "- `웹툰납본프로세스가이드_v1.0.txt` : 프로세스 가이드(①~⑤ 단계). 그림은 `../images/guide/NN.png`(파일 번호 = 가이드 그림 번호 − 1).",
            "- `참고자료_v1.3_계정제외.txt` : 보안USB·웹하드·하이웨어 절차(계정 표는 뺐다).", ""]
    (TEXT / "INDEX.md").write_text("\n".join(idx), encoding="utf-8")
    print("INDEX.md 작성")


if __name__ == "__main__":
    main()
