# kolis — 웹툰 납본·수집 대행 KOLIS 자동화 (human-in-the-loop)

국립중앙도서관 "웹툰 납본·수집 대행 사업"의 수집·등록·구축·점검 절차를 반자동화하는 프로그램.
사람이 판정하는 지점(복본 판정, 반입 엑셀 최종 확인, 전거 연결 승인, 점검 결과 확정)은 남기고, 그 사이 손작업을 프로그램이 한다.

## 현재 상태 (2026-09-19 00:10, 도서관 PC 세션 종료)
- **창 하나짜리 프로그램(7단계)** 이 동작한다: 납품 폴더 → 파일명 정리 → 기초메타데이터 보완(클로드 리서치 + 플랫폼 수집) → 반입용 엑셀 → KOLIS 일괄반입 → 전체출력·폴더명 CNTS → 썸네일 등록 반복.
- **실제 KOLIS 작업 1건 진행 중**: 5-219 '폐급에서 성주까지 레벨업'(접수번호 811, 123건). 일괄반입 → 원문일괄등록(2.3GB) → 일괄정보입력 → 원문등록 완료. 썸네일 7/123 등록. **다음 세션: 7단계로 나머지 116건.**
- 케나즈 '죽고 못사는 연애'(5-203)는 반입용 엑셀까지 만들어 둠(직원 확인 후 반입).
- 세션 시작은 `CLAUDE.md` → `docs/HANDOFF.md`(0절) → `docs/EXECUTION-LOG.md`. 메모리 사본은 `docs/memory/`.

## 실행
바탕화면 **"KOLIS 웹툰 납본 도우미"** 바로 가기(`bin\app.vbs`, 콘솔 없음) 또는:
```
.\.venv\Scripts\python.exe -m kolis_tool.app
```
전제: Edge 에서 KOLIS 로그인(5·6·7단계), 클로드코드 로그인(3단계), Playwright(`pip install playwright`, 이 PC 의 Edge 사용).
결과·로그: `work\`(git 제외). 파일 로그 `work\logs\app-YYYYMMDD.log`, 실패 캡처 `work\logs\fail-*.png`, 작업 상태 `work\<작품>.상태.json`.

## 다른 PC 에서 시작하기
```
git clone https://github.com/Team-DogFoot/kolis.git
cd kolis
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env       (KOLIS_ID, KOLIS_PW 입력)
claude
```
클로드코드가 뜨면 **"시작"** 이라고 입력한다. 지시는 `docs/HANDOFF.md` 0절.

## 명령줄(프로그램과 같은 기능)
```
python -m kolis_tool unzip    <출판사.zip> -o <폴더>
python -m kolis_tool inspect  <원문 상위폴더>
python -m kolis_tool rename   <원문 상위폴더> [--dry-run|--undo]
python -m kolis_tool thumbs   <회차썸네일 폴더> --title "<제목>" [--dry-run|--undo]
python -m kolis_tool enrich   <출판사용.xlsx> -o work/보완.xlsx [--json 작품정보.json | --cliptoon 파일…]
python -m kolis_tool convert  <출판사용.xlsx> --template kolis_tool/templates/import_template_83.xlsx --root <원문 상위폴더> --work-json 작품정보.json -o <반입용.xlsx>
python -m kolis_tool ids <전체출력.xls> -o work/ids.txt
python -m kolis_tool mods-fetch work/ids.txt [--preview] -o work/xml --config kolis.json
python -m kolis_tool mods-check work/xml --wonbu <원부번호> --nth 1
```

## 폴더
- `kolis_tool/` 본체. `app.py`+`ui/index.html`(창), `enrich.py`(리서치·보완), `platforms.py`(플랫폼 수집), `convert_import.py`, `kolis_ui.py`(KOLIS UI 자동화 공통·일괄반입·전체출력), `kolis_thumbs.py`(썸네일 등록 반복), `cnts_folders.py`, `ids_from_export.py`, `rename_files.py`, `logutil.py`, `templates/import_template_83.xlsx`
- `docs/HANDOFF.md` 세션 시작 지시·상태 / `docs/EXECUTION-LOG.md` 실제 진행 기록(시각·화면·교훈) / `docs/FIELD-CHECKLIST.md` 현장 확인 / `docs/source/` 도서관 원본 자료 / `docs/memory/` 클로드코드 메모리 사본
- `bin/` app.vbs·app.bat·단계별 bat, `work/` 산출물(git 제외)

계정·비밀번호는 `.env`(git 제외)와 환경변수로만. 클라이언트 원고·HAR·계정이 든 파일은 저장소에 넣지 않는다.
