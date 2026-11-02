package com.kvothesson.tachan;

import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.Arrays;

/** Corre el lector sobre las imágenes crudas que arma pruebas/prueba_lector.py: nombre_ANCHOxALTO.raw */
public class PruebaLector {
    public static void main(String[] args) throws Exception {
        File carpeta = new File(args[0]);
        String esperado = new String(Files.readAllBytes(new File(args[1]).toPath()), StandardCharsets.UTF_8);
        File[] crudos = carpeta.listFiles((d, n) -> n.endsWith(".raw"));
        Arrays.sort(crudos);
        int bien = 0;
        for (File f : crudos) {
            String n = f.getName().replace(".raw", "");
            String[] medida = n.substring(n.lastIndexOf('_') + 1).split("x");
            long t0 = System.nanoTime();
            String leido = QrLector.leer(Files.readAllBytes(f.toPath()), Integer.parseInt(medida[0]), Integer.parseInt(medida[1]));
            long ms = (System.nanoTime() - t0) / 1000000;
            boolean ok = esperado.equals(leido);
            boolean debeLeer = !n.startsWith("sin_qr");
            boolean paso = debeLeer ? ok : leido == null;
            if (paso) bien++;
            System.out.println((paso ? "OK    " : "FALLA ") + n + "  " + ms + " ms");
        }
        System.out.println(bien == crudos.length ? "TODO BIEN " + bien : "FALLAS: " + (crudos.length - bien) + " de " + crudos.length);
    }
}
