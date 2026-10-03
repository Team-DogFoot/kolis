@echo off
rem ③구간(구축·점검) 반자동용 Edge: 제어 포트(9222)를 열고 별도 프로필로 KOLIS 를 띄운다. 로그인은 프로그램이 한다.
set "PROFILE=%LOCALAPPDATA%\kolis_tool\edge"
if not exist "%PROFILE%" mkdir "%PROFILE%"
start "" "msedge" --remote-debugging-port=9222 --user-data-dir="%PROFILE%" --no-first-run --no-default-browser-check --disable-features=AutomaticHttpsDefault,HttpsUpgrades,HttpsFirstBalancedMode,HttpsFirstModeV2 http://kolis.nl.go.kr/main/login.do
rem 창 위치(오른쪽 절반)는 프로그램이 붙을 때 맞춘다. 프로그램에서 띄우면(kolis_browser.launch_edge) 처음부터 오른쪽 절반이다.
