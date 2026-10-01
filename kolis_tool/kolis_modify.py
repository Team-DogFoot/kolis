"""썸네일 등록 — 브라우저 없이, 건마다 한 장씩(2026-10-01).

화면에서 직원이 하는 일(납본자료접수 → 수정 → 자리 행 원문삭제·저장 → 원문등록(파일 전송, 원문유형 썸네일) → 저장)과 **같은 요청**을 보낸다.
  1. 썸네일 파일 전송: 업로더 주소로 1장(임시 위치 `/Upload1/tmp/wonmun/<날짜+시각>/`).
  2. 반입 때 생긴 0 Bytes 자리 행이 있으면: 그 행을 지우는 저장 요청.
  3. 썸네일 행을 넣은 저장 요청.
저장 요청(`popupUpdateOnlineDepstRecet.do`)은 수정 화면의 서지 칸 전부(146개)를 함께 보낸다. 값은 그 건의 지금 값을 KOLIS 에서 읽어 그대로 돌려보낸다.
칸의 이름·순서·어느 값에서 오는지는 `templates/modify_param_spec.json`(수정 화면의 스크립트 getParam 에서 뽑은 것)에 있다.
근거: 2026-10-01 접수 982 에서 수정 화면의 스크립트가 실제로 보낸 본문을 기록해 맞췄다(`docs/REQUEST-AUTOMATION.md` 6절).

지키는 것: 저장 전·후에 그 건의 값을 다시 읽어 서지 값이 바뀌지 않았는지, 파일 목록이 기대대로인지 확인하고 다르면 멈춘다.
원문일괄등록 요청(`insertContentsText.do`)에 원문유형 06 을 넣는 방법은 KOLIS 가 거절한다("해당콘텐츠에 원문이 이미 존재합니다", 접수 982).
"""
from __future__ import annotations
import datetime, json, re, time, uuid
from pathlib import Path
from urllib.parse import urlencode
from .kolis_request import FORM, MIME, CHUNK_LIMIT, TEXT_KIND, THUMB_KIND, U_HANDLER, U_FILE_LIST, Stop, _text, upload_fields, uploader_answer

U_DATA = "/online/acq/bodepst/depstrecet/onlineDepstRecet/modifyInputOnlineDepstRecet/selectModifyInputOnlineDepstRecetData.do"
U_UPDATE = "/online/acq/bodepst/depstrecet/onlineDepstRecet/popupUpdateOnlineDepstRecet.do"
SPEC = json.loads((Path(__file__).parent / "templates" / "modify_param_spec.json").read_text(encoding="utf-8"))
LICENSE_TEXT = {"0": "외부공개", "1": "비공개", "2": "국립중앙도서관 공개"}       # 서비스범위 선택지의 글자(수정 화면, 2026-10-01). 웹툰 사업은 1(성인용)과 2
WORKING = ("DS_1100", "DS_0110", "DS_0120")                                      # 등록여부 선택지
VOLATILE = {"contents_record_change_date", "work_date", "create_date", "acquisit_date", "use_limit_code", "contents_access_condition",
            "contents_xml", "species_xml"}                     # 수정 화면의 저장이 스스로 바꾸는 값(same_bib 의 설명). XML 은 따로 비교한다
ROW_KEYS = ("FILE_ID", "FILE_LOCA", "NO", "ACCESSION_NO", "TEXT_GBN_CD", "TEXT_GBN", "FILE_NAME", "FILE_SIZE", "SEQ_NO", "REG_DT")


def _s(v) -> str:
    return "" if v is None else str(v)


def read(client, item: dict) -> dict:
    """수정 화면이 여는 그 건의 값(148칸)."""
    r = client.send("POST", U_DATA, urlencode({"receipt_key": _s(item["RECEIPT_KEY"]), "arrSpeciesKey": _s(item.get("REC_KEY") or item["SPECIES_KEY"])}), FORM)
    rows = r.get("data") or []
    if len(rows) != 1:
        raise Stop(f"수정 화면의 값이 {len(rows)}건 왔습니다(1건이어야 함): {item.get('CONTENTS_ID')}")
    return rows[0]


def files(client, cid: str) -> list[dict]:
    return client.send("POST", U_FILE_LIST, urlencode({"contents_id": cid}), FORM).get("list") or []


def build(d: dict, receipt: str, frm_file: str, frm_del_file: str) -> list[tuple[str, str]]:
    """저장 본문. 수정 화면의 getParam 과 같은 항목·순서."""
    lic = _s(d.get("contents_license_type"))
    if lic not in LICENSE_TEXT:
        raise Stop(f"서비스범위 값 '{lic}' 의 글자를 모릅니다(수정 화면의 선택지를 확인해 LICENSE_TEXT 에 넣어야 함)")
    if _s(d.get("working_status")) not in WORKING:
        raise Stop(f"등록여부 값 '{d.get('working_status')}' 는 수정 화면의 선택지에 없습니다")
    timed = lic == "1" and _s(d.get("lic_alw_start_day"))
    special = {
        "receiptNoHasFlag": "Y", "receiptNoVal": _s(receipt), "receiptKeyVal": _s(d.get("receipt_key")), "receiptWorkCodeVal": _s(d.get("work_code")), "regForm": "", "update": "Y",
        "typeofresourceContents": f"{_s(d.get('typeofresource'))} | {_s(d.get('typeofresource_name'))}", "genreContents": f"{_s(d.get('genre'))} | {_s(d.get('genre_name'))}",
        "useLimitCode": _s(d.get("use_limit_code")) or "--", "useLimitChangeCode": _s(d.get("use_limit_change_code")), "useLimitEndDate": _s(d.get("use_limit_end_date")),
        "useLimitRemark": _s(d.get("use_limit_remark")), "accessConditionLicenseContentsText": LICENSE_TEXT[lic],
        "openFlagType": "T" if timed else "P", "openDate": _s(d.get("lic_alw_start_day")) if lic == "1" else "", "openRemark": _s(d.get("lic_remark")) if lic == "1" else "",
        "identifierTypeContents": "ISBN", "frm_file": frm_file, "frm_del_file": frm_del_file,
    }
    return [(k, special[k] if k in special else (_s(d.get(src)) if src else "")) for k, src in SPEC if src != "!" or k in special]


def _row(x: dict, pos: int, uid: int, chk) -> dict:
    """수정 화면의 파일 표 한 행(loadGrid 가 만드는 모양)."""
    return {"_jqx_idx": pos, "_chk": chk, **{k: x.get(k) for k in ROW_KEYS}, "FILE_EXT": x.get("FILE_EXTE_NM"), "FOLD_YN": x.get("FOLD_YN"), "TEMP_PATH": x.get("TEMP_PATH"),
            "CONTENTS_ID": x.get("CONTENTS_ID"), "ENCRYPT_FLAG": x.get("ENCRYPT_FLAG"), "uid": uid}


def _json(rows: list[dict]) -> str:
    return "[" + ",".join(json.dumps(r, ensure_ascii=False, indent="\t") for r in rows) + "]"


def _real(x: dict) -> bool:
    return _s(x.get("FILE_ID")).startswith("FILE-")


def _save(client, d: dict, receipt: str, frm_file: str, frm_del_file: str, what: str) -> None:
    r = client.send("POST", U_UPDATE, urlencode(build(d, receipt, frm_file, frm_del_file)), FORM, wait=120, shown=f"(수정 저장: {what})")
    if _text(r.get("sttus")) != "success":
        raise Stop(f"저장이 실패했습니다({what}): {_text(r.get('msg'))[:200]}")


def same_bib(a: dict, b: dict) -> list[str]:
    """저장 전·후의 서지 값 비교. 달라진 칸 이름을 돌려준다.
    수정 화면의 저장은 그 자체로 몇 가지를 바꾼다(화면에서 손으로 저장해도 같다, 2026-10-01 접수 982 에서 확인): 생성일·작업일이 저장 시각으로, 입수일이 비고,
    이용제한구분이 '--', 서비스범위 글자가 채워지고, MODS 는 빈 태그(subTitle, partName, 대등표제, edition, KoreaUniversity)와 accessCondition 이 더해지고 순서가 바뀐다.
    그래서 MODS 는 '값이 든 요소의 목록'이 같은지로 본다."""
    def filled(t):
        got = re.findall(r"<mods:(\w+)((?:\s[^>]*)?)>([^<]+)</mods:\1>", _s(t))
        return sorted((tag, " ".join(sorted(attrs.split())), text.strip()) for tag, attrs, text in got if text.strip() and tag not in ("recordChangeDate", "accessCondition"))
    out = [k for k in sorted(set(a) | set(b)) if k not in VOLATILE and _s(a.get(k)) != _s(b.get(k))]
    return out + [k for k in ("contents_xml", "species_xml") if filled(a.get(k)) != filled(b.get(k))]


def upload_thumbs(client, receipt: str, pairs: list[tuple[dict, Path]], log=None, handle: dict | None = None, check=None) -> dict:
    """pairs: (접수 목록의 한 건, 썸네일 파일) — 반입용 엑셀의 행 순서대로."""
    log = log or (lambda m: None)
    handle = handle or {}
    check = check or (lambda name, ok, value="", why="": None)
    missing = [str(f) for _, f in pairs if not Path(f).is_file() or Path(f).stat().st_size == 0]
    check("썸네일 파일이 전부 있음", not missing, missing[:3] or f"{len(pairs)}장")
    odd = [Path(f).name for _, f in pairs if Path(f).suffix.lower() not in MIME or Path(f).stat().st_size >= CHUNK_LIMIT]
    check("썸네일이 이미지이고 10MB 미만", not odd, odd[:3] or "예")
    done, removed, t0 = [], 0, time.time()
    for n, (item, f) in enumerate(pairs, 1):
        if handle.get("cancel"):
            raise Stop(f"사용자가 중단함(썸네일 {n - 1}/{len(pairs)}건)")
        f, cid = Path(f), _s(item["CONTENTS_ID"])
        before = files(client, cid)
        views = [x for x in before if x.get("TEXT_GBN_CD") == TEXT_KIND and _real(x)]
        check(f"{cid}: 열람 원문이 있음", len(views) >= 1, f"{len(views)}개")
        have = [x for x in before if x.get("TEXT_GBN_CD") == THUMB_KIND and _real(x)]
        check(f"{cid}: 썸네일이 아직 없음", not have, [x.get("FILE_NAME") for x in have] or "없음")
        other = [x for x in before if not _real(x) and x.get("TEXT_GBN_CD") != THUMB_KIND]
        check(f"{cid}: 파일 목록에 모르는 행이 없음", not other, [(x.get("TEXT_GBN"), x.get("FILE_NAME")) for x in other] or "없음")
        d0 = read(client, item)
        check(f"{cid}: 수정 화면의 값이 이 건의 것", _s(d0.get("contents_id")) == cid, _s(d0.get("contents_id")))
        # 1) 전송
        rule = "/Upload1/tmp/wonmun/" + datetime.datetime.now().strftime("%Y%m%d") + str(int(time.time() * 1000))
        data = f.read_bytes()
        raw = client.upload(U_HANDLER, upload_fields(str(uuid.uuid4()).upper(), f.name, "0z", rule), f.name, data, MIME[f.suffix.lower()], note={"rule": rule})
        try:
            ans = uploader_answer(raw).split("|")
        except Exception as e:  # noqa: BLE001
            raise Stop(f"전송 응답을 읽지 못했습니다({cid}/{f.name}): {raw[:120]}") from e
        temp = (ans[1].split("::", 1)[-1] if len(ans) > 1 else "").replace("//", "/")
        if ans[0] != "success" or temp != f"{rule}/{f.name}" or (len(ans) > 3 and ans[3] != str(len(data))):
            raise Stop(f"전송 결과가 예상과 다릅니다({cid}/{f.name}): {ans}")
        # 2) 자리 행 지우기(있을 때만)
        holders = [i for i, x in enumerate(before) if not _real(x)]
        if holders:
            kept = [(i, x) for i, x in enumerate(before) if i not in holders]
            keep = [_row(x, pos, i + 1, False) | {"datafield": False} for pos, (i, x) in enumerate(kept, 1)]
            gone = [{"idx": k, "file_id": before[i].get("FILE_ID"), "file_name": before[i].get("FILE_NAME"), "file_loca": before[i].get("FILE_LOCA"),
                     "seq_no": before[i].get("SEQ_NO"), "contents_id": cid} for k, i in enumerate(holders)]
            _save(client, d0, receipt, _json(keep), json.dumps(gone, ensure_ascii=False, separators=(",", ":")), "자리 행 삭제")
            mid = files(client, cid)
            check(f"{cid}: 자리 행이 지워지고 원문은 그대로", [x.get("FILE_ID") for x in mid] == [x.get("FILE_ID") for x in before if _real(x)], f"{len(mid)}행")
            removed += len(holders)
        else:
            mid = before
        # 3) 썸네일 행 넣고 저장
        d1 = read(client, item)
        target = [x for x in mid if x.get("TEXT_GBN_CD") == TEXT_KIND][-1]["FILE_ID"]      # 원문등록 창의 '경로' 기본값: 위치가 있는 마지막 행
        rows = [_row(x, i, i, True) for i, x in enumerate(mid, 1)]
        pos = len(rows) + 1
        ext = f.suffix.lstrip(".")
        rows.append({"_jqx_idx": pos, "_chk": "0", "FILE_ID": "", "FILE_LOCA": temp, "NO": pos, "ACCESSION_NO": None, "TEXT_GBN_CD": THUMB_KIND, "TEXT_GBN": "썸네일",
                     "FILE_NAME": f.name, "FILE_EXT": ext, "FOLDER_PATH": "", "TEMP_PATH": temp, "FILE_SIZE": str(len(data)), "SELECT_FILE_ID": target, "SEQ_NO": "0",
                     "REG_DT": "", "DRM_YN": "", "uid": pos})
        add = {"contents_id": cid, "kolis_control_no": "", "select_file_id": target,
               "data": [{"idx": 0, "text_gbn": THUMB_KIND, "text_gbn_desc": "썸네일", "file_name": f.name, "file_ext": ext, "file_size": str(len(data)), "temp_path": temp,
                         "folder_path": "", "har_type_cd": _s(d1.get("har_type_cd"))}]}
        _save(client, d1, receipt, _json(rows), json.dumps(add, ensure_ascii=False, separators=(",", ":")), "썸네일 등록")
        after = files(client, cid)
        thumb = [x for x in after if x.get("TEXT_GBN_CD") == THUMB_KIND]
        ok = len(thumb) == 1 and _real(thumb[0]) and thumb[0].get("FILE_NAME") == f.name and str(thumb[0].get("FILE_SIZE")) == str(len(data)) and bool(thumb[0].get("REG_DT"))
        check(f"{cid}: 썸네일 등록됨({f.name}, {len(data):,}B)", ok, [(x.get("FILE_NAME"), x.get("FILE_SIZE"), x.get("REG_DT"), x.get("FILE_ID")) for x in thumb] or "썸네일 행 없음")
        v = lambda rows_: [(x.get("FILE_ID"), x.get("FILE_SIZE")) for x in rows_ if x.get("TEXT_GBN_CD") == TEXT_KIND]
        check(f"{cid}: 열람 원문이 그대로", v(after) == v(before), f"{len(v(after))}개")
        diff = same_bib(d0, read(client, item))
        check(f"{cid}: 저장 뒤 서지 값이 그대로", not diff, diff or "같음(저장이 스스로 바꾸는 날짜·빈 태그 제외)", "저장 요청이 서지 값을 바꿨습니다 → 직원 확인")
        done.append({"id": cid, "file": f.name, "file_id": thumb[0].get("FILE_ID")})
        log(f"  썸네일 등록 {n}/{len(pairs)}: {cid} ← {f.name}")
    return {"count": len(done), "seconds": int(time.time() - t0), "items": done, "placeholders": removed}
