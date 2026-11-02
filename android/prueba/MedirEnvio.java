package com.kvothesson.tachan;

import java.io.ByteArrayInputStream;
import java.io.FileInputStream;
import java.io.InputStream;
import java.util.Random;

/** Corre el envío real en el celu, sin pantalla ni servicio, para separar qué parte tarda. Lo lanza pruebas/medir_velocidad.py. */
public class MedirEnvio {
    static void medir(String etiqueta, Transporte.Compu c, InputStream in, long largo) throws Exception {
        long t0 = System.nanoTime();
        long[] ultimo = {0};
        Transporte.enviar(c, in, largo, etiqueta + ".bin", "archivo", n -> ultimo[0] = n);
        double s = (System.nanoTime() - t0) / 1e9;
        System.out.printf("%s: %.0f MB en %.1f s = %.2f MB/s%n", etiqueta, largo / 1048576.0, s, largo / 1048576.0 / s);
    }

    public static void main(String[] a) throws Exception {
        Transporte.Compu c = Transporte.vincular(Transporte.leerEnlace(a[0]), "medir");
        int mb = Integer.parseInt(a[1]);
        byte[] datos = new byte[mb * 1048576];
        new Random(7).nextBytes(datos);
        medir("desde_memoria", c, new ByteArrayInputStream(datos), datos.length);
        medir("desde_memoria_2", c, new ByteArrayInputStream(datos), datos.length);
        java.io.File f = new java.io.File(a[2]);
        medir("desde_archivo", c, new FileInputStream(f), f.length());
    }
}
