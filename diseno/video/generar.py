"""Genera los videos cuadro por cuadro a partir de video.html y corto.html. Reconstruyen las pantallas: no son grabaciones.

Los textos de pantalla y los colores salen de las apps: si una clave desaparece, corta en vez de mostrar algo viejo.

python diseno/video/generar.py todos                                # los dos videos, en los dos idiomas
python diseno/video/generar.py largo                                # web/tachan-es.mp4, web/tachan-en.mp4 y sus portadas
python diseno/video/generar.py corto                                # diseno/video/salida/tachan-corto-es.mp4 y -en.mp4
python diseno/video/generar.py anuncio                              # diseno/video/salida/tachan-anuncio-es.mp4 y -en.mp4
python diseno/video/generar.py anuncio --es                         # solo en español, para probar
python diseno/video/generar.py corto --cuadros 2.8,8.2,10.6 carpeta # solo esos cuadros, en PNG
"""
from array import array
import json
import math
import re
import subprocess
import sys
import wave
import xml.etree.ElementTree as ET
from pathlib import Path
from playwright.sync_api import sync_playwright

AQUI = Path(__file__).resolve().parent
REPO = AQUI.parent.parent
SONIDO = REPO / "diseno" / "tachan.wav"
FPS = 30
# El corto queda fuera de web/ porque publicar_web.py sube todo lo que haya ahí.
PIEZAS = {
    "largo": {"html": "video.html", "ancho": 1280, "alto": 800, "salida": REPO / "web", "nombre": "tachan-{}", "portada": 8.9},
    "corto": {"html": "corto.html", "ancho": 720, "alto": 1280, "salida": AQUI / "salida", "nombre": "tachan-corto-{}", "portada": 39.2},
    "anuncio": {"html": "corto.html", "corte": "anuncio", "ancho": 720, "alto": 1280, "salida": AQUI / "salida", "nombre": "tachan-anuncio-{}", "portada": 10.5, "volumen": "8dB"},
}


def musica(datos, duracion):
    """La música del anuncio: diez notas que suben hasta el sol del ta-chán, silencio y un do mayor suave después. Sin archivos de otros."""
    r = 44100
    audio = array("h", bytes(2 * int(duracion * r)))

    def nota(t, fin, frecuencias, volumen, sube=.003, cae=.15):
        for i in range(int(t * r), min(int(fin * r), len(audio))):
            x = i / r - t
            onda = sum(math.sin(2 * math.pi * f * x) + .3 * math.sin(4 * math.pi * f * x) for f in frecuencias) / len(frecuencias)
            audio[i] += int(volumen * min(x / sube, 1) * math.exp(-x / cae) * onda)

    for t, semitonos in zip(datos["tics"], (0, 2, 3, 5, 7, 8, 10, 12, 14, 19)):
        nota(t, min(t + .45, datos["corte"]), [130.81 * 2 ** (semitonos / 12)], 6000)
    for t in datos["toques"]:
        nota(t, t + .12, [880], 2200, cae=.03)
    # El ta-chán termina en do y mi: el acorde sigue desde ahí, por debajo.
    nota(datos["llegada"] + .15, duracion, [261.63, 329.63, 392, 523.25], 2600, sube=.5, cae=duracion - datos["llegada"])
    for i in range(int(.6 * r)):
        audio[-1 - i] = int(audio[-1 - i] * i / (.6 * r))
    ruta = AQUI / "salida" / "musica.wav"
    ruta.parent.mkdir(exist_ok=True)
    with wave.open(str(ruta), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(r)
        w.writeframes(audio.tobytes())
    return ruta


def datos_de_las_apps(idioma):
    """Lo que se ve igual en las apps y en el video: colores de pc/marca.json, textos de Android y de Windows."""
    carpeta = "values-es" if idioma == "es" else "values"
    celu = {e.get("name"): (e.text or "").replace("\\'", "'") for e in ET.parse(REPO / "android/res" / carpeta / "textos.xml").getroot()}
    marca = (REPO / "pc/Marca.cs").read_text(encoding="utf-8")
    bloque = re.search(r'\["' + idioma + r'"\] = new Dictionary.*?\n            \},', marca, re.S)[0]
    compu = dict(re.findall(r'\["(\w+)"\] = "([^"]*)"', bloque))
    return {
        "colores": json.loads((REPO / "pc/marca.json").read_text(encoding="utf-8"))["noche"],
        "textos": {
            "escanea_pc": compu["escanea"], "ver_codigo": compu["codigo"], "listo": compu["listo"],
            "escanea": celu["escanea"], "escanear_qr": celu["camara"], "escribir": celu["escribir"], "vincular_con": celu["vincular_con"],
            "vincular": celu["vincular"], "cancelar": celu["cancelar"], "en_red": celu["en_red"], "enviando": celu["canal"], "enviado_a": celu["enviado_a"],
        },
    }


def abrir(navegador, pieza, idioma):
    pagina = navegador.new_page(viewport={"width": pieza["ancho"], "height": pieza["alto"]})
    pagina.add_init_script("window.APP = " + json.dumps(datos_de_las_apps(idioma), ensure_ascii=False))
    pagina.goto((AQUI / pieza["html"]).as_uri() + "?lang=" + idioma + "&corte=" + pieza.get("corte", ""))
    pagina.evaluate("document.fonts.ready")
    pagina.wait_for_timeout(400)
    return pagina


def cuadro(pagina, t, **opciones):
    pagina.evaluate("t => render(t)", t)
    return pagina.screenshot(**opciones)


def video(navegador, pieza, idioma):
    pagina = abrir(navegador, pieza, idioma)
    duracion = pagina.evaluate("window.DURACION")
    sonidos = [(SONIDO, t) for t in pagina.evaluate("LLEGADAS")] + [(musica(m, duracion), 0) for m in [pagina.evaluate("window.MUSICA || null")] if m]
    pieza["salida"].mkdir(exist_ok=True)
    nombre = pieza["nombre"].format(idioma)
    salida = pieza["salida"] / f"{nombre}.mp4"
    entradas = []
    for ruta, _ in sonidos:
        entradas += ["-i", str(ruta)]
    mezcla = "".join(f"[{i + 1}:a]adelay={int(t * 1000)}:all=1[s{i}];" for i, (_, t) in enumerate(sonidos))
    mezcla += "".join(f"[s{i}]" for i in range(len(sonidos))) + f"amix=inputs={len(sonidos)}:normalize=0,volume={pieza.get('volumen', '0dB')},apad,atrim=0:{duracion}[a]"
    ff = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "png", "-i", "-", *entradas,
                           "-filter_complex", mezcla, "-map", "0:v", "-map", "[a]",
                           "-c:v", "libx264", "-preset", "slow", "-crf", "25", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "64k", "-movflags", "+faststart", str(salida)],
                          stdin=subprocess.PIPE)
    total = int(duracion * FPS)
    for i in range(total):
        ff.stdin.write(cuadro(pagina, i / FPS, type="png"))
        if i % 150 == 0:
            print(idioma, i, "de", total, flush=True)
    ff.stdin.close()
    if ff.wait():
        sys.exit("ffmpeg falló")
    cuadro(pagina, pieza["portada"], type="jpeg", quality=80, path=str(pieza["salida"] / f"{nombre}.jpg"))
    print(salida, salida.stat().st_size // 1024, "KB")


with sync_playwright() as p:
    navegador = p.chromium.launch(channel="msedge")  # el Edge de Windows: no hace falta bajar el Chromium de Playwright
    if "--cuadros" in sys.argv:
        i = sys.argv.index("--cuadros")
        carpeta = Path(sys.argv[i + 2])
        pagina = abrir(navegador, PIEZAS[next((n for n in PIEZAS if n in sys.argv), "largo")], "es")
        for t in sys.argv[i + 1].split(","):
            cuadro(pagina, float(t), path=str(carpeta / f"cuadro_{t}.png"))
            print(carpeta / f"cuadro_{t}.png")
    else:
        for nombre, pieza in PIEZAS.items():
            if "todos" in sys.argv or nombre in sys.argv:
                for idioma in ("es",) if "--es" in sys.argv else ("es", "en"):
                    video(navegador, pieza, idioma)
    navegador.close()
