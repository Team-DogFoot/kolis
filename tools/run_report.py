"""개발용: 에이전트 실행 한 번의 행동 기록(_events.jsonl)을 읽어 보고서(report.md)와 자료(report.json)를 만든다. 판단하지 않고 세기만 한다.
2026-10-04 유저: "한 바퀴 끝까지 돌려보고 에이전트의 행동을 파악해서 고도화의 재료로 쓰자. 로깅이랑 모니터링만 잘해서 정리만 잘해놓자."

실행: .venv-mac/bin/python -X utf8 tools/run_report.py <작업 폴더(jobs/<작업>)> <납품 폴더> [--out <폴더>] [--no-color]
읽는 것: <작업 폴더>/_events.jsonl(실행기가 즉시 덧붙이는 stream-json 이벤트 + 프로그램 기록), observations/*.json, research.json, import.json
만드는 것: <out>/report.md, <out>/report.json (실행 중에도 돌릴 수 있다 — 그때까지의 기록으로)
"""
from __future__ import annotations
import sys, json, re, argparse, time
from collections import Counter, defaultdict
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kolis_tool import coverage  # noqa: E402

IMG = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp")


def k(n) -> str:
    n = int(n or 0)
    return f"{n/1_000_000:.2f}M" if n >= 1_000_000 else f"{n/1000:.0f}k" if n >= 1000 else str(n)


def hms(sec) -> str:
    sec = int(sec or 0)
    return f"{sec//3600}:{sec%3600//60:02d}:{sec%60:02d}" if sec >= 3600 else f"{sec//60}:{sec%60:02d}"


def short(s, n=160) -> str:
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s if len(s) <= n else s[:n] + "…"


def result_text(content) -> tuple[str, int]:
    """도구 결과 → (글, 이미지 수)."""
    if isinstance(content, str):
        return content, 0
    out, imgs = [], 0
    for b in content or []:
        if isinstance(b, dict):
            if b.get("type") == "text":
                out.append(b.get("text") or "")
            elif b.get("type") == "image":
                imgs += 1
    return "\n".join(out), imgs


def kolis_cmd(cmd: str) -> tuple[str, str]:
    """명령 글 → (kolis_tool 하위 명령 이름, 그 뒤 인자). kolis_tool 명령이 아니면 ("", 원문)."""
    m = re.search(r"-m kolis_tool\s+([\w-]+)\s*(.*)", cmd or "", re.S)
    return (m.group(1), m.group(2).strip()) if m else ("", cmd or "")


def load_events(path: Path) -> list[dict]:
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def analyze(job_dir: Path, folder: Path, with_color: bool = True) -> dict:
    events = load_events(job_dir / "_events.jsonl")
    t_first = events[0]["wall"] if events else 0
    calls: dict[str, dict] = {}            # tool_use id → 호출
    order: list[str] = []
    msgs: dict[str, dict] = {}             # message id → {model, parent, usage}
    texts: list[dict] = []                 # 에이전트가 한 말
    program: list[dict] = []
    results: list[dict] = []               # result 이벤트
    limits: list[dict] = []
    inits: list[dict] = []
    notifs: dict[str, dict] = {}
    last_by_parent: dict[str, float] = {}
    for ev in events:
        typ, rel = ev.get("type"), round(ev.get("wall", t_first) - t_first, 1)
        parent = ev.get("parent_tool_use_id") or ""
        if typ == "program":
            program.append({**ev, "rel": rel}); continue
        if typ == "rate_limit_event":
            info = ev.get("rate_limit_info") or {}
            w = info.get("unifiedWindows") or {}
            limits.append({"rel": rel, "status": info.get("status"), "type": info.get("rateLimitType"), "utilization": info.get("utilization"),
                           "five_hour": (w.get("five_hour") or {}).get("utilization"), "seven_day": (w.get("seven_day") or {}).get("utilization")})
            continue
        if typ == "system" and ev.get("subtype") == "task_notification":      # 하위 에이전트는 뒤에서 돈다(Agent 호출의 결과는 "띄웠다"뿐) → 끝은 이 알림으로 안다
            notifs[ev.get("tool_use_id") or ""] = {"rel": rel, "status": ev.get("status"), "summary": ev.get("summary") or "", "usage": ev.get("usage")}
            continue
        if typ in ("assistant", "user") and parent:
            last_by_parent[parent] = rel
        if typ == "system" and ev.get("subtype") == "init":
            inits.append({"rel": rel, "session_id": ev.get("session_id"), "model": ev.get("model"), "tools": len(ev.get("tools") or []),
                          "mcp_servers": [s.get("name") for s in ev.get("mcp_servers") or []], "agents": ev.get("agents"), "skills": ev.get("skills")}); continue
        if typ == "result":
            results.append({"rel": rel, "subtype": ev.get("subtype"), "is_error": ev.get("is_error"), "num_turns": ev.get("num_turns"), "duration_ms": ev.get("duration_ms"),
                            "usage": ev.get("usage"), "modelUsage": ev.get("modelUsage"), "denials": ev.get("permission_denials") or [], "result": ev.get("result")}); continue
        msg = ev.get("message") or {}
        if typ == "assistant":
            mid = msg.get("id") or f"noid-{len(msgs)}"
            u = msg.get("usage") or {}
            msgs[mid] = {"model": msg.get("model") or "", "parent": parent, "rel": rel,
                         "input": int(u.get("input_tokens") or 0), "output": max(int(u.get("output_tokens") or 0), msgs.get(mid, {}).get("output", 0)),
                         "cache_read": int(u.get("cache_read_input_tokens") or 0), "cache_create": int(u.get("cache_creation_input_tokens") or 0)}
            for b in msg.get("content") or []:
                if b.get("type") == "tool_use":
                    cid = b.get("id")
                    calls[cid] = {"id": cid, "name": b.get("name"), "input": b.get("input") or {}, "parent": parent, "rel": rel, "msg": mid}
                    order.append(cid)
                elif b.get("type") == "text" and (b.get("text") or "").strip():
                    texts.append({"rel": rel, "parent": parent, "text": b["text"].strip()})
        elif typ == "user":
            content = msg.get("content")
            if isinstance(content, list):
                for b in content:
                    if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("tool_use_id") in calls:
                        c = calls[b["tool_use_id"]]
                        txt, imgs = result_text(b.get("content"))
                        c.update({"end": rel, "error": bool(b.get("is_error")), "result": txt, "images": imgs})

    # ---- 하위 에이전트(Agent/Task 호출)
    subs = {}
    for cid in order:
        c = calls[cid]
        if c["name"] in ("Agent", "Task"):
            inp = c["input"]
            subs[cid] = {"id": cid, "type": inp.get("subagent_type") or "(기본)", "description": inp.get("description") or "", "prompt": inp.get("prompt") or "",
                         "start": c["rel"], "end": (notifs.get(cid) or {}).get("rel"), "status": (notifs.get(cid) or {}).get("status") or "실행 중", "last_event": last_by_parent.get(cid),
                         "error": c.get("error"), "answer": (notifs.get(cid) or {}).get("summary") or "", "launched_by": c["parent"],
                         "tools": Counter(), "turns": 0, "tokens": {"input": 0, "output": 0, "cache_read": 0, "cache_create": 0}, "models": Counter(),
                         "reads": [], "looks": [], "zooms": 0, "writes": [], "errors": 0}
    for cid in order:
        c = calls[cid]
        s = subs.get(c["parent"])
        if not s:
            continue
        name = c["name"]
        if name in ("Bash", "PowerShell"):
            sub, rest = kolis_cmd(c["input"].get("command") or "")
            name = f"명령:{sub or '기타'}"
            if sub == "look":
                s["looks"].append(rest)
                if "--zoom" in rest:
                    s["zooms"] += 1
        elif name == "Read":
            s["reads"].append(c["input"].get("file_path") or "")
        elif name == "Write":
            s["writes"].append(c["input"].get("file_path") or "")
        s["tools"][name] += 1
        if c.get("error"):
            s["errors"] += 1
    for mid, m in msgs.items():
        s = subs.get(m["parent"])
        if s:
            s["turns"] += 1; s["models"][m["model"]] += 1
            for key in ("input", "output", "cache_read", "cache_create"):
                s["tokens"][key] += m[key]

    for t in texts:
        s = subs.get(t["parent"])
        if s:
            s["last_text"] = t["text"]
    for s in subs.values():
        if s.get("end") is None and s.get("status") == "실행 중" and events and s.get("last_event") is not None and events[-1].get("type") == "program":
            s["status"] = "끝 알림 없음"
    # ---- 토큰: 모델별 · 누가(작품 에이전트 / 하위 종류)별
    tok_model, tok_actor = defaultdict(lambda: Counter()), defaultdict(lambda: Counter())
    for mid, m in msgs.items():
        actor = "작품 에이전트" if not m["parent"] else f"하위:{subs[m['parent']]['type']}" if m["parent"] in subs else "하위:(알 수 없음)"
        for key in ("input", "output", "cache_read", "cache_create"):
            tok_model[m["model"]][key] += m[key]; tok_actor[actor][key] += m[key]
        tok_model[m["model"]]["responses"] += 1; tok_actor[actor]["responses"] += 1

    # ---- 실제로 연 파일
    reads_all = [c["input"].get("file_path") or "" for c in calls.values() if c["name"] == "Read"]
    reads_ok = {c["input"].get("file_path") or "" for c in calls.values() if c["name"] == "Read" and not c.get("error")}

    # ---- 회차별 관찰 범위
    eps = []
    ep_dirs = sorted({p.parent for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in IMG and "섬네일" not in str(p) and "썸네일" not in str(p)})
    obs_dir = job_dir / "observations"
    sub_by_folder = {}
    for s in subs.values():
        if s["type"] == "observe-episode":
            for d in ep_dirs:
                if str(d) in s["prompt"] or d.name in s["prompt"]:
                    sub_by_folder.setdefault(d.name, []).append(s)
    for d in ep_dirs:
        images = sorted(p for p in d.iterdir() if p.suffix.lower() in IMG)
        need = {p.name: coverage.tiles_expected(p) for p in images}
        tiles_total = sum(need.values()); fit_total = sum(1 for v in need.values() if v == 0)
        gaps = coverage.read_gaps(images, reads_ok)
        missing_tiles = sum(len(g["missing"]) for g in gaps if g["missing"] != ["전체"])
        missing_fit = sum(1 for g in gaps if g["missing"] == ["전체"])
        untouched = [g["image"] for g in gaps if g["missing"] == ["전체"] or len(g["missing"]) == need.get(g["image"], 0)]
        ob, ob_err = None, ""
        op = obs_dir / f"{d.name}.json"
        if op.exists():
            try:
                ob = json.loads(op.read_text(encoding="utf-8"))
            except Exception as e:  # noqa: BLE001
                ob_err = f"읽기 실패: {e}"
        else:
            cand = [p for p in obs_dir.glob("*.json")] if obs_dir.exists() else []
            for p in cand:        # 정리 뒤 이름으로 저장했을 수 있다 → folder 값으로 찾는다
                try:
                    o = json.loads(p.read_text(encoding="utf-8"))
                except Exception:  # noqa: BLE001
                    continue
                if d.name in str(o.get("folder") or ""):
                    ob, op = o, p; break
        row = {"folder": d.name, "images": len(images), "tiles": tiles_total, "fit_pages": fit_total, "tiles_missing": missing_tiles, "fit_missing": missing_fit,
               "untouched_images": untouched, "gaps": gaps, "obs_file": op.name if ob is not None else "", "obs_error": ob_err}
        if ob is not None:
            pages = ob.get("pages") or []
            quotes = [t for pg in pages for t in (pg.get("text") or []) if isinstance(t, dict)]
            sm = ob.get("summary") or {}
            row.update({"viewed": len(ob.get("images_viewed") or []), "pages": len(pages), "quotes": len(quotes), "uncertain": sum(1 for t in quotes if t.get("uncertain")),
                        "skipped": [(pg.get("file"), pg.get("skipped_tiles")) for pg in pages if pg.get("skipped_tiles")],
                        "kinds": dict(Counter(str(pg.get("kind")) for pg in pages)), "color": sm.get("color"), "color_reason": sm.get("color_reason"),
                        "gray_pages": sum(1 for pg in pages if pg.get("grayscale_only")), "not_found": ob.get("not_found"),
                        "quotes_on_unread": _quotes_on_unread(pages, gaps), "summary": sm, "page_kind": {str(pg.get("file")): str(pg.get("kind")) for pg in pages}})
        ss = sub_by_folder.get(d.name) or []
        row["agents"] = [{"start": s["start"], "end": s["end"], "seconds": round((s["end"] or 0) - s["start"]) if s["end"] else None, "turns": s["turns"], "reads": len(s["reads"]),
                          "looks": len(s["looks"]), "zooms": s["zooms"], "tokens": s["tokens"], "answer": short(s["answer"], 200), "errors": s["errors"]} for s in ss]
        if with_color:
            ratios = coverage.measure_colors(images, job_dir.parent / f"_colors_{d.name}.json")
            colored = [n for n, r in ratios.items() if r > coverage.COLOR_THRESHOLD]
            row["measured_colored"] = len(colored); row["measured_min"] = min(ratios.values()) if ratios else None
            if ob is not None and row.get("color"):
                row["color_problem"] = coverage.color_claim_problem(row["color"], ratios, row.get("page_kind") or {})
        eps.append(row)

    # ---- 명령 이력
    cmds = []
    for cid in order:
        c = calls[cid]
        if c["name"] in ("Bash", "PowerShell"):
            sub, rest = kolis_cmd(c["input"].get("command") or "")
            cmds.append({"rel": c["rel"], "end": c.get("end"), "who": _who(c, subs), "cmd": sub or "기타", "args": rest, "error": c.get("error"), "result": c.get("result") or ""})
    web = [{"rel": c["rel"], "who": _who(c, subs), "tool": c["name"], "what": c["input"].get("query") or c["input"].get("url") or "", "error": c.get("error"),
            "size": len(c.get("result") or "")} for c in (calls[i] for i in order) if c["name"] in ("WebSearch", "WebFetch")]
    errors = [{"rel": c["rel"], "who": _who(c, subs), "tool": c["name"], "input": short(json.dumps(c["input"], ensure_ascii=False), 240), "result": short(c.get("result"), 400)}
              for c in (calls[i] for i in order) if c.get("error")]
    unfinished = [{"rel": c["rel"], "who": _who(c, subs), "tool": c["name"], "input": short(json.dumps(c["input"], ensure_ascii=False), 200)} for c in (calls[i] for i in order) if "end" not in c]
    tool_count = defaultdict(Counter)
    for c in calls.values():
        name = c["name"]
        if name in ("Bash", "PowerShell"):
            name = "명령:" + (kolis_cmd(c["input"].get("command") or "")[0] or "기타")
        tool_count[_who(c, subs)][name] += 1
    docs_read = Counter()
    for p in reads_all:
        if any(x in p for x in ("/knowledge/", "/.claude/", "/docs/", "CLAUDE.md")) and not p.lower().endswith(IMG):
            docs_read[p] += 1
    files_written = [{"rel": c["rel"], "who": _who(c, subs), "tool": c["name"], "path": c["input"].get("file_path") or ""} for c in (calls[i] for i in order) if c["name"] in ("Write", "Edit")]

    out = {"job_dir": str(job_dir), "folder": str(folder), "made": time.strftime("%Y-%m-%d %H:%M:%S"), "events": len(events),
           "span_seconds": round(events[-1]["wall"] - t_first) if events else 0, "started": events[0]["ts"] if events else "", "last": events[-1]["ts"] if events else "",
           "program": program, "inits": inits, "results": results, "limits": limits,
           "tokens_by_model": {m: dict(v) for m, v in tok_model.items()}, "tokens_by_actor": {a: dict(v) for a, v in tok_actor.items()},
           "subagents": [{**{kk: vv for kk, vv in s.items() if kk not in ("tools", "models")}, "tools": dict(s["tools"]), "models": dict(s["models"])} for s in subs.values()],
           "episodes": eps, "commands": cmds, "web": web, "errors": errors, "unfinished": unfinished,
           "tool_count": {a: dict(v) for a, v in tool_count.items()}, "docs_read": dict(docs_read), "files_written": files_written,
           "texts": texts, "calls": len(calls), "responses": len(msgs)}
    return out


def _who(c: dict, subs: dict) -> str:
    if not c["parent"]:
        return "작품 에이전트"
    s = subs.get(c["parent"])
    return f"하위:{s['type']}" if s else "하위"


def _quotes_on_unread(pages: list, gaps: list) -> int:
    """한 조각도 열지 않은 장인데 관찰 파일에 글자가 적혀 있는 수(= 보지 않고 적은 글자)."""
    never = {g["image"] for g in gaps if g["missing"] == ["전체"] or g["need"].startswith("조각") and len(g["missing"]) == int(re.search(r"\d+", g["need"]).group())}
    return sum(len(pg.get("text") or []) for pg in pages if str(pg.get("file")) in never)


# ---------------------------------------------------------------- 글로
def render(a: dict) -> str:
    L: list[str] = []
    w = L.append
    w(f"# 에이전트 실행 행동 기록 — {Path(a['folder']).name}")
    w("")
    w(f"만든 시각 {a['made']} · 기록 {a['events']}건 · 시작 {a['started']} · 마지막 기록 {a['last']} · 걸린 시간 {hms(a['span_seconds'])}")
    w(f"작업 폴더 `{a['job_dir']}` · 납품 폴더 `{a['folder']}`")
    w("")
    w("이 문서는 세기만 한 것이다(판단 없음). 숫자는 전부 `_events.jsonl`(실행기가 즉시 덧붙인 기록)과 관찰 파일에서 나왔다.")
    w("")
    # 1 프로그램 기록
    w("## 1. 프로그램이 한 일(실행 시작·끝·검사)")
    w("")
    w("| 경과 | 무엇 | 내용 |"); w("|---|---|---|")
    for p in a["program"]:
        what = p.get("what")
        if what == "job_start":
            body = f"스킬 {p.get('skill')} · 이미지 {(p.get('job') or {}).get('image_count')}장"
        elif what == "run_start":
            body = f"모델 {p.get('model')} · 제한 {p.get('timeout')}초 · " + ("이어서(같은 대화)" if p.get("resume") else "새 대화") + f" · 넘긴 말: {short(p.get('prompt'), 200)}"
        elif what == "run_end":
            body = f"종료 코드 {p.get('returncode')} · {hms(p.get('seconds'))} · 제한 시간 초과 {'예' if p.get('timed_out') else '아니오'} · 거부된 도구 {p.get('denied')}건" + (f" · 오류 끝부분: {short(p.get('stderr_tail'), 200)}" if p.get("stderr_tail") else "")
        elif what == "program_check":
            fails = p.get("fails") or []
            body = f"{p.get('round')}회차 검사 · 걸린 항목 {len(fails)}건" + ("".join(f"<br>- {short(f, 300)}" for f in fails))
        elif what == "job_end":
            body = f"남은 항목 {len(p.get('remaining') or [])}건 · 턴 {p.get('turns')}"
        else:
            body = short(json.dumps(p, ensure_ascii=False), 200)
        w(f"| {hms(p['rel'])} | {what} | {body} |")
    w("")
    for i, r in enumerate(a["results"], 1):
        w(f"- 대화 {i} 끝({hms(r['rel'])}): {r.get('subtype')} · 턴 {r.get('num_turns')} · 거부 {len(r.get('denials') or [])}건")
        for d in r.get("denials") or []:
            w(f"  - 거부된 호출: {short(json.dumps(d, ensure_ascii=False), 300)}")
    w("")
    # 2 토큰
    w("## 2. 토큰(응답 번호로 중복을 없애고 합산. 금액은 적지 않는다)")
    w("")
    w("| 모델 | 응답 수 | 입력 | 출력 | 캐시 읽기 | 캐시 생성 |"); w("|---|---:|---:|---:|---:|---:|")
    for m, v in sorted(a["tokens_by_model"].items()):
        w(f"| {m} | {v.get('responses', 0)} | {k(v.get('input'))} | {k(v.get('output'))} | {k(v.get('cache_read'))} | {k(v.get('cache_create'))} |")
    w("")
    w("| 누가 | 응답 수 | 입력 | 출력 | 캐시 읽기 | 캐시 생성 |"); w("|---|---:|---:|---:|---:|---:|")
    for m, v in sorted(a["tokens_by_actor"].items()):
        w(f"| {m} | {v.get('responses', 0)} | {k(v.get('input'))} | {k(v.get('output'))} | {k(v.get('cache_read'))} | {k(v.get('cache_create'))} |")
    w("")
    if a["results"]:
        w("실행기가 받은 합계(대화가 끝날 때 `claude -p` 가 알려 준 값):")
        for i, r in enumerate(a["results"], 1):
            for model, mu in (r.get("modelUsage") or {}).items():
                w(f"- 대화 {i} · {model}: 입력 {k(mu.get('inputTokens'))} · 출력 {k(mu.get('outputTokens'))} · 캐시 읽기 {k(mu.get('cacheReadInputTokens'))} · 캐시 생성 {k(mu.get('cacheCreationInputTokens'))}")
        w("")
    if a["limits"]:
        f, l = a["limits"][0], a["limits"][-1]
        w(f"사용 한도 알림(구독): 처음 {hms(f['rel'])} 5시간 창 {f.get('five_hour')} · 7일 창 {f.get('seven_day')} → 마지막 {hms(l['rel'])} 5시간 창 {l.get('five_hour')} · 7일 창 {l.get('seven_day')} (상태 {l.get('status')}, 알림 {len(a['limits'])}건)")
        w("")
    # 3 도구 사용
    w("## 3. 도구 호출 수")
    w("")
    names = sorted({n for v in a["tool_count"].values() for n in v})
    w("| 누가 | " + " | ".join(names) + " | 합 |"); w("|---|" + "---:|" * (len(names) + 1))
    for who, v in sorted(a["tool_count"].items()):
        w(f"| {who} | " + " | ".join(str(v.get(n, "")) for n in names) + f" | {sum(v.values())} |")
    w("")
    # 4 하위 에이전트
    w("## 4. 하위 에이전트(띄운 순서)")
    w("")
    w("| # | 종류 | 시작 | 걸린 시간 | 응답 수 | Read | look | 확대 | 오류 | 출력 | 캐시 읽기 | 캐시 생성 | 마지막 답 |"); w("|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for i, s in enumerate(a["subagents"], 1):
        dur = hms(s["end"] - s["start"]) if s.get("end") is not None else f"{s.get('status')}"
        t = s["tokens"]
        w(f"| {i} | {s['type']} {short(s['description'], 24)} | {hms(s['start'])} | {dur} | {s['turns']} | {len(s['reads'])} | {len(s['looks'])} | {s['zooms']} | {s['errors']} | {k(t['output'])} | {k(t['cache_read'])} | {k(t['cache_create'])} | {short(s.get('last_text') or s['answer'], 110)} |")
    w("")
    # 5 관찰 범위
    eps = a["episodes"]
    w("## 5. 회차별 관찰 범위(실제로 연 기록과 대조)")
    w("")
    tt, tm = sum(e["tiles"] for e in eps), sum(e["tiles_missing"] for e in eps)
    ft, fm = sum(e["fit_pages"] for e in eps), sum(e["fit_missing"] for e in eps)
    w(f"회차 {len(eps)}개 · 이미지 {sum(e['images'] for e in eps)}장 · 조각 {tt}개 중 열지 않은 것 {tm}개({(tm / tt * 100 if tt else 0):.1f}%) · 조각이 필요 없는 장 {ft}장 중 열지 않은 것 {fm}장 · 관찰 파일 {sum(1 for e in eps if e.get('obs_file'))}개")
    w("")
    w("| 회차 폴더 | 이미지 | 조각 | 안 연 조각 | 한 조각도 안 연 장 | 관찰 파일의 본 장 | 적은 글자 | 불확실 | 안 본 장에 적은 글자 | 색(관찰) | 색 있는 장(측정) | 색 어긋남 | 관찰 걸린 시간 | 응답 수 | 확대 |")
    w("|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---:|---:|---:|")
    for e in eps:
        ag = e.get("agents") or []
        dur = "+".join(hms(x["seconds"]) if x.get("seconds") is not None else "미완" for x in ag) or "-"
        w(f"| {e['folder']} | {e['images']} | {e['tiles']} | {e['tiles_missing']} | {len(e['untouched_images'])} | {e.get('viewed', '-')} | {e.get('quotes', '-')} | {e.get('uncertain', '-')} | {e.get('quotes_on_unread', '-')} | "
          f"{e.get('color') or '-'} | {e.get('measured_colored', '-')} | {'어긋남' if e.get('color_problem') else ''} | {dur} | {'+'.join(str(x['turns']) for x in ag) or '-'} | {'+'.join(str(x['zooms']) for x in ag) or '-'} |")
    w("")
    bad = [e for e in eps if e.get("skipped")]
    if bad:
        w("관찰 파일이 스스로 건너뛰었다고 적은 조각:")
        for e in bad:
            w(f"- {e['folder']}: {e['skipped']}")
        w("")
    cp = [e for e in eps if e.get("color_problem")]
    if cp:
        w("색이 측정과 어긋난 회차:")
        for e in cp:
            w(f"- {e['folder']}: {e['color_problem']} / 관찰의 이유: {short(e.get('color_reason'), 200)}")
        w("")
    # 6 글자 읽기 일관성
    w("## 6. 회차마다 읽은 글자의 갈래(같은 글자를 회차마다 어떻게 읽었나)")
    w("")
    for key, title in (("title_as_seen", "제목"), ("authors_as_seen", "저자"), ("producers_as_seen", "제작처·발행처"), ("part_as_seen", "권차"), ("age_mark_as_seen", "연령 표시"),
                       ("isbn_as_seen", "ISBN"), ("date_as_seen", "발행일"), ("alt_names_as_seen", "다른 이름"), ("edition_as_seen", "판 표시"), ("awards_as_seen", "수상")):
        c = Counter(); eps_with = 0
        for e in eps:
            items = (e.get("summary") or {}).get(key) or []
            if items:
                eps_with += 1
            seen = set()
            for it in items if isinstance(items, list) else [items]:
                v = (f"{it.get('name', '')} / {it.get('role', '')}".strip(" /") if "name" in it else str(it.get("quote") or "")) if isinstance(it, dict) else str(it)
                if v and v not in seen:
                    seen.add(v); c[v] += 1
        if not c:
            w(f"- **{title}**: 어느 회차에도 없음"); continue
        w(f"- **{title}** ({eps_with}개 회차에 있음, 갈래 {len(c)}개): " + " · ".join(f"`{v}` ×{n}" for v, n in c.most_common(40)))
    w("")
    # 7 명령 이력
    w("## 7. 검사 명령 이력(에이전트가 스스로 돌린 검사와 그 결과 전문)")
    w("")
    for c in a["commands"]:
        if c["cmd"] in ("write-import", "check-research", "check-findings", "check-dup"):
            w(f"### {hms(c['rel'])} · {c['who']} · `{c['cmd']}`" + (" · 오류" if c["error"] else ""))
            w("")
            w("```"); w((c["result"] or "(결과 없음)").strip()[:6000]); w("```")
            w("")
    w("## 8. 그 밖의 명령(조회·페이지 열기)")
    w("")
    w("| 경과 | 누가 | 명령 | 인자 | 결과 크기 | 오류 | 결과 앞부분 |"); w("|---|---|---|---|---:|---|---|")
    for c in a["commands"]:
        if c["cmd"] in ("render", "authority", "기타"):
            w(f"| {hms(c['rel'])} | {c['who']} | {c['cmd']} | {short(c['args'], 150)} | {len(c['result'])} | {'오류' if c['error'] else ''} | {short(c['result'], 140)} |")
    w("")
    if a["web"]:
        w("| 경과 | 누가 | 도구 | 무엇 | 결과 크기 | 오류 |"); w("|---|---|---|---|---:|---|")
        for x in a["web"]:
            w(f"| {hms(x['rel'])} | {x['who']} | {x['tool']} | {short(x['what'], 170)} | {x['size']} | {'오류' if x['error'] else ''} |")
        w("")
    # 9 오류
    w(f"## 9. 오류로 끝난 도구 호출 {len(a['errors'])}건")
    w("")
    for x in a["errors"]:
        w(f"- {hms(x['rel'])} · {x['who']} · {x['tool']} · 입력 {x['input']} → {x['result']}")
    w("")
    if a["unfinished"]:
        w(f"결과가 기록되지 않은 호출 {len(a['unfinished'])}건(실행 중이거나 끊긴 것):")
        for x in a["unfinished"][:60]:
            w(f"- {hms(x['rel'])} · {x['who']} · {x['tool']} · {x['input']}")
        w("")
    # 10 문서 열람
    w("## 10. 에이전트가 연 지침·지식 파일")
    w("")
    for p, n in sorted(a["docs_read"].items()):
        w(f"- {p} ×{n}")
    w("")
    w("## 11. 에이전트가 쓴 파일(관찰 파일 제외)")
    w("")
    for x in a["files_written"]:
        if "/observations/" not in x["path"]:
            w(f"- {hms(x['rel'])} · {x['who']} · {x['tool']} · {x['path']}")
    w("")
    # 12 말
    w("## 12. 작품 에이전트가 한 말 전문(시간순)")
    w("")
    for t in a["texts"]:
        if not t["parent"]:
            w(f"**{hms(t['rel'])}** {t['text']}")
            w("")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("job_dir"); ap.add_argument("folder"); ap.add_argument("--out", default=""); ap.add_argument("--no-color", action="store_true")
    ns = ap.parse_args()
    job_dir, folder = Path(ns.job_dir), Path(ns.folder)
    out = Path(ns.out) if ns.out else job_dir
    out.mkdir(parents=True, exist_ok=True)
    a = analyze(job_dir, folder, with_color=not ns.no_color)
    (out / "report.json").write_text(json.dumps(a, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "report.md").write_text(render(a), encoding="utf-8")
    eps = a["episodes"]
    tt, tm = sum(e["tiles"] for e in eps), sum(e["tiles_missing"] for e in eps)
    print(f"기록 {a['events']}건 · {hms(a['span_seconds'])} · 도구 호출 {a['calls']} · 하위 에이전트 {len(a['subagents'])} · 관찰 파일 {sum(1 for e in eps if e.get('obs_file'))}/{len(eps)} · 조각 {tt}개 중 안 연 것 {tm}개 · 오류 {len(a['errors'])}건")
    print(out / "report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
