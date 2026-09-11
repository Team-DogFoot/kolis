@echo off
chcp 65001 >nul
cd /d "%~dp0\.."
call .venv\Scripts\activate.bat
if exist .env ( for /f "usebackq tokens=1,* delims==" %%a in (".env") do ( if not "%%a"=="" if not "%%a:~0,1%"=="#" set "%%a=%%b" ) )
set PYTHONIOENCODING=utf-8
