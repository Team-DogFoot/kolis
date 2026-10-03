# 개선안 — 반입용 메타데이터 작성(1단계)에서 모든 것을 끝낸다 (2026-10-04, 맥북에서 작성 · 같은 날 리뷰 48건 반영 · ①~④ 구현 끝)

이 문서는 2026-10-04 유저 결정에 따라 1단계(납품 폴더 → 반입용 엑셀)를 다시 설계한 개선안이다. 처음 읽는 사람(다른 PC, 다른 모델일 수 있는 다음 세션)이 맥락 없이도 따라갈 수 있게, 요약하지 않고 전부 적는다.
**읽는 순서**: `CLAUDE.md` → `docs/HANDOFF.md` → 이 문서 → `docs/BUILD-CHECK-RECON.md` 9절(반입 헤더 시험) → `docs/MODS-FIELDS.md`(MODS 칸의 모수) → `docs/PLAN-2026-10-03-IMPORT-QUALITY.md`(전 계획, 이 문서가 대체).
**이 문서와 다른 문서가 다르면 이 문서가 우선**이다(더 나중의 유저 확정). 특히 `PLAN-2026-10-03-IMPORT-QUALITY.md` 의 "전거 번호·주제명 번호·둘째 출처정보를 끼워 넣지 않는다"와 3-2 "한 번에 입력" 기본 경로는 이 문서로 폐기된다.

이 문서를 쓰기 전에 읽은 것: 프로젝트 지침 3개(`~/CLAUDE.md`, `dog-foot/CLAUDE.md`, 이 저장소 `CLAUDE.md`), `docs/HANDOFF.md` 전체, `docs/FIELD-CHECKLIST.md`, `docs/PLAN-2026-10-01.md`, `docs/PLAN-2026-10-03-IMPORT-QUALITY.md`, `docs/EXECUTION-LOG.md` 10-03 항목, `docs/BUILD-CHECK-RECON.md` 9절, `docs/MODS-FIELDS.md`, `docs/source/text/MODS_입력가이드.md`(0.2·0.3·1·2·5·7·8·9·10·12·13·14절), `docs/source/text/IMAGE-NOTES-mods-guide.md`·`IMAGE-NOTES-process-guide.md`, `docs/source/text/웹툰납본프로세스가이드_v1.0.txt` 3.2·5.3절, `docs/source/text/웹툰대행사업_매뉴얼_v1.6.md` 3.1절, `docs/rulebook/build-judgment-rules.md`, `kolis_tool/agent.py`, `kolis_tool/prepare.py`, `kolis_tool/import_writer.py`, `kolis_tool/checks.py`(check_research), `kolis_tool/inspect_files.py`, `kolis_tool/authority.py`, `kolis_tool/mods_batch.py`(collect_work), `kolis_tool/agent_home/CLAUDE.md`, 스킬 `prepare-import`·`research-work`·`build-mods-work`, 검수 에이전트 `reviewer.md`, 지식 파일 `platform-notes.md`·`corrections.md`, `tools/import_probe.py`, 예시 파일 `docs/source/3_샘플양식/완료사례_코리스반입용_로맨스낫로맨틱(88열).xlsx` 의 Contents 머리글·2행 값과 템플릿 `kolis_tool/templates/import_template_83.xlsx` 머리글 대조.

---

## 0. 유저 결정 원문 (2026-10-04, 바꾸지 말 것)

유저가 한 말을 그대로 옮긴다. 이 문서의 모든 설계는 이 네 줄에서 나온다.

1. "내 목적은 무조건 가능한, 최대한 최초 '반입용 메타데이터 작성'에서 모든걸 끝내고 싶다. 최종 실험도 이걸 위함이었어."
2. "mods 헤더는 고정하지 말자. 왜냐면 실험한 내용들중에 반복이 가능한것들이 있는데 그것들을 작품마다 유동적으로 반복할 수 있어야해. 그럴려면 헤더를 스트릭하게 고정하면 안될것 같다."
3. "위의 목적을 달성하기 위해선 서버든 벡엔드든 에이전트든 헤드리스든 ui ux 든 만들어둔 코드든 절대로 하위호환성 신경쓰지말고 필요하면 전부다 갈아엎어서라도 구현해야한다."
4. (2 의 보충) "2 묶음 으로 고정하는것도 아니지. 그 이상있으면 더 여러 묶음으로 작성해야지."

같은 날 앞서 유저가 적은 상황: "원래 작업하던 내부망 컴퓨터에서 작업을 마무리 하고 내 개인 맥북으로 환경을 옮겼다." / "오늘은 그래서 kolis에 요청을 보내는 등의 테스트를 할수 없다." / "자리 옮기기 직전에 각종 메뉴얼 및 mods 요청 응답 테스트를 해서 '최초 반입용 메타데이터 작성'시점에 필요한 모든걸 가져오기 위한 고도화 테스트를 했다." / "지금 작성되어 있는 헤드리스 에이전트에 추가적으로 에이전트가 원문을 직접 저 보고(가능하면 전체) 필요한걸 더 수집해서 반입욕 메타데이터 작성을 고도화 하고싶다."

이전 확정 중 그대로 유효한 것: 2026-09-12(사람 판정 지점, KOLIS 요청은 직원 입회 아래, 계정은 `.env`), 09-29(읽기·조사·판단은 에이전트, 고정 코드는 형태가 정해진 쓰기·검사만, 시험은 프로그램 창으로, 도서관 양식 밖의 중간 산출물 금지, 모델 Sonnet), 09-30(①구간은 브라우저 없이 요청만으로), 10-01(반입 규칙 14개, 확인 완료 버튼), 10-03(품질 기준은 지침·프로세스 가이드·예시 파일 하나, 채점 틀 금지, 복본조사는 과장님 몫). 10-03 저녁의 "전거·주제명·둘째 출처정보를 끼워 넣지 않는다"만 폐기.

---

## 1. 사정과 지금 상태 (처음 읽는 사람용)

### 1-1. 이 일이 무엇인지
국립중앙도서관 온라인자료과의 "웹툰 납본·수집 대행 사업"이다. 납본은 출판물을 국립중앙도서관에 의무 제출하는 제도이고, 이 사업은 웹툰 출판사가 보낸 원고 이미지와 정보를 도서관 시스템에 대신 등록해 주는 일이다. 도서관 시스템 이름이 KOLIS(코리스)이고, 등록할 때 쓰는 서지 정보(제목·저자·발행처처럼 자료를 설명하는 정보) 형식이 MODS(모즈, 미국 의회도서관이 만든 서지 표준)다. 목표는 50,000건(회차 단위). 유저는 이 일을 사람이 손으로 하지 않도록 프로그램을 만들고 있고, 2026-09-29 확정으로 "주 목적은 프로그램 개발이며 작품은 시험 재료"다.

### 1-2. 업무 단계와 번호 체계
출판사 자료가 들어오면 ① 수집 → ② 검수 → ③ KOLIS 등록 → ④ 구축 → ⑤ 점검·납품 순서다. 프로그램에서는 이것을 두 구간으로 부른다.
- **①구간**: 반입용 엑셀을 만들어 KOLIS 에 올리고(일괄반입) 원문 이미지를 등록하고 가원부번호를 받기까지. 프로그램 1번(반입용 엑셀)과 2번(KOLIS 등록) 버튼.
- **③구간**: 원부번호가 나온 뒤 MODS 를 다듬고(구축, 프로세스 가이드 5.3) 점검해 납품하기까지. 프로그램 3번 카드.

번호가 셋 있다. **접수번호**는 KOLIS 에 엑셀을 올릴 때(일괄반입 응답) 생기는 번호, **가원부번호**는 등록을 마치고 받는 임시 원부 번호, **원부번호**는 도서관 주무관이 가원부를 정식 원부로 만들어 준 번호다. 가원부번호까지는 되돌릴 수 있고(접수번호 취소 요청 목록 `work/취소요청_목록.csv`), 원부번호 이후는 실제 업무 자료라 되돌릴 수 없다.

### 1-3. 반입용 엑셀이 무엇인지
KOLIS 는 자료 여러 건을 엑셀 한 장으로 받아들이는 일괄반입 기능이 있다. 그 엑셀은 1행 머리글이 MODS 경로(예: `/mods/titleInfo/title` 은 본표제, `/mods/name/namePart` 는 저자명, `/mods/name[@type]` 은 저자명 요소의 type 속성)이고 2행부터 한 행이 한 회차다. 저자가 둘이면 저자 열 묶음을 두 번 반복해 적는다. 도서관이 준 양식은 시트 둘(Sample = 열 설명과 값 규칙 50항목, Contents = 실제 값)이다. 유저가 참고 기준으로 정한 예시 파일 하나가 `docs/source/3_샘플양식/완료사례_코리스반입용_로맨스낫로맨틱(88열).xlsx` 이다. 이 예시는 저자 묶음 4개(넷째는 빈칸), 첫 출처정보에 발행처 칸 2개(`Studio Bluelime`, `미스터블루`), 판사항 `개정판`, 일반 주기 `Studio Bluelime은 미스터블루의 임프린트임`, 이용대상 주기 `15세 이용가`, 입수처 주기 `한국웹툰산업협회를 통해 수집한 자료임`, 권차 `01회`, 정가·보상금 500·보상 Y, 썸네일 파일명 `로맨스 낫 로맨틱_S1_01회_001.jpg` 같은 값을 담고 있다. 프로그램에는 83열짜리 템플릿 `kolis_tool/templates/import_template_83.xlsx` 가 있고, 지금 코드는 그 템플릿을 복사해 값을 채운다. 템플릿과 예시 88열의 차이는 저자 묶음 1개(5열)·발행처 1칸이 예시에 더 있고, 템플릿에만 둘째 `/mods/subject/topic` 열이 있다는 것이다.

### 1-4. 정보를 어디서 읽어야 하는지(지침)
도서관 지침(`docs/source/text/MODS_입력가이드.md`)은 값을 정하는 근거를 "으뜸정보원"과 "참고"로 나눈다(0.2·0.3절). 으뜸정보원은 **원문**(출판사가 보낸 원고 이미지 자체: 표지·타이틀컷·크레딧면·판권면)과 **출판사가 보낸 기초메타데이터 엑셀**, 이 둘뿐이다. 웹툰 플랫폼 화면(네이버시리즈·리디·미스터블루·카카오페이지 같은 곳)은 참고일 뿐이고, 거기서만 확인한 값은 각괄호 `[ ]` 로 묶어 표시한다. 채택 순서는 원문 > 출판사 엑셀 > 플랫폼이고, 같은 원문 안에 같은 항목이 여러 번 나오면 먼저 나오는 것을 쓴다. 으뜸정보원의 값에 각괄호가 있으면 원괄호로 바꾼다.

### 1-5. 지금 프로그램 1단계가 하는 일(코드를 읽은 대로)
프로그램 창에서 납품 폴더를 지정하고 버튼 하나를 누르면 다음이 돈다.
- 프로그램(`kolis_tool/prepare.py` `run`)이 zip 을 풀고(`unpack_zips`), 폴더 구성과 출판사 엑셀의 모든 칸을 글자로 옮긴 `snapshot.txt` 를 만든다(`snapshot`). 출판사마다 엑셀 양식이 달라서 어느 열이 무엇인지는 프로그램이 판단하지 않는다.
- 헤드리스 에이전트를 한 번 띄운다(`agent.run_job`). 헤드리스 에이전트는 클로드코드를 화면 없이(`claude -p --output-format stream-json`) 돌리는 것이고 모델은 Sonnet 이다. 작업 폴더는 저장소 밖 `%LOCALAPPDATA%\kolis_tool\agent\`(`agent.deploy` 가 `kolis_tool/agent_home/` 을 펼침)이다. 에이전트는 "스킬"(어떤 일을 어떻게 하는지 적은 지시 문서, `.claude/skills/<이름>/SKILL.md`)을 읽고 스스로 돈다. 지금 스킬은 `prepare-import`(납품 폴더 → 반입용 엑셀 전체 절차와 칸별 기준)와 `research-work`(웹 조사 기준과 결과 형식)이고, 끝에 `reviewer`(검수 에이전트, 작업자의 결과를 독립적으로 다시 확인하는 하위 에이전트, `.claude/agents/reviewer.md`)에게 검수를 받는다.
- 허용 도구(`agent.job_tools`): Read, Write, Edit, Glob, Grep, WebSearch, WebFetch, Agent, Task, Skill + 명령 `render`(자바스크립트 페이지를 Edge 로 열어 글자를 뽑음), `check-research`, `write-import`, `check-build`, `check-build-work`, `check-dup`, `authority`.
- 에이전트의 순서: 납품 자료 읽기 → 폴더 정리 계획(`arrange`, 회차 폴더와 썸네일 폴더를 KOLIS 가 받는 모양으로. 옮기는 것은 프로그램) → 웹 조사(최초 연재 플랫폼, 회차별 공개일·가격·이용등급, 발행처 소재지, ISBN) → 칸마다 값 결정 → 저자마다 전거 후보 조회 → `write-import` 로 엑셀 쓰기와 검사 → 검수 → 배운 것을 `knowledge/platform-notes.md` 에 기록.
- **전거**는 도서관이 관리하는 사람·단체의 공식 이름 기록이다. 같은 이름의 다른 사람을 구별하려고 번호(KAC로 시작)가 붙어 있고, 저자를 전거에 "연결"하면 MODS 저자 항목의 `@ID` 에 그 번호, `@authority` 에 `국립중앙도서관전거데이터` 가 들어간다. 전거 후보 조회는 10-03 에 만든 `kolis_tool/authority.py`(명령 `kolis_tool authority "<이름>"`)로, 프로그램이 KOLIS 에 로그인해 `listACMat.do` 로 이름이 같은 전거 목록(AC_CONTROL_NO·CHOICE_SIGNPOST·JOB·BIRTH_YEAR·SUMMARY 등)을 받아 `work/authority/<이름>.json` 에 두고 에이전트에게 넘긴다. 에이전트는 KOLIS 에 직접 닿지 않는다.
- 끝나면 프로그램이 같은 검사(`prepare._check_all` = `checks.check_research` + `import_writer.check`)를 다시 돌리고, 걸리면 같은 대화를 이어서(`--resume`, 최대 3회) 에이전트에게 알려 준다. 그다음 엑셀을 최종으로 쓰고(`import_writer.write`), 마무리(`finalize`)로 폴더를 옮기고 원고 파일명을 8자리 번호로, 썸네일 파일명을 엑셀 값으로 바꾼다(되돌리기 가능).
- 사람 확인 지점은 여기 한 곳이다. 화면에 "직원이 확인할 것" 표(칸·넣은 값·출판사 값·이유·근거 주소·직원이 정할 질문)가 뜨고 엑셀의 그 칸이 노란색이 된다. 직원이 고친 뒤 **확인 완료** 버튼(`Api.confirm_import` → `import_writer.clear_marks`)을 눌러야 2번(KOLIS 등록)이 열린다.

### 1-6. 지금 에이전트가 원문을 어떻게 보는지(문제의 핵심)
- 스킬 `prepare-import` 1절 3번: "원고 이미지를 Read 로 직접 본다: 첫 폴더의 처음 2~3장, 마지막 폴더의 마지막 2~3장(판권면이 있는 경우가 많다), 폴더마다 첫 장." **표본만 본다.** 볼 것으로 적힌 항목은 제목 표기(띄어쓰기 포함), 권차 표기 방식, 저자 표기와 역할, 색(내용 기준), 판권면의 출판사·발행일·ISBN 이다.
- 어떤 이미지를 봤는지 적는 자리(`import.json` 의 `reading.seen_in_manuscript.images_viewed`)는 있지만, 검사 코드 `import_writer.check` 는 그 자리를 전혀 보지 않는다. 그래서 에이전트가 몇 장을 봤는지, 봐야 할 장을 건너뛰었는지 프로그램이 알 수 없다.
- 10-03 밤 시험(프로그램 「다시 만들기」 단추, 원시인 삼촌, 813초)에서 남은 결함 둘이 바로 원문을 덜 본 결과다. ① 권차를 출판사 엑셀 표기(`1`, `2 (완결)`)로 썼고 원고 표기는 확인하지 못했다(확인할 칸에는 올렸다). ② 표지에 적힌 `흑나비프로덕션作品`(제작처)을 발행처 칸(`publishers`)에 넣지 않고 `issues` 에만 적었다(스킬 5절에 보강은 했으나 재시험 전).
- 매뉴얼 3.1(`웹툰대행사업_매뉴얼_v1.6.md` 179행): "원문파일은 표지 및 판권면 파일을 열어서 제목, 저자 등의 기본정보를 확인하고 전체 이미지 파일의 이상유무 확인". 이상 유무 검사 도구 `kolis_tool/inspect_files.py`(깨진 파일·0바이트·형식·완전 동일 컷·유사 컷·해상도·용량)는 있지만 명령줄(`kolis_tool inspect`) 전용이고 1단계 에이전트의 허용 명령에는 없다.

### 1-7. 지침이 원문에서 읽으라고 하는 항목 전부
이것이 에이전트가 원문 전체에서 수집해야 할 목록이다. 조항 번호는 `MODS_입력가이드.md`.
- **본표제** 표기(띄어쓰기 포함), 표제 앞 관제(원괄호로), 외국어 표제는 문장 첫 글자만 대문자, 한자표제(독음이 같으면 주기에 "한자표제: ○○", 독음은 다르고 해석이 같으면 대등표제, 둘 다 다르면 표제관련정보). 1.1·1.6·참고.
- **표제관련정보**: 시즌·외전 문구는 원문 그대로 표제관련정보에, 제목 뒤 숫자·로마자는 본표제에 포함. 1.2.
- **권차**는 원문 표기 그대로(2부, 0화, 01회, 1권), 프롤로그·에필로그는 권차를 비우고 권차표제에. 회차 제목은 **권차표제**. 1.3·1.4.
- **불용어**: 외국어 표제의 문두 관사. 1.5.
- **저자명·역할어**는 원문 > 엑셀 > 플랫폼, 같은 원문 안에서는 먼저 나오는 것, 표제면·판권기·표지가 서로 다르면 더 상세한 것. 보조 역할(어시스트·콘티·채색·배경·편집)은 제외, 단 글·각색 표시가 없고 콘티만 있으면 콘티를 저자로. 유형은 개인명/단체명, 단체명의 수식어(주식회사·도서출판 등) 생략. 역할어는 원문 형태 그대로, 관형형("지은")은 명사형("지음")으로, 역할이 둘이면 중간점(각색·작화). 첫 저자는 `@usage=primary`. 2·2.3.
- **다른이름**: 필명·본명 병기, 영문 병기는 저자 항목 안의 다른이름(`alternativeName`)에 적는다. 유형(`altType`)은 셋: nickname(필명, 저자명은 본명), formal name(본명, 저자명은 필명), no specific type(그 밖, 영문 표기·도치형). 직원 답변 7~10(`build-judgment-rules.md`): 출처는 원문뿐, 영문은 '성, 이름' 꼴, 원문에 없으면 비워 둔다. 2.4.
- **전거형과 디스플레이형식**: 전거형(전거에 적힌 공식 이름)과 원문 표기가 다르면 저자명에는 전거형을, 원문 표기는 디스플레이형식(`displayForm`)과 다른이름에 적는다. 같으면 디스플레이형식을 쓰지 않는다. 전거 연결은 생몰년·직업 등이 완전히 일치할 때만. 2.1·2.2.
- **발행처·제작처**는 자료 안의 표기 순서대로. 크레딧면에 로고가 둘(예: 그림 02 의 `웹툰창고` + `J STUDIO`)이면 발행처 칸 둘. 발행지가 다른 제작처는 둘째 출처정보 묶음에 `[제작]`을 붙여 따로. 영문 발행처는 각 단어 첫 글자만 대문자(KWBOOKS → Kwbooks), 머리글자 약어만 예외. 큰 글자가 한글이면 한글명, 영문이면 영문명. 5·5.2.
- **발행지**: 시 단위명 제외, 추정은 각괄호, 코드는 KORMARC 발행국부호(서울 ulk, 경기 ggk, 부산 bnk …). 5.1.
- **발행일** YYYYMMDD, 모르는 자리는 `-`. 5.3.
- **판사항**(개정판, 19세 완전판, 제2판). '판'자가 없으면 각괄호(개정[판]). 5.4.
- **색**: 무채색 외 색이 하나라도 있으면 천연색, 무채색만이면 흑백. 직원 규칙(10-01)으로 표지만 천연색이고 내용이 흑백이면 흑백. 7.4.
- **이용대상** 표기(19세 등). 성인물은 이용대상자 '성인용' + 주기 "19세 미만 구독불가" + 이용제한 설정. 8.
- **주기**: 약어 풀이, 필명·본명 관계(그 이름은 다른이름에도), 임프린트(한 출판사의 하위 브랜드) 관계, 수상(원문·기초메타데이터·배포자료에 있을 때). 순서는 일반 > 이용대상 > 입수처 > 수상. 9.
- **총서사항**(여러 편이 한 대표 제목 아래 있을 때 상위 제목)·**종이책 관계**(같은 내용의 종이책이 도서관에 있을 때 그 제어번호). 12.1·12.2.
- **ISBN**: 판권면에 있으면 읽고, nl.go.kr/seoji 에서 파일형식·발행처 확인, 붙임표 없이. 13.
- 판권면의 발행일(옛 단행본 스캔 자료에 있음). 5.3.

### 1-8. 10-03 밤 헤더 시험이 바꾼 것
지침은 전거 연결·다른이름·주제명 연결·UCI 는 "구축 단계(③구간)에서 KOLIS 화면을 열어 따로 넣는다"고 적고 있다(프로세스 가이드 5.3: "반입용 기초메타데이터 작성 시 구현할 수 없었던 내용을 추가 작업(저자전거 연결, 저자정보_다른이름, 주제명 연결, 식별기호(UCI 입력) 등)"). **주제명**은 도서관이 정한 표준 주제어(주제명표목표, 번호 KSH로 시작)이고, **UCI** 는 국가 디지털 콘텐츠 식별자(ISBN 과 비슷한 번호)다. 유저가 "다 테스트 해봐, 취소하면 되잖아"라고 허용해, `tools/import_probe.py` 로 원시인 삼촌 2행의 반입용 엑셀에 시험 열을 끼워 실제로 KOLIS 에 올려 봤다(접수 1027~1029, 원문 등록·가원부는 안 하고 `work/취소요청_목록.csv` 에 "취소 요청"). 접수 목록 응답이 돌려주는 콘텐츠 MODS(CONTENTS_XML)로 확인한 결과 **전부 들어갔다**(`docs/BUILD-CHECK-RECON.md` 9절, `docs/HANDOFF.md` 2-6절).
- 저자 전거 번호 `/mods/name[@ID]` 와 전거 기관 `/mods/name[@authority]` → `<name ID="KAC…" authority="국립중앙도서관전거데이터" type="개인명">`.
- 다른이름 `/mods/name/alternativeName` + `/mods/name/alternativeName[@type]`(값 nickname) + `/mods/name/alternativeName/namePart` → `<alternativeName altType="nickname">`. 열 이름을 `[@type]` 로 써도 `[@altType]` 로 써도 altType 으로 들어간다.
- 디스플레이형식 `/mods/name/displayForm`(3차).
- 주제명 2묶음: `/mods/subject/` | `/mods/subject/topic` | `/mods/subject[@ID]` | `/mods/subject[@authority]` | `/mods/subject/` | `/mods/subject/genre` | `[@ID]` | `[@authority]` → 만화[漫畵] KSH1998022212 topic, 웹툰[webtoon] KSH2016000049 genre, 전거 `국립중앙도서관주제명표목표`.
- UCI: 둘째 `/mods/identifier` + `/mods/identifier[@type]`=uci → `<identifier type="uci">`. 지침 13 이 "반입하면 오류"라고 적었지만 지금 KOLIS 에서는 반입 직후에 재현되지 않는다.
- 출처정보 2묶음: 둘째 `/mods/originInfo` 부모 열 뒤에 `[@type]`·발행지·발행처·발행일·발행연속성 → 두 `<originInfo>`. **발행지 구조는 부모 열 `/mods/originInfo/place` 로 정해진다**: 부모 열을 placeTerm 쌍 앞에 한 번 두면 `<place>` 하나에 placeTerm(text, code) 둘(지침 꼴, 2차), placeTerm 마다 두면 `<place>` 둘(1차), 부모 열이 없으면 앞 묶음에 붙는다(유저가 본 "출처정보 하나에 발행지 4개"의 원인 = 둘째 `/mods/originInfo` 부모 열 없이 placeTerm 만 반복). Sample 시트 규칙: "반복에 따른 부모정의 항목으로 데이터는 없음".
- 첫 출처정보 발행처 2칸, 판사항 `/mods/originInfo/edition`, 넷째 주기(`[@type]`=awards)(3차).
- 결론: **구축 5.3 의 추가 작업을 반입에서 끝낼 수 있다.** 같은 날 저녁에 정했던 "전거 번호·주제명 번호·둘째 출처정보를 엑셀에 끼워 넣지 않는다"는 이 결과로 다시 열렸고, 10-04 유저가 "반입에서 모든 걸 끝낸다"로 정했으므로 폐기한다.
- `docs/MODS-FIELDS.md` 1절의 근거: 반입 파서는 Sample 필드설명에 없는 열(`name[@usage]`, `note[@type]`, `originInfo[@eventType]`, `classification[@edition]`, `originInfo/edition`)도 "요소 뒤 속성" 일반 규칙으로 받는다. KOLIS MODS 수정 화면의 칸 174개가 저장소 쪽 자리이므로, 화면에 있는 경로는 원칙적으로 반입 대상이 될 수 있다.

### 1-9. 맥북의 제약(2026-10-04)
- 저장소는 10-03 밤 커밋(b9e4c7b)까지 깨끗이 받아져 있다. 메모리 사본은 이 맥북의 세션 메모리 폴더 `~/.claude/projects/-Users-kkh-works-dog-foot-dataclip-kolis/memory/` 에 복사했고, 10-04 결정은 `import-finishes-everything.md`, 브리핑 쓰는 법은 `briefing-format-that-worked.md` 로 적었다(`docs/memory/` 에도 사본).
- 없는 것: `work/`(산출물·실행 기록·취소 요청 목록·전거 조회 캐시 `work/authority/`·헤더 시험 결과 `work/probe/`), `.env`(계정), 시험 재료(`Downloads\수집자료_개발용_0929` 의 타임머신 대소동·원시인 삼촌·추풍낙엽, `Downloads\484_미스터블루_옆집 기러기 아빠 구워먹기`), 프로그램 창 패키지(pywebview 미설치. 파이썬 3.14 과 openpyxl 은 있음), 바탕화면 `반입헤더시험_2026-10-03` 폴더(요청·응답 사본).
- KOLIS 는 도서관 내부망에서, 계정에 신청된 IP 에서만 열린다. 오늘은 반입 시험과 전거 조회(`authority` 명령은 KOLIS 로그인이 필요하고 캐시도 없다)를 할 수 없다. 에이전트를 실제 작품으로 돌리려면 폴더를 옮겨 와야 하고, "시험은 프로그램 창으로" 규칙도 오늘은 지킬 수 없다.
- 그래서 오늘 할 수 있는 것은 아래 5절 순서의 ①~④(설계·코드·스킬·KOLIS 없는 시험)이고, ⑤~⑥은 도서관 PC 에서 한다.

---

## 2. 결정이 바꾸는 것

### 2-1. 결정 1 "반입에서 모든 걸 끝낸다"의 범위
반입용 엑셀로 들어가는 것이 확인된 항목을 전부 1단계 에이전트가 채운다: 저자 전거 번호·기관, 디스플레이형식, 다른이름(유형 포함), 주제명 묶음(전거 번호·기관 포함), UCI, 출처정보 여러 묶음, 발행처 여러 칸, 판사항, 수상·약어·필명·임프린트 주기, 대등표제. 반입으로 못 끝내는 것은 셋뿐이고 ③구간에 그대로 남는다.
1. **성인물 이용제한구분.** MODS 가 아니라 KOLIS "종"(작품 단위 기록) 화면의 값(이용제한구분 "1. 청소년 유해매체물", GM/CD1)이라 반입 엑셀에 자리가 없다. 이미 `build_prep.use_limit_adult` 로 자동. 성인물 여부 판단은 1단계가 하고(이용대상자 '성인용' + 주기 + 접근제한 1), 3번 카드가 그 값을 보고 자동 실행한다.
2. **복본조사·완료·일괄변경.** 과장님 일이고 고정 탭 「복본조사」(`dup_request.py`, `ledger_batch.py`)에서 한다. 바꾸지 않는다.
3. **반입 뒤 직원이 바꾸고 싶은 값의 보정.** 3-2 의 「KOLIS 값 읽어 대조」(`mods_compare.py`)로 반입값과 KOLIS 값을 칸마다 비교하고, 틀린 칸만 고쳐 저장한다(`mods_batch.send_bodies` 의 전·후 XML 대조 안전장치는 그대로 쓴다).

따라서 3-2 의 「작품 전체 판단」(`build-mods-work` 에이전트)·「저장 본문 준비」·「준비된 회차에 한 번에 넣기」는 기본 경로에서 빠진다. 대조에서 다른 칸이 있을 때의 보정 수단으로만 남긴다.

### 2-2. 결정 2 "헤더를 고정하지 않는다"의 구조
지금 `kolis_tool/import_writer.py` 는 83열 템플릿을 복사하고(`write`), 고정 사전 `FIELDS`(항목 이름 → (열 이름, 몇 번째))·`CONSTANTS`(고정값)·`NAME_KEYS`(저자 3묶음)로 열 위치를 찾은 뒤, `_grow_columns` 로 저자 묶음·발행처 칸·주기 쌍 세 가지만 열을 끼워 넣는다. 이 구조로는 표제정보 반복, 저자 한 명의 다른이름 여러 개, 식별기호 여러 개(ISBN + UCI), 주제명 묶음(topic/genre + @ID/@authority), 둘째 이후 출처정보의 발행지 부모 열, 전거 번호 열을 낼 수 없다. 바꿀 구조:
- 에이전트는 행마다 **MODS 트리**를 쓴다. 트리란 "표제정보 묶음 목록, 저자 묶음 목록(각 저자 안에 다른이름 목록), 출처정보 묶음 목록(각 묶음 안에 발행지·발행처 목록), 주기 목록, 주제명 목록, 식별기호 목록, 원문주소 목록 …" 처럼 요소를 겹쳐 담은 자료 구조다. 양식 고유 칸(`currency_code`·`contents_price`·`compensation`·`reward_yn`·`thum_files`)도 함께 적는다.
- 고정 코드가 트리를 열로 **직렬화**한다. 직렬화는 겹친 구조를 한 줄의 열 목록으로 펴는 일이다. 규칙은 양식 Sample 시트의 설명("엘리먼트를 먼저 기술하고 속성을 기술한다", "반복에 따른 부모정의 항목으로 데이터는 없음")과 1·2·3차 시험으로 확인한 것(발행지 부모 열은 출처정보마다 한 번, 다른이름 유형 열, 주제명 묶음 열, 둘째 식별기호).
- **반복 묶음의 수는 상한이 없다**(유저 보충 "2묶음으로 고정하는 것도 아니지. 그 이상 있으면 더 여러 묶음"). 반복 요소 전부: 표제정보(본표제·대등표제·그 밖), 저자(각 저자 안의 다른이름도 n개), 출처정보(발행지가 다른 제작처·유통사가 셋이면 3묶음, 묶음마다 발행처 n칸), 주기, 주제명, 식별기호(ISBN·UCI·그 밖), 원문주소, 분류, 연관정보. 열 수는 그 작품 행들 중 **최대 반복 수**로 정하고, 모자란 행은 빈칸으로 둔다. 빈 묶음이 반입에 문제없다는 것은 예시 88열(넷째 저자 묶음과 둘째 출처정보가 빈 채 승인됨)이 보여 준다. "2"로 보였던 것 중 주제명 "만화·웹툰 둘만"은 직원 답변 11~13 의 **내용 규칙**이지 구조 상한이 아니고(직원이 더 넣으라고 하면 셋이 된다), 지침이 "반복불가"라고 적은 요소(판사항·역할어·디스플레이형식·발행연속성·수량·콘텐츠유형·이용대상자 등)만 하나이며 그것도 **에이전트가 지침을 따르는 것이지 코드가 막는 것이 아니다.**
- 열 순서는 Sample 시트 순서를 따르고 묶음 안 순서(부모 → 요소 → 속성)만 지킨다. 묶음 사이 순서가 KOLIS 파서에 영향을 주는지는 확인된 바 없으므로 Sample 순서를 그대로 쓰는 것이 안전하다.
- 시험은 KOLIS 없이 된다. ① 예시 88열을 트리로 역변환해 다시 쓰면 셀 단위로 같아야 한다(수량·썸네일은 폴더가 없으니 제외하거나 예시 값을 그대로 넣는 경로를 둔다). ② `tools/import_probe.py` 의 `build()` 가 만드는 1~3차 시험 열 목록을 트리로 만들어 쓰면 그 열 목록이 그대로 나와야 한다(실제 시험 엑셀은 도서관 PC 에만 있으므로 `build()` 의 논리로 재현).

### 2-3. 결정 3 "하위호환 무시"로 갈아엎을 것
**버림**
- `kolis_tool/import_writer.py`: `FIELDS`, `CONSTANTS`, `REPEAT_FIELDS`, `ORIGIN2_KEYS`, `NAME_GROUP`, `name_keys`, `NAME_KEYS`, `COMPUTED`, `REQUIRED`, `KOREAN`, `column_label`, `_grow_columns`, `_insert_after`, `check()` 의 항목 이름 목록 검사(`field_names`), `write()` 의 고정 사전 순회.
- `kolis_tool/templates/import_template_83.xlsx` 의 Contents 머리글(Sample 시트는 양식이므로 그대로 둔다).
- 스킬 `prepare-import` 3절의 항목 이름 표(`title`·`names`·`publisher` …)와 4절 `import.json` 꼴, `decisions` 를 따로 두는 구조(전거·성인물·UCI 판단을 엑셀 밖에 두던 것).
- `tools/import_probe.py`(열 만들기 논리를 직렬화기 시험에 흡수. 접수를 보내는 부분은 도서관 PC 의 ⑤ 시험 도구로 다시 쓴다).
- 3-2 기본 경로: `mods_batch.run_work_agent`·`prepare_bodies`·`send_bodies` 를 **기본 경로에서** 뺀다(코드는 보정용으로 둠), 화면 「작품 전체 판단」·「저장 본문 준비」·「준비된 회차에 한 번에 넣기」 단추.
- 스킬 `build-mods-work` 의 2-1(전거)·2-2(주제명)·2-5(UCI)·2-6(다른이름) 판단 부분(1단계로 옮김). 남는 것은 "반입값이 회차끼리 다르거나 지침과 어긋나 보이는 것" 보고(2-7)와 직원 보정 반영.
- `docs/PLAN-2026-10-03-IMPORT-QUALITY.md` 의 1-2(전거 번호는 엑셀에 넣지 않음)·2-2·2-3(한 번에 입력) 절. 문서는 기록으로 두되 머리에 "10-04 개선안으로 대체"를 적는다.

**살림**
- `kolis_tool/agent.py`(실행기: deploy, run_job, run, resume, collect_knowledge, job_tools).
- `kolis_tool/prepare.py` 의 `unpack_zips`, `snapshot`, `finalize`, `undo`, `output_name`(결과 구조 `result` 는 손봄).
- `kolis_tool/arrange.py`(정리 계획 검사·옮기기·되돌리기).
- `kolis_tool/authority.py`(전거 후보 조회).
- `kolis_tool/checks.py` 의 `check_research` 와 스킬 `research-work`(웹 조사 기준·결과 형식·검사). 단 `research-work` 의 결과가 트리에 들어가는 자리를 2-A 에서 정한다.
- `kolis_flow.py`·`kolis_http.py`·`kolis_request.py`·`journal.py`(①구간 등록). 반입용 엑셀의 열이 바뀌어도 일괄반입 요청은 파일을 그대로 첨부하므로 영향 없음.
- `kolis_tool/mods_compare.py`(대조. 반입용 엑셀을 트리로 읽게 고침).
- `kolis_tool/inspect_files.py`(에이전트 도구로 승격, 색 판정 고침).
- 지식 파일 `agent_home/knowledge/*.md`, 규칙 원문 배포(`tools/build_rules.py` → `docs/source/text` → `knowledge/rules/`).
- 복본조사 고정 탭(`dup_request.py`, `ledger_batch.py`, `dup_judge.py`, 스킬 `judge-duplicates`).
- 확인 완료 잠금(`Api.confirm_import`, `clear_marks`, `marks`, `kolis_flow` 의 첫 확인).

**손볼 것**
- `kolis_tool/app.py` 와 `kolis_tool/ui/index.html` 의 "직원이 확인할 것" 표: 항목 이름 기준 → **MODS 경로 + Sample 한글 이름 + 몇 번째 묶음** 기준. 새 항목(전거 연결·다른이름·UCI)의 근거 펼침.
- 3-2 카드: 「KOLIS 값 읽어 대조」와 「틀린 칸 고쳐 저장」만.
- `mods_batch.py`: 직원 보정 저장만(대조에서 다른 칸 → 직원이 값 선택 → 그 칸만 바꾼 저장 본문 → 전·후 XML 대조).
- `reviewer.md`: 6절(반입용 값) 전면 재작성(아래 3-C).
- `prepare.py` `run` 의 `result` 구조(화면이 읽는 `import`·`confirm_cells`·`title` 등)를 트리 기준으로.

---

## 3. 새 설계

### 3-A. 서지 모형과 직렬화(고정 코드)

**결과 파일 `import.json`(새 정의).** 행마다 다음을 적는다.
- `mods`: MODS 트리. 요소 이름은 MODS 태그 그대로, 반복 요소는 목록, 속성은 `@` 로 시작하는 키, 글자 값은 `_` 키(또는 `text`). 예(저자 둘, 둘째 저자에 다른이름 하나):
  ```json
  {"titleInfo": [{"title": "로맨스 낫 로맨틱", "partNumber": "01회"}, {"@type": "parallel", "title": "Romance not romantic"}],
   "name": [{"@usage": "primary", "@type": "개인명", "@ID": "KAC201418251", "@authority": "국립중앙도서관전거데이터", "namePart": "김밀가", "role": {"roleTerm": "원작"}},
            {"@type": "개인명", "namePart": "상두", "displayForm": "상두(SANGDU)", "role": {"roleTerm": "그림"},
             "alternativeName": [{"@altType": "no specific type", "namePart": "Sangdu"}]}],
   "originInfo": [{"@eventType": "publication", "place": [{"placeTerm": [{"@type": "text", "_": "[서울]"}, {"@type": "code", "@authority": "kormarccountry", "_": "ulk"}]}],
                   "publisher": ["Studio Bluelime", "미스터블루"], "dateIssued": "20241001", "edition": "개정판", "issuance": "단행자료"},
                  {"@type": "production", "place": [...], "publisher": ["○○[제작]"], "issuance": "단행자료"}],
   "note": [{"_": "Studio Bluelime은 미스터블루의 임프린트임"}, {"@type": "target audience", "_": "15세 이용가"}, {"@type": "acquisition", "_": "한국웹툰산업협회를 통해 수집한 자료임"}, {"@type": "awards", "_": "문화체육관광부장관상, 2025"}],
   "subject": [{"@ID": "KSH1998022212", "@authority": "국립중앙도서관주제명표목표", "topic": "만화[漫畵]"}, {"@ID": "KSH2016000049", "@authority": "국립중앙도서관주제명표목표", "genre": "웹툰[webtoon]"}],
   "identifier": [{"@type": "isbn", "_": "9791109764511"}, {"@type": "uci", "_": "G903+…"}],
   "location": {"url": ["https://www.mrblue.com/webtoon/mon", "https://www.mrblue.com/webtoon/wt_000065653"], "physicalLocation": "국립중앙도서관"},
   "targetAudience": "일반이용자", "accessCondition": {"licenseType": "2"}, "classification": {"@authority": "KDC", "@edition": "6", "_": "810"},
   "language": {"languageTerm": {"@authority": "iso639-2b", "@type": "code", "_": "kor"}},
   "physicalDescription": {"form": "전자자료(Image)", "reformattingQuality": "access", "digitalOrigin": "BornDigital"},
   "typeOfResource": "텍스트", "genre": "만화", "extension": {"regionOfPublishing": "한국"}}
  ```
  수량(`extent`)·파일 형식(`internetMediaType`)은 프로그램이 폴더에서 세어 넣는다(에이전트는 색만 정한다). 사업 고정값(언어·형태·분류 810·소장위치·지역·콘텐츠유형·장르·입수처 주기)은 **프로그램 설정**(`work/build_settings.json` 과 같은 자리)에서 넣되, 에이전트가 지침 근거로 바꿀 수 있어야 하면 트리에 그대로 적게 한다. 어느 쪽인지는 구현 때 정하되, "사업마다 다른 값은 설정, 자료마다 다른 값은 에이전트"가 기준이다.
- `extra`: 양식 고유 칸 `{"currency_code": "\\", "contents_price": 500, "compensation": 500, "reward_yn": "Y", "thum_files": "…"}`.
- `folder`, `thumb_source`, `thumb_file`, `color`(천연색/흑백).
- `confirm[]`: 확인할 칸. `path`(예 `name[1].alternativeName[0]` 또는 열 이름 `/mods/name/alternativeName/namePart #2`), `reason`, `publisher_says`, `evidence`, `ask`. 글투 규칙은 지금 스킬 3절 그대로(직원이 그 항목만 읽고 정할 수 있게, 내부 용어 금지).
- `sources`: 값마다 출처 `{"path": "…", "from": "원문 <파일>|출판사 엑셀 <칸>|플랫폼 <이름> <주소>|전거 <번호>|직원 지시", "quote": "글자 그대로"}`.
작품 단위로는 `title`, `unit`, `publisher_xlsx`, `manuscripts_root`, `thumbs_dir`, `arrange`(지금 그대로), `reading.mapping`(출판사 엑셀 열 해석), `observations_dir`, `issues`, `review`.

**직렬화기(`kolis_tool/mods_sheet.py`, 새 파일).**
- 입력: 행 목록(트리 + extra). 출력: 머리글 목록과 행별 값 목록, 그리고 openpyxl 로 Contents 시트에 쓰기. Sample 시트는 템플릿에서 그대로 복사한다(템플릿 파일은 Sample 시트만 남기고 Contents 는 머리글 없이 둔다).
- 열 만들기 규칙:
  1. Sample 시트의 요소 순서(titleInfo → name → typeOfResource → genre → originInfo → language → physicalDescription → targetAudience → note → subject → classification → identifier → location → accessCondition → extension …)를 기준 순서로 둔다. 예시 88열의 순서와 같다.
  2. 반복 요소마다 묶음 수 = 모든 행의 최대 개수. 묶음마다 **부모 열**(값 없음: `/mods/titleInfo/`, `/mods/name`, `/mods/originInfo`, `/mods/subject/`, `/mods/originInfo/place`, `/mods/name/alternativeName`, `/mods/name/role`)을 먼저, 그다음 자식 요소, 그다음 그 요소의 속성(`[@…]`). 자식도 반복이면 같은 규칙을 재귀로.
  3. 속성 열은 요소 열 **바로 뒤**(Sample: "엘리먼트를 먼저 기술하고 속성을 기술한다"). 요소 자체에 값이 없고 속성만 있는 경우(`/mods/originInfo[@eventType]`)는 부모 열 뒤에 속성 열.
  4. 발행지: `/mods/originInfo/place`(부모, 값 없음) → `/mods/originInfo/place/placeTerm` + `[@type]`(text) → `/mods/originInfo/place/placeTerm` + `[@authority]` + `[@type]`(code). 출처정보 묶음마다 한 번(2차 시험 결과).
  5. 다른이름: `/mods/name/alternativeName`(부모) → `/mods/name/alternativeName[@altType]` → `/mods/name/alternativeName/namePart`. 저자 안에서 n번 반복.
  6. 양식 고유 칸(`currency_code`, `contents_price`, `compensation`, `reward_yn`, `thum_files`)은 맨 뒤.
  7. 값이 모든 행에서 비어 있는 선택 열(예: 셋째 저자의 다른이름)은 묶음 수 계산에 들어가지 않는다. 다만 예시처럼 빈 묶음이 생기는 것은 허용한다(최대치 기준이라 어떤 행은 빈칸).
- 숫자 서식: 지금 `import_writer.NUMERIC`·`ISBN_FORMAT` 의 규칙(정가·보상금·발행일·ISBN·접근제한을 숫자로, ISBN 은 지수 표기 방지 서식)을 옮긴다.
- 노란 칸·메모: `confirm[].path` 를 열로 변환해 그 칸을 칠하고 메모를 단다(`confirm_text` 옮김). `marks`·`clear_marks` 는 그대로.
- 역직렬화(`read_sheet`): 반입용 엑셀 → 트리. `mods_compare.py`(KOLIS 값 대조)와 역변환 시험이 쓴다. 머리글의 부모 열로 묶음 경계를 잡는다.

**검사(`kolis_tool/import_check.py`, 새 파일. 판단하지 않는다).**
- 값 규칙: Sample 필드설명의 선택값 표(`titleInfo[@type]` uniform/title/parallel/translated/original…, `name[@type]` 개인명/단체명, `placeTerm[@authority]` kormarccountry, `languageTerm` kor…, `form`, `reformattingQuality`, `targetAudience` 목록, `note[@type]` 목록, `identifier[@type]` isbn/uci…, `accessCondition/licenseType`), 발행일 8자리(모르는 자리 `-`), ISBN 13자리 검증 숫자, 전거 번호 꼴(`KAC`+숫자, `KSH`+숫자), 전거 번호가 있으면 `@authority` 도 있어야 함, 발행처 각괄호 금지, 저자 각괄호는 출처가 플랫폼일 때만, 역할어 관형형 금지, 영문 발행처 전체 대문자 경고, 원문주소 첫째가 사이트 첫 화면이면 거부, 권차가 단위 없는 숫자만이면 출처가 원문인지 확인, 보상금 = 정가·유료 Y·무료 N·정가 0 (10-01 규칙), 같은 ISBN 여러 행이면 confirm 요구, 발행처 둘인데 일반 주기 없으면 confirm 요구, 주제명 묶음에 ID 가 있으면 topic/genre 와 번호가 짝이 맞는지(KSH1998022212 ↔ 만화[漫畵], KSH2016000049 ↔ 웹툰[webtoon]), UCI 가 있으면 출처 주소가 있어야 함.
- 파일 증거: 행 수 = 원고 하위 폴더 수(`arrange.View` 로 정리 뒤 모습), 폴더마다 이미지 있음, 이미지 아닌 파일 없음, 썸네일 파일 존재, **관찰 파일이 회차 수만큼 있고 각 파일의 `images_viewed` 가 그 폴더의 이미지 목록과 같음**, 저자에 `@ID` 가 있으면 `work/authority/<이름>.json` 후보에 그 번호가 있음(직원 결정 `source: staff` 는 면제).
- confirm 글: `reason`·`ask` 있음, 항목 경로가 실제 열로 변환됨.
- 검수: `review.done` 과 findings/resolved 수 일치(지금 규칙).

**사람이 보는 칸 이름.** `경로 #묶음번호 (Sample 한글 이름)` 예: `/mods/name/alternativeName/namePart #2 (다른이름)`. Sample 시트의 한글 이름을 읽어 사전으로 쓴다(코드에 한글 이름을 박지 않는다).

### 3-B. 원문 전체 읽기(에이전트)

**왜 지금 구조로는 안 되는가.**
- 이미지 한 장을 Read 로 보면 약 1,000~1,600 토큰이 든다. 옆집 기러기 아빠 구워 먹기는 11건 149장(414MB), 타임머신 대소동은 3권 192장, 1607 마음휴가 같은 25화 작품은 수백 장이다. 한 에이전트 대화에 전부 넣으면 한도를 넘고, 넘지 않아도 앞에서 본 장을 뒤에서 잊는다.
- 세로로 아주 긴 한 장짜리 스크롤 이미지(폭 1500px, 10-01 납품)는 Read 가 전체를 축소해 보여 주므로 글자가 안 읽힌다. 10-03 그림 판독 때도 1839×283 캡처를 4조각으로 잘라 3배 확대해서야 읽었다.
- 지금 에이전트에는 이미지를 자르거나 확대하는 도구가 없다. 허용 명령은 `render`·검사·쓰기·`authority` 뿐이다.

**해법: 회차 단위 하위 에이전트와 관찰 파일.**
- 작품 에이전트가 회차(권)마다 하위 에이전트(Agent 도구)를 띄워 그 폴더의 이미지를 **전부** 보게 하고, 결과를 `jobs/<작업>/observations/<폴더>.json` 로 받는다. 작품 에이전트는 관찰 파일만 읽고 값을 정한다. 한 대화에 모든 이미지가 들어오지 않으니 한도 문제가 없고, 회차가 많으면 동시에 여러 개를 띄운다(동시 수는 스킬에 적되 코드로 막지 않는다).
- 관찰 하위 에이전트의 지시는 스킬 `observe-episode`(새로 만듦)에 둔다. 하위 에이전트는 KOLIS 에 닿지 않고 웹도 보지 않는다. 폴더의 이미지를 파일명 순서로 전부 열고(긴 이미지는 `look` 으로 조각), 장마다 적는다.
- 관찰 파일 형식:
  ```json
  {"folder": "001_1화", "images_viewed": ["00000001.jpg", "…"], "count": 26,
   "pages": [{"file": "00000001.jpg", "kind": "표지|타이틀컷|크레딧면|본문|판권면|빈 쪽|광고|끝|그 밖", "order": 1,
              "text": [{"what": "제목|권차|회차 제목|저자|역할|제작처|발행처|필명|본명|영문 표기|판 표시|연령 표시|ISBN|발행일|수상|약어|시즌·외전 문구|그 밖", "quote": "글자 그대로", "where": "상단 로고|하단 크레딧|…"}],
              "grayscale_only": true, "problems": ["깨짐|빈 쪽|중복 의심|쪽 번호 끊김"]}],
   "summary": {"title_as_seen": "", "part_as_seen": "", "part_name_as_seen": "", "authors_as_seen": [{"name": "", "role": "", "file": "", "order": 1}], "producers_as_seen": [], "alt_names_as_seen": [], "edition_as_seen": "", "age_mark_as_seen": "", "isbn_as_seen": "", "date_as_seen": "", "awards_as_seen": [], "color": "천연색|흑백", "color_reason": ""},
   "not_found": ["판권면 없음", "저자 표기 없음"]}
  ```
  사실만 적고 판단은 작품 에이전트가 한다. `order`(장 번호)를 적어 두면 "같은 원문 안에서 먼저 나오는 것 채택"(지침 0.3·2)과 "표제면 > 판권기 > 표지"(직원 답변 21) 규칙을 작품 에이전트가 바로 적용할 수 있다.
- 작품 에이전트는 관찰 파일의 `summary` 를 모아 회차끼리 다른 점(저자 표기가 회차마다 다름, 어떤 회차에만 수상 표시)을 찾고, 다른이름은 회차마다(직원 답변 20) 넣는다.

**고정 도구 둘(에이전트 허용 명령에 추가).**
- `kolis_tool look <이미지> [--tiles] [--zoom 영역]`: 긴 이미지를 읽을 수 있는 높이(예: 폭 기준 1.5배)로 잘라 조각 파일을 임시 폴더(`jobs/<작업>/_look/`)에 쓰고 경로 목록을 출력한다. `--zoom` 은 좌표 영역을 확대본으로 만든다. 이미지 자르기는 양식·사이트가 바뀌어도 깨지지 않는 일이라 코드로 두어도 09-29 원칙에 맞는다. 하위 에이전트는 `look` 결과의 조각을 Read 로 본다.
- `kolis_tool inspect <폴더>`: 기존 `inspect_files.inspect_folder` 를 에이전트가 부를 수 있게 JSON 으로 출력. **색 판정 고침**: 지금 `grayscale_all` 은 "이미지 모드가 L 또는 1 이면 단색"이라 RGB 로 저장된 흑백 스캔(옛 단행본)을 천연색으로 본다. 채도 분포(HSV 의 S 채널에서 일정 값 이상인 화소 비율)로 "무채색만인지"를 재게 바꾸고, 장마다 값을 돌려준다. 매뉴얼 7.4 의 정의(무채색 외 색이 하나 이상이면 천연색)와 맞고, 10-01 규칙(표지 천연색 + 본문 흑백 = 흑백)도 장 단위 값으로 판정할 수 있다. 최종 색 결정은 에이전트가 하되 숫자 근거를 받는다. `extent` 문구는 프로그램이 에이전트의 색 결정으로 만든다.

**검사·검수에 넣을 것.**
- 검사(3-A): 관찰 파일 수 = 회차 수, 각 관찰 파일의 `images_viewed` = 그 폴더의 이미지 목록(정리 뒤 모습 기준). 판단이 아니라 파일 증거 대조.
- 검수(`reviewer`): "관찰 파일에서 무작위로 회차 둘을 골라 그 폴더의 이미지를 직접 다시 보고 관찰과 대조한다. 다른 점이 있으면 어느 파일 어느 글자인지 적는다." 지금의 "원고 이미지를 몇 장 열어 본다"를 대체.

**이 관찰 파일이 채우는 다른 할 일.** `docs/HANDOFF.md` 2-5절의 "①단계에서 원문을 읽을 때 회차마다 표제면·판권기·표지의 글자를 관찰 기록으로 남겨 ③단계(구축)가 다시 보지 않고 쓰게 한다(할 일)". 3-2 보정 때 `build-mods-work` 가 다른이름을 위해 회차 폴더의 처음·끝 이미지를 다시 보던 것(2-6)을 관찰 파일 읽기로 바꾼다. 관찰 파일은 `work/<작품>.작업.json` 에 경로를 남겨 3번 카드가 찾는다.

### 3-C. 값 결정(에이전트 스킬 전면 재작성)

**스킬 `prepare-import` 를 새로 쓴다.** 구조:
0. 시작: `knowledge/platform-notes.md`, `knowledge/corrections.md`, `knowledge/rules/build-judgment-rules.md`(직원 답변, 가이드보다 우선) 읽기. 헷갈리면 `knowledge/rules/INDEX.md` → `MODS_입력가이드.md`.
1. 납품 자료 읽기: `snapshot.txt`, 폴더·행 짝짓기, 정리 계획(지금 1-5절 그대로).
2. **원문 관찰**: 회차마다 하위 에이전트(`observe-episode`)를 띄워 관찰 파일을 받는다. 전부 받은 뒤 다음으로.
3. 웹 조사: `research-work` 그대로(최초 연재 플랫폼·회차별 공개일·가격·등급·발행처 소재지·ISBN).
4. 전거·주제명·UCI·발행지 조회: 저자마다 `authority`(후보), UCI 는 `render` 로 서지정보유통지원시스템(`https://www.nl.go.kr/seoji/contents/S80300000000.do?page=1&pageUnit=10&schType=simple&schStr=<작품명>`, 작품명·ISBN·발행처명으로 각각), 발행지는 `render` 로 문체부 출판사 검색(`https://book.mcst.go.kr/html/searchList.php?search_area=전체&search_state=13&search_kind=1&search_type=1&search_word=<출판사>`). 주제명은 고정 두 묶음(직원 답변 11~13).
5. **트리 채우기**: 요소마다 지침 조항을 번호·원문으로 적고(요약 금지), 관찰 파일의 어느 글자에서 왔는지 `sources` 에 적는다. 조항 목록은 1-7절 전부 + 다음:
   - 전거 연결(직원 답변 A 1~6): 후보 상세정보(JOB·BRANCH·SUMMARY·ORGANIZATION·BIRTH_YEAR·SPECIESA_CNT)와 웹 검색 둘 다로 "강한 확신"일 때만 `@ID`·`@authority` 를 넣는다. 이름만 같으면 아님. 동명이인 중 만화가가 둘 이상이면 대조 없이 고르지 않는다. 전부 다른 직업이면 연결 안 함. "요청하기" 안 씀. 글·그림 각각. 전거형 ≠ 원문 표기이면 저자명은 전거형, `displayForm` 과 다른이름(no specific type)에 원문 표기(2.1·2.2).
   - 다른이름(B 7~10): 원문에 있을 때만, 영문 '성, 이름', 유형 셋 중 하나, 회차마다.
   - 주제명(C 11~14): 만화[漫畵] KSH1998022212 topic + 웹툰[webtoon] KSH2016000049 genre, `@authority` 국립중앙도서관주제명표목표. 장르물이어도 둘만. `genre` 요소(장르 "만화")는 그대로.
   - 발행처·발행지(D 15~17): 제작사 기본, 플랫폼이 직접 발행했을 때만 플랫폼. 발행지 코드는 문체부 검색. 발행처 둘이면 발행일은 첫 묶음에만.
   - UCI(E 18): 찾으면 둘째 식별기호(`@type` uci), 없으면 비움. 지침 13 의 "엑셀에 기입하지 않음"은 10-03 시험으로 반입이 되는 것이 확인됐으므로 따르지 않는다(단 4-E 의 미확인 사항 참고).
   - 입수처 주기(E 19): 사업 고정값(프로그램 설정). 제작지원(funding) 주기는 원문·엑셀에 있으면 넷째 이후 주기로(열 시험 전까지는 issues 에도 같이).
   - 성인물(G 24~25): 이용대상자 '성인용', 주기 "19세 미만 구독불가", 접근제한 1. 종 화면 이용제한은 프로그램이 한다.
   - 10-01 직원 규칙 14개(`docs/PLAN-2026-10-01.md` 2절) 그대로.
   - 양식에 넣을 수 있는지 **시험 전인 항목**(4-E): 둘째 표제정보 묶음의 그 밖 유형, 생몰년 둘째 저자명, 한 저자의 다른이름 여럿, funding 주기, 총서사항·종이책 관계, 불용어 → 시험 전까지는 트리에 넣되 `issues` 에 "시험 전 항목"이라고 같이 적는다. 직렬화기는 열을 낸다.
6. 쓰기와 검사: `write-import` → 걸린 것 고침 → 통과.
7. 검수: `reviewer`.
8. 배운 것 적기.
9. 끝: 반입용 엑셀 경로, 행 수, 확인할 칸 목록, 엇갈림, 찾지 못한 값, issues.

**스킬 `observe-episode`(새로).** 입력: 폴더 경로, 작품 제목(참고), 결과 파일 경로. 도구: Read, `look`, `inspect`, Write. 순서: `inspect` 로 파일 목록·이상·장별 채도 → 이미지를 순서대로 전부 Read(긴 것은 `look` 조각) → 장마다 기록 → `summary` → `images_viewed` 가 폴더 전부인지 스스로 확인 → 저장. 지어내지 않는다, 안 보이면 "읽을 수 없음".

**검수 에이전트 `reviewer.md` 6절(반입용 값) 재작성.** 관찰 무작위 대조(3-B), 전거 연결 저자는 후보 상세와 근거 주소를 직접 열어 확인(지금 "MODS 구축 판단" 절의 1~2번을 여기로), UCI 는 근거 주소를 열어 같은 작품·권차·발행처인지, 다른이름은 관찰 파일에 그 글자가 있는지, 주제명 두 묶음, 트리 값이 조사 결과와 같은지, 10-01 규칙 14개, confirm 글투. "MODS 구축 판단" 절은 보정용으로 축소.

**스킬 `build-mods-work` 축소.** 입력은 그대로(프로그램이 KOLIS 화면을 읽은 것) + 1단계 `import.json`·관찰 파일 경로. 하는 일: 반입값과 KOLIS 값이 다른 칸, 회차끼리 다른 칸, 지침과 어긋나 보이는 칸을 보고(2-7). 전거·주제명·UCI·다른이름 판단은 하지 않는다(1단계 값이 정본). 직원 보정은 화면에서.

### 3-D. 사람 확인·화면
- 확인 지점은 지금처럼 반입 전 한 곳(확인할 칸 표 + 엑셀 노란 칸 + 확인 완료 버튼).
- 표를 경로 기준으로 다시 그린다: 칸(경로 #묶음 (한글)), 행, 넣은 값, 출판사 값, 왜, 근거(주소·원문 파일·화면 글자), 직원이 정할 것. 새로 들어가는 항목(전거 연결·다른이름·UCI·둘째 출처정보)은 근거 펼침(전거 후보 상세 표, 서지정보 검색 결과 글자, 관찰 파일의 장과 글자).
- 직원이 전거 번호를 바꾸거나 연결을 끊는 입력 칸(지금 3-2 「직원 결정으로 바꾸기」를 1단계 표로 옮김). 바꾸면 `import.json` 의 그 값에 `source: staff` 를 적고 엑셀을 다시 쓴다(확인 완료 전이므로 안전).
- 3-2 카드: 「KOLIS 값 읽어 대조」(원부의 콘텐츠마다 MODS XML 을 읽어 반입용 엑셀 트리와 칸마다 비교, 전부 같으면 한 줄) + 「틀린 칸 고쳐 저장」(다른 칸 목록에서 직원이 어느 쪽 값으로 할지 고르고, 그 칸만 바꾼 저장 본문을 화면 저장 함수 가로채기로 만들어 보내고 전·후 XML 대조). 「작품 전체 판단」·「저장 본문 준비」·「한 번에 넣기」 단추는 뺀다.
- `prepare.py` `result`: `import`(트리), `confirm_cells`, `observations_dir`, `title`, `unit`, `output_xlsx`, `rows`, `manuscripts`, `thumbs`, `research`, `remaining`, `finalize`, `run`.

### 3-E. 도서관 PC 에서만 되는 확인(이 설계의 전제가 되는 미확인 사항)
1. **반입값이 끝까지 살아남는지.** 10-03 시험은 반입 직후 접수 목록이 돌려주는 MODS 까지만 봤다. 원문등록 → 등록대상처리 → 가원부 → (복본조사 뒤) 구축 화면에서 전거 번호·다른이름 유형·디스플레이형식·UCI·둘째 출처정보가 그대로인지, 구축 화면 저장(`updateHarContents.do`)이 그 값을 지우지 않는지(1614 1화 저장 전·후 XML 로 전거·주제명은 유지됨이 확인됐지만 다른이름·displayForm·UCI·둘째 출처정보는 미확인)를 원시인 삼촌 한 작품으로 한 바퀴 돌려 봐야 한다. 확인 방법: `POST /online/contents/popup/getHarContentsXml.do`(contentsId)로 단계마다 MODS XML 을 받아 대조(`mods_compare.py`).
2. **아직 시험 안 한 열**: 둘째 표제정보 묶음 전체(대등표제 `[@type]=parallel` 은 됨), 전거 연결 저자의 생몰년 둘째 `namePart`(그림 27·28 의 `1956-`, `namePart[@type]=date` 로 추정), 한 저자의 다른이름 여러 개, 주기 유형 `funding`, 총서사항(`relatedItem[@type]=series` + titleInfo)·종이책 관계(`relatedItem[@type]=otherFormat` + recordInfo/recordIdentifier), 불용어 `nonSort`, 주제명 묶음의 부모 열 표기(`/mods/subject/` 로 썼음), 셋째 이상 출처정보 묶음, 발행처 3칸 이상. 직렬화기는 이 열들도 낼 수 있게 만들되, 시험 전까지는 에이전트가 `issues` 에 "시험 전 항목"으로 같이 적는다.
3. 지침 13 "UCI 반입 오류"가 등록대상처리·가원부·원부 작성 단계에서 나는 오류인지(반입 직후에는 안 났음). 1번 시험에서 같이 본다.
4. 묶음 사이 열 순서가 파서에 영향을 주는지(Sample 순서를 지키면 확인 불필요. 바꿀 일이 생기면 그때 시험).
5. 반입용 엑셀 1개 500건 제한(매뉴얼)과 열 수 상한이 있는지(열이 150개를 넘는 작품이 나오면 시험).
6. 10-01 목록의 직원 확인 항목(비고 번호 484, 무료 회차 보상금 0·빈칸, 예고편 1건 여부, 완결 표기, 썸네일 thum_files, 연결 8개, 납품 파일 이름, 취소 요청 목록 전달)과 10-03 목록(1610 저스툰 수집본 내용 동일 여부, 1607 ISBN 25화 동일, 출처정보 2개인 작품 예)은 그대로 남아 있다.

---

## 4. 순서(맥북 ①~④, 도서관 PC ⑤~⑥)

| 순서 | 일 | 시험 | KOLIS 요청 | 어디서 |
|---|---|---|---|---|
| ① | 서지 모형(`import.json` 새 정의) · 직렬화기 `mods_sheet.py` · 검사 `import_check.py` · 템플릿 Contents 머리글 제거 | 예시 88열 역변환 → 셀 단위 동일 / `import_probe.build()` 논리로 1~3차 열 목록 재현 | 없음 | 맥북 |
| ② | `look`·`inspect` 명령, 채도 기반 색 판정, `agent.job_tools` 허용 목록 | 긴 이미지 1장·흑백 스캔 1장으로 조각·판정 확인(샘플 이미지는 유저가 준다) | 없음 | 맥북 |
| ③ | 스킬 `prepare-import` 전면 재작성, `observe-episode` 신설, `reviewer` 재작성, `build-mods-work` 축소, `agent_home/CLAUDE.md` 용어·순서 갱신 | 시험 폴더가 있으면 에이전트 1회(전거 조회는 실패 전제) | 없음(`authority` 는 도서관에서만) | 맥북(재료 있을 때) |
| ④ | 화면·API: 확인할 칸 표(경로 기준·근거 펼침·직원 결정 입력), 3-2 축소, `prepare.run` 결과 구조, `mods_compare` 트리 읽기 | 가짜 백엔드 `tools/ui_shots.py` 로 렌더 확인 | 없음 | 맥북 |
| ⑤ | 원시인 삼촌으로 1단계 전체 실행(프로그램 창) → 확인 완료 → 2번 등록(반입 → 원문 → 가원부) → 단계마다 MODS XML 받아 전 칸 대조 → 접수 취소 요청. 3-E 의 미확인 열도 같은 건에 끼워 시험 | 전 칸 대조 보고 | 반입·원문·가원부·조회 | 도서관 PC(직원 입회) |
| ⑥ | 결과로 스킬·직렬화기·검사 보정 → 다음 작품(옆집 기러기 아빠, 썸네일 있는 작품) → 원부번호가 나오면 3-2 대조만으로 ③구간이 끝나는지 확인 | 같은 작품 두 번 실행해 값이 같은지 | 같음 | 도서관 PC |

우선순위는 ① → ③ → ② → ④ (직렬화기와 스킬이 핵심, 도구와 화면은 그다음). ①의 역변환 시험이 통과하기 전에는 스킬을 돌리지 않는다(결과를 쓸 수 없으므로).

---

## 5. 지키는 것(변함없음)
- KOLIS 요청은 직원 입회 아래, ⑤ 이후에만. 비밀번호 5회 오류 = 계정 잠김. 계정은 `.env`·프로그램 창에만.
- 에이전트는 KOLIS 에 닿지 않는다(`authority`·`render` 는 프로그램이 대신 조회).
- 도서관 양식 밖의 중간 산출물을 만들지 않는다(관찰 파일·`import.json` 은 에이전트 작업 폴더 안의 내부 파일이고 직원이 보는 파일은 출판사 엑셀과 반입용 엑셀 둘뿐).
- 검사는 판단하지 않는다. 결과가 흔들리면 코드로 묶지 말고 스킬·검수·지식을 고친다.
- 시험은 프로그램 창으로(도서관 PC). 같은 작품을 두 번 돌려 같은지 본다.
- 금액은 보고하지 않는다. 모델은 Sonnet.
- 세션 끝: `EXECUTION-LOG`·`HANDOFF`·README·`docs/memory/` 갱신 → 커밋·푸시.

## 6. 유저 말과 하나씩 대응(결론)
1. "내 목적은 무조건 가능한, 최대한 최초 '반입용 메타데이터 작성'에서 모든걸 끝내고 싶다. 최종 실험도 이걸 위함이었어." → 2-1: 반입으로 끝낼 수 있는 항목은 시험으로 확인된 전부. 못 끝내는 것은 성인물 이용제한(종 화면)·복본조사·사후 보정 셋. 3-2 는 대조·보정으로 축소. "끝까지 살아남는지"는 3-E 1번으로 도서관 PC 에서 확인.
2. "mods 헤더는 고정하지 말자 … 작품마다 유동적으로 반복할 수 있어야해." → 2-2·3-A: 83열 템플릿과 고정 사전을 버리고, 에이전트가 MODS 트리를 쓰고 고정 코드가 Sample 규칙으로 열을 직렬화.
3. "절대로 하위호환성 신경쓰지말고 필요하면 전부다 갈아엎어서라도 구현해야한다." → 2-3 의 버림·살림·손볼 것 목록.
4. "2 묶음 으로 고정하는것도 아니지. 그 이상있으면 더 여러 묶음으로 작성해야지." → 2-2: 모든 반복 요소를 n묶음, 상한 없이. 묶음 수는 작품 행들의 최대치. 주제명 "둘만"은 내용 규칙, "반복불가"는 지침을 에이전트가 따르는 것.
5. "원래 작업하던 내부망 컴퓨터에서 작업을 마무리 하고 내 개인 맥북으로 환경을 옮겼다." / "오늘은 그래서 kolis에 요청을 보내는 등의 테스트를 할수 없다." → 1-9: 오늘은 4절의 ①~④까지.
6. "자리 옮기기 직전에 각종 메뉴얼 및 mods 요청 응답 테스트를 해서 … 고도화 테스트를 했다." → 1-8: 그 결과가 이 설계의 근거.
7. "에이전트가 원문을 직접 저 보고(가능하면 전체) 필요한걸 더 수집해서 반입욕 메타데이터 작성을 고도화 하고싶다." → 3-B: 회차 단위 하위 에이전트 + 관찰 파일 + `look`·`inspect` + "봤는지" 검사.


---

## 7. 리뷰 반영 기록(2026-10-04, 서브에이전트 리뷰 3개 — 코드 실현성·지침 정합성·에이전트 운용. 지적 48건, 기각 0)

유저 지시 "전부 반영"에 따라 위 본문의 설계를 아래와 같이 고쳐 구현했다. 본문(3절)과 다르면 **이 절이 우선**이다. 코드가 정본이다(`kolis_tool/mods_sheet.py`, `import_check.py`, `look.py`, `agent.py`, `prepare.py`, `agent_home/`).

### 7-1. 직렬화·역변환 시험(코드 2-1~2-7, 지침 1-1~1-7)
- 기준 열 순서는 **예시 88열(=템플릿 83열) 순서**다. Sample 시트 순서가 아니다(Sample 은 저자 묶음이 맨 끝). Sample 은 한글 이름·선택값 사전으로만 쓴다. → `mods_sheet.ORDER_TOP`.
- 속성 열 위치는 일반 규칙이 아니라 묶음마다 예시·시험 엑셀 그대로 표로 박았다(`GROUP_ORDER`): name = 부모·@usage·namePart·@type·@ID·@authority·role·displayForm·alternativeName / titleInfo = 부모·title·@type… / subject = 부모·topic|genre·@ID·@authority / originInfo = 부모·@eventType|@type·place·issuance·publisher×n·dateIssued·edition.
- **발행지 구조**: 첫 출처정보는 부모 열 없이 placeTerm 쌍(템플릿·예시·끝까지 등록된 사례 모양), 둘째 이후는 placeTerm 마다 부모 열 `/mods/originInfo/place`(1차 시험 꼴 = `<place>` 둘 = 구축 완료 XML 그림 34). 본문 3-A 규칙 4("묶음마다 한 번")는 폐기. 구축 화면·점검 추출에서 어떻게 보이는지는 3-E.
- 역변환 시험 기준: 머리글 동일(첫 출처정보에 부모 열을 두지 않으므로 예시와 같아진다) + **값이 있는 셀의 (행, 경로, n번째, 값) 집합 동일**. 빈 묶음은 최소 묶음 수(`MIN_COUNTS`, 템플릿 모양)로 재현한다. `location` 안 열은 예시대로 url·url·physicalLocation·url(77열 도서관 예시는 physicalLocation 이 앞이라 같은 묶음 안 형제 순서는 파서가 가리지 않는다).
- 다른이름 유형 열은 `[@type]`(Sample·템플릿 표기). `[@altType]` 은 읽을 때만 받는다.
- 한글 이름 사전 = Sample + 코드 보충(`LABELS_EXTRA`, 전거·다른이름·UCI·판사항 등 15개). `(사용안함)` 꼬리는 뗀다. 값 규칙 검사 기준 = **예시 88열 값 + 10-03 시험 값**(개인명/단체명, BornDigital, JPG, kormarccountry, text/code, iso639-2b). Sample 선택값은 예시에 없는 열에만.
- 둘째 출처정보 속성 열 이름(`[@type]` vs `[@eventType]`)과 XML 에 들어간 속성, 3차 시험 결과는 RECON 9 에 기록이 없음 → 3-E·`FIELD-CHECKLIST.md` C-3.
- `[제작]` 은 이름 뒤 한 칸 띄움(지침 예 `다온웹툰 [제작]`). 검사가 붙여 쓴 것을 거부. 같은 묶음 둘째 칸 제작처에 붙이는지는 직원 질문.
- 트리 예시의 잘못(전거 미연결 저자에 디스플레이형식, 시험용 KAC 번호)은 스킬에서 바로잡음: 디스플레이형식은 전거 연결 저자에만, 검사도 거부.
- 대등표제는 "됨"이 아니라 "완료 사례 승인 엑셀에 있었음, XML 미확인". 주제명 부모 열 표기와 funding 주기는 확인된 항목으로 옮김.

### 7-2. 결과 파일·검사·코드 의존(코드 1-1~1-3, 3-1~3-3, 4-1~4-2, 5-1~5-4, 6-1~6-2)
- `import.json` = `common.mods`(공통) + `rows[].mods`(행마다 다른 값, 최상위 요소 단위로 덮음) + `extra` + `confirm[].path`(트리 경로 **하나**) + `sources[].path`. 고정값은 트리에 항상 적는다(설정 `project` 는 에이전트에게 주는 기본값). 언어는 에이전트가 정한다(지침 6 "본문 내용의 언어").
- `mods_compare.import_rows` 는 `read_sheet` 로 트리를 읽고, 대조에 전거·다른이름·디스플레이형식·주제명·UCI·출처정보 수를 더했다.
- 성인물 이용제한 자동 실행의 방아쇠: `build_status` 가 build.json 이 없으면 1단계 `import.json` 의 `adult` 를 `judgment` 로 넘긴다(`_import_for_wonbu`). 1단계 결과에 작품 단위 `adult`·`adult_reason`.
- `app._view` 는 트리를 경로로 읽고(`mods_sheet.get`), 칸 이름 `경로 #묶음 (한글)`. 직원 결정 `set_author`(확인 완료 전만, 엑셀 다시 씀).
- 역변환 시험은 직렬화기만 부른다(`folder=None`). 10-03 시험 배치는 `import_probe.build()` 대신 트리로 재현(`tools/import_sheet_tests.py` 2번). `import_writer.py`·`import_probe.py`·`import_roundtrip.py` 삭제.
- `inspect` 색 값 `흑백`, 채도 비율 판정, `--no-dup`. `look`·`inspect-folder` 는 `cli.py` 와 `agent.job_tools` 둘 다. 하위 에이전트의 도구 제한은 에이전트 정의의 `tools:` 로(코드로는 못 막음).
- 맥북: `KOLIS_AGENT_HOME`(상위 `~/CLAUDE.md`), `tools/ui_shots.py` 저장소 기준 경로 + chromium 대체(`.venv-mac` 에 playwright).

### 7-3. 지침·직원 답변(지침 2-1~2-3, 3-1~3-6, 4-1~4-4, 5-1~5-2, 6)
- 스킬에 추가한 조항 원문: 2.1 전거형이 없을 때 저자명 표기(한국인 성이름, 영문만 '성, 이름', 서양인 원어 '성, 이름', 구분 불명이면 원문 그대로, 일본인, 필명·본명 둘 다면 널리 알려진 이름)·영문저자명 대소문자 / 5·5.2 "발행처를 가장 먼저", "1화·최초 플랫폼 기준" / 8 "전체이용가·12세·15세는 일반이용자 + 주기", "기초메타데이터로 성인용이면 성인용" / 11 분류 예외 보고(024.2) / 1.1 둘 이상 언어·★☆ 기호 / 1.6 대등표제 관사 / 5.4 판사항 둘 이상 쉼표·아라비아 숫자 / 14.1 연재처 소멸 시 미기재 / 13 ISBN 괄호 안 숫자 미기입.
- 정보원 순위: **직원 답변 21(표제면 > 판권기 > 표지)이 우선**, 지침 0.3 ③(먼저 나오는 것)은 같은 종류의 장 안에서만.
- 다른이름·필명 주기는 원문에 있을 때만(답변 10). 영문 다른이름 '성, 이름'(답변 8, 지침 그림 28 과 다르면 답변 8).
- 성인물 접근제한 1 은 완료 사례 근거뿐 → 검사가 confirm 을 요구, 직원 질문.
- 3-E 에 추가(FIELD-CHECKLIST C-3): 둘째 이후 저자 묶음의 다른이름·디스플레이·전거 열, 둘째 출처정보 속성, 발행지 구조의 구축·점검 표시, 저자 묶음 속성 열 위치 변경 가능 여부, 대등표제, 접근제한 1, `[제작]`, 발행처 2칸 3차 결과, 생몰년 열, `[@usage]` 빈 열, `location` 열 순서.

### 7-4. 에이전트 운용(운용 1~7)
- `observe-episode` 는 스킬이 아니라 **에이전트 정의**(`agents/observe-episode.md`, `tools: Read, Write, Glob, Bash, PowerShell` — 웹 도구 없음). 작품 제목을 넘기지 않는다. 장마다 관찰 파일에 덧붙여 저장. `uncertain`·`split_suggested`. 한 번에 3개, 없으면 한 번 더, 두 번째도 없으면 issues 에 적고 멈춤. 검수 에이전트는 하위 에이전트를 부르지 않는다.
- 타임아웃 = 3600 + 이미지 장당 10초(상한 7200). 타임아웃 뒤 같은 대화 `--resume` 1회(10-01 "이어서 실행 금지"는 접수번호가 남는 KOLIS 구간 규칙이고 에이전트 작업 폴더에는 해당 없음). 진행은 실행기 로그의 Agent 호출로 보인다.
- 하위 에이전트 마지막 답은 한 줄. 작품 에이전트는 `summary` 만 읽고 필요한 회차만 `pages` 를 연다. `import.json` 은 common + rows.
- `look`: 기본 조각 1500×1500, `--fit` 긴 변 1500 축소본, `--zoom N:상|중|하`(좌표 없음), 절대 경로 출력, `KOLIS_LOOK_DIR`(작업 폴더 `_look/`, 끝나면 삭제). 조각은 `images_viewed` 에 넣지 않고 `tiles_of` 로.
- **"봤는지" 검사 = 실행기의 Read/look 호출 기록 대조**(`agent._record_read` → `_reads.json` → `import_check`). 파일 목록 대조는 보조.
- `authority` 실패(`error`) ≠ 후보 없음: 연결 판단 없이 원문 표기, confirm 에 "조회하지 못했습니다", 검사가 "전거 없는 저자마다 캐시 파일 또는 confirm" 요구. 캐시 경로 절대 경로.
- 검수의 무작위 회차 둘: 첫·마지막 회차 제외, 번호만 적기, Read 기록으로 실제로 열었는지 확인, 조각 60 넘는 회차는 표지·처음 3장·마지막 3장만.
- 과거 제약: 절대 경로만, `#`·`★` 경로 인자 1회 시험, `|` 잇기 금지.

### 7-5. 유저 결정(권한 쪽으로 정함, 2026-10-04 "알아서")
1. 발행지 구조 기본값 = `<place>` 둘(1차 꼴, 그림 34). 2. `ui_shots.py` 는 맥북에서 고쳐 돌림(`.venv-mac`). 3. 직원 질문 추가(FIELD-CHECKLIST C-3). 4. `MAX_AGENTS` 3 유지(⑤ 시험에서 429 가 나면 2).

### 7-6. 구현 상태(2026-10-04 맥북)
①~④ 끝(`docs/EXECUTION-LOG.md` 2026-10-04 항목). 시험: `tools/import_sheet_tests.py` 3/3 통과, 검사 끝까지 1건 통과, `look`·`inspect-folder` 합성 이미지 확인, 화면 렌더 `tools/ui_shots.py` 확인. ⑤·⑥은 도서관 PC.
