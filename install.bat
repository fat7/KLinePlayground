@echo off

REM ==================================================================
REM 步骤 1: 构建主应用程序
REM ==================================================================
echo Building main program (KLineTrainer.exe)...
.venv\Scripts\pyinstaller.exe .\KLineTrainerOneFile.spec
if errorlevel 1 (
    echo.
    echo Error: Build KLineTrainer.exe failed!
    pause
    exit /b 1
)
ren ".\dist\KlineTrainerApp.exe" "KLineTrainer.exe"
echo Build succeed.
echo.

REM ==================================================================
REM 步骤 2: 构建 AI 策略测试器 (KLineTrainer_AI_Assistant.exe)
REM ==================================================================
echo building KLineTrainer_AI_Assistant.exe...
call .\build_ai_tester.bat
if errorlevel 1 (
    echo.
    echo Error: Build AI Tester Failed!
    pause
    exit /b 1
)
echo Build AI Tester succeed.
echo.

REM ==================================================================
REM 步骤 3: 将程序复制到安装程序源目录
REM ==================================================================
echo Coping files...
copy "dist\KLineTrainer.exe" ".\installer_source\app_files\"
copy "dist\AI_Tester_Release\KLineTrainer_AI_Assistant.exe" ".\installer_source\app_files\"
del ".\dist\KLineTrainer.exe"
mkdir ".\installer_source\data" 2>nul
copy "data\stock_list.csv" ".\installer_source\data\"
copy "data\stock_names.json" ".\installer_source\data\"
echo Done. Copy done.
echo.

REM ==================================================================
REM 步骤 4: 构建最终的安装程序 (这部分在 setlocal 内部)
REM ==================================================================
echo Final target building...
cd ".\installer_source\"
..\.venv\Scripts\pyinstaller.exe Installer.spec
if errorlevel 1 (
    echo.
    echo Error: Build final Installer.exe failed!
    pause
    exit /b 1
)
echo.
echo All done!
pause
