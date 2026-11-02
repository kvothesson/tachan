"""Manda muchas fotos grandes al exe aislado y mide memoria, CPU en reposo y qué tan rápido responde.

Usa el portapapeles real: guarda el texto que haya y lo restaura. Una imagen copiada se pierde."""
import base64, http.client, io, json, os, shutil, ssl, subprocess, sys, tempfile, time, urllib.parse
from pathlib import Path
import numpy as np
import psutil
import win32clipboard, win32con, win32gui, win32process
from PIL import Image

REPO = Path(__file__).resolve().parent.parent
AQUI = Path(tempfile.gettempdir()) / "tachan_pruebas"; AQUI.mkdir(exist_ok=True)
DATOS = AQUI / "memoria_datos"
PUERTO = 47950
FOTOS = int(sys.argv[1]) if len(sys.argv) > 1 else 25
ANCHO, ALTO = 4000, 3000


def leer_texto():
    win32clipboard.OpenClipboard()
    try:
        return win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT) if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT) else None
    finally:
        win32clipboard.CloseClipboard()


def poner_texto(t):
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        if t is not None:
            win32clipboard.SetClipboardText(t, win32con.CF_UNICODETEXT)
    finally:
        win32clipboard.CloseClipboard()


guardado = leer_texto()
shutil.rmtree(DATOS, ignore_errors=True); DATOS.mkdir()
(DATOS / "ajustes.txt").write_text("sonido=0\n")
p = subprocess.Popen([REPO / "pc/compilado/Tachan.exe"], env=dict(os.environ, TACHAN_DATOS=str(DATOS), TACHAN_PUERTO=str(PUERTO)))
try:
    for _ in range(60):
        if (DATOS / "enlace.txt").exists(): break
        time.sleep(0.25)
    time.sleep(1)
    enlace = (DATOS / "enlace.txt").read_text()
    c = enlace.split("c=")[1].split("&")[0]
    secreto = base64.b32decode(c.upper() + "=" * (-len(c) % 8))[6:12].hex()
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE


    def pedir(metodo, ruta, cuerpo=b"", **cab):
        con = http.client.HTTPSConnection("127.0.0.1", PUERTO, context=ctx, timeout=60)
        con.request(metodo, ruta, body=cuerpo, headers={k.replace("_", "-"): v for k, v in cab.items()})
        r = con.getresponse(); d = r.read(); con.close()
        return r.status, d


    token = json.loads(pedir("POST", "/vincular", X_Secreto=secreto, X_Dispositivo="Memoria")[1])["token"]
    proceso = psutil.Process(p.pid)


    def megas():
        m = proceso.memory_info()
        return m.rss // 2**20, m.private // 2**20


    def aviso_visible():
        res = []
        def ver(h, _):
            if win32process.GetWindowThreadProcessId(h)[1] == p.pid and win32gui.IsWindowVisible(h) and win32gui.GetWindowText(h) == "":
                r = win32gui.GetWindowRect(h)
                if r[2] - r[0] > 100: res.append(h)
        win32gui.EnumWindows(ver, None)
        return bool(res)


    tope = time.time() + 12
    while aviso_visible() and time.time() < tope: time.sleep(0.1)  # el aviso de "vinculado"
    time.sleep(1)
    print("al arrancar (uso, privada MB):", megas())
    azar = np.random.default_rng(3)
    grande = azar.integers(0, 255, (ALTO // 16, ANCHO // 16, 3), dtype=np.uint8)
    im = Image.fromarray(grande).resize((ANCHO, ALTO), Image.BICUBIC)
    b = io.BytesIO(); im.save(b, "JPEG", quality=92); foto = b.getvalue()
    print(f"foto de prueba: {ANCHO}x{ALTO}, {len(foto) // 1024} KB")

    picos, esperas = [], []
    for n in range(FOTOS):
        t0 = time.time()
        assert pedir("POST", "/enviar", foto, Authorization="Bearer " + token, X_Clase="archivo", X_Nombre=urllib.parse.quote(f"m{n}.jpg"))[0] == 200
        tope = time.time() + 8
        while not aviso_visible() and time.time() < tope: time.sleep(0.01)
        esperas.append(time.time() - t0)
        time.sleep(1.0)
        picos.append(megas()[1])
        if n % 10 == 9: print(f"  {n + 1:3} fotos: {megas()} handles {proceso.num_handles()} hilos {proceso.num_threads()}")
    print(f"pico de memoria privada: {max(picos)} MB")
    for _ in range(60):
        time.sleep(0.25)
        if not aviso_visible(): break
    time.sleep(10)
    print("tras cerrar el aviso y 10 s (uso, privada MB):", megas())
    proceso.cpu_percent(None); time.sleep(10)
    print("CPU en reposo (%):", proceso.cpu_percent(None), "| hilos:", proceso.num_threads(), "| handles:", proceso.num_handles())
finally:
    p.kill()
    time.sleep(0.3)
    poner_texto(guardado)
    print("portapapeles restaurado")
