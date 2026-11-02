using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Media;
using System.Runtime.InteropServices;
using System.Security.Principal;
using System.Threading;
using System.Windows.Forms;
using Microsoft.Win32;

namespace Tachan
{
    static class Programa
    {
        [STAThread]
        static void Main(string[] argumentos)
        {
            if (argumentos.Contains("--firewall"))
            {
                Firewall.Agregar();
                return;
            }
            using (var unico = new Mutex(true, NombreUnico("instancia"), out var primero))
            using (var senal = new EventWaitHandle(false, EventResetMode.AutoReset, NombreUnico("abrir")))
            {
                if (!primero)
                {
                    senal.Set();
                    return;
                }
                Application.EnableVisualStyles();
                Application.SetCompatibleTextRenderingDefault(false);
                Datos.Cargar();
                Application.Run(new Bandeja(senal, argumentos.Contains("--oculto")));
            }
        }

        static string NombreUnico(string que)
        {
            var carpeta = Datos.Carpeta.ToLowerInvariant().GetHashCode();
            return "Local\\" + Marca.Nombre + "_" + que + "_" + (Datos.EsPrueba ? carpeta.ToString() : "real");
        }
    }

    static class Firewall
    {
        static string Regla => Marca.Nombre;

        static int Netsh(string argumentos)
        {
            using (var p = Process.Start(new ProcessStartInfo("netsh.exe", argumentos) { CreateNoWindow = true, UseShellExecute = false, RedirectStandardOutput = true }))
            {
                p.StandardOutput.ReadToEnd();
                p.WaitForExit();
                return p.ExitCode;
            }
        }

        public static bool Permitido() => Netsh("advfirewall firewall show rule name=\"" + Regla + "\"") == 0;

        // Solo equipos de la misma red: nadie de afuera llega, aunque el router dejara pasar.
        public static void Agregar()
        {
            Netsh("advfirewall firewall delete rule name=\"" + Regla + "\"");
            Netsh("advfirewall firewall add rule name=\"" + Regla + "\" dir=in action=allow enable=yes profile=any remoteip=localsubnet program=\""
                + Application.ExecutablePath + "\"");
        }

        public static void PedirPermiso()
        {
            try
            {
                using (Process.Start(new ProcessStartInfo(Application.ExecutablePath, "--firewall") { Verb = "runas", UseShellExecute = true })) { }
            }
            catch (System.ComponentModel.Win32Exception) { }  // el usuario dijo que no
        }
    }

    static class Inicio
    {
        const string Clave = @"Software\Microsoft\Windows\CurrentVersion\Run";

        public static bool Activo
        {
            get
            {
                using (var k = Registry.CurrentUser.OpenSubKey(Clave)) return k?.GetValue(Marca.Nombre) != null;
            }
        }

        public static void Poner(bool activo)
        {
            if (Datos.EsPrueba) return;
            using (var k = Registry.CurrentUser.CreateSubKey(Clave))
            {
                if (activo) k.SetValue(Marca.Nombre, "\"" + Application.ExecutablePath + "\" --oculto");
                else k.DeleteValue(Marca.Nombre, false);
            }
        }
    }

    static class Sonido
    {
        static readonly SoundPlayer Reproductor = new SoundPlayer(Sintetizar());

        public static void Sonar()
        {
            if (Datos.Sonido) Reproductor.Play();
        }

        public static void Guardar(string ruta) => File.WriteAllBytes(ruta, Sintetizar().ToArray());

        // Suave como una marimba: un ta grave y corto, y un chán de dos notas que se apaga solo.
        static double Nota(double segundos, double inicio, double duracion, double tono, double caida)
        {
            var s = segundos - inicio;
            if (s < 0 || s >= duracion) return 0;
            var ataque = Math.Min(1, s / 0.012);
            var final = Math.Min(1, (duracion - s) / 0.06);
            var onda = Math.Sin(2 * Math.PI * tono * s) + 0.08 * Math.Sin(4 * Math.PI * tono * s);
            return onda / 1.08 * ataque * final * Math.Exp(-s * caida);
        }

        static MemoryStream Sintetizar()
        {
            const int frecuencia = 44100;
            var muestras = (int)(frecuencia * 0.45);
            var salida = new MemoryStream();
            var w = new BinaryWriter(salida);
            w.Write(new[] { (byte)'R', (byte)'I', (byte)'F', (byte)'F' });
            w.Write(36 + muestras * 2);
            w.Write(new[] { (byte)'W', (byte)'A', (byte)'V', (byte)'E', (byte)'f', (byte)'m', (byte)'t', (byte)' ' });
            w.Write(16);
            w.Write((short)1);
            w.Write((short)1);
            w.Write(frecuencia);
            w.Write(frecuencia * 2);
            w.Write((short)2);
            w.Write((short)16);
            w.Write(new[] { (byte)'d', (byte)'a', (byte)'t', (byte)'a' });
            w.Write(muestras * 2);
            for (var i = 0; i < muestras; i++)
            {
                var s = i / (double)frecuencia;
                var onda = Nota(s, 0, 0.09, 392.00, 14) + Nota(s, 0.10, 0.35, 523.25, 8) + 0.5 * Nota(s, 0.10, 0.35, 659.25, 10);
                w.Write((short)(onda * 5200));
            }
            salida.Position = 0;
            return salida;
        }
    }

    // El programa vive en el ícono junto al reloj.
    class Bandeja : ApplicationContext
    {
        const int EsperaTandaMs = 700;  // lo que llega junto se copia junto

        readonly NotifyIcon icono = new NotifyIcon();
        readonly Control hilo = new Control();
        readonly Aviso aviso = new Aviso();
        readonly Servidor servidor;
        readonly System.Windows.Forms.Timer espera = new System.Windows.Forms.Timer { Interval = EsperaTandaMs };
        readonly List<Recibido> tanda = new List<Recibido>();
        readonly ToolStripMenuItem menuCelus;
        VentanaVinculo ventana;

        public Bandeja(EventWaitHandle senal, bool oculto)
        {
            hilo.CreateControl();
            var _ = hilo.Handle;
            servidor = new Servidor(Datos.Identidad());
            servidor.Llegada += r => hilo.BeginInvoke((Action)(() => Lleno(r)));
            servidor.Vinculado += d => hilo.BeginInvoke((Action)(() => AlVincular(d)));
            servidor.SecretoAgotado += () => hilo.BeginInvoke((Action)(() => ventana?.Refrescar()));
            servidor.Arrancar();

            espera.Tick += (s, a) => Entregar();

            var menu = new ContextMenuStrip { Renderer = Tema.Oscuro ? new RendererOscuro() : null };
            menu.Items.Add(Textos.T("vincular"), null, (s, a) => AbrirVinculo());
            menuCelus = new ToolStripMenuItem(Textos.T("vinculados"));
            menu.Items.Add(menuCelus);
            menu.Items.Add(new ToolStripSeparator());
            menu.Items.Add(Textos.T("carpeta"), null, (s, a) => AbrirCarpeta());
            menu.Items.Add(new ToolStripSeparator());
            menu.Items.Add(Casilla("pegar", () => Datos.PegarSolo, v => { Datos.PegarSolo = v; Datos.GuardarAjustes(); }));
            menu.Items.Add(Casilla("sonido", () => Datos.Sonido, v => { Datos.Sonido = v; Datos.GuardarAjustes(); }));
            menu.Items.Add(Casilla("inicio", () => Inicio.Activo, Inicio.Poner));
            menu.Items.Add(new ToolStripSeparator());
            menu.Items.Add(Textos.T("salir"), null, (s, a) => Salir());
            menu.Items.Add(new ToolStripSeparator());
            menu.Items.Add(new ToolStripMenuItem(Textos.T("firma")) { Enabled = false });
            menu.Opening += (s, a) => ArmarCelus();

            icono.Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath);
            icono.Text = Marca.Visible;
            icono.ContextMenuStrip = menu;
            icono.Visible = true;
            icono.MouseUp += (s, a) => { if (a.Button == MouseButtons.Left) AbrirVinculoOCarpeta(); };

            // Otra instancia abierta (doble clic en el programa) pide mostrar la ventana.
            new Thread(() =>
            {
                while (senal.WaitOne()) hilo.BeginInvoke((Action)AbrirVinculo);
            }) { IsBackground = true }.Start();

            Prueba.Enganchar(this, servidor);
            if (!oculto && Datos.Dispositivos.Count == 0) AbrirVinculo();
        }

        static ToolStripMenuItem Casilla(string clave, Func<bool> leer, Action<bool> poner)
        {
            var item = new ToolStripMenuItem(Textos.T(clave)) { CheckOnClick = true, Checked = leer() };
            item.CheckedChanged += (s, a) => poner(item.Checked);
            return item;
        }

        void AbrirVinculoOCarpeta()
        {
            if (Datos.Dispositivos.Count == 0) AbrirVinculo();
            else AbrirCarpeta();
        }

        void AbrirCarpeta()
        {
            Directory.CreateDirectory(Datos.Recibidos);
            Process.Start("explorer.exe", "\"" + Datos.Recibidos + "\"");
        }

        void ArmarCelus()
        {
            menuCelus.DropDownItems.Clear();
            List<Dispositivo> lista;
            lock (Datos.Cerrojo) lista = Datos.Dispositivos.ToList();
            if (lista.Count == 0) menuCelus.DropDownItems.Add(new ToolStripMenuItem(Textos.T("ninguno")) { Enabled = false });
            foreach (var d in lista)
            {
                var celu = new ToolStripMenuItem(d.Nombre);
                celu.DropDownItems.Add(Textos.T("desvincular"), null, (s, a) =>
                {
                    lock (Datos.Cerrojo) Datos.Dispositivos.RemoveAll(x => x.Id == d.Id);
                    Datos.GuardarDispositivos();
                });
                menuCelus.DropDownItems.Add(celu);
            }
        }

        public void AbrirVinculo()
        {
            if (ventana != null && !ventana.IsDisposed)
            {
                ventana.Activate();
                return;
            }
            ventana = new VentanaVinculo(servidor);
            ventana.FormClosed += (s, a) => { servidor.CerrarVinculo(); ventana = null; };
            ventana.Show();
        }

        void AlVincular(Dispositivo d)
        {
            ventana?.Close();
            if (Datos.Dispositivos.Count == 1) Inicio.Poner(true);
            Sonido.Sonar();
            aviso.MostrarTexto(Textos.T("listo") + ": " + d.Nombre);
        }

        public void Lleno(Recibido r)
        {
            tanda.Add(r);
            espera.Stop();
            espera.Start();
        }

        void Entregar()
        {
            espera.Stop();
            var copia = tanda.ToList();
            tanda.Clear();
            var seCopio = Portapapeles.Copiar(copia);
            Sonido.Sonar();
            aviso.Mostrar(copia, seCopio);
            if (seCopio && Datos.PegarSolo) Portapapeles.ApretarPegar();
        }

        public void Salir()
        {
            icono.Visible = false;
            servidor.Apagar();
            ExitThread();
        }

        class RendererOscuro : ToolStripProfessionalRenderer
        {
            public RendererOscuro() : base(new Colores()) { }

            protected override void OnRenderItemText(ToolStripItemTextRenderEventArgs e)
            {
                e.TextColor = e.Item.Enabled ? Tema.Texto : Tema.Tenue;
                base.OnRenderItemText(e);
            }

            protected override void OnRenderArrow(ToolStripArrowRenderEventArgs e)
            {
                e.ArrowColor = Tema.Tenue;
                base.OnRenderArrow(e);
            }

            protected override void OnRenderItemCheck(ToolStripItemImageRenderEventArgs e)
            {
                var r = e.ImageRectangle;
                e.Graphics.SmoothingMode = System.Drawing.Drawing2D.SmoothingMode.AntiAlias;
                Tema.Icono(e.Graphics, "ok", r, Tema.Acento, 2.6f);
            }

            class Colores : ProfessionalColorTable
            {
                public override Color ToolStripDropDownBackground => Tema.Fondo;
                public override Color MenuBorder => Tema.Fondo2;
                public override Color MenuItemBorder => Tema.Fondo2;
                public override Color MenuItemSelected => Tema.Fondo2;
                public override Color MenuItemSelectedGradientBegin => Tema.Fondo2;
                public override Color MenuItemSelectedGradientEnd => Tema.Fondo2;
                public override Color ImageMarginGradientBegin => Tema.Fondo;
                public override Color ImageMarginGradientMiddle => Tema.Fondo;
                public override Color ImageMarginGradientEnd => Tema.Fondo;
                public override Color SeparatorDark => Tema.Fondo2;
                public override Color SeparatorLight => Tema.Fondo2;
                public override Color CheckBackground => Tema.Fondo;
                public override Color CheckSelectedBackground => Tema.Fondo2;
                public override Color CheckPressedBackground => Tema.Fondo2;
            }
        }
    }

    class VentanaVinculo : Form
    {
        const int MinutosValidez = 5;

        readonly Servidor servidor;
        readonly PictureBox qr = new PictureBox { SizeMode = PictureBoxSizeMode.Zoom };
        readonly Label frase = new Label { TextAlign = ContentAlignment.MiddleCenter };
        readonly LinkLabel verCodigo = new LinkLabel { TextAlign = ContentAlignment.MiddleCenter, LinkBehavior = LinkBehavior.HoverUnderline };
        readonly TextBox codigo = new TextBox { ReadOnly = true, BorderStyle = BorderStyle.None, TextAlign = HorizontalAlignment.Center, Visible = false };
        readonly Button red = new Button { FlatStyle = FlatStyle.System };
        readonly System.Windows.Forms.Timer renovar = new System.Windows.Forms.Timer { Interval = MinutosValidez * 60 * 1000 };

        public VentanaVinculo(Servidor servidor)
        {
            this.servidor = servidor;
            Text = Marca.Visible;
            Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath);
            FormBorderStyle = FormBorderStyle.FixedSingle;
            MaximizeBox = false;
            MinimizeBox = false;
            StartPosition = FormStartPosition.CenterScreen;
            BackColor = Tema.Suelo;
            float e;
            using (var g = CreateGraphics()) e = g.DpiX / 96f;
            int M(int v) => (int)(v * e);
            ClientSize = new Size(M(320), M(400));

            qr.SetBounds(M(40), M(24), M(240), M(240));
            qr.BackColor = Color.White;
            frase.SetBounds(0, M(276), M(320), M(30));
            frase.Text = Textos.T("escanea");
            frase.Font = new Font("Segoe UI Semibold", 11.5f);
            frase.ForeColor = Tema.Texto;
            verCodigo.SetBounds(0, M(310), M(320), M(22));
            verCodigo.Text = Textos.T("codigo");
            verCodigo.Font = new Font("Segoe UI", 9f);
            verCodigo.LinkColor = Tema.Tenue;
            verCodigo.ActiveLinkColor = Tema.Acento;
            verCodigo.LinkClicked += (s, a) =>
            {
                verCodigo.Visible = false;
                codigo.Visible = true;
            };
            codigo.SetBounds(M(10), M(312), M(300), M(22));
            codigo.BackColor = Tema.Suelo;
            codigo.ForeColor = Tema.Texto;
            codigo.Font = new Font("Consolas", 8.5f);
            red.SetBounds(M(60), M(346), M(200), M(36));
            red.Text = Textos.T("red");
            red.Font = new Font("Segoe UI", 9f);
            red.Visible = false;
            SendMessage(red.Handle, 0x160C, IntPtr.Zero, (IntPtr)1);  // BCM_SETSHIELD
            red.Click += (s, a) =>
            {
                Firewall.PedirPermiso();
                red.Visible = !Firewall.Permitido();
            };
            Controls.AddRange(new Control[] { qr, frase, verCodigo, codigo, red });

            renovar.Tick += (s, a) => Refrescar();
            renovar.Start();
            Refrescar();
            var chequeo = new Thread(() =>
            {
                var permitido = Firewall.Permitido();
                try { BeginInvoke((Action)(() => red.Visible = !permitido)); }
                catch (InvalidOperationException) { }  // ya la cerraron
            }) { IsBackground = true };
            HandleCreated += (s, a) => chequeo.Start();
            FormClosed += (s, a) => renovar.Stop();
        }

        // Cada QR dura 5 minutos: si alguien lo fotografía después, ya no sirve.
        public void Refrescar()
        {
            var c = servidor.AbrirVinculo();
            var enlace = Marca.Esquema + "://v?c=" + c + "&n=" + Uri.EscapeDataString(Environment.MachineName);
            codigo.Text = c;
            qr.Image?.Dispose();
            qr.Image = Qr.Crear(enlace).Imagen(8, 3);
            Prueba.AnotarCodigo(enlace, qr.Image);
        }

        [DllImport("user32.dll")]
        static extern IntPtr SendMessage(IntPtr ventana, int mensaje, IntPtr w, IntPtr l);
    }

    // Solo con TACHAN_DATOS puesto: deja el enlace en un archivo para las pruebas automáticas.
    static class Prueba
    {
        public static void Enganchar(Bandeja bandeja, Servidor servidor)
        {
            if (!Datos.EsPrueba) return;
            File.WriteAllText(Path.Combine(Datos.Carpeta, "puerto.txt"), servidor.Puerto.ToString());
            Sonido.Guardar(Path.Combine(Datos.Carpeta, "sonido.wav"));
        }

        public static void AnotarCodigo(string enlace, Image qr)
        {
            if (!Datos.EsPrueba) return;
            qr.Save(Path.Combine(Datos.Carpeta, "qr.png"));
            File.WriteAllText(Path.Combine(Datos.Carpeta, "enlace.txt"), enlace);
        }
    }
}
