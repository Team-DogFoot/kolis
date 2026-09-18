"""③-4 반입 결과 → 원고 폴더명을 콘텐츠ID(CNTS-…)로. 가이드 3.4-가 "반입 결과 확인 후 생성된 콘텐츠ID(CNTS번호)로 원문파일 폴더명 수정".

입력: 전체출력 파일(ExcelDown….xls, 접수번호 811-N ↔ 콘텐츠ID), 원고 상위 폴더(회차 폴더 001, 002 … 또는 EP01 …).
짝짓기: 접수번호 뒤 숫자 N = 반입용 엑셀 N번째 행 = 회차 폴더를 자연 정렬한 N번째. 폴더 수와 반입 건수가 다르면 중단.
되돌리기: 상위 폴더에 cnts_manifest.json.
"""
from __future__ import annotations
import json
from pathlib import Path
from .common import natural_key, list_images
from .ids_from_export import receipt_map

MANIFEST = "cnts_manifest.json"


def episode_folders(root: Path) -> list[Path]:
    return sorted((p for p in Path(root).iterdir() if p.is_dir() and list_images(p)), key=lambda p: natural_key(p.name))


def plan(export_file: Path, root: Path) -> dict:
    root = Path(root)
    if (root / MANIFEST).exists():
        raise SystemExit(f"이미 바꾼 폴더입니다({MANIFEST} 존재). 되돌린 뒤 다시 하세요.")
    m = receipt_map(export_file)
    folders = episode_folders(root)
    if not m:
        raise SystemExit("전체출력 파일에서 접수번호·콘텐츠ID 를 찾지 못했습니다")
    if len(m) != len(folders):
        raise SystemExit(f"반입 건수 {len(m)} ≠ 회차 폴더 수 {len(folders)} — 짝을 지을 수 없습니다")
    seqs = [x["seq"] for x in m]
    if seqs != list(range(1, len(m) + 1)):
        raise SystemExit(f"접수번호 순번이 1..{len(m)} 연속이 아닙니다: {seqs[:5]}…")
    pairs = [(f, root / x["cnts"], x["no"]) for f, x in zip(folders, m)]
    dup = [p for p in pairs if p[1].exists() and p[1] != p[0]]
    if dup:
        raise SystemExit(f"이미 같은 이름의 폴더가 있습니다: {dup[0][1].name}")
    return {"receipt": m[0]["no"].split("-")[0], "title": m[0]["title"], "count": len(pairs),
            "pairs": [(a.name, b.name, no) for a, b, no in pairs]}


def apply(export_file: Path, root: Path) -> dict:
    root = Path(root)
    p = plan(export_file, root)
    done = []
    for a, b, no in p["pairs"]:
        (root / a).rename(root / b); done.append([a, b, no])
    (root / MANIFEST).write_text(json.dumps({"receipt": p["receipt"], "done": done}, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


def undo(root: Path) -> int:
    root = Path(root); mf = root / MANIFEST
    data = json.loads(mf.read_text(encoding="utf-8"))
    n = 0
    for a, b, _ in reversed(data["done"]):
        if (root / b).exists():
            (root / b).rename(root / a); n += 1
    mf.unlink()
    return n
