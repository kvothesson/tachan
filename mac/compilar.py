"""Compila Tachán para Mac con el swiftc de las Command Line Tools: sin Xcode, sin paquetes.

Lee la versión de android/AndroidManifest.xml, los colores de pc/marca.json, los textos y constantes de
pc/Marca.cs y la llave pública de pc/Actualizador.cs: nada de eso se copia a mano. Deja la app universal
(arm64 + x86_64) en mac/compilado/Tachan.app, firmada ad hoc, y el zip en web/Tachan-mac.zip.
python3 mac/compilar.py

Para pruebas: --salida DIR compila aparte (app y zip en DIR) y --llave-prueba MODULO pone otra llave pública
(módulo RSA en base64, exponente 65537), para probar el actualizador sin la llave real. Ver pruebas/prueba_actualizar_mac.py.
"""
import argparse
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
SALIDA = AQUI / "compilado"
APP = SALIDA / "Tachan.app"
ZIP = RAIZ / "web" / "Tachan-mac.zip"
MINIMO = "15.0"
ARQUITECTURAS = ["arm64", "x86_64"]
LLAVE_PRUEBA = None


def leer(ruta):
    return (RAIZ / ruta).read_text(encoding="utf-8")


def cadena(s):
    return json.dumps(s, ensure_ascii=False)


def generar():
    """Escribe compilado/Generado.swift con lo que viene de afuera de mac/."""
    manifiesto = leer("android/AndroidManifest.xml")
    codigo = int(re.search(r'versionCode="(\d+)"', manifiesto)[1])
    nombre = re.search(r'versionName="([^"]+)"', manifiesto)[1]

    marca = leer("pc/Marca.cs")
    constante = lambda c: re.search(rf"const \w+ {c} = (\"[^\"]*\"|\d+);", marca)[1]
    textos = {}
    for idioma, cuerpo in re.findall(r'\["(\w\w)"\] = new Dictionary<string, string>\s*\{(.*?)\n\s*\},', marca, re.S):
        textos[idioma] = dict(re.findall(r'\["(\w+)"\] = "((?:[^"\\]|\\.)*)"', cuerpo))

    colores = json.loads(leer("pc/marca.json"))["noche"]
    camello = lambda k: re.sub(r"-(\w)", lambda m: m[1].upper(), k)
    rgb = lambda h: "srgbRed: {:.4f}, green: {:.4f}, blue: {:.4f}".format(*(int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)))

    actualizador = leer("pc/Actualizador.cs")
    modulo = LLAVE_PRUEBA or re.search(r"<Modulus>([^<]+)</Modulus>", actualizador)[1]
    exponente = re.search(r"<Exponent>([^<]+)</Exponent>", actualizador)[1]

    lineas = ["// Generado por mac/compilar.py: no editar a mano.", "import AppKit", "",
              "enum Marca {",
              f"    static let nombre = {constante('Nombre')}",
              f"    static let visible = {constante('Visible')}",
              f"    static let enlace = {constante('Enlace')}",
              f"    static let puertoTcp = {constante('PuertoTcp')}",
              f"    static let puertoUdp = {constante('PuertoUdp')}",
              "}", "",
              "enum VersionApp {",
              f"    static let codigo = {codigo}",
              f"    static let nombre = {cadena(nombre)}",
              "}", "",
              "enum Colores {"]
    lineas += [f"    static let {camello(k)} = NSColor({rgb(v)}, alpha: 1)" for k, v in colores.items()]
    lineas += ["}", "",
               "enum LlaveActualizar {",
               f"    static let modulo = {cadena(modulo)}",
               f"    static let exponente = {cadena(exponente)}",
               "}", "",
               "let textosPc: [String: [String: String]] = ["]
    for idioma, tabla in textos.items():
        pares = ", ".join(f"{cadena(k)}: {cadena(v)}" for k, v in tabla.items())
        lineas.append(f"    {cadena(idioma)}: [{pares}],")
    lineas += ["]", ""]
    SALIDA.mkdir(parents=True, exist_ok=True)
    (SALIDA / "Generado.swift").write_text("\n".join(lineas), encoding="utf-8")
    return codigo, nombre


def overlay():
    """Las Command Line Tools de Xcode 16 traen el módulo SwiftBridging dos veces y swiftc se niega a compilar.
    Se tapa uno con un archivo vacío solo para esta compilación, sin tocar el sistema."""
    duplicado = Path("/Library/Developer/CommandLineTools/usr/include/swift/bridging.modulemap")
    if not duplicado.exists() or not duplicado.with_name("module.modulemap").exists():
        return []
    vacio = SALIDA / "vacio.modulemap"
    vacio.write_text("")
    yaml = SALIDA / "overlay.yaml"
    yaml.write_text(json.dumps({"version": 0, "case-sensitive": "false", "roots": [
        {"type": "file", "name": str(duplicado), "external-contents": str(vacio)}]}))
    return ["-vfsoverlay", str(yaml)]


def plist(codigo, nombre):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleIdentifier</key><string>com.kvothesson.tachan</string>
    <key>CFBundleName</key><string>Tachan</string>
    <key>CFBundleDisplayName</key><string>Tachán</string>
    <key>CFBundleExecutable</key><string>Tachan</string>
    <key>CFBundleIconFile</key><string>Tachan</string>
    <key>CFBundlePackageType</key><string>APPL</string>
    <key>CFBundleShortVersionString</key><string>{nombre}</string>
    <key>CFBundleVersion</key><string>{codigo}</string>
    <key>CFBundleDevelopmentRegion</key><string>es</string>
    <key>LSMinimumSystemVersion</key><string>{MINIMO}</string>
    <key>LSUIElement</key><true/>
    <key>LSMultipleInstancesProhibited</key><false/>
    <key>NSHighResolutionCapable</key><true/>
    <key>NSLocalNetworkUsageDescription</key><string>Tachán recibe lo que mandás desde tu celu por el wifi de tu casa, directo y cifrado.</string>
    <key>NSHumanReadableCopyright</key><string>Kvothesson · GPLv3</string>
</dict>
</plist>
"""


INFOPLIST_EN = '"NSLocalNetworkUsageDescription" = "Tachán receives what you send from your phone over your home Wi-Fi, directly and encrypted.";\n'


def main():
    global SALIDA, APP, ZIP, LLAVE_PRUEBA
    opciones = argparse.ArgumentParser()
    opciones.add_argument("--salida")
    opciones.add_argument("--llave-prueba")
    a = opciones.parse_args()
    if a.salida:
        SALIDA = Path(a.salida).resolve()
        APP, ZIP = SALIDA / "Tachan.app", SALIDA / "Tachan-mac.zip"
    LLAVE_PRUEBA = a.llave_prueba
    codigo, nombre = generar()
    fuentes = [str(p) for p in sorted(AQUI.glob("*.swift"))] + [str(SALIDA / "Generado.swift")]
    extra = overlay()
    binarios = []
    for arq in ARQUITECTURAS:
        salida = SALIDA / f"Tachan-{arq}"
        subprocess.run(["swiftc", "-Osize", "-wmo", "-swift-version", "5", "-target", f"{arq}-apple-macos{MINIMO}",
                        "-Xfrontend", "-disable-reflection-metadata", "-Xlinker", "-dead_strip", "-Xlinker", "-x",
                        *extra, "-o", str(salida), *fuentes], check=True)
        binarios.append(str(salida))

    if APP.exists():
        shutil.rmtree(APP)
    (APP / "Contents" / "MacOS").mkdir(parents=True)
    recursos = APP / "Contents" / "Resources"
    (recursos / "en.lproj").mkdir(parents=True)
    ejecutable = APP / "Contents" / "MacOS" / "Tachan"
    subprocess.run(["lipo", "-create", "-output", str(ejecutable), *binarios], check=True)
    subprocess.run(["strip", "-x", str(ejecutable)], check=True)
    (APP / "Contents" / "Info.plist").write_text(plist(codigo, nombre), encoding="utf-8")
    (recursos / "en.lproj" / "InfoPlist.strings").write_text(INFOPLIST_EN, encoding="utf-8")

    # El ícono lo dibuja la propia app, con los mismos trazos que el de Windows.
    with tempfile.TemporaryDirectory() as tmp:
        juego = Path(tmp) / "Tachan.iconset"
        subprocess.run([str(ejecutable), "--icono", str(juego)], check=True)
        subprocess.run(["iconutil", "-c", "icns", "-o", str(recursos / "Tachan.icns"), str(juego)], check=True)

    # Firma ad hoc: sin cuenta de Apple Developer no hay notarización. Apple Silicon no corre nada sin firma.
    subprocess.run(["codesign", "--force", "--sign", "-", "--timestamp=none", str(APP)], check=True)
    subprocess.run(["codesign", "--verify", "--strict", str(APP)], check=True)

    ZIP.unlink(missing_ok=True)
    subprocess.run(["ditto", "-c", "-k", "--keepParent", "--norsrc", str(APP), str(ZIP)], check=True)
    print(f"Listo: {APP} (binario {ejecutable.stat().st_size // 1024} KB), {ZIP.name} {ZIP.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
