@echo off
chcp 65001 >nul
cd /d "%~dp0\.."
if not exist .venv ( python -m venv .venv )
call .venv\Scripts\activate.bat
python -m pip install -q --upgrade pip
pip install -q -r requirements.txt
echo 설치 완료. 이제 bin\1_inspect.bat 부터 순서대로 실행하세요.
pause
