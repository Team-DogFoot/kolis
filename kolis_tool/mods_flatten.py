"""MODS XML → 열 펼치기. MODStoXL 출력 형식과 같은 열 이름을 쓴다.

열 이름 규칙(추출 예시 파일에서 확인):
  /mods/titleInfo/title            텍스트
  /mods/name[@type]                속성
  [1] /mods/name/namePart          같은 경로 2번째 등장, [2] 3번째 …
열 순서: 경로 문자열 알파벳순(추출 예시와 동일)
"""
from __future__ import annotations
import re
from collections import Counter
from pathlib import Path
from lxml import etree


def _local(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def flatten(xml_bytes: bytes) -> dict[str, str]:
    root = etree.fromstring(xml_bytes)
    # mods 루트 찾기 (modsCollection 감싸진 경우 포함)
    if _local(root.tag) != "mods":
        found = root.find(".//{*}mods")
        if found is None:
            raise ValueError("mods 요소 없음")
        root = found
    out: dict[str, str] = {}
    counter: Counter = Counter()

    def put(path: str, value: str):
        value = (value or "").strip()
        if value == "":
            return
        n = counter[path]
        key = path if n == 0 else f"[{n}] {path}"
        out[key] = value
        counter[path] += 1

    def walk(el, path):
        for k, v in el.attrib.items():
            put(f"{path}[@{_local(k)}]", v)
        children = [c for c in el if isinstance(c.tag, str)]
        if not children:
            put(path, el.text or "")
        for c in children:
            walk(c, f"{path}/{_local(c.tag)}")

    walk(root, "/mods")
    return out


def flatten_files(paths: list[Path]) -> tuple[list[str], list[dict[str, str]]]:
    rows = [flatten(Path(p).read_bytes()) for p in paths]
    cols = sorted({k for r in rows for k in r}, key=_sort_key)
    return cols, rows


def _sort_key(col: str):
    m = re.match(r"\[(\d+)\] (.*)", col)
    return (m.group(2), int(m.group(1))) if m else (col, 0)
