---
name: kolis-webtoon-project
description: 국립중앙도서관 웹툰 납본 대행 KOLIS 자동화 — 합의 방향, 프로그램 상태(7단계), 진행 중인 실제 작업(811 썸네일 116건 남음). 세션 시작은 docs/HANDOFF.md
metadata:
  type: project
---

**무엇:** 국립중앙도서관 "웹툰 납본·수집 대행 사업"(KOLIS 등록·MODS 구축·점검, 50,000건) 반자동화. 저장소 `C:\Users\User\dataclip\kolis`(github Team-DogFoot/kolis). 세션 시작은 `CLAUDE.md` → `docs/HANDOFF.md` 0절 → `docs/EXECUTION-LOG.md`.

**2026-09-12 확정(바꾸지 말 것):** human-in-the-loop(복본 판정·반입 엑셀 확인·전거 승인·점검 확정은 사람) / MODStoXL·정리매크로·다크네이머·하이웨어 안 씀 / 윈도 파이썬+클로드코드 / KOLIS 요청은 직원 입회·동의 아래에서만, 시험 요청 금지 / 계정은 환경변수만.

**2026-09-18 확정:** "1차 명령줄" 대신 **처음부터 pywebview 창 프로그램**, 기능을 하나씩 추가 / 전략: UI 자동화 반자동으로 ①~⑤ 끝까지 → 실제 업무 HAR 관찰 → HTTP 완전 자동화 / 발행일은 회차별 가장 이른 공개일 / LLM=판단, 코드=수집 / ClipToon(직원 도구)은 참고만 / 썸네일 등록은 유저 정의 절차(HANDOFF 3절 7단계).

**상태(2026-09-19 00:10):** 프로그램 7단계 완성·검증. 실제 작업 5-219 '폐급에서 성주까지 레벨업'(접수번호 811, 123건): 일괄반입·원문일괄등록·일괄정보입력·원문등록 완료, 썸네일 7/123. **다음: 7단계로 116건 등록(접수번호 811, 건수 0).** 케나즈 5-203 은 반입용 엑셀까지(직원 확인 대기). HAR 는 아직 없음(IEChooser 로 받을 것).

**Why:** 다음 세션이 상태를 되묻지 않게. **How to apply:** 코드를 고치면 `pythonw` 를 죽이고 바탕화면 바로 가기로 앱을 재시작한다. 실행 기록은 EXECUTION-LOG 에 시각과 함께. 관련: [[kolis-automation-strategy]] [[user-profile]] [[never-reduce-scope-on-my-own]] [[question-means-answer-only]]
