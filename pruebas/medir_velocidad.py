"""Mide la velocidad del protocolo real desde el celu contra un exe aislado, sin pantalla ni servicio de Android.

Usa el portapapeles de esta compu: guarda el texto que haya y lo restaura."""
import os, shutil, subprocess, sys, tempfile, time
from pathlib import Path
import win32clipboard, win32con

REPO = Path(__file__).resolve().parent.parent
ADB = r"D:\dev\android-sdk\platform-tools\adb.exe"
SDK = Path(r"D:\dev\android-sdk\build-tools\35.0.0")
JDK = Path(r"D:\dev\jdk17\bin")
ANDROID_JAR = r"D:\dev\android-sdk\platforms\android-35\android.jar"
DATOS = Path(tempfile.gettempdir()) / "tachan_pruebas" / "velocidad_datos"
PUERTO = "47810" if len(sys.argv) > 2 and sys.argv[2] == "real" else "47980"
MB = int(sys.argv[1]) if len(sys.argv) > 1 else 30


def adb(*a, tope=300):
    return subprocess.run([ADB, *a], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=tope)


win32clipboard.OpenClipboard()
guardado = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT) if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT) else None
win32clipboard.CloseClipboard()
trabajo = Path(tempfile.mkdtemp())
subprocess.run([JDK / "javac.exe", "-encoding", "UTF-8", "-Xlint:-options", "-source", "8", "-target", "8", "-d", trabajo,
                REPO / "android/src/com/kvothesson/tachan/Transporte.java", REPO / "android/prueba/MedirEnvio.java"], check=True, capture_output=True)
subprocess.run([str(SDK / "d8.bat"), "--min-api", "26", "--lib", ANDROID_JAR, "--output", str(trabajo), *map(str, trabajo.rglob("*.class"))],
               check=True, capture_output=True, env=dict(os.environ, JAVA_HOME=str(JDK.parent)))
adb("push", str(trabajo / "classes.dex"), "/data/local/tmp/velocidad.dex")
adb("shell", f"dd if=/dev/urandom of=/data/local/tmp/velocidad.bin bs=1048576 count={MB} 2>/dev/null")
shutil.rmtree(trabajo, ignore_errors=True)
shutil.rmtree(DATOS, ignore_errors=True); DATOS.mkdir(parents=True)
(DATOS / "ajustes.txt").write_text("sonido=0\n")
p = subprocess.Popen([REPO / "pc/compilado/Tachan.exe"], env=dict(os.environ, TACHAN_DATOS=str(DATOS), TACHAN_PUERTO="47980"))
try:
    for _ in range(60):
        if (DATOS / "enlace.txt").exists(): break
        time.sleep(0.25)
    time.sleep(1)
    enlace = (DATOS / "enlace.txt").read_text()
    r = adb("shell", f"dalvikvm -cp /data/local/tmp/velocidad.dex com.kvothesson.tachan.MedirEnvio '{enlace}' {MB} /data/local/tmp/velocidad.bin 2>&1")
    print(r.stdout[-1500:])
finally:
    p.kill(); time.sleep(0.3)
    adb("shell", "rm", "-f", "/data/local/tmp/velocidad.dex", "/data/local/tmp/velocidad.bin")
    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    if guardado is not None: win32clipboard.SetClipboardText(guardado, win32con.CF_UNICODETEXT)
    win32clipboard.CloseClipboard()
    print("portapapeles restaurado")
