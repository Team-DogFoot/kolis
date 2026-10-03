# Memory Index

- [kolis-webtoon-project](kolis-webtoon-project.md) — 웹툰 납본 KOLIS 자동화: 합의(09-12·18·29·30, 10-01, 10-03), 프로그램 구조(1 반입용 엑셀 + 확인 완료 버튼, 2 KOLIS 등록 브라우저 없이, 3 원부번호 이후 Edge+Playwright 반자동 + build-mods 에이전트), 복본조사 고정 탭(과장님), 요청 방식 기본, 1614 1화 저장·2화 본문 준비 상태. 세션 시작은 docs/HANDOFF.md
- [kolis-no-browser-requests](kolis-no-browser-requests.md) — ①구간 KOLIS 는 브라우저 없이 요청만으로(③구간은 Edge+Playwright 반자동 먼저); 이어서 실행 금지; KOLIS 가 주는 파일은 받은 그대로; 요청 형식을 알아내는 방법
- [say-unverified-and-blockers-first](say-unverified-and-blockers-first.md) — 안 될 것·확인 안 된 것은 그 자리에서 말하고, '불가' 전에 다른 방법을 찾고, 기준 자료의 출처를 확인한다
- [agent-first-fixed-output](agent-first-fixed-output.md) — 에이전트를 제대로 쓴다(스스로 도는 루프·스킬·검수·지식), 고정 코드는 양식 쓰기·검사만
- [test-through-the-program](test-through-the-program.md) — 시험은 실제 프로그램 창으로, 두 번 돌려 같은지 확인; 에이전트 결과가 흔들리면 보고 전에 원인을 고친다
- [kolis-automation-strategy](kolis-automation-strategy.md) — (예비) KOLIS 화면 방식의 함정 목록과 요청 기록 방법. 썸네일 등록·새 화면 조사에 씀
- [user-profile](user-profile.md) — 웹백엔드/데브옵스 개발자, 도커+FastAPI 운영 선호, 비개발자용 포장 필요
- [never-reduce-scope-on-my-own](never-reduce-scope-on-my-own.md) — 유저가 정한 범위를 비용 이유로 임의 축소 금지
- [question-means-answer-only](question-means-answer-only.md) — 질문에는 답변만, 행동은 명시 지시가 있을 때만
- [check-official-docs-first](check-official-docs-first.md) — 동작 확인은 임의 테스트 말고 공식문서부터
- [somansa-dlp-tls-interception](somansa-dlp-tls-interception.md) — 도서관 PC 의 HTTPS 는 Somansa DLP 가 가로챔; 클로드코드는 NODE_EXTRA_CA_CERTS, Playwright Node 쪽은 CA 키가 약해 거부
- [remote-control-keepalive-setup](remote-control-keepalive-setup.md) — 도서관 PC: 원격 제어를 숨은 스케줄 작업으로 상시 실행; 이름 변경은 bridge-pointer.json 삭제
- [headless-edge-for-kolis-recon](headless-edge-for-kolis-recon.md) — KOLIS 요청 형식은 화면 없는 Edge 에 화면을 띄워 그 스크립트가 만드는 본문을 떠서 알아낸다(개발용, 프로그램에는 넣지 않음)
- [read-code-before-explaining](read-code-before-explaining.md) — 설명하기 전에 그 경로의 코드를 읽는다; 질문에는 먼저 예/아니오와 방법
- [kolis-roadmap-abstraction](kolis-roadmap-abstraction.md) — 프로그램 장기 구조: 자료 종류(최대 32종) › 작품 › 단계 A/B › 하위 단계; 내부 로직은 당장 안 바꾸되 종류별로 갈라질 지점(양식·스킬·코드·고정값)과 공통 지점을 알고 개발; 회차별 원문 관찰 기록
- [no-translationese-korean](no-translationese-korean.md) — 화면·에이전트 글·브리핑에 번역체 금지(~에 대해, ~되었습니다, 진행 중, 영어 낱말, 제3자 시점 '직원 입회'); 동사로 짧게, 다음 행동으로
- [import-quality-by-guide-only](import-quality-by-guide-only.md) — 반입용 엑셀 에이전트 품질은 지침·가이드·예시 하나로만; 채점 틀 금지; 전거·주제명 번호를 엑셀에 안 끼움(10-03)
