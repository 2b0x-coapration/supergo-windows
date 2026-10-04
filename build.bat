@echo off
rem Local build. Needs 64-bit Python 3.8 (last version that runs on Windows 7).
py -3.8 -m pip install -r requirements.txt || goto :err
py -3.8 -m PyInstaller --noconfirm --onefile --windowed --icon supergo.ico --add-data "supergo.png;." --name SUPERGO supergo.py || goto :err
echo.
echo Done: dist\SUPERGO.exe  (single file)
pause
exit /b 0
:err
echo Build failed.
pause
