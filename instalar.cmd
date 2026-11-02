@echo off
rem Deja entrar al celu por la red de casa y prende el receptor con Windows.
net session >nul 2>&1
if errorlevel 1 (
  powershell -NoProfile -Command "Start-Process -Verb RunAs -FilePath '%~f0'"
  exit /b
)
netsh advfirewall firewall delete rule name="Mandar a la compu" >nul 2>&1
netsh advfirewall firewall add rule name="Mandar a la compu" dir=in action=allow protocol=TCP localport=7780 profile=private
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Startup')+'\Mandar a la compu.lnk'); $s.TargetPath='D:\dev\python\3.13.1\pythonw.exe'; $s.Arguments='\"%~dp0receptor.py\" --oculto'; $s.WorkingDirectory='%~dp0'; $s.Save()"
echo.
echo Listo. Ya podes cerrar esta ventana.
pause
