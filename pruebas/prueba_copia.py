"""Controla el portapapeles después de recibir, sin mover el mouse. Guarda el texto que haya y lo restaura."""
import base64, http.client, io, json, os, shutil, ssl, struct, subprocess, tempfile, time, urllib.parse
from pathlib import Path
import win32clipboard, win32con
from PIL import Image

REPO = Path(__file__).resolve().parent.parent
DATOS = Path(tempfile.gettempdir()) / "tachan_pruebas" / "copia_datos"
PUERTO = 47960


def abrir():
    for _ in range(40):
        try:
            win32clipboard.OpenClipboard()
            return
        except Exception:
            time.sleep(0.05)
    raise RuntimeError("portapapeles ocupado")


abrir()
guardado = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT) if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT) else None
win32clipboard.CloseClipboard()
shutil.rmtree(DATOS, ignore_errors=True); DATOS.mkdir(parents=True)
(DATOS / "ajustes.txt").write_text("sonido=0\n")
p = subprocess.Popen([REPO / "pc/compilado/Tachan.exe"], env=dict(os.environ, TACHAN_DATOS=str(DATOS), TACHAN_PUERTO=str(PUERTO)))
fallas = 0


def chequear(nombre, bien):
    global fallas
    print(("OK    " if bien else "FALLA ") + nombre)
    fallas += 0 if bien else 1


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


    token = json.loads(pedir("POST", "/vincular", X_Secreto=secreto, X_Dispositivo="Copia")[1])["token"]


    def mandar(datos, nombre, clase="archivo"):
        assert pedir("POST", "/enviar", datos, Authorization="Bearer " + token, X_Clase=clase, X_Nombre=urllib.parse.quote(nombre))[0] == 200


    def contenido():
        abrir()
        try:
            archivos = win32clipboard.GetClipboardData(win32con.CF_HDROP) if win32clipboard.IsClipboardFormatAvailable(win32con.CF_HDROP) else ()
            medida = struct.unpack("<ii", win32clipboard.GetClipboardData(win32con.CF_DIB)[4:12]) if win32clipboard.IsClipboardFormatAvailable(win32con.CF_DIB) else None
            texto = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT) if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT) else None
            return [Path(a).name for a in archivos], medida, texto
        finally:
            win32clipboard.CloseClipboard()


    im = Image.new("RGB", (1200, 800), (235, 110, 60)); im.paste((50, 90, 170), (0, 0, 600, 800))
    exif = Image.Exif(); exif[274] = 6
    b = io.BytesIO(); im.save(b, "JPEG", exif=exif); foto = b.getvalue()

    mandar(foto, "girada.jpg"); time.sleep(2)
    a, m, _ = contenido()
    chequear(f"una foto: archivo y dibujo derecho, {a} {m}", a == ["girada.jpg"] and m is not None and m[0] == 800 and abs(m[1]) == 1200)

    mandar(b"hola", "nota.txt"); time.sleep(2)
    a, m, _ = contenido()
    chequear(f"archivo sin imagen: sin dibujo, {a} {m}", a == ["nota.txt"] and m is None)

    mandar(foto, "primera.jpg"); mandar(b"chau", "ultima.txt"); time.sleep(2)
    a, m, _ = contenido()
    chequear(f"foto y archivo juntos: los dos y el dibujo de la foto, {a} {m}", a == ["primera.jpg", "ultima.txt"] and m is not None)

    mandar("Hola: ñandú".encode(), "", "texto"); time.sleep(2)
    a, m, t = contenido()
    chequear(f"texto: {t!r}", t == "Hola: ñandú" and not a)
    print("TODO BIEN" if fallas == 0 else f"FALLAS: {fallas}")
finally:
    p.kill(); time.sleep(0.3)
    abrir()
    win32clipboard.EmptyClipboard()
    if guardado is not None: win32clipboard.SetClipboardText(guardado, win32con.CF_UNICODETEXT)
    win32clipboard.CloseClipboard()
    print("portapapeles restaurado")
