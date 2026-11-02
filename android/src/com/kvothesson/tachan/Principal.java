package com.kvothesson.tachan;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.ClipData;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.pm.ShortcutInfo;
import android.content.pm.ShortcutManager;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.Icon;
import android.graphics.drawable.RippleDrawable;
import android.content.res.ColorStateList;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.DocumentsContract;
import android.text.InputType;
import android.text.TextUtils;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import java.io.IOException;
import java.net.URL;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import javax.net.ssl.HttpsURLConnection;

/** Tres pantallas: escanear, confirmar y la principal. Todo se decide por el estado, sin navegación. */
public class Principal extends Activity {
    private static final int ELEGIR = 1;
    private static final int PERMISO = 2;
    private static final int LEER = 3;
    private static final String WEB = "https://kvothesson.com/tachan/";
    private static final int MAXIMO_FOTOS = 100;

    private Transporte.Enlace pendiente;
    private View punto;
    private TextView estado;
    private boolean visible;

    @Override
    protected void onCreate(Bundle guardado) {
        super.onCreate(guardado);
        tomarEnlace(getIntent());
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        tomarEnlace(intent);
    }

    @Override
    protected void onResume() {
        super.onResume();
        visible = true;
        dibujar();
    }

    @Override
    protected void onPause() {
        super.onPause();
        visible = false;
    }

    private void tomarEnlace(Intent intent) {
        if (Intent.ACTION_VIEW.equals(intent.getAction()) && intent.getData() != null) {
            pendiente = Transporte.leerEnlace(intent.getData().toString());
            if (pendiente == null) aviso(R.string.codigo_vencido);
            intent.setData(null);
            intent.setAction(Intent.ACTION_MAIN);
        }
    }

    private void dibujar() {
        if (pendiente != null) pantallaConfirmar();
        else if (Almacen.compu(this) == null) pantallaEscanear();
        else pantallaPrincipal();
    }

    // --- Pantallas ---

    private void pantallaEscanear() {
        LinearLayout raiz = raiz();
        LinearLayout centro = centro(raiz);
        LinearLayout iconos = new LinearLayout(this);
        iconos.setGravity(Gravity.CENTER);
        iconos.addView(icono(R.drawable.qr, 56, 0));
        iconos.addView(icono(R.drawable.notificacion, 32, getColor(R.color.kvo_muted)), margenes(10, 0, 10, 0));
        iconos.addView(icono(R.drawable.pc, 56, getColor(R.color.kvo_ink)));
        centro.addView(iconos);
        centro.addView(frase(getString(R.string.escanea)), margenes(0, 18, 0, 0));
        raiz.addView(boton(getString(R.string.camara), this::escanear));
        raiz.addView(enlace(getString(R.string.escribir), this::escribirCodigo));
        raiz.addView(enlace(getString(R.string.sin_programa), this::abrirWeb));
        setContentView(raiz);
    }

    private void pantallaConfirmar() {
        LinearLayout raiz = raiz();
        LinearLayout centro = centro(raiz);
        centro.addView(icono(R.drawable.pc, 72, getColor(R.color.kvo_ink)));
        String nombre = TextUtils.isEmpty(pendiente.nombre) ? pendiente.host : pendiente.nombre;
        centro.addView(frase(getString(R.string.vincular_con, nombre)), margenes(0, 18, 0, 0));
        raiz.addView(boton(getString(R.string.vincular), this::vincular));
        raiz.addView(enlace(getString(R.string.cancelar), () -> {
            pendiente = null;
            dibujar();
        }));
        setContentView(raiz);
    }

    private void pantallaPrincipal() {
        final Transporte.Compu compu = Almacen.compu(this);
        LinearLayout raiz = raiz();

        TextView titulo = texto(getString(R.string.app_name), 32, getColor(R.color.kvo_ink));
        titulo.setTypeface(Typeface.DEFAULT_BOLD);
        LinearLayout cabeza = new LinearLayout(this);
        cabeza.setGravity(Gravity.CENTER_VERTICAL);
        cabeza.addView(titulo, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        ImageView cristal = new ImageView(this);
        cristal.setImageResource(R.drawable.firma);
        cristal.setScaleType(ImageView.ScaleType.CENTER);
        cristal.setContentDescription(getString(R.string.acerca));
        cristal.setBackground(new RippleDrawable(ColorStateList.valueOf(getColor(R.color.kvo_ink) & 0x00FFFFFF | 0x33000000), null, circulo(Color.BLACK)));
        cristal.setOnClickListener(v -> acercaDe());
        cabeza.addView(cristal, new LinearLayout.LayoutParams(dp(48), dp(48)));
        LinearLayout.LayoutParams separada = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        separada.bottomMargin = dp(16);
        raiz.addView(cabeza, separada);

        LinearLayout tarjeta = new LinearLayout(this);
        tarjeta.setGravity(Gravity.CENTER_VERTICAL);
        tarjeta.setPadding(dp(14), dp(12), dp(14), dp(12));
        GradientDrawable borde = redondeado(getColor(R.color.kvo_ground), 14);
        borde.setStroke(dp(1), getColor(R.color.kvo_line));
        tarjeta.setBackground(conToque(borde));
        LinearLayout datos = new LinearLayout(this);
        datos.setOrientation(LinearLayout.VERTICAL);
        TextView nombre = texto(compu.nombre, 15, getColor(R.color.kvo_ink));
        nombre.setTypeface(Typeface.DEFAULT_BOLD);
        nombre.setSingleLine(true);
        nombre.setEllipsize(TextUtils.TruncateAt.END);
        datos.addView(nombre);
        estado = texto("", 12, getColor(R.color.kvo_muted));
        estado.setTypeface(Typeface.MONOSPACE);
        datos.addView(estado);
        tarjeta.addView(datos, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        punto = new View(this);
        punto.setBackground(circulo(getColor(R.color.kvo_line_strong)));
        tarjeta.addView(punto, new LinearLayout.LayoutParams(dp(10), dp(10)));
        tarjeta.setOnClickListener(v -> opcionesCompu());
        raiz.addView(tarjeta);
        revisarPunto(compu);

        LinearLayout centro = centro(raiz);
        ImageView mas = new ImageView(this);
        mas.setImageResource(R.drawable.mas);
        mas.setScaleType(ImageView.ScaleType.CENTER);
        mas.setBackground(conToque(circulo(getColor(R.color.kvo_accent))));
        mas.setContentDescription(getString(R.string.elegir));
        mas.setOnClickListener(v -> elegirArchivos());
        centro.addView(mas, new LinearLayout.LayoutParams(dp(116), dp(116)));

        ScrollView desplazable = new ScrollView(this);
        LinearLayout lista = new LinearLayout(this);
        lista.setOrientation(LinearLayout.VERTICAL);
        for (String reciente : Almacen.recientes(this)) {
            View filete = new View(this);
            filete.setBackgroundColor(getColor(R.color.kvo_line));
            lista.addView(filete, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(1)));
            lista.addView(filaReciente(reciente));
        }
        desplazable.addView(lista);
        raiz.addView(desplazable, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(170)));
        setContentView(raiz);
    }

    private View filaReciente(String nombre) {
        LinearLayout fila = new LinearLayout(this);
        fila.setGravity(Gravity.CENTER_VERTICAL);
        fila.setPadding(0, dp(10), 0, dp(10));
        TextView t = texto(nombre, 13, getColor(R.color.kvo_muted));
        t.setSingleLine(true);
        t.setEllipsize(TextUtils.TruncateAt.MIDDLE);
        fila.addView(t, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        fila.addView(icono(R.drawable.ok, 18, 0));
        return fila;
    }

    /** El punto se pone verde si la compu responde. Si cambió de dirección, la busca. */
    private void revisarPunto(final Transporte.Compu compu) {
        final View esteP = punto;
        new Thread(() -> {
            int color = R.color.kvo_line_strong;
            boolean rechazado = false;
            try {
                try {
                    Transporte.hola(compu);
                } catch (Transporte.NoLlega e) {
                    if (Transporte.descubrir(compu, EnvioServicio.PUERTO_UDP) == null) throw e;
                    Almacen.guardar(this, compu);
                    Transporte.hola(compu);
                }
                color = R.color.kvo_ok;
            } catch (Transporte.Rechazado | Transporte.Impostor e) {
                rechazado = true;
            } catch (IOException e) {
                color = R.color.kvo_line_strong;
            }
            final int final_ = color;
            final boolean fueRechazado = rechazado;
            runOnUiThread(() -> {
                if (!visible) return;
                if (fueRechazado) {
                    Almacen.olvidar(this);
                    aviso(R.string.revincular);
                    dibujar();
                } else if (esteP == punto) {
                    punto.setBackground(circulo(getColor(final_)));
                    estado.setText(final_ == R.color.kvo_ok ? R.string.en_red : R.string.no_aparece);
                }
            });
        }).start();
    }

    // --- Acciones ---

    private void abrirWeb() {
        abrirLink(WEB);
    }

    private void abrirLink(String link) {
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(link)));
        } catch (ActivityNotFoundException e) {
            aviso(R.string.sin_programa);
        }
    }

    private void escanear() {
        startActivityForResult(new Intent(this, Lector.class), LEER);
    }

    private void escribirCodigo() {
        final EditText campo = new EditText(this);
        campo.setHint(R.string.pega);
        campo.setSingleLine(true);
        campo.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS);
        LinearLayout marco = new LinearLayout(this);
        marco.setPadding(dp(20), dp(8), dp(20), 0);
        marco.addView(campo, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        new AlertDialog.Builder(this)
                .setView(marco)
                .setPositiveButton(R.string.vincular, (d, w) -> {
                    pendiente = Transporte.leerEnlace(campo.getText().toString());
                    if (pendiente == null) aviso(R.string.codigo_vencido);
                    dibujar();
                })
                .setNegativeButton(R.string.cancelar, null)
                .show();
    }

    private void vincular() {
        final Transporte.Enlace enlace = pendiente;
        new Thread(() -> {
            int error = 0;
            Transporte.Compu compu = null;
            try {
                compu = Transporte.vincular(enlace, Build.MODEL);
                Almacen.guardar(this, compu);
            } catch (Transporte.NoLlega e) {
                error = R.string.sin_conexion;
            } catch (IOException e) {
                error = R.string.codigo_vencido;
            }
            final int mensaje = error;
            final Transporte.Compu vinculada = compu;
            runOnUiThread(() -> {
                pendiente = null;
                if (mensaje != 0) aviso(mensaje);
                else {
                    publicarAtajo(vinculada);
                    pedirNotificaciones();
                }
                dibujar();
            });
        }).start();
    }

    private void opcionesCompu() {
        CharSequence[] opciones = {getString(R.string.otra), getString(R.string.desvincular)};
        new AlertDialog.Builder(this).setItems(opciones, (d, cual) -> confirmarDesvincular()).show();
    }

    /** Volver a vincular pide ir hasta la compu: un toque de más no puede costar eso. */
    private void confirmarDesvincular() {
        final Transporte.Compu vieja = Almacen.compu(this);
        new AlertDialog.Builder(this)
                .setMessage(getString(R.string.desvincular_de, vieja.nombre))
                .setPositiveButton(R.string.desvincular, (d, w) -> {
                    // Si la compu no está prendida se entera más tarde: su token ya no se usa.
                    new Thread(() -> {
                        try { Transporte.desvincular(vieja); } catch (IOException e) { }
                    }).start();
                    Almacen.olvidar(this);
                    if (Build.VERSION.SDK_INT >= 25) getSystemService(ShortcutManager.class).removeAllDynamicShortcuts();
                    dibujar();
                })
                .setNegativeButton(R.string.cancelar, null)
                .show();
    }

    private String nombreVersion() {
        try { return getPackageManager().getPackageInfo(getPackageName(), 0).versionName; }
        catch (android.content.pm.PackageManager.NameNotFoundException e) { return ""; }
    }

    private int codigoVersion() {
        try { return getPackageManager().getPackageInfo(getPackageName(), 0).versionCode; }
        catch (android.content.pm.PackageManager.NameNotFoundException e) { return Integer.MAX_VALUE; }
    }

    /** Solo se conecta a internet si lo pedís. Android rechaza un APK que no venga firmado con la misma llave. */
    private void buscarActualizacion() {
        new Thread(() -> {
            int publicado = -1;
            try {
                HttpsURLConnection c = (HttpsURLConnection) new URL(WEB + "version.json?t=" + System.currentTimeMillis()).openConnection();
                c.setConnectTimeout(8000);
                c.setReadTimeout(8000);
                try (java.util.Scanner lector = new java.util.Scanner(c.getInputStream(), "UTF-8")) {
                    Matcher m = Pattern.compile("\"codigo\"\\s*:\\s*(\\d+)").matcher(lector.useDelimiter("\\A").next());
                    if (m.find()) publicado = Integer.parseInt(m.group(1));
                } finally {
                    c.disconnect();
                }
            } catch (IOException | RuntimeException e) {
                publicado = -1;
            }
            final int encontrado = publicado;
            runOnUiThread(() -> {
                if (!visible) return;
                if (encontrado < 0) aviso(R.string.sin_conexion);
                else if (encontrado <= codigoVersion()) aviso(R.string.ultima_version);
                else new AlertDialog.Builder(this)
                        .setMessage(R.string.hay_version)
                        .setPositiveButton(R.string.bajar, (d, w) -> abrirLink(WEB + "tachan.apk"))
                        .setNegativeButton(R.string.cancelar, null)
                        .show();
            });
        }).start();
    }

    private void acercaDe() {
        LinearLayout firma = new LinearLayout(this);
        firma.setGravity(Gravity.CENTER_VERTICAL);
        firma.setPadding(dp(24), dp(24), dp(24), dp(16));
        firma.addView(icono(R.drawable.firma, 16, 0));
        TextView texto = texto(getString(R.string.firma), 12, getColor(R.color.kvo_muted));
        texto.setTypeface(Typeface.MONOSPACE);
        firma.addView(texto, margenes(8, 0, 0, 0));
        new AlertDialog.Builder(this)
                .setTitle(getString(R.string.app_name) + " " + nombreVersion())
                .setView(firma)
                .setPositiveButton(R.string.buscar_actualizacion, (d, w) -> buscarActualizacion())
                .show();
    }

    private void elegirArchivos() {
        CharSequence[] opciones = {getString(R.string.fotos), getString(R.string.archivos)};
        new AlertDialog.Builder(this).setItems(opciones, (d, cual) -> {
            if (cual == 0) elegirFotos();
            else elegirDocumentos();
        }).show();
    }

    /** El selector de fotos no pide permisos ni pasa por el de documentos, que en algunos celus se cae por otras apps. */
    private void elegirFotos() {
        Intent i = new Intent("android.provider.action.PICK_IMAGES");
        i.putExtra("android.provider.extra.PICK_IMAGES_MAX", MAXIMO_FOTOS);
        try {
            startActivityForResult(i, ELEGIR);
        } catch (ActivityNotFoundException e) {
            Intent galeria = new Intent(Intent.ACTION_GET_CONTENT);
            galeria.setType("image/*");
            galeria.putExtra(Intent.EXTRA_MIME_TYPES, new String[]{"image/*", "video/*"});
            galeria.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
            startActivityForResult(galeria, ELEGIR);
        }
    }

    private void elegirDocumentos() {
        Intent i = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        i.addCategory(Intent.CATEGORY_OPENABLE);
        i.setType("*/*");
        i.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
        // Sin esto arranca en la última carpeta usada por cualquier app, que puede ser cualquier cosa.
        if (Build.VERSION.SDK_INT >= 26)
            i.putExtra(DocumentsContract.EXTRA_INITIAL_URI, DocumentsContract.buildDocumentUri("com.android.externalstorage.documents", "primary:Download"));
        startActivityForResult(i, ELEGIR);
    }

    @Override
    protected void onActivityResult(int pedido, int resultado, Intent datos) {
        super.onActivityResult(pedido, resultado, datos);
        if (pedido == LEER) {
            if (resultado == RESULT_OK && datos != null) pendiente = Transporte.leerEnlace(datos.getStringExtra(Lector.TEXTO));
            else if (resultado == Lector.ESCRIBIR) escribirCodigo();
            return;
        }
        if (pedido != ELEGIR || resultado != RESULT_OK || datos == null) return;
        ArrayList<Uri> elegidos = new ArrayList<>();
        if (datos.getData() != null) elegidos.add(datos.getData());
        ClipData clip = datos.getClipData();
        if (clip != null) for (int i = 0; i < clip.getItemCount(); i++) elegidos.add(clip.getItemAt(i).getUri());
        EnvioServicio.iniciar(this, elegidos, null);
    }

    private void pedirNotificaciones() {
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != android.content.pm.PackageManager.PERMISSION_GRANTED)
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, PERMISO);
    }

    /** La compu aparece con su nombre en la fila de Compartir. */
    private void publicarAtajo(Transporte.Compu compu) {
        if (Build.VERSION.SDK_INT < 30 || compu == null) return;
        Set<String> categorias = new HashSet<>(Collections.singletonList("com.kvothesson.tachan.COMPU"));
        ShortcutInfo atajo = new ShortcutInfo.Builder(this, "compu")
                .setShortLabel(compu.nombre)
                .setIcon(Icon.createWithResource(this, R.mipmap.icono))
                .setLongLived(true)
                .setCategories(categorias)
                .setIntent(new Intent(this, Principal.class).setAction(Intent.ACTION_MAIN))
                .build();
        getSystemService(ShortcutManager.class).pushDynamicShortcut(atajo);
    }

    // --- Piezas de interfaz ---

    private LinearLayout raiz() {
        LinearLayout r = new LinearLayout(this);
        r.setOrientation(LinearLayout.VERTICAL);
        r.setPadding(dp(16), dp(24), dp(16), dp(24));
        r.setBackgroundColor(getColor(R.color.kvo_ground));
        r.setFitsSystemWindows(true);
        return r;
    }

    private LinearLayout centro(LinearLayout raiz) {
        LinearLayout c = new LinearLayout(this);
        c.setOrientation(LinearLayout.VERTICAL);
        c.setGravity(Gravity.CENTER);
        raiz.addView(c, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1));
        return c;
    }

    private TextView frase(String s) {
        TextView t = texto(s, 18, getColor(R.color.kvo_ink));
        t.setTypeface(Typeface.DEFAULT_BOLD);
        t.setGravity(Gravity.CENTER);
        return t;
    }

    private TextView texto(String s, int sp, int color) {
        TextView t = new TextView(this);
        t.setText(s);
        t.setTextSize(TypedValue.COMPLEX_UNIT_SP, sp);
        t.setTextColor(color);
        return t;
    }

    private ImageView icono(int recurso, int lado, int tinte) {
        ImageView i = new ImageView(this);
        i.setImageResource(recurso);
        if (tinte != 0) i.setImageTintList(ColorStateList.valueOf(tinte));
        i.setLayoutParams(new LinearLayout.LayoutParams(dp(lado), dp(lado)));
        return i;
    }

    private TextView boton(String s, final Runnable accion) {
        TextView b = texto(s, 15, getColor(R.color.kvo_on_accent));
        b.setTypeface(Typeface.DEFAULT_BOLD);
        b.setGravity(Gravity.CENTER);
        b.setBackground(conToque(redondeado(getColor(R.color.kvo_accent), 14)));
        b.setLayoutParams(new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(48)));
        b.setOnClickListener(v -> accion.run());
        return b;
    }

    private TextView enlace(String s, final Runnable accion) {
        TextView t = texto(s, 14, getColor(R.color.kvo_muted));
        t.setGravity(Gravity.CENTER);
        t.setPadding(0, dp(14), 0, dp(6));
        t.setOnClickListener(v -> accion.run());
        return t;
    }

    private GradientDrawable redondeado(int color, int radio) {
        GradientDrawable d = new GradientDrawable();
        d.setColor(color);
        d.setCornerRadius(dp(radio));
        return d;
    }

    private GradientDrawable circulo(int color) {
        GradientDrawable d = new GradientDrawable();
        d.setShape(GradientDrawable.OVAL);
        d.setColor(color);
        return d;
    }

    private RippleDrawable conToque(GradientDrawable fondo) {
        return new RippleDrawable(ColorStateList.valueOf(getColor(R.color.kvo_ink) & 0x00FFFFFF | 0x33000000), fondo, null);
    }

    private LinearLayout.LayoutParams margenes(int izq, int arr, int der, int aba) {
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        p.setMargins(dp(izq), dp(arr), dp(der), dp(aba));
        return p;
    }

    private int dp(int v) {
        return Math.round(v * getResources().getDisplayMetrics().density);
    }

    private void aviso(int texto) {
        Toast.makeText(this, texto, Toast.LENGTH_LONG).show();
    }
}
