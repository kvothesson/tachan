package com.kvothesson.tachan;

import java.io.File;
import java.nio.file.Files;
import java.util.Arrays;

/** Mide cuánto tarda el lector por cuadro en el procesador del celu. Se corre con dalvikvm desde pruebas/medir_celu.py. */
public class MedirLector {
    public static void main(String[] args) throws Exception {
        File[] crudos = new File(args[0]).listFiles((d, n) -> n.endsWith(".raw"));
        Arrays.sort(crudos);
        for (File f : crudos) {
            String n = f.getName().replace(".raw", "");
            String[] medida = n.substring(n.lastIndexOf('_') + 1).split("x");
            byte[] cuadro = Files.readAllBytes(f.toPath());
            int w = Integer.parseInt(medida[0]), h = Integer.parseInt(medida[1]);
            long[] tiempos = new long[15];
            String leido = null;
            for (int i = 0; i < tiempos.length; i++) {
                long t0 = System.nanoTime();
                leido = QrLector.leer(cuadro, w, h);
                tiempos[i] = (System.nanoTime() - t0) / 1000000;
            }
            Arrays.sort(tiempos);
            System.out.println(n + ": mediana " + tiempos[7] + " ms, peor " + tiempos[14] + " ms, " + (leido != null ? "leyó" : "sin lectura"));
        }
    }
}
