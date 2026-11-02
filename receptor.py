"""Recibe fotos del celu por la red de casa y las deja a mano en la compu.

Cada foto se guarda en Imagenes/Del celu, queda copiada para pegar con Ctrl+V
y aparece en una ventanita de la que se puede arrastrar.
"""
import ctypes
import hmac
import io
import json
import os
import queue
import re
import secrets
import socket
import struct
import sys
import threading
import time
import tkinter as tk
import urllib.parse
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import win32api
import win32clipboard
import win32con
import win32gui
import win32process
from PIL import Image, ImageOps, ImageTk

AQUI = Path(__file__).resolve().parent
CONFIG = AQUI / "config.json"
PAGINA = AQUI / "pagina.html"
APK = AQUI / "android" / "mandar-a-la-compu.apk"
DESTINO = Path.home() / "Pictures" / "Del celu"
PUERTO = 7780
MAXIMO_BYTES = 500 * 1024 * 1024
MINIATURAS = 6
LADO_MINIATURA = 130
ESPERA_TANDA_MS = 700  # las fotos que llegan juntas se copian juntas


def leer_config():
    config = {"token": None, "pegar_solo": False}
    if CONFIG.exists():
        config.update(json.loads(CONFIG.read_text(encoding="utf-8")))
    if not config["token"]:
        config["token"] = secrets.token_hex(4)
        guardar_config(config)
    return config


def guardar_config(config):
    CONFIG.write_text(json.dumps(config, indent=2), encoding="utf-8")


def ip_local():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("192.0.2.1", 9))  # no manda nada: solo elige la placa de red
        return s.getsockname()[0]


def nombre_seguro(crudo):
    nombre = Path(urllib.parse.unquote(crudo or "").replace("\\", "/")).name
    nombre = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", nombre).strip(" .")
    return nombre[:120] or time.strftime("foto_%Y%m%d_%H%M%S.jpg")


def ruta_libre(nombre):
    ruta = DESTINO / nombre
    n = 2
    while ruta.exists():
        ruta = DESTINO / f"{Path(nombre).stem}_{n}{Path(nombre).suffix}"
        n += 1
    return ruta


class Receptor(BaseHTTPRequestHandler):
    token = ""
    llegadas = None
    mostrar = None

    def log_message(self, *_):
        pass

    def responder(self, codigo, cuerpo, tipo="application/json"):
        datos = cuerpo.encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def autorizado(self):
        url = urllib.parse.urlparse(self.path)
        dado = self.headers.get("X-Token") or urllib.parse.parse_qs(url.query).get("t", [""])[0]
        return hmac.compare_digest(dado.encode(), self.token.encode())

    def do_GET(self):
        ruta = urllib.parse.urlparse(self.path).path
        if not self.autorizado():
            self.responder(403, '{"ok":false}')
        elif ruta == "/mostrar":
            self.mostrar()
            self.responder(200, '{"ok":true}')
        elif ruta == "/app.apk" and APK.exists():
            datos = APK.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/vnd.android.package-archive")
            self.send_header("Content-Disposition", 'attachment; filename="mandar-a-la-compu.apk"')
            self.send_header("Content-Length", str(len(datos)))
            self.end_headers()
            self.wfile.write(datos)
        else:
            self.responder(200, PAGINA.read_text(encoding="utf-8"), "text/html; charset=utf-8")

    def do_POST(self):
        self.close_connection = True
        if not self.autorizado():
            self.responder(403, '{"ok":false}')
            return
        try:
            largo = int(self.headers.get("Content-Length", ""))
        except ValueError:
            self.responder(411, '{"ok":false}')
            return
        if not 0 < largo <= MAXIMO_BYTES:
            self.responder(413, '{"ok":false}')
            return
        DESTINO.mkdir(parents=True, exist_ok=True)
        parcial = DESTINO / f".recibiendo_{secrets.token_hex(6)}"
        try:
            with open(parcial, "wb") as f:
                restante = largo
                while restante:
                    trozo = self.rfile.read(min(1024 * 1024, restante))
                    if not trozo:
                        raise ConnectionError("se corto el envio")
                    f.write(trozo)
                    restante -= len(trozo)
            ruta = ruta_libre(nombre_seguro(self.headers.get("X-Nombre")))
            parcial.rename(ruta)
        finally:
            parcial.unlink(missing_ok=True)
        self.llegadas.put(ruta)
        self.responder(200, json.dumps({"ok": True, "nombre": ruta.name}))


def abrir_imagen(ruta):
    """La foto derecha, o None si PIL no la entiende (HEIC, video)."""
    try:
        with Image.open(ruta) as im:
            return ImageOps.exif_transpose(im).convert("RGB")
    except Exception:
        return None


def copiar(rutas):
    """Deja las rutas como archivos y la ultima imagen como dibujo: sirve en cualquier programa."""
    imagen = next((im for im in map(abrir_imagen, reversed(rutas)) if im), None)
    dib = None
    if imagen:
        salida = io.BytesIO()
        imagen.save(salida, "BMP")
        dib = salida.getvalue()[14:]
    lista = "\0".join(str(r) for r in rutas) + "\0\0"
    archivos = struct.pack("<IiiII", 20, 0, 0, 0, 1) + lista.encode("utf-16-le")
    for _ in range(10):  # otro programa puede tener el portapapeles abierto
        try:
            win32clipboard.OpenClipboard()
            break
        except Exception:
            time.sleep(0.05)
    else:
        return False
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_HDROP, archivos)
        if dib:
            win32clipboard.SetClipboardData(win32con.CF_DIB, dib)
    finally:
        win32clipboard.CloseClipboard()
    return True


def apretar_ctrl_v():
    win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
    win32api.keybd_event(ord("V"), 0, 0, 0)
    win32api.keybd_event(ord("V"), 0, win32con.KEYEVENTF_KEYUP, 0)
    win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)


# El arrastre va directo contra Windows: el DoDragDrop de pywin32 revienta el proceso.
HRESULT = ctypes.c_long
_E_NOINTERFACE, _DRAGDROP_S_DROP, _DRAGDROP_S_CANCEL, _DRAGDROP_S_USEDEFAULTCURSORS = (
    ctypes.c_long(0x80004002).value, 0x00040100, 0x00040101, 0x00040102)
_DROPEFFECT_COPY, _MK_LBUTTON = 1, 1
_ole32 = ctypes.WinDLL("ole32")
_shell32 = ctypes.WinDLL("shell32")
_IID_IDataObject = (ctypes.c_byte * 16).from_buffer_copy(uuid.UUID("0000010e-0000-0000-c000-000000000046").bytes_le)
_IID_IUnknown = uuid.UUID("00000000-0000-0000-c000-000000000046").bytes_le
_IID_IDropSource = uuid.UUID("00000121-0000-0000-c000-000000000046").bytes_le
_shell32.SHParseDisplayName.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p),
                                        ctypes.c_ulong, ctypes.c_void_p]
_shell32.SHParseDisplayName.restype = HRESULT
_shell32.SHCreateDataObject.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p),
                                        ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
_shell32.SHCreateDataObject.restype = HRESULT
_ole32.DoDragDrop.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong)]
_ole32.DoDragDrop.restype = HRESULT
_shell32.ILFindLastID.argtypes = [ctypes.c_void_p]
_shell32.ILFindLastID.restype = ctypes.c_void_p
_ole32.OleInitialize.argtypes = [ctypes.c_void_p]
_ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]


class _OrigenArrastre(ctypes.Structure):
    _fields_ = [("tabla", ctypes.c_void_p)]


@ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))
def _query_interface(este, iid, salida):
    if ctypes.string_at(iid, 16) in (_IID_IUnknown, _IID_IDropSource):
        salida[0] = este
        return 0
    salida[0] = None
    return _E_NOINTERFACE


@ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)
def _una_referencia(_este):
    return 1  # vive todo el programa


@ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, ctypes.c_int, ctypes.c_ulong)
def _seguir_arrastrando(_este, escape, teclas):
    if escape:
        return _DRAGDROP_S_CANCEL
    # El estado de "teclas" llega viejo desde otro hilo: se le pregunta a Windows directo.
    return 0 if win32api.GetAsyncKeyState(win32con.VK_LBUTTON) & 0x8000 else _DRAGDROP_S_DROP


@ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, ctypes.c_ulong)
def _cursor(_este, _efecto):
    return _DRAGDROP_S_USEDEFAULTCURSORS


_tabla = (ctypes.c_void_p * 5)(*[ctypes.cast(f, ctypes.c_void_p) for f in
                                 (_query_interface, _una_referencia, _una_referencia,
                                  _seguir_arrastrando, _cursor)])
_origen = _OrigenArrastre(ctypes.cast(_tabla, ctypes.c_void_p))


def arrastrar(ruta, hilo_ventana):
    # En su propio hilo para que la ventana no se trabe mientras dura el arrastre.
    hilo = win32api.GetCurrentThreadId()
    _ole32.OleInitialize(None)
    win32process.AttachThreadInput(hilo, hilo_ventana, True)  # para heredar el mouse apretado
    pidl = ctypes.c_void_p()
    pidl_carpeta = ctypes.c_void_p()
    datos = ctypes.c_void_p()
    try:
        if _shell32.SHParseDisplayName(str(ruta), None, ctypes.byref(pidl), 0, None) < 0:
            return
        if _shell32.SHParseDisplayName(str(ruta.parent), None, ctypes.byref(pidl_carpeta), 0, None) < 0:
            return
        hijo = ctypes.c_void_p(_shell32.ILFindLastID(pidl))
        if _shell32.SHCreateDataObject(pidl_carpeta, 1, ctypes.byref(hijo), None, ctypes.byref(_IID_IDataObject),
                                       ctypes.byref(datos)) < 0:
            return
        efecto = ctypes.c_ulong()
        _ole32.DoDragDrop(datos, ctypes.byref(_origen), _DROPEFFECT_COPY, ctypes.byref(efecto))
    finally:
        _ole32.CoTaskMemFree(pidl)
        _ole32.CoTaskMemFree(pidl_carpeta)
        win32process.AttachThreadInput(hilo, hilo_ventana, False)
        _ole32.OleUninitialize()


class Ventana:
    FONDO = "#1f2125"
    TEXTO = "#e8e8e8"
    TENUE = "#9a9da3"

    def __init__(self, config, link, llegadas, oculto):
        self.config = config
        self.llegadas = llegadas
        self.recientes = []
        self.tanda = []
        self.espera = None
        self.fotos_tk = []
        self.root = tk.Tk()
        self.root.title("Del celu")
        self.root.configure(bg=self.FONDO, padx=12, pady=10)
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)
        self.root.protocol("WM_DELETE_WINDOW", self.root.withdraw)

        self.aviso = tk.Label(self.root, bg=self.FONDO, fg=self.TEXTO, font=("Segoe UI", 11, "bold"),
                              text="Esperando fotos del celu", anchor="w", justify="left")
        self.aviso.pack(fill="x")
        self.detalle = tk.Label(self.root, bg=self.FONDO, fg=self.TENUE, font=("Segoe UI", 9),
                                text=f"Para mandar sin app, abrí en el celu:\n{link}",
                                anchor="w", justify="left")
        self.detalle.pack(fill="x", pady=(2, 8))
        self.grilla = tk.Frame(self.root, bg=self.FONDO)
        self.grilla.pack(fill="x")

        pie = tk.Frame(self.root, bg=self.FONDO)
        pie.pack(fill="x", pady=(8, 0))
        self.pegar_solo = tk.BooleanVar(value=config["pegar_solo"])
        tk.Checkbutton(pie, text="Pegar solo donde estoy", variable=self.pegar_solo,
                       command=self.cambiar_pegado, bg=self.FONDO, fg=self.TEXTO,
                       selectcolor=self.FONDO, activebackground=self.FONDO,
                       activeforeground=self.TEXTO, font=("Segoe UI", 9)).pack(side="left")
        for texto, accion in (("Apagar", self.root.destroy),
                              ("Abrir carpeta", self.abrir_carpeta)):
            tk.Button(pie, text=texto, command=accion, relief="flat", bg="#33363c", fg=self.TEXTO,
                      activebackground="#44474e", activeforeground=self.TEXTO, padx=8,
                      font=("Segoe UI", 9)).pack(side="right", padx=(6, 0))

        self.root.update_idletasks()
        self.no_robar_foco()
        if oculto:
            self.root.withdraw()
        else:
            self.acomodar()
        self.root.after(200, self.revisar)

    def no_robar_foco(self):
        # La ventana aparece encima sin sacarte de donde estás escribiendo.
        hwnd = win32gui.GetParent(self.root.winfo_id())
        estilo = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE,
                               estilo | win32con.WS_EX_NOACTIVATE | win32con.WS_EX_TOOLWINDOW)

    def acomodar(self):
        foco = win32gui.GetForegroundWindow()
        self.root.deiconify()
        self.root.update_idletasks()
        ancho, alto = self.root.winfo_reqwidth(), self.root.winfo_reqheight()
        x = self.root.winfo_screenwidth() - ancho - 24
        y = self.root.winfo_screenheight() - alto - 90
        self.root.geometry(f"+{x}+{y}")
        self.root.update()
        if foco and win32gui.GetForegroundWindow() != foco:
            win32gui.SetForegroundWindow(foco)

    def mostrar(self):
        self.root.after(0, self.acomodar)

    def revisar(self):
        nuevas = False
        try:
            while True:
                ruta = self.llegadas.get_nowait()
                self.tanda.append(ruta)
                self.recientes.insert(0, ruta)
                nuevas = True
        except queue.Empty:
            pass
        if nuevas:
            del self.recientes[MINIATURAS:]
            if self.espera:
                self.root.after_cancel(self.espera)
            self.espera = self.root.after(ESPERA_TANDA_MS, self.entregar)
        self.root.after(200, self.revisar)

    def entregar(self):
        tanda, self.tanda, self.espera = self.tanda, [], None
        copiada = copiar(tanda)
        cuantas = "La foto llegó" if len(tanda) == 1 else f"Llegaron {len(tanda)} fotos"
        if not copiada:
            self.avisar(f"{cuantas}, pero no pude copiarla", "Hacé clic en la foto para reintentar")
        elif self.pegar_solo.get():
            apretar_ctrl_v()
            self.avisar(f"{cuantas} y la pegué", "También podés arrastrarla desde acá")
        else:
            self.avisar(f"{cuantas}: Ctrl+V para pegar", "O arrastrala desde acá")
        self.dibujar_miniaturas()
        self.acomodar()

    def avisar(self, aviso, detalle):
        self.aviso.configure(text=aviso)
        self.detalle.configure(text=detalle)

    def dibujar_miniaturas(self):
        for hijo in self.grilla.winfo_children():
            hijo.destroy()
        self.fotos_tk = []
        for i, ruta in enumerate(self.recientes):
            imagen = abrir_imagen(ruta)
            if imagen:
                imagen.thumbnail((LADO_MINIATURA, LADO_MINIATURA))
                foto = ImageTk.PhotoImage(imagen)
                self.fotos_tk.append(foto)
                celda = tk.Label(self.grilla, image=foto, bg=self.FONDO, cursor="hand2")
            else:
                celda = tk.Label(self.grilla, text=ruta.name, wraplength=LADO_MINIATURA - 10,
                                 bg="#33363c", fg=self.TEXTO, cursor="hand2", width=16, height=7,
                                 font=("Segoe UI", 8))
            celda.grid(row=i // 3, column=i % 3, padx=3, pady=3)
            self.conectar(celda, ruta)

    def conectar(self, celda, ruta):
        estado = {"x": 0, "y": 0, "arrastrada": False}

        def apretar(e):
            estado.update(x=e.x_root, y=e.y_root, arrastrada=False)

        def mover(e):
            if not estado["arrastrada"] and max(abs(e.x_root - estado["x"]), abs(e.y_root - estado["y"])) > 6:
                estado["arrastrada"] = True
                # tkinter queda quieto hasta soltar: si sigue andando le saca el mouse al arrastre.
                hilo = threading.Thread(target=arrastrar, args=(ruta, win32api.GetCurrentThreadId()), daemon=True)
                hilo.start()
                hilo.join()

        def soltar(_):
            if not estado["arrastrada"] and copiar([ruta]):
                self.avisar("Copiada: Ctrl+V para pegar", ruta.name)

        celda.bind("<ButtonPress-1>", apretar)
        celda.bind("<B1-Motion>", mover)
        celda.bind("<ButtonRelease-1>", soltar)
        celda.bind("<Double-Button-1>", lambda _: os.startfile(ruta))

    def cambiar_pegado(self):
        self.config["pegar_solo"] = self.pegar_solo.get()
        guardar_config(self.config)

    def abrir_carpeta(self):
        DESTINO.mkdir(parents=True, exist_ok=True)
        os.startfile(DESTINO)


def main():
    oculto = "--oculto" in sys.argv
    config = leer_config()
    llegadas = queue.Queue()
    Receptor.token = config["token"]
    Receptor.llegadas = llegadas
    try:
        servidor = ThreadingHTTPServer(("0.0.0.0", PUERTO), Receptor)
    except OSError:
        # Ya está prendido: alcanza con volver a mostrar su ventana.
        if not oculto:
            urllib.request.urlopen(f"http://127.0.0.1:{PUERTO}/mostrar?t={config['token']}", timeout=3)
        return
    link = f"http://{ip_local()}:{PUERTO}/?t={config['token']}"
    ventana = Ventana(config, link, llegadas, oculto)
    Receptor.mostrar = ventana.mostrar
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    ventana.root.mainloop()
    servidor.shutdown()


if __name__ == "__main__":
    main()
