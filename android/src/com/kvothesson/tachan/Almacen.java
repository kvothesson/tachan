package com.kvothesson.tachan;

import android.content.Context;
import android.content.SharedPreferences;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

/** La compu vinculada y lo último enviado. La copia de seguridad está apagada en el manifiesto: el token no sale del celu. */
final class Almacen {
    private static final int MAXIMO_RECIENTES = 12;

    private Almacen() {}

    private static SharedPreferences prefs(Context c) {
        return c.getSharedPreferences("tachan", Context.MODE_PRIVATE);
    }

    static Transporte.Compu compu(Context c) {
        SharedPreferences p = prefs(c);
        String token = p.getString("token", null);
        if (token == null) return null;
        Transporte.Compu compu = new Transporte.Compu();
        compu.token = token;
        compu.host = p.getString("host", "");
        compu.puerto = p.getInt("puerto", 0);
        compu.huella = p.getString("huella", "");
        compu.nombre = p.getString("nombre", "");
        return compu;
    }

    static void guardar(Context c, Transporte.Compu compu) {
        prefs(c).edit().putString("token", compu.token).putString("host", compu.host).putInt("puerto", compu.puerto)
                .putString("huella", compu.huella).putString("nombre", compu.nombre).apply();
    }

    static void olvidar(Context c) {
        prefs(c).edit().remove("token").remove("host").remove("puerto").remove("huella").remove("nombre").apply();
    }

    static List<String> recientes(Context c) {
        String crudo = prefs(c).getString("recientes", "");
        return crudo.isEmpty() ? new ArrayList<String>() : new ArrayList<>(Arrays.asList(crudo.split("\n")));
    }

    static void agregarReciente(Context c, String nombre) {
        List<String> lista = recientes(c);
        lista.add(0, nombre.replace('\n', ' '));
        while (lista.size() > MAXIMO_RECIENTES) lista.remove(lista.size() - 1);
        prefs(c).edit().putString("recientes", android.text.TextUtils.join("\n", lista)).apply();
    }
}
