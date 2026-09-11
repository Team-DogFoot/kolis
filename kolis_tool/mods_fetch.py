"""⑤ MODS XML 받기 — MODStoXL.exe 대체.

MODStoXL.exe 안에서 확인된 주소(2024-07-02 빌드):
  http://kolis.nl.go.kr/main/login.do
  http://kolis.nl.go.kr/main/loginprocess.do                         (POST, 필드명 미확인)
  http://kolis.nl.go.kr/online/contents/popup/getHarContentsXml.do   (파라미터 미확인)
  http://kolis.nl.go.kr/ndl2011/contents/harcontents/popup/contentsXml.ndl?contentsBean.contentsId={CNTS}&contentsBean.harTypeCd=62

★ 미검증. 로그인 폼 필드명과 응답 형식은 현장 HAR 로 확인한 뒤 config(JSON) 에 적는다.
★ 도서관 요구: 테스트 목적 요청 금지. 검증은 --preview(요청만 출력, 전송 안 함)와 HAR 대조로만 하고,
   첫 실제 실행은 실제 작품 점검 단계에서 직원과 함께 한다. AI 는 이 모듈을 실행하지 않는다(사람이 명령).
   config 예: {"login_fields": {"userId": "...", "userPw": "..."}, "extra": {}}
   비밀번호는 config 파일이 아니라 환경변수 KOLIS_ID / KOLIS_PW 로 준다.
"""
from __future__ import annotations
import json, os, time
from pathlib import Path
import requests

BASE = "http://kolis.nl.go.kr"
LOGIN_PAGE = f"{BASE}/main/login.do"
LOGIN_POST = f"{BASE}/main/loginprocess.do"
XML_URL = f"{BASE}/ndl2011/contents/harcontents/popup/contentsXml.ndl"
XML_URL_ALT = f"{BASE}/online/contents/popup/getHarContentsXml.do"


class Kolis:
    def __init__(self, config: dict | None = None):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) kolis_tool/0.1"
        self.cfg = config or {}

    def login(self) -> None:
        uid, pw = os.environ.get("KOLIS_ID"), os.environ.get("KOLIS_PW")
        if not uid or not pw:
            raise SystemExit("환경변수 KOLIS_ID / KOLIS_PW 필요")
        self.s.get(LOGIN_PAGE, timeout=30)
        fields = dict(self.cfg.get("login_fields") or {"userId": "{id}", "userPw": "{pw}"})
        data = {k: v.replace("{id}", uid).replace("{pw}", pw) for k, v in fields.items()}
        r = self.s.post(LOGIN_POST, data=data, timeout=30)
        r.raise_for_status()
        ok_marker = self.cfg.get("login_ok_marker")
        if ok_marker and ok_marker not in r.text:
            raise SystemExit("로그인 실패로 보임(ok_marker 없음). HAR 로 필드명 확인 필요")

    def fetch_xml(self, cnts_id: str) -> bytes:
        params = {"contentsBean.contentsId": cnts_id, "contentsBean.harTypeCd": self.cfg.get("harTypeCd", "62")}
        r = self.s.get(XML_URL, params=params, timeout=60)
        r.raise_for_status()
        return r.content


def preview(ids: list[str], config_path: Path | None = None) -> None:
    """전송 없이 보낼 요청(주소·필드명)만 출력. HAR 과 대조용."""
    cfg = json.load(open(config_path, encoding="utf-8")) if config_path else {}
    fields = dict(cfg.get("login_fields") or {"userId": "{id}", "userPw": "{pw}"})
    print("GET ", LOGIN_PAGE)
    print("POST", LOGIN_POST, "fields:", {k: ("<KOLIS_ID>" if "{id}" in v else "<KOLIS_PW>" if "{pw}" in v else v) for k, v in fields.items()})
    for cid in ids[:3]:
        print("GET ", f"{XML_URL}?contentsBean.contentsId={cid}&contentsBean.harTypeCd={cfg.get('harTypeCd', '62')}")
    print(f"... 총 {len(ids)}건 (전송하지 않음)")


def fetch_all(ids: list[str], out_dir: Path, config_path: Path | None = None, delay: float = 0.3) -> list[Path]:
    cfg = json.load(open(config_path, encoding="utf-8")) if config_path else {}
    k = Kolis(cfg); k.login()
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, cid in enumerate(ids, 1):
        p = out_dir / f"{cid}.xml"
        if not p.exists():
            p.write_bytes(k.fetch_xml(cid)); time.sleep(delay)
        paths.append(p)
        if i % 50 == 0:
            print(f"  {i}/{len(ids)}")
    return paths
