"""Mide en el celu conectado y en la compu: arranque y lector de QR. El envío real está en medir_envio.py.

Requiere el programa prendido y el celu desbloqueado."""
import os, shutil, subprocess, sys, tempfile, time
from pathlib import Path
import psutil

REPO = Path(__file__).resolve().parent.parent
ADB = r"D:\dev\android-sdk\platform-tools\adb.exe"
SDK = Path(r"D:\dev\android-sdk\build-tools\35.0.0")
JDK = Path(r"D:\dev\jdk17\bin")
ANDROID_JAR = r"D:\dev\android-sdk\platforms\android-35\android.jar"
PAQUETE = "com.kvothesson.tachan"
MB = int(sys.argv[1]) if len(sys.argv) > 1 else 300
NOMBRE = "tachan_prueba.mp4"
# Adentro de la carpeta de la app: es lo único que puede leer sin que otra app le dé permiso.
CELU = f"/sdcard/Android/data/{PAQUETE}/files/{NOMBRE}"
RECIBIDOS = Path.home() / "Downloads" / "Tachan"
CRUDOS = Path(tempfile.gettempdir()) / "tachan_pruebas" / "lector_crudos"


def adb(*a, tope=120):
    try:
        return subprocess.run([ADB, *a], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=tope).stdout.strip()
    except subprocess.TimeoutExpired:
        return ""


def memoria_celu():
    for l in adb("shell", "dumpsys", "meminfo", PAQUETE, tope=8).splitlines():
        if "TOTAL PSS" in l:
            return int(l.split()[2]) // 1024
    return 0


def cpu_celu():
    # Compartir puede arrancar otro proceso: el pid se busca cada vez.
    pid = adb("shell", "pidof", PAQUETE).split()
    if not pid:
        return 0.0
    for l in adb("shell", "top", "-b", "-n", "1", "-p", pid[0], tope=8).splitlines():
        partes = l.split()
        if partes and partes[0] == pid[0]:
            return float(partes[8])
    return 0.0


adb("shell", "input", "keyevent", "KEYCODE_WAKEUP"); adb("shell", "wm", "dismiss-keyguard"); time.sleep(1.5)
if "isKeyguardShowing=true" in adb("shell", "dumpsys", "window"): raise SystemExit("EL CELU ESTA BLOQUEADO: hay que desbloquearlo")
print("== Arranque")
compu = psutil.Process(next(p.pid for p in psutil.process_iter(["name"]) if p.info["name"] == "Tachan.exe"))
datos = Path(tempfile.gettempdir()) / "tachan_pruebas" / "arranque_datos"
tiempos = []
for _ in range(3):
    shutil.rmtree(datos, ignore_errors=True); datos.mkdir(parents=True)
    t0 = time.time()
    p = subprocess.Popen([REPO / "pc/compilado/Tachan.exe"], env=dict(os.environ, TACHAN_DATOS=str(datos), TACHAN_PUERTO="47970"))
    while not (datos / "enlace.txt").exists() and time.time() - t0 < 15: time.sleep(0.005)
    tiempos.append(int((time.time() - t0) * 1000))
    p.kill(); time.sleep(0.5)
print("compu, abrir hasta tener el QR (ms):", tiempos)
adb("shell", "input", "keyevent", "KEYCODE_WAKEUP")
frios = []
for _ in range(3):
    adb("shell", "am", "force-stop", PAQUETE); time.sleep(0.7)
    salida = adb("shell", "am", "start", "-W", "-n", f"{PAQUETE}/.Principal")
    for l in salida.splitlines():
        if l.strip().startswith("TotalTime"): frios.append(int(l.split(":")[1]))
    if not frios: print(salida[:300])
    time.sleep(1)
print("celu, abrir en frío (ms):", frios)
time.sleep(1.5)
print("celu, memoria abierta (MB):", memoria_celu())

print("== Lector de QR en el procesador del celu")
trabajo = Path(tempfile.mkdtemp())
subprocess.run([JDK / "javac.exe", "-encoding", "UTF-8", "-Xlint:-options", "-source", "8", "-target", "8", "-d", trabajo,
                REPO / "android/src/com/kvothesson/tachan/QrLector.java", REPO / "android/prueba/MedirLector.java"], check=True, capture_output=True)
subprocess.run([str(SDK / "d8.bat"), "--min-api", "26", "--lib", ANDROID_JAR, "--output", str(trabajo), *map(str, trabajo.rglob("*.class"))],
               check=True, capture_output=True, env=dict(os.environ, JAVA_HOME=str(JDK.parent)))
adb("push", str(trabajo / "classes.dex"), "/data/local/tmp/medir.dex")
adb("shell", "mkdir", "-p", "/data/local/tmp/cuadros")
for caso in ("limpio", "todo_junto", "sin_qr_ruido"):
    adb("push", str(CRUDOS / f"{caso}_1280x720.raw"), "/data/local/tmp/cuadros/")
print(adb("shell", "dalvikvm", "-cp", "/data/local/tmp/medir.dex", "com.kvothesson.tachan.MedirLector", "/data/local/tmp/cuadros", tope=300))
adb("shell", "rm", "-rf", "/data/local/tmp/cuadros", "/data/local/tmp/medir.dex")
shutil.rmtree(trabajo, ignore_errors=True)

# El envío real va por medir_envio.py, por el selector de fotos: desde la 1.3 Tachán rechaza file://, y desde adb
# no se le puede dar permiso para leer un content://, así que acá el envío nunca salía y la prueba esperaba 10 minutos.
print("== Envío real: correr pruebas/medir_envio.py")
