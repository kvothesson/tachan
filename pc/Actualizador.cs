using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Net;
using System.Security.Cryptography;
using System.Text.RegularExpressions;
using System.Threading;

namespace Tachan
{
    // Solo se conecta a internet si lo pedís: Tachán no consulta nada por su cuenta.
    static class Actualizador
    {
        static string Base => Environment.GetEnvironmentVariable("TACHAN_ACTUALIZAR") ?? "https://kvothesson.com/tachan/";

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
                        var exe = web.DownloadData(Base + Marca.Nombre + ".exe?t=" + DateTime.UtcNow.Ticks);
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
    }
}
