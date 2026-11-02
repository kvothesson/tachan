"""Mide un envío real por el camino de una persona: + -> Fotos y videos -> elegir, y bloquea el celu mientras viaja.

Requiere el celu desbloqueado, vinculado y sin tocar. Lee la pantalla antes de cada toque, y corta si no ve lo esperado.
Crea un video de prueba, lo manda y lo borra de los dos lados. Guarda el texto del portapapeles y lo restaura."""
import re, subprocess, sys, tempfile, time
from pathlib import Path
import psutil
import win32clipboard, win32con
from PIL import Image

ADB = r"D:\dev\android-sdk\platform-tools\adb.exe"
PAQUETE = "com.kvothesson.tachan"
MB = int(sys.argv[1]) if len(sys.argv) > 1 else 300
NOMBRE = "tachan_prueba.mp4"
CELU = f"/sdcard/DCIM/{NOMBRE}"
RECIBIDOS = Path.home() / "Downloads" / "Tachan"
AQUI = Path(tempfile.gettempdir()) / "tachan_pruebas"
CAPTURA = AQUI / "notificacion.png"


def adb(*a, tope=30):
    try:
        return subprocess.run([ADB, *a], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=tope).stdout.strip()
    except subprocess.TimeoutExpired:
        return ""


def pantalla():
    adb("shell", "uiautomator", "dump", "/sdcard/ui.xml", tope=20)
    x = adb("shell", "cat", "/sdcard/ui.xml", tope=10)
    adb("shell", "rm", "-f", "/sdcard/ui.xml")
    return re.findall(r"<node [^>]*>", x)


def centro(nodo):
    b = list(map(int, re.findall(r"\d+", re.search(r'bounds="([^"]*)"', nodo)[1])))
    return (b[0] + b[2]) // 2, (b[1] + b[3]) // 2


def buscar(patron, nodos=None):
    for n in nodos if nodos is not None else pantalla():
        d = re.search(r'text="([^"]*)"', n)[1] + "|" + re.search(r'content-desc="([^"]*)"', n)[1]
        if re.search(patron, d):
            return n
    return None


def tocar(patron, intentos=8):
    for _ in range(intentos):
        n = buscar(patron)
        if n:
            x, y = centro(n)
            adb("shell", "input", "tap", str(x), str(y))
            return True
        time.sleep(0.7)
    raise SystemExit(f"no veo {patron!r} en pantalla: corto sin tocar nada más")


def memoria():
    for l in adb("shell", "dumpsys", "meminfo", PAQUETE, tope=8).splitlines():
        if "TOTAL PSS" in l:
            return int(l.split()[2]) // 1024
    return 0


def cpu():
    pid = adb("shell", "pidof", PAQUETE).split()
    if not pid:
        return 0.0
    for l in adb("shell", "top", "-b", "-n", "1", "-p", pid[0], tope=8).splitlines():
        p = l.split()
        if p and p[0] == pid[0]:
            return float(p[8])
    return 0.0


def bloqueado():
    return "isKeyguardShowing=true" in adb("shell", "dumpsys", "window")


adb("shell", "input", "keyevent", "KEYCODE_WAKEUP"); adb("shell", "wm", "dismiss-keyguard"); time.sleep(1.5)
if bloqueado():
    raise SystemExit("EL CELU ESTA BLOQUEADO: hay que desbloquearlo")
win32clipboard.OpenClipboard()
guardado = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT) if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT) else None
win32clipboard.CloseClipboard()
antes = {f.name for f in RECIBIDOS.iterdir()} if RECIBIDOS.exists() else set()
destino = None


def llegado():
    # El selector de fotos le cambia el nombre: se reconoce como lo nuevo con el tamaño justo.
    for f in RECIBIDOS.iterdir():
        if f.name not in antes and not f.name.startswith(".") and f.stat().st_size == MB * 2**20:
            return f
    return None


compu = psutil.Process(next(p.pid for p in psutil.process_iter(["name"]) if p.info["name"] == "Tachan.exe"))
try:
    print(f"creando el video de prueba de {MB} MB")
    adb("shell", "dd", "if=/dev/urandom", f"of={CELU}", "bs=1048576", f"count={MB}", tope=300)
    adb("shell", "am", "broadcast", "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE", "-d", f"file://{CELU}")
    time.sleep(4)
    adb("shell", "input", "keyevent", "KEYCODE_WAKEUP")
    adb("shell", "am", "start", "-n", f"{PAQUETE}/.Principal"); time.sleep(2)
    if not buscar("Eleg"):
        raise SystemExit("Tachán no está en su pantalla principal: ¿sigue vinculado?")
    print("reposo: cpu", cpu(), "% memoria", memoria(), "MB")
    tocar("Eleg"); time.sleep(1.2)
    tocar("Fotos y"); time.sleep(3)
    nodos = pantalla()
    miniaturas = [n for n in nodos if 'clickable="true"' in n and re.search(r'content-desc="[^"]*(Video|video|Foto|Photo|Imagen)[^"]*"', n)]
    print("en el selector:", len(miniaturas), "miniaturas; la primera:", (re.search(r'content-desc="([^"]*)"', miniaturas[0])[1][:70] if miniaturas else "ninguna"))
    if not miniaturas:
        raise SystemExit("no reconozco el selector de fotos: corto sin elegir nada")
    primera = re.search(r'content-desc="([^"]*)"', miniaturas[0])[1]
    if not re.search("video", primera, re.I):
        raise SystemExit(f"la primera miniatura no es el video de prueba ({primera[:50]}): corto para no mandar una foto tuya")
    x, y = centro(miniaturas[0]); adb("shell", "input", "tap", str(x), str(y)); time.sleep(1)
    n = buscar("Agregar|Add|Listo|Done")
    if n:
        x, y = centro(n); adb("shell", "input", "tap", str(x), str(y))
    compu_antes = compu.memory_info().private // 2**20
    t0 = time.time()
    empezo = None
    while empezo is None and time.time() - t0 < 60:
        if any(RECIBIDOS.glob(".recibiendo_*")): empezo = time.time()
        time.sleep(0.2)
    print("arrancó el envío:", empezo is not None)
    time.sleep(5)
    notif = adb("shell", "dumpsys", "notification", "--noredact", tope=8)
    print("notificación:", [l.strip()[:70] for l in notif.splitlines() if ("android.title=" in l or "android.text=" in l) and ("Enviando" in l or " MB" in l)][:3])
    adb("shell", "cmd", "statusbar", "expand-notifications"); time.sleep(1.2)
    nodos = pantalla()
    n = buscar(r"Enviando", nodos)
    with open(CAPTURA, "wb") as f:
        subprocess.run([ADB, "exec-out", "screencap", "-p"], stdout=f, timeout=20)
    if n:
        b = list(map(int, re.findall(r"\d+", re.search(r'bounds="([^"]*)"', n)[1])))
        Image.open(CAPTURA).crop((0, max(0, b[1] - 70), 1080, b[3] + 170)).save(AQUI / "notificacion_recorte.png")
    CAPTURA.unlink(missing_ok=True)  # la pantalla entera muestra otras notificaciones personales
    adb("shell", "cmd", "statusbar", "collapse")
    adb("shell", "input", "keyevent", "KEYCODE_SLEEP")
    print("celu bloqueado durante el envío")
    # Sin pedirle nada al celu mientras viaja: medir su memoria también lo frena.
    while llegado() is None and time.time() - t0 < 900:
        time.sleep(0.5)
    destino = llegado()
    assert destino, "no llegó"
    red = time.time() - empezo
    print(f"llegó con el celu bloqueado: {MB} MB en {red:.1f} s = {MB / red:.2f} MB/s")
    time.sleep(10)
    print("10 s después: compu", compu.memory_info().private // 2**20, "MB, celu", memoria(), "MB, servicio activo:", adb("shell", "dumpsys", "activity", "services", PAQUETE, tope=8).count("ServiceRecord"))
finally:
    adb("shell", "rm", "-f", CELU)
    adb("shell", "am", "broadcast", "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE", "-d", f"file://{CELU}")
    for _ in range(20):
        try:
            if destino is not None: destino.unlink(missing_ok=True)
            break
        except OSError:
            time.sleep(0.5)
    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    if guardado is not None: win32clipboard.SetClipboardText(guardado, win32con.CF_UNICODETEXT)
    win32clipboard.CloseClipboard()
    print("limpio: archivo de prueba borrado de los dos lados, portapapeles restaurado")
