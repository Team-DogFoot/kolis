"""화면을 누르지 않고 KOLIS 에 요청을 보내는 방식(요청 방식). 근거는 2026-09-29 기록(`work/captures/rec/`, docs/REQUEST-AUTOMATION.md).

어떻게 보내는가: 로그인 쿠키는 스크립트에서 읽을 수 없다(화면에서 보이는 쿠키에 세션 쿠키가 없음). 그래서 따로 접속하지 않고,
**직원이 로그인해 둔 Edge 의 KOLIS 화면 안에서** 요청을 보낸다(그 화면의 XMLHttpRequest). 계정·쿠키를 다루지 않는다.
마우스·키보드·창 위치와 무관하므로 프로그램 창을 내리거나 Edge 를 앞에 둘 필요가 없다.

되는 것: 접수번호의 목록(콘텐츠ID·원문 수·MODS), 등록대상처리, 가원부번호 발급, 등록원부관리 목록 → 가원부 파일.
안 되는 것: 파일을 보내는 단계(일괄반입의 엑셀 첨부, 원문일괄등록의 폴더 전송). 화면의 스크립트는 PC 의 파일을 스스로 집을 수 없다.

**이 모듈의 함수는 부르면 KOLIS 에 실제 요청이 간다.** 직원 입회 아래에서만 부른다. 검증은 저장된 응답으로 한다(`check_saved`).
바꾸는 요청(등록대상처리, 가원부번호 발급)은 yes="YES" 가 있어야 하고, 보내기 전에 목록을 읽어 조건을 확인하고, 보낸 뒤 다시 읽어 확인한다.
"""
from __future__ import annotations
import json, re, time, uuid
from pathlib import Path
from urllib.parse import urlencode

BASE = "http://kolis.nl.go.kr"
WORK_CODE = "62"            # 납본(단행)
REG_CODE = "FTX"
WONMUN_SVC = "07"           # 납본뷰어
S_RECEIVED, S_TARGET, S_RECORD = "DS_1100", "DS_2100", "DS_3100"      # 접수 / 낱권등록대상 / 등록가원부자료

U_IMPORT = "/online/reg/bo/accrectarget/fileUpload.do"
IMPORT_DIR = "/Upload1/jangseo/ImpCont/amcont/"
U_KEY = "/online/acq/bodepst/depstrecet/onlineDepstRecet/getReceiptKeyByRcptNo.do"
U_LIST = "/online/acq/bodepst/depstrecet/onlineDepstRecet/selectMultipleOnlineDepstrecetList.do"
U_TARGET = "/online/acq/bodepst/depstrecet/onlineDepstRecet/updateTargetProcessing.do"
U_MAKE_LIST = "/online/reg/bo/accrecmake/onlineAccRecMake/selectAccRecMakeListWithParam.do"
U_MAKE = "/online/reg/bo/accrecmake/onlineAccRecMake/popup/insertTempAccessionRecNo.do"
U_MNG_LIST = "/online/reg/bo/accrecmng/onlineAccRecMng/selectAccRecMngListWithParam.do"

FORM = "application/x-www-form-urlencoded; charset=UTF-8"
JSON = "application/json"

# 화면의 목록 열 ↔ 응답 항목(화면 스크립트의 열 정의에서 읽음). 전체출력 파일과 같은 표를 만들 때 쓴다.
RECEIPT_COLUMNS = [("접수구분", "WORKING_STATUS_NAME"), ("접수자ID", "REG_ER_ID"), ("접수번호", "RECEIPT_NO"), ("콘텐츠유형", "TYPEOFRESOURCE_NAME"),
                   ("장르", "GENRE_NAME"), ("ISBN", "ISBN"), ("발간등록번호", "GPRN"), ("본표제", "TITLE"), ("편권차", "PARTNUMBER"),
                   ("표제관련정보", "SUBTITLE"), ("저작자", "AUTHOR"), ("발행자", "PUBLISHER"), ("발행년", "PUBLISH_YEAR"), ("가격", "CONTENTS_PRICE"),
                   ("원문갯수", "CNT_FILES"), ("업무구분", "WORK_CODE_NAME"), ("콘텐츠ID", "CONTENTS_ID"), ("담당자", "ORGANIZATION_CHARGE_NAME"),
                   ("파일명", "FILE_NM_DESC")]
RECORD_COLUMNS = [("일련번호", "ACCESSION_SERIAL_NO"), ("콘텐츠ID", "CONTENTS_ID"), ("발행자구분", "PUBLISHER_CODE_NAME"), ("본표제", "TITLE"),
                  ("저작자", "AUTHOR"), ("발행자", "PUBLISHER"), ("발행일", "PROD_DAY"), ("ISBN", "EA_ISBN"), ("콘텐츠수", "CNT_CONTENTS"),
                  ("등록번호", "ACCESSION_NO"), ("관리번호", "MANAGE_NO"), ("담당자", "LAST_MOD_ER_ID"), ("업무구분", "WORK_CODE"),
                  ("서비스범위", "LICENSETYPE"), ("원문서비스구분", "WONMUN_SVC"), ("이용대상", "USE_OBJ_CODE_NAME")]


class Stop(RuntimeError):
    pass


class NotSent(Stop):
    """요청이 KOLIS 로 나가지 않았다(화면을 못 찾음, 스크립트 오류). KOLIS 의 자료는 바뀌지 않았으므로 화면 방식으로 바꿔 진행해도 된다."""


# ---------- 화면 안에서 요청 보내기 ----------
SEND = r"""
(function(id, method, url, ctype, body){
  var b64 = null;
  if (body && body.indexOf('base64:') === 0) { b64 = body.substring(7); body = null; }
  window.__kolisReq = window.__kolisReq || {};
  var slot = window.__kolisReq[id] = {done: false, sent: false, status: 0, text: '', error: ''};
  try {
    var x = new XMLHttpRequest();
    x.open(method, url, true);
    if (ctype) x.setRequestHeader('Content-Type', ctype);
    x.setRequestHeader('Accept', 'application/json, text/javascript, */*; q=0.01');
    x.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
    x.onreadystatechange = function(){
      if (x.readyState !== 4) return;
      try { slot.status = x.status; slot.text = x.responseText; } catch (e) { slot.error = '' + (e.message || e); }
      slot.done = true;
    };
    if (b64) {                       // 파일이 든 본문: 프로그램이 만든 바이트를 그대로 보낸다
      var bin = window.atob(b64), n = bin.length, u = new Uint8Array(n);
      for (var i = 0; i < n; i++) u[i] = bin.charCodeAt(i);
      slot.sent = true;
      x.send(u.buffer);
    } else {
      slot.sent = true;
      x.send(body);
    }
  } catch (e) { slot.error = '' + (e.message || e); slot.done = true; }
})(%s, %s, %s, %s, %s);
"""
READ = r"""
(function(id){
  var s = (window.__kolisReq || {})[id], out = '';
  if (s && s.done) { out = s.status + '\n' + (s.sent ? 'sent' : 'notsent') + '\n' + s.error + '\n' + s.text; delete window.__kolisReq[id]; }
  document.documentElement.setAttribute('data-kolis-req', out);
})(%s);
"""


def _js(v) -> str:
    return "null" if v is None else json.dumps(str(v))      # json 문자열은 자바스크립트 문자열로도 유효(비ASCII 는 \uXXXX)


class Page:
    """로그인된 KOLIS 화면 하나. 알림창·대화 상자 뒤에 가려 멈춰 있는 화면은 쓰지 않는다."""

    def __init__(self, log=None, journal=None):
        self.log = log or (lambda m: None)
        self.journal = journal          # 보낸 것과 받은 것을 전부 남기는 기록(journal.Journal)
        self.doc = None
        self.count = 0

    def _find(self):
        from . import ie_dom
        for _title, _cls, top in ie_dom._documents(only_free=True):
            try:
                url = str(top.URL)
            except Exception:  # noqa: BLE001
                continue
            if url.startswith(BASE + "/") and "login" not in url.lower():
                return top
        raise NotSent("로그인된 KOLIS 화면을 찾지 못했습니다. Edge 에서 KOLIS 에 로그인하고, 떠 있는 알림창·팝업을 닫은 뒤 다시 실행하세요")

    def _note(self, **row):
        if self.journal:
            self.journal.write("request", **row)

    def send(self, method: str, path: str, body: str | None, ctype: str | None, wait: float = 60.0, shown: str | None = None) -> dict:
        """응답을 JSON 으로 돌려준다. 로그인 화면이 돌아오면(세션 끊김) 멈춘다. 보낸 것과 받은 것을 기록에 남긴다.
        shown: 기록에 남길 본문(파일이 든 본문은 바이트 대신 항목 요약을 남긴다)."""
        self.count += 1
        n, t0 = self.count, time.time()
        shown = body if shown is None else shown
        self.log(f"  요청 {n}: {method} {path} (본문 {len(body or '')}자)")
        self._note(n=n, phase="send", method=method, path=path, content_type=ctype, body=shown)
        try:
            if self.doc is None:
                self.doc = self._find()
            page = str(self.doc.URL)
            rid = uuid.uuid4().hex
            win = self.doc.parentWindow
            win.execScript(SEND % (_js(rid), _js(method), _js(BASE + path), _js(ctype), _js(body)), "JavaScript")
        except Stop:
            self._note(n=n, phase="fail", sent=False, error="로그인된 KOLIS 화면 없음")
            raise
        except Exception as e:  # noqa: BLE001
            self._note(n=n, phase="fail", sent=False, error=f"{type(e).__name__}: {e}")
            raise NotSent(f"화면에 요청 스크립트를 넣지 못했습니다({path}): {type(e).__name__}: {str(e)[:120]}") from e
        end = time.time() + wait
        while time.time() < end:
            time.sleep(0.2)
            try:
                win.execScript(READ % _js(rid), "JavaScript")
                raw = str(self.doc.documentElement.getAttribute("data-kolis-req") or "")
            except Exception as e:  # noqa: BLE001
                self._note(n=n, phase="fail", sent=None, error=f"응답을 읽다가 {type(e).__name__}: {e}")
                raise Stop(f"요청을 보낸 뒤 화면을 읽지 못했습니다({path}). 요청이 처리됐는지 KOLIS 에서 확인하세요: {type(e).__name__}") from e
            if raw:
                self.doc.documentElement.setAttribute("data-kolis-req", "")
                sec = round(time.time() - t0, 2)
                status, sent, error, text = (raw.split("\n", 3) + ["", "", ""])[:4]
                self._note(n=n, phase="response", page=page, status=status, sent=sent == "sent", error=error, seconds=sec, chars=len(text), response=text[:20000])
                self.log(f"  응답 {n}: 상태 {status}, {len(text)}자, {sec}초" + (f", 오류 {error}" if error else ""))
                if sent != "sent":
                    raise NotSent(f"요청이 나가지 않았습니다({path}): {error or '이유 없음'}")
                return parse(f"{status}\n{error}\n{text}", path)
        self._note(n=n, phase="fail", sent=None, error=f"{wait:.0f}초 안에 응답 없음")
        raise Stop(f"{wait:.0f}초 안에 응답이 없습니다: {path}. 요청이 처리됐는지 KOLIS 에서 확인하세요")


def parse(raw: str, path: str = "") -> dict:
    status, error, text = (raw.split("\n", 2) + ["", ""])[:3]
    if error:
        raise Stop(f"요청을 보내지 못했습니다({path}): {error}")
    if status != "200":
        raise Stop(f"응답 상태 {status}: {path}")
    if text.lstrip().startswith("<"):
        raise Stop(f"JSON 이 아니라 화면이 돌아왔습니다(로그인이 풀렸을 수 있음): {path}")
    try:
        d = json.loads(text)
    except json.JSONDecodeError as e:
        raise Stop(f"응답을 읽지 못했습니다({path}): {e}") from e
    if isinstance(d, dict) and d.get("sttus") not in (None, "success"):
        raise Stop(f"KOLIS 가 실패를 돌려주었습니다({path}): {d.get('msg') or d.get('sttus')}")
    return d


# ---------- 요청 본문(기록된 형식 그대로) ----------
def body_receipt(year: str, receipt: str) -> str:
    return urlencode({"acquisit_yr": year, "work_code": WORK_CODE, "receipt_no": receipt})


def body_target(items: list[dict]) -> str:
    keys = {i["RECEIPT_KEY"] for i in items}
    if len(keys) != 1:
        raise Stop(f"접수 키가 하나가 아닙니다: {sorted(keys)}")
    return json.dumps({"receipt_key": keys.pop(), "species_key": [i["SPECIES_KEY"] for i in items],
                       "contents_id": [i["CONTENTS_ID"] for i in items], "isbn": [i.get("ISBN") or "" for i in items],
                       "work_code": WORK_CODE, "checkYn": "all"}, ensure_ascii=False, separators=(",", ":"))


def body_make_list(year: str, receipt: str) -> str:
    return json.dumps([{"acquisit_yr": year, "receipt_no": str(receipt), "work_code": WORK_CODE}], separators=(",", ":"))


def body_make(year: str, items: list[dict]) -> str:
    pairs = [("accession_rec_make_year", year), ("reg_code", REG_CODE), ("acquisit_code", str(items[0]["ACQUISIT_CODE"]))]
    pairs += [("species_keys", i["SPECIES_KEY"]) for i in items]
    pairs += [("receipt_keys", i["RECEIPT_KEY"]) for i in items]
    pairs += [("wonmunSvcGbnCd", WONMUN_SVC)]
    return urlencode(pairs)


def body_mng_list(year: str, no: str) -> str:
    return urlencode({"acc_rec_key": "", "key_arr": "", "har_stat_cd": "20", "use_limit_code": "", "reg_code": REG_CODE,
                      "accession_rec_make_year": year, "rec_no_yn": "N", "accession_rec_no": no, "species": "", "book": "", "missingregnocnt": ""})


def multipart(fields: list[tuple[str, str]], file_field: str, file_path: Path, at: int, boundary: str = "") -> tuple[str, bytes]:
    """파일 첨부 형식의 본문. 화면의 폼과 같은 순서로 항목을 넣는다(at = 파일 항목이 들어갈 자리). (Content-Type, 본문 바이트)"""
    boundary = boundary or "----kolisFormBoundary" + uuid.uuid4().hex[:16]
    file_path = Path(file_path)
    parts = [f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode("utf-8") for k, v in fields]
    head = (f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; filename="{file_path.name}"\r\n'
            "Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet\r\n\r\n").encode("utf-8")
    parts.insert(at, head + file_path.read_bytes() + b"\r\n")
    return f"multipart/form-data; boundary={boundary}", b"".join(parts) + f"--{boundary}--\r\n".encode("ascii")


def import_fields(year: str, note: str) -> list[tuple[str, str]]:
    """일괄반입 팝업의 폼 항목(2026-09-29 기록의 순서와 값). 접수 키·접수번호는 비워 보낸다(KOLIS 가 새 접수번호를 만든다)."""
    return [("acquisit_code", "1"), ("acquisit_year", year), ("work_code", WORK_CODE), ("receipt_key", ""), ("receipt_no", ""),
            ("working_status", S_RECEIVED), ("har_stat_cd", "14"), ("desc", note), ("ipt_acquisit_year", year), ("s_work_code", WORK_CODE),
            ("ipt_desc", note), ("work_dir_path", IMPORT_DIR)]


def import_excel(page: Page, year: str, note: str, xlsx: Path, rows: int, yes: str, log=None) -> dict:
    """일괄반입을 요청으로. 반입은 되돌릴 수 없다: 보내기 전에 조건을 확인하고, 보낸 뒤 목록을 읽어 건수를 맞춰 본다.
    요청이 나가지 않았으면 NotSent(화면 방식으로 바꿔도 됨), 나간 뒤의 실패는 Stop(다시 반입하면 안 됨)."""
    import base64
    log = log or (lambda m: None)
    if yes != "YES":
        raise Stop("반입은 직원 동의 후 YES 를 넘겨야 합니다")
    xlsx = Path(xlsx)
    if not xlsx.is_file() or xlsx.suffix.lower() != ".xlsx":
        raise NotSent(f"반입용 엑셀이 없거나 xlsx 가 아닙니다: {xlsx}")
    if not note or re.search(r"\(차\)|\(\)", note):
        raise NotSent("비고에 차수와 번호가 없습니다")
    size = xlsx.stat().st_size
    fields = import_fields(year, note)
    ctype, body = multipart(fields, "file_name", xlsx, 11)
    log(f"일괄반입 요청: 파일 {xlsx.name} ({size:,}바이트, {rows}행), 비고 '{note}', 수입년도 {year}, 업무구분 {WORK_CODE}")
    page.send("POST", "/main/sessionDelay.do", None, None, wait=20)        # 로그인 상태 확인(화면이 주기적으로 보내는 것과 같은 요청, 자료를 바꾸지 않음)
    d = page.send("POST", U_IMPORT, "base64:" + base64.b64encode(body).decode("ascii"), ctype, wait=900,
                  shown=json.dumps({"fields": fields, "file": {"name": xlsx.name, "bytes": size}}, ensure_ascii=False))
    receipt = _text(d.get("receiptno"))
    if not receipt.isdigit():
        raise Stop(f"반입 응답에 접수번호가 없습니다: {str(d)[:200]}. KOLIS 에서 반입됐는지 확인하세요(다시 반입하지 마세요)")
    if int(d.get("file_size") or 0) != size:
        log(f"경고: KOLIS 가 받은 크기 {d.get('file_size')} ≠ 보낸 파일 크기 {size}")
    items = receipt_items(page, year, receipt)
    if rows and len(items) != rows:
        raise Stop(f"반입은 됐지만(접수번호 {receipt}) 목록이 {len(items)}건으로 반입용 엑셀 {rows}행과 다릅니다 → 직원 확인")
    log(f"반입 완료: 접수번호 {receipt}, {len(items)}건 ({items[0]['CONTENTS_ID']} … {items[-1]['CONTENTS_ID']})")
    return {"receipt": receipt, "count": len(items), "file_size": d.get("file_size"), "message": _text(d.get("msg")), "ok": True,
            "ids": [i["CONTENTS_ID"] for i in items], "titles": sorted({_text(i.get("TITLE")) for i in items})}


# ---------- 읽기 ----------
def _text(v) -> str:
    return "" if v is None else str(v)


def table(items: list[dict], columns: list[tuple[str, str]]) -> list[dict]:
    """화면의 전체출력과 같은 열 이름의 표."""
    return [{"No": str(n), **{label: _text(i.get(key)) for label, key in columns}} for n, i in enumerate(items, 1)]


def receipt_items(page: Page, year: str, receipt: str) -> list[dict]:
    d = page.send("POST", U_LIST, body_receipt(year, receipt), FORM)
    items = d.get("data") or []
    bad = [i.get("RECEIPT_NO") for i in items if not re.fullmatch(rf"{re.escape(str(receipt))}(-\d+)?", _text(i.get("RECEIPT_NO")))]
    if bad:
        raise Stop(f"접수번호 {receipt} 가 아닌 건이 섞여 왔습니다: {bad[:3]}")
    return sorted(items, key=lambda i: int(i.get("SERIAL_NO") or 0))


def contents(page: Page, year: str, receipt: str, log=None) -> dict:
    """접수번호의 콘텐츠ID·원문 수·MODS. 전체출력 파일을 받지 않고 같은 내용을 얻는다(읽기만 함)."""
    items = receipt_items(page, year, receipt)
    if log:
        log(f"접수번호 {receipt}: {len(items)}건, 원문 등록된 건 {sum(1 for i in items if int(i.get('CNT_FILES') or 0) > 0)}건")
    return {"receipt": receipt, "count": len(items), "table": table(items, RECEIPT_COLUMNS),
            "items": [{"serial": int(i.get("SERIAL_NO") or 0), "id": i["CONTENTS_ID"], "vol": _text(i.get("VOL")), "title": _text(i.get("TITLE")),
                       "isbn": _text(i.get("ISBN")), "files": int(i.get("CNT_FILES") or 0), "status": _text(i.get("WORKING_STATUS")),
                       "mods": _text(i.get("CONTENTS_XML"))} for i in items]}


def export_receipt(page: Page, year: str, receipt: str, work_dir: Path = Path("work"), log=None) -> dict:
    """화면의 '전체출력'을 대신한다(읽기만 함). 같은 열의 표를 `work/접수번호 N.xlsx` 로 쓰고 화면 방식과 같은 결과를 돌려준다.
    MODS 는 `work/xml/<콘텐츠ID>.xml` 로 함께 남긴다(점검 도구가 읽는다)."""
    import openpyxl
    c = contents(page, year, receipt, log)
    if not c["count"]:
        raise Stop(f"접수번호 {receipt} 에 자료가 없습니다(번호가 틀렸거나 이미 등록대상처리됨)")
    rows = list(reversed(c["table"]))          # 화면 목록은 뒤 번호부터
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = f"접수번호 {receipt}"
    ws.append(list(rows[0].keys()))
    for n, r in enumerate(rows, 1):
        ws.append([str(n)] + list(r.values())[1:])
    work_dir = Path(work_dir); work_dir.mkdir(parents=True, exist_ok=True)
    out = work_dir / f"접수번호 {receipt}.xlsx"
    wb.save(out)
    xml = work_dir / "xml"; xml.mkdir(exist_ok=True)
    for i in c["items"]:
        if i["mods"]:
            (xml / f"{i['id']}.xml").write_text(i["mods"], encoding="utf-8")
    if log:
        log(f"접수 목록 저장: {out.name} ({c['count']}건), MODS {sum(1 for i in c['items'] if i['mods'])}건 → {xml}")
    it = c["items"]
    return {"file": str(out), "receipt": str(receipt), "count": c["count"], "first": it[0]["id"], "last": it[-1]["id"], "title": it[0]["title"],
            "files": sum(1 for i in it if i["files"] > 0)}


# ---------- 바꾸는 요청 ----------
def target_process(page: Page, year: str, receipt: str, yes: str, log=None) -> dict:
    log = log or (lambda m: None)
    if yes != "YES":
        raise Stop("등록대상처리는 직원 동의 후 YES 를 넘겨야 합니다")
    items = receipt_items(page, year, receipt)
    if not items:
        raise Stop(f"접수번호 {receipt} 에 자료가 없습니다(이미 등록대상처리됐을 수 있음)")
    wrong = [i["CONTENTS_ID"] for i in items if i.get("WORKING_STATUS") != S_RECEIVED]
    if wrong:
        raise Stop(f"'접수' 상태가 아닌 건이 있습니다: {wrong[:3]}")
    nofile = [i["CONTENTS_ID"] for i in items if int(i.get("CNT_FILES") or 0) < 1]
    if nofile:
        raise Stop(f"원문이 등록되지 않은 건이 있습니다({len(nofile)}건): {nofile[:3]}. 원문일괄등록을 먼저 끝내세요")
    log(f"등록대상처리 요청: 접수번호 {receipt}, {len(items)}건")
    page.send("POST", U_TARGET, body_target(list(reversed(items))), JSON, wait=180)     # 화면은 목록 순서(뒤 번호부터)로 보낸다
    left = receipt_items(page, year, receipt)
    if left:
        raise Stop(f"등록대상처리 뒤에도 접수 목록에 {len(left)}건이 남아 있습니다")
    log("등록대상처리 완료(접수 목록에서 빠짐)")
    return {"receipt": receipt, "count": len(items), "ids": [i["CONTENTS_ID"] for i in items]}


def make_items(page: Page, year: str, receipt: str) -> list[dict]:
    d = page.send("POST", U_MAKE_LIST, body_make_list(year, receipt), JSON)
    items = [i for i in (d.get("data") or []) if _text(i.get("RECEIPT_NO")) == str(receipt)]
    return sorted(items, key=lambda i: _text(i.get("MANAGE_NO")))


def check_make(items: list[dict], receipt: str) -> None:
    """가원부번호를 주기 전에 확인하는 조건(화면 방식 `kolis_register.make_record` 와 같은 조건)."""
    if not items:
        raise Stop(f"등록원부작성 목록에 접수번호 {receipt} 가 없습니다(등록대상처리 전이거나 이미 가원부번호를 받음)")
    for name, key, want in (("상태", "WORKING_STATUS", S_TARGET), ("등록구분", "REG_CODE", REG_CODE)):
        bad = [i["CONTENTS_ID"] for i in items if i.get(key) != want]
        if bad:
            raise Stop(f"{name}이(가) {want} 가 아닌 건이 있습니다: {bad[:3]}")
    for name, key in (("이용대상", "USE_OBJ_CODE"), ("서비스범위", "LICENSETYPE")):
        kinds = sorted({_text(i.get(key)) for i in items})
        if len(kinds) > 1:
            raise Stop(f"{name}이(가) 섞여 있습니다({', '.join(kinds)}). 한 가원부에는 같은 값만 넣습니다 → 직원 확인")
    total = {int(i.get("TOT_CNT_SPECIES") or 0) for i in items}
    if total != {len(items)}:
        raise Stop(f"목록 건수({len(items)})와 KOLIS 가 알려 준 건수({sorted(total)})가 다릅니다")
    nofile = [i["CONTENTS_ID"] for i in items if int(i.get("CNT_FILES") or 0) < 1]
    if nofile:
        raise Stop(f"원문이 없는 건이 있습니다: {nofile[:3]}")


def make_record(page: Page, year: str, receipt: str, yes: str, log=None) -> dict:
    log = log or (lambda m: None)
    if yes != "YES":
        raise Stop("가원부번호 발급은 직원 동의 후 YES 를 넘겨야 합니다")
    items = make_items(page, year, receipt)
    check_make(items, receipt)
    log(f"가원부번호 요청: 접수번호 {receipt}, {len(items)}건, 등록구분 {REG_CODE}, 원문서비스구분 {WONMUN_SVC}(납본뷰어)")
    d = page.send("POST", U_MAKE, body_make(year, items), FORM, wait=180)
    no = _text(d.get("temp_accession_rec_no"))
    if not no.isdigit():
        raise Stop(f"가원부번호를 받지 못했습니다: {str(d)[:120]}")
    log(f"가원부번호 {year}-{no}")
    return {"receipt": receipt, "year": year, "no": no, "count": len(items)}


def record_items(page: Page, year: str, no: str) -> list[dict]:
    d = page.send("POST", U_MNG_LIST, body_mng_list(year, no), FORM)
    items = [i for i in (d.get("list") or []) if _text(i.get("TEMP_ACCESSION_REC_NO")) == str(no)]
    return sorted(items, key=lambda i: int(i.get("ACCESSION_SERIAL_NO") or 0))


def write_record(items: list[dict], year: str, no: str, receipt: str, work_dir: Path) -> Path:
    """직원이 주고받는 가원부 파일과 같은 형태(시트 이름, 열 17개)."""
    import openpyxl
    rows = table(items, RECORD_COLUMNS)
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = f"가원부번호 {year}-{no}"
    ws.append(list(rows[0].keys()))
    for r in rows:
        ws.append([v if v != "" else None for v in r.values()])
    work_dir = Path(work_dir); work_dir.mkdir(parents=True, exist_ok=True)
    out = work_dir / f"가원부번호 {year}-{no}(접수번호 {receipt}).xlsx"
    wb.save(out)
    return out


def export_record(page: Page, year: str, no: str, receipt: str, work_dir: Path = Path("work"), log=None) -> dict:
    items = record_items(page, year, no)
    if not items:
        raise Stop(f"등록원부관리에 가원부번호 {year}-{no} 가 없습니다")
    other = sorted({m.group(1).lstrip("0") for i in items if (m := re.fullmatch(r"\d+-\d+-(\d+)-\d+", _text(i.get("MANAGE_NO"))))} - {str(receipt)})
    if other:
        raise Stop(f"가원부번호 {no} 에 다른 접수번호({', '.join(other)})의 자료가 있습니다 → 직원 확인")
    out = write_record(items, year, no, receipt, work_dir)
    if log:
        log(f"가원부 파일 저장: {out.name} ({len(items)}건)")
    return {"file": str(out), "count": len(items), "no": no, "year": year, "receipt": receipt, "ids": [i["CONTENTS_ID"] for i in items]}


def run(receipt: str, year: str, work_dir: Path = Path("work"), log=None, handle: dict | None = None, yes: str = "", page: Page | None = None) -> dict:
    """등록대상처리 → 가원부번호 → 가원부 파일. 화면 방식 `kolis_register.run` 과 같은 결과를 돌려준다."""
    handle = handle or {}
    log = log or (lambda m: None)
    page = page or Page(log)
    if receipt_items(page, year, receipt):
        a = target_process(page, year, receipt, yes, log)
    else:          # 앞 실행이 등록대상처리까지 하고 멈춘 경우: 등록원부작성 목록에 있으면 이어서 한다
        made = make_items(page, year, receipt)
        if not made:
            raise Stop(f"접수번호 {receipt} 가 납본자료접수에도 등록원부작성에도 없습니다(번호가 틀렸거나 이미 가원부번호를 받음) → KOLIS 에서 확인")
        log(f"납본자료접수 목록에 없음 — 등록대상처리는 이미 된 상태. 등록원부작성 목록 {len(made)}건으로 이어서 진행")
        a = {"receipt": receipt, "count": len(made), "ids": [i["CONTENTS_ID"] for i in made], "already": True}
    if handle.get("cancel"):
        raise Stop("사용자가 중단함(등록대상처리까지 끝남)")
    b = make_record(page, year, receipt, yes, log)
    if handle.get("cancel"):
        raise Stop(f"사용자가 중단함(가원부번호 {year}-{b['no']} 발급까지 끝남)")
    c = export_record(page, year, b["no"], receipt, work_dir, log)
    if c["count"] != a["count"] or sorted(c["ids"]) != sorted(a["ids"]):
        raise Stop(f"등록대상처리한 자료({a['count']}건)와 가원부 파일의 자료({c['count']}건)가 다릅니다 → 직원 확인")
    return {"receipt": receipt, "target": a, "record": b, "export": c, "record_no": f"{year}-{b['no']}", "file": c["file"], "count": c["count"]}


# ---------- 저장된 기록으로 검증(KOLIS 에 보내지 않음) ----------
class Replay:
    """기록 파일의 응답을 돌려주는 가짜 화면. 이 모듈이 만드는 본문이 기록된 본문과 같은지도 함께 본다."""

    def __init__(self, rec_root: Path):
        self.rows = []
        for f in sorted(Path(rec_root).glob("*/requests.jsonl")):
            for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if r.get("kind") == "xhr" and r.get("response"):
                    self.rows.append(r)
        self.sent: list[dict] = []
        self.used: dict[str, int] = {}

    def send(self, method, path, body, ctype, wait=0, shown=None):
        found = [r for r in self.rows if r["url"].split("?")[0] == BASE + path]
        if not found:
            raise Stop(f"기록에 없는 주소: {path}")
        n = self.used.get(path, 0)
        r = found[min(n, len(found) - 1)]
        self.used[path] = n + 1
        rec = re.sub(r"&?jqxWidget\w+=\w+", "", r.get("body") or "")       # 화면 부품이 덧붙인 값은 뺀다
        self.sent.append({"path": path, "same_body": (body or "") == rec, "mine": body, "recorded": rec})
        return parse(f"200\n\n{r['response']}", path)


def check_saved(rec_root: Path = Path("work/captures/rec"), work_dir: Path = Path("work")) -> list[str]:
    """기록(접수 939, 가원부 2026-1615)으로 확인: 본문 형식이 기록과 같은가, 만든 표가 화면에서 받은 파일과 같은가."""
    import openpyxl
    from .ids_from_export import export_table
    out = []
    p = Replay(rec_root)
    items = receipt_items(p, "2026", "939")
    mine = table(list(reversed(items)), RECEIPT_COLUMNS)
    real = export_table(work_dir / "접수번호 939.xls")
    skip = {"No", "ㅁ", "원문갯수", "가격"}        # 원문갯수는 받은 시점이 다르고, 가격은 화면이 통화 기호를 붙인다
    diff = [(a["접수번호"], k, a[k], b.get(k)) for a, b in zip(mine, real) for k in a if k not in skip and a[k] != (b.get(k) or "")]
    out.append(f"접수 목록 표 vs 전체출력 파일: {len(mine)}행/{len(real)}행, 다른 칸 {len(diff)} {diff[:3]}")
    import tempfile
    from .ids_from_export import receipt_map
    with tempfile.TemporaryDirectory() as td:
        p.used.clear()
        r = export_receipt(p, "2026", "939", Path(td))
        a, b = receipt_map(Path(r["file"])), receipt_map(work_dir / "접수번호 939.xls")
        out.append(f"요청으로 만든 접수 목록 파일 → 폴더명 단계가 읽는 값: {'전체출력 파일과 같음' if a == b else '다름'} ({len(a)}건), MODS {len(list((Path(td) / 'xml').glob('*.xml')))}건")
    # 일괄반입 본문: 항목 이름·순서가 기록(화면의 폼)과 같은가, 파일이 그대로 들어가는가
    import email, email.policy
    rec_fields = next(r for f in sorted(Path(rec_root).glob("*/requests.jsonl")) for r in map(json.loads, f.read_text(encoding="utf-8", errors="replace").splitlines())
                      if r.get("kind") == "ajaxSubmit")["fields"]
    x = Path(next(f["value"] for f in rec_fields if f["type"] == "file"))
    note = next(f["value"] for f in rec_fields if f["name"] == "desc")
    if x.is_file():
        ctype, raw = multipart(import_fields("2026", note), "file_name", x, 11)
        msg = email.message_from_bytes(b"Content-Type: " + ctype.encode() + b"\r\n\r\n" + raw, policy=email.policy.HTTP)
        got = [(p.get_param("name", header="content-disposition"), p.get_payload(decode=True)) for p in msg.iter_parts()]
        same_names = [n for n, _ in got] == [f["name"] for f in rec_fields]
        same_vals = all(v.decode("utf-8") == f["value"] for (n, v), f in zip(got, rec_fields) if f["type"] != "file")
        same_file = dict(got)["file_name"] == x.read_bytes()
        out.append(f"일괄반입 본문: 항목 이름·순서 {'같음' if same_names else '다름'}, 값 {'같음' if same_vals else '다름'}, 파일 바이트 {'같음' if same_file else '다름'} ({len(raw):,}바이트)")
    else:
        out.append(f"일괄반입 본문: 기록에 있는 파일이 없어 확인하지 못함({x.name})")
    out.append("등록대상처리 본문: " + ("기록과 같음" if body_target(list(reversed(items))) == next(
        r["body"] for r in p.rows if r["url"].endswith("updateTargetProcessing.do")) else "기록과 다름"))
    made = make_items(p, "2026", "939")
    check_make(made, "939")
    out.append("가원부번호 본문: " + ("기록과 같음" if body_make("2026", made) == next(
        r["body"] for r in p.rows if r["url"].endswith("insertTempAccessionRecNo.do")) else "기록과 다름"))
    rec = record_items(p, "2026", "1615")
    ws = openpyxl.load_workbook(work_dir / "가원부번호 2026-1615(접수번호 939).xlsx").active
    real = [tuple("" if v is None else str(v) for v in r) for r in ws.iter_rows(values_only=True)]
    rows = table(rec, RECORD_COLUMNS)
    mine = [tuple(rows[0].keys())] + [tuple(r.values()) for r in rows]
    out.append(f"가원부 표 vs 화면에서 받은 가원부 파일: {'같음' if mine == real else '다름'} ({len(mine) - 1}행)")
    for s in p.sent:
        out.append(f"보낸 본문 {s['path'].split('/')[-1]}: " + ("기록과 같음" if s["same_body"] else f"기록과 다름\n   내 것: {s['mine']}\n   기록: {s['recorded']}"))
    return out
