---
name: kolis-webtoon-project
description: 국립중앙도서관 웹툰 납본 대행 KOLIS 자동화 — 09-12 합의 방향, 도구 상태, 제약. 저장소 Team-DogFoot/kolis, 세션 시작은 docs/HANDOFF.md
metadata:
  type: project
---

**무엇:** 국립중앙도서관 "웹툰 납본·수집 대행 사업"(KOLIS 등록·MODS 구축·점검, 50,000건) 반자동화. 저장소 `~/works/dog-foot/kolis` (github Team-DogFoot/kolis, 비공개). 저장소 루트 `CLAUDE.md`와 `docs/HANDOFF.md`가 같은 내용을 담고 있으니 도서관 PC에서도 그걸 읽으면 됨.

**2026-09-12 유저 확정(바꾸지 말 것):** human-in-the-loop(복본 판정·반입 엑셀 확인·전거 승인·점검 확정은 사람) / MODStoXL.exe·정리매크로·다크네이머·하이웨어 SFTP 안 씀(파이썬 대체, 썸네일 건별) / 윈도 네이티브 파이썬+클로드코드 / 일반 화면 Playwright, IE모드 3화면(일괄반입·원문일괄등록·썸네일)은 1차 수동 / LLM은 claude -p 헤드리스(exec)가 1순위, API는 대량 처리 대안, 웹 리서치 포함 / 1차 명령줄, 완성 후 pywebview+FastAPI UI(일렉트론 X) / 1차 목표=실제 접수 1건을 ①~⑤ 전 과정 통과(도구 없는 단계는 그 자리에서 손으로, 뒤로 미루지 않음) / 계정은 환경변수만, 참고자료 PDF 평문 계정 절대 옮기지 않음 / USB 불가·외부망 가능.

**도서관 요구(유저 재확인):** KOLIS 요청은 직원 입회·요청·동의 아래에서만. 그 조건이면 브라우저 조작·computer use 등 전부 허용. 금지는 '테스트·검증' 명목의 무분별한 요청(콘텐츠ID 시험 조회 포함). 검증은 HAR·저장 응답·--preview로만, 첫 실제 실행은 실제 작품으로 직원과 함께 진짜 제출하면서.

**Why:** 한 번 논의로 확정한 사항이라 다음 세션이 되묻지 않게 하기 위해.
**How to apply:** 세션 시작 시 `docs/HANDOFF.md` → `docs/FIELD-CHECKLIST.md`. 출판사 zip은 `kolis_tool unzip`으로(한글 cp949). 관련: [[user-profile]] [[never-reduce-scope-on-my-own]]
