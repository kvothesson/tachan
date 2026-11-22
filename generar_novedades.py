"""Arma web/novedades.html y las notas de cada release desde NOVEDADES.md, que es el único lugar donde se escriben.

python generar_novedades.py    # escribe la página y muestra las notas de la versión del manifiesto
"""
import html
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
WEB = RAIZ / "web"
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def numero(version):
    return tuple(int(n) for n in version.split("."))


def version_manifiesto():
    manifiesto = (RAIZ / "android" / "AndroidManifest.xml").read_text(encoding="utf-8")
    return re.search(r'versionName="([^"]+)"', manifiesto)[1]


def versiones(hasta=None):
    """[(versión, fecha o None, [renglones])], la más nueva primero. Sin las que pasan de `hasta`."""
    texto = (RAIZ / "NOVEDADES.md").read_text(encoding="utf-8")
    lista = []
    for bloque in re.split(r"^## ", texto, flags=re.M)[1:]:
        titulo, _, cuerpo = bloque.partition("\n")
        m = re.match(r"(\d+(?:\.\d+)*)\s*(?:·\s*(\S.*))?$", titulo.strip())
        if not m:
            raise SystemExit("NOVEDADES.md: título raro: " + titulo)
        fecha = m[2] if m[2] and re.fullmatch(r"\d{4}-\d{2}-\d{2}", m[2]) else None
        renglones = [r[2:].strip() for r in cuerpo.splitlines() if r.startswith("- ")]
        if hasta is None or numero(m[1]) <= numero(hasta):
            lista.append((m[1], fecha, renglones))
    return lista


def notas(version):
    """El texto de la release de GitHub para esa versión."""
    for v, _, renglones in versiones():
        if v == version:
            return "\n".join("- " + r for r in renglones) + "\n\nCómo se instala y cómo comprobarlo: https://kvothesson.com/tachan/"
    raise SystemExit(f"NOVEDADES.md no tiene la versión {version}: anotala antes de publicar")


def fecha_larga(iso):
    a, m, d = (int(x) for x in iso.split("-"))
    return f"{d} de {MESES[m - 1]} de {a}"


def generar():
    # La cabeza y el sello salen de privacidad.html: así la página se ve igual que las demás.
    base = (WEB / "privacidad.html").read_text(encoding="utf-8")
    cabeza = re.search(r"<head>.*?</head>", base, re.S)[0]
    cabeza = re.sub(r"<title>.*?</title>", "<title>Novedades de Tachán</title>", cabeza)
    cabeza = re.sub(r'<link rel="canonical" href="[^"]*">', '<link rel="canonical" href="https://kvothesson.com/tachan/novedades.html">', cabeza)
    sello = re.search(r'<p class="sello">.*?</p>', base, re.S)[0]
    partes = []
    for v, fecha, renglones in versiones(version_manifiesto()):
        cuando = f" <small>{fecha_larga(fecha)}</small>" if fecha else ""
        items = "\n".join(f"      <li>{html.escape(r, quote=False)}</li>" for r in renglones)
        partes.append(f'    <h2 id="v{v}">{v}{cuando}</h2>\n    <ul>\n{items}\n    </ul>')
    pagina = f"""<!doctype html>
<html lang="es">
{cabeza}
<body>
<main>
  {sello}
  <section lang="es">
    <h1>Novedades</h1>
    <p>Lo que cambia en cada versión de Tachán. Para tenerla, tocá <b>Buscar actualización</b> en la compu o en el celu.</p>
{chr(10).join(partes)}
  </section>
  <p><a href="./">Tachán</a></p>
</main>
</body>
</html>
"""
    (WEB / "novedades.html").write_text(pagina, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")  # la consola de Windows no imprime el ⋯ en cp1252
    generar()
    print(notas(version_manifiesto()))
