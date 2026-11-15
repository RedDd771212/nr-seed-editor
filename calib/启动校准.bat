@echo off
chcp 65001 >nul
cd /d "%~dp0.."
set "PY=C:\Users\19803\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
start "" /min "%PY%" calib\server.py 8778
ping -n 4 127.0.0.1 >nul
start "" http://127.0.0.1:8778/
exit
