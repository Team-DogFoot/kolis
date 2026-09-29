"""브라우저 없이 KOLIS 에 접속한다. 계정은 환경변수 KOLIS_ID / KOLIS_PW(없으면 저장소의 `.env`)에서만 읽는다.
계정·쿠키는 파일·로그·기록 어디에도 쓰지 않는다. KOLIS 는 `http://kolis.nl.go.kr`(평문)이라 이 PC 의 HTTPS 가로채기와 무관하다.

`kolis_request.Page` 와 같은 모양(send)이라 `kolis_request` 의 함수에 그대로 넣어 쓴다.
로그인(2026-09-30 로그인 화면에서 읽음): `POST /main/loginprocess.do` 항목 uid, pwd, jsp_ip(로그인 화면이 알려 주는 접속 IP).
**비밀번호를 5번 틀리면 계정이 잠긴다 → 로그인은 실행당 한 번만 시도하고, 실패하면 다시 시도하지 않는다.**
"""
from __future__ import annotations
import base64, os, re, threading, time
from pathlib import Path

from .kolis_request import BASE, NotSent, Stop, parse

AGENT = "Mozilla/5.0 (Windows NT 10.0; WOW64; Trident/7.0; rv:11.0) like Gecko"
LOGIN_MESSAGES = {"useNUser": "계정이 미사용 상태", "nonExistsId": "등록되지 않은 아이디", "passwordErrorExpire": "비밀번호 5회 실패로 로그인 차단",
                  "passwordError": "비밀번호가 틀림(5회 실패 시 차단)", "longTermUnUse": "장기 미사용 계정", "dateExpire": "계정 사용 기간 만료",
                  "notUseDate": "아직 이용할 수 없는 계정", "notAccessIp": "이 PC 의 IP 는 계정에 신청된 IP 가 아님", "parseError": "접속 시도 중 오류"}


def source() -> str:
    """계정을 어디서 읽게 되는지: 'login'(프로그램 창에서 로그인), 'env'(환경변수), 'file'(.env), ''(없음). 값은 돌려주지 않는다."""
    if os.environ.get("KOLIS_ID") and os.environ.get("KOLIS_PW"):
        return "login" if os.environ.get("KOLIS_ACCOUNT_FROM") == "login" else "env"
    env = Path(__file__).resolve().parent.parent / ".env"
    if env.exists():
        t = env.read_text(encoding="utf-8-sig")
        if re.search(r"(?m)^\s*KOLIS_ID\s*=\s*\S", t) and re.search(r"(?m)^\s*KOLIS_PW\s*=\s*\S", t):
            return "file"
    return ""


def credentials() -> tuple[str, str]:
    """프로그램 창에서 로그인한 계정(이 프로그램의 환경변수)이 먼저, 없으면 .env."""
    uid, pw = os.environ.get("KOLIS_ID"), os.environ.get("KOLIS_PW")
    if not (uid and pw):
        env = Path(__file__).resolve().parent.parent / ".env"
        if env.exists():
            for line in env.read_text(encoding="utf-8-sig").splitlines():
                m = re.match(r"\s*(KOLIS_ID|KOLIS_PW)\s*=\s*(.*)\s*$", line)
                if m:
                    v = m.group(2).strip().strip('"').strip("'")
                    uid, pw = (v, pw) if m.group(1) == "KOLIS_ID" else (uid, v)
    if not (uid and pw):
        raise NotSent("KOLIS 계정이 없습니다. 프로그램 창 위쪽에서 KOLIS 아이디와 비밀번호로 로그인하세요")
    return uid, pw


class Client:
    """로그인된 접속 하나. 여러 작품이 같이 쓴다(요청은 한 번에 하나씩 나가도록 잠근다)."""

    def __init__(self, log=None, journal=None):
        import requests
        self.log = log or (lambda m: None)
        self.journal = journal
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": AGENT, "Accept-Language": "ko-KR"})
        self.s.trust_env = False            # 프록시 설정을 따르지 않는다(내부망 주소)
        self.count = 0
        self.logged_in = False
        self.tried = False
        self._lock = threading.Lock()

    def _note(self, **row):
        if self.journal:
            self.journal.write("request", **row)

    def login(self) -> None:
        if self.logged_in:
            return
        if self.tried:
            raise NotSent("로그인에 실패한 접속입니다(계정 잠김을 막으려고 다시 시도하지 않음)")
        self.tried = True
        uid, pw = credentials()
        try:
            r = self.s.get(BASE + "/main/login.do", timeout=30)
        except Exception as e:  # noqa: BLE001
            raise NotSent(f"KOLIS 에 접속하지 못했습니다: {type(e).__name__}: {str(e)[:120]}") from e
        m = re.search(r'var\s+jsp_ip\s*=\s*"([^"]*)"', r.text)
        ip = m.group(1) if m else ""
        self._note(phase="login", step="화면", status=r.status_code, ip=ip)
        try:
            r = self.s.post(BASE + "/main/loginprocess.do", data={"uid": uid, "pwd": pw, "jsp_ip": ip}, timeout=30,
                            headers={"Referer": BASE + "/main/login.do"})
        except Exception as e:  # noqa: BLE001
            raise NotSent(f"로그인 요청을 보내지 못했습니다: {type(e).__name__}: {str(e)[:120]}") from e
        msg = re.search(r'var\s+msg\s*=\s*"([^"]*)"', r.text)
        code = msg.group(1) if msg else ""
        at_login = 'name="pwd"' in r.text
        self._note(phase="login", step="결과", status=r.status_code, url=r.url, message=code, at_login=at_login, chars=len(r.text),
                   moves=[h.status_code for h in r.history])
        if code or at_login:
            raise NotSent("로그인하지 못했습니다: " + (LOGIN_MESSAGES.get(code, code) or "로그인 화면이 다시 나옴") + " → 계정을 확인하세요(다시 시도하지 않음)")
        self.logged_in = True
        self.log(f"  KOLIS 로그인됨(브라우저 없음, 접속 IP {ip})")

    def send(self, method: str, path: str, body: str | None, ctype: str | None, wait: float = 60.0, shown: str | None = None) -> dict:
        with self._lock:
            self.login()
            self.count += 1
            n, t0 = self.count, time.time()
            data = base64.b64decode(body[7:]) if body and body.startswith("base64:") else (body.encode("utf-8") if body is not None else None)
            self.log(f"  요청 {n}: {method} {path} (본문 {len(data or b''):,}바이트)")
            self._note(n=n, phase="send", method=method, path=path, content_type=ctype, body=body if shown is None else shown)
            h = {"Accept": "application/json, text/javascript, */*; q=0.01", "X-Requested-With": "XMLHttpRequest", "Referer": BASE + "/main/gohome.do"}
            if ctype:
                h["Content-Type"] = ctype
            try:
                r = self.s.request(method, BASE + path, data=data, headers=h, timeout=(30, wait), allow_redirects=False)
            except Exception as e:  # noqa: BLE001
                import requests
                sent = not isinstance(e, (requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError)) or isinstance(e, requests.exceptions.ReadTimeout)
                self._note(n=n, phase="fail", sent=sent, error=f"{type(e).__name__}: {e}")
                if not sent:
                    raise NotSent(f"KOLIS 에 연결하지 못했습니다({path}): {type(e).__name__}") from e
                raise Stop(f"요청을 보낸 뒤 응답을 받지 못했습니다({path}): {type(e).__name__}. 처리됐는지 KOLIS 에서 확인하세요") from e
            r.encoding = r.encoding if r.encoding and r.encoding.lower() != "iso-8859-1" else "utf-8"
            text = r.text
            sec = round(time.time() - t0, 2)
            self._note(n=n, phase="response", status=r.status_code, sent=True, seconds=sec, chars=len(text), location=r.headers.get("Location", ""),
                       response=text[:20000])
            self.log(f"  응답 {n}: 상태 {r.status_code}, {len(text):,}자, {sec}초")
            if r.status_code in (301, 302, 303, 307) or 'name="pwd"' in text[:20000]:
                self.logged_in = False
                raise Stop(f"로그인이 풀렸습니다({path} → {r.headers.get('Location', '로그인 화면')}). 다른 곳에서 같은 계정으로 로그인했는지 확인하세요")
            return parse(f"{r.status_code}\n\n{text}", path)

    def upload(self, path: str, fields: dict, name: str, data: bytes, mime: str, wait: float = 300.0, note: dict | None = None) -> str:
        """파일 하나를 보낸다(업로더가 보내는 것과 같은 형식). 응답 글자를 그대로 돌려준다."""
        with self._lock:
            self.login()
            self.count += 1
            n, t0 = self.count, time.time()
            self._note(n=n, phase="send", method="POST", path=path, body=note or {}, file={"name": name, "bytes": len(data)})
            try:
                r = self.s.post(BASE + path, data=fields, files={"fileToUpload": (name, data, mime)}, timeout=(30, wait),
                                headers={"Referer": BASE + "/online/cmmn/contentsTextRegPop.do?har_type_cd=62&directory="})
            except Exception as e:  # noqa: BLE001
                self._note(n=n, phase="fail", error=f"{type(e).__name__}: {e}")
                raise Stop(f"파일을 보내지 못했습니다({name}): {type(e).__name__}: {str(e)[:120]}") from e
            self._note(n=n, phase="response", status=r.status_code, seconds=round(time.time() - t0, 2), chars=len(r.text), response=r.text[:2000])
            if r.status_code != 200:
                raise Stop(f"파일 전송 응답 상태 {r.status_code}({name})")
            return r.text

    def get(self, path: str, wait: float = 60.0):
        """화면(HTML)이나 파일을 받는다. 자료를 바꾸지 않는 요청에만 쓴다."""
        with self._lock:
            self.login()
            self.count += 1
            r = self.s.get(BASE + path, timeout=(30, wait), headers={"Referer": BASE + "/main/gohome.do"})
            self._note(n=self.count, phase="get", path=path, status=r.status_code, chars=len(r.content))
            return r

    def close(self) -> None:
        """로그아웃하지 않고 접속만 닫는다(로그아웃 요청이 같은 계정의 다른 접속을 끊는지 확인되지 않았다)."""
        try:
            self.s.close()
        except Exception:  # noqa: BLE001
            pass
