"""Lo que sale de la cola del celu no pisa el portapapeles ni se suma a lo nuevo. Guarda el texto que haya y lo restaura."""
import base64, http.client, io, json, os, shutil, ssl, struct, subprocess, tempfile, time, urllib.parse
from pathlib import Path
import win32clipboard, win32con
from PIL import Image, ImageGrab

REPO = Path(__file__).resolve().parent.parent
DATOS = Path(tempfile.gettempdir()) / "tachan_pruebas" / "demorado_datos"
PUERTO = 47965


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


def poner_marca(texto):
    abrir()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardText(texto, win32con.CF_UNICODETEXT)
    win32clipboard.CloseClipboard()


def contenido():
    abrir()
    try:
        archivos = win32clipboard.GetClipboardData(win32con.CF_HDROP) if win32clipboard.IsClipboardFormatAvailable(win32con.CF_HDROP) else ()
        texto = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT) if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT) else None
        return [Path(a).name for a in archivos], texto
    finally:
        win32clipboard.CloseClipboard()


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


    token = json.loads(pedir("POST", "/vincular", X_Secreto=secreto, X_Dispositivo="Demorado")[1])["token"]
    time.sleep(7)  # que se vaya el aviso de "vinculado"


    def mandar(datos, nombre, clase="archivo", demorado=False):
        cab = dict(Authorization="Bearer " + token, X_Clase=clase, X_Nombre=urllib.parse.quote(nombre))
        if demorado: cab["X_Demorado"] = "1"
        assert pedir("POST", "/enviar", datos, **cab)[0] == 200


    def foto(color):
        b = io.BytesIO(); Image.new("RGB", (900, 600), color).save(b, "JPEG"); return b.getvalue()


    poner_marca("lo que yo tenia copiado")
    mandar(foto((235, 110, 60)), "vieja1.jpg", demorado=True)
    mandar(foto((50, 90, 170)), "vieja2.jpg", demorado=True)
    time.sleep(2)
    chequear(f"cola: el portapapeles queda igual, {contenido()}", contenido() == ([], "lo que yo tenia copiado"))
    pantalla = ImageGrab.grab()
    captura = Path(tempfile.gettempdir()) / "tachan_pruebas" / "aviso_demorado.png"
    pantalla.crop((pantalla.width - 360, pantalla.height - 460, pantalla.width, pantalla.height)).save(captura)  # solo el rincón del aviso
    print("captura:", captura)
    time.sleep(6)

    mandar(foto((60, 160, 90)), "nueva.jpg")
    mandar(foto((235, 110, 60)), "vieja3.jpg", demorado=True)
    time.sleep(2)
    a, _ = contenido()
    chequear(f"nuevo y cola juntos: solo se copia lo nuevo, {a}", a == ["nueva.jpg"])
    time.sleep(13)  # se va el de lo nuevo y aparece y se va el de la cola

    poner_marca("otra cosa copiada")
    mandar("clave sin saltos".encode(), "", "texto", demorado=True)
    time.sleep(2)
    chequear(f"texto de la cola: no se copia ni se pega solo, {contenido()}", contenido() == ([], "otra cosa copiada"))

    mandar("recien mandado".encode(), "", "texto")
    time.sleep(2)
    chequear(f"texto nuevo: se copia como siempre, {contenido()}", contenido() == ([], "recien mandado"))
    print("TODO BIEN" if fallas == 0 else f"FALLAS: {fallas}")
finally:
    p.kill(); time.sleep(0.3)
    abrir()
    win32clipboard.EmptyClipboard()
    if guardado is not None: win32clipboard.SetClipboardText(guardado, win32con.CF_UNICODETEXT)
    win32clipboard.CloseClipboard()
    print("portapapeles restaurado")
