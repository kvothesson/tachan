using System.Collections.Generic;
using System.Globalization;

namespace Tachan
{
    // El nombre vive acá y en android/res/values/textos.xml. Nombre va en rutas y reglas, Visible en pantalla.
    static class Marca
    {
        public const string Nombre = "Tachan";
        public const string Visible = "Tachán";
        // El código va después del #: esa parte del link el navegador no se la manda a ningún servidor.
        public const string Enlace = "https://kvothesson.com/tachan/#";
        public const int PuertoTcp = 47810;
        public const int PuertoUdp = 47811;
    }

    static class Textos
    {
        static readonly Dictionary<string, Dictionary<string, string>> Todos = new Dictionary<string, Dictionary<string, string>>
        {
            ["en"] = new Dictionary<string, string>
            {
                ["vincular"] = "Link a phone", ["vinculados"] = "Linked phones", ["desvincular"] = "Unlink",
                ["carpeta"] = "Open folder", ["pegar"] = "Paste automatically", ["sonido"] = "Sound",
                ["inicio"] = "Start with Windows", ["salir"] = "Quit", ["escanea"] = "Scan with your phone",
                ["red"] = "Allow on network", ["codigo"] = "Show code", ["copiar"] = "Copy",
                ["abrir"] = "Open", ["ninguno"] = "None", ["listo"] = "Linked", ["firma"] = "made by Kvothesson", ["buscar"] = "Check for updates", ["ultima"] = "You have the latest version", ["actualizando"] = "Updating…", ["sinred"] = "Couldn't check. Try again later.", ["demorado"] = "Sent earlier",
            },
            ["es"] = new Dictionary<string, string>
            {
                ["vincular"] = "Vincular un celu", ["vinculados"] = "Celus vinculados", ["desvincular"] = "Desvincular",
                ["carpeta"] = "Abrir carpeta", ["pegar"] = "Pegar solo", ["sonido"] = "Sonido",
                ["inicio"] = "Iniciar con Windows", ["salir"] = "Salir", ["escanea"] = "Escaneá con el celu",
                ["red"] = "Permitir en la red", ["codigo"] = "Ver código", ["copiar"] = "Copiar",
                ["abrir"] = "Abrir", ["ninguno"] = "Ninguno", ["listo"] = "Vinculado", ["firma"] = "hecho por Kvothesson", ["buscar"] = "Buscar actualización", ["ultima"] = "Tenés la última versión", ["actualizando"] = "Actualizando…", ["sinred"] = "No se pudo buscar. Probá más tarde.", ["demorado"] = "Mandado antes",
            },
            ["pt"] = new Dictionary<string, string>
            {
                ["vincular"] = "Vincular celular", ["vinculados"] = "Celulares vinculados", ["desvincular"] = "Desvincular",
                ["carpeta"] = "Abrir pasta", ["pegar"] = "Colar automaticamente", ["sonido"] = "Som",
                ["inicio"] = "Iniciar com o Windows", ["salir"] = "Sair", ["escanea"] = "Escaneie com o celular",
                ["red"] = "Permitir na rede", ["codigo"] = "Ver código", ["copiar"] = "Copiar",
                ["abrir"] = "Abrir", ["ninguno"] = "Nenhum", ["listo"] = "Vinculado", ["firma"] = "feito por Kvothesson", ["buscar"] = "Procurar atualização", ["ultima"] = "Você tem a versão mais recente", ["actualizando"] = "Atualizando…", ["sinred"] = "Não foi possível procurar. Tente mais tarde.", ["demorado"] = "Enviado antes",
            },
            ["fr"] = new Dictionary<string, string>
            {
                ["vincular"] = "Associer un téléphone", ["vinculados"] = "Téléphones associés", ["desvincular"] = "Dissocier",
                ["carpeta"] = "Ouvrir le dossier", ["pegar"] = "Coller automatiquement", ["sonido"] = "Son",
                ["inicio"] = "Lancer avec Windows", ["salir"] = "Quitter", ["escanea"] = "Scannez avec le téléphone",
                ["red"] = "Autoriser sur le réseau", ["codigo"] = "Voir le code", ["copiar"] = "Copier",
                ["abrir"] = "Ouvrir", ["ninguno"] = "Aucun", ["listo"] = "Associé", ["firma"] = "fait par Kvothesson", ["buscar"] = "Rechercher une mise à jour", ["ultima"] = "Vous avez la dernière version", ["actualizando"] = "Mise à jour…", ["sinred"] = "Recherche impossible. Réessayez plus tard.", ["demorado"] = "Envoyé plus tôt",
            },
            ["de"] = new Dictionary<string, string>
            {
                ["vincular"] = "Handy verbinden", ["vinculados"] = "Verbundene Handys", ["desvincular"] = "Trennen",
                ["carpeta"] = "Ordner öffnen", ["pegar"] = "Automatisch einfügen", ["sonido"] = "Ton",
                ["inicio"] = "Mit Windows starten", ["salir"] = "Beenden", ["escanea"] = "Mit dem Handy scannen",
                ["red"] = "Im Netzwerk erlauben", ["codigo"] = "Code anzeigen", ["copiar"] = "Kopieren",
                ["abrir"] = "Öffnen", ["ninguno"] = "Keine", ["listo"] = "Verbunden", ["firma"] = "von Kvothesson", ["buscar"] = "Nach Updates suchen", ["ultima"] = "Du hast die neueste Version", ["actualizando"] = "Wird aktualisiert…", ["sinred"] = "Suche nicht möglich. Versuch es später.", ["demorado"] = "Früher gesendet",
            },
            ["it"] = new Dictionary<string, string>
            {
                ["vincular"] = "Collega un telefono", ["vinculados"] = "Telefoni collegati", ["desvincular"] = "Scollega",
                ["carpeta"] = "Apri cartella", ["pegar"] = "Incolla automaticamente", ["sonido"] = "Suono",
                ["inicio"] = "Avvia con Windows", ["salir"] = "Esci", ["escanea"] = "Scansiona con il telefono",
                ["red"] = "Consenti in rete", ["codigo"] = "Mostra codice", ["copiar"] = "Copia",
                ["abrir"] = "Apri", ["ninguno"] = "Nessuno", ["listo"] = "Collegato", ["firma"] = "fatto da Kvothesson", ["buscar"] = "Cerca aggiornamenti", ["ultima"] = "Hai l'ultima versione", ["actualizando"] = "Aggiornamento…", ["sinred"] = "Ricerca non riuscita. Riprova più tardi.", ["demorado"] = "Inviato prima",
            },
        };

        public static string T(string clave)
        {
            var idioma = CultureInfo.CurrentUICulture.TwoLetterISOLanguageName;
            return (Todos.TryGetValue(idioma, out var tabla) ? tabla : Todos["en"])[clave];
        }
    }
}
