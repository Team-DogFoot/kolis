# kolis — 웹툰 납본·수집 대행 KOLIS 자동화 (human-in-the-loop)

국립중앙도서관 "웹툰 납본·수집 대행 사업"의 수집·등록·구축·점검 절차를 자동화하는 프로그램.
사람이 판정하는 지점(복본 판정, 반입 엑셀 최종 확인, 전거 연결 승인, 점검 결과 확정)은 남기고, 그 사이 일을 프로그램이 한다.

## 현재 상태 (2026-09-29)
- **프로그램 화면**: ① 납품 폴더 → 반입용 엑셀(에이전트가 한 번에) → (사람: 반입용 엑셀 확인) → ② KOLIS 등록(버튼 하나: 일괄반입 → 콘텐츠ID → 폴더명 → 원문일괄등록 → 썸네일(동봉된 납품만) → 등록대상처리·가원부번호·가원부 파일). 단계별 버튼은 ② 아래에 접혀 있다.
- ②는 **브라우저를 쓰지 않는다.** 프로그램이 `.env` 의 계정(KOLIS_ID, KOLIS_PW)으로 직접 로그인해 요청만으로 한다. 09-30 에 타임머신 대소동(3권, 192장)을 28.9초에 끝냄. 실행할 때마다 새 접수번호가 생기고, 전부 `work\취소요청_목록.csv` 에 남는다(마지막 성공만 유지). 실행 기록은 `work\logs\flow-<작품>-<시각>.jsonl`. 썸네일이 동봉된 납품의 썸네일 등록만 Edge 가 필요하다.
- **작품 탭**: 여러 작품을 탭으로 열어 둔다. ①은 동시에 여러 작품(한도 3개), ②~⑤는 KOLIS 창이 하나라 한 번에 한 작품만.
- **①은 에이전트(클로드코드 헤드리스)가 한다.** 출판사 엑셀과 원고 읽기, 웹 조사, 칸마다 값 결정, 스스로 검사, 별도 검수까지. 코드는 83열 양식 쓰기와 형식·파일 증거 검사만 한다.
- ①은 개발용 3작품으로 프로그램 창에서 검증함. 09-29 에 타임머신 대소동으로 ②③⑤를 끝까지 진행(접수번호 939, 가원부번호 2026-1615). 이 중 ③의 팝업 열기·끌어다 놓기와 ⑤의 전체 실행은 클로드가 손으로 한 절차를 코드로 옮긴 것이라 프로그램 창으로는 아직 돌리지 않음(다음 작품에서 확인).
- KOLIS 단계를 실행하면 요청 기록이 `work\captures\rec\` 에 남는다(`ie_dom.py`, 끄려면 `KOLIS_RECORD=0`). 요청 방식 자동화 분석은 `docs/REQUEST-AUTOMATION.md`.
- 세션 시작은 `CLAUDE.md` → `docs/HANDOFF.md`(0절) → `docs/EXECUTION-LOG.md`. 메모리 사본은 `docs/memory/`.

## 실행
바탕화면 **"KOLIS 웹툰 납본 도우미"** 바로 가기(`bin\app.vbs`, 콘솔 없음) 또는:
```
.\.venv\Scripts\python.exe -m kolis_tool.app
```
전제: 클로드코드 로그인(①), `.env` 의 KOLIS 계정(②), Playwright(이 PC 의 Edge 사용). Edge 에서 KOLIS 로그인은 단계별 버튼과 썸네일 등록에만 필요.
결과·로그: `work\`(git 제외). 파일 로그 `work\logs\app-YYYYMMDD.log`, 실패 캡처 `work\logs\fail-*.png`,
작품별 `work\<폴더>.상태.json`(진행 상태), `.작업.json`(에이전트 결과), `.로그.json`(탭 로그), 열어 둔 탭 `work\tabs.json`.

## 에이전트
- 원본: `kolis_tool/agent_home/` — `CLAUDE.md`(역할·일하는 순서), `.claude/skills/prepare-import`(납품 폴더 → 반입용 엑셀), `.claude/skills/research-work`(조사 기준),
  `.claude/agents/reviewer.md`(검수 에이전트), `knowledge/`(쌓이는 요령, 직원이 고친 내용).
- 실행할 때 `%LOCALAPPDATA%\kolis_tool\agent\` 에 펼쳐 그 안에서 돈다(저장소 밖: 저장소의 CLAUDE.md 가 섞이지 않게). 도서관 매뉴얼 원문을 `knowledge/rules/` 로 복사한다.
- 에이전트가 고친 `knowledge/*.md` 는 실행이 끝나면 저장소 원본으로 되가져온다(커밋 대상).
- 에이전트가 쓰는 명령(이것만 허용): `render`(페이지 열기), `check-research`(조사 결과 검사), `write-import`(반입용 값 검사 + 엑셀 쓰기).
- 모델은 Sonnet(환경변수 `KOLIS_AGENT_MODEL`), 동시 실행 한도는 3(환경변수 `KOLIS_MAX_AGENTS`).

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

## 명령줄(점검 도구)
```
python -m kolis_tool unzip    <출판사.zip> -o <폴더>
python -m kolis_tool inspect  <원문 상위폴더>
python -m kolis_tool ids <전체출력.xls> -o work/ids.txt
python -m kolis_tool mods-fetch work/ids.txt [--preview] -o work/xml --config kolis.json
python -m kolis_tool mods-check work/xml --wonbu <원부번호> --nth 1
```

## 폴더
- `kolis_tool/` 본체. `app.py`+`ui/index.html`(창, 탭), `prepare.py`(① 실행·마무리), `agent.py`(클로드코드 실행기), `agent_home/`(에이전트 작업 공간 원본),
  `import_writer.py`(83열 쓰기·검사), `checks.py`(조사 결과 검사), `render.py`(페이지 열기), `kolis_ui.py`(KOLIS 화면 조작 공통·일괄반입·전체출력),
  `kolis_upload.py`(원문일괄등록), `kolis_thumbs.py`(썸네일 등록 반복), `cnts_folders.py`, `ids_from_export.py`, `rename_files.py`, `logutil.py`, `templates/import_template_83.xlsx`
- `docs/HANDOFF.md` 세션 시작 지시·상태 / `docs/EXECUTION-LOG.md` 실제 진행 기록 / `docs/FIELD-CHECKLIST.md` 현장 확인 / `docs/source/` 도서관 원본 자료 / `docs/memory/` 클로드코드 메모리 사본
- `bin/` app.vbs·app.bat·setup.bat, `work/` 산출물(git 제외)

계정·비밀번호는 `.env`(git 제외)와 환경변수로만. 클라이언트 원고·HAR·계정이 든 파일은 저장소에 넣지 않는다.
