"""Compila la app con el SDK de D:\\dev, sin Gradle.

python android/compilar.py            APK de prueba, firmado con la llave de desarrollo
python android/compilar.py --tienda   además, el AAB para Google Play y el APK de la web, firmados con la llave definitiva
"""
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
SDK = Path(r"D:\dev\android-sdk")
JDK = Path(r"D:\dev\jdk17")
HERRAMIENTAS = SDK / "build-tools" / "36.0.0"
ANDROID_JAR = SDK / "platforms" / "android-36" / "android.jar"
SALIDA = AQUI / "compilado"
LLAVE = AQUI / "tachan.keystore"
APK = AQUI / "tachan.apk"
AAB = AQUI / "tachan.aab"
APK_WEB = AQUI.parent / "web" / "tachan.apk"
LLAVE_SUBIDA = Path.home() / ".tachan" / "subida.keystore"
CLAVE_SUBIDA = Path.home() / ".tachan" / "subida.txt"
CACHE_GRADLE = Path.home() / ".gradle" / "caches" / "modules-2" / "files-2.1"
DEPENDENCIAS = ["bundletool", "guava", "failureaccess", "protobuf-java", "protobuf-java-util", "gson", "aapt2-proto", "dagger", "javax.inject", "jsr305",
                "auto-value-annotations", "jose4j", "slf4j-api", "error_prone_annotations", "checker-qual"]


def correr(*comando, cwd=None):
    subprocess.run([str(c) for c in comando], check=True, cwd=cwd, env={**os.environ, "JAVA_HOME": str(JDK)})


def main():
    shutil.rmtree(SALIDA, ignore_errors=True)
    clases = SALIDA / "clases"
    dex = SALIDA / "dex"
    generado = SALIDA / "generado"
    for carpeta in (clases, dex, generado):
        carpeta.mkdir(parents=True)

    recursos = SALIDA / "recursos.zip"
    correr(HERRAMIENTAS / "aapt2.exe", "compile", "--dir", AQUI / "res", "-o", recursos)
    sin_firmar = SALIDA / "alineable.apk"
    correr(HERRAMIENTAS / "aapt2.exe", "link", "-o", sin_firmar, "-I", ANDROID_JAR,
           "--manifest", AQUI / "AndroidManifest.xml", "--java", generado, recursos)

    fuentes = [*(AQUI / "src").rglob("*.java"), *generado.rglob("*.java")]
    correr(JDK / "bin" / "javac.exe", "-encoding", "UTF-8", "-source", "8", "-target", "8",
           "-Xlint:-options", "-Xlint:-deprecation", "-classpath", ANDROID_JAR, "-d", clases, *fuentes)
    correr(HERRAMIENTAS / "d8.bat", "--release", "--min-api", "23", "--lib", ANDROID_JAR,
           "--output", dex, *clases.rglob("*.class"))

    correr(JDK / "bin" / "jar.exe", "uf", "alineable.apk", "-C", "dex", "classes.dex", cwd=SALIDA)
    alineado = SALIDA / "alineado.apk"
    correr(HERRAMIENTAS / "zipalign.exe", "-f", "4", sin_firmar, alineado)

    if not LLAVE.exists():
        correr(JDK / "bin" / "keytool.exe", "-genkeypair", "-keystore", LLAVE, "-alias", "tachan",
               "-keyalg", "RSA", "-keysize", "2048", "-validity", "10000",
               "-storepass", "tachan-local", "-keypass", "tachan-local",
               "-dname", "CN=Tachan")
    correr(HERRAMIENTAS / "apksigner.bat", "sign", "--ks", LLAVE, "--ks-pass", "pass:tachan-local",
           "--out", APK, alineado)
    correr(HERRAMIENTAS / "apksigner.bat", "verify", APK)
    print(f"Listo: {APK} ({APK.stat().st_size // 1024} KB)")
    if "--tienda" in sys.argv:
        armar_aab(recursos, dex)
        armar_apk_web(alineado)


def armar_apk_web(alineado):
    # Con la misma llave que después usará Play, para que quien la baje de la web pueda actualizarla desde ahí.
    correr(HERRAMIENTAS / "apksigner.bat", "sign", "--ks", LLAVE_SUBIDA, "--ks-pass", f"file:{CLAVE_SUBIDA}", "--ks-key-alias", "subida",
           "--out", APK_WEB, alineado)
    correr(HERRAMIENTAS / "apksigner.bat", "verify", APK_WEB)
    Path(str(APK_WEB) + ".idsig").unlink(missing_ok=True)
    print(f"Listo: {APK_WEB} ({APK_WEB.stat().st_size // 1024} KB)")


def bundletool(*argumentos):
    """Usa el bundletool que dejó Gradle en su caché: la app no depende de Gradle para compilar."""
    jars = []
    for nombre in DEPENDENCIAS:
        hallados = [j for j in CACHE_GRADLE.glob(f"*/{nombre}/*/*/{nombre}-*.jar") if not j.stem.endswith(("-sources", "-javadoc"))]
        if not hallados:
            raise SystemExit(f"Falta {nombre} en {CACHE_GRADLE}")
        jars.append(max(hallados, key=lambda j: j.parent.parent.name))
    correr(JDK / "bin" / "java.exe", "-cp", os.pathsep.join(map(str, jars)), "com.android.tools.build.bundletool.BundleToolMain", *argumentos)


def armar_aab(recursos, dex):
    if not LLAVE_SUBIDA.exists():
        raise SystemExit(f"Falta la llave de subida: {LLAVE_SUBIDA}")
    proto = SALIDA / "proto.apk"
    correr(HERRAMIENTAS / "aapt2.exe", "link", "--proto-format", "-o", proto, "-I", ANDROID_JAR,
           "--manifest", AQUI / "AndroidManifest.xml", recursos)
    modulo = SALIDA / "base.zip"
    with zipfile.ZipFile(proto) as entrada, zipfile.ZipFile(modulo, "w", zipfile.ZIP_DEFLATED) as salida:
        for item in entrada.namelist():
            destino = "manifest/AndroidManifest.xml" if item == "AndroidManifest.xml" else item
            salida.writestr(destino, entrada.read(item))
        salida.write(dex / "classes.dex", "dex/classes.dex")
    AAB.unlink(missing_ok=True)
    bundletool("build-bundle", f"--modules={modulo}", f"--output={AAB}")
    correr(JDK / "bin" / "jarsigner.exe", "-keystore", LLAVE_SUBIDA, "-storepass:file", CLAVE_SUBIDA, "-sigalg", "SHA256withRSA", "-digestalg", "SHA-256", AAB, "subida")
    bundletool("validate", f"--bundle={AAB}")
    print(f"Listo: {AAB} ({AAB.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
