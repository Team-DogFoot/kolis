"""헤드리스 클로드(`claude -p`) 공통 실행기. 읽기·조사·판단은 에이전트가, 형태가 정해진 쓰기·검증은 코드가 한다(유저 확정 2026-09-29).

- run(prompt, tools, ...) : stream-json 으로 돌리며 도구 사용(검색어·읽는 주소·파일)을 실시간 로그로 보내고 마지막 답변 글을 돌려준다.
- extract_json(text)      : 답변 마지막의 ```json 코드블록을 꺼낸다.
- render_tool()           : 자바스크립트로 그려지는 페이지를 에이전트가 읽게 하는 명령(`python -m kolis_tool render`)과 그 허용 규칙.

에이전트는 KOLIS 에 접근하지 않는다: 계정 환경변수를 넘기지 않고, render 명령은 KOLIS 주소를 거부한다.
작업 폴더는 저장소 밖(`%LOCALAPPDATA%\\kolis_tool\\agent`)이라 저장소의 CLAUDE.md 를 읽지 않는다(agent_dir 참조).
"""
from __future__ import annotations
import json, os, re, shutil, subprocess, sys, threading, time
from pathlib import Path

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)   # 창 없는 실행(pythonw)에서 콘솔이 튀어나오지 않게
REPO = Path(__file__).resolve().parent.parent
SECRET_ENV = ("KOLIS_ID", "KOLIS_PW", "KOLIS_SYSTEM_ID", "KOLIS_SYSTEM_PW")
TRANSIENT = ("overloaded", "rate limit", "429", "econnreset", "etimedout", "fetch failed", "503", "529")


class Cancelled(Exception):
    pass


def claude_exe() -> str | None:
    return shutil.which("claude") or shutil.which("claude.cmd") or shutil.which("claude.exe")


def friendly_error(stderr: str, returncode: int) -> str:
    s = (stderr or "").lower()
    if "not logged in" in s or "login" in s or "authentication" in s or "unauthorized" in s or "401" in s:
        return "클로드코드에 로그인이 되어 있지 않습니다. 터미널에서 `claude` 를 한 번 실행해 로그인한 뒤 다시 시도하세요."
    if "enotfound" in s or "econnrefused" in s or "fetch failed" in s or "network" in s or "certificate" in s:
        return "네트워크 또는 인증서 문제로 클로드가 외부에 접속하지 못했습니다(보안 에이전트 확인). 원문: " + stderr[-300:]
    if "rate limit" in s or "overloaded" in s or "429" in s:
        return "클로드 사용량 한도에 걸렸습니다. 잠시 뒤 다시 시도하세요."
    return f"클로드 실행 실패(코드 {returncode}): {stderr[-400:]}"


def agent_dir() -> Path:
    """에이전트 작업 폴더. 반드시 저장소 **밖**이어야 한다: 클로드코드는 작업 폴더와 그 상위 폴더의 CLAUDE.md 를 읽으므로,
    저장소 안(work/agent)에 두면 프로젝트 지침(세션 시작 시 문서 읽기 등)을 따라 하느라 시간과 토큰을 쓴다(2026-09-29 확인)."""
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "kolis_tool" / "agent"
    base.mkdir(parents=True, exist_ok=True)
    for p in base.parents:
        if (p / "CLAUDE.md").exists():
            raise SystemExit(f"에이전트 작업 폴더의 상위에 CLAUDE.md 가 있습니다: {p}")
    return base


HOME_SRC = Path(__file__).resolve().parent / "agent_home"       # 저장소 안의 원본(지침·스킬·검수 에이전트·지식)
RULE_SOURCES = [REPO / "docs" / "rulebook", REPO / "docs" / "source" / "text"]   # 도서관 매뉴얼 원문(계정 정보 제외본). text/ 는 tools/build_rules.py 가 만든다
RULE_IMAGES = REPO / "docs" / "source" / "images"                                   # 원문의 그림(text/*.md 가 ../images/… 로 링크)


_DEPLOY_LOCK = threading.Lock()


def deploy(log=None) -> Path:
    with _DEPLOY_LOCK:
        return _deploy(log)


def _deploy(log=None) -> Path:
    """에이전트 작업 공간을 작업 폴더에 펼친다. 지침·스킬·검수 에이전트는 매번 원본으로 덮어쓰고(명령 경로를 이 PC 값으로 채움),
    지식(knowledge/*.md)은 작업 폴더의 것이 살아 있는 기록이므로 없을 때만 원본을 복사한다. 끝난 뒤 collect_knowledge 로 저장소에 되가져온다."""
    home = agent_dir()
    py = python_exe()
    for src in HOME_SRC.rglob("*"):
        if src.is_dir():
            continue
        rel = src.relative_to(HOME_SRC)
        dst = home / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if rel.parts[0] == "knowledge":
            if not dst.exists():
                shutil.copy(src, dst)
            continue
        dst.write_text(src.read_text(encoding="utf-8").replace("{PY}", py), encoding="utf-8")
    rules = home / "knowledge" / "rules"
    rules.mkdir(parents=True, exist_ok=True)
    srcs = [f for d in RULE_SOURCES for f in (d.glob("*") if d.exists() else []) if f.suffix.lower() in (".md", ".txt") and "참고자료" not in f.name]
    names = {f.name for f in srcs}
    for old in rules.glob("*"):          # 원본에서 빠진(대체된) 규칙 파일만 지운다. 전부 지웠다 다시 쓰면 동시에 도는 다른 작품의 에이전트가 빈 순간을 본다(2026-10-03 사고)
        if old.is_file() and old.name not in names:
            old.unlink()
    for f in srcs:
        dst = rules / f.name
        if not dst.exists() or dst.read_bytes() != f.read_bytes():
            tmp = dst.with_suffix(dst.suffix + ".tmp"); shutil.copy(f, tmp); tmp.replace(dst)     # 통째로 바꿔 끼움(읽는 쪽이 반쪽 파일을 보지 않게)
    if RULE_IMAGES.exists():   # 그림은 바뀐 것만 복사(knowledge/images/<문서>/…, md 의 ../images 링크와 맞는 위치)
        for f in RULE_IMAGES.rglob("*"):
            if f.is_file():
                dst = home / "knowledge" / "images" / f.relative_to(RULE_IMAGES)
                if not dst.exists() or dst.stat().st_size != f.stat().st_size:
                    dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy(f, dst)
    (home / "jobs").mkdir(exist_ok=True)
    return home


def collect_knowledge(log=None) -> list[str]:
    """에이전트가 덧붙인 지식을 저장소 원본으로 되가져온다(버전 관리 대상). 바뀐 파일 이름을 돌려준다."""
    home, changed = agent_dir(), []
    for f in (home / "knowledge").glob("*.md"):
        dst = HOME_SRC / "knowledge" / f.name
        new = f.read_text(encoding="utf-8")
        if not dst.exists() or dst.read_text(encoding="utf-8") != new:
            dst.write_text(new, encoding="utf-8"); changed.append(f.name)
    if changed and log:
        log(f"  에이전트가 지식 기록을 고침: {', '.join(changed)}")
    return changed


def job_tools() -> list[str]:
    """작업 공간에서 일하는 에이전트에게 허용하는 도구. 명령은 페이지 읽기와 자기 검사 두 가지뿐."""
    py = python_exe()
    cmds = [f"{py} -m kolis_tool render", f"{py} -m kolis_tool check-research", f"{py} -m kolis_tool write-import", f"{py} -m kolis_tool check-build", f"{py} -m kolis_tool check-build-work", f"{py} -m kolis_tool check-dup", f"{py} -m kolis_tool authority"]
    rules = [f"{shell}({c}:*)" for c in cmds for shell in ("Bash", "PowerShell")]
    return ["Read", "Write", "Edit", "Glob", "Grep", "WebSearch", "WebFetch", "Agent", "Task", "Skill", *rules]


def run_job(skill: str, name: str, job: dict, result_name: str, check, log=None, handle: dict | None = None,
            add_dirs: list[Path] | None = None, model: str | None = None, timeout: int = 2400, max_resume: int = 3) -> tuple[dict, list[str], Path]:
    """작품 하나의 일을 에이전트에게 맡긴다. 에이전트가 작업 공간 안에서 스스로 돌며(일 → 저장 → 검사 → 고침 → 검수) 끝낸다.
    끝난 뒤 프로그램이 같은 검사를 돌려, 걸리면 **같은 대화를 이어서**(--resume) 걸린 내용을 알려 준다. 새로 시작하지 않는다.
    돌려주는 것: (결과, 끝까지 남은 걸린 항목, 작업 폴더)."""
    log = log or (lambda m: None)
    handle = handle if handle is not None else {}
    home = deploy(log)
    jd = home / "jobs" / re.sub(r"[^\w가-힣-]+", "", name)
    jd.mkdir(parents=True, exist_ok=True)
    result = jd / result_name
    if result.exists():
        result.unlink()
    (jd / "job.json").write_text(json.dumps(job, ensure_ascii=False, indent=1), encoding="utf-8")
    rel = jd.relative_to(home).as_posix()
    prompt = f"/{skill} {rel}/job.json\n\n맡은 일: `{rel}/job.json`. 결과는 `{rel}/{result_name}` 에 저장하세요. 스킬의 순서대로 검사와 검수까지 끝내세요."
    run(prompt, job_tools(), log, handle, add_dirs, model, timeout, label="에이전트")
    fails = check(result)
    for i in range(1, max_resume + 1):
        if not fails or not handle.get("session_id"):
            break
        log(f"  검사에 걸린 항목 {len(fails)}건 — 같은 대화를 이어서 알려 줌({i}/{max_resume}): " + "; ".join(fails)[:300])
        msg = ("프로그램이 결과 파일을 검사했더니 아래 항목이 걸렸습니다. 이어서 처리하고, 검사 명령으로 통과를 확인한 뒤 끝내세요.\n"
               + "\n".join(f"- {f}" for f in fails))
        run(msg, job_tools(), log, handle, add_dirs, model, timeout, label="에이전트", resume=handle["session_id"])
        fails = check(result)
    collect_knowledge(log)
    if not result.exists():
        raise SystemExit(f"에이전트가 결과 파일을 만들지 못했습니다: {result}")
    return json.loads(result.read_text(encoding="utf-8")), fails, jd


def python_exe() -> str:
    """render 명령을 돌릴 파이썬. pythonw 로 떠 있어도 콘솔용 python 을 쓴다(출력을 읽어야 하므로)."""
    p = Path(sys.executable)
    if p.name.lower() == "pythonw.exe" and (p.parent / "python.exe").exists():
        p = p.parent / "python.exe"
    return p.as_posix()


def render_tool() -> tuple[str, list[str]]:
    """(에이전트에게 알려 줄 명령 앞부분, 허용 규칙 목록). 경로에 공백이 없어야 따옴표 없이 규칙과 맞는다."""
    cmd = f"{python_exe()} -m kolis_tool render"
    return cmd, [f"Bash({cmd}:*)", f"PowerShell({cmd}:*)"]


def _describe(name: str, inp: dict) -> str:
    what = inp.get("query") or inp.get("url") or inp.get("file_path") or inp.get("command") or inp.get("pattern") or ""
    what = what or inp.get("description") or inp.get("skill") or ""
    label = {"WebSearch": "검색", "WebFetch": "페이지 읽기", "Read": "파일 보기", "Bash": "명령", "PowerShell": "명령",
             "Glob": "파일 찾기", "Grep": "내용 찾기", "Write": "파일 쓰기", "Edit": "파일 고치기", "Agent": "검수 맡김", "Task": "검수 맡김",
             "Skill": "스킬 읽기"}.get(name, name)
    what = re.sub(r"^.*-m kolis_tool ", "", str(what))      # 명령은 뒷부분(무엇을 하는지)만 보여 준다
    return f"{label}: {what[:110]}"


def run(prompt: str, tools: list[str], log=None, handle: dict | None = None, add_dirs: list[Path] | None = None,
        model: str | None = None, timeout: int = 1200, label: str = "클로드", _retried: bool = False, resume: str | None = None) -> str:
    """claude -p 를 돌리고 마지막 답변 글을 돌려준다. handle['proc'] 에 프로세스를 두어 취소 가능.
    handle['session_id'] 에 대화 번호를 남긴다. resume 에 그 번호를 주면 같은 대화를 이어 간다(앞에서 본 것을 기억한 채로)."""
    log = log or (lambda m: None)
    exe = claude_exe()
    if not exe:
        raise SystemExit("클로드코드(claude)가 설치되어 있지 않거나 PATH 에 없습니다.")
    cwd = agent_dir()
    cmd = [exe, "-p", "--verbose", "--output-format", "stream-json", "--model", model or os.environ.get("KOLIS_AGENT_MODEL", "sonnet")]
    if resume:
        cmd += ["--resume", resume]
    if tools:
        cmd += ["--allowedTools", *tools]
    for d in add_dirs or []:
        cmd += ["--add-dir", str(d)]
    env = {k: v for k, v in os.environ.items() if k not in SECRET_ENV}
    env["PYTHONPATH"] = str(REPO) + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
                            errors="replace", creationflags=NO_WINDOW, cwd=str(cwd), env=env)
    if handle is not None:
        handle["proc"] = proc
    killer = threading.Timer(timeout, proc.kill)
    killer.daemon = True
    killer.start()
    proc.stdin.write(prompt); proc.stdin.close()
    err_buf: list[str] = []
    threading.Thread(target=lambda: err_buf.append(proc.stderr.read()), daemon=True).start()
    text, t0, denied = "", time.time(), 0
    for line in proc.stdout:
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("session_id") and handle is not None:
            handle["session_id"] = ev["session_id"]
        who = "검수" if ev.get("parent_tool_use_id") else label      # 하위 에이전트(검수)가 한 일은 구분해서 보여 준다
        if ev.get("type") == "assistant":
            for b in (ev.get("message") or {}).get("content", []):
                if b.get("type") == "tool_use":
                    log(f"  [{int(time.time() - t0)}s] {who} › {_describe(b.get('name', ''), b.get('input') or {})}")
                elif b.get("type") == "text" and b.get("text", "").strip():
                    log(f"  [{int(time.time() - t0)}s] {who}: {b['text'].strip()[:160]}")
        elif ev.get("type") == "result":
            text = ev.get("result") or ""
            denied = len(ev.get("permission_denials") or [])
            if handle is not None:
                handle["turns"] = handle.get("turns", 0) + int(ev.get("num_turns") or 0)
    rc = proc.wait()
    killer.cancel()
    if handle is not None and handle.get("cancel"):
        raise Cancelled("사용자가 중단함")
    if denied:
        log(f"  허용되지 않아 거부된 도구 호출 {denied}건")
    if rc != 0:
        err = "".join(err_buf)
        if time.time() - t0 >= timeout:
            raise SystemExit(f"{label}: 제한 시간 {timeout}초를 넘겨 중단했습니다.")
        if any(k in err.lower() for k in TRANSIENT) and not _retried:
            log(f"  일시적 오류로 보여 30초 뒤 1회 재시도: {err[-120:]}")
            time.sleep(30)
            return run(prompt, tools, log, handle, add_dirs, model, timeout, label, True, resume)
        raise SystemExit(friendly_error(err, rc))
    log(f"  {label} 완료 ({int(time.time() - t0)}초)")
    return text


def extract_json(text: str, raw_path: Path | None = None) -> dict:
    m = re.findall(r"```json\s*(\{.*?\})\s*```", text, re.S)
    if m:
        try:
            return json.loads(m[-1])
        except json.JSONDecodeError:
            pass
    if raw_path is not None:
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(text, encoding="utf-8")
        raise SystemExit(f"클로드 답변에서 JSON 을 읽지 못했습니다 → {raw_path} 확인")
    raise SystemExit("클로드 답변에서 JSON 을 읽지 못했습니다")
