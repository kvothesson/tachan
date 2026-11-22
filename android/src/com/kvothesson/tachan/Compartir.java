package com.kvothesson.tachan;

import android.app.Activity;
import android.content.ClipData;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.widget.Toast;

import java.util.ArrayList;
import java.util.Iterator;

/** Recibe lo que se comparte desde cualquier app y se lo pasa al servicio. Sin pantalla. */
public class Compartir extends Activity {
    @Override
    protected void onCreate(Bundle guardado) {
        super.onCreate(guardado);
        Intent recibido = getIntent();
        if (Almacen.compu(this) == null) {
            startActivity(new Intent(this, Principal.class));
            finish();
            return;
        }
        // Si se eligió una compu en la fila de Compartir, va a esa. Si no, el servicio busca la que esté prendida.
        Transporte.Compu elegida = Almacen.deAtajo(this, recibido.getStringExtra(Intent.EXTRA_SHORTCUT_ID));
        try {
            EnvioServicio.iniciar(this, adjuntos(recibido), textoDe(recibido), elegida);
        } catch (SecurityException e) {
            // La otra app compartió algo sin darnos permiso para leerlo.
            Toast.makeText(this, R.string.fallo, Toast.LENGTH_LONG).show();
        }
        finish();
    }

    static ArrayList<Uri> adjuntos(Intent intent) {
        ArrayList<Uri> lista = new ArrayList<>();
        if (Intent.ACTION_SEND.equals(intent.getAction())) {
            Uri una = intent.getParcelableExtra(Intent.EXTRA_STREAM);
            if (una != null) lista.add(una);
        } else if (Intent.ACTION_SEND_MULTIPLE.equals(intent.getAction())) {
            ArrayList<Uri> varias = intent.getParcelableArrayListExtra(Intent.EXTRA_STREAM);
            if (varias != null) lista.addAll(varias);
        }
        ClipData clip = intent.getClipData();
        if (lista.isEmpty() && clip != null)
            for (int i = 0; i < clip.getItemCount(); i++)
                if (clip.getItemAt(i).getUri() != null) lista.add(clip.getItemAt(i).getUri());
        // Otra app podría pedirnos file:// para que mandemos nuestros propios datos: solo se acepta lo que comparte ella.
        for (Iterator<Uri> i = lista.iterator(); i.hasNext(); )
            if (!"content".equals(i.next().getScheme())) i.remove();
        return lista;
    }

    private static String textoDe(Intent intent) {
        CharSequence texto = intent.getCharSequenceExtra(Intent.EXTRA_TEXT);
        return texto == null ? null : texto.toString();
    }
}
