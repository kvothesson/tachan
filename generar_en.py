"""Arma web/en.html desde web/index.html, para que Google tenga una dirección por idioma.

python generar_en.py
"""
import re
from pathlib import Path

WEB = Path(__file__).resolve().parent / "web"
TITULO = "Tachán: transfer photos and files from Android to PC wirelessly"
DESCRIPCION = "Transfer photos, videos and files from your Android phone to your Windows PC or Mac wirelessly. Encrypted over your wifi, with no account and no servers."
AL_COMPARTIR = "Transfer photos, videos and files from your Android phone to your Windows PC or Mac wirelessly."
FICHA = "Transfer photos, videos, files and text from your Android phone to your Windows PC or Mac wirelessly. It arrives copied, ready to paste."


def generar():
    html = (WEB / "index.html").read_text(encoding="utf-8")

    def cambiar(patron, nuevo):
        # Si index.html cambió y un patrón ya no está, mejor frenar que publicar una página a medias.
        nonlocal html
        html, veces = re.subn(patron, lambda _: nuevo, html, flags=re.S)
        if not veces:
            raise SystemExit("generar_en: no encontré " + patron)

    cambiar(r'<html lang="es">', '<html lang="en">')
    cambiar(r"<title>.*?</title>", f"<title>{TITULO}</title>")
    cambiar(r'<meta name="description" content="[^"]*">', f'<meta name="description" content="{DESCRIPCION}">')
    cambiar(r'<link rel="canonical" href="[^"]*">', '<link rel="canonical" href="https://kvothesson.com/tachan/en.html">')
    cambiar(r'<meta property="og:title" content="[^"]*">', f'<meta property="og:title" content="{TITULO}">')
    cambiar(r'<meta property="og:description" content="[^"]*">', f'<meta property="og:description" content="{AL_COMPARTIR}">')
    cambiar(r'<meta property="og:url" content="[^"]*">', '<meta property="og:url" content="https://kvothesson.com/tachan/en.html">')
    cambiar(r'"url": "https://kvothesson\.com/tachan/", "inLanguage": "es", "description": "[^"]*"',
            f'"url": "https://kvothesson.com/tachan/en.html", "inLanguage": "en", "description": "{FICHA}"')
    cambiar(r'  html:lang\(es\) \[lang="en"\][^\n]*\n', "")
    cambiar(r'  \.otroidioma[^\n]*\n', "")
    cambiar(r'<script>if \(/\(\^\|&\)c=/[^\n]*</script>\n', "")
    cambiar(r'  <p class="otroidioma".*?</p>\n', "")
    cambiar(r'    if \(!/\(\^\|&\)c=/\.test\(datos\)[^\n]*\n', "")
    cambiar(r'    if \(document\.documentElement\.lang === "en"\) \{.*?\n    \}\n', "")
    cambiar(r'src="tachan-es\.mp4" poster="tachan-es\.jpg"', 'src="tachan-en.mp4" poster="tachan-en.jpg"')
    cambiar(r'aria-label="Cómo funciona Tachán"', 'aria-label="How Tachán works"')
    cambiar(r'<a href="en\.html" hreflang="en">English</a>', '<a href="./" hreflang="es">Español</a>')
    # Acepta etiquetas adentro, como un link, mientras no sean otro span.
    html = re.sub(r'<span lang="es">(?:[^<]|<(?!/?span\b))*</span>', "", html)
    if 'lang="es"' in html.replace('hreflang="es"', ""):
        raise SystemExit('generar_en: quedó texto en español')
    (WEB / "en.html").write_bytes(html.encode("utf-8"))


if __name__ == "__main__":
    generar()
    print("en.html listo")
