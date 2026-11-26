"""La portada sale en un idioma por página: web/index.html solo en castellano y web/en.html solo en inglés.

Falla si una trae texto del otro idioma o si quedaron viejas respecto de portada.html (falta correr generar_portada.py).
python pruebas/prueba_web.py
"""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from generar_portada import FUENTE, castellano, ingles

WEB = REPO / "web"
sys.stdout.reconfigure(encoding="utf-8")
fallas = []


def con_lang(html, idioma):
    """Elementos con lang="<idioma>", sin contar los hreflang de los links ni la etiqueta <html>."""
    return re.findall(r'<(?!html\b)\w+[^>]*\slang="%s"' % idioma, html)


fuente = FUENTE.read_text(encoding="utf-8")
paginas = {"index.html": ("es", "en", castellano(fuente)), "en.html": ("en", "es", ingles(fuente))}
for nombre, (propio, ajeno, esperado) in paginas.items():
    html = (WEB / nombre).read_text(encoding="utf-8")
    if f'<html lang="{propio}">' not in html:
        fallas.append(f'{nombre}: no dice <html lang="{propio}">')
    if con_lang(html, ajeno):
        fallas.append(f'{nombre}: trae texto lang="{ajeno}": {con_lang(html, ajeno)[:3]}')
    if f'html:lang(' in html:
        fallas.append(f"{nombre}: todavía esconde un idioma con CSS")
    if html != esperado:
        fallas.append(f"{nombre}: no está al día con portada.html, correr python generar_portada.py")

index = (WEB / "index.html").read_text(encoding="utf-8")
for palabra in ("Download for", "Link your phone", "Questions"):
    if palabra in index:
        fallas.append(f"index.html: trae '{palabra}'")
en = (WEB / "en.html").read_text(encoding="utf-8")
for palabra in ("Bajar para", "Vinculá", "Preguntas"):
    if palabra in en:
        fallas.append(f"en.html: trae '{palabra}'")
# Del QR con el navegador en otro idioma, index.html manda a en.html con el código; en.html nunca devuelve.
if 'location.replace("en.html" + location.hash)' not in index:
    fallas.append("index.html: falta mandar el QR a en.html")
if "location.replace" in en:
    fallas.append("en.html: redirige, puede armar una vuelta")
if (WEB / "portada.html").exists():
    fallas.append("web/portada.html no se tiene que publicar")

print("\n".join(fallas) or "web: un idioma por página, OK")
sys.exit(1 if fallas else 0)
