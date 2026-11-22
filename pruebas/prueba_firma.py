"""Buscar actualización contra una web local, con datos aislados: solo baja el programa si la firma es de nuestra llave.

No toca la instalación real. Mira si se pidió el exe: sin firma válida ni se baja."""
import hashlib, http.server, json, os, socketserver, subprocess, sys, tempfile, threading, time
from functools import partial
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from firmar import crear, firmar

EXE = REPO / "pc" / "compilado" / "Tachan.exe"
SITIO = Path(tempfile.mkdtemp())
PUERTO = 8098
pedidos = []


class Registra(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        pedidos.append(self.path.split("?")[0])
        super().do_GET()


servidor = socketserver.ThreadingTCPServer(("127.0.0.1", PUERTO), partial(Registra, directory=str(SITIO)))
threading.Thread(target=servidor.serve_forever, daemon=True).start()
(SITIO / "actualizar-Tachan.exe").write_bytes(EXE.read_bytes())
sha = hashlib.sha256(EXE.read_bytes()).hexdigest()
ajena = SITIO.parent / ("ajena_" + SITIO.name + ".pem")
crear(ajena)


def probar(version):
    (SITIO / "version.json").write_text(json.dumps(version), encoding="utf-8")
    pedidos.clear()
    datos = tempfile.mkdtemp()
    entorno = dict(os.environ, TACHAN_DATOS=datos, TACHAN_PUERTO="47960", TACHAN_ACTUALIZAR=f"http://127.0.0.1:{PUERTO}/")
    p = subprocess.Popen([EXE, "--oculto", "--buscar-actualizacion"], env=entorno)
    time.sleep(6)
    vivo = p.poll() is None
    p.kill()
    p.wait()
    time.sleep(.5)
    return "/actualizar-Tachan.exe" in pedidos, vivo


casos = [
    ("sin firma", {"codigo": 99, "nombre": "x", "exe_sha256": sha}, False),
    ("firma de otra llave", {"codigo": 99, "nombre": "x", "exe_sha256": sha, "firma": firmar(99, sha, ajena)}, False),
    ("firma de otra versión", {"codigo": 99, "nombre": "x", "exe_sha256": sha, "firma": firmar(98, sha)}, False),
    ("firma de otro programa", {"codigo": 99, "nombre": "x", "exe_sha256": "0" * 64, "firma": firmar(99, sha)}, False),
    ("firma rota", {"codigo": 99, "nombre": "x", "exe_sha256": sha, "firma": "AAAA"}, False),
    ("firma nuestra", {"codigo": 99, "nombre": "x", "exe_sha256": sha, "firma": firmar(99, sha)}, True),
]
fallas = 0
for nombre, version, baja in casos:
    bajo, vivo = probar(version)
    bien = bajo == baja and vivo
    fallas += not bien
    print("OK   " if bien else "FALLA", nombre, "| bajó el exe:", bajo, "| programa vivo:", vivo)
ajena.unlink()
servidor.shutdown()
print("TODO BIEN" if not fallas else f"FALLAS: {fallas}")
