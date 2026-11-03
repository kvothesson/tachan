package com.kvothesson.tachan;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.ClipData;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.database.Cursor;
import android.graphics.Bitmap;
import android.graphics.ImageDecoder;
import android.net.Uri;
import android.net.wifi.WifiManager;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.PowerManager;
import android.os.SystemClock;
import android.provider.OpenableColumns;
import android.text.format.DateUtils;
import android.text.format.Formatter;
import android.widget.Toast;

import java.io.ByteArrayInputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicInteger;

/** Manda en segundo plano con una notificación de avance: la pantalla queda libre. */
public class EnvioServicio extends Service {
    static final String CANAL = "envios";
    static final int NOTI_AVANCE = 1;
    static final int NOTI_RESULTADO = 2;
    static final int PUERTO_UDP = 47811;
    private static final int CALIDAD_JPEG = 95;
    private static final long INTERVALO_AVANCE_MS = 300;
    private static final long ESPERA_ESTIMADO_MS = 2000;
    private static final long PASO_ESTIMADO_S = 5;
    private static final long MAXIMO_DESPIERTO_MS = 60 * 60 * 1000L;

    private final ExecutorService hilo = Executors.newSingleThreadExecutor();
    private final AtomicInteger trabajos = new AtomicInteger();
    private long ultimoAvance;
    private int piezaActual;
    private long inicioPieza;
    private long ultimosBytes;
    private PowerManager.WakeLock procesador;
    private WifiManager.WifiLock wifi;

    static void iniciar(Context c, ArrayList<Uri> adjuntos, String texto) {
        if (adjuntos.isEmpty() && (texto == null || texto.isEmpty())) return;
        Intent i = new Intent(c, EnvioServicio.class);
        i.putExtra("texto", texto);
        i.putParcelableArrayListExtra("adjuntos", adjuntos);
        if (!adjuntos.isEmpty()) {
            // Sin esto, el permiso de lectura muere cuando se cierra la pantalla que lo recibió.
            ClipData clip = ClipData.newRawUri("", adjuntos.get(0));
            for (int n = 1; n < adjuntos.size(); n++) clip.addItem(new ClipData.Item(adjuntos.get(n)));
            i.setClipData(clip);
            i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        }
        if (Build.VERSION.SDK_INT >= 26) c.startForegroundService(i);
        else c.startService(i);
    }

    @Override public IBinder onBind(Intent intent) { return null; }

    @Override
    public int onStartCommand(Intent intent, int flags, final int idInicio) {
        crearCanal(this);
        getSystemService(NotificationManager.class).cancel(NOTI_RESULTADO);  // un error viejo no tiene que quedar al lado del envío nuevo
        Notification inicial = avance(getString(R.string.canal), 0, 0).build();
        if (Build.VERSION.SDK_INT >= 29) startForeground(NOTI_AVANCE, inicial, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC);
        else startForeground(NOTI_AVANCE, inicial);
        if (intent == null) {
            stopSelf(idInicio);
            return START_NOT_STICKY;
        }
        final ArrayList<Uri> adjuntos = intent.getParcelableArrayListExtra("adjuntos");
        final String texto = intent.getStringExtra("texto");
        trabajos.incrementAndGet();
        mantenerDespierto();
        hilo.execute(() -> {
            try { procesar(adjuntos, texto); }
            finally {
                if (trabajos.decrementAndGet() == 0) {
                    soltarDespierto();
                    stopForeground(true);
                    stopSelf();
                }
            }
        });
        return START_NOT_STICKY;
    }

    /** Al bloquear el celu, Android apaga el procesador y el wifi: un envío en curso se cortaría. Solo se pide mientras se manda. */
    private synchronized void mantenerDespierto() {
        if (procesador != null) return;
        procesador = getSystemService(PowerManager.class).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "tachan:envio");
        procesador.setReferenceCounted(false);
        procesador.acquire(MAXIMO_DESPIERTO_MS);
        wifi = ((WifiManager) getApplicationContext().getSystemService(Context.WIFI_SERVICE)).createWifiLock(WifiManager.WIFI_MODE_FULL_HIGH_PERF, "tachan:envio");
        wifi.setReferenceCounted(false);
        wifi.acquire();
    }

    private synchronized void soltarDespierto() {
        if (procesador == null) return;
        if (procesador.isHeld()) procesador.release();
        procesador = null;
        if (wifi.isHeld()) wifi.release();
        wifi = null;
    }

    @Override
    public void onDestroy() {
        soltarDespierto();
        super.onDestroy();
    }

    private void procesar(ArrayList<Uri> adjuntos, String texto) {
        Transporte.Compu compu = Almacen.compu(this);
        if (compu == null) return;
        List<Pieza> piezas = new ArrayList<>();
        if (adjuntos != null) for (Uri u : adjuntos) piezas.add(Pieza.deUri(this, u));
        if (piezas.isEmpty() && texto != null) piezas.add(Pieza.deTexto(texto));
        int hechas = 0;
        for (int i = 0; i < piezas.size(); i++) {
            Pieza p = piezas.get(i);
            final int orden = i + 1, total = piezas.size();
            try {
                p.prepararHeic(this);
                intentar(compu, p, bytes -> mostrarAvance(orden, total, p.largo, bytes));
                p.borrarTemporal();
                Almacen.agregarReciente(this, p.etiqueta(this));
                hechas++;
            } catch (SecurityException e) {
                // Se venció o nunca hubo permiso sobre el original: reintentar no lo va a arreglar.
                p.borrarTemporal();
                resultado(getString(R.string.fallo), true);
            } catch (Transporte.Rechazado e) {
                for (Pieza resto : piezas) resto.borrarTemporal();
                Almacen.olvidar(this);
                resultado(getString(R.string.revincular), true);
                return;
            } catch (IOException e) {
                // No está la compu: lo que falta queda en cola y sale solo cuando vuelva.
                for (Pieza resto : piezas.subList(i, piezas.size())) {
                    try { Cola.guardar(this, resto); }
                    catch (IOException | SecurityException noEntra) {
                        resultado(getString(R.string.fallo), true);
                        return;
                    }
                    finally { resto.borrarTemporal(); }
                }
                ReintentoJob.programar(this);
                resultado(getString(R.string.esperando), false);
                return;
            }
        }
        if (hechas > 0) avisarListo(getString(R.string.enviado_a, compu.nombre));
    }

    /** Si la compu cambió de dirección, la busca en la red y prueba una vez más. */
    private void intentar(Transporte.Compu compu, Pieza p, Transporte.Avance avance) throws IOException {
        try {
            try (InputStream in = p.abrir(this)) {
                Transporte.enviar(compu, in, p.largo, p.nombre, p.clase, avance);
            }
        } catch (Transporte.NoLlega e) {
            if (Transporte.descubrir(compu, PUERTO_UDP) == null) throw e;
            Almacen.guardar(this, compu);
            try (InputStream in = p.abrir(this)) {
                Transporte.enviar(compu, in, p.largo, p.nombre, p.clase, avance);
            }
        }
    }

    private void mostrarAvance(int orden, int total, long largo, long bytes) {
        long ahora = SystemClock.elapsedRealtime();
        if (ahora - ultimoAvance < INTERVALO_AVANCE_MS) return;
        ultimoAvance = ahora;
        if (orden != piezaActual || bytes < ultimosBytes) {
            piezaActual = orden;
            inicioPieza = ahora;
        }
        ultimosBytes = bytes;
        int porcentaje = largo > 0 ? (int) (bytes * 100 / largo) : 0;
        NotificationManager nm = getSystemService(NotificationManager.class);
        nm.notify(NOTI_AVANCE, avance(getString(R.string.enviando_n, orden, total), 100, porcentaje)
                .setContentText(detalle(largo, bytes, ahora - inicioPieza)).build());
    }

    /** "120 MB de 300 MB · faltan 0:40". El tiempo aparece cuando ya se puede estimar, redondeado para que no salte. */
    private String detalle(long largo, long bytes, long transcurridoMs) {
        if (largo <= 0) return Formatter.formatShortFileSize(this, bytes);
        String hecho = Formatter.formatShortFileSize(this, bytes), todo = Formatter.formatShortFileSize(this, largo);
        if (transcurridoMs < ESPERA_ESTIMADO_MS || bytes == 0) return getString(R.string.avance_parcial, hecho, todo);
        long segundos = (largo - bytes) * transcurridoMs / bytes / 1000;
        long redondeados = (segundos / PASO_ESTIMADO_S + 1) * PASO_ESTIMADO_S;
        return getString(R.string.avance_detalle, hecho, todo, DateUtils.formatElapsedTime(redondeados));
    }

    private Notification.Builder avance(String titulo, int maximo, int valor) {
        return base(this).setContentTitle(titulo).setOngoing(true).setOnlyAlertOnce(true).setProgress(maximo, valor, maximo == 0);
    }

    private void resultado(String texto, boolean abrirApp) {
        Notification.Builder b = base(this).setContentTitle(texto).setAutoCancel(true);
        if (abrirApp) {
            b.setContentIntent(PendingIntent.getActivity(this, 0, new Intent(this, Principal.class), PendingIntent.FLAG_IMMUTABLE));
        }
        getSystemService(NotificationManager.class).notify(NOTI_RESULTADO, b.build());
    }

    private void avisarListo(final String texto) {
        new Handler(Looper.getMainLooper()).post(() -> Toast.makeText(getApplicationContext(), texto, Toast.LENGTH_SHORT).show());
    }

    static Notification.Builder base(Context c) {
        Notification.Builder b = Build.VERSION.SDK_INT >= 26 ? new Notification.Builder(c, CANAL) : new Notification.Builder(c);
        return b.setSmallIcon(R.drawable.notificacion).setColor(c.getColor(R.color.kvo_accent));
    }

    static void crearCanal(Context c) {
        if (Build.VERSION.SDK_INT < 26) return;
        c.getSystemService(NotificationManager.class).createNotificationChannel(
                new NotificationChannel(CANAL, c.getString(R.string.canal), NotificationManager.IMPORTANCE_LOW));
    }

    /** Una cosa para mandar: archivo del celu, archivo en cola o texto. */
    static final class Pieza {
        Uri uri;
        File archivo;
        File temporal;
        byte[] texto;
        String nombre = "";
        String clase = "archivo";
        String mime;
        long largo = -1;

        static Pieza deTexto(String t) {
            Pieza p = new Pieza();
            p.texto = t.getBytes(StandardCharsets.UTF_8);
            p.largo = p.texto.length;
            p.clase = "texto";
            return p;
        }

        static Pieza deUri(Context c, Uri u) {
            Pieza p = new Pieza();
            p.uri = u;
            p.mime = c.getContentResolver().getType(u);
            try (Cursor cursor = c.getContentResolver().query(u, new String[]{OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE}, null, null, null)) {
                if (cursor != null && cursor.moveToFirst()) {
                    if (!cursor.isNull(0)) p.nombre = cursor.getString(0);
                    if (!cursor.isNull(1)) p.largo = cursor.getLong(1);
                }
            } catch (RuntimeException e) {
                // Algunas apps no informan: la compu le pone nombre y el largo se mide abajo.
            }
            return p;
        }

        /** Un texto puede ser una contraseña: en Recientes no se muestra. */
        String etiqueta(Context c) {
            if (texto != null) return c.getString(R.string.texto_enviado);
            return nombre.isEmpty() ? "…" : nombre;
        }

        InputStream abrir(Context c) throws IOException {
            if (texto != null) return new ByteArrayInputStream(texto);
            if (archivo != null) return new FileInputStream(archivo);
            if (largo < 0) copiarAMemoriaInterna(c);
            if (archivo != null) return new FileInputStream(archivo);
            InputStream in = c.getContentResolver().openInputStream(uri);
            if (in == null) throw new IOException("no se pudo abrir");
            return in;
        }

        private void copiarAMemoriaInterna(Context c) throws IOException {
            File destino = File.createTempFile("envio", null, c.getCacheDir());
            try (InputStream in = c.getContentResolver().openInputStream(uri);
                 OutputStream out = new FileOutputStream(destino)) {
                if (in == null) throw new IOException("no se pudo abrir");
                byte[] trozo = new byte[64 * 1024];
                int n;
                while ((n = in.read(trozo)) != -1) out.write(trozo, 0, n);
            }
            archivo = destino;
            temporal = destino;
            largo = destino.length();
        }

        void borrarTemporal() {
            if (temporal != null) temporal.delete();
            temporal = null;
        }

        /** Windows casi nunca abre HEIC: va como JPEG para que se vea y se pegue. */
        void prepararHeic(Context c) {
            if (uri == null || mime == null || Build.VERSION.SDK_INT < 28) return;
            if (!mime.equalsIgnoreCase("image/heic") && !mime.equalsIgnoreCase("image/heif")) return;
            try {
                Bitmap imagen = ImageDecoder.decodeBitmap(ImageDecoder.createSource(c.getContentResolver(), uri));
                File destino = File.createTempFile("heic", ".jpg", c.getCacheDir());
                try (OutputStream out = new FileOutputStream(destino)) {
                    imagen.compress(Bitmap.CompressFormat.JPEG, CALIDAD_JPEG, out);
                }
                imagen.recycle();
                archivo = destino;
                temporal = destino;
                largo = destino.length();
                int punto = nombre.lastIndexOf('.');
                nombre = (punto > 0 ? nombre.substring(0, punto) : "foto") + ".jpg";
            } catch (IOException | OutOfMemoryError e) {
                // va el original
            }
        }
    }
}
