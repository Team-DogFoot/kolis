"""한글 파일명이 깨지는 zip 풀기. 윈도에서 만든 zip 은 파일명이 cp949 로 들어 있어
맥·리눅스 기본 unzip 이나 일부 윈도 도구에서 '�?��?��?�' 처럼 깨진다. utf-8 플래그가 없는 항목은 cp949 로 재해석한다."""
from __future__ import annotations
import zipfile
from pathlib import Path


def extract(zip_path: Path, dest: Path) -> int:
    dest = Path(dest); dest.mkdir(parents=True, exist_ok=True)
    n = 0
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            name = info.filename
            if not (info.flag_bits & 0x800):          # utf-8 플래그 없음 → cp437 로 읽힌 바이트를 cp949 로
                try:
                    name = name.encode("cp437").decode("cp949")
                except (UnicodeEncodeError, UnicodeDecodeError):
                    pass
            target = dest / name
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True); continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, open(target, "wb") as out:
                out.write(src.read())
            n += 1
    return n
