# Tachán: guía para trabajar en este repo

Leé esto antes de tocar nada. `README.md` explica el producto; este archivo tiene el contexto, las reglas y lo que falta.

## Qué es

Compartís algo en el celu y aparece en la compu, por la red local, cifrado y sin servidores ni cuenta. Queda copiado para Ctrl+V (Cmd+V en Mac) y aparece un aviso con un ta-chán que no saca el foco.

- **En producción:** versión 1.3, en https://kvothesson.com/tachan/
- **Este repo:** `kvothesson/tachan`, público desde el 2026-11-21, con licencia GPLv3. Tiene el código, la web y las descargas.
- **Web:** la carpeta `web/` se publica sola en https://kvothesson.com/tachan/ cuando un cambio suyo llega a `main` (`.github/workflows/web.yml`). El nombre del repo no se puede cambiar: las apps instaladas y los QR tienen fija esa dirección.
- **Diseño:** sale de un sistema de marca común a varias apps, que vive fuera de este repo.
- **Notas internas:** si existe la carpeta `privado/`, leerla también. No se versiona.

## Reglas

- **Lenguaje:** español rioplatense, respuestas cortas y sin raya larga. Se decide por resultados, no por detalles técnicos.
- **Evidencia:** no decir "listo" sin mostrar la prueba. Si algo no se probó, decirlo.
- **Identidad:** el repo es público: nunca poner datos personales (nombres reales, mails, nombres de equipos) en el código, las capturas ni los commits.
- **Publicar:** pedir OK antes de cada publicación, sea de la web o de este repo.
- **Crecimiento:** sin promoción. Crecer por confiabilidad, por estar donde la gente ya busca y por el uso.
- **Producto:** una cosa, rápido, casi sin palabras. Sin cuenta, sin servidores, sin rastreo. Sin dependencias: el exe y el APK pesan menos de 100 KB y así se quedan.
- **Internet:** Tachán solo sale a internet cuando alguien toca **Buscar actualización**. No agregar chequeos automáticos sin decidirlo antes y cambiar `web/privacidad.html`.
- **El celu de pruebas:**
  - Instalar siempre con `adb install --user 0 -r`. Sin `--user 0`, se instala en todos los perfiles del celu.
  - Si alguien lo usa al mismo tiempo, leer la pantalla justo antes de cada toque. Un toque a ciegas ya desvinculó el celu una vez.
  - Si aparecen notificaciones en una captura, no compartir la pantalla entera: recortar.

## Cómo está hecho

```
Celu (Android, Java sin librerías)              Compu (Windows, C# sobre .NET 4.8)
Compartir / Principal -> EnvioServicio  TLS --> Servidor -> Descargas\Tachan
Lector + QrLector       Cola + ReintentoJob     Portapapeles -> Aviso (no saca el foco)
Transporte (protocolo, Java puro)               Instalador, Actualizador, Qr, Datos

                                                Mac (Swift + AppKit, macOS 15+): los mismos nombres en mac/
```

**Protocolo:** HTTPS propio en el puerto TCP 47810 (`POST /vincular`, `GET /hola`, `POST /enviar`, `POST /desvincular`) y búsqueda UDP en el 47811 (`TCHN?<huella>` y `TCHN!<puerto>`).

**Cola:** lo que se mandó con la compu apagada sale solo al volver, con la cabecera `X-Demorado`. La compu avisa ("Mandado antes"), pero no lo copia, no lo pega y no lo suma a lo nuevo. De ese aviso se arrastra y se copia solo lo que se ve; lo demás está en la carpeta. Un texto demorado queda en pantalla hasta pasarle el mouse, porque no se guarda en ningún archivo.

**Vínculo:** el QR es `https://kvothesson.com/tachan/#c=<base32>&n=<nombre>`. El código va después del `#` para que no llegue a ningún servidor. Lleva IP, puerto, secreto y huella, dura 5 minutos, sirve una vez y siempre se confirma en el celu. Si la app está, la web la abre con un `intent://`; si no, baja el APK. El lector propio acepta también `tachan://v?c=...`.

**Seguridad:** el celu fija la huella del certificado de la compu, y la compu guarda solo el hash de cada token. Un archivo recibido nunca se abre solo.

**Windows:** el exe se copia solo a `%LOCALAPPDATA%\Programs\Tachan`, con acceso en Inicio, entrada en Aplicaciones y arranque con Windows. Abrir una versión distinta cierra la vieja y la reemplaza sin tocar los datos, que están en `%APPDATA%\Tachan`.

**Mac:** `mac/` imita a `pc/` archivo por archivo, con el mismo protocolo: el APK no distingue una compu de la otra. La app se copia sola a `~/Applications/Tachan.app` y vive en la barra de menú (`LSUIElement`). Abrir una versión distinta cierra la vieja y la reemplaza; los datos están en `~/Library/Application Support/Tachan` y lo recibido en `~/Downloads/Tachan`, marcado en cuarentena como bajado de internet. Arranca con la sesión con `SMAppService` y el aviso es un `NSPanel` que no se activa, arriba a la derecha. `TACHAN_DATOS`, `TACHAN_PUERTO` y `TACHAN_ACTUALIZAR` valen igual; `TACHAN_NOMBRE` cambia el nombre que ve el celu, para capturas.

**Marca:** `pc/MarcaColores.cs`, `pc/marca.json`, `web/marca.css` y `android/res/values*/marca.xml` se generan desde ese sistema de marca. No se editan a mano. Tachán es temperatura calor (ámbar) y siempre de noche: se ve oscuro con cualquier tema de Windows o del celu (`"modo": "noche"` en `apps.json`).

**Herramientas:** Roslyn de VS 2022 BuildTools, y el SDK de Android y el JDK 17 en las rutas que figuran arriba de `android/compilar.py` (`D:\dev\android-sdk`, `D:\dev\jdk17`). Sin Gradle. El AAB usa el bundletool de la caché de Gradle de esta PC.

## Compilar y publicar

La versión se decide en un solo lugar: `versionCode` y `versionName` de `android/AndroidManifest.xml`. Subirla en cada publicación: sin eso, nadie recibe la actualización.

```bash
python pc/compilar.py                # genera VersionApp.cs y copia el exe a web/
python android/compilar.py --tienda  # APK de prueba, AAB y web/tachan.apk con la llave definitiva
python3 mac/compilar.py             # en una Mac: Tachan.app firmada ad hoc y web/Tachan-mac.zip
python publicar_web.py "mensaje"     # escribe version.json, sube las descargas y publica web/
```

**Mac:** se compila en una Mac y se publica desde Windows, donde están las llaves. Después de subir la versión en el manifiesto, compilar en la Mac y commitear `web/Tachan-mac.zip`: `publicar_web.py` no publica si el zip es de otra versión, porque las Mac lo bajarían una y otra vez. `version.json` lleva `mac_sha256` y `firma_mac` (la misma llave firma `codigo\nsha256` del zip); Windows y el celu leen sus campos con regex que no los tocan. La release suma `Tachan-mac.zip` y `actualizar-Tachan-mac.zip`.

**Herramientas en Mac:** las Command Line Tools de Xcode (`swiftc`, `lipo`, `codesign`, `iconutil`, `ditto`) y Python 3, sin Xcode ni paquetes. Para las pruebas, JDK 17 y adb de Homebrew (`brew install openjdk@17 android-platform-tools`). `compilar.py` lee la versión del manifiesto, los colores de `pc/marca.json`, los textos de `pc/Marca.cs` y la llave pública de `pc/Actualizador.cs`: no se copian a mano. Lo que en Mac se dice distinto ("Abrir al iniciar sesión") está en `mac/Textos.swift`.

**Web en inglés:** `web/en.html` se genera desde `web/index.html` con `generar_en.py`, y `publicar_web.py` lo corre solo. No se edita a mano: el texto va en los `<span lang="en">` de `index.html`, y el título y la descripción en `generar_en.py`. `index.html` queda siempre en español para que Google lo lea así; solo cambia al idioma del navegador cuando se llega por el QR.

**Videos:** se regeneran seguido, para que las pantallas sigan iguales a las apps. `python diseno/video/generar.py todos` arma el de la web (`web/tachan-es.mp4` y `-en.mp4`, desde `video.html`) el tutorial vertical (`diseno/video/salida/`, desde `corto.html`) y el anuncio de 15 segundos (`tachan-anuncio-*.mp4`, que remonta las escenas del tutorial con `?corte=anuncio`), unos 6 minutos.
- Reconstruyen las pantallas, no son grabaciones. Los colores y los textos de las apps entran solos desde `pc/marca.json`, `android/res` y `pc/Marca.cs`.
- Si cambia cómo se ve o se usa una pantalla, hay que cambiar también su diseño en esas páginas. Regenerar antes de publicar.
- La compu se llama "Mi compu" o "Mi PC": nunca poner nombres reales.

- Para compilar el exe hay que cerrar Tachán si corre desde `pc/compilado`. La copia instalada no molesta.
- Después de publicar, comprobar que los archivos en línea son iguales a los del commit. La web tarda uno o dos minutos; `gh run list -w web.yml` dice si el despliegue terminó.

**Llave de actualizaciones:** `~/.tachan/actualizar.pem`, fuera del repo. `publicar_web.py` firma `version.json` con ella (`firmar.py`) y su parte pública va en `pc/Actualizador.cs`. Si se pierde, las compus ya instaladas no aceptan más actualizaciones por el botón.

**Llave de firma:** `~/.tachan/subida.keystore` y su clave `subida.txt`, fuera del repo. Sin ella no se pueden publicar actualizaciones que se instalen encima. Usarla también en Google Play, cargándola como llave de firma propia. `android/tachan.keystore` es solo de desarrollo y **no se mezcla**: cambiar entre las dos obliga a desinstalar y volver a vincular.

## Pruebas

Corren con datos aislados por `TACHAN_DATOS`, salvo las marcadas como reales.

| Prueba | Qué cubre | Cuidado |
|---|---|---|
| `pruebas/prueba_e2e.py` | Protocolo y seguridad, en Windows y en Mac | "QR en pantalla: False" solo significa que otra ventana lo tapó. Usa un puerto libre y una carpeta nueva por corrida, y cierra su exe aunque falle: un exe viejo de prueba no la cruza |
| `pruebas/prueba_copia.py` | Portapapeles | Restaura el texto; una imagen copiada se pierde |
| `pruebas/prueba_demorado.py` | Lo que sale de la cola no pisa el portapapeles ni se suma a lo nuevo | Restaura el texto; una imagen copiada se pierde |
| `pruebas/prueba_arriba.py` | Aviso sobre pantalla completa | Abre una ventana unos segundos |
| `pruebas/prueba_aviso_imagen.py` | Imágenes altas, anchas y transparentes | Mirar `avisos.png` en la carpeta temporal |
| `pruebas/prueba_puerto_ocupado.py` | Puerto ocupado: espera a que se libere y, si no, avisa | Abre un cartel unos segundos; `TACHAN_EXE` prueba otro exe |
| `pruebas/prueba_memoria.py` | Memoria y recursos | Usa el portapapeles |
| `pruebas/prueba_lector.py` | Lector de QR | Sale 17 de 18: la perspectiva extrema falla y es aceptado |
| `pruebas/prueba_pc.py` | Arrastre y pegado | **Mueve el mouse real:** solo si nadie está usando la compu |
| `pruebas/prueba_actualizar.py` | Actualización | **Toca la instalación real** |
| `pruebas/prueba_buscar_version.py` | Buscar actualización | **Toca la instalación real** |
| `pruebas/prueba_actualizar_mac.py` | Actualización en Mac con una llave de prueba | **Toca la instalación real** (`~/Applications`); al final reinstala `mac/compilado` |
| `pruebas/prueba_firma.py` | Firma de la actualización | Datos aislados; no toca la instalación |
| `pruebas/medir_celu.py` | Arranque y lector | Celu desbloqueado y conectado; cierra y abre la app tres veces |
| `pruebas/medir_envio.py` | Envío real por el selector de fotos | Celu desbloqueado, conectado y sin tocar; toca la pantalla y la bloquea al terminar |
| `pruebas/medir_velocidad.py` | Protocolo solo | Celu conectado |

## Trampas ya pagadas

- `adb` desde Git Bash: `MSYS_NO_PATHCONV=1` rompe las rutas de Windows locales y sin él se rompen las del celu. Si falla, usar PowerShell.
- **Nunca** medir velocidad pidiendo `dumpsys meminfo` o `top` durante un envío: lo frena. Con esas lecturas, en 2,4 GHz dio 0,74 MB/s; sin ellas, en 5 GHz, 5,12 MB/s.
- Compartir un archivo desde `adb` no sirve, porque Tachán no tiene permiso de lectura: ni con `file://` (lo rechaza desde la 1.3) ni con `content://` y `--grant-read-uri-permission` (el permiso no viaja en el extra). Usar el selector de fotos, que además le cambia el nombre al archivo.
- Android no abre la pantalla de compartir con el celu bloqueado: primero compartir y después bloquear.
- Con el puerto ocupado, el exe se caía en silencio (código 0xE0434352). Ahora espera 10 segundos a que se libere y, si no, avisa con un cartel.
- Un proceso lanzado con `UseShellExecute = false` hereda el puerto abierto. Por eso `Actualizador` usa el shell: si no, la versión nueva no puede escuchar y se cierra.
- El selector de archivos de Android sale vacío ("Sin elementos") en el celu de pruebas, también abierto sin Tachán. Al `com.google.android.documentsui` actualizado por Play no le dieron `MANAGE_DOCUMENTS`, y el log dice `Permission Denial` y `ProvidersCache: Timeout`. No es Tachán. Por eso el + ofrece **Fotos y videos** aparte.
- Cada recompilación del exe cambia sus bytes, y eso alcanza para que cuente como "otra versión".
- El emulador de Android 16 no arranca en esta PC (probado el 2026-11-08, emulador 37.2.13, imagen `android-36;default;x86_64`, WHPX): se cae con 0xC0000005 o queda colgado antes del kernel, con cualquier ajuste de gráficos o procesador. Para Android 16 hace falta un celu real o el informe previo al lanzamiento de Play.
- La cámara de algunos celus no abre `tachan://`: por eso el QR es un link web y la app trae lector propio.

**En Mac:**
- Las Command Line Tools de Xcode 16 traen el módulo `SwiftBridging` dos veces y `swiftc` no compila nada ("redefinition of module"). `compilar.py` tapa uno con un overlay (`-vfsoverlay`) sin tocar el sistema.
- macOS da una identidad TLS solo desde el llavero o desde un `.p12`. Con el llavero, cada versión (otra firma ad hoc) haría preguntar por la llave. Por eso el certificado lo crea `/usr/bin/openssl` la primera vez y se carga solo en memoria con `kSecImportToMemoryOnly`, que existe desde macOS 15: de ahí el mínimo.
- El `.p12` queda protegido solo por permisos 0600 (en Windows lo cifra DPAPI). Su clave no protege nada.
- Compilar dos veces la misma fuente da los mismos bytes, al revés que en Windows. Para probar el reemplazo de versión, volver a firmar una copia (`codesign --force -s - --options runtime`).
- Sin cuenta de Apple Developer no hay notarización. En macOS 15 el clic derecho, Abrir, ya no saltea Gatekeeper: hay que ir a Ajustes del Sistema, Privacidad y seguridad, Abrir igual. La copia en `~/Applications` va sin cuarentena y no vuelve a preguntar.
- Desde una terminal sin permisos de Accesibilidad y Grabación de pantalla no se puede apretar Cmd+V con `osascript` ni sacar una captura de otra ventana. En modo prueba la app deja una foto de cada aviso (`aviso_NN.png` en la carpeta de datos), sin el resto de la pantalla.
- Hasta la 1.4 el celu guardaba una sola compu: vincularlo con la Mac le sacaba el vínculo con la PC. Desde la 1.5 guarda varias (`Almacen`): cada una tiene su atajo en la fila de Compartir, y tocar Tachán sin elegir manda a la última usada si está prendida o, si no, a la primera que conteste. Lo encolado recuerda a qué compu iba (`.compu` al lado de cada pieza de la cola).

## Decisiones tomadas

- **Nombre:** Tachán. No proponer un barco ni volver sobre eso.
- **Distribución:** primero la web. Google Play pide 12 testers reales durante 14 días de prueba cerrada. No pagar testers ni crear cuentas propias para eso.
- **Actualizaciones:** manuales, con botón, para no tener conexiones automáticas. Desde la 1.4 las apps bajan el programa nuevo de la release `v<nombre>` en GitHub, de las copias `actualizar-Tachan.exe` y `actualizar-tachan.apk` que sube `publicar_web.py`. Su cuenta de descargas es la única medida de cuántos siguen usando Tachán (columna `usan` de `scripts/metricas_tachan.py` en el taller). No sacar `Tachan.exe` ni `tachan.apk` de `web/`: las 1.3 instaladas se actualizan desde ahí.
- **Código:** abierto con GPLv3 desde el 2026-11-21. Los cambios de afuera entran por pull request.

## Velocidad y consumo de referencia

| Medición | Valor |
|---|---|
| 300 MB por 5 GHz, con el celu bloqueado | 59 s (5,12 MB/s, red: 5,46) |
| Red de 2,4 GHz | 2,5 MB/s de techo |
| Memoria de la compu | 25 MB al arrancar, 66 MB en reposo después de fotos de 12 MP |
| Memoria del celu | unos 26 MB |
| CPU en reposo | 0% en los dos |
| Abrir la app | 240-430 ms |
| Lector de QR | unos 25 ms por cuadro |

## Qué falta

**Por probar:**
- Mandar algo con la compu apagada y que salga solo al volver.
- Que arranque sola después de un reinicio real.
- **Buscar actualización** en el celu, y una actualización real entre versiones publicadas.
- Celus con Android 15 o más nuevo, y dos celus en la misma compu.
- Red local en Android (revisado el 2026-11-07 en developer.android.com): con `targetSdkVersion` 35 o 36 y el permiso `INTERNET`, Tachán sigue con acceso. Recién al apuntar a 37 (Android 17) hay que pedir `ACCESS_LOCAL_NETWORK` en el momento y manejar que digan que no.

- Mac: que arranque sola al iniciar sesión, Pegar solo (Accesibilidad, que con firma ad hoc puede volver a pedirse en cada versión), el aviso sobre una app a pantalla completa, y una Mac Intel.

**Por hacer:**
- Microsoft Store, para sacar el cartel de SmartScreen. Revisar las condiciones actuales antes de crear la cuenta.
- **Google Play exige `targetSdkVersion` 36 para apps nuevas desde el 2026-08-31.** Desde el 2026-11-08 la app apunta a 36 y compila con `platforms/android-36` y `build-tools/36.0.0` (69 KB, sin APIs obsoletas nuevas; el AAB se valida). Probada el 2026-11-08 en un celu con Android 12: llegaron una imagen y dos fotos compartidas desde otras apps, abre en 236-324 ms y el lector lee en 18-28 ms. Falta un celu con Android 16, que es donde se activan los cambios de la 36, y probar la cola. Lo que cambia con 36 casi no la toca: no usa la salida de pantalla completa forzada ni el botón atrás propio; solo el `portrait` del Lector deja de valer en tablets.
- Google Play: falta la cuenta (USD 25 una sola vez), un mail de contacto, los testers, capturas e ícono de 512 px. La ficha está en `tienda/`.
- **Confianza:** como está hecho con ayuda de IA, hay que dar pruebas de calidad. Hecho: revisión de seguridad (primera pasada hecha por IA, en `REVISION_SEGURIDAD.md`, con lo arreglado en la 1.3 y lo que queda), página `web/comprobar.html` (las fallas llegan por el reporte privado de GitHub de `kvothesson/tachan`; si cambia algo de lo que dice, actualizarla) y código abierto. Falta: que lo revise una persona de afuera y una compilación que se pueda comprobar contra el código.
- Verificación de desarrolladores (revisado el 2026-11-07 en developer.android.com/developer-verification): desde el 2026-09-30 rige en Brasil, Indonesia, Singapur y Tailandia, y en 2027 en todo el mundo, también para el APK de la web. Si Tachán va a Play, se registra desde la Play Console; si no, en la Android Developer Console. La cuenta gratis para aficionados llega solo a 20 aparatos, así que no alcanza. Sin registro, el usuario tiene que pasar por un camino avanzado para instalar. Decidir antes de 2027.
