"""Compila el programa de PC con el C# de Visual Studio Build Tools: .NET 4.8 ya viene en Windows."""
import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

AQUI = Path(__file__).resolve().parent
CSC = Path(r"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\MSBuild\Current\Bin\Roslyn\csc.exe")
NET = Path(r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319")
WPF = NET / "WPF"
SALIDA = AQUI / "compilado"
EXE = SALIDA / "Tachan.exe"
ICONO = SALIDA / "icono.ico"
MARCA = json.loads((AQUI / "marca.json").read_text(encoding="utf-8"))["noche"]


def color(nombre):
    h = MARCA[nombre]
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) + (255,)


def dibujar_icono(lado):
    """La flecha en arco, recortada por el hexágono del cristal."""
    escala = 4
    n = lado * escala
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    u = n / 24
    d.polygon([(12 * u, 0.4 * u), (22.2 * u, 6.2 * u), (22.2 * u, 17.8 * u), (12 * u, 23.6 * u), (1.8 * u, 17.8 * u), (1.8 * u, 6.2 * u)], fill=color("accent"))
    tinta = color("on-accent")
    grosor = max(int(2 * u), 2)
    chico = lambda x, y: ((12 + (x - 12) * 0.68) * u, (12 + (y - 10.5) * 0.68) * u)
    arco = [(4.5 + 15 * t, 18.5 - 13 * (1 - (1 - t) ** 2)) for t in (i / 24 for i in range(25))]
    d.line([chico(x, y) for x, y in arco], fill=tinta, width=grosor, joint="curve")
    d.line([chico(15, 2.8), chico(19.7, 5.8), chico(17, 11)], fill=tinta, width=grosor, joint="curve")
    return im.resize((lado, lado), Image.LANCZOS)


def main():
    SALIDA.mkdir(exist_ok=True)
    grande = dibujar_icono(256)
    grande.save(ICONO, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (256, 256)])
    referencias = ["System.dll", "System.Core.dll", "System.Drawing.dll", "System.Windows.Forms.dll",
                   "System.Security.dll", WPF / "PresentationCore.dll", WPF / "WindowsBase.dll"]
    comando = [str(CSC), "/nologo", "/nostdlib+", "/noconfig", "/target:winexe", "/optimize+", "/platform:anycpu",
               "/langversion:latest", f"/out:{EXE}", f"/win32icon:{ICONO}", f"/win32manifest:{AQUI / 'app.manifest'}",
               f"/r:{NET / 'mscorlib.dll'}"]
    comando += [f"/r:{NET / r if isinstance(r, str) else r}" for r in referencias]
    comando += [str(p) for p in sorted(AQUI.glob("*.cs"))]
    subprocess.run(comando, check=True)
    print(f"Listo: {EXE} ({EXE.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
