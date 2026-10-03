# MODS 칸의 모수 — 지침 · KOLIS 수정 화면 · 반입 양식 (2026-10-03, 읽기만으로 모음)

만든 도구: `tools/mods_fields_doc.py`. 출처 세 가지를 경로 기준으로 합쳤다. 경로 표기는 `/mods/요소/하위요소[@속성]`.

| 출처 | 무엇 | 수 |
|---|---|---|
| A 지침 | MODS 입력가이드 0.5 전체 요소 목록(전자책 기준) | 55 |
| B KOLIS 화면 | MODS 수정 화면(onContentsDetailPop)의 칸 — 저장 요청이 받는 전부(1614 1화 폼 기록) | 174 |
| C 반입 양식 | 템플릿 Sample 시트 「필드설명」(도서관 공식 열 설명) | 50 |
| C' 템플릿 83열 | 실제 승인된 양식의 열(고유 경로 54) | 83 |
| C'' 예시 88열 | 완료 사례 로맨스낫로맨틱(고유 경로 54) | 88 |
| D 반입 확인 | 반입 직후(저장 전) XML 에서 실제로 들어간 요소·속성 | 42 |

## 1. 결론(반입에서 끝낼 수 있는가)

- **반입 파서는 경로 열을 그대로 받는다.** Sample 필드설명에 **없는** 열(`/mods/name[@usage]`, `/mods/note[@type]`, `/mods/originInfo[@eventType]`, `/mods/classification[@edition]`, `/mods/originInfo/edition`)이 템플릿·예시에 있고, 그중 `name[@usage]`·`note[@type]`·`originInfo[@eventType]`·`classification[@authority]`·`placeTerm[@authority]` 는 반입된 XML(D)에 그대로 들어가 있다 → 속성 열은 '앞 요소에 속성을 붙인다'는 일반 규칙으로 처리된다(Sample 2행: "엘리먼트를 먼저 기술하고 속성을 기술한다").
- 따라서 **저자 전거(`/mods/name[@ID]`, `/mods/name[@authority]`), 주제명 전거(`/mods/subject[@ID]`, `/mods/subject[@authority]`), 장르주제명(`/mods/subject/genre`), 다른이름 유형(`/mods/name/alternativeName[@altType]`)** 도 같은 규칙이면 반입으로 들어갈 가능성이 높다. B(KOLIS 화면)에 그 칸이 모두 있으므로 저장소 쪽 자리는 있다.
- **미확인(문서로는 끝까지 확정 못 함):** 반입 파서가 Sample 목록 밖의 속성 이름을 전부 받는지, `[@altType]` 과 Sample 의 `[@type]` 중 어느 표기를 쓰는지, UCI(`identifier[@type]=uci`)는 지침 13 이 "반입하면 오류"라고 적음. 확정하려면 **반입 1회**(가원부번호까지 → 접수번호 취소 요청, 되돌릴 수 있음)가 필요하다. 시험 열: `name[@ID]`·`name[@authority]`·`subject[@ID]`·`subject[@authority]`·`subject/genre`(둘째 주제명 묶음)·`alternativeName[@altType]`. 유저 결정(10-03): 이 길은 가지 않기로 했으므로 **결정이 바뀔 때만**.
- Sample 의 `name[@type]` 값은 `personal/corporate/conference` 인데 템플릿·예시·반입 XML 은 `개인명` 을 썼고 그대로 들어갔다(저장 뒤 KOLIS 가 `personal` 로 바꿈). `displayForm` 은 Sample 에 "(사용안함)".

## 2. 경로별 대조표

| 경로 | A 지침(반복/필수) | B KOLIS 화면 | C 필드설명(한글명 · 값 규칙) | 83열 | 88열 | D 반입 확인 |
|---|---|---|---|---|---|---|
| `/mods/titleInfo` | 표제정보 ○/필수 | ○ | 표제사항 | 2 | 2 |  |
| `/mods/titleInfo[@displayLabel]` |  | ○ |  |  |  |  |
| `/mods/titleInfo[@type]` |  | ○ | type · 아래 텍스트 중 하나가 들어가야 합니다. / uniform     : 통일표제 / title       : 본표제 / parallel    : 대등표제 / translated  : 번역표제 / original     | 2 | 2 |  |
| `/mods/titleInfo[@nameTitleGroup]` |  | ○ |  |  |  |  |
| `/mods/titleInfo[@ID]` |  | ○ |  |  |  |  |
| `/mods/titleInfo/title` | 표제 ○/필수 | ○ | 웹툰명 | 2 | 2 | ○ |
| `/mods/titleInfo/subTitle` | 표제관련정보 ○/해당 시 필수 | ○ | 부제목 | 2 | 2 |  |
| `/mods/titleInfo/partNumber` | 권차 ○/해당 시 필수 | ○ | 권차(회차) | 2 | 2 | ○ |
| `/mods/titleInfo/partName` | 권차표제 ○/해당 시 필수 | ○ |  | 2 | 2 |  |
| `/mods/titleInfo/nonSort` | 불용어 -/해당 시 필수 | ○ | 배열시 제외문자 |  |  |  |
| `/mods/name` | 저자정보 ○/필수 | ○ | 저자정보 | 3 | 4 |  |
| `/mods/name[@nameTitleGroup]` |  | ○ |  |  |  |  |
| `/mods/name[@usage]` |  | ○ |  | 1 | 1 | ○ |
| `/mods/name[@ID]` |  | ○ |  |  |  |  |
| `/mods/name[@authority]` |  | ○ |  |  |  |  |
| `/mods/name[@type]` |  | ○ | type · 아래 텍스트 중 하나가 들어가야 합니다. / conference : 회의명 / corporate  : 단체명 / personal   : 개인명 | 3 | 4 | ○ |
| `/mods/name[@xlink]` |  | ○ |  |  |  |  |
| `/mods/name/namePart` | 저자명 ○/필수 | ○ | 저자명 | 3 | 4 | ○ |
| `/mods/name/namePart[@type]` |  | ○ |  |  |  |  |
| `/mods/name/etal` | 기타 -/해당 시 필수 | ○ |  |  |  |  |
| `/mods/name/role` |  | ○ | 역할 | 3 | 4 |  |
| `/mods/name/role/roleTerm` | 역할/역할어 -/해당 시 필수 | ○ | 역할어 | 3 | 4 |  |
| `/mods/name/displayForm` | 디스플레이 형식 -/선택 | ○ | 디스플레이형식(사용안함) |  |  |  |
| `/mods/name/alternativeName` |  | ○ | 다른이름 | 1 | 1 |  |
| `/mods/name/alternativeName[@altType]` |  | ○ |  |  |  |  |
| `/mods/name/alternativeName/namePart` | 다른이름 ○/해당 시 필수 | ○ |  | 1 | 1 |  |
| `/mods/typeOfResource` | 콘텐츠유형 -/필수 | ○ | 자료유형 | 1 | 1 | ○ |
| `/mods/genre` | 장르 -/필수 | ○ | 장르 · 만화 | 1 | 1 | ○ |
| `/mods/originInfo` | 출처정보 ○/필수 | ○ |  | 2 | 2 |  |
| `/mods/originInfo[@eventType]` |  | ○ |  | 1 | 1 | ○ |
| `/mods/originInfo/place` |  | ○ | 발행지 |  |  |  |
| `/mods/originInfo/place/placeTerm` | 발행지/발행지명 ○/해당 시 필수 | ○ | placeTerm | 2 | 2 | ○ |
| `/mods/originInfo/place/placeTerm[@authority]` |  | ○ | authority · 아래 텍스트 중 하나가 들어가야 합니다. / iso3166 / marccountry / marcgac | 1 | 1 | ○ |
| `/mods/originInfo/place/placeTerm[@type]` |  | ○ | type · code | 2 | 2 | ○ |
| `/mods/originInfo/publisher` | 발행처 ○/필수 | ○ | 발행자 | 2 | 3 | ○ |
| `/mods/originInfo/dateIssued` | 발행일 ○/해당 시 필수 | ○ | 발행일 | 2 | 2 | ○ |
| `/mods/originInfo/dateIssued[@encoding]` |  | ○ |  |  |  |  |
| `/mods/originInfo/dateIssued[@point]` |  | ○ |  |  |  |  |
| `/mods/originInfo/dateCreated` |  | ○ |  |  |  |  |
| `/mods/originInfo/copyrightDate` |  | ○ |  |  |  |  |
| `/mods/originInfo/dateOther` |  | ○ |  |  |  |  |
| `/mods/originInfo/dateOther[@type]` |  | ○ |  |  |  |  |
| `/mods/originInfo/edition` | 판사항 -/해당 시 필수 | ○ |  | 1 | 1 |  |
| `/mods/originInfo/issuance` | 발행연속성 -/필수 | ○ | 발행연속성 · 단행자료 | 2 | 2 | ○ |
| `/mods/originInfo/frequency` |  | ○ | 발행빈도 · 아래 텍스트 중 하나가 들어가야 합니다. / 연속간행자료인 경우 / => 일간/주간/격주간/월간/격월간/계간/반년간/연간/계속갱신/부정기간 /간행빈도 불명/기타 로 변경되었습니다. |  |  |  |
| `/mods/language` | 언어 ○/필수 | ○ |  |  |  |  |
| `/mods/language[@objectPart]` |  | ○ |  |  |  |  |
| `/mods/language/languageTerm` | 언어 ○/필수 | ○ | 본문언어 · 아래 텍스트 중 하나가 들어가야 합니다. / kor  : 한국어 / eng : 영어 / chi  : 중국어 / jpn  : 일본어 | 1 | 1 | ○ |
| `/mods/language/languageTerm[@authority]` |  | ○ |  | 1 | 1 | ○ |
| `/mods/language/languageTerm[@type]` |  | ○ | type · code | 1 | 1 | ○ |
| `/mods/physicalDescription` | 형태기술정보 -/필수 | ○ |  |  |  |  |
| `/mods/physicalDescription/form` | 자료형태 -/필수 | ○ | 자료형태 · 아래 텍스트 중 하나가 들어가야 합니다. | 1 | 1 | ○ |
| `/mods/physicalDescription/reformattingQuality` | 디지털 품질 -/필수 | ○ | 매체제작목적 · access       : 접근 | 1 | 1 | ○ |
| `/mods/physicalDescription/internetMediaType` | 디지털 자료유형 -/필수 | ○ | 디지털자료유형 · 아래 텍스트 중 하나가 들어가야 합니다. | 1 | 1 | ○ |
| `/mods/physicalDescription/extent` | 수량(크기) -/필수 | ○ | 크기(수량) | 1 | 1 | ○ |
| `/mods/physicalDescription/extent[@unit]` |  | ○ |  |  |  |  |
| `/mods/physicalDescription/digitalOrigin` | 원자료형태 -/필수 | ○ | 디지털 자료형태 · 아래 텍스트 중 하나가 들어가야 합니다. / born digital / digitized microfilm / digitized other analog / reformatted digital | 1 | 1 | ○ |
| `/mods/physicalDescription/note` |  | ○ | 주기 |  |  |  |
| `/mods/abstract` |  | ○ | 초록 |  |  |  |
| `/mods/abstract[@type]` |  | ○ | type · 아래 텍스트 중 하나가 들어가야 합니다. / 기타 / 서평 / 요약 / 초록 / 해제 |  |  |  |
| `/mods/abstract[@xlink]` |  | ○ |  |  |  |  |
| `/mods/tableOfContents` | 내용목차정보 ○/해당 시 필수 | ○ | 목차 |  |  |  |
| `/mods/tableOfContents[@type]` |  | ○ | type · 아래 텍스트 중 하나가 들어가야 합니다. / 기타목차 / 내용목차 / 부분목차 / 표목차 |  |  |  |
| `/mods/tableOfContents[@xlink]` |  | ○ |  |  |  |  |
| `/mods/targetAudience` | 이용대상자 -/필수 | ○ | 이용대상자 · 아래 텍스트 중 하나가 들어가야 합니다. / 고등학생 / 미상 / 성인용 / 아동용 / 일반이용자 / 중학생 / 초등학생 / 취학전아동 / 특수계층 | 1 | 1 | ○ |
| `/mods/note` | 주기사항 ○/해당 시 필수 | ○ | 서지적 주기 | 3 | 3 | ○ |
| `/mods/note[@type]` |  | ○ |  | 3 | 3 | ○ |
| `/mods/subject` | 주제명 ○/해당 시 필수 | ○ | 주제명 | 1 | 1 |  |
| `/mods/subject[@ID]` |  | ○ |  |  |  |  |
| `/mods/subject[@authority]` |  | ○ | 전거 |  |  |  |
| `/mods/subject[@authorityURI]` |  | ○ |  |  |  |  |
| `/mods/subject/topic` | 일반주제명 ○/해당 시 필수 | ○ | 일반주제명 | 2 | 1 | ○ |
| `/mods/subject/geographic` | 지리주제명 ○/해당 시 필수 | ○ |  |  |  |  |
| `/mods/subject/temporal` | 시대주제명 ○/해당 시 필수 | ○ |  |  |  |  |
| `/mods/subject/titleInfo` | 표제주제명 ○/해당 시 필수 | ○ |  |  |  |  |
| `/mods/subject/titleInfo/title` |  | ○ |  |  |  |  |
| `/mods/subject/genre` | 장르주제명 ○/해당 시 필수 | ○ |  |  |  |  |
| `/mods/subject/name` | 이름주제명 ○/해당 시 필수 | ○ |  |  |  |  |
| `/mods/subject/name[@ID]` |  | ○ |  |  |  |  |
| `/mods/subject/name[@authority]` |  | ○ |  |  |  |  |
| `/mods/subject/name[@type]` |  | ○ |  |  |  |  |
| `/mods/subject/name[@valueURI]` |  | ○ |  |  |  |  |
| `/mods/subject/name/namePart` |  | ○ |  |  |  |  |
| `/mods/subject/name/namePart[@type]` |  | ○ |  |  |  |  |
| `/mods/subject/hierarchicalGeographic` |  | ○ |  |  |  |  |
| `/mods/subject/cartographics` |  | ○ |  |  |  |  |
| `/mods/subject/cartographics/scale` |  | ○ |  |  |  |  |
| `/mods/subject/cartographics/projection` |  | ○ |  |  |  |  |
| `/mods/subject/cartographics/coordinates` |  | ○ |  |  |  |  |
| `/mods/subject/occupation` |  | ○ |  |  |  |  |
| `/mods/subject/geographicCode` |  | ○ |  |  |  |  |
| `/mods/classification` | 분류기호 ○/필수 | ○ | 분류기호 | 1 | 1 | ○ |
| `/mods/classification[@authority]` |  | ○ | authority · 아래 텍스트 중 하나가 들어가야 합니다. / DDC / KDC / LCC / UDC | 1 | 1 | ○ |
| `/mods/classification[@edition]` |  | ○ |  | 1 | 1 | ○ |
| `/mods/classification[@generator]` |  | ○ |  |  |  |  |
| `/mods/relatedItem` | 연관정보 ○/해당 시 필수 | ○ |  |  |  |  |
| `/mods/relatedItem[@type]` |  | ○ |  |  |  |  |
| `/mods/relatedItem[@xlink]` |  | ○ |  |  |  |  |
| `/mods/relatedItem/titleInfo` |  | ○ |  |  |  |  |
| `/mods/relatedItem/titleInfo[@type]` |  | ○ |  |  |  |  |
| `/mods/relatedItem/titleInfo/title` | 표제정보/표제 ○/해당 시 필수 | ○ |  |  |  |  |
| `/mods/relatedItem/titleInfo/subTitle` |  | ○ |  |  |  |  |
| `/mods/relatedItem/titleInfo/partNumber` | 표제정보/권차 ○/해당 시 필수 | ○ |  |  |  |  |
| `/mods/relatedItem/titleInfo/partName` | 표제정보/권차표제 ○/해당 시 필수 | ○ |  |  |  |  |
| `/mods/relatedItem/name` |  | ○ |  |  |  |  |
| `/mods/relatedItem/name[@type]` |  | ○ |  |  |  |  |
| `/mods/relatedItem/name/namePart` |  | ○ |  |  |  |  |
| `/mods/relatedItem/name/role` |  | ○ |  |  |  |  |
| `/mods/relatedItem/name/role/roleTerm` |  | ○ |  |  |  |  |
| `/mods/relatedItem/name/displayForm` |  | ○ |  |  |  |  |
| `/mods/relatedItem/name/alternativeName` |  | ○ |  |  |  |  |
| `/mods/relatedItem/name/alternativeName[@altType]` |  | ○ |  |  |  |  |
| `/mods/relatedItem/name/alternativeName/namePart` |  | ○ |  |  |  |  |
| `/mods/relatedItem/typeOfResource` |  | ○ |  |  |  |  |
| `/mods/relatedItem/identifier` |  | ○ |  |  |  |  |
| `/mods/relatedItem/identifier[@type]` |  | ○ |  |  |  |  |
| `/mods/relatedItem/location` |  | ○ |  |  |  |  |
| `/mods/relatedItem/location/url` |  | ○ |  |  |  |  |
| `/mods/relatedItem/part` |  | ○ |  |  |  |  |
| `/mods/relatedItem/part/detail` |  | ○ |  |  |  |  |
| `/mods/relatedItem/part/detail/number` |  | ○ |  |  |  |  |
| `/mods/relatedItem/part/detail/caption` |  | ○ |  |  |  |  |
| `/mods/relatedItem/part/detail/title` |  | ○ |  |  |  |  |
| `/mods/relatedItem/part/extent` |  | ○ |  |  |  |  |
| `/mods/relatedItem/part/extent/list` |  | ○ |  |  |  |  |
| `/mods/relatedItem/recordInfo` |  | ○ |  |  |  |  |
| `/mods/relatedItem/recordInfo/recordIdentifier` | 레코드정보/제어번호 ○/해당 시 필수 | ○ |  |  |  |  |
| `/mods/identifier` | 식별기호 ○/해당 시 필수 | ○ | 식별자 | 1 | 1 | ○ |
| `/mods/identifier[@type]` |  | ○ | type · 아래 텍스트 중 하나가 들어가야 합니다. / coi / doi / hdl / isbn / ismn / isrc / issn / issue number / istc / lccn / local / matrix numbe | 1 | 1 | ○ |
| `/mods/identifier[@typeURI]` |  | ○ |  |  |  |  |
| `/mods/location` | 소장정보 ○/필수 | ○ |  |  |  |  |
| `/mods/location/url` | 원문주소 ○/해당 시 필수 | ○ | 원문주소 | 3 | 3 | ○ |
| `/mods/location/physicalLocation` | 소장위치 ○/필수 | ○ | 소장위치 | 1 | 1 | ○ |
| `/mods/location/physicalLocation[@authority]` |  | ○ |  |  |  |  |
| `/mods/accessCondition` | 접근제한정보 -/필수 | ○ |  |  |  |  |
| `/mods/accessCondition/licenseType` | 접근제한유형 -/필수 | ○ | 저작권유무 · 아래 텍스트 중 하나가 들어가야 합니다. / 0 : 외부 공개 / 1 : 비공개 / 2 : 국립중앙도서관 공개 / 3 : 국립중앙도서관, 국립어린이청소년도서관, 협력기관(공공.대학.전문/특수.해외.작은도서관) 공개  | 1 | 1 | ○ |
| `/mods/part` |  | ○ |  |  |  |  |
| `/mods/part[@ID]` |  | ○ |  |  |  |  |
| `/mods/part[@order]` |  | ○ |  |  |  |  |
| `/mods/part[@type]` |  | ○ |  |  |  |  |
| `/mods/part/detail` |  | ○ |  |  |  |  |
| `/mods/part/detail[@type]` |  | ○ |  |  |  |  |
| `/mods/part/detail/number` |  | ○ |  |  |  |  |
| `/mods/part/detail/caption` |  | ○ |  |  |  |  |
| `/mods/part/detail/title` |  | ○ |  |  |  |  |
| `/mods/part/extent` |  | ○ |  |  |  |  |
| `/mods/part/extent/start` |  | ○ |  |  |  |  |
| `/mods/part/extent/end` |  | ○ |  |  |  |  |
| `/mods/part/extent/total` |  | ○ |  |  |  |  |
| `/mods/part/extent/list` |  | ○ |  |  |  |  |
| `/mods/part/date` |  | ○ |  |  |  |  |
| `/mods/part/date[@encoding]` |  | ○ |  |  |  |  |
| `/mods/part/date[@point]` |  | ○ |  |  |  |  |
| `/mods/part/date[@qualifier]` |  | ○ |  |  |  |  |
| `/mods/part/text` |  | ○ |  |  |  |  |
| `/mods/extension` | 로컬정보 ○/해당 시 필수 | ○ |  |  |  |  |
| `/mods/extension/regionOfPublishing` | 지역구분 -/해당 시 필수 | ○ | 지역구분 · 아래 텍스트 중 하나가 들어가야 합니다. / 동양 / 서양 / 일본 / 중국 / 한국 | 1 | 1 | ○ |
| `/mods/extension/note` |  | ○ |  |  |  |  |
| `/mods/extension/KoreaUniversity` | 한국대학부호 -/해당 시 필수 | ○ |  |  |  |  |
| `/mods/extension/KoreaUniversity[@type]` |  | ○ |  |  |  |  |
| `/mods/extension/KoreaGovernment` | 한국정부기관부호 -/해당 시 필수 | ○ |  |  |  |  |
| `/mods/extension/KoreaGovernment[@type]` |  | ○ |  |  |  |  |
| `/mods/extension/KoreaPublicInstitution` | 한국공공기관부호 -/해당 시 필수 | ○ |  |  |  |  |
| `/mods/extension/KoreaPublicInstitution[@type]` |  | ○ |  |  |  |  |
| `/mods/extension/keyword` |  | ○ |  |  |  |  |
| `/mods/recordInfo` |  | ○ |  |  |  |  |
| `/mods/recordInfo/recordContentSource` |  | ○ |  |  |  | ○ |
| `/mods/recordInfo/recordCreationDate` |  | ○ |  |  |  | ○ |
| `/mods/recordInfo/recordCreationDate[@encoding]` |  | ○ |  |  |  | ○ |
| `/mods/recordInfo/recordChangeDate` |  | ○ |  |  |  | ○ |
| `/mods/recordInfo/recordChangeDate[@encoding]` |  | ○ |  |  |  | ○ |
| `/mods/recordInfo/recordIdentifier` |  | ○ |  |  |  | ○ |
| `/mods/recordInfo/recordIdentifier[@source]` |  | ○ |  |  |  |  |
| `/mods/recordInfo/recordOrigin` |  | ○ |  |  |  |  |
| `/mods/subject/keyword` |  |  | 비통제주제명 |  |  |  |
| `/mods/name/alternativeName[@type]` |  |  | type · 아래 텍스트 중 하나가 들어가야 합니다. / no specific type / nickname / formal name / acronym | 1 | 1 |  |
| `/mods/originInfo[@type]` |  |  |  | 1 | 1 |  |

## 3. 값 규칙(Sample 필드설명에서)

- `/mods/titleInfo[@type]` (type): 아래 텍스트 중 하나가 들어가야 합니다. / uniform     : 통일표제 / title       : 본표제 / parallel    : 대등표제 / translated  : 번역표제 / original    
- `/mods/genre` (장르): 만화
- `/mods/originInfo/place/placeTerm[@authority]` (authority): 아래 텍스트 중 하나가 들어가야 합니다. / iso3166 / marccountry / marcgac
- `/mods/originInfo/place/placeTerm[@type]` (type): code
- `/mods/originInfo/issuance` (발행연속성): 단행자료
- `/mods/originInfo/frequency` (발행빈도): 아래 텍스트 중 하나가 들어가야 합니다. / 연속간행자료인 경우 / => 일간/주간/격주간/월간/격월간/계간/반년간/연간/계속갱신/부정기간 /간행빈도 불명/기타 로 변경되었습니다.
- `/mods/language/languageTerm` (본문언어): 아래 텍스트 중 하나가 들어가야 합니다. / kor  : 한국어 / eng : 영어 / chi  : 중국어 / jpn  : 일본어 — 기타 언어는 아래 언어값 참고
- `/mods/language/languageTerm[@type]` (type): code
- `/mods/physicalDescription/form` (자료형태): 아래 텍스트 중 하나가 들어가야 합니다. — 아래 자료형태별 디지털자료유형 변경(2012.03.08) 참고
- `/mods/physicalDescription/internetMediaType` (디지털자료유형): 아래 텍스트 중 하나가 들어가야 합니다. — 아래 자료형태별 디지털자료유형 변경(2012.03.08) 참고
- `/mods/physicalDescription/reformattingQuality` (매체제작목적): access       : 접근
- `/mods/physicalDescription/digitalOrigin` (디지털 자료형태): 아래 텍스트 중 하나가 들어가야 합니다. / born digital / digitized microfilm / digitized other analog / reformatted digital
- `/mods/abstract[@type]` (type): 아래 텍스트 중 하나가 들어가야 합니다. / 기타 / 서평 / 요약 / 초록 / 해제
- `/mods/tableOfContents[@type]` (type): 아래 텍스트 중 하나가 들어가야 합니다. / 기타목차 / 내용목차 / 부분목차 / 표목차
- `/mods/targetAudience` (이용대상자): 아래 텍스트 중 하나가 들어가야 합니다. / 고등학생 / 미상 / 성인용 / 아동용 / 일반이용자 / 중학생 / 초등학생 / 취학전아동 / 특수계층
- `/mods/classification[@authority]` (authority): 아래 텍스트 중 하나가 들어가야 합니다. / DDC / KDC / LCC / UDC
- `/mods/identifier[@type]` (type): 아래 텍스트 중 하나가 들어가야 합니다. / coi / doi / hdl / isbn / ismn / isrc / issn / issue number / istc / lccn / local / matrix numbe
- `/mods/accessCondition/licenseType` (저작권유무): 아래 텍스트 중 하나가 들어가야 합니다. / 0 : 외부 공개 / 1 : 비공개 / 2 : 국립중앙도서관 공개 / 3 : 국립중앙도서관, 국립어린이청소년도서관, 협력기관(공공.대학.전문/특수.해외.작은도서관) 공개 
- `/mods/extension/regionOfPublishing` (지역구분): 아래 텍스트 중 하나가 들어가야 합니다. / 동양 / 서양 / 일본 / 중국 / 한국
- `/mods/name[@type]` (type): 아래 텍스트 중 하나가 들어가야 합니다. / conference : 회의명 / corporate  : 단체명 / personal   : 개인명
- `/mods/name/alternativeName[@type]` (type): 아래 텍스트 중 하나가 들어가야 합니다. / no specific type / nickname / formal name / acronym

## 4. 웹툰 사업에서 쓰는 열(가이드 1~14절 요약 → 어디서 넣나)

| 항목 | 반입용 엑셀 | KOLIS 구축(3-2) |
|---|---|---|
| 표제·표제관련정보·권차·권차표제·대등표제(titleInfo[@type]=parallel) | ○ | 확인만 |
| 저자명(전거형)·유형·역할어 | ○ | 확인만 |
| 저자 전거 번호 @ID·@authority | × (미확인, 1절) | ○ 찾기 팝업/insertAcMat |
| 디스플레이형식 | × (Sample '사용안함') | ○ |
| 다른이름 + altType | 첫 저자 묶음만 열 있음(83열) | ○ |
| 발행지 글자+코드·발행처(n)·발행일·판사항·발행연속성·둘째 출처정보 | ○ | 확인만 |
| 언어·형태기술(자료형태·품질·미디어타입·수량·digitalOrigin) | ○(고정값·수량은 프로그램) | KOLIS 가 저장 때 표기 변경 |
| 이용대상자·주기 n쌍(유형) | ○ | 확인만 |
| 일반주제명 만화 | ○ (topic 글자만) | @ID·@authority 연결 |
| 장르주제명 웹툰[webtoon] | × (지침 10: 구축에서) | ○ |
| 분류 810 KDC 6 | ○ | 확인만 |
| ISBN | ○ | 확인만 |
| UCI | × (지침 13: 반입 오류) | ○ |
| 원문주소 2·소장위치·접근제한·지역구분·자료유형·장르 | ○ | 확인만 |
| 이용제한(성인) | × (종 화면) | ○ 자동 |
| 가격·보상·썸네일 | ○ (부록 A) | — |
