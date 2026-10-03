"""저자 전거 후보 조회(요청만, 브라우저 없음). 에이전트용 명령 `kolis_tool authority "<이름>"` 이 이 모듈을 부른다.
전거 찾기 팝업이 보내는 조회(listACMat.do)와 같은 요청을 프로그램의 로그인 세션으로 보낸다. 에이전트는 KOLIS 화면·계정에 직접 닿지 않는다.
결과는 JSON 으로 출력하고 work/authority/<이름>.json 에도 둔다(같은 이름은 하루 안에 다시 묻지 않는다)."""
from __future__ import annotations
import datetime, json, re
from pathlib import Path
from urllib.parse import urlencode

from . import kolis_http

DROP = ("MARC", "SIGNPOSTS", "_chk", "REC_KEY", "TAG373")
KEEP = ("AC_CONTROL_NO", "CHOICE_SIGNPOST", "AC_TYPE_NAME", "JOB", "BIRTH_YEAR", "BIRTH_PLACE", "SUMMARY", "ORGANIZATION", "ORGANIZATION_TYPE", "BRANCH", "EDUCATION_LEVEL", "CHI_NAME", "SPECIESA_CNT", "SPECIESB_CNT", "AC_REGION_NAME", "ESTABLISHMENT_DATE")
REPO = Path(__file__).resolve().parent.parent
CACHE = REPO / "work" / "authority"       # 절대 경로: 에이전트 명령은 작업 폴더(저장소 밖)에서 돌고, 검사는 저장소에서 돈다(2026-10-04 리뷰 5-2)


def lookup(name: str, log=print, client: kolis_http.Client | None = None, use_cache: bool = True) -> dict:
    name = (name or "").strip()
    if not name:
        return {"name": name, "candidates": [], "error": "이름이 비어 있습니다"}
    CACHE.mkdir(parents=True, exist_ok=True)
    cp = CACHE / (re.sub(r"[\\/:*?\"<>|]+", "_", name) + ".json")
    if use_cache and cp.exists():
        try:
            d = json.loads(cp.read_text(encoding="utf-8"))
            if d.get("date") == f"{datetime.date.today()}":
                return d
        except Exception:  # noqa: BLE001
            pass
    own = client is None
    c = client or kolis_http.Client(log)
    try:
        c.login()
        body = {"flag": "4", "type": "0", "targetid": "", "subdata": "", "contents_id": "", "species_key": "", "keyword": name, "exact_yn": "Y", "ac_class": "", "choice": "on"}
        r = c.send("POST", "/bocata/kormarcmatmng/kormarcmatmng/listACMat.do", urlencode(body), "application/x-www-form-urlencoded; charset=UTF-8")
        rows = [{k: v for k, v in row.items() if k in KEEP and v not in (None, "")} for row in (r.get("list") or [])]
        d = {"name": name, "date": f"{datetime.date.today()}", "count": len(rows), "candidates": rows, "cache": str(cp),
             "note": "KOLIS 전거 후보(이름 완전일치). 연결은 생몰년·직업 등이 완전히 일치하는 강한 확신일 때만(가이드 2.1). candidates 가 비어 있고 error 가 없으면 '후보 없음', error 가 있으면 '조회 실패'(연결 판단을 하지 않고 confirm 에 적는다)."}
        cp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        return d
    finally:
        if own:
            c.close()


def main(name: str) -> int:
    try:
        d = lookup(name, log=lambda m: None)
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"name": name, "candidates": [], "error": f"{type(e).__name__}: {e}", "note": "조회 실패입니다(후보 없음이 아님). 연결 판단을 하지 말고 저자명은 원문 표기 그대로, confirm 에 '전거 조회를 하지 못했습니다(이유). 도서관에서 다시 조회해 주십시오' 를 적으세요"}, ensure_ascii=False))
        return 1
    print(json.dumps(d, ensure_ascii=False, indent=1))
    return 0
