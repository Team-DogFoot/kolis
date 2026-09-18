@echo off
call "%~dp0_env.bat"
echo [0단계] 출판사 기초메타데이터 보완 (웹 리서치, claude -p 헤드리스). KOLIS 에 접근하지 않음.
set /p PUB=출판사용 기초메타데이터 엑셀 경로:
set /p OUT=보완본 출력 경로(예: work\작품명_기초메타데이터_보완.xlsx):
python -m kolis_tool enrich "%PUB%" -o "%OUT%"
echo 결과: 노란 셀(웹에서 채운 값)과 '근거' 시트를 확인한 뒤 1단계로. 작품 정보 JSON 은 같은 이름의 .work.json
pause
