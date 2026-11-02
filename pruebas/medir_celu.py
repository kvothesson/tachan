"""Mide en el celu conectado y en la compu: arranque, lector de QR y un envío grande real.

Requiere el programa prendido y el celu vinculado. Crea un video de prueba, lo manda y lo borra de los dos lados.
Guarda el texto del portapapeles y lo restaura."""
import os, shutil, subprocess, sys, tempfile, threading, time
from pathlib import Path
import psutil
import win32clipboard, win32con

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

print(f"== Envío real de {MB} MB")
win32clipboard.OpenClipboard()
guardado = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT) if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT) else None
win32clipboard.CloseClipboard()
destino = RECIBIDOS / NOMBRE
try:
    assert not destino.exists(), "ya hay un archivo de prueba en la compu"
    adb("shell", "mkdir", "-p", f"/sdcard/Android/data/{PAQUETE}/files")
    adb("shell", "dd", "if=/dev/urandom", f"of={CELU}", "bs=1048576", f"count={MB}", tope=300)
    uri = f"file://{CELU}"
    print("celu, reposo: cpu", cpu_celu(), "% memoria", memoria_celu(), "MB")
    compu_antes = compu.memory_info().private // 2**20
    t0 = time.time()
    print(adb("shell", "am", "start", "-n", f"{PAQUETE}/.Compartir", "-a", "android.intent.action.SEND", "-t", "video/mp4", "--eu", "android.intent.extra.STREAM", uri).splitlines()[-1][:90])
    # Android no abre la pantalla de compartir con el celu bloqueado: primero se comparte y después se bloquea, como haría una persona.
    time.sleep(4)
    avance = adb("shell", "dumpsys", "notification", "--noredact", tope=8)
    for l in avance.splitlines():
        if PAQUETE in l and "pkg=" in l: pass
        if "android.text=" in l and " MB" in l: print("notificación:", l.strip()[:90]); break
    captura = Path(tempfile.gettempdir()) / "tachan_pruebas" / "notificacion.png"
    adb("shell", "cmd", "statusbar", "expand-notifications")
    time.sleep(1)
    with open(captura, "wb") as f:
        subprocess.run([ADB, "exec-out", "screencap", "-p"], stdout=f, timeout=20)
    adb("shell", "cmd", "statusbar", "collapse")
    adb("shell", "input", "keyevent", "KEYCODE_SLEEP")
    time.sleep(2)
    cpus, memorias, picos_compu = [], [], []
    compu.cpu_percent(None)
    cpu_pc = []
    empezo = None
    while not destino.exists() and time.time() - t0 < 600:
        if empezo is None and any(RECIBIDOS.glob(".recibiendo_*")): empezo = time.time()
        cpus.append(cpu_celu()); memorias.append(memoria_celu())
        picos_compu.append(compu.memory_info().private // 2**20); cpu_pc.append(compu.cpu_percent(None))
        time.sleep(2)
    t = time.time() - t0
    assert destino.exists(), "no llegó"
    tamano = destino.stat().st_size // 2**20
    red = time.time() - empezo if empezo else t
    print(f"llegó: {tamano} MB en {t:.1f} s en total; por wifi {red:.1f} s = {tamano / red:.1f} MB/s")
    if cpus:
        print(f"celu durante el envío: cpu media {sum(cpus) / len(cpus):.0f}% (100% = un núcleo), memoria máxima {max(memorias)} MB")
        print(f"compu durante el envío: cpu media {sum(cpu_pc) / len(cpu_pc):.0f}% de un núcleo, memoria {compu_antes} -> {max(picos_compu)} MB")
    print("celu, servicio de envío:", adb("shell", "dumpsys", "activity", "services", PAQUETE, tope=8).count("ServiceRecord"), "| bloqueos pendientes:",
          sum("tachan:envio" in l for l in adb("shell", "dumpsys", "power", tope=8).splitlines()))
    time.sleep(10)
    print("compu 10 s después:", compu.memory_info().private // 2**20, "MB | celu:", memoria_celu(), "MB")
finally:
    adb("shell", "rm", "-f", CELU)
    if destino.exists():
        for _ in range(20):
            try:
                destino.unlink(); break
            except OSError:
                time.sleep(0.5)
    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    if guardado is not None: win32clipboard.SetClipboardText(guardado, win32con.CF_UNICODETEXT)
    win32clipboard.CloseClipboard()
    print("limpio: archivo de prueba borrado de los dos lados, portapapeles restaurado")
