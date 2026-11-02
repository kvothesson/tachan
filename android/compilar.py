"""Compila la app con el SDK de D:\\dev, sin Gradle, y deja el APK en esta carpeta."""
import os
import shutil
import subprocess
from pathlib import Path

AQUI = Path(__file__).resolve().parent
SDK = Path(r"D:\dev\android-sdk")
JDK = Path(r"D:\dev\jdk17")
HERRAMIENTAS = SDK / "build-tools" / "35.0.0"
ANDROID_JAR = SDK / "platforms" / "android-35" / "android.jar"
SALIDA = AQUI / "compilado"
LLAVE = AQUI / "tachan.keystore"
APK = AQUI / "tachan.apk"


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


if __name__ == "__main__":
    main()
