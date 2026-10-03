---
name: build-mods-work
description: 원부번호가 나온 웹툰 작품의 KOLIS MODS 값을 1단계 반입값(정본)과 대조해, 다른 칸·회차끼리 다른 칸·지침과 어긋나 보이는 칸을 보고하고 보정값을 제안한다(2026-10-04 개선안: 전거·주제명·UCI·다른이름은 반입에서 끝내므로 여기서는 판단하지 않는다). "MODS 대조 보정", "원부 보정" 작업에 쓴다.
---

# 작품 MODS 대조·보정 (구축 5.3, 작품 단위 — 반입값이 정본)

2026-10-04 개선안으로 저자 전거 연결·다른이름·디스플레이형식·주제명·UCI·출처정보는 **1단계 반입용 엑셀에서 끝난다**. 이 스킬은 반입 뒤 KOLIS 의 값이 반입값과 다르거나 회차끼리 다를 때만 쓴다.

입력 `jobs/<작업>/job.json` (프로그램이 KOLIS 화면을 회차마다 읽어 만든 것. 당신은 KOLIS 에 접근하지 않는다):
- `wonbu`, `title`, `count`(회차 수), `instructions`(직원 지시. 다른 기준보다 우선), `project`(사업 고정값), `manuscript`(원문 폴더 또는 `null`), `observations_dir`(1단계 관찰 파일 폴더 또는 `null`), `import_json`(1단계 반입값 파일 경로 또는 `null`)
- `episodes[]` : 회차마다 `{row, contents_id, title, part, date, isbn, publisher, place, urls, notes, authors, subject_topics, form}` (KOLIS 현재 값)
- `diffs[]` : 프로그램이 반입값과 대조해 찾은 다른 칸 `{contents_id, vol, 칸, 반입값, KOLIS, note}` (있으면)

출력 `jobs/<작업>/build.json`:
```json
{"wonbu": "", "title": "", "count": 0,
 "fixes": [{"contents_id": "", "path": "트리 경로(예 name[0].@ID, originInfo[0].publisher[0])", "kolis": "지금 KOLIS 값", "proposed": "넣을 값", "basis": "반입값|지침 n|직원 답변 n|관찰 <파일>", "reason": "", "evidence": [{"url": "", "quote": ""}]}],
 "episodes": [{"contents_id": "", "part": "", "issues": [], "notes": []}],
 "issues": [], "notes_for_staff": [""],
 "review": {"done": false, "findings": [], "resolved": []}}
```

## 0. 시작하기 전에
`knowledge/rules/build-judgment-rules.md`(직원 답변, 가이드보다 우선), `knowledge/corrections.md`, `knowledge/platform-notes.md` 를 읽는다. `import_json` 이 있으면 그것이 정본이다. `observations_dir` 가 있으면 원문을 다시 보지 않고 관찰 파일을 읽는다.

## 1. 무엇을 하는가
1. `diffs` 의 칸마다: 반입값이 맞으면 `proposed` = 반입값(basis 반입값). KOLIS 가 저장 때 스스로 바꾸는 표기(JPG↔image/jpg, BornDigital↔born digital, 개인명↔personal)는 다른 것이 아니다 → 넣지 않는다. 반입값 자체가 지침과 어긋나 보이면 `issues` 에 적고 `proposed` 를 비운다(직원 결정).
2. 회차끼리 다른 칸(표제·저자·발행처·발행지·이용대상·주기·주제명): 다수 값과 다른 회차를 `episodes[].issues` 에, 어느 쪽이 맞는지는 관찰 파일·반입값으로 적는다.
3. 직원 지시(`instructions`)에 "○○ 전거를 △△ 로" 같은 결정이 있으면 그대로 `fixes` 에(basis 직원 결정).
4. 판단하지 않는 것: 전거 연결 여부(반입값대로), 주제명(고정 두 묶음), UCI(반입값대로), 다른이름(관찰 파일에 있는 것만). 이 네 가지에서 반입값이 비어 있고 직원이 채우라고 했을 때만 `prepare-import` 5-1 의 같은 조항으로 정하고 근거를 단다.

## 2. 글투(직원이 읽는 칸: reason·issues·notes·notes_for_staff)
합니다체 완결문. 영어 낱말·필드 경로·식별번호(KAC·KSH 는 값 칸에만)·"에이전트"·"직원이"는 쓰지 않는다. 한 항목은 값 → 근거 → 요청 순.

## 3. 스스로 검사
`{PY} -m kolis_tool check-build-work "jobs/<작업>/build.json"` — 통과할 때까지 고친다. 통과시키려고 값을 지어내지 않는다.

## 4. 검수받기
검사를 통과하면 `reviewer` 에이전트에게 맡긴다(Agent 도구). 넘길 말: `build.json`·`job.json` 경로, "MODS 보정 판단 검수". 지적을 처리해 `review` 에 적고 `review.done` 을 true 로 한 뒤 3번을 다시 돌린다.

## 5. 끝
마지막 답: 결과 파일 경로, 보정 제안 수와 요지, 회차별로 다른 점, 직원이 확인할 것.
