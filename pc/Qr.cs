using System;
using System.Collections.Generic;
using System.Drawing;
using System.Linq;
using System.Text;

namespace Tachan
{
    // Generador de QR en modo byte, corrección M, versiones 1 a 9: todo lo que necesita el vínculo.
    class Qr
    {
        static readonly int[] EccPorBloque = { -1, 10, 16, 26, 18, 24, 16, 18, 22, 22 };
        static readonly int[] Bloques = { -1, 1, 1, 1, 2, 2, 4, 4, 4, 5 };

        readonly int version;
        public readonly int Lado;
        readonly bool[,] modulos;
        readonly bool[,] funcion;

        Qr(int version)
        {
            this.version = version;
            Lado = version * 4 + 17;
            modulos = new bool[Lado, Lado];
            funcion = new bool[Lado, Lado];
        }

        public bool Negro(int x, int y) => modulos[y, x];

        static int ModulosCrudos(int v)
        {
            var r = (16 * v + 128) * v + 64;
            if (v >= 2)
            {
                var a = v / 7 + 2;
                r -= (25 * a - 10) * a - 55;
                if (v >= 7) r -= 36;
            }
            return r;
        }

        static int Capacidad(int v) => ModulosCrudos(v) / 8 - EccPorBloque[v] * Bloques[v];

        public static Qr Crear(string texto)
        {
            var datos = Encoding.UTF8.GetBytes(texto);
            var v = 1;
            while (v <= 9 && datos.Length + 2 > Capacidad(v)) v++;
            if (v > 9) throw new ArgumentException("texto demasiado largo");

            var bits = new List<bool>();
            Agregar(bits, 4, 4);
            Agregar(bits, datos.Length, 8);
            foreach (var b in datos) Agregar(bits, b, 8);
            var capacidadBits = Capacidad(v) * 8;
            Agregar(bits, 0, Math.Min(4, capacidadBits - bits.Count));
            Agregar(bits, 0, (8 - bits.Count % 8) % 8);
            for (var relleno = 0xEC; bits.Count < capacidadBits; relleno ^= 0xEC ^ 0x11) Agregar(bits, relleno, 8);
            var palabras = new byte[Capacidad(v)];
            for (var i = 0; i < bits.Count; i++)
                if (bits[i]) palabras[i >> 3] |= (byte)(1 << (7 - (i & 7)));

            var qr = new Qr(v);
            qr.DibujarFijos();
            qr.DibujarDatos(qr.ConCorreccion(palabras));
            qr.ElegirMascara();
            return qr;
        }

        static void Agregar(List<bool> bits, int valor, int cuantos)
        {
            for (var i = cuantos - 1; i >= 0; i--) bits.Add(((valor >> i) & 1) != 0);
        }

        void Poner(int x, int y, bool negro)
        {
            modulos[y, x] = negro;
            funcion[y, x] = true;
        }

        void DibujarFijos()
        {
            for (var i = 0; i < Lado; i++)
            {
                Poner(6, i, i % 2 == 0);
                Poner(i, 6, i % 2 == 0);
            }
            Buscador(3, 3);
            Buscador(Lado - 4, 3);
            Buscador(3, Lado - 4);
            var pos = PosicionesAlineacion();
            for (var i = 0; i < pos.Length; i++)
                for (var j = 0; j < pos.Length; j++)
                    if (!(i == 0 && j == 0 || i == 0 && j == pos.Length - 1 || i == pos.Length - 1 && j == 0))
                        Alineacion(pos[i], pos[j]);
            Formato(0);
            VersionBits();
        }

        int[] PosicionesAlineacion()
        {
            if (version == 1) return new int[0];
            var cantidad = version / 7 + 2;
            var paso = (version * 8 + cantidad * 3 + 5) / (cantidad * 4 - 4) * 2;
            var r = new int[cantidad];
            r[0] = 6;
            for (int i = cantidad - 1, p = Lado - 7; i >= 1; i--, p -= paso) r[i] = p;
            return r;
        }

        void Buscador(int x, int y)
        {
            for (var dy = -4; dy <= 4; dy++)
                for (var dx = -4; dx <= 4; dx++)
                {
                    var d = Math.Max(Math.Abs(dx), Math.Abs(dy));
                    int xx = x + dx, yy = y + dy;
                    if (xx >= 0 && xx < Lado && yy >= 0 && yy < Lado) Poner(xx, yy, d != 2 && d != 4);
                }
        }

        void Alineacion(int x, int y)
        {
            for (var dy = -2; dy <= 2; dy++)
                for (var dx = -2; dx <= 2; dx++)
                    Poner(x + dx, y + dy, Math.Max(Math.Abs(dx), Math.Abs(dy)) != 1);
        }

        void Formato(int mascara)
        {
            var datos = mascara;  // los bits de nivel M son 00
            var resto = datos;
            for (var i = 0; i < 10; i++) resto = (resto << 1) ^ ((resto >> 9) * 0x537);
            var bits = (datos << 10 | resto) ^ 0x5412;
            Func<int, bool> b = i => ((bits >> i) & 1) != 0;
            for (var i = 0; i <= 5; i++) Poner(8, i, b(i));
            Poner(8, 7, b(6));
            Poner(8, 8, b(7));
            Poner(7, 8, b(8));
            for (var i = 9; i < 15; i++) Poner(14 - i, 8, b(i));
            for (var i = 0; i < 8; i++) Poner(Lado - 1 - i, 8, b(i));
            for (var i = 8; i < 15; i++) Poner(8, Lado - 15 + i, b(i));
            Poner(8, Lado - 8, true);
        }

        void VersionBits()
        {
            if (version < 7) return;
            var resto = version;
            for (var i = 0; i < 12; i++) resto = (resto << 1) ^ ((resto >> 11) * 0x1F25);
            var bits = version << 12 | resto;
            for (var i = 0; i < 18; i++)
            {
                var b = ((bits >> i) & 1) != 0;
                int a = Lado - 11 + i % 3, c = i / 3;
                Poner(a, c, b);
                Poner(c, a, b);
            }
        }

        byte[] ConCorreccion(byte[] datos)
        {
            int cantidad = Bloques[version], ecc = EccPorBloque[version];
            var crudas = ModulosCrudos(version) / 8;
            var cortos = cantidad - crudas % cantidad;
            var largoCorto = crudas / cantidad;
            var bloques = new List<byte[]>();
            var divisor = Divisor(ecc);
            for (int i = 0, k = 0; i < cantidad; i++)
            {
                var largoDatos = largoCorto - ecc + (i < cortos ? 0 : 1);
                var d = datos.Skip(k).Take(largoDatos).ToArray();
                k += largoDatos;
                var e = Resto(d, divisor);
                var b = new byte[largoCorto + 1];
                Array.Copy(d, 0, b, 0, largoDatos);
                Array.Copy(e, 0, b, largoCorto + 1 - ecc, ecc);
                bloques.Add(b);
            }
            var salida = new List<byte>();
            for (var i = 0; i <= largoCorto; i++)
                for (var j = 0; j < cantidad; j++)
                    if (i != largoCorto - ecc || j >= cortos) salida.Add(bloques[j][i]);
            return salida.ToArray();
        }

        static byte[] Divisor(int grado)
        {
            var r = new byte[grado];
            r[grado - 1] = 1;
            var raiz = 1;
            for (var i = 0; i < grado; i++)
            {
                for (var j = 0; j < grado; j++)
                {
                    r[j] = Mult(r[j], (byte)raiz);
                    if (j + 1 < grado) r[j] ^= r[j + 1];
                }
                raiz = Mult((byte)raiz, 2);
            }
            return r;
        }

        static byte[] Resto(byte[] datos, byte[] divisor)
        {
            var r = new byte[divisor.Length];
            foreach (var b in datos)
            {
                var factor = (byte)(b ^ r[0]);
                Array.Copy(r, 1, r, 0, r.Length - 1);
                r[r.Length - 1] = 0;
                for (var i = 0; i < r.Length; i++) r[i] ^= Mult(divisor[i], factor);
            }
            return r;
        }

        static byte Mult(byte x, byte y)
        {
            var z = 0;
            for (var i = 7; i >= 0; i--)
            {
                z = (z << 1) ^ ((z >> 7) * 0x11D);
                z ^= ((y >> i) & 1) * x;
            }
            return (byte)z;
        }

        void DibujarDatos(byte[] datos)
        {
            var i = 0;
            for (var derecha = Lado - 1; derecha >= 1; derecha -= 2)
            {
                if (derecha == 6) derecha = 5;
                for (var vert = 0; vert < Lado; vert++)
                    for (var j = 0; j < 2; j++)
                    {
                        var x = derecha - j;
                        var sube = ((derecha + 1) & 2) == 0;
                        var y = sube ? Lado - 1 - vert : vert;
                        if (!funcion[y, x] && i < datos.Length * 8)
                        {
                            modulos[y, x] = ((datos[i >> 3] >> (7 - (i & 7))) & 1) != 0;
                            i++;
                        }
                    }
            }
        }

        void AplicarMascara(int m)
        {
            for (var y = 0; y < Lado; y++)
                for (var x = 0; x < Lado; x++)
                {
                    bool invertir;
                    switch (m)
                    {
                        case 0: invertir = (x + y) % 2 == 0; break;
                        case 1: invertir = y % 2 == 0; break;
                        case 2: invertir = x % 3 == 0; break;
                        case 3: invertir = (x + y) % 3 == 0; break;
                        case 4: invertir = (x / 3 + y / 2) % 2 == 0; break;
                        case 5: invertir = x * y % 2 + x * y % 3 == 0; break;
                        case 6: invertir = (x * y % 2 + x * y % 3) % 2 == 0; break;
                        default: invertir = ((x + y) % 2 + x * y % 3) % 2 == 0; break;
                    }
                    if (!funcion[y, x] && invertir) modulos[y, x] = !modulos[y, x];
                }
        }

        void ElegirMascara()
        {
            var mejor = 0;
            var menor = int.MaxValue;
            for (var m = 0; m < 8; m++)
            {
                AplicarMascara(m);
                Formato(m);
                var p = Penalidad();
                if (p < menor)
                {
                    menor = p;
                    mejor = m;
                }
                AplicarMascara(m);
            }
            AplicarMascara(mejor);
            Formato(mejor);
        }

        int Penalidad()
        {
            var total = 0;
            for (var eje = 0; eje < 2; eje++)
                for (var a = 0; a < Lado; a++)
                {
                    var corrida = 0;
                    var color = false;
                    var ventana = 0;
                    for (var b = 0; b < Lado; b++)
                    {
                        var m = eje == 0 ? modulos[a, b] : modulos[b, a];
                        if (b > 0 && m == color)
                        {
                            corrida++;
                            if (corrida == 5) total += 3;
                            else if (corrida > 5) total++;
                        }
                        else
                        {
                            color = m;
                            corrida = 1;
                        }
                        ventana = ((ventana << 1) | (m ? 1 : 0)) & 0x7FF;
                        if (b >= 10 && (ventana == 0x5D0 || ventana == 0x05D)) total += 40;
                    }
                }
            var negros = 0;
            for (var y = 0; y < Lado; y++)
                for (var x = 0; x < Lado; x++)
                {
                    if (modulos[y, x]) negros++;
                    if (x + 1 < Lado && y + 1 < Lado && modulos[y, x] == modulos[y, x + 1] && modulos[y, x] == modulos[y + 1, x] && modulos[y, x] == modulos[y + 1, x + 1])
                        total += 3;
                }
            var pasos = (Math.Abs(negros * 20 - Lado * Lado * 10) + Lado * Lado - 1) / (Lado * Lado) - 1;
            return total + pasos * 10;
        }

        public Bitmap Imagen(int escala, int margen)
        {
            var px = (Lado + margen * 2) * escala;
            var imagen = new Bitmap(px, px);
            using (var g = Graphics.FromImage(imagen))
            {
                g.Clear(Color.White);
                for (var y = 0; y < Lado; y++)
                    for (var x = 0; x < Lado; x++)
                        if (Negro(x, y)) g.FillRectangle(Brushes.Black, (x + margen) * escala, (y + margen) * escala, escala, escala);
            }
            return imagen;
        }
    }
}
