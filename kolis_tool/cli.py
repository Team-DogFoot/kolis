"""명령줄 진입점.  python -m kolis_tool <명령> ...

납품 폴더 → 반입용 엑셀은 프로그램 창에서 한다(bin\\app.vbs). 여기 있는 것은 에이전트가 작업 중에 쓰는 도구와 점검 도구다.

  render          (에이전트용) 페이지를 Edge 로 열어 화면 글자 출력
  check-research  (에이전트용) 조사 결과 파일의 형식·근거 검사
  write-import    (에이전트용) 반입용 값 검사 + 반입용 엑셀 쓰기
  unzip     출판사 zip 풀기(한글 파일명 cp949 깨짐 방지)
  inspect   원문 폴더 검수(깨짐·형식·중복·용량) → out/inspect.xlsx
  ids       전체출력 파일에서 콘텐츠ID 목록 추출 → work/ids.txt
  mods-fetch  콘텐츠ID 목록 → MODS XML 저장(미검증, HAR 확인 후 사용)
  mods-check  MODS XML 폴더 → 점검용 xlsx (매크로 대체)
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):     # 윈도 콘솔(cp949)에서 한글 출력 깨짐 방지, 진행 로그는 줄마다 바로 출력
    try:
        _stream.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:  # noqa: BLE001
        pass


def main(argv=None):
    ap = argparse.ArgumentParser(prog="kolis_tool", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("render", help="(에이전트용) 페이지를 Edge 로 열어 화면 글자 출력"); a.add_argument("url")
    a.add_argument("--scroll", type=int, default=0); a.add_argument("--links", action="store_true"); a.add_argument("--max", type=int, default=60000)
    a.add_argument("--find", default="", help="'단어1|단어2' — 그 단어가 든 줄과 앞뒤만 출력")
    a = sub.add_parser("check-research", help="(에이전트용) 조사 결과 파일의 형식·근거 검사"); a.add_argument("result"); a.add_argument("--job")
    a = sub.add_parser("write-import", help="(에이전트용) 반입용 값 검사 + 반입용 엑셀 쓰기"); a.add_argument("import_json")
    a = sub.add_parser("unzip", help="한글 파일명 깨짐 없이 zip 풀기(cp949)"); a.add_argument("zip"); a.add_argument("-o", "--out", required=True)
    a = sub.add_parser("inspect"); a.add_argument("root"); a.add_argument("-o", "--out", default="out")
    a = sub.add_parser("ids", help="전체출력 파일(.xls/HTML)에서 콘텐츠ID 목록 추출"); a.add_argument("export_file"); a.add_argument("-o", "--out", default="work/ids.txt")
    a = sub.add_parser("mods-fetch"); a.add_argument("ids_file"); a.add_argument("-o", "--out", default="work/xml"); a.add_argument("--config")
    a.add_argument("--preview", action="store_true", help="전송 없이 보낼 요청만 출력(HAR 대조용)")
    a = sub.add_parser("mods-check"); a.add_argument("xml_dir"); a.add_argument("--wonbu", required=True, help="원부번호")
    a.add_argument("--nth", type=int, default=1); a.add_argument("--year", default="2026"); a.add_argument("-o", "--out", default="out")
    ns = ap.parse_args(argv)

    if ns.cmd == "render":
        from .render import render
        print(render(ns.url, ns.scroll, ns.links, ns.max, ns.find))
    elif ns.cmd == "check-research":
        from .checks import main_check_research
        sys.exit(main_check_research(ns.result, ns.job))
    elif ns.cmd == "write-import":
        from .import_writer import main as write_main
        sys.exit(write_main(ns.import_json))
    elif ns.cmd == "unzip":
        from .unzip_kr import extract
        print(f"{extract(Path(ns.zip), Path(ns.out))}개 파일 → {ns.out}")
    elif ns.cmd == "inspect":
        from .inspect_files import inspect_root, write_reports
        res = inspect_root(Path(ns.root))
        j, x = write_reports(res, Path(ns.out))
        bad = [r for r in res if r.has_problem]
        print(f"폴더 {len(res)}개 검사, 문제 {len(bad)}개 → {x}")
        for r in bad: print(" -", r.folder, "|", " / ".join(r.problems))
    elif ns.cmd == "ids":
        from .ids_from_export import extract_ids
        ids = extract_ids(Path(ns.export_file))
        out = Path(ns.out); out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(ids) + "\n", encoding="utf-8")
        print(f"콘텐츠ID {len(ids)}건 → {out}")
    elif ns.cmd == "mods-fetch":
        from .mods_fetch import fetch_all, preview
        ids = [l.strip() for l in Path(ns.ids_file).read_text(encoding="utf-8").splitlines() if l.strip().startswith("CNTS")]
        if ns.preview:
            preview(ids, Path(ns.config) if ns.config else None); return
        print("KOLIS 에 실제 요청을 보냅니다. 실제 작품 점검 단계에서 직원과 함께일 때만 진행하세요. 계속하려면 YES 입력:")
        if input().strip() != "YES": sys.exit("중단")
        paths = fetch_all(ids, Path(ns.out), Path(ns.config) if ns.config else None)
        print(f"{len(paths)}건 저장 → {ns.out}")
    elif ns.cmd == "mods-check":
        from .mods_flatten import flatten_files
        from .mods_check import check_rows, write_check_xlsx, output_name
        xmls = sorted(Path(ns.xml_dir).glob("*.xml"))
        if not xmls: sys.exit("xml 없음")
        cols, rows = flatten_files(xmls)
        F = check_rows(cols, rows)
        out = Path(ns.out); out.mkdir(parents=True, exist_ok=True)
        p = write_check_xlsx(cols, rows, F, out / output_name(ns.year, ns.wonbu, ns.nth, F))
        errs = sum(1 for f in F if f.level == "error"); chk = len(F) - errs
        print(f"{len(rows)}건, 오류 {errs} / 확인 {chk} → {p}")


if __name__ == "__main__":
    main()
