using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Security;
using System.Net.Sockets;
using System.Runtime.InteropServices;
using System.Security.Authentication;
using System.Security.Cryptography;
using System.Security.Cryptography.X509Certificates;
using System.Text;
using System.Threading;

namespace Tachan
{
    class Recibido
    {
        public string Ruta;   // null si es texto
        public string Texto;  // null si es archivo
        public bool Demorado;  // se mandó antes, con la compu apagada: salió solo de la cola del celu
    }

    class Servidor
    {
        const long MargenDisco = 200L * 1024 * 1024;
        const int MaximoTexto = 2 * 1024 * 1024;
        const int MaximoCabecera = 16 * 1024;
        const int MaximoIntentos = 5;

        readonly X509Certificate2 identidad;
        readonly byte[] huella;
        readonly SemaphoreSlim cupos = new SemaphoreSlim(8);
        TcpListener oyente;
        UdpClient udp;
        volatile bool apagando;
        byte[] secretoVinculo;
        int intentosVinculo;
        readonly object cerrojoVinculo = new object();

        public int Puerto { get; private set; }
        public event Action<Recibido> Llegada;
        public event Action<Dispositivo> Vinculado;
        public event Action SecretoAgotado;

        public Servidor(X509Certificate2 identidad)
        {
            this.identidad = identidad;
            huella = Datos.Huella(identidad);
        }

        public void Arrancar()
        {
            var puerto = int.TryParse(Environment.GetEnvironmentVariable("TACHAN_PUERTO"), out var p) ? p : Marca.PuertoTcp;
            oyente = new TcpListener(IPAddress.Any, puerto);
            oyente.Start();
            Puerto = ((IPEndPoint)oyente.LocalEndpoint).Port;
            new Thread(BucleTcp) { IsBackground = true }.Start();
            udp = new UdpClient(new IPEndPoint(IPAddress.Any, puerto + 1));
            new Thread(BucleUdp) { IsBackground = true }.Start();
        }

        public void Apagar()
        {
            apagando = true;
            oyente?.Stop();
            udp?.Close();
        }

        // Mientras la ventana de vincular está abierta hay un secreto válido; al cerrarla, ninguno.
        public string AbrirVinculo()
        {
            lock (cerrojoVinculo)
            {
                secretoVinculo = new byte[6];
                using (var rng = RandomNumberGenerator.Create()) rng.GetBytes(secretoVinculo);
                intentosVinculo = 0;
                return CodigoVinculo.Armar(IpLocal().GetAddressBytes(), Puerto, secretoVinculo, huella);
            }
        }

        public void CerrarVinculo()
        {
            lock (cerrojoVinculo) secretoVinculo = null;
        }

        public static IPAddress IpLocal()
        {
            using (var s = new Socket(AddressFamily.InterNetwork, SocketType.Dgram, ProtocolType.Udp))
            {
                s.Connect("192.0.2.1", 9);  // no manda nada: solo elige la placa de red
                return ((IPEndPoint)s.LocalEndPoint).Address;
            }
        }

        // Responde solo a quien ya conoce esta compu: el pedido lleva el comienzo de su huella.
        void BucleUdp()
        {
            var esperado = Encoding.ASCII.GetBytes("TCHN?" + Datos.Hex(huella).Substring(0, 16));
            var respuesta = Encoding.ASCII.GetBytes("TCHN!" + Puerto);
            while (!apagando)
            {
                try
                {
                    var origen = new IPEndPoint(IPAddress.Any, 0);
                    var datos = udp.Receive(ref origen);
                    if (datos.SequenceEqual(esperado)) udp.Send(respuesta, respuesta.Length, origen);
                }
                catch (SocketException) { }
                catch (ObjectDisposedException) { return; }
            }
        }

        void BucleTcp()
        {
            while (!apagando)
            {
                TcpClient cliente;
                try { cliente = oyente.AcceptTcpClient(); }
                catch (Exception) { return; }
                if (!cupos.Wait(0))
                {
                    cliente.Close();
                    continue;
                }
                ThreadPool.QueueUserWorkItem(_ =>
                {
                    try { Atender(cliente); }
                    catch (Exception) { }  // conexión cortada o cliente que no habla TLS
                    finally
                    {
                        cliente.Close();
                        cupos.Release();
                    }
                });
            }
        }

        void Atender(TcpClient cliente)
        {
            cliente.ReceiveTimeout = 30000;
            cliente.SendTimeout = 30000;
            using (var ssl = new SslStream(cliente.GetStream(), false))
            {
                ssl.AuthenticateAsServer(identidad, false, SslProtocols.Tls12, false);
                var cabeceras = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
                var primera = LeerCabecera(ssl, cabeceras).Split(' ');
                if (primera.Length < 2)
                {
                    Responder(ssl, 400, "{}");
                    return;
                }
                var ruta = primera[0] + " " + primera[1];
                if (ruta == "POST /vincular") Vincular(ssl, cabeceras);
                else if (Autorizado(cabeceras) == null) Responder(ssl, 401, "{}");
                else if (ruta == "GET /hola") Responder(ssl, 200, "{\"nombre\":\"" + Json(Environment.MachineName) + "\"}");
                else if (ruta == "POST /enviar") Enviar(ssl, cabeceras);
                else if (ruta == "POST /desvincular") Desvincular(ssl, cabeceras);
                else Responder(ssl, 404, "{}");
            }
        }

        static string LeerCabecera(Stream s, Dictionary<string, string> cabeceras)
        {
            var bytes = new List<byte>(512);
            while (true)
            {
                var b = s.ReadByte();
                if (b < 0) throw new IOException("cortado");
                bytes.Add((byte)b);
                if (bytes.Count > MaximoCabecera) throw new IOException("cabecera enorme");
                var n = bytes.Count;
                if (n >= 4 && bytes[n - 1] == 10 && bytes[n - 2] == 13 && bytes[n - 3] == 10 && bytes[n - 4] == 13) break;
            }
            var lineas = Encoding.UTF8.GetString(bytes.ToArray()).Split(new[] { "\r\n" }, StringSplitOptions.RemoveEmptyEntries);
            foreach (var linea in lineas.Skip(1))
            {
                var i = linea.IndexOf(':');
                if (i > 0) cabeceras[linea.Substring(0, i).Trim()] = linea.Substring(i + 1).Trim();
            }
            return lineas.Length > 0 ? lineas[0] : "";
        }

        static void Responder(Stream s, int codigo, string json)
        {
            var cuerpo = Encoding.UTF8.GetBytes(json);
            var cabecera = Encoding.ASCII.GetBytes("HTTP/1.1 " + codigo + " X\r\nContent-Type: application/json\r\nContent-Length: "
                + cuerpo.Length + "\r\nConnection: close\r\n\r\n");
            s.Write(cabecera, 0, cabecera.Length);
            s.Write(cuerpo, 0, cuerpo.Length);
            s.Flush();
        }

        static string Json(string texto) =>
            texto.Replace("\\", "\\\\").Replace("\"", "\\\"").Replace("\n", " ").Replace("\r", " ");

        static bool Iguales(byte[] a, byte[] b)
        {
            if (a.Length != b.Length) return false;
            var diferencia = 0;
            for (var i = 0; i < a.Length; i++) diferencia |= a[i] ^ b[i];
            return diferencia == 0;
        }

        Dispositivo Autorizado(Dictionary<string, string> cabeceras)
        {
            if (!cabeceras.TryGetValue("Authorization", out var valor) || !valor.StartsWith("Bearer ")) return null;
            var hash = Encoding.ASCII.GetBytes(Datos.HashToken(valor.Substring(7)));
            lock (Datos.Cerrojo)
            {
                Dispositivo hallado = null;
                foreach (var d in Datos.Dispositivos)
                    if (Iguales(hash, Encoding.ASCII.GetBytes(d.HuellaToken))) hallado = d;
                return hallado;
            }
        }

        void Desvincular(Stream s, Dictionary<string, string> cabeceras)
        {
            var d = Autorizado(cabeceras);
            lock (Datos.Cerrojo) Datos.Dispositivos.RemoveAll(x => x.Id == d.Id);
            Datos.GuardarDispositivos();
            Responder(s, 200, "{}");
        }

        void Vincular(Stream s, Dictionary<string, string> cabeceras)
        {
            string secreto;
            cabeceras.TryGetValue("X-Secreto", out secreto);
            var agotado = false;
            lock (cerrojoVinculo)
            {
                if (secretoVinculo == null || secreto == null || !Iguales(Encoding.ASCII.GetBytes(secreto), Encoding.ASCII.GetBytes(Datos.Hex(secretoVinculo))))
                {
                    if (secretoVinculo != null && ++intentosVinculo >= MaximoIntentos)
                    {
                        secretoVinculo = null;  // demasiados intentos: el QR deja de valer
                        agotado = true;
                    }
                    secreto = null;
                }
                else secretoVinculo = null;  // de un solo uso
            }
            if (agotado) SecretoAgotado?.Invoke();
            if (secreto == null)
            {
                Responder(s, 401, "{}");
                return;
            }
            cabeceras.TryGetValue("X-Dispositivo", out var nombre);
            nombre = Uri.UnescapeDataString(nombre ?? "");
            nombre = new string(nombre.Where(c => !char.IsControl(c)).Take(60).ToArray());
            if (nombre.Length == 0) nombre = "Android";
            var bytes = new byte[32];
            using (var rng = RandomNumberGenerator.Create()) rng.GetBytes(bytes);
            var token = Convert.ToBase64String(bytes).Replace('+', '-').Replace('/', '_').TrimEnd('=');
            var nuevo = new Dispositivo { Id = Guid.NewGuid().ToString("N"), Nombre = nombre, HuellaToken = Datos.HashToken(token) };
            lock (Datos.Cerrojo) Datos.Dispositivos.Add(nuevo);
            Datos.GuardarDispositivos();
            Responder(s, 200, "{\"token\":\"" + token + "\",\"huella\":\"" + Datos.Hex(huella) + "\",\"nombre\":\"" + Json(Environment.MachineName) + "\"}");
            Vinculado?.Invoke(nuevo);
        }

        const int TamanoTrozo = 80 * 1024;  // justo por debajo de donde .NET lo trataría como objeto grande

        void Enviar(Stream s, Dictionary<string, string> cabeceras)
        {
            if (!cabeceras.TryGetValue("Content-Length", out var crudo) || !long.TryParse(crudo, out var largo) || largo < 0)
            {
                Responder(s, 411, "{}");
                return;
            }
            cabeceras.TryGetValue("X-Clase", out var clase);
            var demorado = cabeceras.ContainsKey("X-Demorado");
            if (clase == "texto")
            {
                if (largo > MaximoTexto)
                {
                    Responder(s, 413, "{}");
                    return;
                }
                var datos = new byte[largo];
                var leidos = 0;
                while (leidos < largo)
                {
                    var n = s.Read(datos, leidos, datos.Length - leidos);
                    if (n <= 0) throw new IOException("cortado");
                    leidos += n;
                }
                Responder(s, 200, "{\"ok\":true}");
                Llegada?.Invoke(new Recibido { Texto = Encoding.UTF8.GetString(datos), Demorado = demorado });
                return;
            }

            Directory.CreateDirectory(Datos.Recibidos);
            var libre = new DriveInfo(Path.GetPathRoot(Path.GetFullPath(Datos.Recibidos))).AvailableFreeSpace;
            if (largo + MargenDisco > libre)
            {
                Responder(s, 507, "{}");
                return;
            }
            cabeceras.TryGetValue("X-Nombre", out var nombre);
            var parcial = Path.Combine(Datos.Recibidos, ".recibiendo_" + Guid.NewGuid().ToString("N"));
            try
            {
                using (var f = File.Create(parcial))
                {
                    var trozo = new byte[TamanoTrozo];
                    var restante = largo;
                    while (restante > 0)
                    {
                        var n = s.Read(trozo, 0, (int)Math.Min(trozo.Length, restante));
                        if (n <= 0) throw new IOException("cortado");
                        f.Write(trozo, 0, n);
                        restante -= n;
                    }
                }
                var final = RutaLibre(NombreSeguro(nombre));
                File.Move(parcial, final);
                MarcarDeInternet(final);
                Responder(s, 200, "{\"ok\":true}");
                Llegada?.Invoke(new Recibido { Ruta = final, Demorado = demorado });
            }
            finally
            {
                if (File.Exists(parcial)) File.Delete(parcial);
            }
        }

        static readonly string[] Reservados = { "CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9", "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9" };

        public static string NombreSeguro(string crudo)
        {
            string nombre;
            try { nombre = Uri.UnescapeDataString(crudo ?? ""); }
            catch (Exception) { nombre = ""; }
            nombre = nombre.Replace('\\', '/');
            nombre = nombre.Substring(nombre.LastIndexOf('/') + 1);
            var invalidos = Path.GetInvalidFileNameChars();
            nombre = new string(nombre.Select(c => invalidos.Contains(c) || c < 32 ? '_' : c).ToArray()).Trim(' ', '.');
            if (nombre.Length == 0) nombre = "archivo_" + DateTime.Now.ToString("yyyyMMdd_HHmmss");
            if (Reservados.Contains(Path.GetFileNameWithoutExtension(nombre).ToUpperInvariant())) nombre = "_" + nombre;
            if (nombre.Length > 120)
            {
                var extension = Path.GetExtension(nombre);
                if (extension.Length > 20) extension = "";
                nombre = nombre.Substring(0, 120 - extension.Length) + extension;
            }
            return nombre;
        }

        static string RutaLibre(string nombre)
        {
            var ruta = Path.Combine(Datos.Recibidos, nombre);
            for (var n = 2; File.Exists(ruta); n++)
                ruta = Path.Combine(Datos.Recibidos, Path.GetFileNameWithoutExtension(nombre) + "_" + n + Path.GetExtension(nombre));
            return ruta;
        }

        // Windows trata lo recibido como bajado de internet: un .exe avisa antes de abrirse.
        static void MarcarDeInternet(string ruta)
        {
            var h = CreateFile(ruta + ":Zone.Identifier", 0x40000000, 0, IntPtr.Zero, 2, 0, IntPtr.Zero);
            if (h.IsInvalid) return;
            using (var f = new FileStream(h, FileAccess.Write))
            {
                var d = Encoding.ASCII.GetBytes("[ZoneTransfer]\r\nZoneId=3\r\n");
                f.Write(d, 0, d.Length);
            }
        }

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        static extern Microsoft.Win32.SafeHandles.SafeFileHandle CreateFile(string nombre, uint acceso, uint compartir, IntPtr seguridad, uint creacion, uint atributos, IntPtr plantilla);
    }
}
