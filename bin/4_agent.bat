@echo off
call "%~dp0_env.bat"
echo [4단계] LLM 보완 (claude -p 헤드리스). KOLIS 에 접근하지 않음. 결과는 '제안' 시트.
set /p XLSX=반입용 엑셀 경로: 
set /p ROOT=원문 상위 폴더 경로: 
set /p LIM=처리할 질의 수 상한(전체면 그냥 Enter): 
if "%LIM%"=="" ( python -m kolis_tool agent "%XLSX%" --root "%ROOT%" --runner claude ) else ( python -m kolis_tool agent "%XLSX%" --root "%ROOT%" --runner claude --limit %LIM% )
echo '제안' 시트에서 승인(Y) 표시 후 아래를 실행하면 본문에 반영됩니다:
echo   python -m kolis_tool agent "%XLSX%" --apply
pause
