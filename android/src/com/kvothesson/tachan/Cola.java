package com.kvothesson.tachan;

import android.content.Context;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;

/** Lo que no pudo salir: copia privada de cada cosa, porque el permiso sobre el original se vence. */
final class Cola {
    private static final long MAXIMO_BYTES = 2L * 1024 * 1024 * 1024;

    private Cola() {}

    private static File carpeta(Context c) {
        File d = new File(c.getFilesDir(), "cola");
        d.mkdirs();
        return d;
    }

    private static long ocupado(Context c) {
        long total = 0;
        File[] lista = carpeta(c).listFiles();
        if (lista != null) for (File f : lista) total += f.length();
        return total;
    }

    static void guardar(Context c, EnvioServicio.Pieza p) throws IOException {
        File base = new File(carpeta(c), System.currentTimeMillis() + "_" + System.nanoTime());
        File datos = new File(base.getPath() + ".dat");
        long copiados = 0;
        long disponible = MAXIMO_BYTES - ocupado(c);
        try (InputStream in = p.abrir(c); OutputStream out = new FileOutputStream(datos)) {
            byte[] trozo = new byte[64 * 1024];
            int n;
            while ((n = in.read(trozo)) != -1) {
                copiados += n;
                if (copiados > disponible) throw new IOException("la cola está llena");
                out.write(trozo, 0, n);
            }
        } catch (IOException e) {
            datos.delete();
            throw e;
        }
        try (OutputStream out = new FileOutputStream(base.getPath() + ".meta")) {
            out.write((p.clase + "\n" + p.nombre).getBytes(StandardCharsets.UTF_8));
        }
    }

    /** Devuelve true si no queda nada pendiente. */
    static boolean procesar(Context c) {
        Transporte.Compu compu = Almacen.compu(c);
        File[] lista = carpeta(c).listFiles((d, n) -> n.endsWith(".meta"));
        if (lista == null || lista.length == 0) return true;
        if (compu == null) {
            borrarTodo(c);  // sin vínculo no hay a quién mandarle
            return true;
        }
        Arrays.sort(lista);
        for (File meta : lista) {
            File datos = new File(meta.getPath().replaceAll("\\.meta$", ".dat"));
            try {
                String[] partes = new String(leerTodo(meta), StandardCharsets.UTF_8).split("\n", 2);
                String nombre = partes.length > 1 ? partes[1] : "";
                try (InputStream in = new FileInputStream(datos)) {
                    enviarConBusqueda(c, compu, in, datos, nombre, partes[0]);
                }
                Almacen.agregarReciente(c, "texto".equals(partes[0]) ? c.getString(R.string.texto_enviado) : nombre.isEmpty() ? "…" : nombre);
                datos.delete();
                meta.delete();
            } catch (Transporte.Rechazado e) {
                Almacen.olvidar(c);
                borrarTodo(c);
                return true;
            } catch (IOException e) {
                return false;
            }
        }
        return true;
    }

    private static void enviarConBusqueda(Context c, Transporte.Compu compu, InputStream in, File datos, String nombre, String clase) throws IOException {
        try {
            Transporte.enviar(compu, in, datos.length(), nombre, clase, null, true);
        } catch (Transporte.NoLlega e) {
            if (Transporte.descubrir(compu, EnvioServicio.PUERTO_UDP) == null) throw e;
            Almacen.guardar(c, compu);
            try (InputStream otra = new FileInputStream(datos)) {
                Transporte.enviar(compu, otra, datos.length(), nombre, clase, null, true);
            }
        }
    }

    private static void borrarTodo(Context c) {
        File[] lista = carpeta(c).listFiles();
        if (lista != null) for (File f : lista) f.delete();
    }

    private static byte[] leerTodo(File f) throws IOException {
        byte[] d = new byte[(int) f.length()];
        try (InputStream in = new FileInputStream(f)) {
            int leidos = 0, n;
            while (leidos < d.length && (n = in.read(d, leidos, d.length - leidos)) > 0) leidos += n;
        }
        return d;
    }
}
