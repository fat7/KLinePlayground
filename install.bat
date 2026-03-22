@echo off

REM ==================================================================
REM 步骤 1: 构建主应用程序
REM ==================================================================
echo 正在构建主应用程序 (KLineTrainer.exe)...
.venv\Scripts\pyinstaller.exe .\KLineTrainerOneFile.spec
if errorlevel 1 (
    echo.
    echo 错误：构建 KLineTrainer.exe 失败！
    pause
    exit /b 1
)
ren ".\dist\KlineTrainerApp.exe" "KLineTrainer.exe"
echo 构建完成。
echo.

REM ==================================================================
REM 步骤 2: 构建 AI 策略测试器 (KLineTrainer_AI策略测试器.exe)
REM ==================================================================
echo 正在构建 AI 策略测试器...
call .\build_ai_tester.bat
if errorlevel 1 (
    echo.
    echo 错误：构建 AI 策略测试器失败！
    pause
    exit /b 1
)
echo AI 策略测试器构建完成。
echo.

REM ==================================================================
REM 步骤 3: 将程序复制到安装程序源目录
REM ==================================================================
echo 正在复制文件到安装目录...
copy "dist\KLineTrainer.exe" ".\installer_source\app_files\"
copy "dist\AI_Tester_Release\KLineTrainer_AI策略测试器.exe" ".\installer_source\app_files\"
del ".\dist\KLineTrainer.exe"
echo 复制完成。
echo.

REM ==================================================================
REM 步骤 4: 构建最终的安装程序 (这部分在 setlocal 内部)
REM ==================================================================
echo 正在切换目录并构建最终的安装程序...
cd ".\installer_source\"
..\.venv\Scripts\pyinstaller.exe Installer.spec
if errorlevel 1 (
    echo.
    echo 错误：构建最终的 Installer.exe 失败！
    pause
    exit /b 1
)
echo.
echo 所有操作已成功完成！
pause
