# Tachán

Compartís algo en el celu y aparece en la compu: fotos, videos, archivos, texto y links, por el wifi de casa y sin pasar por ningún servidor.

Al llegar queda copiado para Ctrl+V y aparece un aviso que no te saca de donde estás. Del aviso se arrastra, y se va solo en 6 segundos.

**Para usarlo:** https://kvothesson.com/tachan/ (Android y Windows, gratis, sin cuenta).

Este es el código completo de las dos apps y de la web. Está abierto para que cualquiera pueda comprobar qué hace: sin servidores, sin rastreo y sin dependencias.

## Partes

- `pc/`: programa de Windows, un `.exe` de unos 80 KB en C# sobre .NET 4.8, que ya viene con Windows. Al abrirlo se instala solo en `%LOCALAPPDATA%\Programs\Tachan`, y abrir una versión distinta lo actualiza. Compilar: `python pc/compilar.py`.
- `android/`: la app, sin Gradle ni librerías. Compilar: `python android/compilar.py`; con `--tienda` también sale el AAB para Google Play.
- `android/src/.../Transporte.java`: el protocolo, en Java puro para poder probarlo contra el `.exe`.
- `android/src/.../QrLector.java` y `Lector.java`: el lector de QR propio, sin librerías. La cámara de cada marca abre distinto los enlaces `tachan://`, por eso el QR es un link web.
- `diseno/`: el sonido de llegada y el primer boceto de pantallas. Los colores (`pc/MarcaColores.cs`, `pc/marca.json`, `web/marca.css` y `android/res/values*/marca.xml`) se generan desde un sistema de marca que vive fuera de este repo, y no se editan a mano.
- `web/`: la página y la privacidad. Se publica en kvothesson.com/tachan con `python publicar_web.py`: al subir un cambio de esta carpeta, GitHub la despliega sola (`.github/workflows/web.yml`). Las descargas salen de las releases de este repo. `tienda/`: la ficha de Google Play en 6 idiomas.
- `pruebas/`: `medir_envio.py` (envío real por el selector de fotos, con el celu bloqueado), `medir_velocidad.py` (el protocolo solo), `medir_celu.py` (arranque y lector), `prueba_memoria.py` (memoria y recursos con muchas fotos), `prueba_copia.py` (portapapeles, sin mover el mouse), `prueba_arriba.py` (el aviso sobre una ventana a pantalla completa), `prueba_buscar_version.py` (Buscar actualización contra una web local), `prueba_aviso_imagen.py` (imágenes altas, anchas y transparentes, enteras), `prueba_actualizar.py` (reemplaza la instalación real, sin perder vínculos), `prueba_lector.py` (el QR real deformado como lo ve una cámara), `prueba_e2e.py` (protocolo y seguridad) y `prueba_pc.py` (aviso, portapapeles, arrastre, pegado). Usan datos aislados con `TACHAN_DATOS`.

## Compilar

Solo en Windows. No hay Gradle ni paquetes que bajar.

- **Compu:** hace falta Python 3 y el compilador de C# de Visual Studio 2022 Build Tools. `python pc/compilar.py` deja el exe en `pc/compilado/`.
- **Celu:** hace falta el SDK de Android (plataforma y build-tools 36) y un JDK 17. Las rutas están arriba de `android/compilar.py`: cambialas por las tuyas. `python android/compilar.py` deja un APK firmado con una llave de desarrollo que se crea sola.

Un APK compilado por vos no se instala encima del oficial, porque la firma es otra: hay que desinstalar y volver a vincular. Las llaves de publicación no están en el repo.

## Seguridad

- Se vincula con un QR que dura 5 minutos, sirve una sola vez y se invalida tras 5 intentos fallidos. Siempre pide confirmar en el celu.
- Todo va cifrado con TLS. El celu fija la huella del certificado de la compu: si otra máquina ocupa su dirección, no le manda nada, ni el token.
- Cada celu tiene su token, y en la compu solo se guarda el hash. Se puede desvincular desde cualquiera de los dos.
- El firewall admite solo equipos de la misma red.
- Un archivo recibido nunca se abre solo. Solo los medios se abren con doble clic, y Windows trata lo recibido como bajado de internet. Un link solo se abre si tocás la flecha.

`REVISION_SEGURIDAD.md` tiene la revisión hecha sobre la 1.2, lo que se arregló en la 1.3 y lo que queda. La hizo una IA, así que todavía falta una mirada de afuera: si sabés del tema, sos bienvenido.

**Si encontrás una falla de seguridad,** avisá en privado por https://github.com/kvothesson/tachan/security/advisories/new y no en un issue público.

## Aportar

Los errores y las ideas van en los issues de este repo, y los cambios por pull request. Tachán hace una sola cosa y pesa menos de 100 KB por lado: los cambios que suman dependencias, cuentas, servidores o conexiones a internet no entran.

Está hecho con ayuda de IA (Claude). `AGENTS.md` es la guía que usa para trabajar acá, y sirve igual para una persona.

## Licencia

GPLv3: ver `LICENSE`. Podés usarlo, estudiarlo y cambiarlo; si repartís una versión cambiada, tiene que seguir abierta con la misma licencia. Si repartís una versión cambiada, ponele otro nombre e ícono, así no se confunde con la original.

## Nombre

En pantalla es Tachán; en tiendas, rutas y código, Tachan. El `package` `com.kvothesson.tachan` no se puede cambiar después de publicar en Google Play.

Para trabajar en el repo, ver `AGENTS.md`: tiene decisiones, pruebas, cómo publicar y qué falta.
