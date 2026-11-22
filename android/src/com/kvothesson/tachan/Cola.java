package com.kvothesson.tachan;

import android.app.NotificationManager;
import android.content.Context;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.HashSet;
import java.util.Set;

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

    /** Cada pieza recuerda a qué compu iba, en un .compu al lado: si hay dos vinculadas, no sale para la otra. */
    static void guardar(Context c, EnvioServicio.Pieza p, Transporte.Compu compu) throws IOException {
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
        try (OutputStream out = new FileOutputStream(base.getPath() + ".compu")) {
            out.write(compu.huella.getBytes(StandardCharsets.UTF_8));
        }
    }

    /** Devuelve true si no queda nada pendiente. */
    static boolean procesar(Context c) {
        File[] lista = carpeta(c).listFiles((d, n) -> n.endsWith(".meta"));
        if (lista == null || lista.length == 0) return true;
        if (Almacen.compu(c) == null) {
            borrarTodo(c);  // sin vínculo no hay a quién mandarle
            return true;
        }
        Arrays.sort(lista);
        Set<String> apagadas = new HashSet<>();
        for (File meta : lista) {
            String base = meta.getPath().replaceAll("\\.meta$", "");
            File datos = new File(base + ".dat"), destino = new File(base + ".compu");
            Transporte.Compu compu;
            try {
                // Lo encolado antes de la 1.5 no dice compu: va a la única que había.
                compu = destino.exists() ? Almacen.compu(c, new String(leerTodo(destino), StandardCharsets.UTF_8)) : Almacen.compu(c);
            } catch (IOException e) {
                compu = null;
            }
            if (compu == null) {
                borrar(datos, meta, destino);  // esa compu se desvinculó
                continue;
            }
            if (apagadas.contains(compu.huella)) continue;  // lo de una compu sale en orden: si falló una cosa, espera todo
            try {
                String[] partes = new String(leerTodo(meta), StandardCharsets.UTF_8).split("\n", 2);
                String nombre = partes.length > 1 ? partes[1] : "";
                try (InputStream in = new FileInputStream(datos)) {
                    enviarConBusqueda(c, compu, in, datos, nombre, partes[0]);
                }
                Almacen.agregarReciente(c, etiqueta(c, partes[0], nombre), compu);
                Almacen.usar(c, compu);
                borrar(datos, meta, destino);
            } catch (Transporte.Rechazado e) {
                Almacen.olvidar(c, compu);
                borrar(datos, meta, destino);
            } catch (IOException e) {
                apagadas.add(compu.huella);
            }
        }
        return apagadas.isEmpty();
    }

    /** Algo que espera en la cola, para mostrarlo y poder cancelarlo. */
    static final class Pendiente {
        String id;
        String nombre;
        String compu;
    }

    /** Lo que espera, en el orden en que va a salir. */
    static List<Pendiente> pendientes(Context c) {
        List<Pendiente> lista = new ArrayList<>();
        File[] metas = carpeta(c).listFiles((d, n) -> n.endsWith(".meta"));
        if (metas == null) return lista;
        Arrays.sort(metas);
        for (File meta : metas) {
            String base = meta.getPath().replaceAll("\\.meta$", "");
            try {
                String[] partes = new String(leerTodo(meta), StandardCharsets.UTF_8).split("\n", 2);
                File destino = new File(base + ".compu");
                Transporte.Compu compu = destino.exists() ? Almacen.compu(c, new String(leerTodo(destino), StandardCharsets.UTF_8)) : Almacen.compu(c);
                if (compu == null) continue;  // se borra en la próxima vuelta: esa compu ya no está
                Pendiente p = new Pendiente();
                p.id = new File(base).getName();
                p.nombre = etiqueta(c, partes[0], partes.length > 1 ? partes[1] : "");
                p.compu = compu.nombre;
                lista.add(p);
            } catch (IOException e) {
                // a medio escribir: aparece en la próxima
            }
        }
        return lista;
    }

    /** Lo saca de la cola. Si no queda nada, tampoco queda el aviso de que espera. */
    static void cancelar(Context c, String id) {
        if (!id.matches("[0-9_-]+")) return;
        File base = new File(carpeta(c), id);
        borrar(new File(base.getPath() + ".meta"), new File(base.getPath() + ".dat"), new File(base.getPath() + ".compu"));
        if (pendientes(c).isEmpty()) {
            c.getSystemService(NotificationManager.class).cancel(EnvioServicio.NOTI_RESULTADO);
            ReintentoJob.cancelar(c);
        }
    }

    private static String etiqueta(Context c, String clase, String nombre) {
        return "texto".equals(clase) ? c.getString(R.string.texto_enviado) : nombre.isEmpty() ? "…" : nombre;
    }

    private static void borrar(File... archivos) {
        for (File f : archivos) f.delete();
    }

    private static void enviarConBusqueda(Context c, Transporte.Compu compu, InputStream in, File datos, String nombre, String clase) throws IOException {
        try {
            Transporte.enviar(compu, in, datos.length(), nombre, clase, null, true);
        } catch (Transporte.NoLlega e) {
            if (Transporte.descubrir(compu, EnvioServicio.PUERTO_UDP) == null) throw e;
            Almacen.actualizar(c, compu);
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
