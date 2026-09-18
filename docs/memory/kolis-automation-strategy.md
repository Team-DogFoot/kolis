---
name: kolis-automation-strategy
description: "KOLIS 자동화 2단계 전략(유저 확정 2026-09-18) — 지금은 UI 자동화 반자동, HAR 관찰 후 HTTP 완전 자동화. 배운 KOLIS 특성 목록."
metadata: 
  node_type: memory
  type: project
  originSessionId: 3409b88b-b819-4b29-ba49-d0dc1d8c2eb1
  modified: 2026-09-18T13:33:39.375Z
---

**전략(유저 확정 2026-09-18):** ① 먼저 pywinauto UI 자동화 + 사람 확인 지점으로 ①~⑤ 전 과정을 반자동 완성. ② 실제 업무 때 IEChooser 로 HAR 를 켜 두고 요청·응답을 분석해 HTTP 클라이언트로 교체(완전 자동화). 테스트 데이터가 없어 시험 요청 불가 → 진짜 업무 관찰 후에만 HTTP 로 옮긴다. Playwright 는 IE 모드를 못 다루므로 중간 단계로 쓰지 않는다.

**KOLIS 에서 확인된 사실:** 주소 직접 입력 시 로그인 풀림(메뉴 경로 필수) / IE 모드 화면 요소는 UIA 이름으로 잡힘, confirm 창은 Win32 '웹 페이지 메시지', 파일 대화상자는 '업로드할 파일 선택' / 팝업 클릭은 set_focus 후 / '반입' 뒤 진행 확인창 + 완료까지 수 분 / 전체출력은 SpreadsheetML(.xls) / 원문일괄등록 DEXT5 진행창은 UIA·win32 로 안 읽힘(화면 캡처만) / 원고 폴더 안에 기록 파일이 있으면 업로드가 멈춤(기록은 `_kolis_manifests/` 로).

**How to apply:** 새 KOLIS 단계를 붙일 때 먼저 UIA 로 요소 이름을 확인하고 `kolis_ui.py` 의 `_act`(재시도) 패턴으로 만든다. 실제 실행은 직원 입회 하에, 그때 HAR 도 같이 남긴다. 관련: [[kolis-webtoon-project]]
