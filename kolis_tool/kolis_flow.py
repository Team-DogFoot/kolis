"""반입용 엑셀 확인(사람) 뒤의 KOLIS 등록을 처음부터 끝까지 한 번에: 일괄반입 → 콘텐츠ID 받기 → 폴더명 CNTS → 원문일괄등록 → (썸네일) →
등록대상처리 → 가원부번호 → 가원부 파일.

방식(mode)
- request: 요청 방식을 먼저 쓴다. 요청이 **KOLIS 로 나가지 않은 경우에만** 같은 단계를 화면 방식으로 바꿔 진행한다.
  요청이 나간 뒤의 실패는 KOLIS 에 반영됐을 수 있으므로 바꿔서 다시 하지 않고 멈춘다.
- screen: 전부 화면 방식(Edge 화면을 눌러서).
원문일괄등록은 파일을 업로더(설치형 부품)가 보내므로 어느 방식이든 팝업에서 한다. 폴더 올리기와 전송 시작은 마우스 없이 스크립트로 한다.

지키는 것
- 단계가 끝날 때마다 상태를 저장한다. 멈췄다가 다시 실행하면 끝난 단계는 건너뛴다.
- **반입은 두 번 하지 않는다.** 보내기 직전에 "보냈다"를 먼저 저장한다. 결과를 확인하지 못한 채 멈췄으면 다시 실행해도 반입하지 않는다.
- 단계마다 실행 전 조건을 확인하고(check), 끝난 뒤 KOLIS 의 값을 다시 읽어 맞춰 본다. 하나라도 다르면 그 자리에서 멈춘다.
- 썸네일: 납품에 동봉돼 있으면 등록하고, 없으면 하지 않는다.
- 전부 기록한다(journal): 조건과 그 값, 단계의 시작·끝·시간, 화면 로그, 보낸 요청과 받은 응답, 멈춘 이유.
"""
from __future__ import annotations
import datetime, json, re, time
from pathlib import Path

STEPS = [("import", "일괄반입"), ("export", "콘텐츠ID 받기"), ("cnts", "원고 폴더명 → 콘텐츠ID"), ("upload", "원문일괄등록"),
         ("thumbs", "썸네일 등록"), ("register", "등록대상처리 → 가원부번호 → 가원부 파일")]


class Stop(RuntimeError):
    pass


def _receipt_from_record(since_ms: float) -> str:
    """방금 반입의 응답에 들어 있는 접수번호(화면 방식일 때 요청 기록에서 읽음)."""
    from . import ie_dom
    r = ie_dom.recorder()
    p = r.dir / "requests.jsonl" if r else None
    if not p or not p.exists():
        return ""
    found = ""
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if d.get("kind") == "xhr" and str(d.get("url", "")).split("?")[0].endswith("/fileUpload.do") and float(d.get("t") or 0) >= since_ms:
            try:
                found = str(json.loads(d.get("response") or "{}").get("receiptno") or "") or found
            except json.JSONDecodeError:
                pass
    return found


def _receipt_from_screen() -> str:
    try:
        from . import kolis_register
        v = str(kolis_register._field(kolis_register._doc("onlineDepstRecet.do"), "receipt_no").value or "").strip()
        return v if v.isdigit() else ""
    except Exception:  # noqa: BLE001
        return ""


def _folders(root: Path) -> list[Path]:
    return [p for p in Path(root).iterdir() if p.is_dir() and not p.name.startswith("_kolis")]


def _excel_rows(xlsx: Path) -> dict:
    """반입용 엑셀의 데이터 행 수와 본표제(반입 뒤 KOLIS 목록과 맞춰 볼 값)."""
    import openpyxl
    wb = openpyxl.load_workbook(xlsx, read_only=True)
    try:
        ws = wb["Contents"] if "Contents" in wb.sheetnames else wb.worksheets[-1]
        rows = [r for r in ws.iter_rows(values_only=True) if any(v not in (None, "") for v in r)]
    finally:
        wb.close()
    head = [str(v or "") for v in rows[0]]
    ti = next((i for i, h in enumerate(head) if h.startswith("/mods/titleInfo/title")), None)
    return {"rows": len(rows) - 1, "sheets": wb.sheetnames, "titles": sorted({str(r[ti]).strip() for r in rows[1:] if ti is not None and r[ti]})}


def run(work: dict, state: dict, save, note: str, yes: str, work_dir: Path, log, handle: dict | None = None,
        progress=None, receipt: str = "", thumb_progress=None, mode: str = "request") -> dict:
    """work: 1단계 결과(title, output_xlsx, rows, manuscripts, thumbs). state: 작품 상태 기록. save(patch): 상태 저장.
    receipt: 이어서 할 때 사람이 넣은 접수번호(없으면 상태 기록이나 반입 결과에서 얻는다)."""
    from . import kolis_ui, kolis_upload, kolis_register, kolis_request as req, cnts_folders
    from .ids_from_export import receipt_map
    from .journal import Journal
    handle = handle or {}
    progress = progress or (lambda key, status, text="": None)
    work_dir = Path(work_dir)
    jr = Journal(work_dir, str(work.get("title") or Path(str(work.get("folder") or "작품")).name))
    log = jr.wrap(log)
    year = str(datetime.date.today().year)
    page = req.Page(log, jr)
    t_all = time.time()
    checks: list = []

    def check(name: str, ok: bool, value="", why: str = ""):
        """조건 하나를 확인하고 기록한다. 거짓이면 멈춘다."""
        jr.write("check", name=name, ok=bool(ok), value=value)
        checks.append((name, bool(ok)))
        log(f"  확인 {'✓' if ok else '✗'} {name}: {value}")
        if not ok:
            raise Stop(f"{name} — {why or value}")

    def check_cancel(after: str):
        if handle.get("cancel"):
            raise Stop(f"사용자가 중단함({after}까지 끝남). 다시 실행하면 이어서 합니다")

    def step(key: str, fn, done: bool, skip_text: str = ""):
        label = dict(STEPS)[key]
        jr.step = key
        if done:
            jr.write("step", status="skip", text=skip_text)
            log(f"■ {label}: 이미 끝남 — 건너뜀 {skip_text}")
            progress(key, "skip", skip_text)
            return None
        jr.write("step", status="start")
        log(f"■ {label}: 시작")
        progress(key, "run")
        t0 = time.time()
        try:
            text = fn() or ""
        except BaseException as e:
            jr.error(e, seconds=round(time.time() - t0, 1))
            jr.write("step", status="fail", text=str(e), seconds=round(time.time() - t0, 1))
            log(f"■ {label}: 멈춤 — {e}")
            progress(key, "fail", str(e)[:300])
            raise
        sec = round(time.time() - t0, 1)
        jr.write("step", status="done", text=text, seconds=sec)
        progress(key, "done", f"{text} ({int(sec)}초)")
        log(f"■ {label}: 완료 {text} ({int(sec)}초)")
        check_cancel(label)
        return text

    def fallback(what: str, e: BaseException):
        jr.write("fallback", what=what, reason=str(e))
        log(f"  요청이 KOLIS 로 나가지 않음({e}) → {what}을(를) 화면 방식으로 진행합니다")

    try:
        # ---------- 시작 전 확인 ----------
        jr.step = "start"
        jr.write("input", mode=mode, note=note, receipt=receipt, year=year, work={k: work.get(k) for k in ("title", "folder", "output_xlsx", "rows", "manuscripts", "thumbs", "confirm_cells")},
                 state={k: state.get(k) for k in ("kolis_submit", "export", "cnts", "upload", "thumbs_register", "register")})
        log(f"=== KOLIS 등록 시작: {work.get('title')} · 방식 {'요청 우선' if mode == 'request' else '화면'} · 기록 {jr.path}")
        check("직원 동의(YES)", yes == "YES", "입력됨" if yes == "YES" else "없음", "직원과 반입용 엑셀을 확인한 뒤 YES 를 넣어야 합니다")
        xlsx = Path(work.get("output_xlsx") or "")
        root = Path(work.get("manuscripts") or "")
        check("반입용 엑셀 파일", xlsx.is_file(), str(xlsx), f"반입용 엑셀이 없습니다: {xlsx}")
        check("원고 폴더", root.is_dir(), str(root), f"원고 폴더가 없습니다: {root}")
        ex_info = _excel_rows(xlsx)
        rows = ex_info["rows"]
        check("반입용 엑셀의 시트", ex_info["sheets"] == ["Sample", "Contents"], ex_info["sheets"], "도서관 양식(Sample, Contents) 밖의 시트가 있습니다")
        check("반입용 엑셀 행 수", 0 < rows <= 500, rows, "행이 없거나 500행을 넘습니다(반입 엑셀 1개당 500건)")
        if work.get("rows"):
            check("엑셀 행 수 = 1단계가 만든 행 수", rows == int(work["rows"]), f"{rows} / {work['rows']}", "1단계 뒤에 엑셀의 행 수가 바뀌었습니다 → 직원 확인")
        folders = _folders(root)
        check("원고 폴더 수 = 엑셀 행 수", len(folders) == rows, f"{len(folders)} / {rows}")
        local = kolis_upload.check_local(root) if all(p.name.startswith("CNTS-") for p in folders) else None
        if local:
            check("원고 폴더 안에 이미지만 있음", not local["problems"], local["problems"] or f"파일 {local['files']}개, {local['mb']}MB")
        thumbs = Path(work["thumbs"]) if work.get("thumbs") and Path(work["thumbs"]).is_dir() and any(Path(work["thumbs"]).iterdir()) else None
        log(f"  썸네일: {'동봉됨 → 등록함 (' + str(thumbs) + ')' if thumbs else '동봉되지 않음 → 등록하지 않음'}")
        jr.write("branch", thumbs=bool(thumbs), path=str(thumbs or ""))
        receipt = str(receipt or "").strip() or str((state.get("kolis_submit") or {}).get("receipt") or (state.get("export") or {}).get("receipt") or "")
        if receipt:
            check("접수번호 형식", receipt.isdigit(), receipt)

        # ---------- 1. 일괄반입 ----------
        sub = state.get("kolis_submit") or {}
        if sub.get("attempted") and not sub.get("ok") and not receipt:
            raise Stop("지난번에 반입을 보냈지만 결과를 확인하지 못했습니다. 다시 반입하지 않습니다. KOLIS 납본자료접수에서 이 작품의 접수번호를 확인해 "
                       "'접수번호' 칸에 넣고 다시 실행하세요(목록에 없으면 직원과 확인한 뒤 상태 기록의 kolis_submit 을 지웁니다)")

        def do_import():
            nonlocal receipt
            check("비고(차수·번호)", bool(note) and not re.search(r"\(차\)|\(\)", note), note, "비고에 차수와 번호를 넣어야 합니다(예: 2026-납본-웹툰대행(5차)(394))")
            mark = {"attempted": True, "ok": False, "note": note, "xlsx": str(xlsx), "rows": rows}
            if mode == "request":
                try:
                    save({"kolis_submit": {**mark, "how": "request"}})
                    r = req.import_excel(page, year, note, xlsx, rows, yes, log)
                    receipt = r["receipt"]
                    same = set(r["titles"]) == set(ex_info["titles"]) if ex_info["titles"] else True
                    save({"kolis_submit": {**mark, "ok": True, "how": "request", "message": r["message"], "receipt": receipt, "count": r["count"]}})
                    check("반입된 본표제 = 엑셀의 본표제", same, f"{r['titles']} / {ex_info['titles']}", "반입된 자료의 제목이 엑셀과 다릅니다 → 직원 확인")
                    return f"접수번호 {receipt}, {r['count']}건 (요청 방식)"
                except req.NotSent as e:
                    save({"kolis_submit": {"attempted": False, "ok": False, "how": "request", "not_sent": str(e)}})
                    fallback("일괄반입", e)
                except req.Stop as e:
                    raise Stop(str(e)) from e
            kolis_ui.prepare_batch_import(note, xlsx, log)
            pop = kolis_ui.popup_window()
            check("일괄반입 팝업 열림", bool(pop), bool(pop))
            since = time.time() * 1000 - 5000
            save({"kolis_submit": {**mark, "how": "screen"}})
            r = kolis_ui.submit(pop, yes, log)
            check("반입 결과 메시지", bool(r.get("ok")), r.get("message") or "결과 메시지 없음", "반입 결과가 '완료'가 아닙니다 → KOLIS 화면 확인(다시 반입하지 마세요)")
            receipt = _receipt_from_record(since) or _receipt_from_screen()
            save({"kolis_submit": {**mark, "ok": True, "how": "screen", "message": r.get("message", ""), "receipt": receipt}})
            check("접수번호 읽음", receipt.isdigit(), receipt or "읽지 못함", "반입은 완료됐지만 접수번호를 읽지 못했습니다. KOLIS 화면에서 확인해 '접수번호' 칸에 넣고 다시 실행하세요")
            return f"접수번호 {receipt} (화면 방식)"
        step("import", do_import, bool(sub.get("ok")) or bool(receipt), f"접수번호 {receipt}")

        # ---------- 2. 콘텐츠ID 받기 ----------
        ex = state.get("export") or {}
        ex_file = Path(ex.get("file") or "")

        def do_export():
            nonlocal ex_file
            r = None
            if mode == "request":
                try:
                    r = req.export_receipt(page, year, receipt, work_dir, log)
                    r["how"] = "request"
                except req.NotSent as e:
                    fallback("콘텐츠ID 받기", e)
                except req.Stop as e:
                    raise Stop(str(e)) from e
            if r is None:
                r = kolis_ui.download_export(log, work_dir, receipt)
                r["how"] = "screen"
            check("받은 목록의 접수번호", str(r["receipt"]) == str(receipt), f"{r['receipt']} / {receipt}")
            check("KOLIS 목록 건수 = 엑셀 행 수", int(r["count"]) == rows, f"{r['count']} / {rows}")
            m = receipt_map(Path(r["file"]))
            check("콘텐츠ID 가 건마다 다름", len({x["cnts"] for x in m}) == rows, len({x["cnts"] for x in m}))
            check("접수번호 뒷번호가 1부터 이어짐", [x["seq"] for x in m] == list(range(1, rows + 1)), [x["seq"] for x in m][:5])
            ex_file = Path(r["file"])
            save({"export": {"file": r["file"], "receipt": r["receipt"], "count": r["count"], "how": r["how"]}})
            return f"{r['count']}건 ({r['first']} … {r['last']}, {'요청' if r['how'] == 'request' else '화면'} 방식)"
        step("export", do_export, ex_file.is_file() and str(ex.get("receipt")) == str(receipt), ex_file.name)

        # ---------- 3. 폴더명 ----------
        ids = {m["cnts"] for m in receipt_map(ex_file)}
        names = {p.name for p in _folders(root)}
        if names and all(n.startswith("CNTS-") for n in names):
            check("원고 폴더 이름 = 이 접수번호의 콘텐츠ID", names == ids, f"다른 것 {sorted(names ^ ids)[:4]}", "원고 폴더 이름이 이 접수번호의 콘텐츠ID 와 다릅니다(다른 접수번호로 바꾼 이름일 수 있음)")

        def do_cnts():
            try:
                p = cnts_folders.plan(ex_file, root)
                jr.write("plan", pairs=p["pairs"])
                for a in p["pairs"][:500]:
                    log(f"  {a[0]} → {a[1]} ({a[2]})")
                r = cnts_folders.apply(ex_file, root)
            except SystemExit as e:
                raise Stop(str(e)) from e
            after = {p.name for p in _folders(root)}
            check("바꾼 뒤 폴더 이름 = 콘텐츠ID", after == ids, f"다른 것 {sorted(after ^ ids)[:4]}")
            save({"cnts": {"count": r["count"], "receipt": r["receipt"]}})
            return f"{r['count']}개 폴더"
        step("cnts", do_cnts, bool(names) and names == ids, f"{len(names)}개 폴더")

        # ---------- 4. 원문일괄등록 ----------
        def files_on_kolis() -> dict | None:
            """건마다 등록된 원문 수(읽기만 함). 요청이 나가지 않으면 None."""
            try:
                return {i["id"]: i["files"] for i in req.contents(page, year, receipt)["items"]}
            except req.Stop as e:
                log(f"  원문 수를 읽지 못함: {e}")
                return None

        def do_upload():
            local = kolis_upload.check_local(root)
            check("원고 폴더 검사", not local["problems"], local["problems"] or f"폴더 {local['folders']}개, 파일 {local['files']}개, {local['mb']}MB")
            before = files_on_kolis() if mode == "request" else None
            if before is not None:
                jr.write("kolis", what="원문 수(전)", value=before)
                check("원문이 아직 등록되지 않음", not any(before.values()), {k: v for k, v in before.items() if v} or "전 건 0",
                      "이미 원문이 등록된 건이 있습니다 → KOLIS 화면에서 확인한 뒤 진행하세요")
            try:
                r = kolis_upload.run(root, log, handle, yes, receipt)
            except kolis_upload.Stop as e:
                raise Stop(str(e)) from e
            after = files_on_kolis() if mode == "request" else None
            if after is not None:
                jr.write("kolis", what="원문 수(후)", value=after)
                check("전 건에 원문이 등록됨", set(after) == ids and all(v >= 1 for v in after.values()), {k: v for k, v in after.items() if v < 1} or f"{len(after)}건 모두 1 이상")
            save({"upload": {"folders": r["folders"], "files": r["files"], "message": r["message"], "verified": after is not None}})
            return f"폴더 {r['folders']}개, 파일 {r['files']}개, {r['mb']}MB"
        step("upload", do_upload, bool(state.get("upload")))

        # ---------- 5. 썸네일(동봉된 납품만) ----------
        def do_thumbs():
            from . import kolis_thumbs
            r = kolis_thumbs.run(xlsx, thumbs, 0, log, handle, thumb_progress, receipt)
            jr.write("thumbs", results=r.get("results"))
            save({"thumbs_register": {"done": r["done"], "skipped": r["skipped"], "complete": not r["stopped"]}})
            check("썸네일 등록이 끝까지 감", not r["stopped"], f"완료 {r['done']}건, 이미 있음 {r['skipped']}건", "썸네일 등록이 중간에 멈췄습니다. 로그의 이유를 확인한 뒤 다시 실행하세요")
            check("썸네일 건수 = 엑셀 행 수", r["done"] + r["skipped"] == rows, f"{r['done'] + r['skipped']} / {rows}")
            return f"등록 {r['done']}건, 이미 있음 {r['skipped']}건"
        jr.step = "thumbs"
        if thumbs is None:
            jr.write("step", status="skip", text="썸네일 없음")
            log("■ 썸네일 등록: 썸네일이 동봉되지 않은 납품 — 하지 않음")
            progress("thumbs", "skip", "썸네일 없음(등록하지 않음)")
        else:
            step("thumbs", do_thumbs, bool((state.get("thumbs_register") or {}).get("complete")))

        # ---------- 6. 등록대상처리 → 가원부번호 → 가원부 파일 ----------
        out: dict = dict(state.get("register") or {})

        def do_register():
            nonlocal out
            r = None
            if mode == "request":
                try:
                    req.receipt_items(page, year, receipt)          # 읽기만 하는 요청으로 먼저 확인: 여기서 나가지 않으면 화면 방식으로
                except req.NotSent as e:
                    fallback("등록대상처리 → 가원부번호", e)
                else:
                    try:
                        r = req.run(receipt, year, work_dir, log, handle, yes, page)
                        r["how"] = "request"
                    except req.Stop as e:
                        raise Stop(f"{e} (요청이 나간 뒤라 화면 방식으로 바꾸지 않았습니다. KOLIS 화면에서 상태를 확인하세요)") from e
            if r is None:
                try:
                    r = kolis_register.run(receipt, work_dir, log, handle, yes)
                    r["how"] = "screen"
                except kolis_register.Stop as e:
                    raise Stop(str(e)) from e
            got = set(r["export"].get("ids") or [])
            out = {"record_no": r["record_no"], "file": r["file"], "count": r["count"], "receipt": receipt, "how": r["how"]}
            save({"register": out})
            check("가원부 파일 건수 = 엑셀 행 수", int(r["count"]) == rows, f"{r['count']} / {rows}")
            check("가원부 파일의 콘텐츠ID = 반입한 콘텐츠ID", got == ids, f"다른 것 {sorted(got ^ ids)[:4]}")
            return f"가원부번호 {r['record_no']}, {r['count']}건 ({'요청' if r['how'] == 'request' else '화면'} 방식)"
        step("register", do_register, bool(out.get("record_no")), str(out.get("record_no") or ""))

        jr.step = "end"
        sec = int(time.time() - t_all)
        jr.write("done", receipt=receipt, record_no=out.get("record_no"), file=out.get("file"), seconds=sec, requests=page.count, checks=len(checks))
        log(f"=== 전체 완료: 접수번호 {receipt}, 가원부번호 {out.get('record_no')} · {sec}초 · 확인 {len(checks)}개 통과 · 요청 {page.count}건 · 기록 {jr.path.name}")
        return {"receipt": receipt, "record_no": out.get("record_no"), "file": out.get("file"), "count": out.get("count"), "export_file": str(ex_file),
                "seconds": sec, "journal": str(jr.path), "checks": len(checks), "requests": page.count}
    except BaseException as e:
        if jr.step not in dict(STEPS):
            jr.error(e)
        jr.write("stopped", reason=str(e), receipt=receipt, seconds=int(time.time() - t_all), requests=page.count)
        log(f"=== 멈춤: {e} · 기록 {jr.path}")
        if isinstance(e, Stop) or not isinstance(e, Exception):
            raise
        raise Stop(f"{type(e).__name__}: {e}") from e
