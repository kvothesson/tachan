import AppKit

// Arranque.
let argumentos = CommandLine.arguments
if let i = argumentos.firstIndex(of: "--icono"), i + 1 < argumentos.count {
    Icono.guardarJuego(argumentos[i + 1])
    exit(0)
}
try? FileManager.default.createDirectory(at: Datos.carpeta, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
if !Instancia.tomar() && !Instancia.pedirQueCierre() {
    Instancia.avisar("abrir")
    exit(0)
}
if Instalador.haceFalta && Instalador.mudarse() { exit(0) }

let app = NSApplication.shared
app.setActivationPolicy(.accessory)
Datos.cargar()
do {
    let bandeja = try Bandeja(oculto: argumentos.contains("--oculto"))
    app.delegate = bandeja
    app.run()
} catch {
    // Sin puerto no puede recibir nada: avisar en vez de cerrarse en silencio.
    NSApp.activate()
    let alerta = NSAlert()
    alerta.messageText = Marca.visible
    alerta.informativeText = error is Servidor.Falla ? Textos.t("ocupado") : error.localizedDescription
    alerta.alertStyle = .warning
    alerta.runModal()
}
