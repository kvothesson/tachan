package com.kvothesson.tachan;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Matrix;
import android.graphics.Paint;
import android.graphics.SurfaceTexture;
import android.hardware.Camera;
import android.os.Bundle;
import android.os.Handler;
import android.os.HandlerThread;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.HapticFeedbackConstants;
import android.view.TextureView;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.widget.FrameLayout;
import android.widget.TextView;
import android.widget.Toast;

import java.io.IOException;

/** Lee el QR de la compu con la cámara, sin depender de la app de cámara de cada marca. */
public class Lector extends Activity implements TextureView.SurfaceTextureListener, Camera.PreviewCallback {
    static final String TEXTO = "texto";
    static final int ESCRIBIR = RESULT_FIRST_USER;
    private static final int PERMISO = 1;
    private static final int ANCHO_IDEAL = 1280, ALTO_IDEAL = 720;

    private TextureView vista;
    private TextView pista;
    private Camera camara;
    private HandlerThread hilo;
    private Handler trabajo;
    private int ancho, alto;
    private boolean terminado;

    @Override
    protected void onCreate(Bundle guardado) {
        super.onCreate(guardado);
        requestWindowFeature(Window.FEATURE_NO_TITLE);
        FrameLayout raiz = new FrameLayout(this);
        raiz.setBackgroundColor(Color.BLACK);
        vista = new TextureView(this);
        vista.setSurfaceTextureListener(this);
        raiz.addView(vista, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        raiz.addView(new Marco(), new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        pista = texto(getString(R.string.escanea), 17);
        pista.setPadding(dp(24), dp(56), dp(24), dp(16));
        raiz.addView(pista, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.TOP));

        TextView escribir = texto(getString(R.string.escribir), 15);
        escribir.setPadding(dp(24), dp(16), dp(24), dp(40));
        escribir.setOnClickListener(v -> {
            setResult(ESCRIBIR);
            finish();
        });
        raiz.addView(escribir, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.BOTTOM));
        setContentView(raiz);
    }

    private TextView texto(String s, int sp) {
        TextView t = new TextView(this);
        t.setText(s);
        t.setTextColor(Color.WHITE);
        t.setTextSize(TypedValue.COMPLEX_UNIT_SP, sp);
        t.setGravity(Gravity.CENTER);
        t.setShadowLayer(dp(4), 0, 0, Color.BLACK);
        return t;
    }

    private int dp(int v) {
        return Math.round(v * getResources().getDisplayMetrics().density);
    }

    @Override
    protected void onResume() {
        super.onResume();
        hilo = new HandlerThread("lector");
        hilo.start();
        trabajo = new Handler(hilo.getLooper());
        if (checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED)
            requestPermissions(new String[]{Manifest.permission.CAMERA}, PERMISO);
        else if (vista.isAvailable()) abrir();
    }

    @Override
    protected void onPause() {
        super.onPause();
        cerrar();
        hilo.quitSafely();
        QrLector.soltar();
    }

    @Override
    public void onRequestPermissionsResult(int pedido, String[] permisos, int[] resultados) {
        if (pedido != PERMISO) return;
        if (resultados.length > 0 && resultados[0] == PackageManager.PERMISSION_GRANTED) {
            if (vista.isAvailable()) abrir();
        } else {
            sinCamara();
        }
    }

    /** Sin cámara queda el código a mano, que siempre funciona. */
    private void sinCamara() {
        Toast.makeText(this, R.string.sin_camara, Toast.LENGTH_LONG).show();
        setResult(ESCRIBIR);
        finish();
    }

    private void abrir() {
        if (camara != null) return;
        try {
            camara = Camera.open();
            if (camara == null) {
                sinCamara();
                return;
            }
            Camera.Parameters p = camara.getParameters();
            Camera.Size mejor = null;
            long menor = Long.MAX_VALUE;
            for (Camera.Size s : p.getSupportedPreviewSizes()) {
                long diferencia = Math.abs((long) s.width * s.height - (long) ANCHO_IDEAL * ALTO_IDEAL);
                if (diferencia < menor) {
                    menor = diferencia;
                    mejor = s;
                }
            }
            p.setPreviewSize(mejor.width, mejor.height);
            ancho = mejor.width;
            alto = mejor.height;
            if (p.getSupportedFocusModes().contains(Camera.Parameters.FOCUS_MODE_CONTINUOUS_PICTURE))
                p.setFocusMode(Camera.Parameters.FOCUS_MODE_CONTINUOUS_PICTURE);
            camara.setParameters(p);
            Camera.CameraInfo info = new Camera.CameraInfo();
            Camera.getCameraInfo(0, info);
            camara.setDisplayOrientation(info.orientation);
            recortar();
            camara.setPreviewTexture(vista.getSurfaceTexture());
            camara.addCallbackBuffer(new byte[ancho * alto * 3 / 2]);
            camara.setPreviewCallbackWithBuffer(this);
            camara.startPreview();
        } catch (IOException | RuntimeException e) {
            cerrar();
            sinCamara();
        }
    }

    /** La imagen llena la pantalla sin deformarse: lo que sobra queda afuera. La pantalla va vertical y la cámara acostada. */
    private void recortar() {
        float vw = vista.getWidth(), vh = vista.getHeight();
        if (vw == 0 || vh == 0) return;
        float escala = Math.max(vw / alto, vh / ancho);
        Matrix m = new Matrix();
        m.setScale(alto * escala / vw, ancho * escala / vh, vw / 2, vh / 2);
        vista.setTransform(m);
    }

    private void cerrar() {
        if (camara == null) return;
        camara.setPreviewCallbackWithBuffer(null);
        camara.stopPreview();
        camara.release();
        camara = null;
    }

    @Override
    public void onPreviewFrame(final byte[] cuadro, final Camera cam) {
        final int w = ancho, h = alto;
        trabajo.post(() -> {
            final String leido = QrLector.leer(cuadro, w, h);
            runOnUiThread(() -> resultado(leido, cuadro, cam));
        });
    }

    private void resultado(String leido, byte[] cuadro, Camera cam) {
        if (terminado || cam != camara) return;
        if (leido != null && Transporte.leerEnlace(leido) != null) {
            terminado = true;
            vista.performHapticFeedback(HapticFeedbackConstants.LONG_PRESS);
            setResult(RESULT_OK, new Intent().putExtra(TEXTO, leido));
            finish();
            return;
        }
        if (leido != null) pista.setText(R.string.no_es_tachan);
        camara.addCallbackBuffer(cuadro);
    }

    @Override
    public void onSurfaceTextureAvailable(SurfaceTexture s, int w, int h) {
        if (checkSelfPermission(Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) abrir();
    }

    @Override
    public void onSurfaceTextureSizeChanged(SurfaceTexture s, int w, int h) {
        if (camara != null) recortar();
    }

    @Override
    public boolean onSurfaceTextureDestroyed(SurfaceTexture s) {
        cerrar();
        return true;
    }

    @Override
    public void onSurfaceTextureUpdated(SurfaceTexture s) { }

    /** Las cuatro esquinas que dicen dónde poner el código. */
    private class Marco extends View {
        private final Paint trazo = new Paint(Paint.ANTI_ALIAS_FLAG);

        Marco() {
            super(Lector.this);
            trazo.setStyle(Paint.Style.STROKE);
            trazo.setStrokeCap(Paint.Cap.ROUND);
            trazo.setStrokeWidth(dp(4));
            trazo.setColor(getColor(R.color.kvo_accent));
        }

        @Override
        protected void onDraw(Canvas c) {
            float lado = getWidth() * 0.72f, l = getWidth() / 2f - lado / 2, t = getHeight() / 2f - lado / 2, r = l + lado, b = t + lado, n = dp(32);
            c.drawLine(l, t, l + n, t, trazo);
            c.drawLine(l, t, l, t + n, trazo);
            c.drawLine(r, t, r - n, t, trazo);
            c.drawLine(r, t, r, t + n, trazo);
            c.drawLine(l, b, l + n, b, trazo);
            c.drawLine(l, b, l, b - n, trazo);
            c.drawLine(r, b, r - n, b, trazo);
            c.drawLine(r, b, r, b - n, trazo);
        }
    }
}
