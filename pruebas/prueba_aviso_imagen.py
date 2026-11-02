"""Manda imágenes altas, anchas y transparentes, y saca una foto de cada aviso para comprobar que se vean enteras.

Guarda el texto del portapapeles y lo restaura."""
import base64, http.client, io, json, os, shutil, ssl, subprocess, tempfile, time, urllib.parse
from pathlib import Path
import win32clipboard, win32con, win32gui, win32process
from PIL import Image, ImageDraw, ImageGrab

REPO = Path(__file__).resolve().parent.parent
AQUI = Path(tempfile.gettempdir()) / "tachan_pruebas"
DATOS = AQUI / "imagen_datos"
PUERTO = 47995


def prueba(ancho, alto, alfa=False):
    """Bordes de colores: si el aviso recorta la imagen, en la foto falta alguno."""
    im = Image.new("RGBA", (ancho, alto), (0, 0, 0, 0) if alfa else (240, 240, 240, 255))
    d = ImageDraw.Draw(im)
    g = max(ancho, alto) // 25
    d.rectangle((0, 0, ancho, g), fill=(230, 40, 40, 255))
    d.rectangle((0, alto - g, ancho, alto), fill=(40, 90, 230, 255))
    d.rectangle((0, 0, g, alto), fill=(40, 180, 80, 255))
    d.rectangle((ancho - g, 0, ancho, alto), fill=(240, 180, 30, 255))
    d.ellipse((ancho // 4, alto // 2 - ancho // 4, ancho * 3 // 4, alto // 2 + ancho // 4), fill=(250, 140, 20, 255))
    b = io.BytesIO(); im.save(b, "PNG"); return b.getvalue()


win32clipboard.OpenClipboard()
guardado = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT) if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT) else None
win32clipboard.CloseClipboard()
shutil.rmtree(DATOS, ignore_errors=True); DATOS.mkdir(parents=True)
(DATOS / "ajustes.txt").write_text("sonido=0\n")
p = subprocess.Popen([REPO / "pc/compilado/Tachan.exe"], env=dict(os.environ, TACHAN_DATOS=str(DATOS), TACHAN_PUERTO=str(PUERTO)))
try:
    for _ in range(60):
        if (DATOS / "enlace.txt").exists(): break
        time.sleep(0.25)
    time.sleep(1)
    c = (DATOS / "enlace.txt").read_text().split("c=")[1].split("&")[0]
    secreto = base64.b32decode(c.upper() + "=" * (-len(c) % 8))[6:12].hex()
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE


    def pedir(metodo, ruta, cuerpo=b"", **cab):
        con = http.client.HTTPSConnection("127.0.0.1", PUERTO, context=ctx, timeout=30)
        con.request(metodo, ruta, body=cuerpo, headers={k.replace("_", "-"): v for k, v in cab.items()})
        r = con.getresponse(); d = r.read(); con.close()
        return r.status, d


    token = json.loads(pedir("POST", "/vincular", X_Secreto=secreto, X_Dispositivo="Imagen")[1])["token"]


    def aviso():
        res = []
        def ver(h, _):
            if win32process.GetWindowThreadProcessId(h)[1] == p.pid and win32gui.IsWindowVisible(h) and win32gui.GetWindowText(h) == "":
                r = win32gui.GetWindowRect(h)
                if r[2] - r[0] > 100: res.append(r)
        win32gui.EnumWindows(ver, None)
        return res[0] if res else None


    time.sleep(1)
    fotos = []
    for nombre, datos in (("alta", prueba(282, 630, True)), ("muy_alta", prueba(300, 2000)), ("cuadrada", prueba(800, 800)), ("normal", prueba(1600, 1000)), ("muy_ancha", prueba(2000, 300))):
        assert pedir("POST", "/enviar", datos, Authorization="Bearer " + token, X_Clase="archivo", X_Nombre=urllib.parse.quote(nombre + ".png"))[0] == 200
        time.sleep(1.7)
        r = aviso()
        foto = ImageGrab.grab(bbox=r, all_screens=True)
        fotos.append(foto)
        print(nombre, "aviso de", r[2] - r[0], "x", r[3] - r[1])
    lienzo = Image.new("RGB", (sum(f.width for f in fotos) + 20 * (len(fotos) + 1), max(f.height for f in fotos) + 40), (128, 128, 128))
    x = 20
    for f in fotos:
        lienzo.paste(f, (x, 20)); x += f.width + 20
    lienzo.save(AQUI / "avisos.png")
finally:
    p.kill(); time.sleep(0.3)
    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    if guardado is not None: win32clipboard.SetClipboardText(guardado, win32con.CF_UNICODETEXT)
    win32clipboard.CloseClipboard()
    print("portapapeles restaurado")
