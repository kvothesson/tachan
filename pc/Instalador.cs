using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Windows.Forms;
using Microsoft.Win32;

namespace Tachan
{
    // Sin instalador aparte: la primera vez que se abre se copia a su carpeta y queda como cualquier programa.
    static class Instalador
    {
        const string ClaveDesinstalar = @"Software\Microsoft\Windows\CurrentVersion\Uninstall\" + Marca.Nombre;

        static string Carpeta => Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs", Marca.Nombre);
        static string Destino => Path.Combine(Carpeta, Marca.Nombre + ".exe");
        static string Acceso => Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs), Marca.Visible + ".lnk");

        public static bool HaceFalta => !Datos.EsPrueba && !string.Equals(Path.GetFullPath(Application.ExecutablePath), Destino, StringComparison.OrdinalIgnoreCase);

        // Devuelve false si no se pudo: el programa igual anda desde donde esté.
        public static bool Mudarse()
        {
            try
            {
                Directory.CreateDirectory(Carpeta);
                File.Copy(Application.ExecutablePath, Destino, true);
                DeleteFile(Destino + ":Zone.Identifier");
                Registrar();
                // Sin el shell de Windows: la copia ya es de confianza y no vuelve a mostrar el cartel.
                using (Process.Start(new ProcessStartInfo(Destino) { UseShellExecute = false })) { }
                return true;
            }
            catch (Exception e) when (e is IOException || e is UnauthorizedAccessException || e is System.ComponentModel.Win32Exception)
            {
                return false;
            }
        }

        static void Registrar()
        {
            CrearAcceso();
            using (var k = Registry.CurrentUser.CreateSubKey(ClaveDesinstalar))
            {
                k.SetValue("DisplayName", Marca.Visible);
                k.SetValue("Publisher", "Kvothesson");
                k.SetValue("DisplayIcon", Destino);
                k.SetValue("InstallLocation", Carpeta);
                k.SetValue("UninstallString", "\"" + Destino + "\" --desinstalar");
                k.SetValue("EstimatedSize", (int)(new FileInfo(Destino).Length / 1024), RegistryValueKind.DWord);
                k.SetValue("NoModify", 1, RegistryValueKind.DWord);
                k.SetValue("NoRepair", 1, RegistryValueKind.DWord);
            }
            if (Inicio.Activo) Inicio.Poner(true, Destino);
        }

        static void CrearAcceso()
        {
            var tipo = Type.GetTypeFromProgID("WScript.Shell");
            var shell = Activator.CreateInstance(tipo);
            try
            {
                var acceso = tipo.InvokeMember("CreateShortcut", System.Reflection.BindingFlags.InvokeMethod, null, shell, new object[] { Acceso });
                var t = acceso.GetType();
                t.InvokeMember("TargetPath", System.Reflection.BindingFlags.SetProperty, null, acceso, new object[] { Destino });
                t.InvokeMember("Save", System.Reflection.BindingFlags.InvokeMethod, null, acceso, null);
                Marshal.ReleaseComObject(acceso);
            }
            finally { Marshal.ReleaseComObject(shell); }
        }

        // Lo llama Windows desde Configuración, Aplicaciones. Lo recibido en Descargas no se toca.
        public static void Desinstalar()
        {
            foreach (var p in Process.GetProcessesByName(Marca.Nombre).Where(x => x.Id != Process.GetCurrentProcess().Id))
            {
                try { p.Kill(); p.WaitForExit(3000); }
                catch (Exception e) when (e is InvalidOperationException || e is System.ComponentModel.Win32Exception) { }
            }
            Inicio.Poner(false);
            if (File.Exists(Acceso)) File.Delete(Acceso);
            Registry.CurrentUser.DeleteSubKeyTree(ClaveDesinstalar, false);
            if (Directory.Exists(Datos.Carpeta)) Directory.Delete(Datos.Carpeta, true);
            // Un programa no se puede borrar a sí mismo mientras corre: lo termina cmd cuando este ya cerró.
            using (Process.Start(new ProcessStartInfo("cmd.exe", "/c ping -n 3 127.0.0.1 >nul & rmdir /s /q \"" + Carpeta + "\"") { CreateNoWindow = true, UseShellExecute = false })) { }
        }

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode)]
        static extern bool DeleteFile(string ruta);
    }
}
