"""Con el puerto ocupado, el exe espera a que se libere y, si no se libera, avisa en vez de caerse.

Datos aislados con TACHAN_DATOS y un puerto libre por caso. TACHAN_EXE elige otro exe.
"""
import os, shutil, socket, subprocess, sys, tempfile, time
from pathlib import Path
import win32gui, win32process

AQUI = Path(tempfile.gettempdir()) / "tachan_pruebas"; AQUI.mkdir(exist_ok=True)
EXE = Path(os.environ.get("TACHAN_EXE", r"D:\repos\tachan\pc\compilado\Tachan.exe"))
fallas = 0


def ver(bien, que):
    global fallas
    fallas += not bien
    print(("OK    " if bien else "FALLA ") + que)


def ocupar():
    """Toma un puerto TCP libre y el UDP siguiente, como haría otro programa."""
    while True:
        t = socket.socket(); t.bind(("", 0)); t.listen(); puerto = t.getsockname()[1]
        u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            u.bind(("", puerto + 1)); return puerto, t, u
        except OSError:
            t.close(); u.close()


def lanzar(nombre, puerto):
    datos = AQUI / f"puerto_{nombre}"
    shutil.rmtree(datos, ignore_errors=True); datos.mkdir()
    return subprocess.Popen([EXE], env=dict(os.environ, TACHAN_DATOS=str(datos), TACHAN_PUERTO=str(puerto)))


def escucha(puerto):
    try:
        with socket.create_connection(("127.0.0.1", puerto), timeout=1): return True
    except OSError:
        return False


def cartel(pid):
    """Ventanas visibles del proceso con el título de Tachán (el cartel de aviso)."""
    res = []
    def mirar(h, _):
        if win32process.GetWindowThreadProcessId(h)[1] == pid and win32gui.IsWindowVisible(h) and win32gui.GetClassName(h) == "#32770":
            res.append(win32gui.GetWindowText(h))
    win32gui.EnumWindows(mirar, None)
    return res


# 1. Se libera a los 3 segundos, como cuando la versión vieja termina de cerrar.
puerto, t, u = ocupar()
p = lanzar("libera", puerto)
try:
    time.sleep(3); t.close(); u.close()
    for _ in range(40):
        if p.poll() is not None or escucha(puerto): break
        time.sleep(0.25)
    ver(p.poll() is None, "sigue vivo mientras espera el puerto")
    ver(escucha(puerto), "escucha cuando el puerto se libera")
finally:
    p.kill(); p.wait(timeout=10)

# 2. No se libera nunca: tiene que avisar, no caerse.
puerto, t, u = ocupar()
p = lanzar("ocupado", puerto)
try:
    for _ in range(80):
        if p.poll() is not None or cartel(p.pid): break
        time.sleep(0.25)
    ver(p.poll() is None, f"no se cae (código {p.returncode})")
    ver(cartel(p.pid) == ["Tachán"], "muestra un cartel de aviso")
finally:
    p.kill(); p.wait(timeout=10); t.close(); u.close()

print("TODO BIEN" if fallas == 0 else f"FALLAS: {fallas}")
sys.exit(1 if fallas else 0)
