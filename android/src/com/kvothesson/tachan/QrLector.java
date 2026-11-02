package com.kvothesson.tachan;

import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

/**
 * Lee los QR que genera pc/Qr.cs: modo byte, corrección M, versiones 1 a 9. Java puro para probarlo en la PC.
 * Va escrito acá porque la cámara de cada marca abre distinto los enlaces tachan:// y las librerías pesan más que la app.
 */
final class QrLector {
    private static final int[] ECC_POR_BLOQUE = {-1, 10, 16, 26, 18, 24, 16, 18, 22, 22};
    private static final int[] BLOQUES = {-1, 1, 1, 1, 2, 2, 4, 4, 4, 5};
    private static final long TIEMPO_POR_CUADRO_NS = 400_000_000L;
    private static final int[] EXP = new int[512];
    private static final int[] LOG = new int[256];

    static {
        int x = 1;
        for (int i = 0; i < 255; i++) {
            EXP[i] = x;
            LOG[x] = i;
            x <<= 1;
            if (x > 255) x ^= 0x11D;
        }
        for (int i = 255; i < 512; i++) EXP[i] = EXP[i - 255];
    }

    private QrLector() { }

    /** Busca un QR en una imagen de luminancia, por ejemplo el primer plano de un cuadro NV21. Devuelve su texto o null. */
    static String leer(byte[] luz, int ancho, int alto) {
        boolean[] negro = binarizar(luz, ancho, alto);
        List<Buscador> hallados = buscar(negro, ancho, alto);
        int n = Math.min(hallados.size(), 8);
        long limite = System.nanoTime() + TIEMPO_POR_CUADRO_NS;
        for (int a = 0; a < n; a++)
            for (int b = a + 1; b < n; b++)
                for (int c = b + 1; c < n; c++) {
                    if (System.nanoTime() > limite) return null;  // el próximo cuadro puede salir mejor
                    String texto = probar(negro, ancho, alto, hallados.get(a), hallados.get(b), hallados.get(c));
                    if (texto != null) return texto;
                }
        return null;
    }

    // --- De la imagen a blanco y negro ---

    /** Compara cada píxel con el promedio de su zona: aguanta sombras y pantallas con brillo desparejo. */
    private static boolean[] binarizar(byte[] luz, int w, int h) {
        int[] suma = new int[(w + 1) * (h + 1)];
        for (int y = 0; y < h; y++) {
            int fila = 0;
            for (int x = 0; x < w; x++) {
                fila += luz[y * w + x] & 255;
                suma[(y + 1) * (w + 1) + x + 1] = suma[y * (w + 1) + x + 1] + fila;
            }
        }
        int radio = Math.max(8, Math.min(w, h) / 16);
        boolean[] negro = new boolean[w * h];
        for (int y = 0; y < h; y++) {
            int y0 = Math.max(0, y - radio), y1 = Math.min(h, y + radio + 1);
            for (int x = 0; x < w; x++) {
                int x0 = Math.max(0, x - radio), x1 = Math.min(w, x + radio + 1);
                int total = suma[y1 * (w + 1) + x1] - suma[y0 * (w + 1) + x1] - suma[y1 * (w + 1) + x0] + suma[y0 * (w + 1) + x0];
                int area = (x1 - x0) * (y1 - y0);
                negro[y * w + x] = (luz[y * w + x] & 255) * area * 100 < total * 92;
            }
        }
        return negro;
    }

    // --- Los tres cuadrados de las esquinas ---

    private static final class Buscador {
        double x, y, modulo;
        int votos = 1;
    }

    private static boolean proporcion(int[] c) {
        int total = c[0] + c[1] + c[2] + c[3] + c[4];
        if (total < 7 || c[0] == 0 || c[1] == 0 || c[2] == 0 || c[3] == 0 || c[4] == 0) return false;
        double m = total / 7.0, tolerancia = m * 0.6;
        return Math.abs(c[0] - m) < tolerancia && Math.abs(c[1] - m) < tolerancia && Math.abs(c[2] - 3 * m) < 3 * tolerancia
                && Math.abs(c[3] - m) < tolerancia && Math.abs(c[4] - m) < tolerancia;
    }

    private static List<Buscador> buscar(boolean[] negro, int w, int h) {
        List<Buscador> hallados = new ArrayList<>();
        int[] c = new int[5];
        for (int y = 0; y < h; y += 2) {
            java.util.Arrays.fill(c, 0);
            int estado = 0;
            for (int x = 0; x < w; x++) {
                boolean n = negro[y * w + x];
                if (n == (estado % 2 == 0)) {
                    if (estado > 0 || n) c[estado]++;
                } else if (estado < 4) {
                    c[++estado]++;
                } else {
                    if (proporcion(c)) confirmar(negro, w, h, c, x, y, hallados);
                    c[0] = c[2];
                    c[1] = c[3];
                    c[2] = c[4];
                    c[3] = 1;
                    c[4] = 0;
                    estado = 3;
                }
            }
        }
        hallados.sort((a, b) -> b.votos - a.votos);
        return hallados;
    }

    /** Una fila puede coincidir de casualidad: el cuadrado de verdad también da la proporción en vertical. */
    private static void confirmar(boolean[] negro, int w, int h, int[] c, int fin, int y, List<Buscador> hallados) {
        double cx = fin - c[4] - c[3] - c[2] / 2.0;
        int x = (int) cx;
        int arriba = y;
        int[] v = new int[5];
        while (arriba >= 0 && negro[arriba * w + x]) { v[2]++; arriba--; }
        while (arriba >= 0 && !negro[arriba * w + x]) { v[1]++; arriba--; }
        while (arriba >= 0 && negro[arriba * w + x]) { v[0]++; arriba--; }
        int abajo = y + 1;
        while (abajo < h && negro[abajo * w + x]) { v[2]++; abajo++; }
        while (abajo < h && !negro[abajo * w + x]) { v[3]++; abajo++; }
        while (abajo < h && negro[abajo * w + x]) { v[4]++; abajo++; }
        if (!proporcion(v)) return;
        double cy = abajo - v[4] - v[3] - v[2] / 2.0;
        double modulo = (c[0] + c[1] + c[2] + c[3] + c[4] + v[0] + v[1] + v[2] + v[3] + v[4]) / 14.0;
        for (Buscador b : hallados)
            if (Math.abs(b.x - cx) < modulo * 2 && Math.abs(b.y - cy) < modulo * 2) {
                b.x = (b.x * b.votos + cx) / (b.votos + 1);
                b.y = (b.y * b.votos + cy) / (b.votos + 1);
                b.modulo = (b.modulo * b.votos + modulo) / (b.votos + 1);
                b.votos++;
                return;
            }
        Buscador nuevo = new Buscador();
        nuevo.x = cx;
        nuevo.y = cy;
        nuevo.modulo = modulo;
        hallados.add(nuevo);
    }

    // --- De la imagen a la grilla ---

    private static double distancia(Buscador a, Buscador b) {
        return Math.hypot(a.x - b.x, a.y - b.y);
    }

    private static String probar(boolean[] negro, int w, int h, Buscador p, Buscador q, Buscador r) {
        // La esquina de arriba a la izquierda está enfrente del lado más largo.
        double pq = distancia(p, q), pr = distancia(p, r), qr = distancia(q, r);
        Buscador a, b, c;
        if (qr >= pq && qr >= pr) { a = p; b = q; c = r; }
        else if (pr >= pq && pr >= qr) { a = q; b = p; c = r; }
        else { a = r; b = p; c = q; }
        double cruz = (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x);
        if (cruz < 0) { Buscador t = b; b = c; c = t; }

        // Tres puntos sueltos casi nunca forman una escuadra: se descartan sin gastar tiempo en leerlos.
        double ab = distancia(a, b), ac = distancia(a, c);
        double coseno = ((b.x - a.x) * (c.x - a.x) + (b.y - a.y) * (c.y - a.y)) / (ab * ac);
        if (Math.abs(coseno) > 0.6 || Math.max(ab, ac) > 1.8 * Math.min(ab, ac)) return null;

        double modulo = (a.modulo + b.modulo + c.modulo) / 3;
        if (Math.max(a.modulo, Math.max(b.modulo, c.modulo)) > 2.2 * Math.min(a.modulo, Math.min(b.modulo, c.modulo))) return null;
        // Girado a 45° el módulo medido sale más grande: se prueban todas las versiones, de la más probable a la menos.
        double separacion = (distancia(a, b) + distancia(a, c)) / 2;
        int estimado = (int) Math.round(separacion / modulo) + 7;
        Integer[] versiones = {1, 2, 3, 4, 5, 6, 7, 8, 9};
        java.util.Arrays.sort(versiones, (u, v) -> Math.abs(u * 4 + 17 - estimado) - Math.abs(v * 4 + 17 - estimado));
        for (int version : versiones) {
            int lado = version * 4 + 17;
            modulo = separacion / (lado - 7);
            double f = (lado - 10.0) / (lado - 7.0);
            double ex = a.x + f * (b.x - a.x) + f * (c.x - a.x), ey = a.y + f * (b.y - a.y) + f * (c.y - a.y);
            double[][] esquinas = version == 1 ? new double[][]{{a.x + b.x - a.x + c.x - a.x, a.y + b.y - a.y + c.y - a.y}}
                    : new double[][]{alineacion(negro, w, h, ex, ey, modulo), {ex, ey}};
            for (double[] d : esquinas) {
                double fin = version == 1 ? lado - 3.5 : lado - 6.5;
                double[] t = transformar(new double[]{3.5, 3.5, lado - 3.5, 3.5, 3.5, lado - 3.5, fin, fin},
                        new double[]{a.x, a.y, b.x, b.y, c.x, c.y, d[0], d[1]});
                if (t == null) continue;
                String texto = decodificar(muestrear(negro, w, h, t, lado), version);
                if (texto != null) return texto;
            }
        }
        return null;
    }

    /** Busca cerca de la estimación el cuadradito de alineación: centro negro, anillo blanco, anillo negro. */
    private static double[] alineacion(boolean[] negro, int w, int h, double ex, double ey, double m) {
        int radio = (int) Math.ceil(m * 7);
        int mejor = Integer.MIN_VALUE;
        double[] res = {ex, ey};
        for (int dy = -radio; dy <= radio; dy++)
            for (int dx = -radio; dx <= radio; dx++) {
                double x = ex + dx, y = ey + dy;
                int puntos = 0;
                for (int i = -2; i <= 2; i++)
                    for (int j = -2; j <= 2; j++) {
                        int anillo = Math.max(Math.abs(i), Math.abs(j));
                        int px = (int) Math.round(x + i * m), py = (int) Math.round(y + j * m);
                        if (px < 0 || py < 0 || px >= w || py >= h) continue;
                        puntos += negro[py * w + px] == (anillo != 1) ? 1 : -1;
                    }
                puntos = puntos * 1000 - dx * dx - dy * dy;
                if (puntos > mejor) {
                    mejor = puntos;
                    res = new double[]{x, y};
                }
            }
        return res;
    }

    /** La perspectiva que lleva cuatro puntos de la grilla a sus cuatro puntos en la imagen. */
    private static double[] transformar(double[] de, double[] a) {
        double[][] m = new double[8][9];
        for (int i = 0; i < 4; i++) {
            double x = de[2 * i], y = de[2 * i + 1], u = a[2 * i], v = a[2 * i + 1];
            m[2 * i] = new double[]{x, y, 1, 0, 0, 0, -u * x, -u * y, u};
            m[2 * i + 1] = new double[]{0, 0, 0, x, y, 1, -v * x, -v * y, v};
        }
        for (int c = 0; c < 8; c++) {
            int pivote = c;
            for (int f = c + 1; f < 8; f++) if (Math.abs(m[f][c]) > Math.abs(m[pivote][c])) pivote = f;
            if (Math.abs(m[pivote][c]) < 1e-9) return null;
            double[] t = m[c]; m[c] = m[pivote]; m[pivote] = t;
            for (int f = 0; f < 8; f++) {
                if (f == c) continue;
                double k = m[f][c] / m[c][c];
                for (int j = c; j < 9; j++) m[f][j] -= k * m[c][j];
            }
        }
        double[] h = new double[8];
        for (int i = 0; i < 8; i++) h[i] = m[i][8] / m[i][i];
        return h;
    }

    private static boolean[][] muestrear(boolean[] negro, int w, int h, double[] t, int lado) {
        boolean[][] g = new boolean[lado][lado];
        for (int y = 0; y < lado; y++)
            for (int x = 0; x < lado; x++) {
                double mx = x + 0.5, my = y + 0.5;
                double d = t[6] * mx + t[7] * my + 1;
                int px = (int) Math.round((t[0] * mx + t[1] * my + t[2]) / d);
                int py = (int) Math.round((t[3] * mx + t[4] * my + t[5]) / d);
                g[y][x] = px >= 0 && py >= 0 && px < w && py < h && negro[py * w + px];
            }
        return g;
    }

    // --- De la grilla al texto: lo inverso de pc/Qr.cs ---

    static String decodificar(boolean[][] g, int version) {
        int lado = g.length;
        int mascara = leerMascara(g, lado);
        if (mascara < 0) return null;
        boolean[][] fijo = zonasFijas(version, lado);
        int crudos = (16 * version + 128) * version + 64;
        if (version >= 2) {
            int a = version / 7 + 2;
            crudos -= (25 * a - 10) * a - 55;
            if (version >= 7) crudos -= 36;
        }
        int largo = crudos / 8;
        int[] palabras = new int[largo];
        int i = 0;
        for (int derecha = lado - 1; derecha >= 1; derecha -= 2) {
            if (derecha == 6) derecha = 5;
            boolean sube = ((derecha + 1) & 2) == 0;
            for (int vert = 0; vert < lado; vert++)
                for (int j = 0; j < 2; j++) {
                    int x = derecha - j, y = sube ? lado - 1 - vert : vert;
                    if (fijo[y][x] || i >= largo * 8) continue;
                    if (g[y][x] != invertir(mascara, x, y)) palabras[i >> 3] |= 1 << (7 - (i & 7));
                    i++;
                }
        }
        int[] datos = corregir(palabras, version);
        return datos == null ? null : leerBytes(datos);
    }

    private static int leerMascara(boolean[][] g, int lado) {
        int primera = 0, segunda = 0;
        for (int i = 0; i < 15; i++) {
            int x1, y1, x2, y2;
            if (i <= 5) { x1 = 8; y1 = i; }
            else if (i == 6) { x1 = 8; y1 = 7; }
            else if (i == 7) { x1 = 8; y1 = 8; }
            else if (i == 8) { x1 = 7; y1 = 8; }
            else { x1 = 14 - i; y1 = 8; }
            if (i < 8) { x2 = lado - 1 - i; y2 = 8; }
            else { x2 = 8; y2 = lado - 15 + i; }
            if (g[y1][x1]) primera |= 1 << i;
            if (g[y2][x2]) segunda |= 1 << i;
        }
        int mejor = -1, menor = 4;
        for (int m = 0; m < 8; m++) {
            int resto = m;
            for (int i = 0; i < 10; i++) resto = (resto << 1) ^ ((resto >> 9) * 0x537);
            int esperado = (m << 10 | resto) ^ 0x5412;
            int errores = Math.min(Integer.bitCount(esperado ^ primera), Integer.bitCount(esperado ^ segunda));
            if (errores < menor) { menor = errores; mejor = m; }
        }
        return mejor;
    }

    private static boolean[][] zonasFijas(int version, int lado) {
        boolean[][] f = new boolean[lado][lado];
        for (int i = 0; i < lado; i++) { f[i][6] = true; f[6][i] = true; }
        rellenar(f, 0, 0, 9, 9);
        rellenar(f, lado - 8, 0, lado, 9);
        rellenar(f, 0, lado - 8, 9, lado);
        if (version >= 2) {
            int cantidad = version / 7 + 2;
            int paso = (version * 8 + cantidad * 3 + 5) / (cantidad * 4 - 4) * 2;
            int[] pos = new int[cantidad];
            pos[0] = 6;
            for (int i = cantidad - 1, p = lado - 7; i >= 1; i--, p -= paso) pos[i] = p;
            for (int i = 0; i < cantidad; i++)
                for (int j = 0; j < cantidad; j++)
                    if (!(i == 0 && j == 0 || i == 0 && j == cantidad - 1 || i == cantidad - 1 && j == 0))
                        rellenar(f, pos[i] - 2, pos[j] - 2, pos[i] + 3, pos[j] + 3);
        }
        if (version >= 7) {
            rellenar(f, lado - 11, 0, lado - 8, 6);
            rellenar(f, 0, lado - 11, 6, lado - 8);
        }
        return f;
    }

    private static void rellenar(boolean[][] f, int x0, int y0, int x1, int y1) {
        for (int y = y0; y < y1; y++)
            for (int x = x0; x < x1; x++) f[y][x] = true;
    }

    private static boolean invertir(int m, int x, int y) {
        switch (m) {
            case 0: return (x + y) % 2 == 0;
            case 1: return y % 2 == 0;
            case 2: return x % 3 == 0;
            case 3: return (x + y) % 3 == 0;
            case 4: return (x / 3 + y / 2) % 2 == 0;
            case 5: return x * y % 2 + x * y % 3 == 0;
            case 6: return (x * y % 2 + x * y % 3) % 2 == 0;
            default: return ((x + y) % 2 + x * y % 3) % 2 == 0;
        }
    }

    private static int[] corregir(int[] palabras, int version) {
        int cantidad = BLOQUES[version], ecc = ECC_POR_BLOQUE[version];
        int largoCorto = palabras.length / cantidad;
        int cortos = cantidad - palabras.length % cantidad;
        int[][] bloques = new int[cantidad][];
        for (int j = 0; j < cantidad; j++) bloques[j] = new int[largoCorto + (j < cortos ? 0 : 1)];
        int k = 0;
        for (int i = 0; i <= largoCorto; i++)
            for (int j = 0; j < cantidad; j++) {
                if (i == largoCorto - ecc && j < cortos) continue;
                if (i == largoCorto && j < cortos) continue;
                int destino = i > largoCorto - ecc && j < cortos ? i - 1 : i;
                bloques[j][destino] = palabras[k++];
            }
        int total = 0;
        for (int j = 0; j < cantidad; j++) {
            if (!reedSolomon(bloques[j], ecc)) return null;
            total += bloques[j].length - ecc;
        }
        int[] datos = new int[total];
        int d = 0;
        for (int j = 0; j < cantidad; j++)
            for (int i = 0; i < bloques[j].length - ecc; i++) datos[d++] = bloques[j][i];
        return datos;
    }

    private static int mult(int a, int b) {
        return a == 0 || b == 0 ? 0 : EXP[LOG[a] + LOG[b]];
    }

    /** Corrige el bloque en su lugar. Devuelve false si tiene más errores de los que se pueden arreglar. */
    private static boolean reedSolomon(int[] b, int ecc) {
        int[] s = new int[ecc];
        boolean limpio = true;
        for (int j = 0; j < ecc; j++) {
            int v = 0;
            for (int c : b) v = mult(v, EXP[j]) ^ c;
            s[j] = v;
            if (v != 0) limpio = false;
        }
        if (limpio) return true;

        // Berlekamp-Massey: el polinomio que ubica los errores, con el término de grado 0 primero.
        int[] sigma = new int[ecc + 1], previo = new int[ecc + 1];
        sigma[0] = 1;
        previo[0] = 1;
        int grado = 0, salto = 1, ultimo = 1;
        for (int n = 0; n < ecc; n++) {
            int delta = s[n];
            for (int i = 1; i <= grado; i++) delta ^= mult(sigma[i], s[n - i]);
            if (delta == 0) {
                salto++;
            } else {
                int[] copia = sigma.clone();
                int factor = mult(delta, EXP[255 - LOG[ultimo]]);
                for (int i = 0; i + salto <= ecc; i++) sigma[i + salto] ^= mult(factor, previo[i]);
                if (2 * grado <= n) {
                    grado = n + 1 - grado;
                    previo = copia;
                    ultimo = delta;
                    salto = 1;
                } else {
                    salto++;
                }
            }
        }
        if (2 * grado > ecc) return false;

        int[] omega = new int[ecc];
        for (int i = 0; i < ecc; i++)
            for (int j = 0; j <= i && j <= grado; j++) omega[i] ^= mult(sigma[j], s[i - j]);

        int hallados = 0;
        for (int pos = 0; pos < b.length; pos++) {
            int potencia = b.length - 1 - pos;  // X = alfa^potencia
            int inversa = EXP[(255 - potencia % 255) % 255];
            int valor = 0, derivada = 0, x = 1;
            for (int i = 0; i <= grado; i++) {
                valor ^= mult(sigma[i], x);
                if (i % 2 == 1) derivada ^= mult(sigma[i], EXP[(LOG[x] + 255 - LOG[inversa]) % 255]);
                x = mult(x, inversa);
            }
            if (valor != 0) continue;
            if (derivada == 0) return false;
            int arriba = 0;
            x = 1;
            for (int i = 0; i < ecc; i++) {
                arriba ^= mult(omega[i], x);
                x = mult(x, inversa);
            }
            // Con la primera raíz en alfa^0, Forney lleva un factor X.
            int magnitud = mult(mult(EXP[potencia % 255], arriba), EXP[255 - LOG[derivada]]);
            b[pos] ^= magnitud;
            hallados++;
        }
        if (hallados != grado) return false;
        for (int j = 0; j < ecc; j++) {
            int v = 0;
            for (int c : b) v = mult(v, EXP[j]) ^ c;
            if (v != 0) return false;
        }
        return true;
    }

    private static String leerBytes(int[] d) {
        if (d.length < 2 || d[0] >> 4 != 4) return null;
        int cuantos = (d[0] & 15) << 4 | d[1] >> 4;
        if (2 + cuantos > d.length) return null;
        byte[] salida = new byte[cuantos];
        for (int i = 0; i < cuantos; i++) salida[i] = (byte) ((d[i + 1] & 15) << 4 | d[i + 2] >> 4);
        return new String(salida, StandardCharsets.UTF_8);
    }
}
