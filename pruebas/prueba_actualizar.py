"""Actualiza el programa instalado de verdad: abre otra compilación con la actual prendida y mira que la reemplace sin perder datos.

Toca la instalación real de esta compu. Pasa dos compilaciones por argumento."""
import hashlib, os, shutil, subprocess, sys, tempfile, time
from pathlib import Path
import psutil

DEST = Path(os.environ["LOCALAPPDATA"]) / "Programs" / "Tachan" / "Tachan.exe"
DATOS = Path(os.environ["APPDATA"]) / "Tachan" / "dispositivos.txt"


def huella(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:12]


def corriendo():
    return [(p.pid, p.exe()) for p in psutil.process_iter(["name"]) if p.info["name"] == "Tachan.exe"]


def abrir(origen):
    temp = Path(tempfile.mkdtemp()) / "Tachan.exe"
    shutil.copy(origen, temp)
    subprocess.Popen([temp, "--oculto"])
    time.sleep(6)


primera, segunda = sys.argv[1:3]
assert huella(primera) != huella(segunda), "las dos compilaciones son iguales"
vinculos = DATOS.read_text(encoding="utf-8")
for p in psutil.process_iter(["name"]):
    if p.info["name"] == "Tachan.exe": p.kill()
time.sleep(1)
abrir(primera)
antes = corriendo()
print("instalada la primera:", huella(DEST) == huella(primera), antes)
abrir(primera)
print("la misma versión no reinicia:", corriendo() == antes)
abrir(segunda)
ahora = corriendo()
print("actualizada a la segunda:", huella(DEST) == huella(segunda))
print("corre una sola, desde su carpeta, con proceso nuevo:", len(ahora) == 1 and Path(ahora[0][1]) == DEST and ahora[0][0] != antes[0][0], ahora)
print("vínculos intactos:", DATOS.read_text(encoding="utf-8") == vinculos)
