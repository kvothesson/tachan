using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Security.Cryptography.X509Certificates;
using System.Text;

namespace Tachan
{
    class Dispositivo
    {
        public string Id;
        public string Nombre;
        public string HuellaToken;  // solo el hash: el token vive en el celu
    }

    // Ajustes, celus vinculados y certificado. TACHAN_DATOS aísla las pruebas de los datos reales.
    static class Datos
    {
        public static readonly bool EsPrueba = Environment.GetEnvironmentVariable("TACHAN_DATOS") != null;
        public static readonly string Carpeta = Environment.GetEnvironmentVariable("TACHAN_DATOS")
            ?? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), Marca.Nombre);

        static string RutaAjustes => Path.Combine(Carpeta, "ajustes.txt");
        static string RutaDispositivos => Path.Combine(Carpeta, "dispositivos.txt");
        static string RutaCertificado => Path.Combine(Carpeta, "identidad.bin");

        public static bool PegarSolo;
        public static bool Sonido = true;
        public static List<Dispositivo> Dispositivos = new List<Dispositivo>();
        public static readonly object Cerrojo = new object();

        public static string Recibidos
        {
            get
            {
                if (EsPrueba) return Path.Combine(Carpeta, "recibidos");
                SHGetKnownFolderPath(new Guid("374DE290-123F-4565-9164-39C4925E467B"), 0, IntPtr.Zero, out var ruta);
                return Path.Combine(ruta ?? Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), Marca.Nombre);
            }
        }

        [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
        static extern int SHGetKnownFolderPath([MarshalAs(UnmanagedType.LPStruct)] Guid id, uint flags, IntPtr token, out string ruta);

        public static void Cargar()
        {
            Directory.CreateDirectory(Carpeta);
            if (File.Exists(RutaAjustes))
                foreach (var linea in File.ReadAllLines(RutaAjustes))
                {
                    if (linea == "pegar=1") PegarSolo = true;
                    if (linea == "sonido=0") Sonido = false;
                }
            if (File.Exists(RutaDispositivos))
                Dispositivos = File.ReadAllLines(RutaDispositivos).Select(l => l.Split('\t')).Where(p => p.Length == 3)
                    .Select(p => new Dispositivo { Id = p[0], Nombre = p[1], HuellaToken = p[2] }).ToList();
        }

        public static void GuardarAjustes() =>
            File.WriteAllLines(RutaAjustes, new[] { "pegar=" + (PegarSolo ? 1 : 0), "sonido=" + (Sonido ? 1 : 0) });

        public static void GuardarDispositivos()
        {
            lock (Cerrojo)
                File.WriteAllLines(RutaDispositivos, Dispositivos.Select(d => d.Id + "\t" + d.Nombre.Replace('\t', ' ') + "\t" + d.HuellaToken));
        }

        // La identidad de esta compu: el celu la fija al vincular y después no confía en otra.
        public static X509Certificate2 Identidad()
        {
            const X509KeyStorageFlags marcas = X509KeyStorageFlags.UserKeySet | X509KeyStorageFlags.PersistKeySet;
            if (File.Exists(RutaCertificado))
            {
                var guardado = ProtectedData.Unprotect(File.ReadAllBytes(RutaCertificado), null, DataProtectionScope.CurrentUser);
                return new X509Certificate2(guardado, "", marcas);
            }
            using (var clave = RSA.Create(2048))
            {
                var pedido = new CertificateRequest("CN=" + Marca.Nombre, clave, HashAlgorithmName.SHA256, RSASignaturePadding.Pkcs1);
                using (var creado = pedido.CreateSelfSigned(DateTimeOffset.UtcNow.AddDays(-1), DateTimeOffset.UtcNow.AddYears(30)))
                {
                    var pfx = creado.Export(X509ContentType.Pfx, "");
                    File.WriteAllBytes(RutaCertificado, ProtectedData.Protect(pfx, null, DataProtectionScope.CurrentUser));
                    return new X509Certificate2(pfx, "", marcas);
                }
            }
        }

        public static byte[] Huella(X509Certificate2 certificado)
        {
            using (var sha = SHA256.Create()) return sha.ComputeHash(certificado.RawData);
        }

        public static string Hex(byte[] datos) => string.Concat(datos.Select(b => b.ToString("x2")));

        public static string HashToken(string token)
        {
            using (var sha = SHA256.Create()) return Hex(sha.ComputeHash(Encoding.UTF8.GetBytes(token)));
        }
    }

    // Lo que trae el QR: dirección, secreto de un solo uso y el comienzo de la huella, en 22 bytes.
    static class CodigoVinculo
    {
        const string Alfabeto = "abcdefghijklmnopqrstuvwxyz234567";

        public static string Armar(byte[] ip, int puerto, byte[] secreto, byte[] huella)
        {
            var d = new byte[22];
            Array.Copy(ip, 0, d, 0, 4);
            d[4] = (byte)(puerto >> 8);
            d[5] = (byte)puerto;
            Array.Copy(secreto, 0, d, 6, 6);
            Array.Copy(huella, 0, d, 12, 10);
            var salida = new StringBuilder();
            int acumulado = 0, bits = 0;
            foreach (var b in d)
            {
                acumulado = (acumulado << 8) | b;
                bits += 8;
                while (bits >= 5)
                {
                    salida.Append(Alfabeto[(acumulado >> (bits - 5)) & 31]);
                    bits -= 5;
                }
                acumulado &= (1 << bits) - 1;
            }
            if (bits > 0) salida.Append(Alfabeto[(acumulado << (5 - bits)) & 31]);
            return salida.ToString();
        }
    }
}
