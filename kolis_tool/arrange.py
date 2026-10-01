"""납품 폴더 정리 — 무엇을 어디로 옮길지는 에이전트가 정하고(`import.json` 의 `arrange`), 이 파일은 그 계획을 그대로 실행한다(유저 확정 2026-10-01).

계획의 모양:
  "arrange": {"moves":     [{"from": "지금 경로", "to": "정리 뒤 경로", "kind": "", "why": ""}],   # 회차 폴더, 썸네일 폴더 등
              "set_aside": [{"from": "지금 경로", "to": "_kolis_제외/…", "why": ""}],              # 원고가 아닌 파일. 지우지 않고 빼 둔다
              "notes": []}
경로는 모두 납품 폴더 기준 상대 경로. `from` 은 정리 전, `to` 는 정리 뒤의 위치다. 실행 순서는 set_aside → moves.
이 파일은 판단하지 않는다: 계획의 형식을 검사하고, 옮기고, 되돌리기 기록을 남긴다. 지우는 일은 없다.

항목의 상태는 폴더를 보고 정한다(표시를 따로 두지 않는다): `from` 이 있고 `to` 가 없으면 아직 안 옮긴 것, 반대면 이미 옮긴 것.
검사와 반입용 엑셀 쓰기는 옮기기 전에도 돌아야 하므로(View), 계획을 적용했다고 가정한 폴더 모습을 계산해 준다.
"""
from __future__ import annotations
import json, os
from pathlib import Path
from .common import list_images, manifest_path

KIND = "arrange"


def _items(data: dict) -> list[dict]:
    a = data.get("arrange") or {}
    return [dict(x, _group="set_aside") for x in a.get("set_aside") or []] + [dict(x, _group="moves") for x in a.get("moves") or []]


def _key(p: Path) -> str:
    return os.path.normcase(os.path.normpath(str(p)))


def _under(p: Path, parent: Path) -> bool:
    a, b = _key(p), _key(parent)
    return a == b or a.startswith(b + os.sep)


def check(folder: Path, data: dict) -> list[str]:
    """계획의 형식. 걸린 항목 목록(비어 있으면 통과)."""
    folder, out, tos, froms = Path(folder), [], {}, {}
    moves_from = []
    for it in _items(data):
        g, f, t = it["_group"], str(it.get("from") or "").strip(), str(it.get("to") or "").strip()
        tag = f"arrange.{g} '{f}' → '{t}'"
        if not f or not t:
            out.append(f"{tag}: from 과 to 를 둘 다 적으세요"); continue
        bad = [x for x in (f, t) if Path(x).is_absolute() or ".." in Path(x).parts or x.startswith(("/", "\\"))]
        if bad:
            out.append(f"{tag}: 납품 폴더 기준 상대 경로만 씁니다('..'·절대 경로 금지)"); continue
        src, dst = folder / f, folder / t
        if _key(src) == _key(dst):
            out.append(f"{tag}: from 과 to 가 같습니다(옮길 것이 없으면 적지 않습니다)"); continue
        if _key(dst) in tos:
            out.append(f"{tag}: 같은 to 가 두 번 나옵니다")
        if _key(src) in froms:
            out.append(f"{tag}: 같은 from 이 두 번 나옵니다")
        tos[_key(dst)] = froms[_key(src)] = True
        if _under(dst, src):
            out.append(f"{tag}: to 가 from 의 안쪽입니다")
        if src.exists() and dst.exists():
            out.append(f"{tag}: to 가 이미 있습니다(덮어쓰지 않습니다). 다른 이름을 쓰세요")
        elif not src.exists() and not dst.exists():
            out.append(f"{tag}: from 이 납품 폴더에 없습니다")
        if g == "moves":
            if any(_under(src, m) or _under(m, src) for m in moves_from):
                out.append(f"{tag}: 다른 moves 항목과 겹칩니다(폴더와 그 안의 것을 따로 옮기지 않습니다)")
            moves_from.append(src)
        else:
            for k in ("manuscripts_root", "thumbs_dir"):
                if data.get(k) and _under(dst, folder / str(data[k])):
                    out.append(f"{tag}: 빼 두는 곳이 {k} 안입니다. '_kolis_제외/…' 처럼 바깥에 두세요")
    return out


class View:
    """계획을 적용했다고 가정한 납품 폴더. 경로는 정리 뒤 기준 상대 경로로 묻고, 답은 지금 실제 경로로 준다."""

    def __init__(self, folder: Path, data: dict):
        self.folder = Path(folder)
        self.pending = [(self.folder / str(it["from"]), self.folder / str(it["to"])) for it in _items(data)
                        if it.get("from") and it.get("to") and (self.folder / str(it["from"])).exists() and not (self.folder / str(it["to"])).exists()]
        self._gone = {_key(s) for s, _ in self.pending}

    def actual(self, rel: str) -> Path:
        v = self.folder / rel
        for src, dst in self.pending:
            if _under(v, dst):
                return src / os.path.relpath(v, dst) if _key(v) != _key(dst) else src
        return v

    def is_dir(self, rel: str) -> bool:
        v, base = self.folder / rel, self.actual(rel)
        real = base.is_dir() and not (_key(base) == _key(v) and _key(v) in self._gone)
        return real or any(_key(dst.parent) == _key(v) for _, dst in self.pending)

    def children(self, rel: str) -> list[tuple[str, Path]]:
        """(정리 뒤 이름, 지금 실제 경로)"""
        v, base, out = self.folder / rel, self.actual(rel), []
        if base.is_dir() and not (_key(base) == _key(v) and _key(base) in self._gone):
            out += [(c.name, c) for c in base.iterdir() if _key(c) not in self._gone]
        out += [(dst.name, src) for src, dst in self.pending if _key(dst.parent) == _key(v)]
        return out

    def images(self, rel: str) -> list[Path]:
        base = self.actual(rel)
        return [p for p in list_images(base) if _key(p) not in self._gone] if base.is_dir() else []

    def others(self, rel: str) -> list[str]:
        """그 폴더 바로 아래의, 이미지가 아닌 것(빼 두기로 한 것은 제외)."""
        imgs = {_key(p) for p in self.images(rel)}
        return [n for n, p in self.children(rel) if _key(p) not in imgs]


def apply(folder: Path, data: dict, log=None) -> dict:
    """아직 안 옮긴 항목을 옮긴다. 되돌리기 기록은 납품 폴더 밖(work/manifests)."""
    folder, log = Path(folder), log or (lambda m: None)
    fails = check(folder, data)
    if fails:
        raise SystemExit("정리 계획이 검사를 통과하지 못해 옮기지 않았습니다: " + "; ".join(fails[:5]))
    mf = manifest_path(folder, KIND)
    done = json.loads(mf.read_text(encoding="utf-8")) if mf.exists() else []
    n = {"moves": 0, "set_aside": 0}
    for it in _items(data):
        src, dst = folder / str(it["from"]), folder / str(it["to"])
        if not src.exists():
            continue                      # 이미 옮긴 것
        made = []
        for d in reversed([p for p in dst.parents if _under(p, folder) and not p.exists()]):
            d.mkdir(); made.append(str(d.relative_to(folder)))
        src.rename(dst)
        done.append({"from": str(it["from"]), "to": str(it["to"]), "made": made})
        mf.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
        n[it["_group"]] += 1
    if n["moves"] or n["set_aside"]:
        log(f"납품 폴더 정리: 옮김 {n['moves']}건, 빼 둠 {n['set_aside']}건(되돌리기 가능)")
    for note in (data.get("arrange") or {}).get("notes") or []:
        log(f"  정리 메모: {note}")
    return n


def undo(folder: Path) -> int:
    folder = Path(folder)
    mf = manifest_path(folder, KIND)
    if not mf.exists():
        return 0
    n, made = 0, set()
    for rec in reversed(json.loads(mf.read_text(encoding="utf-8"))):
        src, dst = folder / rec["from"], folder / rec["to"]
        if dst.exists() and not src.exists():
            src.parent.mkdir(parents=True, exist_ok=True)
            dst.rename(src); n += 1
        made.update(rec.get("made") or [])
    for d in sorted(made, key=lambda s: -len(Path(s).parts)):      # 정리하면서 만든 폴더는 비었으면 지운다(안쪽부터)
        p = folder / d
        if p.is_dir() and not any(p.iterdir()):
            p.rmdir()
    mf.unlink()
    return n
