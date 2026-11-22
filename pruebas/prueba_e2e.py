"""Levanta la compu aislada, verifica el QR y corre el cliente Java; saca fotos de cada aviso.

En Windows prueba pc/compilado/Tachan.exe (QR con OpenCV, fotos de la pantalla). En Mac prueba
mac/compilado/Tachan.app: el QR lo lee el lector del celu (QrLector.java) y las fotos de los avisos
las deja la propia app en la carpeta de datos, así nunca sale el resto de la pantalla.
"""
import io, os, shutil, socket, struct, subprocess, sys, threading, time, zlib
from pathlib import Path

MAC = sys.platform == "darwin"
AQUI = Path(__import__("tempfile").gettempdir()) / "tachan_pruebas"; AQUI.mkdir(exist_ok=True)
REPO = Path(__file__).resolve().parent.parent
if MAC:
    JDK = Path(os.environ.get("JAVA_HOME", "/opt/homebrew/opt/openjdk@17")) / "bin"
    EXE = REPO / "mac" / "compilado" / "Tachan.app" / "Contents" / "MacOS" / "Tachan"
    JAVA, JAVAC = JDK / "java", JDK / "javac"
else:
    from PIL import Image, ImageGrab
    import win32con, win32gui
    JDK = Path(r"D:\dev\jdk17\bin")
    EXE = REPO / "pc" / "compilado" / "Tachan.exe"
    JAVA, JAVAC = JDK / "java.exe", JDK / "javac.exe"
CLASES = REPO / "android" / "prueba" / "compilado"


def puerto_libre():
    """TCP y el UDP siguiente libres, para no cruzarse con una compu de otra corrida que quedó viva."""
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


def png_gris(ruta):
    """Lee un PNG de 8 bits sin entrelazar (el que escribe la app) y lo devuelve en gris: ancho, alto, bytes."""
    d = Path(ruta).read_bytes()
    i, datos, ancho = 8, b"", 0
    while i < len(d):
        largo, tipo = struct.unpack(">I4s", d[i:i + 8])
        cuerpo = d[i + 8:i + 8 + largo]
        if tipo == b"IHDR":
            ancho, alto, _, color = struct.unpack(">IIBB", cuerpo[:10])
            canales = {0: 1, 2: 3, 4: 2, 6: 4}[color]
        elif tipo == b"IDAT":
            datos += cuerpo
        i += 12 + largo
    crudo, fila, previa, salida = zlib.decompress(datos), ancho * canales, bytearray(ancho * canales), bytearray()
    for y in range(alto):
        filtro, linea = crudo[y * (fila + 1)], bytearray(crudo[y * (fila + 1) + 1:(y + 1) * (fila + 1)])
        for x in range(fila):
            a = linea[x - canales] if x >= canales else 0
            b, c = previa[x], previa[x - canales] if x >= canales else 0
            if filtro == 1: linea[x] = (linea[x] + a) & 255
            elif filtro == 2: linea[x] = (linea[x] + b) & 255
            elif filtro == 3: linea[x] = (linea[x] + (a + b) // 2) & 255
            elif filtro == 4:
                p = a + b - c; pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                linea[x] = (linea[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        salida += bytes(linea[x * canales] for x in range(ancho))
        previa = linea
    return ancho, alto, bytes(salida)


def foto_jpeg():
    """Una foto de 900x600 con orientación EXIF 6: si la compu no la endereza, el aviso la muestra acostada."""
    if not MAC:
        im = Image.new("RGB", (900, 600), (235, 110, 60)); im.paste((50, 90, 170), (0, 0, 450, 600))
        exif = Image.Exif(); exif[274] = 6
        b = io.BytesIO(); im.save(b, "JPEG", exif=exif)
        return b.getvalue()
    # Sin PIL: la dibuja sips desde un PPM y le pone la orientación.
    ppm = AQUI / "foto_e2e.ppm"
    fila = bytes((50, 90, 170)) * 450 + bytes((235, 110, 60)) * 450
    ppm.write_bytes(b"P6 900 600 255\n" + fila * 600)
    jpg = AQUI / "foto_e2e.jpg"
    subprocess.run(["sips", "-s", "format", "jpeg", str(ppm), "--out", str(jpg)], check=True, capture_output=True)
    # sips no escribe la orientación: va un EXIF mínimo (una sola entrada, 0x0112 = 6) después del SOI.
    tiff = b"II*\x00" + struct.pack("<I", 8) + struct.pack("<H", 1) + struct.pack("<HHIHH", 0x0112, 3, 1, 6, 0) + struct.pack("<I", 0)
    app1 = b"Exif\x00\x00" + tiff
    d = jpg.read_bytes()
    return d[:2] + b"\xff\xe1" + struct.pack(">H", len(app1) + 2) + app1 + d[2:]


PUERTO = puerto_libre()
# Carpeta propia por corrida: la compu es "programa único" por carpeta de datos, y así no le habla a una vieja.
for vieja in AQUI.glob("e2e_datos*"): shutil.rmtree(vieja, ignore_errors=True)
DATOS = AQUI / f"e2e_datos_{os.getpid()}"
DATOS.mkdir()
shutil.rmtree(CLASES, ignore_errors=True)
CLASES.mkdir(parents=True)
subprocess.run([JAVAC, "-encoding", "UTF-8", "-d", CLASES,
                REPO / "android/src/com/kvothesson/tachan/Transporte.java",
                REPO / "android/src/com/kvothesson/tachan/QrLector.java",
                REPO / "android/prueba/PruebaTransporte.java",
                REPO / "android/prueba/PruebaLector.java"], check=True)

foto = AQUI / "foto_e2e.jpg"; foto.write_bytes(foto_jpeg())

entorno = dict(os.environ, TACHAN_DATOS=str(DATOS), TACHAN_PUERTO=str(PUERTO), TACHAN_NOMBRE="Mi compu")
p = subprocess.Popen([EXE], env=entorno)
codigo = 1
try:
    enlace = DATOS / "enlace.txt"
    for _ in range(60):
        if enlace.exists(): break
        time.sleep(0.25)
    time.sleep(2.5)
    print("compu viva:", p.poll() is None, "| enlace:", enlace.read_text().split("c=")[0] + "c=...")

    if MAC:
        # El QR que dibuja la app, leído por el mismo lector que usa el celu.
        crudos = DATOS / "qr_crudo"; crudos.mkdir()
        ancho, alto, gris = png_gris(DATOS / "qr.png")
        (crudos / f"qr_{ancho}x{alto}.raw").write_bytes(gris)
        lector = subprocess.run([JAVA, "-cp", CLASES, "com.kvothesson.tachan.PruebaLector", crudos, enlace], capture_output=True, text=True)
        print("QR leído por QrLector igual al enlace:", "TODO BIEN" in lector.stdout)
    else:
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

    def foto_aviso(nombre):
        """En Windows busca la ventana sin título del proceso y la fotografía. En Mac las fotos las deja la app."""
        if MAC:
            return False
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

    cliente = subprocess.Popen([JAVA, "-Dfile.encoding=UTF-8", "-cp", CLASES, "PruebaTransporte", enlace, str(PUERTO + 1), foto],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    salida = []
    lector = threading.Thread(target=lambda: salida.extend(cliente.stdout.readlines()), daemon=True)
    lector.start()
    t0 = time.time()
    n = 0
    while cliente.poll() is None and time.time() - t0 < 120:
        time.sleep(0.25)
        n += 1
        if n % 4 == 0: foto_aviso(f"t{n//4:02d}")
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
    if MAC:
        marca = subprocess.run(["xattr", "-p", "com.apple.quarantine", exe_recibido], capture_output=True, text=True).returncode == 0
    else:
        marca = exe_recibido.exists() and "ZoneId=3" in open(str(exe_recibido) + ":Zone.Identifier").read()
    print("marca de internet en el exe:", marca)
    if dispositivos.exists():
        celus = dispositivos.read_text(encoding="utf-8")
        print("celus tras desvincular:", repr(celus))
        print("token en disco en claro:", any("token-" in l for l in celus.splitlines()))
    if MAC:
        time.sleep(1)
        print("fotos de avisos:", sorted(x.name for x in DATOS.glob("aviso_*.png")), "en", DATOS)
    print("compu viva al final:", p.poll() is None)
finally:
    # Siempre, aunque algo falle antes: si no, queda escuchando.
    p.kill()
    p.wait(timeout=10)
    print("compu cerrada:", p.poll() is not None)
sys.exit(codigo)
