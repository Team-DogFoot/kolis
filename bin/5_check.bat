@echo off
call "%~dp0_env.bat"
echo [5단계] MODS 점검. 먼저 KOLIS 디지털콘텐츠관리에서 전체출력한 파일이 필요합니다.
set /p EXP=전체출력 파일 경로(ExcelDown….xls): 
python -m kolis_tool ids "%EXP%" -o work\ids.txt
set /p WONBU=원부번호: 
echo --- 보낼 요청 미리보기(전송 안 함) ---
python -m kolis_tool mods-fetch work\ids.txt --preview --config kolis.json
echo.
echo KOLIS 로 실제 요청을 보내는 단계입니다. 직원 입회·동의 후에만 진행하세요.
python -m kolis_tool mods-fetch work\ids.txt -o work\xml --config kolis.json
python -m kolis_tool mods-check work\xml --wonbu %WONBU% --nth 1 -o out
echo 결과: out\2026-%WONBU% 1차점검(...).xlsx
pause
