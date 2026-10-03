# 구축·점검 화면 사전 수집 (2026-10-01 시작, **대기 중**)

> **10-01 유저 지시: 원부번호를 기다리는 중이고, 원부번호 이후 단계는 테스트해도 되는지 아직 모른다. 지금까지의 지식만 정리해 두고 대기한다.** 유저가 말하기 전에는 이 문서의 화면에서 저장·변경을 보내지 않는다(접수 985·991 같은 우리 자료에도). 5절의 "다음 할 일"은 유저가 풀어 줄 때 이어서 한다. 접수 985 는 그 뒤 취소 요청 건이 됐고 지금 유지 건은 991(CNTS-00135578133~143, 종키는 접수 목록에서 다시 읽는다)이다.

목적: 원부번호가 나온 작품 1개로 **한 번에** 구축·점검을 끝내면서 요청 방식과 화면 방식을 둘 다 완성하기 위해, 지금 조회만으로 모을 수 있는 것을 모아 둔다(`docs/PLAN-2026-10-01.md` 5절).
수집한 원본(화면 소스, 화면 캡처, 요청·응답)은 `work/captures/pages/<번호_이름>/`(저장소에 없음). 이 문서는 그 요약이다.

## 0. 수집 방법 (다음 세션도 이대로)
- `tools/recon.py <이름> <주소> [--fill id=값] [--click 선택자] [--wait 초]`: 프로그램과 같은 방법으로 로그인한 뒤, **화면 없는 Edge**에 그 화면을 띄워 화면의 스크립트를 그대로 돌리고 소스·버튼·입력 칸·선택지·표 머리·주고받은 요청을 저장한다. 깃 배시에서는 `MSYS_NO_PATHCONV=1` 을 줘야 `/`로 시작하는 주소가 망가지지 않는다.
- 메뉴를 거치지 않고 주소를 바로 열어도 로그인은 풀리지 않았다(프로그램 접속 기준. 09-29 의 "주소 직접 입력 → 로그인 풀림"은 Edge 화면에서의 일).
- 팝업은 부모 창의 표(`opener.grid`)를 읽는다. 부모 대역을 만들어 띄워야 스크립트가 끝까지 돈다(방법은 `tools/modify_truth.py`: 빈 페이지에 `grid`, `$`, `bindDataToGrid` 를 만들고 `window.open`).
- **누르지 않는 것**: 저장, 완료, 복본조사 실행, 일괄변경 저장, 삭제, 분리·통합, 이관. 찾기·조회·팝업 열기만.
- **하지 말 것**: `POST /online/cmmn/listAccRec.do`(정리대상원부보기의 검색)를 작성년도만 넣고 보내면 KOLIS 가 4분 넘게 응답하지 않았다(2번 시도, 둘 다 시간 초과). 서버에 무거운 조회로 보인다. 다시 보내지 않는다. 필요하면 직원에게 화면에서 어떤 조건으로 쓰는지 묻는다.

## 1. 화면 주소 (메뉴: 정리 › 디지털콘텐츠 › 온라인 › 단행)
| 가이드 | 화면 | 주소 | 엔진 |
|---|---|---|---|
| 5.1 | 일괄복본조사 | `/online/cata/bocata/digitalcont/dupexmin/bundledupexmin/onlineBundleDupExmin.do` (메뉴 F1131110) | 크롬 엔진에서 열림 |
| 5.1 | 복본조사KEY설정(팝업) | `/cmmn/dupexminkeyset/main.do`, 저장 `/cmmn/dupexminkeyset/dupExminKeySet.do` | 〃 |
| 5.1 | 건별복본조사 | `/online/cata/bocata/digitalcont/dupexmin/casebydupexmin/onlineCaseByDupExmin.do` (F1131120) | 수집 안 함 |
| 5.2·5.5 | 디지털콘텐츠관리 | `/online/cata/bocata/digitalcont/digitalcontmng/onlineDigitalContMng.do?type=mo` (F1131200) | 〃 |
| — | 디지털콘텐츠수정 | `/online/cata/bocata/digitalcont/digitalcontmng/onlineDigitalContUpdate.do?type=mo` (F1131300) | 〃 |
| 5.3 | 종·콘텐츠 화면(MODS정리 버튼) | `/online/cmmn/onSpecViewPop.do?species_key=<종키>&har_stat_cd=30&menu_id=F1131200` | 〃 |
| 5.3 | MODS 수정 화면(MODS수정 버튼) | `/online/contents/onContentsDetailPop.do?contents_id=<콘텐츠ID>&view_type=&menu_id=F1131200` | 부모 대역 필요(아직 못 띄움) |
| 5.3 | 저자전거 찾기 | `/bocata/kormarcmatmng/kormarcmatmng/ACControl.do?flag=4&tagno=700&type=0,1,2` | 수집 전 |
| 5.3 | 주제명 찾기 | `/cmmn/subjnm/subjNmPop.do?flag_type=on` | 수집 전 |
| 5.4 | MODS 보기 | `/online/contents/popXmlView.do` (부모 화면의 값을 읽어 뜸) | 수집 전 |
| 검수 | 통합검색(복본 판정) | `/cmmn/unisearch/uniSearchMain.do`, 조회 `/cmmn/unisearch/listUniSearchMain.do`·`listUniSearchMainOnline.do`, 상세 `/cmmn/unisearch/popup/uniSearchDetail.do` | 열림, 조회는 수집 전 |

## 2. 디지털콘텐츠관리
- 조회 요청(찾기 버튼): `POST /online/cata/bocata/digitalcont/digitalcontmng/onlineDigitalContMngList.do`
  본문(실제 기록): `har_type_cd=&bus_id=&coll_id=&key_arr=&acc_rec_key=&type=mo&work_status_list_start=DS_3200&work_status_list_end=DS_3400&har_stat_cd=30&tran_stat_cd=40&list_menu_id=F1131200&init_dcms_yn=&use_limit_code=&reg_code=FTX&acquisit_yr=2026&accession_rec_no_start=<원부번호>&accession_rec_no_end=<원부번호>&accession_no_start=&accession_no_end=&searchSpecCnt=&searchContCnt=` → `{"cnt", "contentsCnt", "list": […], "sttus"}`
- **가원부번호로는 나오지 않는다.** 가원부 1598 과 가이드 예시 2026-379 로 조회 → 0건. 화면이 작업상태 `DS_3200~DS_3400`(정리 단계)만 조회한다. 주무관이 원부번호를 준 자료만 보인다. 목록 응답의 칸 이름은 아직 못 봤다(보이는 자료가 없음).
- 표 머리: No, SPECIES_KEY, SPE_SPECIES_KEY, HAR_TYPE_CD, APPLY_YN, ACC_KEY, 복본, 복본체크, 원부번호, 등록번호, 본표제, 편/권차, 편제, 저작자, 발행자, 발행년, 콘텐츠유형, 장르, 콘텐츠수, 분류기호, 정부기관부호, 공공기관부호, 발행자구분, 이용대상구분, 서비스범위, 원문서비스구분, MODS수정일
- 버튼이 여는 것(소스에서 읽음, 눌러 보지 않음): MODS정리 → 선택한 행의 SPECIES_KEY 로 종·콘텐츠 화면 / 일괄변경 `…/digitalcontmng/codeMngPop.do`(450×230) / 콘텐츠목록보기 `…/digitalcontmng/showContentsList.do?type=onlineDigitalContMngMo` / 서비스범위일괄수정 `…/popLicCd.do?har_stat_cd=30` / 정리대상원부보기 `/online/cmmn/accRecList.do?publish_form_code=MO&har_stat_cd=30&working_status=DS_3300`(조회 `/online/cmmn/listAccRec.do`, 위 "하지 말 것") / 엑셀 반출(`btnExp`, 소스 1513행 — 읽기 전).

## 3. 일괄복본조사
- 입력 칸: `acquisit_yr`(2026), `accession_rec_no_start`(원부번호), `accession_no_from`·`accession_no_to`, `reg_code`(FTX = (온)텍스트)
- 버튼: 복본조사 `btnDupExmin`, 상세보기 `btnDetail`, 완료 `btnComplete`, 복본조사KEY설정 `btnDupExminKeySet`, 정리대상원부보기
- 주소(소스): 목록 `…/bundledupexmin/getDupExminList.do`, 복본조사 실행 `…/bundledupexmin/dupExminProcBoCata.do`, 완료 `…/bundledupexmin/dupExminComplete.do`, `…/getDropAccNoCnt.do`, 상세 `/online/cmmn/dupexmin/detail.do`
- 표 머리: No, REC_KEY, ACC_REC_NO_LIST, ORIGIN_YN, ACC_REC_KEY, DUP_SPECIES_KEY, 복본확인, 복본, 복본체크, 식별기호, 본표제, 저작자, 콘텐츠유형, 장르, 발행자, 발행일, 콘텐츠수, 첫등록번호, 원부일련번호
- 요청 본문은 아직 모른다(원부번호가 있어야 조회가 된다). 소스의 `btnDupExmin`·`btnComplete` 함수를 읽어 본문을 적는 일이 남았다.

## 4. 종·콘텐츠 화면과 MODS 수정 화면
- 종·콘텐츠 화면은 **가원부 상태인 우리 자료로도 열린다**(접수 985 의 종키 89750759 로 확인: 본표제·저자·발행자·ISBN 이 채워져 열림). 구축 화면의 수집은 접수 985(유지) 자료로 할 수 있다.
- 종·콘텐츠 화면의 요청: 값 읽기 `/online/cmmn/getOnSpecView.do`, 권호 목록 `/online/cmmn/listVolumn.do`, 콘텐츠 목록 `/online/contents/listVolContentsForOne.do`, 종 저장 `/online/cmmn/onSpecSave.do`, 코드 `/online/common/code/retrieveOfferdbCode1List.do`(CH1 e-콘텐츠 …)·`retrieveOfferdbCode2List.do`
- 버튼: 종MODS수정, MODS수정(`btnModCnts`) → MODS 수정 화면, MODS보기(`btnViewMods`) → `popXmlView.do`, 원문목록(`btnFile`) → `/online/contents/wFilePop.do?contents_id=…`, 저장, 이전·다음
- MODS 수정 화면의 주소(소스): 값 읽기 `/online/contents/onContentsDetail.do`, 이전·다음 `/online/contents/onContentsDetailPreNext.do`, **저장 `/online/contents/updateHarContents.do`**, 전거 정보 `/online/contents/acInfoPop.do`, 로마자 `/online/contents/genRomaja.do`, 이용제한 `/online/contents/useLimitPop.do`, MODS 보기 `/online/contents/popXmlView.do`
- 부모 대역 없이 띄우면 `parentGrid is not defined` 로 폼이 그려지지 않는다 → **다음 할 일 1번**.

## 4-1. MODS 수정 화면 — 접수 985 자료로 띄워 확인한 것 (10-01 저녁)
- 띄우는 법: `tools/recon.py 5-3_MODS수정화면 "/online/contents/onContentsDetailPop.do?contents_id=<콘텐츠ID>&view_type=&menu_id=F1131200" --opener work/captures/pages/opener_985.json`. 부모 대역 파일은 `{"rows": [{"CONTENTS_ID", "SPECIES_KEY"}], "vals": {"#species_key": "…", "#issuance": "MO"}}`.
- 화면이 값을 읽는 요청: `POST /online/contents/onContentsDetail.do`(본문은 `harContentsUpdateForm` 폼 전체: `contentsId=<콘텐츠ID>&xmlType=2&…`). 응답은 **MODS 입력 폼의 HTML**이다(칸 이름이 `_titleInfo_title10`, `_name_namePart54` 처럼 요소 경로 + 번호).
- **저장 = 그 폼을 그대로 직렬화해 `POST /online/contents/updateHarContents.do`**(화면의 `serializeObject('harContentsUpdateForm')`). 접수 985 첫 건에서 저장 본문을 **보내지 않고** 떠 두었다: `work/captures/pages/5-3_MODS수정화면/eval1.json`(273항목, 값 있는 것 81개). 수정 팝업(썸네일)과 달리 폼이 서버가 그려 준 것이라, 요청 방식은 "폼 HTML 을 받아 칸을 읽고, 바꿀 칸만 바꿔 그대로 돌려보내기"로 만들 수 있다. 폼에 `contentsWofElemListSerialized`(서버가 준 긴 값)가 들어 있으므로 반드시 받은 값을 그대로 돌려보낸다.
- 구축에서 채울 칸(저장 본문의 이름): 저자전거 연결 `_name@ID`, `_name@authority`(찾기 버튼 `popSearchNameKolis('_name_namePartN', N, '_name_IDN', '_name_authorityN', '_name_typeN')`) / 주제명 연결 `_subject@ID`, `_subject@authority`, `_subject@authorityURI`(찾기 `subjectSearchPop(...)`) / 식별기호 `_identifier`, `_identifier@type`(UCI) / 저자 다른이름은 `_name` 묶음의 반복 칸(＋ 버튼 21개, － 버튼 20개 — 반복 칸을 늘리는 스크립트는 아직 읽지 않음).
- 지금 값(반입 직후): `_name@type` personal, `_name_role_roleTerm` 글·그림, `_subject_topic` [만화, 웹툰], `_classification` 810(KDC 6), `_note` 2개(target audience, acquisition), `_originInfo_place_placeTerm` [[서울], ulk], `_accessCondition_licenseType` 1.
- 찾기 함수(`popSearchNameKolis`, `subjectSearchPop`, `popSearchKInqcode`, `kdcSearchPop`)의 본문은 `onContentsDetail.do` 가 돌려주는 HTML 안에 있다(수집본은 20만 자에서 잘렸다 → `tools/recon.py` 의 응답 저장 한도를 늘려 다시 받아 읽는다). 전거 찾기 팝업 주소 후보는 종·콘텐츠 화면에 있던 `/bocata/kormarcmatmng/kormarcmatmng/ACControl.do?flag=4&tagno=700&type=0,1,2`, 주제명은 `/cmmn/subjnm/subjNmPop.do?flag_type=on`.
- 그 밖의 버튼: 전거추출목록 `/online/contents/acInfoPop.do?contents_id=…`, 이용제한 `/online/contents/useLimitPop.do?contents_id=…`, 원문목록 `/online/contents/wFilePop.do`, 변경이력 `/online/contents/cntsHistPop.do`.

## 4-2. MODS XML 받기 (점검의 입력) — 확인됨
- `POST /online/contents/popup/getHarContentsXml.do` 본문 `contentsId=<콘텐츠ID>` → `{"sttus": "success", "mods_xml": "<?xml …"}`. 접수 985 첫 건으로 받음(2,988자, `mods:` 접두사, MODS 3.7). MODS보기 버튼의 화면은 `/online/contents/popXmlView.do?contentsId=…` 이고 그 화면이 위 요청을 보낸다.
- **`kolis_tool/mods_fetch.py` 는 옛 주소(`/ndl2011/…/contentsXml.ndl`)를 쓰고 있어 고쳐야 한다**: 로그인은 `kolis_http.Client`, 받기는 위 요청으로. MODStoXL 을 대신하는 부분이 이것으로 확정된다.
- `tests/fixtures/CNTS-00134746760.xml` 은 가이드 그림을 옮겨 적은 것이다. 실제 응답 한 건을 기준 자료로 바꾼다(작품 내용이 들어가므로 저장소에 넣어도 되는지 유저에게 확인).

## 5. 다음 할 일 (순서대로)
1. (끝냄, 4-1절) MODS 수정 화면을 띄워 폼과 저장 본문을 떠 둠. 남은 것: 찾기 함수 본문 읽기, 반복 칸(＋)을 늘리는 방법, **접수 985 의 한 건에 실제로 전거·주제명을 연결해 저장해 보기**(985 는 유지 건이므로 유저·직원에게 먼저 묻는다. 취소 요청 건 984 로 해도 되는지도 묻는다).
2. 저자전거 찾기(`ACControl.do`), 주제명 찾기(`subjNmPop.do`)를 띄워 조회 요청·응답을 기록한다(찾기는 조회다). 검색어: 큰조맨, 만화, 웹툰.
3. (요청 확정, 4-2절) `mods_fetch.py` 를 새 요청으로 고치고, 접수 985 의 11건을 받아 `mods-check` 로 점검 시트까지 만들어 본다(프로그램 창에 붙이는 것은 그 뒤).
4. 일괄변경 팝업(`codeMngPop.do`), 콘텐츠목록보기(`showContentsList.do`), 엑셀 반출, 일괄복본조사의 실행·완료 함수의 본문을 소스에서 읽어 적는다.
5. 통합검색 조회(복본 판정)를 본표제로 한 번 보내 응답을 기록한다.
6. 원부번호가 필요한 조회(디지털콘텐츠관리 목록, 일괄복본조사 목록)는 직원에게 **정리 단계에 있는 원부번호 하나**를 받아 조회만 한다. 직원에게 물을 것: 가원부가 원부로 바뀌면 프로그램이 어떻게 아는가(주무관이 메일로 알려 주는가), 일괄복본조사의 '완료'는 무엇을 바꾸는가.
7. 그 뒤 PLAN 5-5 의 산출물(단계별 요청 초안·화면 방식 초안·1회 실행 순서표)을 이 문서에 채운다.

## 6. 2026-10-03 확정된 것 (③구간 반자동으로 실제 수행)
- **5.1 복본조사**: `dupExminKeySet.do`(KEY, 그림 21) → `getDupExminList.do` → `dupExminProcBoCata.do` 건마다 → 결과 표: 우리 자료 행(ORIGIN_YN=V, IDENT_MARK=순번, ACCESSION_NO 있음) 아래에 후보 행들(ORIGIN_YN=N) — 칸 REC_KEY, TITLE, AUTHOR, PUBLISHER, PUBLISH_YEAR, TYPEOFRESOURCE, CNTS_COUNT, DUP_CONF(V=우리 행), DUP, DUP_CHECK, `_chk`(복본 체크). 복본으로 판정한 후보에 `_chk` 를 켜고 `getDropAccNoCnt.do` → 확인창 "복본조사완료 하시겠습니까?" → `dupExminComplete.do?type=A`. 판정 규칙(유저 위임): 표제·저작자·발행처·발행년 모두 같으면 복본, 하나라도 다르면 아님(발행처만 다르면 직원 확인 권고). 1610 등짝: 후보 64건 전부 발행처(KOCN↔저스툰)만 달라 복본 아님으로 완료.
- **5.2 일괄변경**: `codeMngPop.do` → `updateCode.do` 본문 `publisher_code=PE&kogl_code=&offerDbcode1s=CH1&offerDbcode2s=CH11&speciesKey_list=…`(종키 반복). 확인은 `getOnSpecView.do` 본문 `species_key=&har_stat_cd=30` → 응답 `{"sttus","data":{OFFER_DBCODE_1S, OFFER_DBCODE_2S, PUBLISHER_CODE, KOGL_CODE, USE_LIMIT_CODE, USE_LIMIT_CHANGE_CODE, USE_OBJ_CODE, …}}`.
- **성인물 이용제한(가이드에 없음, 유저가 알려 준 절차)**: 종·콘텐츠 화면(`onSpecViewPop.do?species_key=…&har_stat_cd=30&menu_id=F1131200`)의 "이용제한구분 [변경]"(`#btn_use_limit_code`, `UseLimitCode.openUseLimitCodePop`) → 팝업 `/cmmn/uselimitcode/useLimitCodeChangePop.do?ulc=--&ulcc=&uld=&ulr=&uled=&uoc=<이용대상>&type=1`(목록 `POST /cmmn/uselimitcode/listUseLimitCode.do`) → 표 첫 행 **"1. 청소년 유해매체물"(USE_LIMIT_CODE GM 일반, USE_LIMIT_CHANGE_CODE CD1)** 체크 → 확인창 "…변경사유가 청소년 유해매체물로 변경되었습니다. 현재 선택된 이용대상구분 [AD | 성인] 이 맞습니까?" 예 → `#btnConfirm` → 종 화면 `#btnSave`(알림 "수정이 완료 되었습니다") → 재조회 USE_LIMIT_CODE=GM, USE_LIMIT_CHANGE_CODE=CD1, USE_OBJ_CODE=AD. 종(회차)마다 반복. 코드 `kolis_tool/build_prep.use_limit_adult`. 지침(MODS 입력가이드 8): 성인물은 MODS 이용대상자 '성인용'·주기 "19세 미만 구독불가"도 함께(3-2 판단에 `adult` 입력).
- **5.3 MODS 수정**: 저자 전거 삽입은 `popSearchNameKolis2` 가 `kolisBean.classCode/dataCode/dataCodeName/type` 숨은 칸에 대상 id 를 적고 팝업의 `insertAcMat(acControlNo, signpost, chi, birth, type, targetId)` 가 `@ID`·`@authority("국립중앙도서관전거데이터")`·`@type` 을 넣는다. 주제명은 `gf_insertSubjNm`. 묶음 추가 `repeat(...)` 는 요소 id 를 다시 매긴다(name 으로 찾을 것). 저장 `lf_update()` → `updateHarContents.do`(아직 보내지 않음).

## 7. MODS 저장 요청 형식(2026-10-03 19:10, 첫 실제 저장 — 1614 접시꽃 도박사 1, CNTS-00135497353)
`POST /online/contents/updateHarContents.do` 본문 13칸: contentsId, xmlType=2, speciesKey·viewType·collId·wofId·collNm·prevNextHarTypeCd(빈 값), 그리고 **다섯 개의 평행 배열**(쉼표로 이은 문자열) — `inputedXpath`(요소 경로, 224개), `inputedElem`(요소/속성 이름), `inputedElemTypeCd`(01 요소 / 02 속성), `inputedElemValue`(값), `inputedTableId`(화면 칸 id, `tag_…` 가 섞여 290개). 같은 경로가 **반복되면 반복 요소**다(예: `/mods/name` 두 묶음, `/mods/originInfo/place/placeTerm` 두 번 = 글자 "[서울]" + 코드 "ulk"). 따라서 **출처정보(originInfo) 두 개, 각각 발행지 두 개**는 `/mods/originInfo` 블록(경로 44~63 꼴)을 그대로 한 번 더 잇고 그 안에 `place/placeTerm` 쌍을 두 번 넣으면 된다. 값에 쉼표가 들어가면 어떻게 이스케이프하는지는 아직 안 봤다(이번 값에는 쉼표 없음).
응답 `{"sttus":"success","harContentsBean":{…}}`(157,557자). 저장 전·후 XML: `work/build/CNTS-00135497353/mods_before.xml`·`mods_after.xml`. 저장이 스스로 바꾼 것: internetMediaType `JPG`→`image/jpg`, digitalOrigin `BornDigital`→`born digital`, `useObjCode` 요소 사라짐, `accessCondition 비공개` 생김, recordChangeDate 갱신 — 10-01 관찰과 같다. 요청 칸 전체 사본 `work/captures/wonbu/updateHarContents_post_fields.json`(git 밖).

## 8. 공용사항관리 팝업(2026-10-03 21:50 조사, 열기만)
디지털콘텐츠관리 `#btnCommonMods` → `openModal('/online/cata/bocata/digitalcont/digitalcontmng/popCommonMods.do?har_stat_cd=30&publish_form_code=MO')`. 칸: 공용사항제목, 장르(콘텐츠유형·장르), 출처정보(발행연속성·간행빈도), 언어, 형태기술정보(자료형태·디지털품질·디지털자료유형·수량·형태주기), 이용대상자, 주기사항 1~3(유형+글), 분류기호(@authority·@edition·@generator), 소장정보(소장위치·@authority), 로컬정보(지역구분·NOTE·한국대학/정부기관/공공기관부호). 단추: 입력·수정·삭제(공용사항 저장본 관리: `insertCommonMods/updateCommonMods/deleteCommonMods/getCommonMods(List).do`), **MODS적용**(`updateContentsXml.do` — 체크한 콘텐츠들에 공용사항을 덮어씀).
**저자(전거)·주제명·식별기호(UCI)·표제·출처정보 발행처 칸이 없다.** → 5.3 의 추가 작업(전거 연결·다른이름·주제명 연결·UCI)에는 쓸 수 없다. 쓸 수 있는 곳: 주기사항·이용대상자·분류·언어처럼 원부 전체가 같은 값(이미 반입에서 들어감). 기록: `work/captures/pages/5-3_공용사항관리/`(popup.html, fields.json, inline_scripts.js, urls.txt, popup.png). 저장은 누르지 않음.

## 9. 반입 헤더 시험(2026-10-03 23:30, 원시인 삼촌 2행, 접수 2건 → 취소 요청 목록)
`tools/import_probe.py`. 일괄반입(요청)에 시험 열을 끼워 넣고 접수 목록이 돌려주는 MODS(CONTENTS_XML)로 확인. **전부 들어갔다.**
- 저자 전거: `/mods/name[@ID]`, `/mods/name[@authority]` → `<name ID="KAC…" authority="국립중앙도서관전거데이터" type="개인명">`.
- 다른이름: 템플릿 열 `/mods/name/alternativeName`, `/mods/name/alternativeName[@type]`(값 nickname), `/mods/name/alternativeName/namePart` → `<alternativeName altType="nickname">`(열 이름은 [@type] 로 써도 altType 으로 들어감).
- 주제명 연결: `/mods/subject/` | `/mods/subject/topic` | `/mods/subject[@ID]` | `/mods/subject[@authority]` | `/mods/subject/` | `/mods/subject/genre` | `[@ID]` | `[@authority]` → 주제명 2묶음(만화[漫畵] KSH1998022212 topic, 웹툰[webtoon] KSH2016000049 genre) 전거 포함.
- 식별기호 UCI: 둘째 `/mods/identifier` + `/mods/identifier[@type]`=uci → `<identifier type="uci">` 들어감(지침 13 의 "반입 오류"는 지금 KOLIS 에서는 재현되지 않음).
- 출처정보 2묶음: 둘째 `/mods/originInfo` 부모 열 뒤에 `[@type]`·발행지·발행처·발행일·발행연속성 → 두 `<originInfo>` 로 나뉨. **발행지 구조는 부모 열 `/mods/originInfo/place` 로 정해진다**: 부모 열을 placeTerm 쌍 앞에 **한 번** 두면 `<place>` 하나에 placeTerm(text, code) 둘(지침 예시 꼴, 2차 시험 접수), placeTerm 마다 두면 `<place>` 둘(1차 시험), 부모 열이 없으면 앞 묶음에 붙는다(유저가 본 "출처정보 하나에 발행지 4개"의 원인 — 둘째 `/mods/originInfo` 부모 열 없이 placeTerm 만 반복하면 그렇게 된다). 규칙(Sample 시트): "반복에 따른 부모정의 항목으로 데이터는 없음".
- 접수번호 1027(1차)·둘째 접수(2차)는 `work/취소요청_목록.csv` 에 "취소 요청"으로 적음. 원문 등록·가원부번호는 하지 않음.
