# kolis — 웹툰 납본·수집 대행 KOLIS 자동화 (human-in-the-loop)

국립중앙도서관 "웹툰 납본·수집 대행 사업"의 수집·등록·구축·점검 절차를 자동화하는 프로그램.
사람이 판정하는 지점(복본 판정, 반입 엑셀 최종 확인, 전거 연결 승인, 점검 결과 확정)은 남기고, 그 사이 일을 프로그램이 한다.

## 현재 상태 (2026-09-30)
- **프로그램 화면**: KOLIS 계정 로그인 → ① 납품 폴더 → 반입용 엑셀 → (사람: 반입용 엑셀 확인) → ② KOLIS 등록(버튼 하나). 옛 단계별 버튼은 ② 아래에 접혀 있다.
- **①은 에이전트(클로드코드 헤드리스)가 한다.** 출판사 엑셀과 원고 읽기, 웹 조사, 칸마다 값 결정, 스스로 검사, 별도 검수까지. 코드는 83열 양식 쓰기와 형식·파일 증거 검사만 한다. 작품당 약 10분, 여러 작품 동시(한도 3개).
- **②는 브라우저를 쓰지 않는다.** 프로그램이 계정으로 직접 로그인해 요청만으로: 일괄반입 → 콘텐츠ID 받기 → 원고 폴더명 → 원문일괄등록 → 썸네일(동봉된 납품만) → 등록대상처리 → 가원부번호 → 가원부 파일(KOLIS 에서 받은 `.xls`). 타임머신 대소동(3권, 192장, 26.7MB)이 약 25초.
- ②는 매번 처음부터 새로 반입한다. 실행한 접수번호는 전부 `work\취소요청_목록.csv` 에 남고, 작품마다 끝까지 성공한 마지막 것만 "유지", 나머지는 "취소 요청"이다(주무관에게 전달하는 것은 사람).
- 아직 없는 것: 브라우저 없는 썸네일 등록(동봉된 납품이면 Edge 화면 방식을 부름), 10MB 이상 이미지, 구축·점검 단계.
- 세션 시작은 `CLAUDE.md` → `docs/HANDOFF.md`(0절) → `docs/EXECUTION-LOG.md`. 시행착오는 `docs/RETROSPECTIVE-2026-09-30.md`. 메모리 사본은 `docs/memory/`.

## 실행
바탕화면 **"KOLIS 웹툰 납본 도우미"** 바로 가기(`bin\app.vbs`, 콘솔 없음) 또는:
```
.\.venv\Scripts\python.exe -m kolis_tool.app
```
전제: 클로드코드 로그인(①), KOLIS 계정(②: 창 위쪽에서 로그인하거나 `.env` 에 KOLIS_ID·KOLIS_PW), Playwright(이 PC 의 Edge 사용). Edge 에서 KOLIS 로그인은 단계별 버튼과 썸네일 등록에만 필요.
결과·로그: `work\`(git 제외). 파일 로그 `work\logs\app-YYYYMMDD.log`, KOLIS 등록 실행 기록 `work\logs\flow-<작품>-<시각>.jsonl`, 취소 요청 목록 `work\취소요청_목록.csv`,
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
copy .env.example .env       (KOLIS_ID, KOLIS_PW 입력 — 또는 프로그램 창에서 로그인)
claude
```
클로드코드가 뜨면 **"시작"** 이라고 입력한다. 지시는 `docs/HANDOFF.md` 0절.

저장소에 없어서 새 PC 에는 없는 것: `work\`(산출물, 실행 기록, 취소 요청 목록), `.env`, `kolis.json`, 납품 자료. KOLIS 는 도서관 내부망에서, 계정에 신청된 IP 에서만 로그인된다.
클로드코드 메모리는 `docs\memory\` 의 파일을 `%USERPROFILE%\.claude\projects\<저장소 경로 이름>\memory\` 로 복사하면 이어진다("시작"이 이 일을 한다).

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
  `import_writer.py`(83열 쓰기·검사), `checks.py`(조사 결과 검사), `render.py`(페이지 열기),
  `kolis_flow.py`(② 순서·확인·취소 요청 목록), `kolis_http.py`(브라우저 없는 로그인·접속), `kolis_request.py`(KOLIS 요청), `journal.py`(실행 기록),
  `kolis_ui.py`·`kolis_upload.py`·`kolis_register.py`(옛 화면 방식, 예비용), `kolis_thumbs.py`(썸네일 등록, 화면 방식), `ie_dom.py`(요청 기록 도구), `cnts_folders.py`, `ids_from_export.py`, `rename_files.py`, `logutil.py`, `templates/import_template_83.xlsx`
- `docs/HANDOFF.md` 세션 시작 지시·상태 / `docs/EXECUTION-LOG.md` 실제 진행 기록 / `docs/REQUEST-AUTOMATION.md` 요청 방식 분석 / `docs/RETROSPECTIVE-2026-09-30.md` 시행착오 / `docs/FIELD-CHECKLIST.md` 현장 확인 / `docs/source/` 도서관 원본 자료 / `docs/memory/` 클로드코드 메모리 사본
- `bin/` app.vbs·app.bat·setup.bat, `work/` 산출물(git 제외)

계정·비밀번호는 `.env`(git 제외)와 환경변수로만. 클라이언트 원고·HAR·계정이 든 파일은 저장소에 넣지 않는다.
