---
name: headless-edge-for-kolis-recon
description: KOLIS 요청 형식을 알아내는 가장 빠른 방법 — 화면 없는 Edge 에 화면을 띄워 그 화면의 스크립트가 만드는 본문을 뜬다(개발용, 프로그램에는 넣지 않음)
metadata:
  type: project
---

KOLIS 의 새 요청을 만들 때는 본문을 추측하거나 화면의 스크립트를 손으로 옮기지 말고, **화면 없는 Edge(Playwright `channel="msedge", headless=True`)에 그 화면을 띄워 화면의 스크립트가 만드는 본문을 뜬 뒤** 파이썬 본문을 그것과 대조한다. 도구는 저장소의 `tools/recon.py`(화면 수집), `tools/modify_truth.py` 등.

방법: `kolis_http.Client` 로 로그인해 쿠키를 얻음 → 헤드리스 컨텍스트에 쿠키 넣음 → 팝업은 부모 창 대역(같은 출처의 빈 페이지에 `grid`·`$`·`bindDataToGrid`)을 만들고 `window.open` → 화면의 함수(`getParam()`, `serializeObject(폼)`)를 불러 본문을 저장. 저장 버튼은 누르지 않는다. 실제로 보내야 할 때만 취소할 접수 건으로.

**Why:** 2026-10-01 썸네일 등록에서 수정 팝업의 저장 본문(서지 146칸)을 손으로 옮기려다 막혔고, 이 방법으로 한 시간 안에 요청만으로 되는 코드가 나왔다. IE 모드 전용이라던 수정 팝업·원문등록 팝업도 크롬 엔진에서 스크립트가 돈다(업로더 부품만 IE 전용). KOLIS 는 http 라 Somansa 가로채기와 무관하다.

**How to apply:** 구축·점검 등 새 화면의 요청을 만들 때 먼저 `tools/recon.py` 로 화면을 띄운다. 깃 배시에서는 `MSYS_NO_PATHCONV=1`. 이것은 **개발할 때 대조용**이다 — 프로그램은 브라우저를 쓰지 않는다([[kolis-no-browser-requests]]). 무거운 조회(`listAccRec.do` 는 4분 넘게 응답 없음)는 다시 보내지 않는다. 관련: [[kolis-webtoon-project]] [[say-unverified-and-blockers-first]]
