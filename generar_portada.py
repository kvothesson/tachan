"""Arma la portada en dos páginas, una por idioma, desde portada.html: web/index.html en castellano y web/en.html en inglés.

portada.html tiene cada texto dos veces, en <span lang="es"> y <span lang="en">, y no se publica.
Así Google ve en cada dirección un solo idioma, sin texto escondido ni casi copias.
python generar_portada.py
"""
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
FUENTE = RAIZ / "portada.html"
WEB = RAIZ / "web"
TITULO = "Tachán: transfer photos and files from Android to PC wirelessly"
DESCRIPCION = "Transfer photos, videos and files from your Android phone to your Windows PC or Mac wirelessly. Encrypted over your wifi, with no account and no servers."
AL_COMPARTIR = "Transfer photos, videos and files from your Android phone to your Windows PC or Mac wirelessly."
FICHA = "Transfer photos, videos, files and text from your Android phone to your Windows PC or Mac wirelessly. It arrives copied, ready to paste."
# Acepta etiquetas adentro, como un link, mientras no sean otro span.
SPAN = r'<span lang="{}">(?:[^<]|<(?!/?span\b))*</span>'


def _cambiador(nombre, html):
    estado = {"html": html}

    def cambiar(patron, nuevo):
        # Si portada.html cambió y un patrón ya no está, mejor frenar que publicar una página a medias.
        estado["html"], veces = re.subn(patron, lambda _: nuevo, estado["html"], flags=re.S)
        if not veces:
            raise SystemExit(f"generar_portada ({nombre}): no encontré {patron}")
    return estado, cambiar


def _sin_idioma(html, idioma, nombre):
    html = re.sub(SPAN.format(idioma), "", html)
    if f'lang="{idioma}"' in html.replace(f'hreflang="{idioma}"', ""):
        raise SystemExit(f'generar_portada ({nombre}): quedó texto con lang="{idioma}"')
    return html


def castellano(html):
    estado, cambiar = _cambiador("index.html", html)
    cambiar(r'  html:lang\(es\) \[lang="en"\][^\n]*\n', "")
    # Por el QR, con el navegador en otro idioma, va a la página en inglés con el mismo código. Sin código no
    # redirige: los robots y quien llega de un buscador se quedan acá, y en.html no vuelve, así que no hay vueltas.
    cambiar(r'document\.documentElement\.lang = "en";</script>', 'location.replace("en.html" + location.hash);</script>')
    cambiar(r'    if \(document\.documentElement\.lang === "en"\) \{.*?\n    \}\n', "")
    return _sin_idioma(estado["html"], "en", "index.html")


def ingles(html):
    estado, cambiar = _cambiador("en.html", html)
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
    return _sin_idioma(estado["html"], "es", "en.html")


def generar():
    html = FUENTE.read_text(encoding="utf-8")
    (WEB / "index.html").write_bytes(castellano(html).encode("utf-8"))
    (WEB / "en.html").write_bytes(ingles(html).encode("utf-8"))


if __name__ == "__main__":
    generar()
    print("index.html y en.html listos")
