"""에이전트용 도구 `look`: 원고 이미지를 읽을 수 있는 조각으로 만든다(형태가 정해진 일. 2026-10-04 개선안 3-B).

  python -m kolis_tool look <이미지 경로> [--fit] [--tiles] [--zoom <조각번호>:<상|중|하>] [--out <폴더>]

- --fit   : 원본을 긴 변 1500 으로 줄인 JPEG 한 장(큰 원본을 Read 하지 않게). 기본.
- --tiles : 세로로 긴 이미지를 폭과 같은 높이(1500×1500 안팎)의 조각으로 잘라 저장한다. 조각 번호는 1부터, 위에서 아래로.
- --zoom N:상|중|하 : N번 조각의 위·가운데·아래 1/3 을 2배로 확대한 파일 하나(작은 글자용). 좌표를 받지 않는다(에이전트가 좌표를 지어내지 않게).
출력: 만든 파일의 절대 경로를 한 줄에 하나씩. 첫 줄은 "원본: <절대 경로> <폭>x<높이>". 다른 명령을 뒤에 잇지 않는다.
저장 위치: --out 이 없으면 원본 옆이 아니라 <작업 폴더>/_look/<원본 이름>/ (prepare 가 끝날 때 지운다).
"""
from __future__ import annotations
import os, sys
from pathlib import Path
from PIL import Image, ImageFile

ImageFile.LOAD_TRUNCATED_IMAGES = True
LONG = 1500
TILE_H = 1500


def _out_dir(src: Path, out: str | None) -> Path:
    base = Path(out) if out else Path(os.environ.get("KOLIS_LOOK_DIR") or (Path.cwd() / "_look"))
    d = base / src.stem
    d.mkdir(parents=True, exist_ok=True)
    return d


def fit(src: Path, out: str | None = None) -> Path:
    d = _out_dir(src, out)
    dst = d / f"{src.stem}_fit.jpg"
    with Image.open(src) as im:
        im = im.convert("RGB")
        w, h = im.size
        s = LONG / max(w, h)
        if s < 1:
            im = im.resize((max(1, int(w * s)), max(1, int(h * s))), Image.Resampling.LANCZOS)
        im.save(dst, "JPEG", quality=85)
    return dst


def tiles(src: Path, out: str | None = None) -> list[Path]:
    d = _out_dir(src, out)
    paths = []
    with Image.open(src) as im:
        im = im.convert("RGB")
        w, h = im.size
        s = LONG / w if w > LONG else 1.0
        if s < 1:
            im = im.resize((int(w * s), int(h * s)), Image.Resampling.LANCZOS)
            w, h = im.size
        n = max(1, (h + TILE_H - 1) // TILE_H)
        for i in range(n):
            top = i * TILE_H
            tile = im.crop((0, top, w, min(h, top + TILE_H)))
            p = d / f"{src.stem}_tile{i + 1:03d}.jpg"
            tile.save(p, "JPEG", quality=85)
            paths.append(p)
    return paths


def zoom(src: Path, spec: str, out: str | None = None) -> Path:
    n_s, _, part = spec.partition(":")
    n = int(n_s)
    part = part or "중"
    d = _out_dir(src, out)
    with Image.open(src) as im:
        im = im.convert("RGB")
        w, h = im.size
        s = LONG / w if w > LONG else 1.0
        if s < 1:
            im = im.resize((int(w * s), int(h * s)), Image.Resampling.LANCZOS); w, h = im.size
        top = (n - 1) * TILE_H
        tile = im.crop((0, top, w, min(h, top + TILE_H)))
        th = tile.size[1]
        third = {"상": 0, "중": 1, "하": 2}.get(part, 1)
        y0 = int(th * third / 3); y1 = int(th * (third + 1) / 3)
        band = tile.crop((0, y0, w, y1))
        band = band.resize((band.size[0] * 2, band.size[1] * 2), Image.Resampling.LANCZOS)
        p = d / f"{src.stem}_tile{n:03d}_{part}_x2.jpg"
        band.save(p, "JPEG", quality=90)
    return p


def main(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="kolis_tool look")
    ap.add_argument("image"); ap.add_argument("--fit", action="store_true"); ap.add_argument("--tiles", action="store_true")
    ap.add_argument("--zoom", default=""); ap.add_argument("--out", default="")
    ns = ap.parse_args(argv)
    src = Path(ns.image).expanduser().resolve()
    if not src.is_file():
        print(f"파일이 없습니다: {src}"); return 1
    try:
        with Image.open(src) as im:
            w, h = im.size
    except Exception as e:  # noqa: BLE001
        print(f"이미지를 열 수 없습니다: {src} ({type(e).__name__}: {e})"); return 1
    print(f"원본: {src} {w}x{h}")
    out = ns.out or None
    if ns.zoom:
        print(zoom(src, ns.zoom, out).resolve()); return 0
    if ns.tiles:
        for p in tiles(src, out):
            print(p.resolve())
        return 0
    print(fit(src, out).resolve())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
