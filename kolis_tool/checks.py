"""에이전트가 자기 결과를 스스로 검사하는 도구. 에이전트가 작업 중에 직접 돌리고(`python -m kolis_tool check-research …`), 프로그램도 끝난 뒤 같은 검사를 돌린다.

여기서는 **판단하지 않는다.** 어느 플랫폼이 최초인지, 어느 날짜가 맞는지는 에이전트와 검수 에이전트가 정한다.
검사하는 것은 형식과 근거뿐이다: 있어야 할 항목이 있는가, 값마다 근거(주소·화면 글자)가 붙었는가, 날짜·가격이 그 글자 안에 실제로 보이는가,
찾지 못한 값에는 어디를 찾아봤는지 적혔는가, 출판사 기재와 다른 값은 엇갈림으로 보고됐는가, 검수를 받았는가.
"""
from __future__ import annotations
import json, re
from pathlib import Path


def _norm(s) -> str:
    return re.sub(r"\s+", "", str(s or "")).lower()


def _same(a, b) -> bool:
    a, b = _norm(a), _norm(b)
    return bool(a) and bool(b) and (a in b or b in a)


def _d8(s) -> str:
    d = re.sub(r"\D", "", str(s or ""))
    return d if len(d) == 8 else ""


def _digits(s) -> str:
    return re.sub(r"\D", "", str(s or ""))


def _ev(items) -> list[dict]:
    return [e for e in (items or []) if isinstance(e, dict) and str(e.get("url") or "").startswith("http") and str(e.get("quote") or "").strip()]


def _in_quotes(value: str, evidence: list[dict], short_ok: bool = False) -> bool:
    for e in evidence:
        q = _digits(e.get("quote"))
        if value and (value in q or (short_ok and len(value) == 8 and value[2:] in q)):
            return True
    return False


def _not_found(data: dict, word: str) -> bool:
    for n in data.get("not_found") or []:
        if word in str(n.get("what") or "") and len([s for s in n.get("searched") or [] if str(s).strip()]) >= 2:
            return True
    return False


def check_research(result: Path, job: Path | None = None) -> list[str]:
    """걸린 항목 목록. 비어 있으면 통과."""
    result = Path(result)
    job = Path(job) if job else result.with_name("job.json")
    if not result.exists():
        return [f"결과 파일이 없습니다: {result}"]
    try:
        d = json.loads(result.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [f"결과 파일이 JSON 으로 읽히지 않습니다: {e}"]
    j = json.loads(job.read_text(encoding="utf-8")) if job.exists() else {}
    n = int(d.get("count") or j.get("count") or 0)      # 납본 건수와 출판사 기재값은 결과 파일에 적힌 것을 우선(작업 파일에 없을 수 있다)
    hints = d.get("publisher_says") or j.get("publisher_says") or {}
    if not n:
        return ["count(납본 건수)가 없습니다: research.json 맨 위에 count 와 publisher_says 를 적으세요"]
    out: list[str] = []

    plats = d.get("platforms") or []
    live = [p for p in plats if str(p.get("url_work") or "").startswith("http")]
    if not d.get("searched"):
        out.append("searched 가 비어 있습니다: 어디를 어떻게 찾아봤는지 전부 적으세요(작품이 없던 곳 포함)")
    if not live:
        out.append("작품 페이지 주소(url_work)가 있는 플랫폼이 하나도 없습니다")
    for p in live:
        if not str(p.get("same_work") or "").strip():
            out.append(f"플랫폼 '{p.get('name')}': 같은 작품이라고 본 근거(same_work)가 없습니다")
        for dt in p.get("dates_on_page") or []:
            if _d8(dt.get("date")) and not _in_quotes(_d8(dt.get("date")), [{"url": "http", "quote": dt.get("quote")}], True):
                out.append(f"플랫폼 '{p.get('name')}' 날짜 {dt.get('date')}: quote 안에 그 날짜가 보이지 않습니다(화면 글자를 그대로 옮기세요)")
    stated = str(hints.get("platform") or "").strip()
    if stated and not any(_same(stated, p.get("name")) for p in plats) and not any(_same(stated, s.get("where")) for s in d.get("searched") or []):
        out.append(f"출판사가 적은 최초 연재 플랫폼 '{stated}' 을 열어 본 기록이 없습니다")

    first = str(d.get("platform_first") or "").strip()
    if not first:
        out.append("platform_first 가 비어 있습니다")
    else:
        if not any(_same(first, p.get("name")) for p in plats):
            out.append(f"platform_first '{first}' 가 platforms 에 없습니다")
        if not str(d.get("platform_first_reason") or "").strip():
            out.append("platform_first_reason(그렇게 정한 이유)이 없습니다")
        if stated and not _same(stated, first) and not any("플랫폼" in str(c.get("field") or "") for c in d.get("conflicts") or []):
            out.append(f"최초 연재 플랫폼이 출판사 기재('{stated}')와 다른데 conflicts 에 보고되지 않았습니다")

    eps = {}
    for e in d.get("episodes") or []:
        try:
            eps[int(e.get("no"))] = e
        except (TypeError, ValueError):
            out.append(f"episodes 의 no 가 숫자가 아닙니다: {e.get('no')!r}")
    no_date, bad_quote, no_price, no_src = [], [], [], []
    for i in range(1, n + 1):
        e = eps.get(i)
        if e is None:
            no_date.append(i); no_price.append(i); continue
        date = _d8(e.get("date"))
        if not date:
            no_date.append(i)
        else:
            if not _in_quotes(date, _ev(e.get("evidence")), True):
                bad_quote.append(i)
            if not str(e.get("source") or "").strip():
                no_src.append(i)
        if not _digits(e.get("price")):
            no_price.append(i)
    if no_date and not _not_found(d, "공개일"):
        out.append(f"공개일이 없는 번호 {no_date[:30]}: 찾아 넣거나, 끝내 못 찾았으면 not_found 에 what 에 '공개일'을 넣고 어디를 찾아봤는지 2곳 이상 적으세요")
    if bad_quote:
        out.append(f"번호 {bad_quote[:30]}: evidence 의 quote 안에 그 공개일이 보이지 않습니다(주소와 화면 글자를 그대로 옮기세요)")
    if no_src:
        out.append(f"번호 {no_src[:30]}: 그 날짜가 어느 플랫폼 것인지(source) 없습니다")
    if no_price and not _not_found(d, "가격"):
        out.append(f"가격이 없는 번호 {no_price[:30]}: 찾아 넣거나 not_found 에 '가격'으로 적으세요")
    extra = sorted(k for k in eps if k < 1 or (n and k > n))
    if extra:
        out.append(f"납본 건수({n})를 벗어난 번호가 episodes 에 있습니다: {extra[:10]}")

    if str(d.get("rating") or "").strip():
        if not _ev(d.get("rating_evidence")):
            out.append("이용등급에 근거(rating_evidence: 주소와 화면 글자)가 없습니다")
    elif not _not_found(d, "등급"):
        out.append("이용등급이 없습니다: 찾아 넣거나 not_found 에 '등급'으로 적으세요")
    authors = d.get("authors") or []
    if not authors and not _not_found(d, "저자"):
        out.append("저자가 없습니다")
    for a in authors:
        if not str(a.get("role") or "").strip() and not _not_found(d, "역할"):
            out.append(f"저자 '{a.get('name')}' 의 역할이 없습니다")
        if not _ev(a.get("evidence")):
            out.append(f"저자 '{a.get('name')}' 에 근거가 없습니다")
    for key, word in (("publisher_name", "발행처"), ("publisher_place", "소재지")):
        if str(d.get(key) or "").strip():
            if not _ev(d.get("publisher_evidence")):
                out.append(f"{word}에 근거(publisher_evidence)가 없습니다")
        elif not _not_found(d, word):
            out.append(f"{word}가 없습니다: 찾아 넣거나 not_found 에 '{word}'로 적으세요")
    for key, word in (("genre", "장르"), ("summary", "소개")):
        if not str(d.get(key) or "").strip() and not _not_found(d, word):
            out.append(f"{word}가 없습니다: 찾아 넣거나 not_found 에 '{word}'로 적으세요")
    if live and not (str(d.get("url_main") or "").startswith("http") and str(d.get("url_work") or "").startswith("http")):
        out.append("원문주소(url_main, url_work)가 없습니다")
    for c in d.get("conflicts") or []:
        if not str(c.get("chosen") or "").strip() or not str(c.get("reason") or "").strip():
            out.append(f"conflicts '{c.get('field')}': 무엇을 골랐는지(chosen)와 이유(reason)가 없습니다")

    if not out:      # 형식·근거가 다 갖춰진 뒤에 검수 단계를 요구한다
        rv = d.get("review") or {}
        if not rv.get("done"):
            out.append("검수를 아직 받지 않았습니다: reviewer 에이전트에게 맡기고, 지적을 처리한 뒤 review.done 을 true 로 하세요")
        elif len(rv.get("findings") or []) != len(rv.get("resolved") or []):
            out.append(f"검수 지적 {len(rv.get('findings') or [])}건 중 처리 기록(review.resolved)이 {len(rv.get('resolved') or [])}건입니다. 지적마다 처리 내용을 적으세요")
    return out


def main_check_research(result: str, job: str | None = None) -> int:
    fails = check_research(Path(result), Path(job) if job else None)
    if not fails:
        print("통과")
        return 0
    print(f"걸린 항목 {len(fails)}건:")
    for f in fails:
        print(f"- {f}")
    return 1


def check_build(result: Path, job: Path | None = None) -> list[str]:
    """MODS 구축 판단(build.json) 검사 — 형식과 근거만. 연결할지 말지는 에이전트와 검수가 정한다.
    저자마다 결정이 있는가, link 면 후보 안의 번호·근거·high 확신인가, 다른이름은 원문 근거가 있는가, 주제명 두 묶음이 고정값인가, UCI 는 근거 또는 찾아본 곳이 있는가, 검수를 받았는가."""
    result = Path(result)
    job = Path(job) if job else result.with_name("job.json")
    if not result.exists():
        return [f"결과 파일이 없습니다: {result}"]
    try:
        d = json.loads(result.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [f"결과 파일이 JSON 으로 읽히지 않습니다: {e}"]
    j = json.loads(job.read_text(encoding="utf-8")) if job.exists() else {}
    out: list[str] = []
    want = {a.get("name"): a for a in j.get("authors") or []}
    got = {a.get("name"): a for a in d.get("authors") or []}
    for name in want:
        if name not in got:
            out.append(f"저자 '{name}' 의 결정이 없습니다(authors 에 저자마다 한 항목)")
    for name, a in got.items():
        dec = a.get("decision")
        if dec not in ("link", "none"):
            out.append(f"저자 '{name}': decision 은 link 또는 none 이어야 합니다(지금 {dec!r})"); continue
        if not str(a.get("reason") or "").strip():
            out.append(f"저자 '{name}': reason(이유)이 없습니다")
        cands = {c.get("AC_CONTROL_NO") for c in (want.get(name) or {}).get("candidates") or []}
        if dec == "link" and a.get("source") == "staff":
            if not str(a.get("ac_control_no") or "").strip():
                out.append(f"저자 '{name}': 직원 결정(staff)인데 전거 번호가 없습니다")
            continue      # 직원이 정한 연결은 후보·확신 검사를 하지 않는다(2026-10-03 계획 6절)
        if dec == "link":
            no = a.get("ac_control_no")
            if cands and no not in cands:
                out.append(f"저자 '{name}': ac_control_no {no!r} 가 전거 검색 후보에 없습니다")
            if a.get("confidence") != "high":
                out.append(f"저자 '{name}': 연결(link)은 confidence 가 high 일 때만 가능합니다(직원 기준: 강한 확신)")
            if not _ev(a.get("evidence")):
                out.append(f"저자 '{name}': 연결 근거(evidence 의 url+quote)가 없습니다")
        else:
            if cands and not a.get("rejected"):
                out.append(f"저자 '{name}': 후보가 {len(cands)}건 있는데 왜 뺐는지(rejected)가 비어 있습니다")
        for alt in a.get("alternative_names") or []:
            if "원문" not in str(alt.get("source") or "") or not str(alt.get("quote") or "").strip():
                out.append(f"저자 '{name}' 다른이름 '{alt.get('name')}': 원문(표제면·판권기·표지) 근거가 없습니다. 원문에 있는 경우에만 넣습니다")
            if alt.get("alt_type") not in ("nickname", "formal name", "no specific type"):
                out.append(f"저자 '{name}' 다른이름 '{alt.get('name')}': alt_type 값이 틀렸습니다")
        if j.get("manuscript") is None and a.get("alternative_names"):
            out.append(f"저자 '{name}': 원문이 없는데(manuscript null) 다른이름이 들어 있습니다")
    subj = d.get("subjects") or []
    fixed = {("topic", "만화[漫畵]", "KSH1998022212"), ("genre", "웹툰[webtoon]", "KSH2016000049")}
    if {(s.get("kind"), s.get("term"), s.get("id")) for s in subj} != fixed or len(subj) != 2:
        out.append("subjects 는 고정 두 묶음(topic 만화[漫畵] KSH1998022212, genre 웹툰[webtoon] KSH2016000049)이어야 합니다")
    u = d.get("uci") or {}
    if str(u.get("value") or "").strip():
        if not _ev(u.get("evidence")):
            out.append("uci 값이 있는데 근거(url+quote)가 없습니다")
        elif not any(str(u["value"]).replace(" ", "") in str(e.get("quote") or "").replace(" ", "") for e in _ev(u.get("evidence"))):
            out.append("uci 값이 evidence 의 quote 안에 보이지 않습니다")
    elif not u.get("searched"):
        out.append("uci 를 찾지 못했으면 searched 에 어디를 어떻게 찾아봤는지 적으세요")
    if not (d.get("review") or {}).get("done"):
        out.append("검수를 아직 받지 않았습니다(review.done)")
    return out


def main_check_build(result: str, job: str | None = None) -> int:
    fails = check_build(Path(result), Path(job) if job else None)
    if fails:
        print("걸린 항목:"); [print(" -", f) for f in fails]
        return 1
    print("통과")
    return 0


def check_build_work(result: Path, job: Path | None = None) -> list[str]:
    """작품 단위 MODS 판단(build.json: 공통 + episodes[]) 검사 — 형식과 근거만."""
    result = Path(result)
    job = Path(job) if job else result.with_name("job.json")
    if not result.exists():
        return [f"결과 파일이 없습니다: {result}"]
    try:
        d = json.loads(result.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [f"결과 파일이 JSON 으로 읽히지 않습니다: {e}"]
    j = json.loads(job.read_text(encoding="utf-8")) if job.exists() else {}
    out: list[str] = []
    want = {a.get("name"): a for a in j.get("authors") or []}
    got = {a.get("name"): a for a in d.get("authors") or []}
    for name in want:
        if name not in got:
            out.append(f"저자 '{name}' 의 결정이 없습니다(authors 에 저자마다 한 항목)")
    for name, a in got.items():
        dec = a.get("decision")
        if dec not in ("link", "none"):
            out.append(f"저자 '{name}': decision 은 link 또는 none 이어야 합니다(지금 {dec!r})"); continue
        if not str(a.get("reason") or "").strip():
            out.append(f"저자 '{name}': reason(이유)이 없습니다")
        cands = {c.get("AC_CONTROL_NO") for c in (want.get(name) or {}).get("candidates") or []}
        if dec == "link" and a.get("source") == "staff":
            if not str(a.get("ac_control_no") or "").strip():
                out.append(f"저자 '{name}': 직원 결정(staff)인데 전거 번호가 없습니다")
            continue      # 직원이 정한 연결은 후보·확신 검사를 하지 않는다(2026-10-03 계획 6절)
        if dec == "link":
            if cands and a.get("ac_control_no") not in cands:
                out.append(f"저자 '{name}': ac_control_no {a.get('ac_control_no')!r} 가 전거 검색 후보에 없습니다")
            if a.get("confidence") != "high":
                out.append(f"저자 '{name}': 연결(link)은 confidence 가 high 일 때만 가능합니다")
            if not _ev(a.get("evidence")):
                out.append(f"저자 '{name}': 연결 근거(evidence 의 url+quote)가 없습니다")
        elif cands and not a.get("rejected"):
            out.append(f"저자 '{name}': 후보가 {len(cands)}건 있는데 왜 뺐는지(rejected)가 비어 있습니다")
    subj = d.get("subjects") or []
    fixed = {("topic", "만화[漫畵]", "KSH1998022212"), ("genre", "웹툰[webtoon]", "KSH2016000049")}
    if {(s.get("kind"), s.get("term"), s.get("id")) for s in subj} != fixed or len(subj) != 2:
        out.append("subjects 는 고정 두 묶음(topic 만화[漫畵] KSH1998022212, genre 웹툰[webtoon] KSH2016000049)이어야 합니다")
    want_eps = {e.get("contents_id") for e in j.get("episodes") or []}
    got_eps = {e.get("contents_id"): e for e in d.get("episodes") or []}
    missing = sorted(want_eps - set(got_eps))
    if missing:
        out.append(f"episodes 에 빠진 회차 {len(missing)}건: {', '.join(missing[:5])}{' …' if len(missing) > 5 else ''} (job 의 회차 전부에 하나씩)")
    for cnts, e in got_eps.items():
        u = e.get("uci") or {}
        if str(u.get("value") or "").strip():
            if not _ev(u.get("evidence")):
                out.append(f"{cnts}: uci 값이 있는데 근거(url+quote)가 없습니다")
            elif not any(str(u["value"]).replace(" ", "") in str(x.get("quote") or "").replace(" ", "") for x in _ev(u.get("evidence"))):
                out.append(f"{cnts}: uci 값이 evidence 의 quote 안에 보이지 않습니다")
        elif not u.get("searched"):
            out.append(f"{cnts}: uci 를 찾지 못했으면 searched 에 어디를 어떻게 찾아봤는지 적으세요")
        for alt in e.get("alternative_names") or []:
            if "원문" not in str(alt.get("source") or "") or not str(alt.get("quote") or "").strip():
                out.append(f"{cnts} 다른이름 '{alt.get('name')}': 원문 근거가 없습니다(원문에 있는 경우에만)")
            if alt.get("alt_type") not in ("nickname", "formal name", "no specific type"):
                out.append(f"{cnts} 다른이름 '{alt.get('name')}': alt_type 값이 틀렸습니다")
            if alt.get("author") not in want:
                out.append(f"{cnts} 다른이름 '{alt.get('name')}': author 가 저자 목록에 없습니다")
        if j.get("manuscript") is None and e.get("alternative_names"):
            out.append(f"{cnts}: 원문이 없는데(manuscript null) 다른이름이 들어 있습니다")
    if "adult" not in d:
        out.append("adult(성인물 여부)를 true/false 로 적으세요(근거는 adult_reason)")
    if not (d.get("review") or {}).get("done"):
        out.append("검수를 아직 받지 않았습니다(review.done)")
    return out


def main_check_build_work(result: str, job: str | None = None) -> int:
    fails = check_build_work(Path(result), Path(job) if job else None)
    if fails:
        print("걸린 항목:"); [print(" -", f) for f in fails]
        return 1
    print("통과")
    return 0


def check_dup(result: Path, job: Path | None = None) -> list[str]:
    """복본 판정(dup_build.json) 검사 — 형식과 근거만. 짝 전부에 판정이 있는가, verdict 값, 이유, dup 은 high 인가, unsure 는 to_check 가 있는가, 검수."""
    result = Path(result)
    job = Path(job) if job else result.with_name("job.json")
    if not result.exists():
        return [f"결과 파일이 없습니다: {result}"]
    try:
        d = json.loads(result.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [f"결과 파일이 JSON 으로 읽히지 않습니다: {e}"]
    j = json.loads(job.read_text(encoding="utf-8")) if job.exists() else {}
    out: list[str] = []
    want = {(p.get("our_key"), p.get("cand_key")) for p in j.get("pairs") or []}
    got = {(p.get("our_key"), p.get("cand_key")): p for p in d.get("pairs") or []}
    missing = want - set(got)
    if missing:
        out.append(f"판정이 없는 짝 {len(missing)}개(job 의 짝 전부에 하나씩): 예 {sorted(missing)[:3]}")
    for k, p in got.items():
        v = p.get("verdict")
        if v not in ("dup", "not", "unsure"):
            out.append(f"짝 {k}: verdict 는 dup/not/unsure 중 하나여야 합니다(지금 {v!r})"); continue
        if not str(p.get("reason") or "").strip():
            out.append(f"짝 {k}: reason(이유)이 없습니다")
        if v in ("dup", "not") and p.get("confidence") != "high":
            out.append(f"짝 {k}: {v} 는 confidence 가 high 일 때만 가능합니다. 가리지 못했으면 unsure 로 두세요")
        if v == "not" and str(p.get("to_check") or "").strip():
            out.append(f"짝 {k}: 복본 아님(not)이면서 확인 요청(to_check)을 적었습니다. 가리지 못한 것이면 unsure 로 바꾸세요")
        if v in ("dup", "unsure") and not [e for e in (p.get("evidence") or []) if str(e.get("url") or "").strip()]:
            out.append(f"짝 {k}: {v} 는 어디를 봤는지 evidence 에 주소와 화면 글자를 남겨야 합니다(찾지 못했어도 본 화면의 주소를 적으세요)")
        if v == "unsure" and not str(p.get("to_check") or "").strip():
            out.append(f"짝 {k}: 판단 불가(unsure)면 무엇을 보면 가릴 수 있는지 to_check 에 적으세요")
    if not str(d.get("summary") or "").strip():
        out.append("summary(담당자가 읽을 한 문단)가 없습니다")
    if not (d.get("review") or {}).get("done"):
        out.append("검수를 아직 받지 않았습니다(review.done)")
    return out


def main_check_dup(result: str, job: str | None = None) -> int:
    fails = check_dup(Path(result), Path(job) if job else None)
    if fails:
        print("걸린 항목:"); [print(" -", f) for f in fails]
        return 1
    print("통과")
    return 0
