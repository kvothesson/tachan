"""Prueba del programa de PC real: QR, foto, foco, portapapeles, arrastre a carpeta y pegado solo."""
import base64, http.client, io, json, os, shutil, ssl, struct, subprocess, sys, time, urllib.parse
from pathlib import Path
import cv2, numpy as np
import win32api, win32clipboard, win32con, win32gui, win32process
from PIL import Image, ImageGrab

AQUI = Path(__import__("tempfile").gettempdir()) / "tachan_pruebas"; AQUI.mkdir(exist_ok=True)
DATOS = AQUI / "pc_datos"
EXE = Path(r"D:\repos\tachan\pc\compilado\Tachan.exe")
PUERTO = 47920
shutil.rmtree(DATOS, ignore_errors=True); DATOS.mkdir()
entorno = dict(os.environ, TACHAN_DATOS=str(DATOS), TACHAN_PUERTO=str(PUERTO))
p = subprocess.Popen([EXE], env=entorno)
for _ in range(80):
    if (DATOS / "qr.png").exists() and (DATOS / "enlace.txt").exists(): break
    time.sleep(0.25)
time.sleep(0.6)
enlace = (DATOS / "enlace.txt").read_text()
qr = cv2.imread(str(DATOS / "qr.png"))
print("QR leído con OpenCV es el enlace:", cv2.QRCodeDetector().detectAndDecode(qr)[0] == enlace)

c = enlace.split("c=")[1].split("&")[0]
crudo = base64.b32decode(c.upper() + "=" * (-len(c) % 8))
secreto = crudo[6:12].hex()
ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE

def pedir(metodo, ruta, cuerpo=b"", **cab):
    con = http.client.HTTPSConnection("127.0.0.1", PUERTO, context=ctx, timeout=20)
    con.request(metodo, ruta, body=cuerpo, headers={k.replace("_", "-"): v for k, v in cab.items()})
    r = con.getresponse(); d = r.read(); con.close()
    return r.status, d

st, d = pedir("POST", "/vincular", X_Secreto=secreto, X_Dispositivo="Prueba")
token = json.loads(d)["token"]
print("vinculó:", st)
AUT = {"Authorization": "Bearer " + token}
time.sleep(1)

def mandar(datos, nombre, clase="archivo"):
    return pedir("POST", "/enviar", datos, X_Clase=clase, X_Nombre=urllib.parse.quote(nombre), **AUT)[0]

def ventana_aviso():
    res = []
    def ver(h, _):
        if win32process.GetWindowThreadProcessId(h)[1] == p.pid and win32gui.IsWindowVisible(h) and win32gui.GetWindowText(h) == "":
            r = win32gui.GetWindowRect(h)
            if r[2] - r[0] > 100: res.append((h, r))
    win32gui.EnumWindows(ver, None)
    return res[0] if res else (None, None)

# foto apaisada guardada girada: debe verse y copiarse vertical
im = Image.new("RGB", (1200, 800), (235, 110, 60)); im.paste((50, 90, 170), (0, 0, 600, 800))
exif = Image.Exif(); exif[274] = 6
b = io.BytesIO(); im.save(b, "JPEG", exif=exif)

foco = win32gui.GetForegroundWindow()
print("foto:", mandar(b.getvalue(), "foto vacaciones.jpg"))
time.sleep(1.6)
h, r = ventana_aviso()
print("aviso visible:", bool(h), r, "| foco sin cambiar:", foco == win32gui.GetForegroundWindow())
ImageGrab.grab(bbox=r, all_screens=True).save(AQUI / "pc_foto.png")
win32clipboard.OpenClipboard()
archivos = win32clipboard.GetClipboardData(win32con.CF_HDROP)
dib = win32clipboard.GetClipboardData(win32con.CF_DIB)
win32clipboard.CloseClipboard()
print("portapapeles: archivo", Path(archivos[0]).name, "| imagen", struct.unpack("<ii", dib[4:12]), "(debe ser 800 x ±1200)")

# arrastre real a una carpeta del Explorador
meta = AQUI / "pc_soltar"; shutil.rmtree(meta, ignore_errors=True); meta.mkdir()
subprocess.Popen(["explorer.exe", str(meta)]); time.sleep(2.5)
ex = win32gui.FindWindow("CabinetWClass", None)
win32gui.ShowWindow(ex, win32con.SW_RESTORE)
win32gui.SetWindowPos(ex, 0, 100, 100, 900, 600, 0); time.sleep(0.5)
print("foto 2:", mandar(b.getvalue(), "para arrastrar.jpg"))
time.sleep(1.4)
h, r = ventana_aviso()
hijos = []
win32gui.EnumChildWindows(ex, lambda w, _: hijos.append(w), None)
lista = win32gui.GetWindowRect(next(w for w in hijos if win32gui.GetClassName(w) == "SHELLDLL_DefView"))
dx, dy = (lista[0] + lista[2]) // 2, (lista[1] + lista[3]) // 2
W, H = win32api.GetSystemMetrics(0), win32api.GetSystemMetrics(1)
def mover(x, y):
    win32api.mouse_event(win32con.MOUSEEVENTF_MOVE | win32con.MOUSEEVENTF_ABSOLUTE, x * 65535 // (W - 1), y * 65535 // (H - 1))
previa = win32api.GetCursorPos()
x, y = (r[0] + r[2]) // 2, r[1] + 60
mover(x, y); time.sleep(0.2)
win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0); time.sleep(0.2)
for i in range(1, 51):
    mover(x + (dx - x) * i // 50, y + (dy - y) * i // 50); time.sleep(0.03)
for i in range(8):
    mover(dx + i % 2, dy); time.sleep(0.08)
win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0); time.sleep(1.5)
win32api.SetCursorPos(previa)
print("arrastre dejó en la carpeta:", [f.name for f in meta.iterdir()])
win32gui.PostMessage(ex, win32con.WM_CLOSE, 0, 0)
print("programa vivo tras arrastrar:", p.poll() is None)

# el aviso se va solo
time.sleep(9)
print("aviso se fue solo:", ventana_aviso()[0] is None)

# texto: copiado como texto
print("texto:", mandar("Hola: ñandú".encode(), "", "texto"))
time.sleep(1.2)
win32clipboard.OpenClipboard()
print("portapapeles texto:", repr(win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)))
win32clipboard.CloseClipboard()

# varias juntas: una sola tanda
for n in range(3):
    mandar(b.getvalue(), f"tanda {n}.jpg")
time.sleep(1.3)
win32clipboard.OpenClipboard()
print("tanda en portapapeles:", len(win32clipboard.GetClipboardData(win32con.CF_HDROP)))
win32clipboard.CloseClipboard()
h, r = ventana_aviso()
ImageGrab.grab(bbox=r, all_screens=True).save(AQUI / "pc_tanda.png")

# pegado solo: reinicia con la opción prendida
p.kill(); p.wait(); time.sleep(0.5)
(DATOS / "ajustes.txt").write_text("pegar=1\nsonido=0\n")
p = subprocess.Popen([EXE], env=entorno); time.sleep(2)
marca = AQUI / "pc_pegado.txt"; marca.unlink(missing_ok=True)
codigo = ("import tkinter as tk\nr=tk.Tk(); r.title('escribiendo'); r.geometry('300x100+200+200')\n"
          f"r.bind('<Control-v>', lambda e: open(r'{marca}','w').write('pego'))\n"
          "r.after(100,r.focus_force); r.after(7000,r.destroy); r.mainloop()\n")
t = subprocess.Popen([sys.executable, "-c", codigo]); time.sleep(2)
print("foreground:", win32gui.GetWindowText(win32gui.GetForegroundWindow()))
print("con pegado solo:", mandar(b.getvalue(), "pegada.jpg"))
time.sleep(2)
print("Ctrl+V llegó a la ventana activa:", marca.exists())
t.wait()

# desvincular: el token deja de valer
(DATOS / "dispositivos.txt").write_text("")
p.kill(); p.wait(); time.sleep(0.5)
p = subprocess.Popen([EXE, "--oculto"], env=entorno); time.sleep(2)
print("sin vínculo:", pedir("GET", "/hola", **AUT)[0], "| aún arranca oculto:", p.poll() is None)
win32gui.GetForegroundWindow()
p.kill()
print("recibidos:", [f.name for f in (DATOS / "recibidos").iterdir()])
win32clipboard.OpenClipboard(); win32clipboard.EmptyClipboard(); win32clipboard.CloseClipboard()
print("Run key real sin tocar:", end=" ")
import winreg
try:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as k:
        print(winreg.QueryValueEx(k, "Tachan")[0])
except FileNotFoundError:
    print("sí")
