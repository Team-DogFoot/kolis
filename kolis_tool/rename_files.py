"""③ 파일명 정리: 폴더 안 이미지 파일을 8자리 일련번호(00000001.jpg ...)로 변경. 다크네이머 대체.

- 자연 정렬(숫자 순)로 순서를 정한다.
- 원래 이름은 rename_manifest.json 에 남기고 --undo 로 되돌린다.
- 확장자는 소문자로 통일하되 jpeg→jpg 로 바꾸지 않는다(내용 변경 없음).
"""
from __future__ import annotations
import json
from pathlib import Path
from .common import list_images

MANIFEST = "rename_manifest.json"


def plan(folder: Path, start: int = 1, digits: int = 8) -> list[tuple[Path, Path]]:
    files = list_images(folder)
    pairs = []
    for i, p in enumerate(files, start):
        pairs.append((p, folder / f"{i:0{digits}d}{p.suffix.lower()}"))
    return pairs


def apply(folder: Path, start: int = 1, digits: int = 8, dry_run: bool = False) -> list[tuple[str, str]]:
    folder = Path(folder)
    if (folder / MANIFEST).exists():
        raise SystemExit(f"{folder}: 이미 이름을 바꾼 폴더입니다({MANIFEST} 존재). --undo 후 다시 하세요.")
    pairs = plan(folder, start, digits)
    if dry_run:
        return [(a.name, b.name) for a, b in pairs]
    # 충돌 방지 2단계: 임시 이름 → 최종 이름
    tmp = []
    for a, b in pairs:
        t = a.with_name(f"__tmp__{a.name}")
        a.rename(t); tmp.append((t, b, a.name))
    done = []
    for t, b, orig in tmp:
        t.rename(b); done.append((orig, b.name))
    (folder / MANIFEST).write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
    return done


def undo(folder: Path) -> int:
    folder = Path(folder)
    m = folder / MANIFEST
    if not m.exists():
        raise SystemExit(f"{folder}: {MANIFEST} 없음")
    done = json.loads(m.read_text(encoding="utf-8"))
    for orig, new in done:
        (folder / new).rename(folder / f"__tmp__{orig}")
    for orig, new in done:
        (folder / f"__tmp__{orig}").rename(folder / orig)
    m.unlink()
    return len(done)


def apply_tree(root: Path, **kw) -> dict[str, list]:
    root = Path(root)
    out = {}
    targets = [root] if list_images(root) else [p for p in sorted(root.iterdir()) if p.is_dir() and list_images(p)]
    for t in targets:
        out[str(t)] = apply(t, **kw)
    return out
