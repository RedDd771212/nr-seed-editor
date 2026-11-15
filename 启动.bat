@echo off
chcp 65001 >nul
cd /d "%~dp0"

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
  echo 找不到 Python。请先安装 Python 3.10+ 并勾选 "Add to PATH"，
  echo 然后双击 检查环境.bat 看看还缺什么。
  echo.
  pause
  exit /b 1
)

echo 启动中……浏览器会自动打开 http://127.0.0.1:8779/
start "" /min %PY% app\server_v3.py 8779
ping -n 4 127.0.0.1 >nul
start "" http://127.0.0.1:8779/
exit
