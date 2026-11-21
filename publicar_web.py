"""Publica web/ en kvothesson.com/tachan: escribe version.json, sube las descargas y sube el commit.

GitHub despliega la carpeta web/ cuando el cambio llega a main (.github/workflows/web.yml).
Solo commitea web/: el resto del repo se commitea aparte.
python publicar_web.py "mensaje del commit"
"""
import hashlib
import json
import re
import subprocess
import sys
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
    archivos = [WEB / "Tachan.exe", WEB / "tachan.apk"]
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


generar()
manifiesto = (WEB.parent / "android" / "AndroidManifest.xml").read_text(encoding="utf-8")
codigo = int(re.search(r'versionCode="(\d+)"', manifiesto)[1])
sha256 = hashlib.sha256((WEB / "Tachan.exe").read_bytes()).hexdigest()
(WEB / "version.json").write_text(json.dumps({
    "codigo": codigo,
    "nombre": re.search(r'versionName="([^"]+)"', manifiesto)[1],
    "exe_sha256": sha256,
    "firma": firmar(codigo, sha256),
}, indent=2), encoding="utf-8")
release(re.search(r'versionName="([^"]+)"', manifiesto)[1])
git("add", "web")
if subprocess.run(["git", "-C", str(RAIZ), "diff", "--cached", "--quiet", "--", "web"]).returncode:
    mensaje = sys.argv[1] if len(sys.argv) > 1 else "Actualiza la web de Tachán"
    git(*IDENTIDAD, "commit", "-q", "-m", mensaje + "\n\nCo-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>", "--", "web")
git("push", "-q", "origin", "main")
print("subido: la web se despliega sola en uno o dos minutos (gh run list -w web.yml)")
