"""Levanta el exe aislado, verifica el QR con OpenCV y corre el cliente Java; saca fotos de cada aviso."""
import io, os, shutil, socket, subprocess, sys, threading, time
from pathlib import Path
from PIL import Image, ImageGrab
import win32con, win32gui

AQUI = Path(__import__("tempfile").gettempdir()) / "tachan_pruebas"; AQUI.mkdir(exist_ok=True)
REPO = Path(r"D:\repos\tachan")
JDK = Path(r"D:\dev\jdk17\bin")
CLASES = REPO / "android" / "prueba" / "compilado"
EXE = REPO / "pc" / "compilado" / "Tachan.exe"


def puerto_libre():
    """TCP y el UDP siguiente libres, para no cruzarse con un exe de otra corrida que quedó vivo."""
    for _ in range(50):
        with socket.socket() as t:
            t.bind(("", 0)); puerto = t.getsockname()[1]
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as u: u.bind(("", puerto + 1))
            with socket.socket() as t: t.bind(("", puerto))
            return puerto
        except OSError:
            continue
    sys.exit("No encontré dos puertos seguidos libres")

PUERTO = puerto_libre()
# Carpeta propia por corrida: el exe es "programa único" por carpeta de datos, y así no le habla a uno viejo.
for vieja in AQUI.glob("e2e_datos*"): shutil.rmtree(vieja, ignore_errors=True)
DATOS = AQUI / f"e2e_datos_{os.getpid()}"
DATOS.mkdir()
shutil.rmtree(CLASES, ignore_errors=True)
CLASES.mkdir(parents=True)
subprocess.run([JDK / "javac.exe", "-encoding", "UTF-8", "-d", CLASES,
                REPO / "android/src/com/kvothesson/tachan/Transporte.java",
                REPO / "android/prueba/PruebaTransporte.java"], check=True)

im = Image.new("RGB", (900, 600), (235, 110, 60)); im.paste((50, 90, 170), (0, 0, 450, 600))
exif = Image.Exif(); exif[274] = 6
b = io.BytesIO(); im.save(b, "JPEG", exif=exif)
foto = AQUI / "foto_e2e.jpg"; foto.write_bytes(b.getvalue())

entorno = dict(os.environ, TACHAN_DATOS=str(DATOS), TACHAN_PUERTO=str(PUERTO))
p = subprocess.Popen([EXE], env=entorno)
codigo = 1
try:
    enlace = DATOS / "enlace.txt"
    for _ in range(60):
        if enlace.exists(): break
        time.sleep(0.25)
    time.sleep(2.5)
    print("exe vivo:", p.poll() is None, "| enlace:", enlace.read_text().split("c=")[0] + "c=...")

    v = win32gui.FindWindow(None, "Tachán")
    # Adelante de todo un momento: si otra ventana la tapa, la foto sale de esa ventana.
    win32gui.SetWindowPos(v, win32con.HWND_TOPMOST, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
    time.sleep(0.4)
    rect = win32gui.GetWindowRect(v)
    ImageGrab.grab(bbox=rect, all_screens=True).save(AQUI / "v_vinculo.png")
    import cv2, numpy as np
    gris = cv2.cvtColor(np.array(ImageGrab.grab(bbox=rect, all_screens=True)), cv2.COLOR_RGB2GRAY)
    leido, _, _ = cv2.QRCodeDetector().detectAndDecode(gris)
    print("QR en pantalla leído con OpenCV igual al enlace:", leido == enlace.read_text())

    fotos = {}
    def foto_aviso(nombre):
        """Busca la ventana sin título del proceso y la fotografía."""
        res = []
        def ver(h, _):
            import win32process
            if win32process.GetWindowThreadProcessId(h)[1] == p.pid and win32gui.IsWindowVisible(h) and win32gui.GetWindowText(h) == "":
                r = win32gui.GetWindowRect(h)
                if r[2] - r[0] > 100: res.append(r)
        win32gui.EnumWindows(ver, None)
        if res:
            ImageGrab.grab(bbox=res[0], all_screens=True).save(AQUI / f"aviso_{nombre}.png")
        return bool(res)

    cliente = subprocess.Popen([JDK / "java.exe", "-Dfile.encoding=UTF-8", "-cp", CLASES, "PruebaTransporte", enlace, str(PUERTO + 1), foto],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    salida = []
    lector = threading.Thread(target=lambda: salida.extend(cliente.stdout.readlines()), daemon=True)
    lector.start()
    vistos = {}
    t0 = time.time()
    n = 0
    ultimo = None
    while cliente.poll() is None and time.time() - t0 < 120:
        a = sorted((DATOS / "recibidos").glob("*")) if (DATOS / "recibidos").exists() else []
        clave = tuple(x.name for x in a)
        if clave != ultimo:
            ultimo = clave
        time.sleep(0.25)
        n += 1
        if n % 4 == 0 and foto_aviso(f"t{n//4:02d}"):
            vistos[n // 4] = True
    codigo = cliente.wait(timeout=30)
    lector.join(timeout=10)
    # Primero lo que dijo el cliente: si algo falla después, igual queda a la vista.
    print("".join(salida))
    dispositivos = DATOS / "dispositivos.txt"
    if not dispositivos.exists():
        print("FALLA: no hay dispositivos.txt, el vínculo no se guardó")
        codigo = codigo or 1
    recibidos = DATOS / "recibidos"
    print("recibidos:", [(x.name, x.stat().st_size) for x in sorted(recibidos.glob("*"))] if recibidos.exists() else "ninguno")
    exe_recibido = recibidos / "programa.exe"
    print("marca de internet en el exe:", exe_recibido.exists() and "ZoneId=3" in open(str(exe_recibido) + ":Zone.Identifier").read())
    if dispositivos.exists():
        celus = dispositivos.read_text(encoding="utf-8")
        print("celus tras desvincular:", repr(celus))
        print("token en disco en claro:", any("token-" in l for l in celus.splitlines()))
    print("exe vivo al final:", p.poll() is None)
finally:
    # Siempre, aunque algo falle antes: si no, el exe queda escuchando.
    p.kill()
    p.wait(timeout=10)
    print("exe cerrado:", p.poll() is not None)
sys.exit(codigo)
