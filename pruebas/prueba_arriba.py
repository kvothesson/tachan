"""Comprueba que el aviso se vea sobre una ventana a pantalla completa, sin sacarle el foco.

Abre esa ventana unos segundos. Guarda el texto del portapapeles y lo restaura."""
import base64, http.client, io, json, os, shutil, ssl, subprocess, sys, tempfile, time
from pathlib import Path
import numpy as np
import win32clipboard, win32con, win32gui, win32process
from PIL import Image, ImageGrab

REPO = Path(__file__).resolve().parent.parent
DATOS = Path(tempfile.gettempdir()) / "tachan_pruebas" / "arriba_datos"
PUERTO = 47985
win32clipboard.OpenClipboard()
guardado = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT) if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT) else None
win32clipboard.CloseClipboard()
shutil.rmtree(DATOS, ignore_errors=True); DATOS.mkdir(parents=True)
(DATOS / "ajustes.txt").write_text("sonido=0\n")
p = subprocess.Popen([REPO / "pc/compilado/Tachan.exe"], env=dict(os.environ, TACHAN_DATOS=str(DATOS), TACHAN_PUERTO=str(PUERTO)))
tapa = None
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


    token = json.loads(pedir("POST", "/vincular", X_Secreto=secreto, X_Dispositivo="Arriba")[1])["token"]


    def aviso():
        res = []
        def ver(h, _):
            if win32process.GetWindowThreadProcessId(h)[1] == p.pid and win32gui.IsWindowVisible(h) and win32gui.GetWindowText(h) == "":
                r = win32gui.GetWindowRect(h)
                if r[2] - r[0] > 100: res.append(h)
        win32gui.EnumWindows(ver, None)
        return res[0] if res else None


    time.sleep(8)  # que se vaya el aviso de vinculado: el que importa es el que aparece después
    codigo = "import tkinter as t\nr=t.Tk();r.configure(bg='#00ff00');r.attributes('-fullscreen',True);r.after(200,r.focus_force);r.after(12000,r.destroy);r.mainloop()\n"
    tapa = subprocess.Popen([sys.executable, "-c", codigo]); time.sleep(2.5)
    foco = win32gui.GetForegroundWindow()
    im = Image.new("RGB", (1200, 800), (40, 60, 200)); b = io.BytesIO(); im.save(b, "JPEG")
    assert pedir("POST", "/enviar", b.getvalue(), Authorization="Bearer " + token, X_Clase="archivo", X_Nombre="arriba.jpg")[0] == 200
    time.sleep(1.6)
    h = aviso()
    assert h, "no apareció el aviso"
    r = win32gui.GetWindowRect(h)
    captura = np.array(ImageGrab.grab(bbox=r, all_screens=True))
    verde = float(((captura[..., 1] > 200) & (captura[..., 0] < 60) & (captura[..., 2] < 60)).mean())
    capa = win32gui.GetWindowLong(h, win32con.GWL_EXSTYLE) & win32con.WS_EX_TOPMOST
    print("marcado arriba de todo:", bool(capa))
    print(f"se ve sobre la pantalla completa: {verde < 0.05} ({verde:.0%} del aviso tapado)")
    print("foco sin cambiar:", foco == win32gui.GetForegroundWindow())
    print("TODO BIEN" if capa and verde < 0.05 and foco == win32gui.GetForegroundWindow() else "FALLA")
finally:
    if tapa: tapa.kill()
    p.kill(); time.sleep(0.3)
    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    if guardado is not None: win32clipboard.SetClipboardText(guardado, win32con.CF_UNICODETEXT)
    win32clipboard.CloseClipboard()
    print("portapapeles restaurado")
