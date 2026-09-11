"""명령줄 진입점.  python -m kolis_tool <명령> ...

  inspect   원문 폴더 검수(깨짐·형식·중복·용량) → out/inspect.xlsx
  rename    8자리 일련번호 파일명 변경(--dry-run, --undo)
  convert   출판사용 엑셀 → 반입용 엑셀(규칙 부분, 확인 필요 셀 노란색)
  agent     반입용 엑셀의 확인 필요 셀을 LLM 이 보완 → '제안' 시트(사람 승인 후 --apply)
  ids       전체출력 파일에서 콘텐츠ID 목록 추출 → work/ids.txt
  mods-fetch  콘텐츠ID 목록 → MODS XML 저장(미검증, HAR 확인 후 사용)
  mods-check  MODS XML 폴더 → 점검용 xlsx (매크로 대체)
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):     # 윈도 콘솔(cp949)에서 한글 출력 깨짐 방지
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def main(argv=None):
    ap = argparse.ArgumentParser(prog="kolis_tool", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("inspect"); a.add_argument("root"); a.add_argument("-o", "--out", default="out")
    a = sub.add_parser("rename"); a.add_argument("root"); a.add_argument("--start", type=int, default=1)
    a.add_argument("--digits", type=int, default=8); a.add_argument("--dry-run", action="store_true"); a.add_argument("--undo", action="store_true")
    a = sub.add_parser("convert"); a.add_argument("publisher_xlsx"); a.add_argument("--template", required=True)
    a.add_argument("-o", "--out", required=True); a.add_argument("--root", help="원문 상위 폴더(작품별 하위폴더)")
    a.add_argument("--publisher-place", help="출판사→발행지 JSON")
    a = sub.add_parser("agent", help="반입용 xlsx 노란 셀을 LLM 으로 보완 → '제안' 시트"); a.add_argument("xlsx")
    a.add_argument("--root", help="원문 상위 폴더"); a.add_argument("--dry-run", action="store_true", help="API 호출 없이 질의 묶음 json 만 생성")
    a.add_argument("--limit", type=int); a.add_argument("--apply", action="store_true", help="'제안' 시트의 승인(Y) 행을 본문에 반영")
    a.add_argument("--runner", choices=["claude", "codex", "api"], default="claude", help="claude=claude -p 헤드리스(기본), codex=codex exec, api=Claude API 직접")
    a = sub.add_parser("ids", help="전체출력 파일(.xls/HTML)에서 콘텐츠ID 목록 추출"); a.add_argument("export_file"); a.add_argument("-o", "--out", default="work/ids.txt")
    a = sub.add_parser("mods-fetch"); a.add_argument("ids_file"); a.add_argument("-o", "--out", default="work/xml"); a.add_argument("--config")
    a.add_argument("--preview", action="store_true", help="전송 없이 보낼 요청만 출력(HAR 대조용)")
    a = sub.add_parser("mods-check"); a.add_argument("xml_dir"); a.add_argument("--wonbu", required=True, help="원부번호")
    a.add_argument("--nth", type=int, default=1); a.add_argument("--year", default="2026"); a.add_argument("-o", "--out", default="out")
    ns = ap.parse_args(argv)

    if ns.cmd == "inspect":
        from .inspect_files import inspect_root, write_reports
        res = inspect_root(Path(ns.root))
        j, x = write_reports(res, Path(ns.out))
        bad = [r for r in res if r.has_problem]
        print(f"폴더 {len(res)}개 검사, 문제 {len(bad)}개 → {x}")
        for r in bad: print(" -", r.folder, "|", " / ".join(r.problems))
    elif ns.cmd == "rename":
        from .rename_files import apply_tree, undo
        if ns.undo:
            root = Path(ns.root)
            targets = [root] if (root / "rename_manifest.json").exists() else [p for p in root.iterdir() if (p / "rename_manifest.json").exists()]
            for t in targets: print(t, "되돌림", undo(t), "개")
        else:
            res = apply_tree(Path(ns.root), start=ns.start, digits=ns.digits, dry_run=ns.dry_run)
            for folder, pairs in res.items():
                print(folder, f"{len(pairs)}개", "(미리보기)" if ns.dry_run else "")
                for a, b in pairs[:3]: print("   ", a, "→", b)
    elif ns.cmd == "convert":
        from .convert_import import convert
        n, f = convert(Path(ns.publisher_xlsx), Path(ns.template), Path(ns.out), Path(ns.root) if ns.root else None,
                       Path(ns.publisher_place) if ns.publisher_place else None)
        print(f"{n}행 변환, 확인 필요 셀 {f}개 → {ns.out}")
    elif ns.cmd == "agent":
        from .agent_fill import run, apply_approved
        if ns.apply:
            print(f"승인 {apply_approved(Path(ns.xlsx))}건 반영")
        else:
            run(Path(ns.xlsx), Path(ns.root) if ns.root else None, ns.dry_run, ns.limit, ns.runner)
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
