import com.kvothesson.tachan.Transporte;

import java.io.ByteArrayInputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.Arrays;

/** Habla con el programa de PC real, usando la misma clase que la app. */
public class PruebaTransporte {
    static int fallas = 0;

    static void chequear(String que, boolean bien) {
        System.out.println((bien ? "OK    " : "FALLA ") + que);
        if (!bien) fallas++;
    }

    interface Accion { void correr() throws Exception; }

    static Class<?> errorDe(Accion a) {
        try {
            a.correr();
            return null;
        } catch (Exception e) {
            return e.getClass();
        }
    }

    static void mandar(Transporte.Compu c, byte[] d, String nombre, String clase) throws Exception {
        Transporte.enviar(c, new ByteArrayInputStream(d), d.length, nombre, clase, null);
    }

    public static void main(String[] a) throws Exception {
        String enlace = new String(Files.readAllBytes(Paths.get(a[0])), StandardCharsets.UTF_8);
        int puertoUdp = Integer.parseInt(a[1]);
        byte[] foto = Files.readAllBytes(Paths.get(a[2]));

        Transporte.Enlace e = Transporte.leerEnlace(enlace);
        chequear("lee el enlace del QR", e != null && e.host.contains(".") && e.nombre.length() > 0);
        chequear("rechaza un enlace inventado", Transporte.leerEnlace("tachan://v?c=abc") == null);
        chequear("lee el código pelado", Transporte.leerEnlace(enlace.substring(enlace.indexOf("c=") + 2, enlace.indexOf('&'))) != null);

        Transporte.Enlace malo = Transporte.leerEnlace(enlace);
        malo.huellaParcial = malo.huellaParcial.clone();
        malo.huellaParcial[0] ^= 1;
        chequear("no le habla a otra máquina (huella distinta)",
                errorDe(() -> Transporte.vincular(malo, "intruso")) == Transporte.Impostor.class);

        Transporte.Enlace sinSecreto = Transporte.leerEnlace(enlace);
        sinSecreto.secreto = "000000000000";
        chequear("secreto equivocado no vincula",
                errorDe(() -> Transporte.vincular(sinSecreto, "intruso")) == Transporte.Rechazado.class);

        Transporte.Compu c = Transporte.vincular(e, "Prueba Ñandú");
        chequear("vincula con el QR", c.token != null && c.huella.length() == 64 && c.nombre.length() > 0);
        chequear("el QR no sirve dos veces",
                errorDe(() -> Transporte.vincular(Transporte.leerEnlace(enlace), "otro")) == Transporte.Rechazado.class);
        chequear("hola con token", errorDe(() -> Transporte.hola(c)) == null);

        Transporte.Compu falsa = new Transporte.Compu();
        falsa.host = c.host; falsa.puerto = c.puerto; falsa.huella = c.huella; falsa.nombre = c.nombre;
        falsa.token = "token-inventado";
        chequear("sin token no entra", errorDe(() -> Transporte.hola(falsa)) == Transporte.Rechazado.class);
        chequear("sin token no manda", errorDe(() -> mandar(falsa, foto, "x.jpg", "archivo")) == Transporte.Rechazado.class);

        long[] avance = {0};
        Transporte.enviar(c, new ByteArrayInputStream(foto), foto.length, "foto de prueba.jpg", "archivo", n -> avance[0] = n);
        chequear("manda una foto con avance", avance[0] == foto.length);
        Thread.sleep(1500);

        mandar(c, "https://example.com/una/pagina".getBytes(StandardCharsets.UTF_8), "", "texto");
        Thread.sleep(1500);
        mandar(c, "Hola desde el celu: ñandú 🐦".getBytes(StandardCharsets.UTF_8), "", "texto");
        Thread.sleep(1500);

        byte[] grande = new byte[40 * 1024 * 1024];
        Arrays.fill(grande, (byte) 7);
        long t0 = System.currentTimeMillis();
        mandar(c, grande, "..\\..\\raro: CON?.bin", "archivo");
        System.out.println("      40 MB en " + (System.currentTimeMillis() - t0) + " ms");
        chequear("manda un archivo grande con nombre peligroso", true);
        Thread.sleep(1500);
        mandar(c, "MZ falso".getBytes(), "programa.exe", "archivo");
        Thread.sleep(1500);

        Transporte.Compu movida = new Transporte.Compu();
        movida.host = "10.255.255.1"; movida.puerto = c.puerto; movida.huella = c.huella; movida.token = c.token;
        chequear("no la encuentra en la dirección vieja", errorDe(() -> Transporte.hola(movida)) == Transporte.NoLlega.class);
        Transporte.Compu buscada = new Transporte.Compu();
        buscada.host = c.host; buscada.puerto = 1; buscada.huella = c.huella; buscada.token = c.token;
        String hallada = Transporte.descubrir(buscada, puertoUdp);
        chequear("la encuentra por la red: " + hallada, hallada != null && buscada.puerto == c.puerto);
        chequear("y sigue siendo ella", errorDe(() -> Transporte.hola(buscada)) == null);

        Transporte.Compu otraHuella = new Transporte.Compu();
        otraHuella.host = c.host; otraHuella.puerto = c.puerto; otraHuella.token = c.token;
        otraHuella.huella = "00" + c.huella.substring(2);
        chequear("tras vincular, otra huella se rechaza (y el token no se manda)",
                errorDe(() -> Transporte.hola(otraHuella)) == Transporte.Impostor.class);
        chequear("otra huella no responde a la búsqueda", Transporte.descubrir(otraHuellaSinHost(c), puertoUdp) == null);

        chequear("desvincular con token ajeno no borra nada", errorDe(() -> Transporte.desvincular(falsa)) == Transporte.Rechazado.class);
        chequear("sigue vinculada", errorDe(() -> Transporte.hola(c)) == null);
        chequear("se desvincula desde el celu", errorDe(() -> Transporte.desvincular(c)) == null);
        chequear("y la compu ya no la reconoce", errorDe(() -> Transporte.hola(c)) == Transporte.Rechazado.class);

        System.out.println(fallas == 0 ? "TODO BIEN" : ("FALLAS: " + fallas));
        System.exit(fallas == 0 ? 0 : 1);
    }

    static Transporte.Compu otraHuellaSinHost(Transporte.Compu c) {
        Transporte.Compu o = new Transporte.Compu();
        o.host = c.host; o.puerto = c.puerto; o.token = c.token;
        o.huella = "ffffffffffffffff" + c.huella.substring(16);
        return o;
    }
}
