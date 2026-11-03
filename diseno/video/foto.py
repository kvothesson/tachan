"""Genera foto.jpg: un atardecer sobre un lago, inventado, para no usar ninguna foto de nadie.

python diseno/video/foto.py
"""
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter

ANCHO, ALTO = 1600, 1000
HORIZONTE = 640
azar = np.random.default_rng(41)


def ruido1d(n, octavas, base=3):
    y = np.zeros(n)
    x = np.linspace(0, 1, n)
    for o in range(octavas):
        puntos = base * 2 ** o + 2
        y += np.interp(x, np.linspace(0, 1, puntos), azar.normal(size=puntos)) / 1.8 ** o
    return y


def ruido2d(alto, ancho, escala_x, escala_y, octavas):
    total = np.zeros((alto, ancho))
    for o in range(octavas):
        h, w = max(2, int(escala_y * 2 ** o)), max(2, int(escala_x * 2 ** o))
        capa = Image.fromarray(azar.normal(size=(h, w)).astype("float32")).resize((ancho, alto), Image.BICUBIC)
        total += np.asarray(capa) / 1.9 ** o
    return total


def mezcla(a, b, k):
    return np.asarray(a, "float32") * (1 - k[..., None]) + np.asarray(b, "float32") * k[..., None]


yy, xx = np.mgrid[0:HORIZONTE, 0:ANCHO].astype("float32")
v = yy / HORIZONTE
SOL = (1040, 400)
# Cielo: de azul a naranja, con nubes largas iluminadas de abajo.
cielo = mezcla((46, 62, 118), (150, 96, 130), np.clip(v / .55, 0, 1))
cielo = mezcla(cielo, (250, 150, 88), np.clip((v - .5) / .35, 0, 1))
cielo = mezcla(cielo, (255, 205, 130), np.clip((v - .82) / .18, 0, 1))
distancia = np.hypot((xx - SOL[0]) / 1.5, yy - SOL[1])
cielo = mezcla(cielo, (255, 226, 170), np.clip(1 - distancia / 430, 0, 1) ** 2.2)
nubes = ruido2d(HORIZONTE, ANCHO, 5, 14, 5)
nubes = np.clip((nubes - .35) / 1.5, 0, 1) * np.clip((v - .08) / .3, 0, 1) * np.clip((.92 - v) / .25, 0, 1)
tono = mezcla((88, 62, 104), (255, 170, 118), np.clip(v * 1.15, 0, 1))
cielo = mezcla(cielo, tono, nubes * .85)
cielo = mezcla(cielo, (255, 247, 220), np.clip(1 - distancia / 46, 0, 1) ** .6)

# Montañas: cada fila más cerca y más oscura, con la bruma tapando las de atrás.
imagen = np.zeros((ALTO, ANCHO, 3), "float32")
imagen[:HORIZONTE] = cielo
capas = [(530, 120, (170, 120, 138), 7), (570, 130, (112, 82, 118), 8), (605, 95, (70, 54, 88), 9), (635, 42, (34, 30, 50), 9)]
filas = np.arange(ALTO)[:, None]
for base, alto, color, octavas in capas:
    forma = ruido1d(ANCHO, octavas)
    perfil = base - (forma - forma.min()) / (forma.max() - forma.min()) * alto
    masc = np.clip(filas - perfil[None, :], 0, 1) * (filas < HORIZONTE)
    textura = 1 + ruido2d(ALTO, ANCHO, 30, 60, 4) * .05
    imagen = imagen * (1 - masc[..., None]) + (np.array(color, "float32") * textura[..., None]) * masc[..., None]

# Lago: el reflejo de lo de arriba, partido en ondas que crecen hacia adelante.
agua = ALTO - HORIZONTE
for f in range(agua):
    k = f / agua
    onda = (ruido1d(ANCHO, 6, base=12) * (2 + 26 * k ** 1.3)).astype(int)
    origen = np.clip(HORIZONTE - 1 - int(f * .85) + (onda * .5).astype(int), 0, HORIZONTE - 1)
    columnas = np.clip(np.arange(ANCHO) + onda, 0, ANCHO - 1)
    imagen[HORIZONTE + f] = imagen[origen, columnas] * (.8 - .3 * k) + np.array((14, 20, 44), "float32") * (.2 + .3 * k)
ancho_brillo = 40 + 150 * (np.arange(agua) / agua)
for f in range(agua):
    brillo = np.exp(-((np.arange(ANCHO) - SOL[0]) / ancho_brillo[f]) ** 2) * (.45 + .55 * azar.random(ANCHO))
    imagen[HORIZONTE + f] += (brillo * (.65 - .4 * f / agua))[:, None] * np.array((255, 196, 130), "float32") * .55

# Lo que hace que parezca sacada con un celular: viñeta, grano y una suavidad leve.
ey, ex = np.mgrid[0:ALTO, 0:ANCHO].astype("float32")
vineta = 1 - .3 * (((ex - ANCHO / 2) / (ANCHO / 2)) ** 2 + ((ey - ALTO / 2) / (ALTO / 2)) ** 2) / 2
imagen = imagen * vineta[..., None] + azar.normal(0, 3.2, (ALTO, ANCHO, 1))
final = Image.fromarray(np.clip(imagen, 0, 255).astype("uint8")).filter(ImageFilter.GaussianBlur(.6))
destino = Path(__file__).resolve().parent / "foto.jpg"
final.save(destino, quality=86)
print(destino, destino.stat().st_size // 1024, "KB")
