"""Publica web/ en kvothesson.com/tachan: escribe version.json, sube las descargas y sube el commit.

Se corre en Windows, donde están las llaves. El zip de Mac (web/Tachan-mac.zip) tiene que estar compilado en una Mac
con la misma versión del manifiesto: si no, no publica.

GitHub despliega la carpeta web/ cuando el cambio llega a main (.github/workflows/web.yml).
Solo commitea web/: el resto del repo se commitea aparte.
python publicar_web.py "mensaje del commit"
"""
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from firmar import firmar
from generar_en import generar

RAIZ = Path(__file__).resolve().parent
WEB = RAIZ / "web"
IDENTIDAD = ["-c", "user.email=46162626+kvothesson@users.noreply.github.com", "-c", "user.name=Kvothesson"]


def git(*a):
    subprocess.run(["git", "-C", str(RAIZ), *a], check=True)


def release(nombre):
    """Deja el exe y el APK en la release v<nombre> de kvothesson/tachan, de donde bajan los botones de la web.

    GitHub cuenta las descargas de cada archivo. Solo se vuelve a subir uno si cambió, porque al reemplazarlo
    su cuenta vuelve a cero. Va antes de subir la web, para que los botones nunca apunten a algo que no está.
    """
    tag = "v" + nombre
    # Las apps bajan la actualización de copias aparte (desde la 1.4): así su cuenta dice cuántos siguen usando
    # Tachán, sin mezclarse con quienes lo bajan de la web. Las copias de web/ quedan para las 1.3 instaladas.
    copias = Path(tempfile.mkdtemp())
    for f in ("Tachan.exe", "tachan.apk", "Tachan-mac.zip"):
        shutil.copy(WEB / f, copias / ("actualizar-" + f))
    archivos = [WEB / "Tachan.exe", WEB / "tachan.apk", WEB / "Tachan-mac.zip",
                copias / "actualizar-Tachan.exe", copias / "actualizar-tachan.apk", copias / "actualizar-Tachan-mac.zip"]
    hay = subprocess.run(["gh", "api", f"repos/kvothesson/tachan/releases/tags/{tag}"], capture_output=True, text=True)
    if hay.returncode:
        subprocess.run(["gh", "release", "create", tag, "-R", "kvothesson/tachan", "--title", f"Tachán {nombre}",
                        "--notes", "Descargas de Tachán. Cómo se instala y cómo comprobarlo: https://kvothesson.com/tachan/",
                        *map(str, archivos)], check=True)
        return
    subidos = {a["name"]: a.get("digest") for a in json.loads(hay.stdout)["assets"]}
    cambiados = [f for f in archivos if subidos.get(f.name) != "sha256:" + hashlib.sha256(f.read_bytes()).hexdigest()]
    if cambiados:
        subprocess.run(["gh", "release", "upload", tag, "-R", "kvothesson/tachan", "--clobber", *map(str, cambiados)], check=True)


def version_mac():
    """El zip de Mac se compila en una Mac (mac/compilar.py) y llega a esta compu por el repo, en web/Tachan-mac.zip."""
    with zipfile.ZipFile(WEB / "Tachan-mac.zip") as z:
        plist = z.read("Tachan.app/Contents/Info.plist").decode("utf-8")
    return int(re.search(r"<key>CFBundleVersion</key><string>(\d+)</string>", plist)[1])


generar()
manifiesto = (WEB.parent / "android" / "AndroidManifest.xml").read_text(encoding="utf-8")
codigo = int(re.search(r'versionCode="(\d+)"', manifiesto)[1])
# Si el zip de Mac es de otra versión, las Mac lo bajarían una y otra vez sin quedar nunca al día.
if version_mac() != codigo:
    sys.exit(f"web/Tachan-mac.zip es la versión {version_mac()} y el manifiesto dice {codigo}: compilalo en la Mac con python3 mac/compilar.py")
sha256 = hashlib.sha256((WEB / "Tachan.exe").read_bytes()).hexdigest()
sha256_mac = hashlib.sha256((WEB / "Tachan-mac.zip").read_bytes()).hexdigest()
# Windows lee exe_sha256 y firma con regex que no tocan los campos de Mac; el celu solo lee codigo y nombre.
(WEB / "version.json").write_text(json.dumps({
    "codigo": codigo,
    "nombre": re.search(r'versionName="([^"]+)"', manifiesto)[1],
    "exe_sha256": sha256,
    "firma": firmar(codigo, sha256),
    "mac_sha256": sha256_mac,
    "firma_mac": firmar(codigo, sha256_mac),
}, indent=2), encoding="utf-8")
release(re.search(r'versionName="([^"]+)"', manifiesto)[1])
git("add", "web")
if subprocess.run(["git", "-C", str(RAIZ), "diff", "--cached", "--quiet", "--", "web"]).returncode:
    mensaje = sys.argv[1] if len(sys.argv) > 1 else "Actualiza la web de Tachán"
    git(*IDENTIDAD, "commit", "-q", "-m", mensaje + "\n\nCo-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>", "--", "web")
git("push", "-q", "origin", "main")
print("subido: la web se despliega sola en uno o dos minutos (gh run list -w web.yml)")
