# kolis — 웹툰 납본·수집 대행 KOLIS 자동화 (human-in-the-loop)

국립중앙도서관 "웹툰 납본·수집 대행 사업"의 수집·등록·구축·점검 절차를 자동화하는 프로그램.
사람이 판정하는 지점(복본 판정, 반입 엑셀 최종 확인, 전거 연결 승인, 점검 결과 확정)은 남기고, 그 사이 일을 프로그램이 한다.

## 현재 상태 (2026-10-03)
- **프로그램 화면**: 상단 자료 종류(`웹툰 ▾`) › 탭 줄: 고정 탭 **「복본조사」**(과장님용: 원부번호 목록 붙여 넣기 → 자동 조회 → 「선택한 원부 처리」 = 복본조사 → 후보 없으면 완료 → 일괄변경, 후보 있으면 멈추고 판정 근거·KOLIS 링크) + 작품 탭들(A 반입: 1 반입용 엑셀 → 확인 완료 → 2 KOLIS 등록 / 가원부번호 전달 띠 / B 구축: 3-1 원부번호, 3-2 MODS 구축 — 반입값 대조, 작품 전체 판단, 이용제한 자동, 회차 표, 저장 본문 준비, 한 번에 넣기, 채우기, 저장 / 3-3 점검 아직).
- **①(반입용 엑셀)은 에이전트**가 한다(폴더 정리 계획, 원고·출판사 엑셀 읽기, 웹 조사, 전거 후보 조회 명령(읽기), 칸 값 결정, 자체 검사, 검수). 기준은 지침·프로세스 가이드·예시 파일 하나. 양식은 MODS 경로 열을 필요한 만큼 반복(저자·발행처·주기), 주제명은 `만화` 만.
- **②(KOLIS 등록)은 브라우저 없이 요청만으로.** 가원부번호까지. 접수번호는 `work/취소요청_목록.csv`.
- **③(원부번호 이후)**: 복본조사·완료·일괄변경은 요청 방식 기본(실패 시 Edge 화면 방식 대체). 후보 판정은 에이전트, 완료는 사람. MODS 구축은 작품 단위 에이전트 판단(전거·다른이름·주제명·UCI·성인물) → 직원 결정 반영 가능 → 회차마다 KOLIS 화면을 열어 채우고 화면의 저장 함수가 만드는 요청 본문을 가로채 둔 뒤 → 사람이 누르면 보내고 전·후 XML 대조. 첫 실제 저장 10-03(1614 1화).
- 모든 KOLIS 요청·응답은 `work/logs/`(browser-*.jsonl, ledger-batch-*.jsonl, flow-*.jsonl)에 남는다(자동화 재료, git 밖).
- 세션 시작은 `CLAUDE.md` → `docs/HANDOFF.md`(0절·4절) → `docs/EXECUTION-LOG.md`. 계획서 `docs/PLAN-2026-10-03-*.md`. 메모리 사본 `docs/memory/`.

## 실행
바탕화면 **"KOLIS 웹툰 납본 도우미"** 바로 가기(`bin\app.vbs`, 콘솔 없음) 또는:
```
.\.venv\Scripts\python.exe -m kolis_tool.app
```
전제: 클로드코드 로그인(①), KOLIS 계정(②: 창 위쪽에서 로그인하거나 `.env` 에 KOLIS_ID·KOLIS_PW), Playwright(이 PC 의 Edge 사용). Edge 에서 KOLIS 로그인은 접어 둔 단계별 버튼(옛 화면 방식)에만 필요.
결과·로그: `work\`(git 제외). 파일 로그 `work\logs\app-YYYYMMDD.log`, KOLIS 등록 실행 기록 `work\logs\flow-<작품>-<시각>.jsonl`, 취소 요청 목록 `work\취소요청_목록.csv`,
작품별 `work\<폴더>.상태.json`(진행 상태), `.작업.json`(에이전트 결과), `.로그.json`(탭 로그), 열어 둔 탭 `work\tabs.json`.

## 에이전트
- 원본: `kolis_tool/agent_home/` — `CLAUDE.md`(역할·일하는 순서), `.claude/skills/prepare-import`(납품 폴더 → 반입용 엑셀), `.claude/skills/research-work`(조사 기준),
  `.claude/agents/reviewer.md`(검수 에이전트), `knowledge/`(쌓이는 요령, 직원이 고친 내용).
- 실행할 때 `%LOCALAPPDATA%\kolis_tool\agent\` 에 펼쳐 그 안에서 돈다(저장소 밖: 저장소의 CLAUDE.md 가 섞이지 않게). 도서관 매뉴얼 원문을 `knowledge/rules/` 로 복사한다.
- 에이전트가 고친 `knowledge/*.md` 는 실행이 끝나면 저장소 원본으로 되가져온다(커밋 대상). 작업 폴더의 것이 원본이므로, 사람이 지식을 고칠 때는 작업 폴더의 파일도 같이 고친다.
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
  `import_writer.py`(83열 쓰기·검사·확인 표시 지우기), `arrange.py`(납품 폴더 정리 계획 검사·실행·되돌리기), `checks.py`(조사 결과 검사), `render.py`(페이지 열기),
  `kolis_flow.py`(② 순서·확인·취소 요청 목록), `kolis_http.py`(브라우저 없는 로그인·접속·동시 전송), `kolis_request.py`(KOLIS 요청), `kolis_modify.py`(썸네일 등록: 수정 화면의 저장 요청), `journal.py`(실행 기록),
  `kolis_ui.py`·`kolis_upload.py`·`kolis_register.py`(옛 화면 방식, 예비용), `kolis_thumbs.py`(썸네일 등록의 옛 화면 방식, 예비용), `ie_dom.py`(요청 기록 도구), `cnts_folders.py`, `ids_from_export.py`, `rename_files.py`, `logutil.py`, `templates/import_template_83.xlsx`, `templates/modify_param_spec.json`(수정 화면 저장 본문의 칸 표)
- `tools/` 개발할 때만 쓰는 도구: `recon.py`(화면 없는 Edge 로 KOLIS 화면 수집), `modify_*.py`(수정 팝업 저장 본문 대조), `upload_speed*.py`·`parallel_flow_check.py`(전송 측정). 프로그램은 브라우저를 쓰지 않는다
- `docs/HANDOFF.md` 세션 시작 지시·상태 / `docs/EXECUTION-LOG.md` 실제 진행 기록 / `docs/REQUEST-AUTOMATION.md` 요청 방식 분석 / `docs/RETROSPECTIVE-2026-10-01.md`·`docs/RETROSPECTIVE-2026-09-30.md` 시행착오 / `docs/PLAN-2026-10-01.md` 10-01 계획과 반입 규칙 14개 / `docs/BUILD-CHECK-RECON.md` 구축·점검 화면 수집 / `docs/FIELD-CHECKLIST.md` 현장 확인 / `docs/source/` 도서관 원본 자료 / `docs/memory/` 클로드코드 메모리 사본
- `bin/` app.vbs·app.bat·setup.bat, `work/` 산출물(git 제외)

계정·비밀번호는 `.env`(git 제외)와 환경변수로만. 클라이언트 원고·HAR·계정이 든 파일은 저장소에 넣지 않는다.
