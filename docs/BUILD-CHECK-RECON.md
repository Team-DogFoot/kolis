# 구축·점검 화면 사전 수집 (2026-10-01 시작, 진행 중)

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

## 5. 다음 할 일 (순서대로)
1. `tools/recon.py` 에 부모 대역(`--opener`)을 넣어 MODS 수정 화면을 접수 985 의 콘텐츠(CNTS-00135578019 ~ 029)로 띄운다. 모을 것: 폼의 칸 전부(저자 반복, 전거 연결 칸, 다른이름, 주제명, 식별기호 UCI), 저장 버튼이 만드는 본문(누르지 않고 `tools/modify_truth.py` 처럼 본문을 만드는 함수만 불러 떠 둔다), 값 읽기 응답.
2. 저자전거 찾기(`ACControl.do`), 주제명 찾기(`subjNmPop.do`)를 띄워 조회 요청·응답을 기록한다(찾기는 조회다). 검색어: 큰조맨, 만화, 웹툰.
3. `popXmlView.do` 로 MODS XML 을 받는 요청을 확정한다(`mods_fetch.py` 는 옛 주소 `…/contentsXml.ndl` 을 쓰고 실행한 적이 없다). 접수 985 의 콘텐츠로 받아 `tests/fixtures/` 의 형식과 같은지 본다.
4. 일괄변경 팝업(`codeMngPop.do`), 콘텐츠목록보기(`showContentsList.do`), 엑셀 반출, 일괄복본조사의 실행·완료 함수의 본문을 소스에서 읽어 적는다.
5. 통합검색 조회(복본 판정)를 본표제로 한 번 보내 응답을 기록한다.
6. 원부번호가 필요한 조회(디지털콘텐츠관리 목록, 일괄복본조사 목록)는 직원에게 **정리 단계에 있는 원부번호 하나**를 받아 조회만 한다. 직원에게 물을 것: 가원부가 원부로 바뀌면 프로그램이 어떻게 아는가(주무관이 메일로 알려 주는가), 일괄복본조사의 '완료'는 무엇을 바꾸는가.
7. 그 뒤 PLAN 5-5 의 산출물(단계별 요청 초안·화면 방식 초안·1회 실행 순서표)을 이 문서에 채운다.
