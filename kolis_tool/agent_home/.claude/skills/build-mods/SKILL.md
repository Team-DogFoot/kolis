---
name: build-mods
description: 원부번호가 나온 웹툰 회차 하나의 MODS 수정 화면(KOLIS 구축 5.3)에 넣을 값을 정한다. 반입된 MODS 값과 KOLIS 전거 검색 후보(프로그램이 떠서 준 것)를 받아 저자전거 연결 여부, 다른이름, 주제명 두 묶음, UCI, 발행처를 근거와 함께 정하고 결과 파일로 저장하고 스스로 검사하고 검수까지 받는다. "MODS 구축", "서지 보완" 작업에 쓴다.
---

# MODS 수정 화면에 넣을 값 정하기 (구축 5.3)

입력 `jobs/<작업>/job.json` (프로그램이 KOLIS 화면에서 읽어 만든 것. 당신은 KOLIS 에 접근하지 않는다):
- `contents_id`, `wonbu`(원부번호), `title`, `part`(권차), `publisher_says`(출판사 엑셀·반입값), `form`(MODS 수정 화면의 현재 칸 값 전부, 칸 이름 = MODS 요소 경로)
- `authors` : 저자마다 `{name, role, type, candidates:[…]}`. `candidates` 는 KOLIS 전거 검색 결과(동명이인 전부). 칸: `AC_CONTROL_NO`(전거 번호 KAC…), `CHOICE_SIGNPOST`(채택표목), `JOB`(직업), `BRANCH`(분야), `SUMMARY`(요약), `ORGANIZATION`(소속), `BIRTH_YEAR`, `BIRTH_PLACE`, `EDUCATION_LEVEL`, `CHI_NAME`, `SPECIESA_CNT`(이 전거가 붙은 자료 수), `AC_TYPE_NAME`(개인명/단체명)
- `manuscript` : 원문(으뜸정보원) 폴더 경로(회차 폴더들이 든 상위 폴더) 또는 이전 단계의 관찰 기록 파일. 없으면 `null` — 그러면 원문으로만 정할 수 있는 값(다른이름)은 "원문 없음"으로 보고한다.
  - 폴더가 주어지면: 그 안에서 **이 회차**(`part`, `title`, `contents_id` 로 짝짓는다. 폴더 이름이 `CNTS-…` 면 contents_id 와 같은 것, 아니면 권차 표기가 맞는 것)의 폴더를 찾아 **처음 2~3장과 마지막 2~3장을 Read 로 직접 본다**(표제면·타이틀컷·크레딧·판권면). 거기 적힌 저자 표기·다른 이름(영문·본명·필명)·발행처 표기를 글자 그대로 `manuscript_seen` 에 적는다. 다른이름은 **여기서 본 것만** 넣는다(`source` 에 파일 이름, `quote` 에 글자 그대로).
  - 회차 폴더를 못 찾으면 어떤 폴더들이 있었는지 `not_verifiable` 에 적고 다른이름은 비운다.
- `instructions` : 직원이 이 작품에 적은 지시. 다른 모든 기준보다 우선.
- `project` : 이번 사업의 고정값(프로그램 설정). `acquisition_note` = 입수처 주기(@type acquisition)에 들어가야 할 문장. 프로그램이 넣으므로 당신은 반입값의 주기가 이것과 다르거나 없으면 `issues` 에만 적는다.

출력 `jobs/<작업>/build.json` (아래 "결과 파일"). 화면에 넣고 저장하는 일은 프로그램이 사람 확인 뒤에 한다.

## 0. 시작하기 전에
1. `knowledge/rules/build-judgment-rules.md` 를 **전부** 읽는다. 직원이 현장에서 답한 기준이며 가이드·지침서보다 우선한다.
2. `knowledge/corrections.md`, `knowledge/platform-notes.md` 를 읽는다.
3. 헷갈리는 항목은 `knowledge/rules/INDEX.md` 에서 찾아 `MODS_입력가이드.md`(2. 저자정보, 2.4 다른이름, 5. 출처정보, 10. 주제명, 13. 식별기호)를 읽는다. 그림은 Read 로 열어 본다.

## 1. 도구
- WebSearch, WebFetch, `{PY} -m kolis_tool render "<주소>"`(자바스크립트 페이지. 옵션 `--scroll N`, `--links`, `--find "단어1|단어2"`). 명령 뒤에 다른 명령을 잇지 않는다.
- UCI 검색(국립중앙도서관 서지정보유통지원시스템): `https://www.nl.go.kr/seoji/contents/S80300000000.do?page=1&pageUnit=10&schType=simple&schStr=<작품명>` — render 로 연다. 결과에서 **같은 작품·같은 권차·같은 발행처**의 UCI 만 고른다.
- 출판사 소재지(문체부 출판사/인쇄사 검색): `https://book.mcst.go.kr/html/searchList.php?search_area=전체&search_state=13&search_kind=1&search_type=1&search_word=<출판사명>` — render 로 연다.

## 2. 무엇을 정하는가

### 2-1. 저자전거 연결 (저자마다 따로. 글·그림이 달라도 각각)
- 기준(직원 2026-10-03): 후보의 **상세정보**(JOB·BRANCH·SUMMARY·ORGANIZATION·BIRTH_YEAR·SPECIESA_CNT)와 **웹 검색** 둘 다로 확인해, 그 전거가 **이 작품의 저자라는 강한 확신**이 들 때만 연결한다. 이름만 같은 것은 일치가 아니다.
- 순서: ① 후보 중 직업·분야가 만화가·웹툰 작가·일러스트레이터·작가인 것을 고른다. 전부 다른 직업(가수·교수·연구원 등)이면 **연결하지 않는다**(검색은 해 보되, 후보 밖의 사람을 연결할 수는 없다). ② 남은 후보는 웹에서 대조한다: 이 작품의 플랫폼 작가 페이지, 작가의 다른 작품 목록, 출판사 소개. 후보의 SUMMARY·BRANCH 에 그 작품·활동이 보이거나, 후보가 붙은 다른 자료가 같은 작가의 작품이면 확신이 선다. ③ 동명이인 중 만화가가 둘 이상이면 대조 없이 고르지 않는다.
- "요청하기"(새 전거 요청)는 쓰지 않는다.
- 결정은 `link`(AC_CONTROL_NO 하나) 또는 `none`. `confidence` 는 `high` 일 때만 `link`. `reason` 에 무엇이 맞았는지(직업·작품·소속)와 웹에서 본 글자를 적는다. `none` 이면 어떤 후보를 왜 뺐는지 한 줄씩.
- 저자 @type: 개인이면 `personal`, 스튜디오·팀·회사면 `corporate`. 웹 검색으로 확인하고 현재 값과 다르면 `type_change` 로 보고(바꾸지 않고 사람이 정한다).

### 2-2. 다른이름 (저자마다)
- **원문(으뜸정보원)에 적힌 경우에만** 넣는다(직원 2026-10-03). 플랫폼·포털·SNS·출판사 엑셀만으로는 넣지 않는다.
- 영문 표기는 `성, 이름` 꼴. 유형(altType): 필명(저자명이 본명일 때) `nickname`, 본명(저자명이 필명일 때) `formal name`, 그 밖(영문·도치형 등) `no specific type`.
- `manuscript` 가 `null` 이면 `alternative_names` 를 비우고 `not_verifiable` 에 "원문 없음 — 직원이 원문(표제면·판권기·표지)에서 확인"을 적는다. 조사로 찾은 영문명·본명이 있으면 **넣지 말고** `notes_for_staff` 에 "원문에 있으면 넣을 수 있음: …"으로 적는다.

### 2-3. 주제명 (고정)
- 묶음 2개: `{"kind":"topic","term":"만화[漫畵]","id":"KSH1998022212"}`, `{"kind":"genre","term":"웹툰[webtoon]","id":"KSH2016000049"}`. 전거는 둘 다 `국립중앙도서관주제명표목표`. 장르물이어도 이 둘만. MODS `genre` 요소(만화)는 그대로.

### 2-4. UCI
- 서지정보유통지원시스템에서 작품명으로 검색해 **이 권차·이 발행처**의 UCI 를 찾는다. 찾으면 `uci.value` 와 근거(주소 + 화면 글자). 없으면 `uci.value` 를 비우고 `uci.searched` 에 검색어·주소를 적는다. 다른 권차의 UCI 를 넣지 않는다.

### 2-5. 발행처·발행지 확인
- 발행처는 **제작사가 기본**(반입값). 플랫폼이 직접 발행한 자료일 때만 플랫폼. 반입값이 기준과 다르면 `publisher.change` 에 제안하고 근거를 적는다(바꾸지 않는다).
- 발행지가 `[서울]`/`ulk` 같은 추정값이면 문체부 출판사 검색으로 소재지를 확인해 `place.verified` 에 적는다(시/도 → 부호표는 `MODS_입력가이드.md` 5.1).

### 2-6. 그 밖
- 반입값 중 지침과 어긋나 보이는 것(콘텐츠유형·장르·분류 810·주기 문형·원문주소 등)은 `issues` 에만 적는다. 바꾸지 않는다.

## 3. 결과 파일 `build.json`
```json
{
 "contents_id": "", "title": "", "part": "",
 "authors": [{"name": "", "role": "", "current_type": "personal",
              "decision": "link|none", "ac_control_no": "", "choice_signpost": "", "confidence": "high|medium|low",
              "reason": "", "evidence": [{"url": "", "quote": ""}],
              "rejected": [{"ac_control_no": "", "why": ""}],
              "type_change": null,
              "alternative_names": [{"name": "", "alt_type": "nickname|formal name|no specific type", "source": "원문 <파일>", "quote": ""}],
              "not_verifiable": []}],
 "subjects": [{"kind": "topic", "term": "만화[漫畵]", "id": "KSH1998022212", "authority": "국립중앙도서관주제명표목표"},
              {"kind": "genre", "term": "웹툰[webtoon]", "id": "KSH2016000049", "authority": "국립중앙도서관주제명표목표"}],
 "uci": {"value": "", "evidence": [{"url": "", "quote": ""}], "searched": [{"where": "", "how": ""}]},
 "publisher": {"current": "", "change": null, "reason": "", "evidence": []},
 "place": {"current": "", "verified": "", "code": "", "evidence": []},
 "issues": [{"field": "", "current": "", "note": ""}],
 "manuscript_seen": [{"file": "", "text": "화면에 적힌 글자 그대로"}],
 "notes_for_staff": [""],
 "review": {"done": false, "findings": [], "resolved": []}
}
```
`evidence.quote` 는 화면에 적힌 글자 그대로. `link` 인 저자는 `evidence` 가 1개 이상, `ac_control_no` 는 `candidates` 안의 값이어야 한다.

## 4. 스스로 검사
`{PY} -m kolis_tool check-build "jobs/<작업>/build.json"` — 통과할 때까지 고친다. 통과시키려고 값을 지어내지 않는다.

## 5. 검수받기
검사를 통과하면 `reviewer` 에이전트에게 맡긴다(Agent 도구). 넘길 말: `build.json` 과 `job.json` 경로, "MODS 구축 판단 검수". 지적을 처리해 `review` 에 적고 `review.done` 을 true 로 한 뒤 4번을 다시 돌린다.

## 6. 배운 것 적기
전거 대조 요령(어느 사이트가 작가 정보를 잘 보여 주는지 등)을 `knowledge/platform-notes.md` 의 "도구"나 "플랫폼" 단락에 적는다. 작품 하나에만 해당하는 사실은 적지 않는다.

## 7. 끝
마지막 답: 결과 파일 경로, 저자마다 연결/미연결과 한 줄 이유, UCI 유무, 직원이 확인할 것.
