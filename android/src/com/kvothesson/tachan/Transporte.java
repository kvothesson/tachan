package com.kvothesson.tachan;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.HttpURLConnection;
import java.net.InetAddress;
import java.net.SocketTimeoutException;
import java.net.URL;
import java.net.URLDecoder;
import java.net.URLEncoder;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.security.cert.CertificateException;
import java.security.cert.X509Certificate;
import java.util.Arrays;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import javax.net.ssl.HttpsURLConnection;
import javax.net.ssl.SSLContext;
import javax.net.ssl.SSLSocketFactory;
import javax.net.ssl.TrustManager;
import javax.net.ssl.X509TrustManager;

/** La conversación con la compu. Java puro, sin Android: se prueba contra el programa de PC real. */
public final class Transporte {
    private Transporte() {}

    /** No se pudo llegar a la compu: conviene reintentar más tarde. */
    public static class NoLlega extends IOException {
        NoLlega(String mensaje) { super(mensaje); }
    }

    /** La compu respondió que no: el vínculo ya no vale, reintentar no sirve. */
    public static class Rechazado extends IOException {
        Rechazado(String mensaje) { super(mensaje); }
    }

    /** El certificado no es el de la compu vinculada: alguien se está haciendo pasar. */
    public static class Impostor extends IOException {
        Impostor(String mensaje) { super(mensaje); }
    }

    public interface Avance {
        void enviados(long bytes);
    }

    /** Lo que trae el QR. */
    public static final class Enlace {
        public String host;
        public int puerto;
        public String secreto;
        public byte[] huellaParcial;
        public String nombre;
    }

    /** Una compu ya vinculada. */
    public static final class Compu {
        public String host;
        public int puerto;
        public String huella;
        public String token;
        public String nombre;
    }

    private static final String ALFABETO = "abcdefghijklmnopqrstuvwxyz234567";
    private static final int LARGO_ENLACE = 22;

    /** Acepta el enlace completo del QR o solo el código. Devuelve null si no es válido. */
    public static Enlace leerEnlace(String crudo) {
        if (crudo == null) return null;
        String texto = crudo.trim();
        String nombre = "";
        // Los datos van después del # en el link del QR, o después del ? al abrir la app desde la web.
        int datos = Math.max(texto.indexOf('#'), texto.indexOf('?'));
        if (datos >= 0) {
            String codigo = null;
            for (String parte : texto.substring(datos + 1).split("&")) {
                if (parte.startsWith("c=")) codigo = parte.substring(2);
                if (parte.startsWith("n=")) {
                    try { nombre = URLDecoder.decode(parte.substring(2), "UTF-8"); }
                    catch (Exception e) { nombre = ""; }
                }
            }
            texto = codigo;
        }
        if (texto == null) return null;
        byte[] d = base32(texto.replace(" ", "").replace("-", "").toLowerCase(Locale.ROOT));
        if (d == null || d.length != LARGO_ENLACE) return null;
        Enlace e = new Enlace();
        e.host = (d[0] & 255) + "." + (d[1] & 255) + "." + (d[2] & 255) + "." + (d[3] & 255);
        e.puerto = ((d[4] & 255) << 8) | (d[5] & 255);
        e.secreto = hex(Arrays.copyOfRange(d, 6, 12));
        e.huellaParcial = Arrays.copyOfRange(d, 12, 22);
        e.nombre = nombre;
        return e;
    }

    private static byte[] base32(String s) {
        ByteArrayOutputStream salida = new ByteArrayOutputStream();
        int acumulado = 0, bits = 0;
        for (int i = 0; i < s.length(); i++) {
            int v = ALFABETO.indexOf(s.charAt(i));
            if (v < 0) return null;
            acumulado = (acumulado << 5) | v;
            bits += 5;
            if (bits >= 8) {
                salida.write((acumulado >> (bits - 8)) & 255);
                bits -= 8;
            }
            acumulado &= (1 << bits) - 1;
        }
        return salida.toByteArray();
    }

    /** Solo acepta el certificado cuya huella ya conocemos: ni autoridades ni nombres de host. */
    private static SSLSocketFactory fijada(final byte[] huella) throws IOException {
        TrustManager fijo = new X509TrustManager() {
            @Override public void checkClientTrusted(X509Certificate[] c, String t) throws CertificateException {
                throw new CertificateException();
            }
            @Override public void checkServerTrusted(X509Certificate[] c, String t) throws CertificateException {
                if (c == null || c.length == 0) throw new CertificateException("sin certificado");
                byte[] real;
                try { real = MessageDigest.getInstance("SHA-256").digest(c[0].getEncoded()); }
                catch (Exception e) { throw new CertificateException(e); }
                if (real.length < huella.length || !MessageDigest.isEqual(Arrays.copyOf(real, huella.length), huella))
                    throw new CertificateException("huella distinta");
            }
            @Override public X509Certificate[] getAcceptedIssuers() { return new X509Certificate[0]; }
        };
        try {
            SSLContext contexto = SSLContext.getInstance("TLS");
            contexto.init(null, new TrustManager[]{fijo}, new SecureRandom());
            return contexto.getSocketFactory();
        } catch (Exception e) {
            throw new IOException(e);
        }
    }

    private static HttpsURLConnection abrir(String host, int puerto, String ruta, byte[] huella, int esperaMs) throws IOException {
        HttpsURLConnection c = (HttpsURLConnection) new URL("https://" + host + ":" + puerto + ruta).openConnection();
        c.setSSLSocketFactory(fijada(huella));
        c.setHostnameVerifier((nombre, sesion) -> true);  // la identidad la da la huella, no el nombre
        c.setConnectTimeout(4000);
        c.setReadTimeout(esperaMs);
        c.setUseCaches(false);
        return c;
    }

    /** Separa "no llegó" de "es otra máquina": lo segundo nunca se reintenta. */
    private static IOException clasificar(IOException e) {
        for (Throwable t = e; t != null; t = t.getCause())
            if (t instanceof CertificateException) return new Impostor("el certificado no coincide");
        return new NoLlega(String.valueOf(e.getMessage()));
    }

    public static Compu vincular(Enlace enlace, String dispositivo) throws IOException {
        HttpsURLConnection c = null;
        try {
            c = abrir(enlace.host, enlace.puerto, "/vincular", enlace.huellaParcial, 10000);
            c.setRequestMethod("POST");
            c.setRequestProperty("X-Secreto", enlace.secreto);
            c.setRequestProperty("X-Dispositivo", URLEncoder.encode(dispositivo, "UTF-8").replace("+", "%20"));
            c.setFixedLengthStreamingMode(0);
            c.setDoOutput(true);
            c.getOutputStream().close();
            int codigo = c.getResponseCode();
            if (codigo != 200) throw new Rechazado("código " + codigo);
            String json = leer(c.getInputStream());
            Compu compu = new Compu();
            compu.host = enlace.host;
            compu.puerto = enlace.puerto;
            compu.token = campo(json, "token");
            compu.huella = campo(json, "huella");
            compu.nombre = campo(json, "nombre");
            byte[] completa = desdeHex(compu.huella);
            if (completa.length != 32 || !MessageDigest.isEqual(Arrays.copyOf(completa, enlace.huellaParcial.length), enlace.huellaParcial))
                throw new Impostor("huella inconsistente");
            return compu;
        } catch (Rechazado | Impostor e) {
            throw e;
        } catch (IOException e) {
            throw clasificar(e);
        } finally {
            if (c != null) c.disconnect();
        }
    }

    public static void hola(Compu compu) throws IOException {
        HttpsURLConnection c = null;
        try {
            c = abrir(compu.host, compu.puerto, "/hola", desdeHex(compu.huella), 5000);
            c.setRequestProperty("Authorization", "Bearer " + compu.token);
            int codigo = c.getResponseCode();
            if (codigo == 401) throw new Rechazado("desvinculado");
            if (codigo != 200) throw new NoLlega("código " + codigo);
        } catch (Rechazado | NoLlega e) {
            throw e;
        } catch (IOException e) {
            throw clasificar(e);
        } finally {
            if (c != null) c.disconnect();
        }
    }

    /** Le pide a la compu que borre este celu de su lista. */
    public static void desvincular(Compu compu) throws IOException {
        HttpsURLConnection c = null;
        try {
            c = abrir(compu.host, compu.puerto, "/desvincular", desdeHex(compu.huella), 5000);
            c.setRequestMethod("POST");
            c.setRequestProperty("Authorization", "Bearer " + compu.token);
            c.setFixedLengthStreamingMode(0);
            c.setDoOutput(true);
            c.getOutputStream().close();
            int codigo = c.getResponseCode();
            if (codigo != 200) throw new Rechazado("código " + codigo);
        } catch (Rechazado e) {
            throw e;
        } catch (IOException e) {
            throw clasificar(e);
        } finally {
            if (c != null) c.disconnect();
        }
    }

    /** Manda un archivo o un texto. clase es "archivo" o "texto". */
    public static void enviar(Compu compu, InputStream datos, long largo, String nombre, String clase, Avance avance) throws IOException {
        enviar(compu, datos, largo, nombre, clase, avance, false);
    }

    /** demorado: sale de la cola, no de un envío de recién. La compu no lo mezcla con lo nuevo ni lo copia sola. */
    public static void enviar(Compu compu, InputStream datos, long largo, String nombre, String clase, Avance avance, boolean demorado) throws IOException {
        hola(compu);  // si el vínculo no vale, se sabe antes de subir nada: el servidor corta sin leer
        HttpsURLConnection c = null;
        try {
            c = abrir(compu.host, compu.puerto, "/enviar", desdeHex(compu.huella), 120000);
            c.setRequestMethod("POST");
            c.setRequestProperty("Authorization", "Bearer " + compu.token);
            c.setRequestProperty("X-Clase", clase);
            c.setRequestProperty("X-Nombre", URLEncoder.encode(nombre == null ? "" : nombre, "UTF-8").replace("+", "%20"));
            if (demorado) c.setRequestProperty("X-Demorado", "1");
            c.setFixedLengthStreamingMode(largo);
            c.setDoOutput(true);
            long total = 0;
            try (OutputStream salida = c.getOutputStream()) {
                byte[] trozo = new byte[64 * 1024];
                int n;
                while ((n = datos.read(trozo)) != -1) {
                    salida.write(trozo, 0, n);
                    total += n;
                    if (avance != null) avance.enviados(total);
                }
            }
            int codigo = c.getResponseCode();
            if (codigo == 401) throw new Rechazado("desvinculado");
            if (codigo != 200) throw new NoLlega("código " + codigo);
        } catch (Rechazado | NoLlega e) {
            throw e;
        } catch (IOException e) {
            throw clasificar(e);
        } finally {
            if (c != null) c.disconnect();
        }
    }

    /** Busca la compu en la red si cambió de dirección. Devuelve su nuevo host o null. */
    public static String descubrir(Compu compu, int puertoUdp) {
        byte[] pedido = ("TCHN?" + compu.huella.substring(0, 16)).getBytes();
        try (DatagramSocket s = new DatagramSocket()) {
            s.setBroadcast(true);
            s.setSoTimeout(700);
            String[] destinos = {"255.255.255.255", subred(compu.host)};
            for (int intento = 0; intento < 3; intento++) {
                for (String destino : destinos) {
                    if (destino == null) continue;
                    try { s.send(new DatagramPacket(pedido, pedido.length, InetAddress.getByName(destino), puertoUdp)); }
                    catch (IOException ignorado) { }
                }
                try {
                    DatagramPacket respuesta = new DatagramPacket(new byte[64], 64);
                    s.receive(respuesta);
                    String texto = new String(respuesta.getData(), 0, respuesta.getLength());
                    if (texto.startsWith("TCHN!")) {
                        compu.puerto = Integer.parseInt(texto.substring(5));
                        compu.host = respuesta.getAddress().getHostAddress();
                        return compu.host;
                    }
                } catch (SocketTimeoutException esperar) {
                    // otro intento
                }
            }
        } catch (IOException | NumberFormatException e) {
            return null;
        }
        return null;
    }

    private static String subred(String host) {
        int i = host.lastIndexOf('.');
        return i < 0 ? null : host.substring(0, i) + ".255";
    }

    private static String leer(InputStream entrada) throws IOException {
        ByteArrayOutputStream salida = new ByteArrayOutputStream();
        byte[] trozo = new byte[4096];
        int n;
        while ((n = entrada.read(trozo)) != -1) salida.write(trozo, 0, n);
        return salida.toString("UTF-8");
    }

    private static String campo(String json, String clave) throws IOException {
        Matcher m = Pattern.compile("\"" + clave + "\":\"((?:[^\"\\\\]|\\\\.)*)\"").matcher(json);
        if (!m.find()) throw new NoLlega("respuesta rara");
        return m.group(1).replace("\\\"", "\"").replace("\\\\", "\\");
    }

    private static String hex(byte[] d) {
        StringBuilder s = new StringBuilder();
        for (byte b : d) s.append(String.format(Locale.ROOT, "%02x", b & 255));
        return s.toString();
    }

    private static byte[] desdeHex(String s) {
        byte[] d = new byte[s.length() / 2];
        for (int i = 0; i < d.length; i++) d[i] = (byte) Integer.parseInt(s.substring(i * 2, i * 2 + 2), 16);
        return d;
    }
}
