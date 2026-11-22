"""Buscar actualización en Mac, de punta a punta, con una llave de prueba. TOCA LA INSTALACIÓN REAL (~/Applications/Tachan.app).

Compila dos apps con la parte pública de una llave nueva, instala la vieja, sirve version.json y el zip desde una web
local y aprieta "Buscar actualización" (--buscar-actualizacion). Primero con una firma falsa, que no tiene que instalar
nada; después con la buena, que tiene que reemplazar la instalada sin tocar los datos. Al final reinstala
mac/compilado/Tachan.app (la de la llave real), así que conviene compilarla antes con mac/compilar.py.
"""
import base64, hashlib, http.server, json, os, shutil, subprocess, sys, tempfile, threading, time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
INSTALADA = Path.home() / "Applications" / "Tachan.app"
DATOS = Path.home() / "Library" / "Application Support" / "Tachan"
T = Path(tempfile.mkdtemp(prefix="tachan_actualizar_"))


def correr(*a, **k):
    return subprocess.run([str(x) for x in a], check=True, capture_output=True, **k)


def procesos():
    r = subprocess.run(["pgrep", "-f", "MacOS/Tachan"], capture_output=True, text=True)
    return [int(x) for x in r.stdout.split()]


def cerrar_todo():
    for p in procesos():
        os.kill(p, 15)
    time.sleep(1.5)


def ejecutable(app):
    return (app / "Contents" / "MacOS" / "Tachan").read_bytes()


# Llave de prueba: el openssl del sistema. Nunca la real, que vive en Windows.
correr("/usr/bin/openssl", "genrsa", "-out", T / "llave.pem", "3072")
modulo_hex = correr("/usr/bin/openssl", "rsa", "-in", T / "llave.pem", "-noout", "-modulus", text=True).stdout.strip().split("=")[1]
modulo = base64.b64encode(bytes.fromhex(modulo_hex)).decode()

for nombre in ("vieja", "nueva"):
    print("compilando", nombre, "…")
    correr(sys.executable, REPO / "mac" / "compilar.py", "--salida", T / nombre, "--llave-prueba", modulo)
# La misma fuente da los mismos bytes: la nueva lleva otra firma ad hoc para contar como otra versión.
correr("codesign", "--force", "-s", "-", "--options", "runtime", "--timestamp=none", T / "nueva" / "Tachan.app")
web = T / "web"; web.mkdir()
correr("ditto", "-c", "-k", "--keepParent", "--norsrc", T / "nueva" / "Tachan.app", web / "actualizar-Tachan-mac.zip")
sha = hashlib.sha256((web / "actualizar-Tachan-mac.zip").read_bytes()).hexdigest()
(T / "mensaje.txt").write_bytes(f"99\n{sha}".encode())
firma = base64.b64encode(correr("/usr/bin/openssl", "dgst", "-sha256", "-sign", T / "llave.pem", T / "mensaje.txt").stdout).decode()


def publicar(f):
    # Los campos de Windows van igual, para ver que conviven.
    (web / "version.json").write_text(json.dumps({"codigo": 99, "nombre": "prueba", "exe_sha256": "0" * 64, "firma": "AAAA",
                                                   "mac_sha256": sha, "firma_mac": f}, indent=2))


class Silencioso(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=str(web), **k)
    def log_message(self, *a): pass


servidor = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Silencioso)
threading.Thread(target=servidor.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{servidor.server_address[1]}/"

identidad = hashlib.sha256((DATOS / "identidad.p12").read_bytes()).hexdigest() if (DATOS / "identidad.p12").exists() else None
fallas = 0


def chequear(que, bien):
    global fallas
    print(("OK    " if bien else "FALLA ") + que)
    fallas += not bien


def buscar():
    """Abre la instalada como lo haría el inicio de sesión y le pide buscar actualización."""
    correr("open", "-n", "--env", f"TACHAN_ACTUALIZAR={base}", INSTALADA, "--args", "--oculto", "--buscar-actualizacion")


try:
    cerrar_todo()
    # Instala la vieja: abrirla fuera de ~/Applications la copia sola.
    correr("open", "-n", T / "vieja" / "Tachan.app", "--args", "--oculto")
    time.sleep(5)
    chequear("la vieja quedó instalada", ejecutable(INSTALADA) == ejecutable(T / "vieja" / "Tachan.app"))
    cerrar_todo()

    publicar(base64.b64encode(b"x" * 384).decode())
    buscar()
    time.sleep(8)
    chequear("con firma falsa no instala nada", ejecutable(INSTALADA) == ejecutable(T / "vieja" / "Tachan.app"))
    cerrar_todo()

    publicar(firma)
    buscar()
    for _ in range(40):
        time.sleep(0.5)
        if ejecutable(INSTALADA) == ejecutable(T / "nueva" / "Tachan.app") and procesos(): break
    time.sleep(3)
    chequear("con la firma buena se reemplaza", ejecutable(INSTALADA) == ejecutable(T / "nueva" / "Tachan.app"))
    chequear("queda una sola corriendo", len(procesos()) == 1)
    if identidad:
        chequear("los datos no se tocan", hashlib.sha256((DATOS / "identidad.p12").read_bytes()).hexdigest() == identidad)
finally:
    servidor.shutdown()
    cerrar_todo()
    # Vuelve a la de la llave real.
    real = REPO / "mac" / "compilado" / "Tachan.app"
    if real.exists():
        correr("open", "-n", real, "--args", "--oculto")
        time.sleep(5)
        print("reinstalada la de mac/compilado:", ejecutable(INSTALADA) == ejecutable(real))
    shutil.rmtree(T, ignore_errors=True)
print("TODO BIEN" if fallas == 0 else f"FALLAS: {fallas}")
sys.exit(1 if fallas else 0)
