using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Net;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;

namespace Tachan
{
    // Solo se conecta a internet si lo pedís: Tachán no consulta nada por su cuenta.
    static class Actualizador
    {
        // La parte pública de ~/.tachan/actualizar.pem, que no está en el sitio. Ver firmar.py.
        const string ClavePublica = "<RSAKeyValue><Modulus>pmnlO5hrq97x3V3zl+bnu35A5vvzod6DOrDbYf63wFKNVOO7VF9sAKFI7226heW8kMrUS+9tkOOIbY/iENqc3D8Bpx2IcVPmU19IotzRU3GfeZokR3Ohrpv3gn8U4UckfeRnb3tF2yqDlR6fQljtNK/HbetH3feRYPtohXuCXq+fB1/DLuekMt2eefCxTAmSZliMzJoupxfFOyaRgQCO6G4SQGTkoABFW6+PAKH1CKLng8zL597LrZ4z35AxpszBhTz0yvInsXhYpuPrtGgy6mH2aXk6RChllH5CjEhxmpvmo9h/QgwGpjSCHWclWNJN5pT1EANXU9IW50HHd4MoD6sp+pMkxRolt4ek6CJhOQbt6RMpyaPReViLzebp0rnAorjtW3TFRaOq6NeDc+WkJJabhCey28Qh1lRpBPEm8jDq5o7kIEVsEwmEeHOk3YYF4xwW5eIJe/8LWubbjRUCBzKsU9Qsaych5Gbm3HZt/t5pM/z5YrDEj5NdOTaMLn0x</Modulus><Exponent>AQAB</Exponent></RSAKeyValue>";

        static string Prueba => Environment.GetEnvironmentVariable("TACHAN_ACTUALIZAR");
        static string Base => Prueba ?? "https://kvothesson.com/tachan/";

        // El programa nuevo sale de la release en GitHub, en un archivo aparte del que bajan los botones de la web.
        // GitHub cuenta cuántas veces se baja: así sabemos cuántos lo siguen usando, sin que Tachán mande nada.
        static string Descarga(string nombre) =>
            Prueba != null ? Prueba + Archivo
            : Regex.IsMatch(nombre, @"^\d+(\.\d+)*$") ? "https://github.com/kvothesson/tachan/releases/download/v" + nombre + "/" + Archivo
            : Base + Marca.Nombre + ".exe";
        const string Archivo = "actualizar-Tachan.exe";

        public static void Buscar(Action<string> avisar)
        {
            new Thread(() =>
            {
                try
                {
                    ServicePointManager.SecurityProtocol = SecurityProtocolType.Tls12;
                    using (var web = new WebClient())
                    {
                        var datos = web.DownloadString(Base + "version.json?t=" + DateTime.UtcNow.Ticks);
                        var codigo = int.Parse(Regex.Match(datos, "\"codigo\"\\s*:\\s*(\\d+)").Groups[1].Value);
                        if (codigo <= VersionApp.Codigo)
                        {
                            avisar(Textos.T("ultima") + ": " + VersionApp.Nombre);
                            return;
                        }
                        var esperado = Regex.Match(datos, "\"exe_sha256\"\\s*:\\s*\"([0-9a-f]{64})\"").Groups[1].Value;
                        // El hash solo descubre una descarga rota: quien controle el sitio lo cambia junto con el exe. La firma, no.
                        if (!FirmaValida(codigo, esperado, Regex.Match(datos, "\"firma\"\\s*:\\s*\"([A-Za-z0-9+/=]+)\"").Groups[1].Value))
                            throw new InvalidDataException("sin firma válida");
                        var exe = web.DownloadData(Descarga(Regex.Match(datos, "\"nombre\"\\s*:\\s*\"([^\"]*)\"").Groups[1].Value));
                        using (var sha = SHA256.Create())
                            if (string.Concat(sha.ComputeHash(exe).Select(b => b.ToString("x2"))) != esperado)
                                throw new InvalidDataException("la descarga no coincide");
                        var carpeta = Path.Combine(Path.GetTempPath(), Marca.Nombre);
                        Directory.CreateDirectory(carpeta);
                        var ruta = Path.Combine(carpeta, Marca.Nombre + ".exe");
                        File.WriteAllBytes(ruta, exe);
                        avisar(Textos.T("actualizando"));
                        // La versión nueva cierra esta y toma su lugar, igual que si la abrieras a mano.
                        // Por el shell: así no hereda el puerto abierto de esta, que dejaría a la nueva sin poder escuchar.
                        using (Process.Start(new ProcessStartInfo(ruta) { UseShellExecute = true })) { }
                    }
                }
                catch (Exception e) when (e is WebException || e is IOException || e is FormatException || e is UnauthorizedAccessException || e is InvalidDataException || e is System.ComponentModel.Win32Exception)
                {
                    avisar(Textos.T("sinred"));
                }
            }) { IsBackground = true }.Start();
        }

        static bool FirmaValida(int codigo, string sha256, string firma)
        {
            using (var rsa = RSA.Create())
            {
                rsa.FromXmlString(ClavePublica);
                try { return rsa.VerifyData(Encoding.ASCII.GetBytes(codigo + "\n" + sha256), Convert.FromBase64String(firma), HashAlgorithmName.SHA256, RSASignaturePadding.Pkcs1); }
                catch (CryptographicException) { return false; }
            }
        }
    }
}
