@echo off

REM ==================================================================
REM ���� 1: ������Ӧ�ó���
REM ==================================================================
echo ���ڹ�����Ӧ�ó��� (KLineTrainer.exe)...
.venv\Scripts\pyinstaller.exe .\KLineTrainerOneFile.spec --distpath .\
if errorlevel 1 (
    echo.
    echo ���󣺹��� KLineTrainer.exe ʧ�ܣ�
    pause
    exit /b 1
)
ren "KlineTrainerApp.exe" "KLineTrainer.exe"
echo ������ɡ�
echo.

REM ==================================================================
REM ���� 2: ���������Ƶ���װ����ԴĿ¼
REM ==================================================================
echo ���ڸ��� KLineTrainer.exe ����װĿ¼...
copy "KLineTrainer.exe" ".\installer_source\app_files\"
echo ������ɡ�
echo.

REM ==================================================================
REM ���� 3: �������յİ�װ���� (�ⲿ���� setlocal �ڲ�)
REM ==================================================================
echo �����л�Ŀ¼���������յİ�װ����...
cd ".\installer_source\"
..\.venv\Scripts\pyinstaller.exe Installer.spec
if errorlevel 1 (
    echo.
    echo ���󣺹������յ� Installer.exe ʧ�ܣ�
    pause
    exit /b 1
)
echo.
echo ���в����ѳɹ���ɣ�
pause
