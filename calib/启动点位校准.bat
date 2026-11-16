@echo off
chcp 65001 >nul
cd /d "%~dp0.."

rem 找一个可用的 Python
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)
if not defined PY (
  if exist "%USERPROFILE%\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe" (
    set "PY=%USERPROFILE%\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
  )
)
if not defined PY (
  echo.
  echo 找不到 Python。请先安装 Python 3.10+ 并勾选 "Add to PATH"。
  echo.
  pause
  exit /b 1
)

start "" /min %PY% calib\layer_server.py 8780
ping -n 3 127.0.0.1 >nul
start "" http://127.0.0.1:8780/
exit
