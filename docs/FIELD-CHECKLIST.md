# 현장 확인 목록 (도서관 PC, 2026-09-13)

체크하면서 결과를 이 파일에 바로 적는다. 비밀번호는 적지 않는다.

## A. 환경 (2026-09-18 확인, PC: DESKTOP-9F61RQO, 저장소 `C:\Users\User\dataclip\kolis`)
- [x] 윈도 11 Pro 10.0.26200. 파이썬 3.14.7 이미 설치됨(`C:\Python314`, py 런처 있음). 현재 계정은 관리자 아님. `.venv` 아직 없음 → `bin\setup.bat` 실행 필요
- [x] `pip install` 외부망 OK: pypi.org·files.pythonhosted.org·github.com HTTPS 응답 확인. 윈도 프록시 설정 없음
- [x] 보안 에이전트: **Somansa NDLP**(모든 HTTPS 를 자체 루트 CA 로 가로챔 → 클로드코드는 `NODE_EXTRA_CA_CERTS=C:\Users\User\.claude\somansa-root-ca.pem` 으로 해결됨, 09-09), **RSC Manager**(nTracksystem: rscmgr·rscdetect·rscPtCtrl·svcrsc), **Genian GPI**(PC 검사), **ESTsecurity ALYac**(백신). 설치 제한은 아직 부딪히지 않음(pip 는 됨). git 은 PATH 에 없음(클론은 다른 경로로 된 것) → 커밋·푸시 전 git 확보 필요
- [x] api.anthropic.com HTTPS 도달 OK(Somansa 인증서 경유). `claude` 실행 파일 있음(`C:\Users\User\.local\bin\claude.exe`) → `agent --runner claude` 가능. ANTHROPIC_API_KEY 미설정(`--runner api` 는 안 씀)
- [x] 엣지 153.0.4234.32. IE 모드 그룹정책(InternetExplorerIntegrationLevel) 없음 → 설정은 `edge://settings/defaultBrowser` › "Internet Explorer 모드에서 사이트 다시 로드 허용" + IE 모드 페이지 목록(사용자 설정). KOLIS 화면에서 실제로 IE 모드로 열리는지는 B 에서 확인
- [x] 클로드코드 원격 세션: 스케줄 작업 `ClaudeRemoteControl` Ready(09-09 설정, 자체 재시작 래퍼). 이 세션 자체가 정상 동작 중
- [x] `.env.example` 이 `.gitignore` 의 `.env.*` 규칙 때문에 커밋되지 않아 없었음 → 새로 만들고 `!.env.example` 예외 추가. `.env` 는 빈 값으로 복사해 둠(유저가 KOLIS_ID/KOLIS_PW 입력). `kolis.json` 은 예시를 복사해 둠(HAR 보고 필드명 수정)
- [x] 09-18 준비 완료: `.venv` 생성·requirements 설치(openpyxl 3.1.5, pillow 12.3, lxml 6.1, requests 2.34, python-docx 1.2), `work\xml`·`out` 폴더, `mods-check` 픽스처 실행 OK(오류 0), `mods-fetch --preview` 출력 OK, `claude -p` 헤드리스 OK
- [x] git 2.55 는 `C:\Program Files\Git\cmd` 에 설치돼 있고 시스템 PATH 에도 등록됨. 클로드코드 세션이 설치 전에 열려 이 세션에서만 안 보이는 것(다음 세션부터 정상). git user.name/email 미설정 → 첫 커밋 전 설정 필요

## B. KOLIS 화면별 확인 (IE 모드 필요 여부 / URL / 폼 항목)
**직원(또는 유저)이 평소 업무를 하는 동안** F12 → 네트워크 → 로그 보존 켜고 → HAR 내보내기. 기록만 하고 시험 요청은 보내지 않는다. HAR 은 PC 밖으로 옮기지 않는다.
- [ ] 로그인 `main/login.do` → `main/loginprocess.do` 폼 필드명(아이디·비밀번호 항목 이름)
- [ ] 통합검색(복본조사): 검색 요청 URL·파라미터, 결과에서 '온라인콘텐츠'·'수집상태' 위치
- [ ] 납본자료접수 › 일괄반입: 팝업 폼(수입년도·업무구분·첨부파일) 전송 방식, 반입 결과에서 CNTS 번호 받는 방법
- [ ] 납본자료접수 › 원문일괄등록(폴더): IE 모드 전용인지, ActiveX 이름, 폴더 드래그 외 방법 유무
- [ ] 썸네일 개별 등록(원문등록 → 파일추가 → 원문유형 썸네일): IE 모드 전용인지
- [ ] 전체출력(엑셀 다운로드) URL, 등록대상처리 요청
- [ ] 등록원부작성/등록원부관리: 원부작성 팝업 폼, 가원부번호 확인 위치
- [ ] 디지털콘텐츠관리: 원부번호 검색 요청, 콘텐츠목록보기, 전체출력
- [ ] 콘텐츠 XML 팝업 `ndl2011/contents/harcontents/popup/contentsXml.ndl?contentsBean.contentsId=CNTS-…&contentsBean.harTypeCd=62`
      → 응답 XML 1건을 `work/xml/` 에 저장(이걸로 `mods-check` 검증)
- [ ] 저자전거 "찾기" 팝업·주제명 "찾기" 팝업의 검색 요청과 선택 결과 반영 방식
- [ ] 일괄복본조사·일괄변경 화면 요청

## C. 데이터 규칙 확인 (2026-09-18 작업자 완료 사례 5-190/201/206/214 로 확인한 것은 [x])
- [x] 반입용 양식: 실제 승인된 파일은 **83열**(Sample 시트 + Contents, 2행부터 데이터, 한글 라벨 행 없음). 도구 템플릿 `kolis_tool/templates/import_template_83.xlsx`
- [ ] 반입용 엑셀의 `_source` 시트(도구가 추가)를 남겨도 되는지 → 안 되면 반입 직전 삭제 옵션 사용
- [x] 발행지: 케나즈 → `[서울]` + `ulk`(플랫폼 출처 각괄호). 스토리숲 → `[안양]` `ggk`. 나머지 REGION_CODE 는 미대조
- [x] 주기 "한국웹툰산업협회를 통해 수집한 자료임"(acquisition) — 5차 완료 사례 전부 동일. note 3쌍 중 **2번째=이용대상, 3번째=수집처, 1번째=기타(한자표제 등)**
- [x] 이용대상 주기: 전체 → '전체이용가', 15세 → '15세 이용가', 성인 → 이용대상자 '성인용' + '19세 미만 구독불가' + 공개여부 1
- [x] 정가: 무료 회차도 유료 회차 가격(케나즈 400~600). **보상여부는 출판사가 '보상안함'이어도 Y·보상금=정가로 반입됨** → 규칙인지 관행인지 직원 확인 필요
- [x] thum_files: 가이드 3.4-다 규정은 "엑셀 값 = 실제 파일명(확장자 포함), 정확히 일치"뿐(예시 `썸네일1.png`). 이름 형식 `<제목 공백제거><NN>.jpg` 는 작업자 관행(작품 간 충돌 방지) → 유지(유저 확정 09-18)
- [ ] 썸네일 건별 등록(그림 9) 때 엑셀 thum_files 로 생긴 '크기 0' 목록에 파일을 붙이는 방식인지 확인. 50화 건별이면 하이웨어 재검토
- [x] 권차: '1화'(5-201) 또는 '1'(5-190) — 원문 표기로 확정. 마지막 회차 '141 ([완결])' 식 표기도 있음
- [ ] **발행연월일**: 완료 사례는 전 회차를 첫 회차 날짜 하나로 통일. 유저 규칙(09-18)은 회차별 가장 이른 공개일. 어느 쪽이 도서관 요구인지 직원 확인
- [ ] 주제명: 완료 사례는 topic '만화'+'웹툰' 고정(BL 작품도). 출판사 '주제 구분'(BL·로맨스)은 구축 단계 참고

## D. 가져올 것
- [ ] 콘텐츠 XML 샘플 1건 이상(위 B)
- [ ] 반입 결과 화면 캡처(CNTS 번호 표시)
- [ ] 원문일괄등록 ActiveX 화면 캡처
- [ ] 저자전거 찾기 팝업 캡처
