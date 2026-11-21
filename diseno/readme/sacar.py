"""Saca las imágenes del README (portada y como-funciona) desde sus HTML, al doble de tamaño.

python diseno/readme/sacar.py            # todas
python diseno/readme/sacar.py portada    # una

Usa Edge en modo sin ventana, que ya viene con Windows. Las fuentes llegan de Google Fonts: hace falta internet.
El fondo queda transparente fuera del lienzo redondeado, para GitHub claro y oscuro.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

AQUI = Path(__file__).resolve().parent
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
ANCHO = 1200
ALTOS = {"portada": 620, "como-funciona": 1400}  # de sobra: se recorta al lienzo


def sacar(nombre):
    alto = ALTOS[nombre]
    salida = AQUI / f"{nombre}.png"
    with tempfile.TemporaryDirectory() as perfil:
        subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={perfil}",
                        "--force-device-scale-factor=2", "--default-background-color=00000000",
                        "--virtual-time-budget=6000", f"--window-size={ANCHO + 2},{alto + 2}",
                        f"--screenshot={salida}", (AQUI / f"{nombre}.html").as_uri()],
                       check=True, capture_output=True)
    # El lienzo mide ANCHO+2 con el borde: se recorta justo a su caja y se comprime sin perder nada.
    img = Image.open(salida).convert("RGBA")
    caja = img.getchannel("A").getbbox()
    img.crop(caja).save(salida, optimize=True)
    print(f"{salida.name}: {img.crop(caja).size[0]}x{img.crop(caja).size[1]}, {salida.stat().st_size // 1024} KB")


for n in sys.argv[1:] or ALTOS:
    sacar(n)
