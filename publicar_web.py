"""Copia web/ al repo público kvothesson/tachan, el único que sirve kvothesson.com/tachan, y lo sube.

El código sigue en el repo privado kvothesson/tachan-app.
python publicar_web.py "mensaje del commit"
"""
import shutil
import subprocess
import sys
from pathlib import Path

WEB = Path(__file__).resolve().parent / "web"
PUBLICO = Path(r"D:\repos\tachan-web")
SALVAR = {".git", "README.md", ".nojekyll"}
IDENTIDAD = ["-c", "user.email=46162626+kvothesson@users.noreply.github.com", "-c", "user.name=Kvothesson"]


def git(*a):
    subprocess.run(["git", "-C", str(PUBLICO), *a], check=True)


for viejo in PUBLICO.iterdir():
    if viejo.name not in SALVAR:
        viejo.unlink()
for nuevo in WEB.iterdir():
    shutil.copy(nuevo, PUBLICO / nuevo.name)
git("add", "-A")
if subprocess.run(["git", "-C", str(PUBLICO), "diff", "--cached", "--quiet"]).returncode:
    mensaje = sys.argv[1] if len(sys.argv) > 1 else "Actualiza la web de Tachán"
    git(*IDENTIDAD, "commit", "-q", "-m", mensaje + "\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>")
    git("push", "-q", "origin", "main")
print("publicado")
