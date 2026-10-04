"""KOLIS 가 돌려주는 MODS XML ↔ 트리(반입용 import.json 과 같은 꼴) ↔ 평면(경로: 값). 2026-10-04 B·C 단계 공용.

- tree_from_xml(xml)      : <mods:…> → {"titleInfo": [...], "name": [...], …} (mods_sheet 의 트리 표기. 속성 "@x", 글자 "_")
- flat(tree)              : {"titleInfo[0].title": "…", "name[1].@ID": "…"} (경로 = mods_sheet.get 과 같은 표기)
- sheet_columns(trees)    : 점검 시트용 열 이름(가이드·매크로 꼴 "[n] /mods/name/namePart" — 같은 경로의 n+1 번째 등장)과 행 값
- normalize(path, value)  : KOLIS 가 저장 때 스스로 바꾸는 표기(JPG↔image/jpg, BornDigital↔born digital, 개인명↔personal, 단체명↔corporate)를 같은 것으로
- diff(a, b)              : 두 트리의 다른 경로 목록
"""
from __future__ import annotations
import json, re
from pathlib import Path
import xml.etree.ElementTree as ET

NS = "http://www.loc.gov/mods/v3"
LABELS: dict[str, str] = json.loads((Path(__file__).parent / "mods_labels.json").read_text(encoding="utf-8"))
# 저장 때 KOLIS 가 바꾸는 표기 — 같은 값으로 본다
AUTO_EQUIV = {"image/jpg": "JPG", "image/jpeg": "JPEG", "born digital": "BornDigital", "personal": "개인명", "corporate": "단체명", "conference": "회의명"}
# KOLIS 가 저장·등록 때 스스로 넣거나 바꾸는 경로(반입값 대조에서 '다름'으로 치지 않는다)
AUTO_PATHS = ("recordInfo", "accessCondition", "physicalDescription.extent", "physicalDescription.internetMediaType", "physicalDescription.digitalOrigin",
              "originInfo[0].dateIssued.@encoding", "useObjCode", "titleInfo[0].@ID", "name[0].@nameTitleGroup")
REPEAT_TOP = {"titleInfo", "name", "originInfo", "note", "subject", "identifier", "classification", "relatedItem"}
REPEAT_IN = {"name": {"alternativeName"}, "originInfo": {"place", "publisher"}, "location": {"url"}, "relatedItem": {"titleInfo", "name"}}   # 반입 트리와 같은 모양(namePart 둘이면 목록이 된다)


def _local(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def tree_from_xml(xml_text: str) -> dict:
    """mods XML → 트리. 반복 요소는 목록으로(REPEAT_*), 그 밖은 하나로. 요소 글자는 "_"(자식·속성이 없으면 글자만)."""
    if not xml_text:
        return {}
    root = ET.fromstring(xml_text)
    if _local(root.tag) != "mods":
        found = root.find(".//{%s}mods" % NS)
        if found is None:
            raise ValueError("mods 요소 없음")
        root = found
    t = _node(root, "")
    for k in [k for k in t if k.startswith("@")]:      # 루트 속성(version, schemaLocation)은 값이 아니다
        t.pop(k)
    return t


def _node(el, parent_name: str):
    attrs = {f"@{_local(k)}": v for k, v in el.attrib.items() if _local(k) not in ("schemaLocation",)}
    if _local(el.tag) == "alternativeName" and "@altType" in attrs:      # 반입 양식·트리는 [@type] 로 쓴다(반입되면 altType 이 된다)
        attrs["@type"] = attrs.pop("@altType")
    kids = [c for c in el if isinstance(c.tag, str)]
    text = (el.text or "").strip()
    if not kids and not attrs:
        return text
    out: dict = {}
    if text:
        out["_"] = text
    out.update(attrs)
    name_here = _local(el.tag)
    for c in kids:
        cn = _local(c.tag)
        v = _node(c, name_here)
        repeat = (name_here == "mods" and cn in REPEAT_TOP) or (cn in REPEAT_IN.get(name_here, set()))
        if repeat:
            out.setdefault(cn, [])
            if not isinstance(out[cn], list):
                out[cn] = [out[cn]]
            out[cn].append(v)
        elif cn in out:
            out[cn] = [out[cn], v] if not isinstance(out[cn], list) else out[cn] + [v]
        else:
            out[cn] = v
    return out


def flat(tree: dict, prefix: str = "") -> dict[str, str]:
    """트리 → {경로: 글자}. 경로 표기는 mods_sheet.get 과 같다(name[1].alternativeName[0].namePart, originInfo[0].@eventType)."""
    out: dict[str, str] = {}

    def walk(node, path):
        if node is None:
            return
        if isinstance(node, list):
            for i, x in enumerate(node):
                walk(x, f"{path}[{i}]")
            return
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "_":
                    if str(v).strip():
                        out[path] = str(v).strip()
                elif k.startswith("@"):
                    if str(v).strip():
                        out[f"{path}.{k}"] = str(v).strip()
                else:
                    walk(v, f"{path}.{k}" if path else k)
            return
        if str(node).strip():
            out[path] = str(node).strip()

    walk(tree, prefix)
    return out


def normalize(path: str, value: str) -> str:
    v = (value or "").strip()
    return AUTO_EQUIV.get(v, v)


def is_auto(path: str) -> bool:
    return any(path.startswith(p) or f".{p}" in path for p in AUTO_PATHS)


def diff(import_tree: dict, kolis_tree: dict) -> list[dict]:
    """반입값(정본) ↔ KOLIS 값. 돌려주는 것: [{path, label, import, kolis, kind}] kind = auto(KOLIS 가 스스로 바꿈) | diff(다름)."""
    a, b = flat(import_tree), flat(kolis_tree)
    out = []
    for p in sorted(set(a) | set(b)):
        va, vb = a.get(p, ""), b.get(p, "")
        if normalize(p, va) == normalize(p, vb):
            continue
        kind = "auto" if is_auto(p) or (not va and p.endswith(("@encoding", "@ID")) and "titleInfo" in p) else "diff"
        out.append({"path": p, "label": label_for(p), "import": va, "kolis": vb, "kind": kind})
    return out


def label_for(path: str) -> str:
    """경로 → 한글 이름(mods_labels.json 의 '/mods/…' 키로)."""
    xp = "/mods/" + re.sub(r"\[\d+\]", "", path).replace(".@", "[@").replace(".", "/")
    if "[@" in xp:
        xp = xp + "]"
    return LABELS.get(xp) or xp.rsplit("/", 1)[-1]


def xpath_of(path: str) -> str:
    """경로 → '/mods/name/namePart' 꼴(속성은 [@x])."""
    xp = "/mods/" + re.sub(r"\[\d+\]", "", path).replace(".@", "[@").replace(".", "/")
    return xp + "]" if "[@" in xp else xp


# ---------------------------------------------------------------- 점검 시트용 평면(매크로 꼴 열 이름)
def sheet_row(tree: dict) -> dict[str, str]:
    """MODS 정리 매크로가 만들던 열 이름 꼴: 경로 '/mods/…' 또는 '[n] /mods/…'(같은 경로의 n+1 번째). 트리 순서를 지킨다."""
    out: dict[str, str] = {}
    counter: dict[str, int] = {}

    def put(xp: str, value: str):
        value = (value or "").strip()
        if not value:
            return
        n = counter.get(xp, 0)
        out[xp if n == 0 else f"[{n}] {xp}"] = value
        counter[xp] = n + 1

    def walk(node, xp):
        if isinstance(node, list):
            for x in node:
                walk(x, xp)
            return
        if isinstance(node, dict):
            for k, v in node.items():
                if k.startswith("@"):
                    put(f"{xp}[{k}]", str(v))
            if "_" in node:
                put(xp, str(node["_"]))
            for k, v in node.items():
                if k == "_" or k.startswith("@"):
                    continue
                walk(v, f"{xp}/{k}")
            return
        put(xp, str(node))

    walk(tree, "/mods")
    return out


SHEET_ORDER = ["titleInfo", "name", "typeOfResource", "genre", "originInfo", "language", "physicalDescription", "targetAudience", "note", "subject", "classification", "identifier", "location", "accessCondition", "extension", "relatedItem", "recordInfo"]


def sheet_columns(rows: list[dict[str, str]]) -> list[str]:
    """점검 시트 열 순서: MODS 요소 순서(가이드 그림 36: 표제·권차·저자… 순, recordInfo 는 끝) → 경로 글자 → 같은 경로의 n번째."""
    cols = {k for r in rows for k in r}
    def key(c):
        m = re.match(r"\[(\d+)\] (.*)", c)
        n, path = (int(m.group(1)), m.group(2)) if m else (0, c)
        top = path.split("/")[2].split("[")[0] if path.startswith("/mods/") else ""
        rank = SHEET_ORDER.index(top) if top in SHEET_ORDER else len(SHEET_ORDER)
        return (rank, path, n)
    return sorted(cols, key=key)


def base_path(col: str) -> str:
    return re.sub(r"^\[\d+\] ", "", col)
