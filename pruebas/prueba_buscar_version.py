"""Prueba Buscar actualización contra una web local: sin novedades, con una descarga dañada y con una versión nueva.

Toca la instalación real de esta compu y la deja actualizada a la compilación que se pasa como segundo argumento.
Uso: prueba_buscar_version.py <exe_prendido> <exe_nuevo>"""
import hashlib, http.server, json, os, shutil, socketserver, subprocess, sys, tempfile, threading, time
from functools import partial
from pathlib import Path
import psutil

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from firmar import firmar

DEST = Path(os.environ["LOCALAPPDATA"]) / "Programs" / "Tachan" / "Tachan.exe"
VINCULOS = Path(os.environ["APPDATA"]) / "Tachan" / "dispositivos.txt"
SITIO = Path(tempfile.mkdtemp())
PUERTO = 8097


class Mudo(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass


socketserver.ThreadingTCPServer.allow_reuse_address = True
servidor = socketserver.ThreadingTCPServer(("127.0.0.1", PUERTO), partial(Mudo, directory=str(SITIO)))
threading.Thread(target=servidor.serve_forever, daemon=True).start()
base, nuevo = Path(sys.argv[1]), Path(sys.argv[2])
huella = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert huella(base) != huella(nuevo)
vinculos = VINCULOS.read_text(encoding="utf-8")
entorno = dict(os.environ, TACHAN_ACTUALIZAR=f"http://127.0.0.1:{PUERTO}/")


def corriendo():
    return [(p.pid, p.exe()) for p in psutil.process_iter(["name"]) if p.info["name"] == "Tachan.exe"]


def matar():
    for p in psutil.process_iter(["name"]):
        if p.info["name"] == "Tachan.exe": p.kill()
    time.sleep(1)


def preparar_instalada():
    matar()
    temp = Path(tempfile.mkdtemp()) / "Tachan.exe"
    shutil.copy(base, temp)
    subprocess.Popen([temp, "--oculto"]); time.sleep(4)
    assert huella(DEST) == huella(base)
    matar()


def buscar(codigo, sha):
    (SITIO / "version.json").write_text(json.dumps({"codigo": codigo, "nombre": "x", "exe_sha256": sha, "firma": firmar(codigo, sha)}), encoding="utf-8")
    subprocess.Popen([DEST, "--oculto", "--buscar-actualizacion"], env=entorno)
    time.sleep(8)


shutil.copy(nuevo, SITIO / "Tachan.exe")
preparar_instalada()
buscar(1, huella(nuevo))
print("sin novedades no cambia nada:", huella(DEST) == huella(base), len(corriendo()) == 1)
matar()
buscar(99, "0" * 64)
print("descarga dañada se rechaza:", huella(DEST) == huella(base), len(corriendo()) == 1)
antes = corriendo()
matar()
buscar(99, huella(nuevo))
ahora = corriendo()
print("con versión nueva se actualiza:", huella(DEST) == huella(nuevo))
print("queda una sola, desde su carpeta:", len(ahora) == 1 and Path(ahora[0][1]) == DEST, ahora)
print("vínculos intactos:", VINCULOS.read_text(encoding="utf-8") == vinculos)
servidor.shutdown()
