"""개발용: 프로그램이 만든 반입용 엑셀 ↔ 기준 엑셀(도서관 완료본)을 머리글과 값 칸 단위로 대조해 글로 쓴다. 채점하지 않는다(같다/다르다와 양쪽 값만 적는다).
실행: .venv-mac/bin/python -X utf8 tools/compare_import.py <프로그램이 만든 엑셀> <기준 엑셀> [--out <파일.md>]
- 머리글 행은 '/mods' 로 시작하는 칸이 5개 넘는 첫 행(프로그램이 만든 파일은 그 위에 한글 머리글 1행이 있다).
- 같은 머리글이 여러 번 나오면 n번째끼리 맞춘다(저자 1·2·3, 출처정보 1·2 …).
- 행은 순서대로 맞춘다(1행 ↔ 1행). 권차 값이 서로 다르면 따로 적는다.
"""
from __future__ import annotations
import sys, re, argparse, unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from openpyxl import load_workbook
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def cell(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return unicodedata.normalize("NFC", str(v)).strip()


def loose(s: str) -> str:
    return re.sub(r"\s+", "", s).lower()


def read(path: Path) -> dict:
    wb = load_workbook(path, data_only=True)
    best = None
    for ws in wb.worksheets:
        for r in range(1, min(ws.max_row, 8) + 1):
            vals = [cell(c.value) for c in ws[r]]
            if sum(1 for v in vals if v.startswith("/mods")) > 5:
                rows = []
                for rr in range(r + 1, ws.max_row + 1):
                    row = [cell(c.value) for c in ws[rr]]
                    if any(row):
                        rows.append(row + [""] * (len(vals) - len(row)))
                cand = {"sheet": ws.title, "header_row": r, "headers": vals, "rows": rows, "above": [[cell(c.value) for c in ws[i]] for i in range(1, r)]}
                if best is None or len(rows) > len(best["rows"]):
                    best = cand
                break
    if best is None:
        raise SystemExit(f"머리글 행(/mods …)을 찾지 못했습니다: {path}")
    occ, keys = Counter(), []
    for h in best["headers"]:
        if not h:
            keys.append(None); continue
        occ[h] += 1
        keys.append((h, occ[h]))
    best["keys"] = keys
    best["sheets"] = wb.sheetnames
    return best


def label_of(header: str) -> str:
    try:
        from kolis_tool import mods_sheet
        return str(mods_sheet.label(header) or "")
    except Exception:  # noqa: BLE001
        return ""


def compare(ours: dict, base: dict) -> dict:
    ko, kb = [x for x in ours["keys"] if x], [x for x in base["keys"] if x]
    so, sb = set(ko), set(kb)
    io = {x: i for i, x in enumerate(ours["keys"]) if x}
    ib = {x: i for i, x in enumerate(base["keys"]) if x}
    n = max(len(ours["rows"]), len(base["rows"]))
    cols = []
    for key in kb + [x for x in ko if x not in sb]:
        in_o, in_b = key in so, key in sb
        same = diff = both_empty = 0
        diffs, loose_same = [], 0
        for r in range(n):
            vo = ours["rows"][r][io[key]] if in_o and r < len(ours["rows"]) and io[key] < len(ours["rows"][r]) else ""
            vb = base["rows"][r][ib[key]] if in_b and r < len(base["rows"]) and ib[key] < len(base["rows"][r]) else ""
            if vo == vb:
                if vo:
                    same += 1
                else:
                    both_empty += 1
            else:
                diff += 1
                if loose(vo) == loose(vb):
                    loose_same += 1
                diffs.append((r + 1, vo, vb))
        cols.append({"key": key, "label": label_of(key[0]), "in_ours": in_o, "in_base": in_b, "same": same, "diff": diff, "both_empty": both_empty, "loose_same": loose_same, "diffs": diffs})
    return {"rows_ours": len(ours["rows"]), "rows_base": len(base["rows"]), "cols": cols, "only_ours": [x for x in ko if x not in sb], "only_base": [x for x in kb if x not in so],
            "order_same": [x for x in ko if x in sb] == [x for x in kb if x in so]}


def name(key) -> str:
    return key[0] + (f" (#{key[1]})" if key[1] > 1 else "")


def render(ours_path: Path, base_path: Path, ours: dict, base: dict, c: dict) -> str:
    L = []; w = L.append
    w("# 반입용 엑셀 대조 — 프로그램이 만든 것 ↔ 기준(도서관 완료본)")
    w("")
    w(f"- 프로그램: `{ours_path}` · 시트 {ours['sheet']} · 머리글 {ours['header_row']}행 · 열 {len([x for x in ours['keys'] if x])}개 · 값 {c['rows_ours']}행")
    w(f"- 기준: `{base_path}` · 시트 {base['sheet']}(전체 시트 {base['sheets']}) · 머리글 {base['header_row']}행 · 열 {len([x for x in base['keys'] if x])}개 · 값 {c['rows_base']}행")
    both = [x for x in c["cols"] if x["in_ours"] and x["in_base"]]
    tot_same, tot_diff = sum(x["same"] for x in both), sum(x["diff"] for x in both)
    w(f"- 양쪽에 다 있는 열 {len(both)}개 · 그 안에서 값이 같은 칸 {tot_same}개 · 다른 칸 {tot_diff}개(그중 띄어쓰기·대소문자만 다른 칸 {sum(x['loose_same'] for x in both)}개) · 양쪽 다 빈 칸 {sum(x['both_empty'] for x in both)}개")
    w(f"- 프로그램에만 있는 열 {len(c['only_ours'])}개 · 기준에만 있는 열 {len(c['only_base'])}개 · 공통 열의 순서 {'같음' if c['order_same'] else '다름'}")
    w("")
    w("## 1. 머리글")
    w("")
    w("### 기준에만 있는 열")
    for key in c["only_base"]:
        col = next(x for x in c["cols"] if x["key"] == key)
        vals = Counter(v for _, _, v in col["diffs"])
        w(f"- `{name(key)}` {col['label']} — 기준 값: " + (" · ".join(f"`{v}` ×{n}" for v, n in vals.most_common(8)) or "전부 빈 칸"))
    if not c["only_base"]:
        w("- 없음")
    w("")
    w("### 프로그램에만 있는 열")
    for key in c["only_ours"]:
        col = next(x for x in c["cols"] if x["key"] == key)
        vals = Counter(v for _, v, _ in col["diffs"])
        w(f"- `{name(key)}` {col['label']} — 프로그램 값: " + (" · ".join(f"`{v}` ×{n}" for v, n in vals.most_common(8)) or "전부 빈 칸"))
    if not c["only_ours"]:
        w("- 없음")
    w("")
    w("### 열 순서(기준 | 프로그램)")
    w("")
    w("| # | 기준 | 프로그램 |"); w("|---:|---|---|")
    ko, kb = [x for x in ours["keys"] if x], [x for x in base["keys"] if x]
    for i in range(max(len(ko), len(kb))):
        a, b = (name(kb[i]) if i < len(kb) else ""), (name(ko[i]) if i < len(ko) else "")
        w(f"| {i + 1} | {a} | {b}{'' if a == b else ' ◀'} |")
    w("")
    w("## 2. 양쪽에 다 있는 열의 값")
    w("")
    w("| 열 | 한글 이름 | 같은 칸 | 다른 칸 | 띄어쓰기만 다름 | 양쪽 빈 칸 |"); w("|---|---|---:|---:|---:|---:|")
    for x in both:
        w(f"| `{name(x['key'])}` | {x['label']} | {x['same']} | {x['diff']} | {x['loose_same']} | {x['both_empty']} |")
    w("")
    w("## 3. 다른 칸 전부(열마다)")
    w("")
    for x in both:
        if not x["diffs"]:
            continue
        w(f"### `{name(x['key'])}` {x['label']} — 다른 칸 {x['diff']}개")
        pairs = Counter((vo, vb) for _, vo, vb in x["diffs"])
        if len(pairs) <= 3 and x["diff"] > 3:
            for (vo, vb), n in pairs.most_common():
                rows = [r for r, a, b in x["diffs"] if (a, b) == (vo, vb)]
                w(f"- {n}개 행({_rows(rows)}): 프로그램 `{vo}` / 기준 `{vb}`")
        else:
            for r, vo, vb in x["diffs"]:
                w(f"- {r}행: 프로그램 `{vo}` / 기준 `{vb}`")
        w("")
    return "\n".join(L)


def _rows(rows: list[int]) -> str:
    out, i = [], 0
    while i < len(rows):
        j = i
        while j + 1 < len(rows) and rows[j + 1] == rows[j] + 1:
            j += 1
        out.append(str(rows[i]) if i == j else f"{rows[i]}~{rows[j]}")
        i = j + 1
    return ", ".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("ours"); ap.add_argument("base"); ap.add_argument("--out", default="")
    ns = ap.parse_args()
    ours, base = read(Path(ns.ours)), read(Path(ns.base))
    c = compare(ours, base)
    text = render(Path(ns.ours), Path(ns.base), ours, base, c)
    if ns.out:
        Path(ns.out).write_text(text, encoding="utf-8"); print(ns.out)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
