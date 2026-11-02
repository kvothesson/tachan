# Tachán

Compartís algo en el celu y aparece en la compu: fotos, videos, archivos, texto y links, por el wifi de casa y sin pasar por ningún servidor.

Al llegar queda copiado para Ctrl+V y aparece un aviso que no te saca de donde estás. Del aviso se arrastra, y se va solo en 6 segundos.

## Partes

- `pc/`: programa de Windows, un `.exe` de unos 80 KB en C# sobre .NET 4.8, que ya viene con Windows. Compilar: `python pc/compilar.py`.
- `android/`: la app, sin Gradle ni librerías. Compilar: `python android/compilar.py`; con `--tienda` también sale el AAB para Google Play.
- `android/src/.../Transporte.java`: el protocolo, en Java puro para poder probarlo contra el `.exe`.
- `android/src/.../QrLector.java` y `Lector.java`: el lector de QR propio, sin librerías. La cámara de cada marca abre distinto los enlaces `tachan://`.
- `diseno/`: el sonido de llegada y el primer boceto de pantallas. El diseño vigente sale del taller, en `D:\workspace\kvothesson\marca`. `pc/MarcaColores.cs`, `pc/marca.json` y `android/res/values*/marca.xml` se generan con `python marca/generar.py` y no se editan a mano.
- `web/`: la página y la privacidad para kvothesson.com/tachan, sin publicar. `tienda/`: la ficha de Google Play en 6 idiomas.
- `pruebas/`: `medir_envio.py` (envío real por el selector de fotos, con el celu bloqueado), `medir_velocidad.py` (el protocolo solo), `medir_celu.py` (arranque y lector), `prueba_memoria.py` (memoria y recursos con muchas fotos), `prueba_copia.py` (portapapeles, sin mover el mouse), `prueba_lector.py` (el QR real deformado como lo ve una cámara), `prueba_e2e.py` (protocolo y seguridad) y `prueba_pc.py` (aviso, portapapeles, arrastre, pegado). Usan datos aislados con `TACHAN_DATOS`.
- `receptor.py`, `pagina.html`, `abrir.cmd`, `instalar.cmd`: la primera versión en Python. Quedan hasta probar la nueva en un celu real.

## Seguridad

- Se vincula con un QR que dura 5 minutos, sirve una sola vez y se invalida tras 5 intentos fallidos. Siempre pide confirmar en el celu.
- Todo va cifrado con TLS. El celu fija la huella del certificado de la compu: si otra máquina ocupa su dirección, no le manda nada, ni el token.
- Cada celu tiene su token, y en la compu solo se guarda el hash. Se puede desvincular desde cualquiera de los dos.
- El firewall admite solo equipos de la misma red.
- Un archivo recibido nunca se abre solo. Solo los medios se abren con doble clic, y Windows trata lo recibido como bajado de internet. Un link solo se abre si tocás la flecha.

## Nombre

En pantalla es Tachán; en tiendas, rutas y código, Tachan. La web va en kvothesson.com/tachan. El `package` `com.kvothesson.tachan` no se puede cambiar después de publicar.

## Antes de publicar

- Probar en celus reales: nada de la parte Android con pantalla se ejecutó todavía.
- Android 15 en adelante y exigencias de Play: revisar el `targetSdk` que pida Google en ese momento y el permiso de red local.
- Declarar en Play el uso de `FOREGROUND_SERVICE_DATA_SYNC`, y publicar una política de privacidad.
- Firmar el `.exe` o publicarlo en Microsoft Store para evitar el aviso de SmartScreen.
- La llave de subida está en `~/.tachan/`, fuera del repo: hacerle una copia de seguridad. Usar Play App Signing, así Google guarda la llave final y la de subida se puede reemplazar.
