@echo off
call "%~dp0_env.bat"
echo [3단계] 출판사용 엑셀 → 반입용 엑셀 (확인 필요 셀은 노란색)
set /p PUB=출판사용 엑셀 경로: 
set /p TPL=반입용 양식(템플릿) 엑셀 경로: 
set /p ROOT=원문 상위 폴더 경로: 
set /p OUT=출력 파일 경로(예: work\반입용_1차.xlsx): 
python -m kolis_tool convert "%PUB%" --template "%TPL%" --root "%ROOT%" -o "%OUT%"
echo 다음: 4단계(LLM 보완) 또는 노란 셀을 직접 채운 뒤 반입.
pause
