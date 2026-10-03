"""개발용: MODS 칸의 모수(종류·수·구조)를 세 출처에서 모아 docs/MODS-FIELDS.md 를 만든다(모두 읽기만, 요청 없음).
 A 지침(MODS 입력가이드 0.5 전체 요소 목록)  B KOLIS MODS 수정 화면의 칸(저장 가능한 전부, form 기록)  C 반입용 양식 필드설명(Sample 시트) + 템플릿 83열 + 예시 88열 + 반입된 XML 에서 확인된 속성
실행: .venv/Scripts/python.exe -X utf8 tools/mods_fields_doc.py"""
import json, re, sys
from pathlib import Path
import openpyxl
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

GUIDE = Path("docs/source/text/MODS_입력가이드.md")
FORM = Path("work/build/CNTS-00135497353/form_after_apply.json")
TEMPLATE = Path("kolis_tool/templates/import_template_83.xlsx")
EXAMPLE = Path("docs/source/3_샘플양식/완료사례_코리스반입용_로맨스낫로맨틱(88열).xlsx")
XML_IMPORTED = Path("work/build/CNTS-00135497353/mods_before.xml")   # 반입 직후(저장 전) — 반입이 받아 준 것의 증거
OUT = Path("docs/MODS-FIELDS.md")


def norm(p: str) -> str:
    """경로 표기 통일: 속성은 [@x], 끝 슬래시·번호 제거."""
    p = re.sub(r"\d+$", "", p.strip()).rstrip("/")
    p = re.sub(r"@(\w+)", r"[@\1]", p) if "[@" not in p else p
    return p


def guide_rows():
    s = GUIDE.read_text(encoding="utf-8")
    a = s.index("### 0.5"); b = s.index("## 1. 표제정보")
    out = []
    for line in s[a:b].splitlines():
        if line.startswith("| ") and "<" in line:
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) >= 4 and cells[1].startswith("<"):
                path = "/mods/" + "/".join(re.findall(r"<(\w+)>", cells[1]))
                out.append({"label": cells[0], "path": path, "repeat": cells[2], "required": cells[3]})
    return out


def form_paths():
    f = json.loads(FORM.read_text(encoding="utf-8"))
    seen = []
    for x in f:
        n = x.get("name", "")
        if not n.startswith("_") or "hidden" in n or n.endswith("Cnt"):
            continue
        p = norm("/mods" + re.sub(r"\d+$", "", n).replace("_", "/"))
        if p not in seen:
            seen.append(p)
    return seen


def sample_spec():
    ws = openpyxl.load_workbook(TEMPLATE, read_only=True)["Sample"]
    out = []
    for r in ws.iter_rows(values_only=True):
        if r and isinstance(r[0], str) and r[0].startswith("/mods"):
            out.append({"path": norm(r[0]), "label": str(r[1] or ""), "type": str(r[2] or "").replace("\n", " / ")[:120], "required": str(r[3] or ""), "note": str(r[4] or "")[:80]})
    return out


def headers(xlsx):
    ws = openpyxl.load_workbook(xlsx, read_only=True)["Contents"]
    h = [c for c in next(ws.iter_rows(min_row=1, max_row=1, values_only=True)) if c]
    from collections import Counter
    return Counter(norm(x) for x in h)


def imported_attrs():
    x = XML_IMPORTED.read_text(encoding="utf-8")
    import xml.etree.ElementTree as ET
    root = ET.fromstring(x); ns = "{http://www.loc.gov/mods/v3}"
    seen = set()
    def walk(e, path):
        tag = e.tag.replace(ns, ""); here = f"{path}/{tag}"
        if (e.text or "").strip() or len(e) == 0:
            seen.add(here)
        for k in e.attrib:
            if tag != "mods":
                seen.add(f"{here}[@{k}]")
        for c in e:
            walk(c, here)
    walk(root, "")
    return {p.replace("/mods/mods", "/mods") if p.startswith("/mods/mods") else p for p in seen}


def main():
    g = guide_rows(); gp = {r["path"]: r for r in g}
    fp = form_paths()
    sp = sample_spec(); spd = {r["path"]: r for r in sp}
    t83 = headers(TEMPLATE); e88 = headers(EXAMPLE)
    imp = imported_attrs()
    allp = []
    for p in fp + [r["path"] for r in g] + [r["path"] for r in sp] + list(t83) + list(e88):
        if p not in allp and p.startswith("/mods"):
            allp.append(p)
    lines = ["# MODS 칸의 모수 — 지침 · KOLIS 수정 화면 · 반입 양식 (2026-10-03, 읽기만으로 모음)", "",
             f"만든 도구: `tools/mods_fields_doc.py`. 출처 세 가지를 경로 기준으로 합쳤다. 경로 표기는 `/mods/요소/하위요소[@속성]`.",
             "", "| 출처 | 무엇 | 수 |", "|---|---|---|",
             f"| A 지침 | MODS 입력가이드 0.5 전체 요소 목록(전자책 기준) | {len(g)} |",
             f"| B KOLIS 화면 | MODS 수정 화면(onContentsDetailPop)의 칸 — 저장 요청이 받는 전부(1614 1화 폼 기록) | {len(fp)} |",
             f"| C 반입 양식 | 템플릿 Sample 시트 「필드설명」(도서관 공식 열 설명) | {len(sp)} |",
             f"| C' 템플릿 83열 | 실제 승인된 양식의 열(고유 경로 {len(t83)}) | {sum(t83.values())} |",
             f"| C'' 예시 88열 | 완료 사례 로맨스낫로맨틱(고유 경로 {len(e88)}) | {sum(e88.values())} |",
             f"| D 반입 확인 | 반입 직후(저장 전) XML 에서 실제로 들어간 요소·속성 | {len(imp)} |", "",
             "## 1. 결론(반입에서 끝낼 수 있는가)", "",
             "- **반입 파서는 경로 열을 그대로 받는다.** Sample 필드설명에 **없는** 열(`/mods/name[@usage]`, `/mods/note[@type]`, `/mods/originInfo[@eventType]`, `/mods/classification[@edition]`, `/mods/originInfo/edition`)이 템플릿·예시에 있고, 그중 `name[@usage]`·`note[@type]`·`originInfo[@eventType]`·`classification[@authority]`·`placeTerm[@authority]` 는 반입된 XML(D)에 그대로 들어가 있다 → 속성 열은 '앞 요소에 속성을 붙인다'는 일반 규칙으로 처리된다(Sample 2행: \"엘리먼트를 먼저 기술하고 속성을 기술한다\").",
             "- 따라서 **저자 전거(`/mods/name[@ID]`, `/mods/name[@authority]`), 주제명 전거(`/mods/subject[@ID]`, `/mods/subject[@authority]`), 장르주제명(`/mods/subject/genre`), 다른이름 유형(`/mods/name/alternativeName[@altType]`)** 도 같은 규칙이면 반입으로 들어갈 가능성이 높다. B(KOLIS 화면)에 그 칸이 모두 있으므로 저장소 쪽 자리는 있다.",
             "- **미확인(문서로는 끝까지 확정 못 함):** 반입 파서가 Sample 목록 밖의 속성 이름을 전부 받는지, `[@altType]` 과 Sample 의 `[@type]` 중 어느 표기를 쓰는지, UCI(`identifier[@type]=uci`)는 지침 13 이 \"반입하면 오류\"라고 적음. 확정하려면 **반입 1회**(가원부번호까지 → 접수번호 취소 요청, 되돌릴 수 있음)가 필요하다. 시험 열: `name[@ID]`·`name[@authority]`·`subject[@ID]`·`subject[@authority]`·`subject/genre`(둘째 주제명 묶음)·`alternativeName[@altType]`. 유저 결정(10-03): 이 길은 가지 않기로 했으므로 **결정이 바뀔 때만**.",
             "- Sample 의 `name[@type]` 값은 `personal/corporate/conference` 인데 템플릿·예시·반입 XML 은 `개인명` 을 썼고 그대로 들어갔다(저장 뒤 KOLIS 가 `personal` 로 바꿈). `displayForm` 은 Sample 에 \"(사용안함)\".", "",
             "## 2. 경로별 대조표", "",
             "| 경로 | A 지침(반복/필수) | B KOLIS 화면 | C 필드설명(한글명 · 값 규칙) | 83열 | 88열 | D 반입 확인 |", "|---|---|---|---|---|---|---|"]
    for p in allp:
        gr = gp.get(p); sr = spd.get(p)
        lines.append(f"| `{p}` | {(gr['label'] + ' ' + gr['repeat'] + '/' + gr['required']) if gr else ''} | {'○' if p in fp else ''} | {(sr['label'] + (' · ' + sr['type'] if sr['type'] and sr['type'] != '텍스트' and sr['type'] != '-' else '')) if sr else ''} | {t83.get(p, '') or ''} | {e88.get(p, '') or ''} | {'○' if p in imp else ''} |")
    lines += ["", "## 3. 값 규칙(Sample 필드설명에서)", ""]
    for r in sp:
        if r["type"] and r["type"] not in ("텍스트", "-"):
            lines.append(f"- `{r['path']}` ({r['label']}): {r['type']}{(' — ' + r['note']) if r['note'] else ''}")
    lines += ["", "## 4. 웹툰 사업에서 쓰는 열(가이드 1~14절 요약 → 어디서 넣나)", "",
              "| 항목 | 반입용 엑셀 | KOLIS 구축(3-2) |", "|---|---|---|",
              "| 표제·표제관련정보·권차·권차표제·대등표제(titleInfo[@type]=parallel) | ○ | 확인만 |",
              "| 저자명(전거형)·유형·역할어 | ○ | 확인만 |",
              "| 저자 전거 번호 @ID·@authority | × (미확인, 1절) | ○ 찾기 팝업/insertAcMat |",
              "| 디스플레이형식 | × (Sample '사용안함') | ○ |",
              "| 다른이름 + altType | 첫 저자 묶음만 열 있음(83열) | ○ |",
              "| 발행지 글자+코드·발행처(n)·발행일·판사항·발행연속성·둘째 출처정보 | ○ | 확인만 |",
              "| 언어·형태기술(자료형태·품질·미디어타입·수량·digitalOrigin) | ○(고정값·수량은 프로그램) | KOLIS 가 저장 때 표기 변경 |",
              "| 이용대상자·주기 n쌍(유형) | ○ | 확인만 |",
              "| 일반주제명 만화 | ○ (topic 글자만) | @ID·@authority 연결 |",
              "| 장르주제명 웹툰[webtoon] | × (지침 10: 구축에서) | ○ |",
              "| 분류 810 KDC 6 | ○ | 확인만 |",
              "| ISBN | ○ | 확인만 |",
              "| UCI | × (지침 13: 반입 오류) | ○ |",
              "| 원문주소 2·소장위치·접근제한·지역구분·자료유형·장르 | ○ | 확인만 |",
              "| 이용제한(성인) | × (종 화면) | ○ 자동 |",
              "| 가격·보상·썸네일 | ○ (부록 A) | — |"]
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"썼습니다: {OUT} — 지침 {len(g)} · 화면 {len(fp)} · 필드설명 {len(sp)} · 83열 고유 {len(t83)} · 88열 고유 {len(e88)} · 반입 확인 {len(imp)} · 합친 경로 {len(allp)}")
    missing = [p for p in fp if p not in spd and p not in t83 and p not in e88]
    print("KOLIS 화면에는 있는데 반입 양식·설명 어디에도 없는 경로:", len(missing))
    for p in missing: print("  ", p)


if __name__ == "__main__":
    main()
