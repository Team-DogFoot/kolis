---
name: kolis-no-browser-requests
description: KOLIS 자동화는 브라우저(Edge) 없이 계정으로 직접 로그인해 요청만으로. 이어서 실행 같은 장치 금지, KOLIS 가 주는 파일은 받은 그대로. 요청 형식을 알아내는 방법과 확인된 주소
metadata:
  type: feedback
---

KOLIS 단계는 **브라우저를 띄우지 않고** 프로그램이 계정으로 직접 로그인해 요청만으로 한다. 실패에 대비한 "이어서 실행" 같은 장치를 만들지 않는다(다시 실행하면 되고, 남는 접수번호는 `work/취소요청_목록.csv` 에 적어 주무관에게 취소 요청). KOLIS 가 주는 파일(전체출력 등)은 **받은 파일을 그대로** 넘기고, 값을 읽어 새 파일로 다시 만들지 않는다.

**Why:** 2026-09-30 유저 지시와 직원 검수. 그 전에 나는 (1) 로그인된 Edge 화면 안에서 요청을 보내는 방식을 골라 Edge 를 띄워 둬야 하는 조건을 붙였고 (2) 파일을 보내는 단계를 근거 없이 "불가"로 적었고 (3) 반입 두 번 방지·이어서 하기를 덧붙였고 (4) 가원부 파일을 값만 가져다 xlsx 로 새로 만들어 형식 불일치 지적을 받았다. 브라우저 없이 하니 3권(192장) 전 과정이 약 25초였다.

**How to apply:**
- 새 KOLIS 단계(썸네일, 구축, 점검)도 먼저 요청으로 만들 수 있는지 본다. 화면 조작(pywinauto)은 마지막 수단.
- 요청 형식을 알아내는 곳: ① 화면의 스크립트(로그인된 접속으로 그 화면을 GET 해서 읽음) ② 브라우저가 PC 에 남긴 파일(`%LOCALAPPDATA%\Microsoft\Windows\INetCache\IE\`) ③ 화면 방식으로 한 번 하면서 `ie_dom.py` 로 기록. 업로더(DEXT5)는 IE 모드에서 설치형 부품이라 스크립트 기록에 안 잡히지만 서버는 일반 요청 전송을 받아 준다.
- 확인된 것: 로그인 `POST /main/loginprocess.do`(uid, pwd, jsp_ip), 반입 `fileUpload.do`, 전송 `/dext5upload/handler/dext5handler.jsp`(값은 base64("R"+base64)), 가원부 파일 `POST /main/save.do`(화면이 만드는 내용을 보내면 파일로 돌아옴). 전체 목록은 `docs/REQUEST-AUTOMATION.md`, 코드는 `kolis_http.py`·`kolis_request.py`.
- 계정은 프로그램 창 로그인(환경변수) 또는 `.env` 에서만 읽는다. 유저가 대화에 적어 줘도 어디에도 옮기지 않는다. **비밀번호 5회 실패 시 계정 잠김 → 로그인은 실행당 한 번만.**
- 관련: [[kolis-automation-strategy]] [[say-unverified-and-blockers-first]] [[kolis-webtoon-project]]

(2026-10-01 추가) 썸네일도 요청으로 옮겼다(`kolis_modify.py`). 요청 형식을 알아내는 방법은 [[headless-edge-for-kolis-recon]] — 화면 없는 Edge 는 개발할 때 대조용이고 프로그램에는 넣지 않는다. 파일 전송은 연결 여러 개로 동시에 한다(연결당 약 1.2~2MB/s, 로그인 하나의 쿠키를 같이 씀).
