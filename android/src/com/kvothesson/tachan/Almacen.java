package com.kvothesson.tachan;

import android.content.Context;
import android.content.SharedPreferences;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;

/** Las compus vinculadas y lo último enviado. La copia de seguridad está apagada en el manifiesto: los tokens no salen del celu. */
final class Almacen {
    private static final int MAXIMO_RECIENTES = 12;
    private static final int MAXIMO_COMPUS = 8;

    private Almacen() {}

    private static SharedPreferences prefs(Context c) {
        return c.getSharedPreferences("tachan", Context.MODE_PRIVATE);
    }

    /** Todas las compus, la última usada primero. */
    static synchronized List<Transporte.Compu> compus(Context c) {
        SharedPreferences p = prefs(c);
        migrar(p);
        List<Transporte.Compu> lista = new ArrayList<>();
        try {
            JSONArray crudo = new JSONArray(p.getString("compus", "[]"));
            for (int i = 0; i < crudo.length(); i++) {
                JSONObject o = crudo.getJSONObject(i);
                Transporte.Compu k = new Transporte.Compu();
                k.token = o.getString("token");
                k.host = o.optString("host", "");
                k.puerto = o.optInt("puerto", 0);
                k.huella = o.getString("huella");
                k.nombre = o.optString("nombre", "");
                lista.add(k);
            }
        } catch (JSONException e) {
            return lista;
        }
        String ultima = p.getString("ultima", "");
        for (int i = 0; i < lista.size(); i++)
            if (lista.get(i).huella.equals(ultima)) lista.add(0, lista.remove(i));
        return lista;
    }

    /** La última usada, o null si no hay ninguna vinculada. */
    static Transporte.Compu compu(Context c) {
        List<Transporte.Compu> lista = compus(c);
        return lista.isEmpty() ? null : lista.get(0);
    }

    static Transporte.Compu compu(Context c, String huella) {
        if (huella == null) return null;
        for (Transporte.Compu k : compus(c)) if (k.huella.equals(huella)) return k;
        return null;
    }

    /** La del atajo de Compartir: su id lleva el comienzo de la huella. */
    static Transporte.Compu deAtajo(Context c, String id) {
        if (id == null || !id.startsWith("compu-")) return null;
        String prefijo = id.substring(6);
        for (Transporte.Compu k : compus(c)) if (k.huella.startsWith(prefijo)) return k;
        return null;
    }

    static String idAtajo(Transporte.Compu k) {
        return "compu-" + k.huella.substring(0, 16);
    }

    /** Suma una compu nueva, o reemplaza el vínculo viejo con la misma compu. */
    static synchronized void guardar(Context c, Transporte.Compu compu) {
        List<Transporte.Compu> lista = compus(c);
        boolean estaba = false;
        for (int i = 0; i < lista.size(); i++)
            if (lista.get(i).huella.equals(compu.huella)) {
                lista.set(i, compu);
                estaba = true;
            }
        if (!estaba) lista.add(0, compu);
        while (lista.size() > MAXIMO_COMPUS) lista.remove(lista.size() - 1);
        escribir(c, lista);
    }

    /** Anota la dirección nueva de una compu que cambió de lugar, si sigue vinculada. */
    static synchronized void actualizar(Context c, Transporte.Compu compu) {
        if (compu(c, compu.huella) != null) guardar(c, compu);
    }

    static synchronized void usar(Context c, Transporte.Compu compu) {
        prefs(c).edit().putString("ultima", compu.huella).apply();
    }

    static synchronized void olvidar(Context c, Transporte.Compu compu) {
        List<Transporte.Compu> lista = compus(c);
        for (int i = lista.size() - 1; i >= 0; i--)
            if (lista.get(i).huella.equals(compu.huella)) lista.remove(i);
        escribir(c, lista);
        if (compu.huella.equals(prefs(c).getString("ultima", ""))) prefs(c).edit().remove("ultima").apply();
    }

    /**
     * Adónde va lo que se comparte sin elegir compu: a la última usada si está prendida; si no, a la primera
     * que conteste. Si no contesta ninguna, queda para la última usada.
     */
    static Transporte.Compu destino(Context c) {
        List<Transporte.Compu> lista = compus(c);
        if (lista.size() <= 1) return lista.isEmpty() ? null : lista.get(0);
        for (Transporte.Compu k : lista) {
            try {
                try {
                    Transporte.hola(k);
                } catch (Transporte.NoLlega e) {
                    if (Transporte.descubrir(k, EnvioServicio.PUERTO_UDP) == null) throw e;
                    actualizar(c, k);
                }
                return k;
            } catch (Transporte.Rechazado e) {
                olvidar(c, k);  // esa compu ya no nos reconoce: que no se lleve lo que va para otra
            } catch (IOException e) {
                // apagada: probar la siguiente
            }
        }
        List<Transporte.Compu> quedan = compus(c);
        return quedan.isEmpty() ? null : quedan.get(0);
    }

    private static void escribir(Context c, List<Transporte.Compu> lista) {
        JSONArray crudo = new JSONArray();
        try {
            for (Transporte.Compu k : lista)
                crudo.put(new JSONObject().put("token", k.token).put("host", k.host).put("puerto", k.puerto)
                        .put("huella", k.huella).put("nombre", k.nombre));
        } catch (JSONException e) {
            return;
        }
        prefs(c).edit().putString("compus", crudo.toString()).apply();
    }

    /** Hasta la 1.4 había una sola compu, guardada suelta. */
    private static void migrar(SharedPreferences p) {
        String token = p.getString("token", null);
        if (token == null) return;
        JSONArray crudo = new JSONArray();
        try {
            crudo.put(new JSONObject().put("token", token).put("host", p.getString("host", "")).put("puerto", p.getInt("puerto", 0))
                    .put("huella", p.getString("huella", "")).put("nombre", p.getString("nombre", "")));
        } catch (JSONException e) {
            return;
        }
        p.edit().putString("compus", crudo.toString()).putString("ultima", p.getString("huella", ""))
                .remove("token").remove("host").remove("puerto").remove("huella").remove("nombre").commit();
    }

    /** Lo último que llegó: {nombre, compu}. Lo anotado antes de la 1.5 no dice compu. */
    static List<String[]> recientes(Context c) {
        String crudo = prefs(c).getString("recientes", "");
        List<String[]> lista = new ArrayList<>();
        if (crudo.isEmpty()) return lista;
        for (String renglon : crudo.split("\n")) {
            int tab = renglon.indexOf('\t');
            lista.add(tab < 0 ? new String[]{renglon, ""} : new String[]{renglon.substring(0, tab), renglon.substring(tab + 1)});
        }
        return lista;
    }

    static synchronized void agregarReciente(Context c, String nombre, Transporte.Compu compu) {
        List<String> lista = new ArrayList<>();
        lista.add(limpio(nombre) + "\t" + limpio(compu.nombre));
        for (String[] r : recientes(c)) lista.add(r[0] + "\t" + r[1]);
        while (lista.size() > MAXIMO_RECIENTES) lista.remove(lista.size() - 1);
        prefs(c).edit().putString("recientes", android.text.TextUtils.join("\n", lista)).apply();
    }

    private static String limpio(String s) {
        return s.replace('\n', ' ').replace('\t', ' ');
    }
}
