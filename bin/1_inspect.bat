@echo off
call "%~dp0_env.bat"
echo [1단계] 원문 폴더 검수 (깨짐·형식·중복·용량)
set /p ROOT=원문 상위 폴더 경로: 
python -m kolis_tool inspect "%ROOT%" -o out
echo 결과: out\inspect.xlsx 를 열어 노란 셀을 확인한 뒤 2단계로.
pause
