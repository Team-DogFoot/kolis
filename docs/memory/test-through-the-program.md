---
name: test-through-the-program
description: 시험은 명령줄·임시 스크립트가 아니라 실제 프로그램 창(직원이 쓰는 경로)으로 한다; 에이전트는 사실만 모으고 결론은 코드 규칙으로
metadata:
  node_type: memory
  type: feedback
  originSessionId: 22e5ecb0-8fe0-458a-a579-69788bfa310b
  modified: 2026-09-29T12:51:17.648Z
---

기능을 만들면 **실제 프로그램 창의 버튼을 눌러** 시험한다. 명령줄이나 임시 스크립트로 함수를 직접 불러 확인한 것은 시험으로 치지 않는다. 같은 작품을 두 번 돌려 결과가 같은지도 확인한다.

**Why:** 이 프로그램은 도서관 직원(비개발자)이 창으로 쓰는 도구다. 2026-09-29 에 명령줄로만 돌려 놓고 "시험했다"고 보고해 유저가 크게 화냈다("누구를 위한 작업인지 모르느냐"). 같은 날 에이전트 조사 결과가 실행마다 달랐는데(최초 연재 플랫폼이 리디/미스터블루로 갈림) 그걸 당연한 듯 보고한 것도 지적받았다. 원인은 결론을 에이전트에게 맡긴 설계였다.

**How to apply:** 창 조작은 `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--remote-debugging-port=9223` 을 준 뒤 `bin\app.vbs` 로 띄우고 Playwright `connect_over_cdp` 로 실제 버튼을 누른다(UIA 로는 창 안 요소가 안 잡힘). 결과가 흔들리면 보고하기 전에 원인을 고친다. 단, 고치는 곳은 코드가 아니라 에이전트 쪽(스킬의 판단 기준·완료 기준, 검수 에이전트, 지식 기록)이다 — 결론을 코드 규칙으로 빼앗는 방식은 같은 날 유저가 거부했다([[agent-first-fixed-output]]). 금액은 보고하지 않는다(구독). 관련: [[agent-first-fixed-output]] [[kolis-webtoon-project]]
