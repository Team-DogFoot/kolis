"""개발용 시험: 예시 파일(완료사례_코리스반입용_로맨스낫로맨틱(88열).xlsx)을 import.json 꼴로 역변환해 양식 쓰기로 다시 쓰고,
① 머리글 열 목록이 예시와 같은지 ② 에이전트가 정하는 칸이 셀 단위로 같은지(수량·파일 형식·썸네일 제외) 본다. 원고 폴더 없이 돈다.
실행: .venv/Scripts/python.exe -X utf8 tools/import_roundtrip.py"""
import sys, json
from pathlib import Path
import openpyxl
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from kolis_tool import import_writer as iw

EX = Path("docs/source/3_샘플양식/완료사례_코리스반입용_로맨스낫로맨틱(88열).xlsx")
OUT = Path("work/eval/roundtrip_로맨스낫로맨틱.xlsx")
SKIP = {"/mods/physicalDescription/extent", "/mods/physicalDescription/internetMediaType", "thum_files"}


def read(xlsx):
    ws = openpyxl.load_workbook(xlsx, read_only=True)["Contents"]
    rows = list(ws.iter_rows(values_only=True))
    h = [(c or "").strip() if isinstance(c, str) else "" for c in rows[0]]
    keys, seen = [], {}
    for x in h:
        keys.append((x, seen.get(x, 0))); seen[x] = seen.get(x, 0) + 1
    data = [dict(zip(keys, r)) for r in rows[1:] if any(c not in (None, "") for c in r)]
    return h, keys, data


def to_import(keys, data):
    rows = []
    for i, r in enumerate(data, 1):
        g = lambda k, n=0: ("" if r.get((k, n)) is None else str(r.get((k, n)))).strip()
        names = []
        for n in range(8):
            nm = g("/mods/name/namePart", n)
            if nm:
                names.append({"name": nm, "type": g("/mods/name[@type]", n) or "개인명", "role": g("/mods/name/role/roleTerm", n)})
        pubs = [g("/mods/originInfo/publisher", n) for n in range(1, 4) if g("/mods/originInfo/publisher", n)]
        # 둘째 출처정보가 비어 있으면 첫 출처정보 발행처들만 publishers
        v = {"title": g("/mods/titleInfo/title"), "subTitle": g("/mods/titleInfo/subTitle"), "partNumber": g("/mods/titleInfo/partNumber"), "partName": g("/mods/titleInfo/partName"),
             "names": names, "publisher": g("/mods/originInfo/publisher"), "publishers": pubs, "place": g("/mods/originInfo/place/placeTerm"), "place_code": g("/mods/originInfo/place/placeTerm", 1),
             "dateIssued": g("/mods/originInfo/dateIssued"), "edition": g("/mods/originInfo/edition"), "targetAudience": g("/mods/targetAudience"),
             "other_note": g("/mods/note"), "audience_note": g("/mods/note", 1), "acquisition_note": g("/mods/note", 2),
             "identifier": g("/mods/identifier"), "identifier_type": g("/mods/identifier[@type]"), "url_main": g("/mods/location/url"), "url_work": g("/mods/location/url", 1),
             "licenseType": g("/mods/accessCondition/licenseType"), "price": g("contents_price"), "compensation": g("compensation"), "reward_yn": g("reward_yn"), "color": "천연색"}
        rows.append({"no": i, "folder": f"row{i}", "thumb_file": g("thum_files"), "values": v, "confirm": []})
    return {"title": rows[0]["values"]["title"], "manuscripts_root": "원고", "rows": rows, "review": {"done": True, "findings": [], "resolved": []}}


def main():
    h_ex, keys_ex, data_ex = read(EX)
    imp = to_import(keys_ex, data_ex)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    r = iw.write(imp, None, OUT)
    h_out, keys_out, data_out = read(OUT)
    print(f"예시 {len(h_ex)}열 / 산출 {r['columns']}열 / 행 {len(data_ex)} vs {len(data_out)}")
    if h_ex != h_out:
        import difflib
        print("머리글 다름:")
        for l in difflib.unified_diff(h_ex, h_out, "예시", "산출", lineterm="", n=0):
            print("  ", l)
    else:
        print("머리글 열 목록 동일")
    bad = 0
    for i, (a, b) in enumerate(zip(data_ex, data_out), 1):
        for k in keys_ex:
            if k[0] in SKIP or k[0] == "":
                continue
            va, vb = a.get(k), b.get(k)
            na = "" if va is None else str(va).strip(); nb = "" if vb is None else str(vb).strip()
            if na != nb:
                bad += 1
                if bad <= 25:
                    print(f"  {i}행 {k[0]}#{k[1]+1}: 예시 {na!r} ≠ 산출 {nb!r}")
    print("셀 불일치:", bad, "(수량·파일 형식·썸네일 제외)")
    return 0 if (h_ex == h_out and bad == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
