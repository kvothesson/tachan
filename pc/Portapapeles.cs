using System;
using System.Collections.Generic;
using System.Collections.Specialized;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Windows.Forms;
using System.Windows.Media.Imaging;

namespace Tachan
{
    static class Imagenes
    {
        static readonly string[] Abribles = { ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".heic", ".heif", ".tif", ".tiff",
                                              ".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi", ".3gp", ".mp3", ".m4a", ".ogg", ".wav", ".opus" };

        // Solo medios se abren con doble clic: un archivo cualquiera puede ser un programa.
        public static bool SeguroDeAbrir(string ruta) => Abribles.Contains(Path.GetExtension(ruta).ToLowerInvariant());

        // La foto derecha, o null si no es una imagen que Windows entienda.
        public static Bitmap Abrir(string ruta)
        {
            try
            {
                using (var archivo = new FileStream(ruta, FileMode.Open, FileAccess.Read, FileShare.Read))
                using (var original = Image.FromStream(archivo))
                {
                    // Sin transparencia alcanza con 3 bytes por píxel: en una foto de 12 MP son 12 MB menos.
                    var formato = Image.IsAlphaPixelFormat(original.PixelFormat) ? PixelFormat.Format32bppArgb : PixelFormat.Format24bppRgb;
                    var derecha = new Bitmap(original.Width, original.Height, formato);
                    using (var g = Graphics.FromImage(derecha)) g.DrawImage(original, 0, 0, original.Width, original.Height);
                    if (Array.IndexOf(original.PropertyIdList, 0x0112) >= 0)
                    {
                        switch (BitConverter.ToUInt16(original.GetPropertyItem(0x0112).Value, 0))
                        {
                            case 2: derecha.RotateFlip(RotateFlipType.RotateNoneFlipX); break;
                            case 3: derecha.RotateFlip(RotateFlipType.Rotate180FlipNone); break;
                            case 4: derecha.RotateFlip(RotateFlipType.Rotate180FlipX); break;
                            case 5: derecha.RotateFlip(RotateFlipType.Rotate90FlipX); break;
                            case 6: derecha.RotateFlip(RotateFlipType.Rotate90FlipNone); break;
                            case 7: derecha.RotateFlip(RotateFlipType.Rotate270FlipX); break;
                            case 8: derecha.RotateFlip(RotateFlipType.Rotate270FlipNone); break;
                        }
                    }
                    return derecha;
                }
            }
            catch (Exception) { }
            return AbrirConWic(ruta);
        }

        // Para el aviso alcanza con algo chico: la foto entera se queda solo el rato de copiarla.
        public static Bitmap Miniatura(Bitmap imagen, int anchoMaximo)
        {
            if (imagen.Width <= anchoMaximo) return new Bitmap(imagen);
            var alto = Math.Max(1, imagen.Height * anchoMaximo / imagen.Width);
            var chica = new Bitmap(anchoMaximo, alto, PixelFormat.Format24bppRgb);
            using (var g = Graphics.FromImage(chica))
            {
                g.InterpolationMode = System.Drawing.Drawing2D.InterpolationMode.HighQualityBicubic;
                g.DrawImage(imagen, 0, 0, anchoMaximo, alto);
            }
            return chica;
        }

        // WebP y HEIC: GDI+ no los lee, pero el códec de Windows sí cuando está instalado.
        static Bitmap AbrirConWic(string ruta)
        {
            try
            {
                using (var archivo = new FileStream(ruta, FileMode.Open, FileAccess.Read, FileShare.Read))
                {
                    var marco = BitmapDecoder.Create(archivo, BitmapCreateOptions.None, BitmapCacheOption.OnLoad).Frames[0];
                    var png = new PngBitmapEncoder();
                    png.Frames.Add(marco);
                    using (var memoria = new MemoryStream())
                    {
                        png.Save(memoria);
                        memoria.Position = 0;
                        using (var leida = Image.FromStream(memoria)) return new Bitmap(leida);
                    }
                }
            }
            catch (Exception) { return null; }
        }

        // La miniatura de Windows: sirve para videos, PDF, etc. Si no, da el ícono del tipo.
        public static Bitmap MiniaturaDeShell(string ruta, int lado)
        {
            try
            {
                var iid = new Guid("bcc18b79-ba16-442f-80c4-8a59c30c463b");
                SHCreateItemFromParsingName(ruta, IntPtr.Zero, ref iid, out var fabrica);
                try
                {
                    fabrica.GetImage(new Tamano { Ancho = lado, Alto = lado }, 0, out var h);
                    try
                    {
                        using (var crudo = Image.FromHbitmap(h))
                        {
                            var d = new BitmapData();
                            var copia = new Bitmap(crudo.Width, crudo.Height, PixelFormat.Format32bppArgb);
                            var rect = new Rectangle(0, 0, crudo.Width, crudo.Height);
                            var fuente = crudo.LockBits(rect, ImageLockMode.ReadOnly, crudo.PixelFormat);
                            try
                            {
                                d = copia.LockBits(rect, ImageLockMode.WriteOnly, PixelFormat.Format32bppArgb);
                                for (var y = 0; y < crudo.Height; y++)
                                {
                                    var fila = new byte[crudo.Width * 4];
                                    Marshal.Copy(fuente.Scan0 + y * fuente.Stride, fila, 0, fila.Length);
                                    Marshal.Copy(fila, 0, d.Scan0 + y * d.Stride, fila.Length);
                                }
                                copia.UnlockBits(d);
                            }
                            finally { crudo.UnlockBits(fuente); }
                            return copia;
                        }
                    }
                    finally { DeleteObject(h); }
                }
                finally { Marshal.ReleaseComObject(fabrica); }
            }
            catch (Exception) { return null; }
        }

        [StructLayout(LayoutKind.Sequential)]
        struct Tamano
        {
            public int Ancho;
            public int Alto;
        }

        [ComImport, Guid("bcc18b79-ba16-442f-80c4-8a59c30c463b"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
        interface IShellItemImageFactory
        {
            void GetImage(Tamano tamano, int opciones, out IntPtr bitmap);
        }

        [DllImport("shell32.dll", CharSet = CharSet.Unicode, PreserveSig = false)]
        static extern void SHCreateItemFromParsingName(string ruta, IntPtr contexto, ref Guid iid, out IShellItemImageFactory item);

        [DllImport("gdi32.dll")]
        static extern bool DeleteObject(IntPtr objeto);
    }

    static class Portapapeles
    {
        // Las rutas como archivos y la última imagen como dibujo: sirve en cualquier programa.
        public static bool Copiar(IList<Recibido> tanda)
        {
            using (var imagen = UltimaImagen(tanda, out _)) return Copiar(tanda, imagen);
        }

        // Decodificar tarda: se hace afuera del hilo de la ventana. Copiar sí tiene que ser en ese hilo.
        public static Bitmap UltimaImagen(IList<Recibido> tanda, out string origen)
        {
            foreach (var ruta in tanda.Where(r => r.Ruta != null).Select(r => r.Ruta).Reverse())
            {
                var imagen = Imagenes.Abrir(ruta);
                if (imagen == null) continue;
                origen = ruta;
                return imagen;
            }
            origen = null;
            return null;
        }

        public static bool Copiar(IList<Recibido> tanda, Bitmap imagen)
        {
            try
            {
                var datos = new DataObject();
                var rutas = tanda.Where(r => r.Ruta != null).Select(r => r.Ruta).ToArray();
                if (rutas.Length > 0)
                {
                    var lista = new StringCollection();
                    lista.AddRange(rutas);
                    datos.SetFileDropList(lista);
                    if (imagen != null) datos.SetImage(imagen);
                }
                var texto = tanda.LastOrDefault(r => r.Texto != null)?.Texto;
                if (texto != null && texto.Length > 0) datos.SetText(texto);
                Clipboard.SetDataObject(datos, true, 10, 100);
                return true;
            }
            catch (ExternalException) { return false; }
        }

        public static void ApretarPegar()
        {
            const byte control = 0x11, v = 0x56;
            const uint soltar = 2;
            keybd_event(control, 0, 0, UIntPtr.Zero);
            keybd_event(v, 0, 0, UIntPtr.Zero);
            keybd_event(v, 0, soltar, UIntPtr.Zero);
            keybd_event(control, 0, soltar, UIntPtr.Zero);
        }

        [DllImport("user32.dll")]
        static extern void keybd_event(byte tecla, byte scan, uint marcas, UIntPtr extra);
    }
}
