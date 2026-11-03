# Revisión de seguridad de Tachán 1.2

Fecha: 2026-11-02. Sobre el código de la versión 1.2 de este repo. **No publicar hasta que la 1.3 esté en línea:** describe cómo aprovechar fallas de la 1.2, que es la que usa la gente hoy.

**Quién la hizo:** Claude, la misma IA que ayudó a escribir el código, así que no cuenta como revisión independiente. Sirve para encontrar y arreglar fallas, pero para generar confianza hace falta que la mire una persona de afuera.

## Estado en la versión 1.3 (compilada, sin publicar)

| # | Arreglo | Comprobado | Lo que queda |
|---|---|---|---|
| 1 | Solo acepta direcciones privadas, la confirmación muestra la dirección y avisa si reemplaza a otra compu | Enlace público rechazado, en prueba. Pantalla sin ver | Alguien en tu misma red todavía puede armar un link falso, y lo que estaba en cola se iría a la compu nueva |
| 2 | `version.json` lleva una firma de una llave que no está en el sitio | `pruebas/prueba_firma.py`: 5 casos malos no bajan el exe y el bueno sí | La primera descarga sigue dependiendo del sitio. La 1.2 instalada no verifica firma, así que recién protege desde la 1.3 |
| 3 | Pegar solo ya no aprieta Ctrl+V si el texto tiene saltos de línea | Sin probar: la prueba apretaría teclas en la ventana activa | Otra app del celu todavía puede mandar cosas y cambiar el portapapeles |
| 4 | Se rechaza `file://` | Sin probar en un celu | Nada conocido |
| 5 | `Impostor` ya no desvincula ni borra la cola. La búsqueda solo acepta a quien muestra el certificado | Respuesta UDP falsa rechazada, en prueba. Que el celu conserve el vínculo, sin probar | Mientras dure, nada sale: queda en cola y el estado lo dice en la app |
| 6 | Plazo de 10 segundos para la cabecera y 4 conexiones por dirección, de 16 en total | Conexiones lentas cortadas en 9 s, otra dirección atendida, en prueba | Hacen falta varias máquinas para ocupar los 16 lugares. Los intentos fallidos todavía pueden invalidar el QR abierto |
| 7 | Se sacan los caracteres invisibles del nombre | Sin probar | Nada conocido |
| 8 | Recientes muestra "Texto" | Sin probar en un celu | Un texto en cola sigue guardado sin cifrar en la memoria privada de la app hasta salir |
| 9 | Se pide no subir a la nube de Windows | Marca leída del portapapeles, en prueba | El historial local sigue activo si lo usás: se dejó así a propósito |
| 10 | La página de privacidad lo dice | Texto agregado, sin publicar | La web sigue usando las fuentes de Google |

`pruebas/prueba_e2e.py` da todo bien con la 1.3 en la compu.

**En un celu real (2026-11-02), con la 1.3 instalada encima de la 1.2:** el vínculo siguió, un texto mandado figura como "Texto" en Recientes (falla 8), y un pedido con `file:///system/etc/hosts` no dejó ningún archivo en Descargas ni entrada en Recientes (falla 4). **Sin aclarar:** ese texto no estaba en el portapapeles de la compu a los 6 segundos. Otra sesión estaba cambiando y reinstalando el programa de la compu en ese momento, así que hay que repetirlo con la compu quieta. La pantalla de confirmación del link y la falla 5 siguen sin probar en el celu.

El detalle de abajo describe la 1.2.

## Qué falla

Las pruebas corrieron con una instancia aislada (`TACHAN_DATOS`, puerto 47950). No se usó el celu de la persona ni un emulador.

| # | Gravedad | Qué pasa | Quién puede | Comprobado |
|---|---|---|---|---|
| 1 | Alta | Un link falso vincula el celu a una máquina ajena, incluso por internet | Quien logre que toques un link y confirmes | Parte con prueba, parte leyendo |
| 2 | Alta | Una actualización falsa corre en la compu | Quien controle el sitio o la cuenta de GitHub | Leyendo el código |
| 3 | Media | Cualquier app del celu manda cosas a la compu sin que toques nada | Una app maliciosa instalada en el celu | Leyendo, sin probar en un celu |
| 4 | Media | Esa app puede hacer que Tachán mande sus propios datos privados, con el token, a la compu | Una app maliciosa instalada en el celu | Leyendo, sin probar en un celu |
| 5 | Media | Se puede desvincular el celu a distancia y borrar lo que esperaba para salir | Alguien en la misma red | Parte con prueba, parte leyendo |
| 6 | Media | Ocho conexiones lentas dejan a la compu sin recibir nada | Alguien en la misma red, sin vínculo | Con prueba |
| 7 | Baja | Un nombre de archivo puede disfrazar su extensión | Un celu ya vinculado | Leyendo el código |
| 8 | Baja | Lo primero de cada texto enviado queda a la vista en el celu | Quien tenga el celu en la mano | Leyendo el código |
| 9 | Baja | El texto recibido puede entrar al historial y a la nube del portapapeles de Windows | Depende de cómo esté configurado Windows | Leyendo el código |
| 10 | Baja | La web le pide las fuentes a Google y la página de privacidad no lo dice | Google ve la IP de quien entra | Leyendo el código |

### 1. Link falso que vincula a otra máquina

`Transporte.leerEnlace` acepta cualquier dirección IPv4, también públicas. El nombre que muestra la pantalla de confirmación sale del mismo link. Una página web puede abrir `tachan://` o `intent://`, y con un toque en Vincular `Almacen.guardar` reemplaza la compu que ya estaba, sin avisar.

Desde ahí, todo lo que compartís va a esa máquina. Eso contradice "por tu red local" de la página de privacidad.

**Prueba:** un enlace con 203.0.113.7 y `n=Mi compu` se acepta y muestra "Mi compu". El reemplazo se comprobó leyendo `Principal.vincular`, sin ejecutarlo.

**Arreglo:** aceptar solo direcciones privadas, mostrar la dirección en la confirmación y avisar si ya hay una compu vinculada.

### 2. Actualización sin firma

`Actualizador.Buscar` baja el exe y su SHA-256 del mismo sitio y lo ejecuta. El hash detecta una descarga rota, pero no a alguien que controle el sitio. El celu no tiene este problema: Android rechaza un APK con otra llave.

**Arreglo:** firmar `version.json` o el exe con una llave guardada fuera del sitio, y traer la clave pública dentro del programa. La primera descarga sigue dependiendo del sitio hasta que el exe tenga firma de código o esté en Microsoft Store.

### 3. Mandar sin que toques nada

`Compartir` tiene que estar `exported` para aparecer al compartir, y eso también deja que otra app la llame directamente. Lo que llega reemplaza el portapapeles de la compu. Si está activado **pegar solo**, además se aprieta Ctrl+V en la ventana activa: un texto con un salto de línea puede ejecutarse en una terminal abierta.

Se ve el aviso y suena el ta-chán, así que no pasa del todo desapercibido. Android no da una forma simple de distinguir un compartir real de uno lanzado por otra app.

**Arreglo:** no pegar solo los textos con saltos de línea, y sumar en esa opción una advertencia.

### 4. Tachán manda sus propios archivos

`Compartir.adjuntos` no filtra el tipo de dirección. `getContentResolver().openInputStream` abre `file://` con los permisos de Tachán, así que `file:///data/data/com.kvothesson.tachan/shared_prefs/tachan.xml` terminaría en `Descargas\Tachan` con el token adentro. El destino sigue siendo tu propia compu, y por eso no es grave solo.

**Arreglo:** rechazar `file://` y cualquier `content://` de la propia app.

### 5. Desvincular a distancia

La búsqueda por UDP acepta cualquier respuesta. El certificado fijado hace bien su trabajo y frena el envío, así que el token no se filtra. El problema es qué hace después: `Impostor` llama a `Almacen.olvidar` en `Principal.revisarPunto`, `EnvioServicio.procesar` y `Cola.procesar`, y esta última también borra la cola.

**Prueba:** una respuesta UDP falsa cambió la dirección guardada en memoria y `hola` terminó en `Impostor`. El olvido y el borrado se comprobaron leyendo el código.

**Arreglo:** ante `Impostor`, no olvidar ni borrar. Mantener el vínculo y la cola, avisar y volver a buscar. Solo `Rechazado` debe desvincular.

### 6. Conexiones lentas

El servidor atiende 8 conexiones a la vez, y `LeerCabecera` deja que cada una dure mientras mande un byte cada menos de 30 segundos.

**Prueba:** con 8 conexiones sin credenciales, cada conexión nueva se cortó durante los 60 segundos que duró la prueba. Al soltarlas, volvió a responder. No se filtra nada, pero tampoco llega nada.

En la misma línea, 5 intentos fallidos invalidan el QR abierto, y alguien en la red puede repetirlo. Esto se comprobó solo leyendo el código.

**Arreglo:** poner un plazo total para la cabecera, de unos 10 segundos, y un límite de conexiones por dirección.

### 7 a 10. Menores

- **Extensión disfrazada:** `NombreSeguro` no saca caracteres invisibles de dirección como U+202E. El doble clic no abre programas y Windows avisa por la marca de internet. **Arreglo:** sacarlos.
- **Textos a la vista:** `Pieza.deTexto` usa los primeros 60 caracteres como nombre. Quedan en Recientes y en el `.meta` de la cola, también si mandaste una contraseña. **Arreglo:** mostrar solo "Texto".
- **Portapapeles de Windows:** `Portapapeles.Copiar` no excluye el texto del historial ni de la sincronización. Es una decisión de producto, porque a algunos les puede servir tenerlo.
- **Fuentes de Google:** `web/index.html` y `web/privacidad.html` las cargan desde Google. **Arreglo:** servirlas desde el sitio o decirlo en privacidad.

## Qué está bien

Comprobado leyendo el código. Lo marcado con * también lo cubre `pruebas/prueba_e2e.py`, que no se corrió en esta revisión.

- Fijación de la huella del certificado en cada conexión, sin autoridades ni nombres de host. *
- Token de 256 bits. La compu guarda solo su hash y lo compara en tiempo constante. *
- Secreto del QR de 48 bits, de un solo uso, con 5 intentos y renovación a los 5 minutos. *
- Nombres de archivo sin rutas, sin flujos alternativos de NTFS y sin nombres reservados. *
- Marca de internet en lo recibido, y un programa nunca se abre con doble clic desde el aviso. *
- Certificado de la compu protegido por Windows para ese usuario (DPAPI).
- Sin copia de seguridad en Android y sin tráfico sin cifrar.
- Regla de firewall limitada a la subred local.
- Los archivos de prueba solo se escriben con `TACHAN_DATOS`.
- La app solo sale a internet al tocar Buscar actualización: no hay otras conexiones a internet en el código leído.

## Qué no se revisó

- `Lector`, `QrLector`, `Qr` y la mayor parte de `Aviso` y `Principal`.
- Pruebas con datos al azar sobre el protocolo y las imágenes. Los decodificadores de imágenes de Windows procesan lo que manda un celu vinculado.
- Las pruebas 3, 4 y 7 no se ejecutaron en un aparato real.
- La seguridad de la cuenta de GitHub y del dominio.
- Los cifrados TLS que negocia cada versión de Windows.
- Celus y versiones de Windows distintos de los de la persona.

## Orden de arreglo propuesto

1. Fallas 1, 4, 5 y 6, y lo de pegar solo de la 3: son cambios chicos en el código.
2. Falla 2: la firma necesita una llave nueva, guardada aparte, y hacer el cambio con cuidado.
3. Fallas 7, 8 y 10, más la decisión sobre la 9.
4. Sacar la versión 1.3 con lo anterior, previo OK de la persona para publicar.
5. Pedirle a una persona técnica de afuera que revise el resultado.
