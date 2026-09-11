@echo off
call "%~dp0_env.bat"
echo [2단계] 파일명 8자리 일련번호 변경 (미리보기 → 확인 → 적용)
set /p ROOT=원문 상위 폴더 경로: 
python -m kolis_tool rename "%ROOT%" --dry-run
set /p OK=위 미리보기대로 바꾸려면 YES 입력: 
if /i "%OK%"=="YES" ( python -m kolis_tool rename "%ROOT%" ) else ( echo 취소 )
echo 되돌리기: python -m kolis_tool rename "%ROOT%" --undo
pause
