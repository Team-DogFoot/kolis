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


# ---------- 동시 전송 ----------
# KOLIS 는 연결 하나당 약 1.2~2MB/s 까지만 받는다. 연결을 여러 개 열면 연결 수만큼 빨라진다(2026-10-01 측정: 8개 11MB/s, 16개 14.8MB/s, 실패 0).
# 로그인 하나의 쿠키를 여러 연결이 같이 써도 된다. 파일 전송은 임시 위치에 파일을 쓰는 독립된 요청이라 순서와 무관하다(접수 988 로 원문등록까지 확인).
# 프로그램 전체가 연결을 LIMIT 개까지만 연다. 가장 먼저 건 작품이 PRIORITY 개를 쓰고, 나머지 연결은 다른 작품들이 돌아가며 쓴다. 비는 연결은 누구든 쓴다.
LIMIT = max(1, int(os.environ.get("KOLIS_UPLOAD_CONNECTIONS") or 8))
PRIORITY = max(1, min(LIMIT, int(os.environ.get("KOLIS_UPLOAD_PRIORITY") or 4)))


class _Job:
    def __init__(self, client, n, path, fields, name, data, mime, expect, wait):
        self.client, self.n, self.path, self.fields, self.name, self.data, self.mime, self.expect, self.wait = client, n, path, fields, name, data, mime, expect, wait
        self.size, self.t0 = len(data), time.time()
        self.done = threading.Event()
        self.error = ""


class _Uploads:
    """프로그램 전체가 같이 쓰는 전송 일꾼들."""

    def __init__(self):
        self.cv = threading.Condition()
        self.queues: dict = {}          # 접속 → 아직 안 보낸 일(건 순서대로). dict 의 순서 = 작품을 건 순서
        self.running: dict = {}         # 접속 → 지금 보내는 중인 수
        self.turn = 0
        self.threads: list = []

    def submit(self, job: _Job) -> None:
        with self.cv:
            self.queues.setdefault(job.client, []).append(job)
            while len(self.threads) < LIMIT:
                th = threading.Thread(target=self._work, daemon=True, name=f"kolis-upload-{len(self.threads) + 1}")
                self.threads.append(th); th.start()
            self.cv.notify_all()

    def drop(self, client) -> int:
        """그 접속의 아직 안 보낸 일을 버린다(중단·오류). 보내는 중인 것은 끝까지 간다."""
        with self.cv:
            left = self.queues.get(client) or []
            self.queues[client] = []
            if not self.running.get(client):
                self.queues.pop(client, None)
            for j in left:
                j.error = "보내지 않음(중단)"; j.done.set()
            return len(left)

    def _pick(self):
        waiting = [c for c, q in self.queues.items() if q]
        if not waiting:
            return None
        first = next(iter(self.queues))                 # 가장 먼저 건 작품(전송이 남았거나 보내는 중인 것만 queues 에 남는다)
        others = [c for c in waiting if c is not first]
        if first in waiting and (self.running.get(first, 0) < PRIORITY or not others):
            c = first
        elif others:
            self.turn += 1
            c = others[self.turn % len(others)]
        else:
            return None
        return self.queues[c].pop(0)

    def _work(self):
        import requests
        from .kolis_request import uploader_answer
        sessions: dict = {}
        while True:
            with self.cv:
                job = self._pick()
                while job is None:
                    self.cv.wait(timeout=30)
                    for c in [c for c in sessions if c.closed]:
                        sessions.pop(c).close()
                    job = self._pick()
                self.running[job.client] = self.running.get(job.client, 0) + 1
            c = job.client
            try:
                s = sessions.get(c)
                if s is None:
                    s = sessions[c] = requests.Session()
                    s.trust_env = False
                    s.headers.update(c.s.headers); s.cookies.update(c.s.cookies)
                t0 = time.time()
                r = s.post(BASE + job.path, data=job.fields, files={"fileToUpload": (job.name, job.data, job.mime)}, timeout=(30, job.wait),
                           headers={"Referer": BASE + "/online/cmmn/contentsTextRegPop.do?har_type_cd=62&directory="})
                c._note(n=job.n, phase="response", status=r.status_code, seconds=round(time.time() - t0, 2), chars=len(r.text), response=r.text[:2000])
                if r.status_code != 200:
                    job.error = f"응답 상태 {r.status_code}"
                else:
                    got = uploader_answer(r.text)
                    if got != job.expect:
                        job.error = f"응답이 예상과 다름: {got[:160]} (예상 {job.expect[:160]})"
            except Exception as e:  # noqa: BLE001
                c._note(n=job.n, phase="fail", error=f"{type(e).__name__}: {e}")
                job.error = f"{type(e).__name__}: {str(e)[:120]}"
            finally:
                job.data = b""
                with self.cv:
                    self.running[c] -= 1
                    if not self.running[c]:
                        self.running.pop(c)
                        if not self.queues.get(c):
                            self.queues.pop(c, None)
                    self.cv.notify_all()
                job.done.set()


UPLOADS = _Uploads()


class Client:
    """로그인된 접속 하나(실행 한 번에 하나). 일반 요청은 한 번에 하나씩 나가고, 파일 전송만 UPLOADS 의 일꾼들이 같은 쿠키로 동시에 보낸다."""

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
        self.jobs: list = []                # 뒤에서 보내고 있는 파일들(drain 이 기다린다)
        self.closed = False

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

    def drain(self, cancel=None, progress=None) -> dict:
        """뒤에서 보내고 있는 파일이 전부 끝나기를 기다리고, 실제 응답이 예상과 같았는지 본다. 다르면 멈춘다.
        자료를 바꾸는 다음 요청이 나가기 전에 반드시 거친다(send·download·get 이 부른다)."""
        jobs, self.jobs = self.jobs, []
        if not jobs:
            return {"files": 0}
        total, size, seen = len(jobs), sum(j.size for j in jobs), 0
        while True:
            done = sum(1 for j in jobs if j.done.is_set())
            bad = [j for j in jobs if j.done.is_set() and j.error]
            if bad or (cancel and cancel()):
                left = UPLOADS.drop(self)
                for j in jobs:
                    j.done.wait()
                if bad:
                    raise Stop(f"파일 전송 실패({bad[0].name}): {bad[0].error} — 보내지 않고 버린 파일 {left}개")
                raise Stop(f"사용자가 중단함(파일 {done}/{total}개 전송)")
            if progress and done != seen and (done - seen >= 25 or done == total):
                progress(done, total); seen = done
            if done == total:
                break
            time.sleep(0.2)
        sec = max(time.time() - jobs[0].t0, 0.01)
        return {"files": total, "bytes": size, "seconds": round(sec, 1), "rate": round(size / 1048576 / sec, 2)}

    def send(self, method: str, path: str, body: str | None, ctype: str | None, wait: float = 60.0, shown: str | None = None) -> dict:
        self.drain()
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
        """파일 하나를 보낸다(업로더가 보내는 것과 같은 형식). 응답 글자를 그대로 돌려준다.
        동시 전송(LIMIT > 1)일 때: 전송은 뒤의 일꾼에게 맡기고, **성공했을 때 올 응답**을 바로 돌려준다. 실제 응답과의 대조는 drain 이 한다."""
        rule = (note or {}).get("rule")
        if LIMIT > 1 and rule:
            with self._lock:
                self.login()
                self.count += 1
                n = self.count
            self._note(n=n, phase="send", method="POST", path=path, body=note or {}, file={"name": name, "bytes": len(data)})
            expect = f"success|{name}::/{rule}/{name}|{name}|{len(data)}"
            while True:         # 파일을 한꺼번에 메모리에 올리지 않게: 이 작품의 대기·전송 중 파일이 LIMIT 의 2배를 넘으면 줄 때까지 기다린다
                bad = [j for j in self.jobs if j.done.is_set() and j.error]
                if bad:
                    UPLOADS.drop(self)
                    raise Stop(f"파일 전송 실패({bad[0].name}): {bad[0].error}")
                if sum(1 for j in self.jobs if not j.done.is_set()) < LIMIT * 2:
                    break
                time.sleep(0.05)
            job = _Job(self, n, path, fields, name, data, mime, expect, wait)
            self.jobs.append(job)
            UPLOADS.submit(job)
            return base64.b64encode(("R" + base64.b64encode(expect.encode("utf-8")).decode("ascii")).encode("ascii")).decode("ascii")
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

    def download(self, path: str, fields: dict, wait: float = 120.0) -> tuple[bytes, str]:
        """화면의 내려받기 버튼과 같은 폼 전송. (받은 파일의 바이트, KOLIS 가 알려 준 파일 이름)"""
        import urllib.parse
        self.drain()
        with self._lock:
            self.login()
            self.count += 1
            n = self.count
            self._note(n=n, phase="send", method="POST", path=path, body={k: (v if len(str(v)) < 200 else f"({len(str(v)):,}자)") for k, v in fields.items()})
            try:
                r = self.s.post(BASE + path, data={k: str(v).encode("utf-8") for k, v in fields.items()}, timeout=(30, wait),
                                headers={"Referer": BASE + "/main/gohome.do", "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"})
            except Exception as e:  # noqa: BLE001
                self._note(n=n, phase="fail", error=f"{type(e).__name__}: {e}")
                raise Stop(f"파일을 받지 못했습니다({path}): {type(e).__name__}") from e
            cd = r.headers.get("Content-Disposition", "")
            m = re.search(r"filename\*?=(?:UTF-8'')?\"?([^\";]+)", cd)
            name = urllib.parse.unquote(m.group(1)) if m else ""
            self._note(n=n, phase="response", status=r.status_code, bytes=len(r.content), content_type=r.headers.get("Content-Type", ""), disposition=cd)
            if r.status_code != 200 or not r.content:
                raise Stop(f"파일 받기 응답 상태 {r.status_code}, {len(r.content)}바이트({path})")
            if b'name="pwd"' in r.content[:20000]:
                self.logged_in = False
                raise Stop("파일을 받으려는데 로그인 화면이 왔습니다(로그인이 풀림)")
            return r.content, name

    def get(self, path: str, wait: float = 60.0):
        """화면(HTML)이나 파일을 받는다. 자료를 바꾸지 않는 요청에만 쓴다."""
        self.drain()
        with self._lock:
            self.login()
            self.count += 1
            r = self.s.get(BASE + path, timeout=(30, wait), headers={"Referer": BASE + "/main/gohome.do"})
            self._note(n=self.count, phase="get", path=path, status=r.status_code, chars=len(r.content))
            return r

    def close(self) -> None:
        """로그아웃하지 않고 접속만 닫는다(로그아웃 요청이 같은 계정의 다른 접속을 끊는지 확인되지 않았다)."""
        UPLOADS.drop(self)
        for j in self.jobs:
            j.done.wait(timeout=310)
        self.jobs = []
        self.closed = True
        try:
            self.s.close()
        except Exception:  # noqa: BLE001
            pass
