"""원문을 "전부" 봤는지와 색의 증거 검사(판단하지 않는다). 2026-10-04 유저 확정: 작품 전체 = 회차 전체 × 장 전체 × 그림 전체.

실작품 시험(로맨스 낫 로맨틱 45회차)에서 드러난 두 가지를 판단이 아니라 측정·기록 대조로 막는다.
  1. 조각 건너뛰기: 관찰 에이전트가 "봤다"고 적은 장이 실제로 전부 열렸는지를 실행기의 Read 호출 기록으로 대조한다.
     세로로 긴 이미지는 look --tiles 가 만드는 조각 **전부**가 Read 되어야 한다(조각 수는 이미지 크기로 계산).
  2. 색 오판: 관찰 모델이 채도 비율 0.03~0.16 을 "거의 무채색"으로 읽어 천연색 회차를 흑백으로 적었다.
     → 장마다 색이 있는지는 코드가 잰다(colored = 색 있는 화소 비율 > COLOR_THRESHOLD). 에이전트는 그 사실로 규칙만 적용한다.
"""
from __future__ import annotations
import json
from pathlib import Path
from PIL import Image

from .look import TILE_W, TILE_H

COLOR_THRESHOLD = 0.01        # 채도 있는 화소(S>0.2, V>0.15)가 1% 를 넘으면 그 장에는 색이 있다
LONG_RATIO = 2.0              # 높이가 폭의 2배를 넘으면 조각으로 봐야 글자가 읽힌다
COVER_KINDS = ("표지", "타이틀컷", "판권면", "광고")     # 이 종류의 장에만 색이 있으면 '표지만 천연색' 규칙(직원 2026-10-01) → 흑백


def tiles_expected(path: Path) -> int:
    """look --tiles 가 만드는 조각 수. 0 이면 조각이 필요 없는 장(축소본 한 장 또는 원본을 보면 된다). 머리만 읽어 빠르다."""
    with Image.open(path) as im:
        w, h = im.size
    if h <= LONG_RATIO * w:
        return 0
    s = TILE_W / w if w > TILE_W else 1.0
    return max(1, (int(h * s) + TILE_H - 1) // TILE_H)


def _norm(p: str) -> str:
    return str(p).replace("\\", "/").lower()


def read_gaps(images: list[Path], reads: set[str]) -> list[dict]:
    """이미지마다 실제로 열린 기록이 있는지. 돌려주는 것: 빠진 것만 [{"image", "need", "missing"}].
    reads = 실행기가 모은 Read 도구의 파일 경로(하위 에이전트 포함). 'look:' 으로 시작하는 항목(명령만 부른 것)은 본 것으로 치지 않는다."""
    seen = [_norm(r) for r in reads if not str(r).startswith("look:")]
    out = []
    for p in images:
        folder, stem = p.parent.name, p.stem
        n = tiles_expected(p)
        base = _norm(f"{folder}_{stem}/{stem}")
        if n:
            missing = [i for i in range(1, n + 1) if not any(r.endswith(f"{base}_tile{i:03d}.jpg") for r in seen)]
            if missing:
                out.append({"image": p.name, "need": f"조각 {n}개", "missing": missing})
        else:
            ok = any(r.endswith(f"{base}_fit.jpg") or r.endswith(_norm(f"{folder}/{p.name}")) or r.endswith(f"{base}_tile001.jpg") for r in seen)
            if not ok:
                out.append({"image": p.name, "need": "축소본 또는 원본", "missing": ["전체"]})
    return out


def color_ratio_fast(path: Path) -> float:
    """색 있는 화소의 비율(0~1). JPEG 은 줄여서 풀어 빠르게 잰다."""
    with Image.open(path) as im:
        if im.mode in ("L", "1"):
            return 0.0
        try:
            im.draft("RGB", (256, 256))
        except Exception:  # noqa: BLE001
            pass
        small = im.convert("RGB")
        small.thumbnail((256, 256))
        n = colored = 0
        for h, s, v in small.convert("HSV").getdata():
            n += 1
            if s > 51 and v > 38:
                colored += 1
    return colored / n if n else 0.0


def measure_colors(images: list[Path], cache: Path | None = None) -> dict[str, float]:
    """{파일 이름: 색 비율}. cache 가 있으면 파일 크기가 같을 때 다시 재지 않는다."""
    old = {}
    if cache and cache.exists():
        try:
            old = json.loads(cache.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            old = {}
    out, store = {}, {}
    for p in images:
        size = p.stat().st_size
        hit = old.get(p.name)
        if hit and hit.get("size") == size:
            r = float(hit["ratio"])
        else:
            r = round(color_ratio_fast(p), 4)
        out[p.name] = r; store[p.name] = {"size": size, "ratio": r}
    if cache:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(store, ensure_ascii=False), encoding="utf-8")
    return out


def color_claim_problem(claim: str, ratios: dict[str, float], kinds: dict[str, str]) -> str | None:
    """행의 색(천연색/흑백)이 측정과 어긋나면 그 이유를 글로. 맞으면 None.
    규칙: 색 있는 장이 하나도 없으면 흑백 / 색 있는 장이 표지류뿐이면 흑백(직원 규칙) / 본문에 색 있는 장이 있으면 천연색(매뉴얼 7.4)."""
    colored = [n for n, r in ratios.items() if r > COLOR_THRESHOLD]
    body_colored = [n for n in colored if (kinds.get(n) or "본문") not in COVER_KINDS]
    total = len(ratios)
    if claim == "천연색" and not colored:
        return f"천연색으로 적었지만 측정으로는 {total}장 모두 무채색입니다"
    if claim == "천연색" and colored and not body_colored:
        return f"천연색으로 적었지만 색이 있는 장은 표지류 {len(colored)}장뿐입니다(표지만 천연색이고 내용이 흑백이면 흑백)"
    if claim == "흑백" and body_colored:
        return (f"흑백으로 적었지만 측정으로는 본문 {len(body_colored)}장(전체 {total}장 중 색 있는 장 {len(colored)}장)에 색이 있습니다. "
                f"색 비율이 0.01(1%)을 넘으면 색이 있는 장입니다(0.03 도 색이 있는 장). 예: {body_colored[:3]}")
    return None


def observation_problems(obs: dict, images: list[Path], reads: set[str] | None) -> list[str]:
    """관찰 파일 하나의 증거 검사: 장 목록, 건너뛴 조각, 실제 Read 기록."""
    out = []
    want = [p.name for p in images]
    seen = [str(n) for n in obs.get("images_viewed") or []]
    miss = [n for n in want if n not in seen]
    if miss:
        out.append(f"images_viewed 에 폴더 이미지 {len(miss)}장이 없습니다(처음 {miss[:3]}). 전부 봐야 합니다")
    pages = obs.get("pages") or []
    if len(pages) < len(want):
        out.append(f"pages 가 {len(pages)}장뿐입니다(폴더 이미지 {len(want)}장). 장마다 기록하세요")
    skipped = [(pg.get("file"), pg.get("skipped_tiles")) for pg in pages if pg.get("skipped_tiles")]
    if skipped:
        out.append(f"건너뛴 조각이 있습니다: {skipped[:4]}. 조각은 전부 봐야 합니다(글자가 없어 보여도). 그 장을 다시 보고 skipped_tiles 를 비우세요")
    if reads is not None:
        gaps = read_gaps(images, reads)
        if gaps:
            ex = "; ".join(f"{g['image']}({g['need']}, 빠진 것 {g['missing'][:6]})" for g in gaps[:4])
            out.append(f"실제로 열어 본 기록이 없는 장·조각이 {len(gaps)}장에 있습니다: {ex}. 목록만 적지 말고 look 으로 만든 조각을 전부 Read 하세요")
    return out
