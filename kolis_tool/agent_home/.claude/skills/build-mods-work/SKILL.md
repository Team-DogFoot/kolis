---
name: build-mods-work
description: 원부번호가 나온 웹툰 작품 하나의 전체 회차에 대해 MODS 수정 화면(KOLIS 구축 5.3)에 넣을 값을 한 번에 정한다. 반입된 MODS 값(회차 전부)과 KOLIS 전거 검색 후보를 받아, 작품 공통 판단(저자전거 연결·주제명·발행처·발행지)과 회차별 판단(UCI·다른이름·회차별 참고 사항)을 근거와 함께 하나의 결과 파일로 저장하고 스스로 검사하고 검수까지 받는다. "MODS 구축", "작품 전체 판단" 작업에 쓴다.
---

# 작품 전체 MODS 값 정하기 (구축 5.3, 작품 단위)

입력 `jobs/<작업>/job.json` (프로그램이 KOLIS 화면을 회차마다 읽어 만든 것. 당신은 KOLIS 에 접근하지 않는다):
- `wonbu`, `title`, `count`(회차 수), `instructions`(직원 지시. 다른 기준보다 우선), `project`(사업 고정값. `acquisition_note` 는 프로그램이 넣음), `manuscript`(원문 폴더 또는 `null`)
- `authors` : 작품의 저자 전부(회차마다 같은 이름은 한 번만). 저자마다 `{name, role, type, current_id, candidates}`. `candidates` 는 KOLIS 전거 검색 결과. 칸: `AC_CONTROL_NO`, `CHOICE_SIGNPOST`, `JOB`, `BRANCH`, `SUMMARY`, `ORGANIZATION`, `BIRTH_YEAR`, `BIRTH_PLACE`, `EDUCATION_LEVEL`, `CHI_NAME`, `SPECIESA_CNT`, `AC_TYPE_NAME`.
- `common` : 첫 회차의 발행처·발행지·날짜 묶음·주제명·원문주소.
- `episodes[]` : 회차마다 `{row, contents_id, title, part, date, isbn, publisher, place, urls, notes, authors, subject_topics, form}`.

출력 `jobs/<작업>/build.json` (아래 "결과 파일"). 화면에 넣고 저장하는 일은 프로그램이 회차마다 사람 확인 뒤에 한다.

## 0. 시작하기 전에
1. `knowledge/rules/build-judgment-rules.md` 를 **전부** 읽는다(직원 답변. 가이드·지침서보다 우선).
2. `knowledge/corrections.md`, `knowledge/platform-notes.md` 를 읽는다.
3. 헷갈리면 `knowledge/rules/INDEX.md` 에서 찾아 `MODS_입력가이드.md`(2. 저자정보, 2.4 다른이름, 5. 출처정보, 8. 이용대상자, 10. 주제명, 13. 식별기호)를 읽는다.

## 1. 도구
- WebSearch, WebFetch, `{PY} -m kolis_tool render "<주소>"`(옵션 `--scroll N`, `--links`, `--find "단어1|단어2"`). 명령 뒤에 다른 명령을 잇지 않는다.
- UCI 검색: `https://www.nl.go.kr/seoji/contents/S80300000000.do?page=1&pageUnit=10&schType=simple&schStr=<작품명>` (render). 같은 작품·같은 권차·같은 발행처의 UCI 만.
- 출판사 소재지: `https://book.mcst.go.kr/html/searchList.php?search_area=전체&search_state=13&search_kind=1&search_type=1&search_word=<출판사명>` (render).

## 2. 무엇을 정하는가

### 작품 공통 (한 번만)
**2-1. 저자전거 연결** — 저자마다. 후보의 상세정보(JOB·BRANCH·SUMMARY·ORGANIZATION·BIRTH_YEAR·SPECIESA_CNT)와 웹 검색 둘 다로 확인해 **강한 확신**일 때만 `link`. 후보가 전부 다른 직업이면 `none`(검색은 하되 후보 밖 사람은 연결 못 함). 동명이인 중 만화가가 둘 이상이면 대조 없이 고르지 않는다. "요청하기"는 쓰지 않는다. `confidence` 가 `high` 일 때만 `link`. `none` 이면 후보마다 왜 뺐는지 한 줄. @type 이 개인/단체와 안 맞으면 `type_change` 로 보고만.
**2-2. 주제명** — 고정 두 묶음: `topic 만화[漫畵] KSH1998022212`, `genre 웹툰[webtoon] KSH2016000049`, 전거 `국립중앙도서관주제명표목표`.
**2-3. 발행처·발행지** — 발행처는 제작사(반입값) 기본, 플랫폼이 직접 발행했을 때만 플랫폼. 바꿀 근거가 있으면 `publisher.change` 에 제안만. 발행지는 문체부 검색으로 소재지 확인 → `place.verified`/`code`.
**2-4. 성인물 여부** — 회차 요약·주기·플랫폼 표기(19세·성인)로 성인물로 판단되면 `adult: true` 와 근거. 지침(MODS 입력가이드 8): 성인물은 이용대상자 '성인용' + 이용제한 설정 + 주기 "19세 미만 구독불가". 바꾸지 말고 `adult_reason` 에 적는다(프로그램·직원이 처리).

### 회차별 (episodes 마다)
**2-5. UCI** — 회차마다 서지정보유통지원시스템에서 **그 권차**의 UCI 를 찾는다. 작품명 검색 결과가 0건이면 모든 회차에 같은 `searched` 를 적고 `value` 를 비운다(회차마다 다시 검색할 필요 없음). 결과가 있으면 권차·발행처가 맞는 것만 그 회차에.
**2-6. 다른이름** — `manuscript` 가 `null` 이면 모든 회차에서 비우고 `not_verifiable` 에 "원문 없음". 폴더가 있으면 회차 폴더의 처음·끝 이미지를 Read 로 보고 거기 적힌 것만(`source` 파일 이름, `quote` 글자 그대로). 영문은 `성, 이름`. altType: `nickname` / `formal name` / `no specific type`.
**2-7. 회차별 참고 사항** — 그 회차의 반입값이 다른 회차와 다르거나 지침과 어긋나 보이는 것(발행일·ISBN·주기·원문주소 등)은 `episodes[].issues` 에. 작품 전체에 해당하는 것은 `issues` 에.

## 3. 결과 파일 `build.json`
```json
{
 "wonbu": "", "title": "", "count": 0,
 "authors": [{"name": "", "role": "", "current_type": "personal", "decision": "link|none", "ac_control_no": "", "choice_signpost": "", "confidence": "high|medium|low",
              "reason": "", "evidence": [{"url": "", "quote": ""}], "rejected": [{"ac_control_no": "", "why": ""}], "type_change": null}],
 "subjects": [{"kind": "topic", "term": "만화[漫畵]", "id": "KSH1998022212", "authority": "국립중앙도서관주제명표목표"},
              {"kind": "genre", "term": "웹툰[webtoon]", "id": "KSH2016000049", "authority": "국립중앙도서관주제명표목표"}],
 "publisher": {"current": "", "change": null, "reason": "", "evidence": []},
 "place": {"current": "", "verified": "", "code": "", "evidence": []},
 "adult": false, "adult_reason": "",
 "episodes": [{"contents_id": "", "part": "",
               "uci": {"value": "", "evidence": [{"url": "", "quote": ""}], "searched": [{"where": "", "how": ""}]},
               "alternative_names": [{"author": "", "name": "", "alt_type": "nickname|formal name|no specific type", "source": "원문 <파일>", "quote": ""}],
               "not_verifiable": [], "issues": [], "notes": []}],
 "manuscript_seen": [{"file": "", "text": ""}],
 "issues": [], "notes_for_staff": [""],
 "review": {"done": false, "findings": [], "resolved": []}
}
```
`episodes` 는 job 의 회차 **전부**에 대해 하나씩(contents_id 로 짝). `link` 인 저자는 `evidence` 1개 이상, `ac_control_no` 는 후보 안의 값.

### 글투(직원이 읽는 칸: reason·why·issues·notes·notes_for_staff·adult_reason)
합니다체 완결문. 지시는 "…하십시오". 영어 낱말·필드 경로·식별번호(KAC·KSH 는 값 칸에만)·"에이전트"·"직원이"는 쓰지 않는다. 한 항목은 값 → 근거 → 요청 순.

## 4. 스스로 검사
`{PY} -m kolis_tool check-build-work "jobs/<작업>/build.json"` — 통과할 때까지 고친다. 통과시키려고 값을 지어내지 않는다.

## 5. 검수받기
검사를 통과하면 `reviewer` 에이전트에게 맡긴다(Agent 도구). 넘길 말: `build.json`·`job.json` 경로, "MODS 구축 판단 검수(작품 단위)". 지적을 처리해 `review` 에 적고 `review.done` 을 true 로 한 뒤 4번을 다시 돌린다.

## 6. 배운 것 적기
전거 대조 요령 등 다음 작품에도 쓸 것만 `knowledge/platform-notes.md` 에.

## 7. 끝
마지막 답: 결과 파일 경로, 저자마다 연결/미연결 한 줄, 성인물 여부, UCI 유무, 회차별로 다른 점이 있으면 요약, 직원이 확인할 것.
