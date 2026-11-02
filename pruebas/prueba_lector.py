"""Toma el QR real del exe, lo deforma como lo vería una cámara y corre el lector de Java sobre cada imagen."""
import os, shutil, subprocess, tempfile, time
from pathlib import Path
import cv2
import numpy as np

AQUI = Path(tempfile.gettempdir()) / "tachan_pruebas"
DATOS = AQUI / "lector_datos"
SALIDA = AQUI / "lector_crudos"
REPO = Path(r"D:\repos\tachan")
JDK = Path(r"D:\dev\jdk17\bin")
CLASES = REPO / "android" / "prueba" / "compilado_lector"
ANCHO, ALTO = 1280, 720

shutil.rmtree(DATOS, ignore_errors=True); DATOS.mkdir(parents=True)
shutil.rmtree(SALIDA, ignore_errors=True); SALIDA.mkdir(parents=True)
entorno = dict(os.environ, TACHAN_DATOS=str(DATOS), TACHAN_PUERTO="47940")
p = subprocess.Popen([REPO / "pc/compilado/Tachan.exe"], env=entorno)
for _ in range(60):
    if (DATOS / "qr.png").exists() and (DATOS / "enlace.txt").exists(): break
    time.sleep(0.25)
time.sleep(0.5)
p.kill()
qr = cv2.imread(str(DATOS / "qr.png"), cv2.IMREAD_GRAYSCALE)
azar = np.random.default_rng(7)


def escena(lado, angulo=0, fondo=40):
    """El QR en una pantalla oscura, centrado y girado."""
    grande = cv2.resize(qr, (lado, lado), interpolation=cv2.INTER_NEAREST)
    lienzo = np.full((ALTO, ANCHO), fondo, np.uint8)
    d = (ALTO - lado) // 2 if lado < ALTO else 0
    x = (ANCHO - lado) // 2
    lienzo[d:d + lado, x:x + lado] = grande
    giro = cv2.getRotationMatrix2D((ANCHO / 2, ALTO / 2), angulo, 1)
    return cv2.warpAffine(lienzo, giro, (ANCHO, ALTO), borderValue=int(fondo))


def perspectiva(imagen, f):
    de = np.float32([[0, 0], [ANCHO, 0], [ANCHO, ALTO], [0, ALTO]])
    a = np.float32([[ANCHO * f, ALTO * f], [ANCHO * (1 - f / 2), 0], [ANCHO, ALTO], [0, ALTO * (1 - f)]])
    return cv2.warpPerspective(imagen, cv2.getPerspectiveTransform(de, a), (ANCHO, ALTO), borderValue=30)


def ruido(imagen, cuanto):
    return np.clip(imagen + azar.normal(0, cuanto, imagen.shape), 0, 255).astype(np.uint8)


def sombra(imagen):
    return (imagen * np.tile(np.linspace(0.35, 1, ANCHO), (ALTO, 1))).astype(np.uint8)


def tapar(imagen, lado):
    # Tapa datos abajo a la derecha: la corrección de errores tiene que recuperarlos.
    y, x = (ALTO + lado) // 2 - lado // 4, (ANCHO + lado) // 2 - lado // 3
    salida = imagen.copy()
    salida[y:y + lado // 40, x:x + lado // 8] = 128
    return salida


casos = {
    "limpio": escena(600),
    "chico": escena(280),
    "grande": escena(700),
    "girado_15": escena(520, 15),
    "girado_45": escena(450, 45),
    "girado_90": escena(520, 90),
    "girado_180": escena(520, 180),
    "girado_250": escena(450, 250),
    "perspectiva": perspectiva(escena(520), 0.12),
    "perspectiva_fuerte": perspectiva(escena(520, 20), 0.22),
    "borroso": cv2.GaussianBlur(escena(520), (7, 7), 0),
    "ruido": ruido(escena(520), 25),
    "poco_contraste": (escena(520) * 0.3 + 90).astype(np.uint8),
    "sombra": sombra(escena(520)),
    "todo_junto": ruido(cv2.GaussianBlur(sombra(perspectiva(escena(500, 10), 0.1)), (5, 5), 0), 12),
    "manchado": tapar(escena(600), 600),
    "sin_qr_negro": np.zeros((ALTO, ANCHO), np.uint8),
    "sin_qr_ruido": azar.integers(0, 255, (ALTO, ANCHO), dtype=np.uint8),
}
for nombre, imagen in casos.items():
    (SALIDA / f"{nombre}_{ANCHO}x{ALTO}.raw").write_bytes(imagen.tobytes())
    cv2.imwrite(str(SALIDA / f"{nombre}.png"), imagen)

shutil.rmtree(CLASES, ignore_errors=True); CLASES.mkdir(parents=True)
subprocess.run([JDK / "javac.exe", "-encoding", "UTF-8", "-Xlint:-options", "-d", CLASES,
                REPO / "android/src/com/kvothesson/tachan/QrLector.java", REPO / "android/prueba/PruebaLector.java"], check=True)
r = subprocess.run([JDK / "java.exe", "-Dfile.encoding=UTF-8", "-cp", CLASES, "com.kvothesson.tachan.PruebaLector", SALIDA, DATOS / "enlace.txt"],
                   text=True, encoding="utf-8", capture_output=True)
print(r.stdout, r.stderr)
shutil.rmtree(CLASES, ignore_errors=True)
