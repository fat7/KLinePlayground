@echo off

echo [1/3] 清理旧的构建目录...
if exist build rmdir /s /q build
if exist "dist\KLineTrainer_AI_Assistant.exe" del /q "dist\KLineTrainer_AI_Assistant.exe"
if exist "dist\AI_Tester_Release" rmdir /s /q "dist\AI_Tester_Release"

echo [2/3] 开始打包单文件可执行程序...
.venv\Scripts\pyinstaller.exe --noconfirm --onefile --windowed --icon="ai_assistant.ico" --add-data="ai_assistant.ico;." --name "KLineTrainer_AI_Assistant" ai_assistant_tester.py

echo [3/3] 正在整理发布文件夹...
mkdir "dist\AI_Tester_Release"
mkdir "dist\AI_Tester_Release\data"
move "dist\KLineTrainer_AI_Assistant.exe" "dist\AI_Tester_Release\" >nul

echo.
echo ==========================================================
echo 打包完成！
echo 程序及其数据文件夹位于: dist\AI_Tester_Release\
echo 说明：
echo - KLineTrainer_AI_Assistant.exe 是单文件主程序
echo - data 文件夹用于独立存放配置或数据文件，方便随程序一同拷贝
echo ==========================================================
pause
