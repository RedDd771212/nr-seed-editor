@echo off
chcp 65001 >nul
cd /d "%~dp0.."

rem 找一个可用的 Python（优先 py -3 / python，最后退回 DSH 自带运行时）
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

start "" /min %PY% calib\server.py 8778
ping -n 4 127.0.0.1 >nul
start "" http://127.0.0.1:8778/
exit
