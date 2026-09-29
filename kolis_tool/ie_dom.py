"""IE 모드 화면(팝업 포함)을 읽고, 화면이 KOLIS 와 주고받는 요청을 **화면 안에서** 기록한다. 이 모듈이 KOLIS 에 요청을 보내지는 않는다.

왜 이 방식인가(2026-09-29): IE 모드는 F12 를 못 쓰고, IEChooser 의 네트워크 탭은 이 PC 에서 "네트워크 컬렉션 에이전트를 시작하지
못했습니다"로 실패한다. 웹 페이지 대화 상자(showModalDialog) 팝업에는 개발자 도구가 붙지도 않는다.
그래서 이미 떠 있는 문서를 창 핸들에서 직접 얻어(WM_HTML_GETOBJECT):
  - 읽는다: 주소, 폼(전송 주소·방식·항목), 스크립트, 전체 HTML           → dump()
  - 기록한다: 기록용 스크립트를 넣어, 화면이 보내는 요청과 받은 응답을 모은다 → Recorder
      XMLHttpRequest, jQuery ajax(파일 전송 포함), 폼 전송, 창 열기(window.open·showModalDialog), 알림창 문구
      모은 것은 그 탭의 sessionStorage 에 쌓아 화면이 바뀌어도 남고, tick() 때 파일로 옮긴다.
화면 이동(메뉴 클릭으로 새 문서가 뜨는 것) 자체는 요청으로 잡히지 않는다. 이동 뒤의 주소와 문서를 읽어 보완한다.

남긴 파일에는 화면의 값(세션 정보 포함)이 그대로 들어간다. `work/captures/` 밖으로 내보내지 않는다(저장소 제외 폴더).
"""
from __future__ import annotations
import ctypes, datetime, json, os, re
from ctypes import wintypes
from pathlib import Path


def _documents(only_free: bool = False):
    """(창 제목, 창 클래스, IHTMLDocument2) 목록.
    only_free: 지금 조작할 수 있는 창만. 알림창이나 대화 상자 팝업이 떠 있으면 그 뒤의 창은 스크립트가 멈춰 있어,
    그 문서에 스크립트를 넣으려 하면 알림창이 닫힐 때까지 돌아오지 않는다 → 비활성(disabled) 창은 건드리지 않는다."""
    import pythoncom, win32com.client
    from pywinauto import Desktop
    try:
        pythoncom.CoInitialize()
    except Exception:  # noqa: BLE001
        pass
    user32 = ctypes.windll.user32
    msg = user32.RegisterWindowMessageW("WM_HTML_GETOBJECT")
    out, seen = [], set()
    for w in Desktop(backend="win32").windows():
        try:
            title, cls = w.window_text(), w.class_name()
            if only_free and not user32.IsWindowEnabled(w.handle):
                continue
            servers = [w] if cls == "Internet Explorer_Server" else w.descendants(class_name="Internet Explorer_Server")
        except Exception:  # noqa: BLE001
            continue
        for s in servers:
            h = s.handle
            if h in seen:
                continue
            seen.add(h)
            res = wintypes.DWORD()
            user32.SendMessageTimeoutW(h, msg, 0, 0, 2, 1500, ctypes.byref(res))
            if not res.value:
                continue
            try:
                obj = pythoncom.ObjectFromLresult(res.value, pythoncom.IID_IDispatch, 0)
                out.append((title, cls, win32com.client.dynamic.Dispatch(obj)))
            except Exception:  # noqa: BLE001
                continue
    return out


def _walk(doc, depth: int = 0) -> list:
    """문서와 그 안의 프레임 문서들."""
    docs = [doc]
    if depth > 3:
        return docs
    try:
        frames = doc.frames
        for i in range(int(frames.length)):
            try:
                docs += _walk(frames.item(i).document, depth + 1)
            except Exception:  # noqa: BLE001  (다른 출처의 프레임은 읽을 수 없다)
                pass
    except Exception:  # noqa: BLE001
        pass
    return docs


def _is_kolis(url: str) -> bool:
    return "kolis.nl.go.kr" in (url or "")


def describe(doc) -> dict:
    d = {"url": str(doc.URL), "title": str(doc.title or ""), "forms": [], "scripts": []}
    try:
        d["cookie_names"] = sorted({c.split("=")[0].strip() for c in str(doc.cookie or "").split(";") if c.strip()})
        d["referrer"] = str(doc.referrer or "")
    except Exception:  # noqa: BLE001
        pass
    try:
        forms = doc.forms
        for i in range(int(forms.length)):
            f = forms.item(i)
            fields = []
            els = f.elements
            for j in range(int(els.length)):
                e = els.item(j)
                try:
                    typ = str(getattr(e, "type", "") or "")
                    val = "" if typ in ("password",) else str(getattr(e, "value", "") or "")[:200]
                    fields.append({"name": str(getattr(e, "name", "") or ""), "id": str(getattr(e, "id", "") or ""), "tag": str(e.tagName), "type": typ, "value": val})
                except Exception:  # noqa: BLE001
                    continue
            d["forms"].append({"name": str(getattr(f, "name", "") or ""), "id": str(getattr(f, "id", "") or ""), "action": str(f.action or ""),
                               "method": str(f.method or ""), "enctype": str(getattr(f, "encoding", "") or ""), "target": str(getattr(f, "target", "") or ""),
                               "fields": fields})
    except Exception as e:  # noqa: BLE001
        d["forms_error"] = str(e)
    try:
        sc = doc.scripts
        for i in range(int(sc.length)):
            s = sc.item(i)
            d["scripts"].append({"src": str(getattr(s, "src", "") or ""), "text": str(getattr(s, "text", "") or "")})
    except Exception as e:  # noqa: BLE001
        d["scripts_error"] = str(e)
    try:
        d["html"] = str(doc.documentElement.outerHTML)
    except Exception as e:  # noqa: BLE001
        d["html"] = ""; d["html_error"] = str(e)
    return d


def _save_doc(d: dict, out_dir: Path, label: str, n: int) -> str:
    stamp = f"{datetime.datetime.now():%H%M%S}"
    name = re.sub(r"[^\w가-힣.-]+", "_", f"{stamp}_{n:02d}_{label}_{d['url'].split('?')[0].split('/')[-1] or 'doc'}")[:120]
    (out_dir / f"{name}.json").write_text(json.dumps({k: v for k, v in d.items() if k != "html"}, ensure_ascii=False, indent=1), encoding="utf-8")
    (out_dir / f"{name}.html").write_text(d.get("html", ""), encoding="utf-8")
    return name


def dump(out_dir: Path, label: str = "") -> list[dict]:
    """떠 있는 IE 모드 문서를 전부 읽어 파일로 남기고 요약을 돌려준다."""
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    summary, n = [], 0
    for title, cls, top in _documents():
        for doc in _walk(top):
            try:
                d = describe(doc)
            except Exception as e:  # noqa: BLE001
                summary.append({"window": title, "error": str(e)}); continue
            n += 1
            d["window"], d["window_class"] = title, cls
            name = _save_doc(d, out_dir, label, n)
            summary.append({"window": title[:60], "url": d["url"], "forms": [{"action": f["action"], "method": f["method"], "enctype": f["enctype"],
                            "fields": [x["name"] or x["id"] for x in f["fields"] if x["name"] or x["id"]]} for f in d["forms"]],
                            "scripts": [s["src"] for s in d["scripts"] if s["src"]], "inline_scripts": sum(1 for s in d["scripts"] if s["text"].strip()),
                            "html_chars": len(d.get("html", "")), "file": f"{name}.json"})
    return summary


# 화면에 넣는 기록용 스크립트. 옛 문서 모드에서도 돌도록 옛 문법으로 쓴다. 원래 동작은 그대로 부른다(기록만 덧붙임).
HOOK = r"""
(function(){
  if (window.__kolisRec) { return; }
  window.__kolisRec = 1;
  var KEY = '__kolisRec';
  function cut(s){ s = (s === null || s === undefined) ? '' : String(s); return s.length > 30000 ? s.substring(0, 30000) + '...(' + s.length + ')' : s; }
  function save(o){
    try {
      o.t = new Date().getTime(); o.page = String(location.href);
      var line = JSON.stringify(o);
      try { var a = window.sessionStorage.getItem(KEY); window.sessionStorage.setItem(KEY, (a ? a + '\n' : '') + line); }
      catch (e1) { window.__kolisLog = (window.__kolisLog || '') + line + '\n'; }
    } catch (e) {}
  }
  save({kind: 'hook', note: 'installed', title: String(document.title), mode: String(document.documentMode || '')});
  try {
    var X = window.XMLHttpRequest;
    if (X && X.prototype && X.prototype.open) {
      var op = X.prototype.open, sd = X.prototype.send, sh = X.prototype.setRequestHeader;
      X.prototype.open = function(m, u, a){ try { this.__r = {method: String(m), url: String(u), async: a, headers: {}}; } catch (e) {} return op.apply(this, arguments); };
      X.prototype.setRequestHeader = function(k, v){ try { this.__r.headers[k] = String(v); } catch (e) {} return sh.apply(this, arguments); };
      X.prototype.send = function(b){
        var x = this, r = x.__r || {};
        try { r.body = (typeof b === 'string') ? cut(b) : (b ? '[글자가 아닌 본문: 파일 전송 등]' : ''); } catch (e) {}
        var done = function(){
          try {
            if (x.readyState == 4 && !r.__d) {
              r.__d = 1;
              var o = {kind: 'xhr', method: r.method, url: r.url, async: r.async, headers: r.headers, body: r.body, status: x.status};
              try { o.response_type = x.getResponseHeader('Content-Type'); } catch (e2) {}
              try { o.response = cut(x.responseText); } catch (e3) { o.response = '[읽을 수 없음]'; }
              save(o);
            }
          } catch (e) {}
        };
        try { if (x.addEventListener) { x.addEventListener('readystatechange', done, false); } } catch (e) {}
        var ret = sd.apply(this, arguments);
        try { if (r.async === false) { done(); } } catch (e) {}
        return ret;
      };
    }
  } catch (e) { save({kind: 'hook', note: 'xhr 실패: ' + e.message}); }
  try {
    var $ = window.jQuery;
    if ($) {
      $(document).ajaxSend(function(ev, xhr, s){
        try {
          var d = s.data; if (d && typeof d !== 'string') { d = '[글자가 아닌 본문: 파일 전송 등]'; }
          save({kind: 'ajaxSend', method: s.type, url: String(s.url), data: cut(d), dataType: s.dataType, contentType: String(s.contentType), async: s.async});
        } catch (e) {}
      });
      $(document).ajaxComplete(function(ev, xhr, s){
        try {
          var o = {kind: 'ajaxComplete', method: s.type, url: String(s.url), status: xhr.status};
          try { o.response = cut(xhr.responseText); } catch (e2) { o.response = '[읽을 수 없음]'; }
          save(o);
        } catch (e) {}
      });
      if ($.fn && $.fn.ajaxSubmit) {
        var as = $.fn.ajaxSubmit;
        $.fn.ajaxSubmit = function(opt){
          try {
            var f = this[0], fields = [];
            if (f && f.elements) { for (var i = 0; i < f.elements.length; i++) { var e = f.elements[i]; if (e.name) { fields.push({name: e.name, type: e.type, value: e.type == 'password' ? '' : cut(e.value).substring(0, 500)}); } } }
            save({kind: 'ajaxSubmit', url: String((opt && opt.url) || (f && f.action) || ''), method: String((opt && opt.type) || (f && f.method) || ''),
                  enctype: String((f && (f.encoding || f.enctype)) || ''), dataType: String((opt && opt.dataType) || ''), fields: fields});
          } catch (e) {}
          return as.apply(this, arguments);
        };
      }
    }
  } catch (e) { save({kind: 'hook', note: 'jquery 실패: ' + e.message}); }
  try {
    var F = window.HTMLFormElement;
    var rec = function(f, how){
      try {
        var fields = [];
        for (var i = 0; i < f.elements.length; i++) { var e = f.elements[i]; if (e.name) { fields.push({name: e.name, type: e.type, value: e.type == 'password' ? '' : cut(e.value).substring(0, 500)}); } }
        save({kind: 'formSubmit', how: how, url: String(f.action), method: String(f.method), enctype: String(f.encoding || f.enctype || ''), target: String(f.target || ''), fields: fields});
      } catch (e) {}
    };
    if (F && F.prototype && F.prototype.submit) { var fs = F.prototype.submit; F.prototype.submit = function(){ rec(this, 'submit()'); return fs.apply(this, arguments); }; }
    if (document.addEventListener) { document.addEventListener('submit', function(ev){ rec(ev.target || ev.srcElement, 'event'); }, true); }
  } catch (e) { save({kind: 'hook', note: 'form 실패: ' + e.message}); }
  try {
    var wo = window.open;
    window.open = function(u, n, f){ save({kind: 'window.open', url: String(u), name: String(n || ''), features: String(f || '')}); return wo.apply ? wo.apply(window, arguments) : wo(u, n, f); };
  } catch (e) {}
  try {
    if (window.showModalDialog) {
      var sm = window.showModalDialog;
      window.showModalDialog = function(u, a, f){
        save({kind: 'showModalDialog', url: String(u), features: String(f || '')});
        var r = sm(u, a, f);
        try { save({kind: 'showModalDialog.return', url: String(u), value: cut(typeof r === 'object' ? JSON.stringify(r) : r)}); } catch (e2) {}
        return r;
      };
    }
  } catch (e) {}
  try {
    var al = window.alert, cf = window.confirm;
    window.alert = function(m){ save({kind: 'alert', text: cut(m)}); return al(m); };
    window.confirm = function(m){ var r = cf(m); save({kind: 'confirm', text: cut(m), answer: r}); return r; };
  } catch (e) {}
})();
"""

# 모은 기록을 문서의 속성으로 옮겨 밖에서 읽을 수 있게 하고, 옮긴 것은 비운다
FLUSH = r"""
(function(){
  var KEY = '__kolisRec', s = '';
  try { s = window.sessionStorage.getItem(KEY) || ''; window.sessionStorage.removeItem(KEY); } catch (e) {}
  try { if (window.__kolisLog) { s = (s ? s + '\n' : '') + window.__kolisLog; window.__kolisLog = ''; } } catch (e) {}
  document.documentElement.setAttribute('data-kolis-rec', s);
})();
"""


class Recorder:
    """프로그램이 KOLIS 화면을 조작하는 동안 곳곳에서 tick() 을 부른다. 부를 때마다:
    떠 있는 KOLIS 문서마다 기록용 스크립트를 넣고(이미 있으면 건너뜀), 모인 기록을 파일로 옮기고, 처음 보는 주소의 문서는 통째로 저장한다.
    어떤 경우에도 예외를 밖으로 내지 않는다(기록 때문에 본 작업이 멈추면 안 된다)."""

    def __init__(self, out_dir: Path | None = None, log=None):
        self.dir = Path(out_dir or Path("work") / "captures" / "rec" / f"{datetime.datetime.now():%Y%m%d-%H%M%S}")
        self.dir.mkdir(parents=True, exist_ok=True)
        self.log = log or (lambda m: None)
        self.seen: set[str] = set()
        self.n = 0
        self.count = 0
        self.off = ""          # 비어 있지 않으면 기록을 멈춘 이유
        self._failed = False

    def _write(self, rows: list[dict]):
        with open(self.dir / "requests.jsonl", "a", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        self.count += len([r for r in rows if r.get("kind") not in ("hook", "step")])

    def tick(self, label: str = "", wait: float = 8.0) -> int:
        """따로 스레드에서 돌리고 wait 초까지만 기다린다. 돌아오지 않으면 기록을 끈다(본 작업을 붙잡지 않는다)."""
        import threading
        if self.off:
            return 0
        box = {}
        def work():
            n = self._tick(label)
            if self._failed:          # 스레드에서 처음 문서를 얻을 때 한 번 실패하는 경우가 있어 한 번 더 한다
                n += self._tick(label + " (다시)")
            box.update(n=n)
        th = threading.Thread(target=work, daemon=True, name="kolis-rec")
        th.start(); th.join(wait)
        if th.is_alive():
            self.off = f"'{label}' 에서 화면이 {wait}초 동안 응답하지 않음"
            self.log(f"요청 기록을 멈춥니다: {self.off}")
            return 0
        return box.get("n", 0)

    def _tick(self, label: str = "") -> int:
        got = 0
        self._failed = False
        try:
            self._write([{"kind": "step", "label": label, "time": f"{datetime.datetime.now():%H:%M:%S}"}])
            for title, cls, top in _documents(only_free=True):
                try:
                    inside = _is_kolis(str(top.URL))
                except Exception:  # noqa: BLE001
                    inside = False
                for doc in _walk(top):
                    try:
                        url = str(doc.URL)
                        # KOLIS 화면 안의 프레임은 주소가 비어 있어도 기록한다(2026-09-29: 업로더 프레임의 주소가 KOLIS 주소가 아니라 빠졌었다)
                        if not _is_kolis(url) and not inside:
                            continue
                        win = doc.parentWindow
                        win.execScript(HOOK, "JavaScript")
                        win.execScript(FLUSH, "JavaScript")
                        raw = str(doc.documentElement.getAttribute("data-kolis-rec") or "")
                        rows = []
                        for line in raw.splitlines():
                            try:
                                r = json.loads(line); r["window"] = title[:60]; r["step"] = label
                                rows.append(r)
                            except json.JSONDecodeError:
                                continue
                        if rows:
                            self._write(rows); got += len(rows)
                        key = url.split("?")[0]
                        if key not in self.seen:
                            self.seen.add(key); self.n += 1
                            d = describe(doc); d["window"], d["window_class"], d["step"] = title, cls, label
                            _save_doc(d, self.dir, re.sub(r"\W+", "", label)[:20], self.n)
                    except Exception as e:  # noqa: BLE001
                        self._failed = True
                        self._write([{"kind": "step", "label": label, "error": f"{type(e).__name__}: {str(e)[:120]}", "window": title[:60]}])
        except Exception:  # noqa: BLE001
            pass
        return got


_RECORDER: Recorder | None = None


def recorder(log=None) -> Recorder | None:
    """프로그램 전체가 같이 쓰는 기록기. 환경변수 KOLIS_RECORD=0 이면 기록하지 않는다."""
    global _RECORDER
    if os.environ.get("KOLIS_RECORD", "1") == "0":
        return None
    if _RECORDER is None:
        _RECORDER = Recorder(log=log)
        if log:
            log(f"요청 기록 켬: {_RECORDER.dir}")
    return _RECORDER


def tick(label: str = "") -> int:
    r = recorder()
    return r.tick(label) if r else 0
