using System;
using System.Collections.Generic;
using System.Collections.Specialized;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.IO;
using System.Linq;
using System.Runtime;
using System.Runtime.InteropServices;
using System.Windows.Forms;
using Kvothesson;
using Microsoft.Win32;

namespace Tachan
{
    static class Tema
    {
        public static bool Oscuro
        {
            get
            {
                using (var k = Registry.CurrentUser.OpenSubKey(@"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"))
                    return (k?.GetValue("AppsUseLightTheme") as int?) == 0;
            }
        }

        // Los valores salen de marca/project/tokens.json del taller: ver MarcaColores.cs.
        public static Color Acento => Oscuro ? MarcaColores.Noche.Accent : MarcaColores.Dia.Accent;
        public static Color Ok => Oscuro ? MarcaColores.Noche.Ok : MarcaColores.Dia.Ok;
        public static Color Suelo => Oscuro ? MarcaColores.Noche.Ground : MarcaColores.Dia.Ground;
        public static Color Fondo => Oscuro ? MarcaColores.Noche.Surface : MarcaColores.Dia.Surface;
        public static Color Fondo2 => Oscuro ? MarcaColores.Noche.SurfaceRaised : MarcaColores.Dia.SurfaceRaised;
        public static Color Texto => Oscuro ? MarcaColores.Noche.Ink : MarcaColores.Dia.Ink;
        public static Color Tenue => Oscuro ? MarcaColores.Noche.Muted : MarcaColores.Dia.Muted;

        public static GraphicsPath Redondeado(RectangleF r, float radio)
        {
            var d = radio * 2;
            var c = new GraphicsPath();
            c.AddArc(r.X, r.Y, d, d, 180, 90);
            c.AddArc(r.Right - d, r.Y, d, d, 270, 90);
            c.AddArc(r.Right - d, r.Bottom - d, d, d, 0, 90);
            c.AddArc(r.X, r.Bottom - d, d, d, 90, 90);
            c.CloseFigure();
            return c;
        }

        // Íconos en una grilla de 24: los mismos del diseño.
        public static void Icono(Graphics g, string cual, RectangleF caja, Color color, float grosor = 2f)
        {
            var estado = g.Save();
            g.TranslateTransform(caja.X, caja.Y);
            g.ScaleTransform(caja.Width / 24f, caja.Height / 24f);
            using (var p = new Pen(color, grosor) { StartCap = LineCap.Round, EndCap = LineCap.Round, LineJoin = LineJoin.Round })
            {
                switch (cual)
                {
                    case "copiar":
                        using (var c = Redondeado(new RectangleF(9, 9, 11, 11), 2.5f)) g.DrawPath(p, c);
                        g.DrawLines(p, new[] { new PointF(15, 5.5f), new PointF(14, 4), new PointF(5.5f, 4), new PointF(4, 5.5f), new PointF(4, 14), new PointF(5.5f, 15) });
                        break;
                    case "carpeta":
                        g.DrawPolygon(p, new[] { new PointF(3.5f, 6), new PointF(9, 6), new PointF(11, 8.5f), new PointF(20.5f, 8.5f), new PointF(20.5f, 19), new PointF(3.5f, 19) });
                        break;
                    case "abrir":
                        g.DrawLines(p, new[] { new PointF(9, 5), new PointF(5, 5), new PointF(5, 19), new PointF(19, 19), new PointF(19, 15) });
                        g.DrawLines(p, new[] { new PointF(13, 5), new PointF(19, 5), new PointF(19, 11) });
                        g.DrawLine(p, 19, 5, 11, 13);
                        break;
                    case "ok":
                        g.DrawLines(p, new[] { new PointF(5, 12.5f), new PointF(9.5f, 17), new PointF(19, 7.5f) });
                        break;
                    case "reloj":
                        g.DrawEllipse(p, 4, 4, 16, 16);
                        g.DrawLines(p, new[] { new PointF(12, 7.5f), new PointF(12, 12), new PointF(15, 14) });
                        break;
                }
            }
            g.Restore(estado);
        }
    }

    // El aviso que aparece al llegar algo. Nunca toma el foco: seguís escribiendo donde estabas.
    class Aviso : Form
    {
        class Accion
        {
            public string Icono;
            public string Ayuda;
            public Action Hacer;
            public RectangleF Caja;
        }

        const int MilisegundosVisible = 6000;
        const int LadoMiniaturaShell = 256;
        const int AltoMaximoImagen = 320;

        readonly Timer reloj = new Timer { Interval = 60 };
        readonly ToolTip ayuda = new ToolTip();
        readonly List<Accion> acciones = new List<Accion>();
        List<Recibido> tanda = new List<Recibido>();
        Bitmap imagen;
        bool imagenDeArchivo;
        DateTime ocultarEn;
        DateTime mostradoEn;
        DateTime confirmadoEn;
        bool copiado;
        Accion bajoElMouse;
        Point? apretadoEn;
        bool arrastrando;
        bool visto;
        int yFinal;
        RectangleF zonaContenido;
        float e = 1f;

        public Aviso()
        {
            FormBorderStyle = FormBorderStyle.None;
            ShowInTaskbar = false;
            StartPosition = FormStartPosition.Manual;
            TopMost = true;
            DoubleBuffered = true;
            AllowDrop = false;
            reloj.Tick += Latido;
            CreateHandle();
            using (var g = CreateGraphics()) e = g.DpiX / 96f;
        }

        protected override bool ShowWithoutActivation => true;

        protected override CreateParams CreateParams
        {
            get
            {
                var p = base.CreateParams;
                p.ExStyle |= 0x08000000 | 0x00000080 | 0x00000008;  // WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TOPMOST
                p.ClassStyle |= 0x00020000;  // sombra
                return p;
            }
        }

        // Un clic en el aviso tampoco te saca de donde estás.
        protected override void WndProc(ref Message m)
        {
            const int WM_MOUSEACTIVATE = 0x21, MA_NOACTIVATE = 3;
            if (m.Msg == WM_MOUSEACTIVATE)
            {
                m.Result = (IntPtr)MA_NOACTIVATE;
                return;
            }
            base.WndProc(ref m);
        }

        public int AnchoImagen => (int)(300 * e);
        public int AltoImagen => (int)(AltoMaximoImagen * e);

        bool Demorada => tanda.LastOrDefault()?.Demorado == true;

        // Un texto no queda en ninguna carpeta: si llegó con la cola, espera a que pases el mouse.
        public Recibido TextoDemoradoSinVer => Visible && Demorada && tanda.Last().Texto != null && !visto ? tanda.Last() : null;

        // Arrastrás y copiás lo que ves. La cola junta cosas que mandaste por separado: esas se agarran de a una.
        IList<Recibido> Elegidos => Demorada ? tanda.Skip(tanda.Count - 1).ToList() : tanda;

        // El aviso se queda con la miniatura y la suelta al cerrarse.
        public void Mostrar(List<Recibido> nueva, bool seCopio, Bitmap miniatura = null)
        {
            // Una ventana nace en el escritorio virtual donde estás: si se reusara, aparecería en el de antes.
            if (!Visible) RecreateHandle();
            tanda = nueva;
            copiado = seCopio;
            visto = false;
            confirmadoEn = DateTime.MinValue;
            imagen?.Dispose();
            imagen = null;
            imagenDeArchivo = false;

            var ultima = tanda.LastOrDefault(r => r.Ruta != null);
            if (tanda.Last().Texto == null && ultima != null)
            {
                imagen = miniatura;
                imagenDeArchivo = imagen != null;
                if (imagen == null) imagen = Imagenes.MiniaturaDeShell(ultima.Ruta, LadoMiniaturaShell);
            }
            else miniatura?.Dispose();
            ArmarAcciones();
            Acomodar();
            ocultarEn = DateTime.Now.AddMilliseconds(MilisegundosVisible);
            mostradoEn = DateTime.Now;
            reloj.Start();
            if (!Visible)
            {
                Location = new Point(Left, yFinal + (int)(16 * e));
                Opacity = 0;
                Show();
            }
            // Mostrarla sin activarla no alcanza para que quede sobre las demás ventanas: hay que pedirlo aparte.
            SetWindowPos(Handle, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE);
            Invalidate();
        }

        static readonly IntPtr HWND_TOPMOST = new IntPtr(-1);
        const uint SWP_NOSIZE = 0x0001, SWP_NOMOVE = 0x0002, SWP_NOACTIVATE = 0x0010;

        [DllImport("user32.dll")]
        static extern bool SetWindowPos(IntPtr ventana, IntPtr despuesDe, int x, int y, int ancho, int alto, uint marcas);

        // Para confirmar algo sin contenido, como un celu recién vinculado.
        public void MostrarTexto(string texto)
        {
            Mostrar(new List<Recibido> { new Recibido { Texto = texto } }, true);
            acciones.Clear();
            Invalidate();
        }

        protected override void OnVisibleChanged(EventArgs a)
        {
            base.OnVisibleChanged(a);
            if (Visible) return;
            imagen?.Dispose();
            imagen = null;
            imagenDeArchivo = false;
            tanda = new List<Recibido>();
            acciones.Clear();
            DevolverMemoria();
        }

        // Queda prendido todo el día: lo que ocuparon las fotos se devuelve ahora, no cuando le toque al sistema.
        public static void DevolverMemoria()
        {
            GCSettings.LargeObjectHeapCompactionMode = GCLargeObjectHeapCompactionMode.CompactOnce;
            GC.Collect();
        }

        Uri EnlaceDeTexto()
        {
            var t = tanda.Last().Texto?.Trim();
            return t != null && Uri.TryCreate(t, UriKind.Absolute, out var u) && (u.Scheme == "http" || u.Scheme == "https") && !t.Contains(' ') ? u : null;
        }

        void ArmarAcciones()
        {
            acciones.Clear();
            var enlace = EnlaceDeTexto();
            if (enlace != null)
                acciones.Add(new Accion { Icono = "abrir", Ayuda = Textos.T("abrir"), Hacer = () => Process.Start(enlace.AbsoluteUri) });
            acciones.Add(new Accion { Icono = "copiar", Ayuda = Textos.T("copiar"), Hacer = CopiarDeNuevo });
            var ruta = tanda.LastOrDefault(r => r.Ruta != null)?.Ruta;
            if (ruta != null && tanda.Last().Texto == null)
                acciones.Add(new Accion { Icono = "carpeta", Ayuda = Textos.T("carpeta"), Hacer = () => Process.Start("explorer.exe", "/select,\"" + ruta + "\"") });
        }

        void CopiarDeNuevo()
        {
            copiado = Portapapeles.Copiar(Elegidos);
            confirmadoEn = DateTime.Now;
            Invalidate();
        }

        float AltoContenido()
        {
            var ancho = 300 * e;
            if (imagenDeArchivo) return Math.Min(AltoMaximoImagen * e, Math.Max(90 * e, ancho * imagen.Height / imagen.Width));
            if (tanda.Last().Texto != null)
            {
                using (var f = new Font("Segoe UI", 10.5f))
                {
                    var alto = TextRenderer.MeasureText(tanda.Last().Texto, f, new Size((int)(ancho - 28 * e), int.MaxValue), TextFormatFlags.WordBreak).Height;
                    return Math.Min(130 * e, alto + 28 * e);
                }
            }
            return 74 * e;
        }

        void Acomodar()
        {
            var ancho = (int)(300 * e);
            var alto = (int)(AltoContenido() + 44 * e);
            var pantalla = Screen.FromPoint(Cursor.Position).WorkingArea;
            yFinal = pantalla.Bottom - alto - (int)(14 * e);
            SetBounds(pantalla.Right - ancho - (int)(14 * e), Visible ? yFinal : Top, ancho, alto);
            zonaContenido = new RectangleF(0, 0, ancho, alto - 44 * e);

            var x = ancho - 8 * e;
            foreach (var a in acciones.AsEnumerable().Reverse())
            {
                x -= 32 * e;
                a.Caja = new RectangleF(x, alto - 38 * e, 32 * e, 32 * e);
                x -= 2 * e;
            }
            using (var c = Tema.Redondeado(new RectangleF(0, 0, ancho, alto), 14 * e)) Region = new Region(c);
        }

        void Latido(object emisor, EventArgs args)
        {
            var transcurrido = (DateTime.Now - mostradoEn).TotalMilliseconds;
            var t = Math.Min(1.0, transcurrido / 180.0);
            var suave = 1 - (1 - t) * (1 - t);
            Opacity = suave;
            var y = yFinal + (int)((1 - suave) * 16 * e);
            if (Top != y) Top = y;

            var adentro = Bounds.Contains(Cursor.Position);
            if (adentro) visto = true;
            if (adentro || arrastrando || TextoDemoradoSinVer != null) ocultarEn = DateTime.Now.AddMilliseconds(2000);
            if (!adentro && bajoElMouse != null)
            {
                bajoElMouse = null;
                Invalidate();
            }
            if (DateTime.Now > ocultarEn)
            {
                reloj.Stop();
                Hide();
            }
            if (confirmadoEn != DateTime.MinValue && (DateTime.Now - confirmadoEn).TotalMilliseconds > 800)
            {
                confirmadoEn = DateTime.MinValue;
                Invalidate();
            }
        }

        protected override void OnPaint(PaintEventArgs a)
        {
            var g = a.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.InterpolationMode = InterpolationMode.HighQualityBicubic;
            g.PixelOffsetMode = PixelOffsetMode.HighQuality;
            g.TextRenderingHint = System.Drawing.Text.TextRenderingHint.ClearTypeGridFit;
            g.Clear(Tema.Fondo);

            var ultima = tanda.LastOrDefault();
            if (ultima == null) return;
            if (imagenDeArchivo) PintarEntera(g, imagen, zonaContenido);
            else if (ultima.Texto != null) PintarTexto(g, ultima.Texto);
            else PintarArchivo(g, ultima.Ruta);

            if (tanda.Count > 1) PintarCantidad(g, tanda.Count);

            var y = Height - 22 * e;
            var okCaja = new RectangleF(12 * e, y - 10 * e, 20 * e, 20 * e);
            if (copiado) Tema.Icono(g, "ok", okCaja, Tema.Ok, 2.6f);
            else if (Demorada)
            {
                Tema.Icono(g, "reloj", okCaja, Tema.Tenue);
                using (var f = new Font("Segoe UI", 8.5f))
                using (var b = new SolidBrush(Tema.Tenue))
                using (var formato = new StringFormat { LineAlignment = StringAlignment.Center, FormatFlags = StringFormatFlags.NoWrap })
                    g.DrawString(Textos.T("demorado"), f, b, new RectangleF(okCaja.Right + 4 * e, okCaja.Y, 170 * e, okCaja.Height), formato);
            }

            foreach (var accion in acciones)
            {
                if (accion == bajoElMouse)
                    using (var c = Tema.Redondeado(accion.Caja, 8 * e))
                    using (var b = new SolidBrush(Tema.Fondo2))
                        g.FillPath(b, c);
                var margen = 7 * e;
                var caja = RectangleF.Inflate(accion.Caja, -margen, -margen);
                var color = accion.Icono == "abrir" ? Tema.Acento : Tema.Tenue;
                if (accion.Icono == "copiar" && confirmadoEn != DateTime.MinValue) Tema.Icono(g, "ok", caja, Tema.Ok, 2.6f);
                else Tema.Icono(g, accion.Icono, caja, color);
            }
        }

        // Se ve siempre entera: lo que llegó tiene que reconocerse de un vistazo, aunque sea largo.
        static void PintarEntera(Graphics g, Image i, RectangleF zona)
        {
            using (var b = new SolidBrush(Tema.Fondo2)) g.FillRectangle(b, zona);
            var escala = Math.Min(zona.Width / i.Width, zona.Height / i.Height);
            var w = i.Width * escala;
            var h = i.Height * escala;
            g.DrawImage(i, zona.X + (zona.Width - w) / 2, zona.Y + (zona.Height - h) / 2, w, h);
        }

        void PintarTexto(Graphics g, string texto)
        {
            // GDI, no GDI+: es el que encuentra los emojis en la fuente de Windows.
            using (var f = new Font("Segoe UI", 10.5f))
                TextRenderer.DrawText(g, texto, f, Rectangle.Round(new RectangleF(14 * e, 14 * e, Width - 28 * e, zonaContenido.Height - 20 * e)), Tema.Texto, Tema.Fondo,
                    TextFormatFlags.WordBreak | TextFormatFlags.EndEllipsis | TextFormatFlags.NoPrefix);
        }

        void PintarArchivo(Graphics g, string ruta)
        {
            var mini = new RectangleF(14 * e, 14 * e, 46 * e, 46 * e);
            using (var c = Tema.Redondeado(mini, 9 * e))
            using (var b = new SolidBrush(Tema.Fondo2))
                g.FillPath(b, c);
            if (imagen != null)
            {
                var interior = RectangleF.Inflate(mini, -5 * e, -5 * e);
                g.DrawImage(imagen, interior);
            }
            var x = mini.Right + 12 * e;
            var ancho = Width - x - 14 * e;
            using (var f = new Font("Segoe UI", 9.5f))
            using (var fc = new Font("Segoe UI", 8.5f))
            using (var bt = new SolidBrush(Tema.Texto))
            using (var bc = new SolidBrush(Tema.Tenue))
            using (var formato = new StringFormat { Trimming = StringTrimming.EllipsisPath, FormatFlags = StringFormatFlags.NoWrap })
            {
                g.DrawString(Path.GetFileName(ruta), f, bt, new RectangleF(x, mini.Y + 3 * e, ancho, 22 * e), formato);
                g.DrawString(Tamano(new FileInfo(ruta).Length), fc, bc, new RectangleF(x, mini.Y + 25 * e, ancho, 20 * e), formato);
            }
        }

        static string Tamano(long bytes)
        {
            if (bytes >= 1L << 30) return (bytes / (double)(1L << 30)).ToString("0.0") + " GB";
            if (bytes >= 1L << 20) return (bytes / (double)(1L << 20)).ToString("0.0") + " MB";
            return Math.Max(1, bytes / 1024) + " KB";
        }

        void PintarCantidad(Graphics g, int cantidad)
        {
            using (var f = new Font("Segoe UI", 8.5f, FontStyle.Bold))
            {
                var texto = cantidad.ToString();
                var m = g.MeasureString(texto, f);
                var caja = new RectangleF(Width - m.Width - 20 * e, 8 * e, m.Width + 12 * e, m.Height + 2 * e);
                using (var c = Tema.Redondeado(caja, caja.Height / 2))
                using (var b = new SolidBrush(Color.FromArgb(170, 0, 0, 0)))
                    g.FillPath(b, c);
                g.DrawString(texto, f, Brushes.White, caja.X + 6 * e, caja.Y + 1 * e);
            }
        }

        Accion AccionEn(Point p) => acciones.FirstOrDefault(a => a.Caja.Contains(p));

        protected override void OnMouseMove(MouseEventArgs a)
        {
            var nueva = AccionEn(a.Location);
            if (nueva != bajoElMouse)
            {
                bajoElMouse = nueva;
                ayuda.SetToolTip(this, nueva?.Ayuda);
                Invalidate();
            }
            Cursor = nueva != null || zonaContenido.Contains(a.Location) ? Cursors.Hand : Cursors.Default;
            if (apretadoEn != null && a.Button == MouseButtons.Left
                && Math.Max(Math.Abs(a.X - apretadoEn.Value.X), Math.Abs(a.Y - apretadoEn.Value.Y)) > 5 * e)
            {
                apretadoEn = null;
                Arrastrar();
            }
        }

        protected override void OnMouseDown(MouseEventArgs a)
        {
            if (a.Button == MouseButtons.Right)
            {
                reloj.Stop();
                Hide();
                return;
            }
            if (a.Button == MouseButtons.Left && AccionEn(a.Location) == null) apretadoEn = a.Location;
        }

        protected override void OnMouseUp(MouseEventArgs a)
        {
            if (a.Button != MouseButtons.Left) return;
            var accion = AccionEn(a.Location);
            if (accion != null) accion.Hacer();
            else if (apretadoEn != null && zonaContenido.Contains(a.Location)) CopiarDeNuevo();
            apretadoEn = null;
        }

        protected override void OnMouseDoubleClick(MouseEventArgs a)
        {
            var ruta = tanda.LastOrDefault()?.Ruta;
            if (ruta != null && Imagenes.SeguroDeAbrir(ruta) && zonaContenido.Contains(a.Location)) Process.Start(new ProcessStartInfo(ruta) { UseShellExecute = true });
        }

        void Arrastrar()
        {
            var datos = new DataObject();
            var elegidos = Elegidos;
            var rutas = elegidos.Where(r => r.Ruta != null).Select(r => r.Ruta).ToArray();
            if (rutas.Length > 0)
            {
                var lista = new StringCollection();
                lista.AddRange(rutas);
                datos.SetFileDropList(lista);
            }
            var texto = elegidos.LastOrDefault(r => r.Texto != null)?.Texto;
            if (!string.IsNullOrEmpty(texto)) datos.SetText(texto);
            arrastrando = true;
            try { DoDragDrop(datos, DragDropEffects.Copy); }
            finally { arrastrando = false; }
        }

        protected override void OnFormClosing(FormClosingEventArgs a)
        {
            if (a.CloseReason == CloseReason.UserClosing)
            {
                a.Cancel = true;
                Hide();
            }
        }
    }
}
