"""로컬 OCR 힌트(선택, 비용 0): 이미지에 어떤 글자가 있는지 미리 뽑아 관찰 에이전트가 어느 장을 자세히 볼지 정하게 한다. 근거가 아니라 힌트다.
- 맥(개발용 임시): Vision 프레임워크(pyobjc-framework-Vision). 한국어·영어.
- 윈도(도서관 PC): 지금은 없음(향후 Windows.Media.Ocr). 없으면 빈 문자열을 돌려주고 inspect-folder 는 `ocr_available: false` 로 알린다.
"""
from __future__ import annotations
import sys
from pathlib import Path


def available() -> bool:
    if sys.platform != "darwin":
        return False
    try:
        import Vision  # noqa: F401
        import Quartz  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def ocr_image(path: Path, max_chars: int = 600, max_side: int = 2000) -> str:
    """이미지의 글자를 위에서 아래 순서로 한 줄씩(요약 힌트)."""
    tiles = ocr_tiles(path)
    out = " / ".join(t for _, txt in tiles for t in txt if t.strip())
    return out[:max_chars]


def ocr_tiles(path: Path) -> list[tuple[int, list[str]]]:
    """look --tiles 와 같은 조각 번호(1부터)로 글자를 나눠 돌려준다: [(조각 번호, [글자 줄…]), …]. OCR 이 없으면 빈 목록."""
    if not available():
        return []
    from PIL import Image
    import io
    from .look import TILE_W, TILE_H
    out = []
    with Image.open(path) as im:
        im = im.convert("RGB")
        w, h = im.size
        s = TILE_W / w if w > TILE_W else 1.0
        tile_h_orig = int(TILE_H / s)
        n = max(1, (h + tile_h_orig - 1) // tile_h_orig)
        for i in range(n):
            top = i * tile_h_orig
            tile = im.crop((0, top, w, min(h, top + tile_h_orig)))
            if tile.size[0] > 1500:
                tile = tile.resize((1500, int(tile.size[1] * 1500 / tile.size[0])))
            buf = io.BytesIO(); tile.save(buf, "JPEG", quality=85)
            out.append((i + 1, _ocr_bytes(buf.getvalue())))
    return out


def _ocr_bytes(data: bytes) -> list[str]:
    import Vision, Quartz
    from Foundation import NSData
    nsdata = NSData.dataWithBytes_length_(data, len(data))
    src = Quartz.CGImageSourceCreateWithData(nsdata, None)
    if src is None:
        return []
    cg = Quartz.CGImageSourceCreateImageAtIndex(src, 0, None)
    if cg is None:
        return []
    req = Vision.VNRecognizeTextRequest.alloc().init()
    req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    req.setRecognitionLanguages_(["ko-KR", "en-US"])
    req.setUsesLanguageCorrection_(False)
    handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(cg, None)
    ok, err = handler.performRequests_error_([req], None)
    if not ok:
        return []
    out = []
    results = req.results() or []
    # 위에서 아래(Vision 좌표는 아래가 0)
    items = []
    for r in results:
        cand = r.topCandidates_(1)
        if not cand:
            continue
        box = r.boundingBox()
        items.append((1 - box.origin.y, str(cand[0].string())))
    for _, t in sorted(items, key=lambda x: x[0]):
        out.append(t)
    return out
