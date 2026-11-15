@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ===== 环境检查 =====
echo.

where py >nul 2>nul
if %errorlevel%==0 (echo [OK]  py  ^(py -3^)) else (
  where python >nul 2>nul
  if %errorlevel%==0 (echo [OK]  python) else (echo [缺]  Python 3.10+ —— 请安装并勾选 Add to PATH)
)
echo.

where dotnet >nul 2>nul
if %errorlevel%==0 (echo [OK]  dotnet  ^(regtool 解包/封包要用^)) else (
  echo [缺]  .NET 运行时 —— 请装 .NET 6/8 Desktop Runtime
)
echo.

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (where python >nul 2>nul && set "PY=python")
if not defined PY if exist "%USERPROFILE%\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe" set "PY=%USERPROFILE%\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"

if defined PY (
  %PY% -c "import PIL, sys; print('[OK]  Pillow', PIL.__version__, ' / Python', sys.version.split()[0])" 2>nul
  if errorlevel 1 echo [缺]  Pillow —— 请运行: %PY% -m pip install pillow
)

echo.
echo 检查随包依赖：
if exist "vendor\regtool\regtool.dll" (echo [OK]  vendor\regtool\regtool.dll) else (echo [缺]  vendor\regtool\regtool.dll)
if exist "vendor\NRDefs\MapPatternSet.xml" (echo [OK]  vendor\NRDefs\) else (echo [缺]  vendor\NRDefs\)
if exist "assets\map\limveld.png" (echo [OK]  assets\map\) else (echo [缺]  assets\map\)
if exist "assets\icon\pin\42009.png" (echo [OK]  assets\icon\pin\) else (echo [缺]  assets\icon\pin\)
echo.
echo 检查完按任意键关闭
pause >nul
