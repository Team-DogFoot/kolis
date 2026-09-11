# kolis — 웹툰 납본·수집 대행 KOLIS 자동화 (human-in-the-loop)

국립중앙도서관 "웹툰 납본·수집 대행 사업"의 수집·등록·구축·점검 절차를 반자동화하는 도구.
사람이 판정해야 하는 지점(복본 판정, 반입 엑셀 최종 확인, 전거 연결 승인, 점검 결과 확정)은 남기고
그 사이의 손작업(파일 검수, 파일명 변경, 엑셀 변환, MODS 추출·점검)을 프로그램이 한다.

## 현재 상태 (2026-09-12)
- 도서관 PC 접속 전 단계. KOLIS 화면·폼은 아직 미확인.
- 샘플 파일(미스터블루 로맨스낫로맨틱 45화, 완료된 반입용 엑셀 포함)로 `inspect` `rename` `convert` `mods-check` 검증 완료.
  `convert` 는 완료 사례와 88열 중 55열이 45행 전부 일치. 나머지 33열은 설계상 LLM/사람 몫(권차 표기, 역할어, 발행지, 임프린트, URL, 썸네일 파일명)이며 노란색으로 표시됨.
- `agent`(LLM 보완)와 `mods-fetch`(KOLIS HTTP)는 API 키·현장 HAR 확인 전이라 미검증.
- 다음 단계: `docs/HANDOFF.md` 참조.

## 설치
```
python -m venv .venv && .venv\Scripts\activate      (윈도)
pip install -r requirements.txt
```

## 단계별 실행(윈도)
`bin\setup.bat` 한 번 → `bin\1_inspect.bat` → `2_rename` → `3_convert` → `4_agent` → `5_check`. 각 단계는 끝나면 멈추고 사람이 결과를 확인한다.

## 명령
```
python -m kolis_tool inspect  <원문 상위폴더>            # 검수 → out/inspect.xlsx
python -m kolis_tool rename   <원문 상위폴더> [--dry-run|--undo]
python -m kolis_tool convert  <출판사용.xlsx> --template <반입용 양식.xlsx> -o <반입용 출력.xlsx> --root <원문 상위폴더>
python -m kolis_tool agent    <반입용 출력.xlsx> --root <원문 상위폴더> [--dry-run] [--limit N] [--apply]
python -m kolis_tool ids <전체출력.xls> -o work/ids.txt                          # 콘텐츠ID 목록
python -m kolis_tool mods-fetch work/ids.txt [--preview] -o work/xml --config kolis.json     # HAR 확인 후
python -m kolis_tool mods-check work/xml --wonbu <원부번호> --nth 1               # 점검용 xlsx
```

## 폴더
- `kolis_tool/` 도구 본체. `mods_labels.json`(한글 항목명 74개, 정리 매크로에서 추출), `import_template_header.json`(반입 양식 77열)
- `docs/rulebook/mods-input-guide.md` MODS 입력가이드 규칙집(LLM system 프롬프트용), `ebook-guideline-ch3.md` 전자책 정리 지침 3장
- `tests/fixtures/` 가이드 캡처에서 옮겨 적은 실제 형식의 MODS XML
- `bin/` 단계별 실행 배치, `kolis.example.json` 로그인 폼 설정 예시
- `docs/HANDOFF.md` 도서관 PC 세션 시작용 인수인계
- `docs/FIELD-CHECKLIST.md` 현장 확인 목록
- `scripts/build_rulebook.py` 가이드 docx → 규칙집 재생성

클라이언트 원문(문서·샘플·정답지)은 저장소에 넣지 않는다. 계정·비밀번호는 환경변수(KOLIS_ID, KOLIS_PW, ANTHROPIC_API_KEY)로만.
