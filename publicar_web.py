"""Copia web/ al repo público kvothesson/tachan, el único que sirve kvothesson.com/tachan, y lo sube.

El código está en kvothesson/tachan-app.
python publicar_web.py "mensaje del commit"
"""
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from firmar import firmar
from generar_en import generar

WEB = Path(__file__).resolve().parent / "web"
PUBLICO = Path(r"D:\repos\tachan-web")  # copia local de kvothesson/tachan
SALVAR = {".git", "README.md", ".nojekyll"}
IDENTIDAD = ["-c", "user.email=46162626+kvothesson@users.noreply.github.com", "-c", "user.name=Kvothesson"]


def git(*a):
    subprocess.run(["git", "-C", str(PUBLICO), *a], check=True)


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
for viejo in PUBLICO.iterdir():
    if viejo.name not in SALVAR:
        viejo.unlink()
for nuevo in WEB.iterdir():
    shutil.copy(nuevo, PUBLICO / nuevo.name)
git("add", "-A")
if subprocess.run(["git", "-C", str(PUBLICO), "diff", "--cached", "--quiet"]).returncode:
    mensaje = sys.argv[1] if len(sys.argv) > 1 else "Actualiza la web de Tachán"
    git(*IDENTIDAD, "commit", "-q", "-m", mensaje + "\n\nCo-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>")
    git("push", "-q", "origin", "main")
print("publicado")
