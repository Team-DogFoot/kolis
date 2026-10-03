"""3-2 반입값 대조(가이드 5.3 첫 문장: "콘텐츠를 한 건씩 열어 반입용 기초메타데이터 파일대로 MODS 항목에 잘 들어갔는지 확인") — 요청만, 읽기만.
원부의 종 → 권 → 콘텐츠 번호를 요청으로 모으고, 콘텐츠마다 MODS XML 을 받아 사람이 읽는 칸으로 펼친다.
- 반입용 엑셀(이 프로그램이 만든 것)이 있으면 행마다 칸 대조(같음/다름).
- 없으면(다른 담당자가 반입한 원부) 콘텐츠끼리 **공통이어야 할 칸**(표제·저자·발행처·발행지·이용대상·주기·접근제한)이 서로 다른 곳을 짚는다.
KOLIS 가 저장 때 스스로 바꾸는 값(internetMediaType JPG↔image/jpg, digitalOrigin BornDigital↔born digital 등)은 같은 것으로 본다."""
from __future__ import annotations
import json, re
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlencode

from . import kolis_http, dup_request
from . import mods_build as mb

NS = {"mods": "http://www.loc.gov/mods/v3"}
FORM = "application/x-www-form-urlencoded; charset=UTF-8"
# 사람이 읽는 칸 이름 → MODS 경로(첫 번째 값). 반복 요소는 따로 모은다.
FIELDS = [
    ("본표제", "titleInfo/title"), ("표제관련정보", "titleInfo/subTitle"), ("권차", "titleInfo/partNumber"), ("권차표제", "titleInfo/partName"),
    ("발행지", "originInfo/place/placeTerm[@type='text']"), ("발행국 부호", "originInfo/place/placeTerm[@type='code']"),
    ("발행일", "originInfo/dateIssued"), ("판사항", "originInfo/edition"), ("발행연속성", "originInfo/issuance"),
    ("이용대상자", "targetAudience"), ("접근제한", "accessCondition/licenseType"), ("ISBN", "identifier[@type='isbn']"), ("UCI", "identifier[@type='uci']"),
    ("수량", "physicalDescription/extent"), ("자료형태", "physicalDescription/form"), ("분류기호", "classification"), ("소장위치", "location/physicalLocation"),
]
COMMON = ("본표제", "표제관련정보", "발행지", "발행국 부호", "발행연속성", "이용대상자", "접근제한", "저자", "발행처", "주기", "주제명", "자료형태", "분류기호", "소장위치")   # 회차끼리 같아야 하는 칸
AUTO = {"JPG": "image/jpg", "image/jpg": "image/jpg", "BornDigital": "born digital", "born digital": "born digital", "개인명": "personal", "단체명": "corporate"}   # 저장 뒤 KOLIS 가 바꾸는 표기


def _norm(v: str) -> str:
    v = (v or "").strip()
    return AUTO.get(v, v)


def flatten(xml_text: str) -> dict:
    """MODS XML → 사람이 읽는 칸. 반복 요소: 저자 [{이름, 유형, 역할, 전거}], 발행처 [..], 주기 [{유형, 글}], 주제명 [{글, 전거}], 원문주소 [..]."""
    out: dict = {}
    if not xml_text:
        return out
    root = ET.fromstring(xml_text)
    def txt(path):
        e = root.find("mods:" + path.replace("/", "/mods:"), NS)
        return (e.text or "").strip() if e is not None and e.text else ""
    for label, path in FIELDS:
        # 속성 조건은 ElementTree 가 지원(예 placeTerm[@type='text'])
        out[label] = txt(path)
    out["저자"] = [{"이름": (n.findtext("mods:namePart", "", NS) or "").strip(), "유형": n.get("type", ""), "역할": (n.findtext("mods:role/mods:roleTerm", "", NS) or "").strip(),
                  "전거": n.get("ID", ""), "전거출처": n.get("authority", ""), "주저자": n.get("usage", "") == "primary",
                  "다른이름": [(a.findtext("mods:namePart", "", NS) or "").strip() for a in n.findall("mods:alternativeName", NS)],
                  "디스플레이": (n.findtext("mods:displayForm", "", NS) or "").strip()} for n in root.findall("mods:name", NS)]
    out["발행처"] = [(e.text or "").strip() for e in root.findall("mods:originInfo/mods:publisher", NS)]
    out["주기"] = [{"유형": e.get("type", ""), "글": (e.text or "").strip()} for e in root.findall("mods:note", NS)]
    out["주제명"] = [{"글": "".join((c.text or "") for c in s), "종류": (s[0].tag.split("}")[1] if len(s) else ""), "전거": s.get("ID", ""), "전거출처": s.get("authority", "")} for s in root.findall("mods:subject", NS)]
    out["원문주소"] = [(e.text or "").strip() for e in root.findall("mods:location/mods:url", NS)]
    out["출처정보 수"] = len(root.findall("mods:originInfo", NS))
    return out


def contents_of(c: kolis_http.Client, wonbu: str, log=print) -> list[dict]:
    """원부 → [{species_key, vol, title, contents_id}] (요청만)."""
    dc = dup_request.digitalcont(c, wonbu)
    out = []
    for sp in dc.get("list") or []:
        sk = sp.get("SPECIES_KEY")
        vols = dup_request.volumes(c, sk)
        for v in vols:
            r = c.send("POST", "/online/contents/listVolContents.do", urlencode({"species_key": str(sk), "vol_key": str(v.get("VOL_KEY")), "har_stat_cd": "30", "issuance": "MO"}), FORM)
            for x in r.get("list") or []:
                out.append({"species_key": sk, "vol": x.get("VOL") or v.get("VOL"), "title": x.get("CONTENTS_NM") or sp.get("TITLE"), "contents_id": x.get("CONTENTS_ID"), "isbn": x.get("IDEN_ID")})
    out.sort(key=lambda x: (len(str(x.get("vol") or "")), str(x.get("vol") or "")))
    log(f"원부 {wonbu}: 종 {len(dc.get('list') or [])} · 콘텐츠 {len(out)}")
    return out


def fetch_xml(c: kolis_http.Client, cnts: str) -> str:
    r = c.send("POST", "/online/contents/popup/getHarContentsXml.do", urlencode({"contentsId": cnts}), FORM)
    return r.get("mods_xml") or ""


def import_rows(wonbu: str) -> list[dict] | None:
    """이 프로그램이 만든 반입용 엑셀이 있으면(탭 상태의 작업 폴더 ↔ 원부번호 짝) 행을 돌려준다. 없으면 None."""
    tabs = Path("work/tabs.json")
    if not tabs.exists():
        return None
    try:
        d = json.loads(tabs.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    t = next((t for t in d.get("tabs") or [] if str(t.get("wonbu") or "") == str(wonbu) and t.get("folder")), None)
    if not t:
        return None
    from . import prepare
    work = prepare.load(Path(t["folder"]), Path("work"))
    xlsx = work and work.get("output_xlsx")
    if not xlsx or not Path(xlsx).exists():
        return None
    import openpyxl
    ws = openpyxl.load_workbook(xlsx, read_only=True)["Contents"]
    rows = list(ws.iter_rows(values_only=True))
    h = [(x or "").strip() if isinstance(x, str) else "" for x in rows[0]]
    keys, seen = [], {}
    for x in h:
        keys.append((x, seen.get(x, 0))); seen[x] = seen.get(x, 0) + 1
    out = []
    for r in rows[1:]:
        if not any(c not in (None, "") for c in r):
            continue
        m = dict(zip(keys, r)); g = lambda k, n=0: ("" if m.get((k, n)) is None else str(m.get((k, n)))).strip()
        out.append({"본표제": g("/mods/titleInfo/title"), "권차": g("/mods/titleInfo/partNumber"), "권차표제": g("/mods/titleInfo/partName"), "표제관련정보": g("/mods/titleInfo/subTitle"),
                    "발행지": g("/mods/originInfo/place/placeTerm"), "발행국 부호": g("/mods/originInfo/place/placeTerm", 1), "발행일": g("/mods/originInfo/dateIssued"), "판사항": g("/mods/originInfo/edition"),
                    "이용대상자": g("/mods/targetAudience"), "접근제한": g("/mods/accessCondition/licenseType"), "ISBN": g("/mods/identifier"),
                    "저자": [{"이름": g("/mods/name/namePart", i), "유형": g("/mods/name[@type]", i), "역할": g("/mods/name/role/roleTerm", i)} for i in range(6) if g("/mods/name/namePart", i)],
                    "발행처": [g("/mods/originInfo/publisher", i) for i in range(4) if g("/mods/originInfo/publisher", i)],
                    "주기": [{"유형": g("/mods/note[@type]", i), "글": g("/mods/note", i)} for i in range(5) if g("/mods/note", i)],
                    "원문주소": [g("/mods/location/url", i) for i in range(3) if g("/mods/location/url", i)]})
    return out


def compare(wonbu: str, log=print) -> dict:
    """원부 전체: 콘텐츠마다 MODS 를 읽고(요청), 반입용 엑셀이 있으면 칸 대조, 없으면 회차끼리 공통 칸 불일치를 짚는다."""
    c = kolis_http.Client(log)
    try:
        c.login()
        items = contents_of(c, wonbu, log)
        for it in items:
            it["mods"] = flatten(fetch_xml(c, it["contents_id"]))
    finally:
        c.close()
    rows = import_rows(wonbu)
    diffs, mode = [], "import" if rows else "consistency"
    if rows:
        # 반입 행과 콘텐츠를 ISBN → 권차 순으로 짝짓는다
        by_isbn = {r["ISBN"]: r for r in rows if r.get("ISBN")}; by_part = {r["권차"]: r for r in rows if r.get("권차")}
        for it in items:
            m = it["mods"]; r = by_isbn.get(re.sub(r"\D", "", m.get("ISBN") or "")) or by_part.get(m.get("권차") or "")
            it["import_matched"] = bool(r)
            if not r:
                diffs.append({"contents_id": it["contents_id"], "vol": it["vol"], "칸": "(짝)", "반입값": "", "KOLIS": m.get("권차") or "", "note": "반입 행을 찾지 못함"}); continue
            for k in ("본표제", "표제관련정보", "권차", "권차표제", "발행지", "발행국 부호", "발행일", "판사항", "이용대상자", "접근제한", "ISBN"):
                a, b = _norm(r.get(k, "")), _norm(m.get(k, ""))
                if k == "ISBN":
                    a, b = re.sub(r"\D", "", a), re.sub(r"\D", "", b)
                if a != b:
                    diffs.append({"contents_id": it["contents_id"], "vol": it["vol"], "칸": k, "반입값": a, "KOLIS": b})
            ra = [(x["이름"], x["역할"]) for x in r["저자"]]; ma = [(x["이름"], x["역할"]) for x in m["저자"]]      # 전거 번호·유형 표기는 구축에서 더해지므로 이름·역할만 대조
            if ra != ma:
                diffs.append({"contents_id": it["contents_id"], "vol": it["vol"], "칸": "저자", "반입값": " / ".join(f"{n}({ro})" for n, ro in ra), "KOLIS": " / ".join(f"{n}({ro})" for n, ro in ma)})
            if r["발행처"] != m["발행처"]:
                diffs.append({"contents_id": it["contents_id"], "vol": it["vol"], "칸": "발행처", "반입값": " · ".join(r["발행처"]), "KOLIS": " · ".join(m["발행처"])})
            rn = [(x["유형"], x["글"]) for x in r["주기"]]; mn = [(x["유형"], x["글"]) for x in m["주기"]]
            if rn != mn:
                diffs.append({"contents_id": it["contents_id"], "vol": it["vol"], "칸": "주기", "반입값": " / ".join(f"[{t}] {g}" for t, g in rn), "KOLIS": " / ".join(f"[{t}] {g}" for t, g in mn)})
            if [u for u in r["원문주소"] if u] != [u for u in m["원문주소"] if u]:
                diffs.append({"contents_id": it["contents_id"], "vol": it["vol"], "칸": "원문주소", "반입값": " / ".join(r["원문주소"]), "KOLIS": " / ".join(m["원문주소"])})
    else:
        def sig(m, k):
            v = m.get(k)
            if k == "저자":
                return tuple((x["이름"], _norm(x["유형"]), x["역할"], x["전거"]) for x in v)
            if k == "주기":
                return tuple((x["유형"], x["글"]) for x in v)
            if k == "주제명":
                return tuple((x["글"], x["전거"]) for x in v)
            return tuple(v) if isinstance(v, list) else _norm(v or "")
        for k in COMMON:
            vals = {}
            for it in items:
                vals.setdefault(sig(it["mods"], k), []).append(it)
            if len(vals) > 1:
                major = max(vals.items(), key=lambda kv: len(kv[1]))
                for s, its in vals.items():
                    if s is major[0]:
                        continue
                    for it in its:
                        diffs.append({"contents_id": it["contents_id"], "vol": it["vol"], "칸": k, "반입값": _show(major[0]), "KOLIS": _show(s), "note": f"다른 회차 {len(major[1])}건과 다름"})
    return {"wonbu": wonbu, "mode": mode, "count": len(items), "import_rows": len(rows or []), "items": [{k: v for k, v in it.items()} for it in items], "diffs": diffs}


def _show(s) -> str:
    if isinstance(s, tuple):
        return " / ".join(_show(x) if isinstance(x, tuple) else str(x) for x in s)
    return str(s)
