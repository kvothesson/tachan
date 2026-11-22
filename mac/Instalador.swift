import AppKit

// Sin instalador aparte: la primera vez que se abre se copia a ~/Applications y queda como cualquier app.
enum Instalador {
    static var destino: URL {
        FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Applications", isDirectory: true)
            .appendingPathComponent(Marca.nombre + ".app", isDirectory: true)
    }

    static var actual: URL { Bundle.main.bundleURL }

    static var haceFalta: Bool {
        !Datos.esPrueba && actual.pathExtension == "app"
            && actual.resolvingSymlinksInPath().standardizedFileURL.path.lowercased() != destino.resolvingSymlinksInPath().standardizedFileURL.path.lowercased()
    }

    static func ejecutable(_ app: URL) -> URL { app.appendingPathComponent("Contents/MacOS/" + Marca.nombre) }

    static var esOtraVersion: Bool {
        guard let nuevo = try? Data(contentsOf: ejecutable(actual)) else { return false }
        guard let viejo = try? Data(contentsOf: ejecutable(destino)) else { return true }
        return nuevo != viejo
    }

    // Devuelve false si no se pudo: la app igual anda desde donde esté.
    static func mudarse() -> Bool {
        let fm = FileManager.default
        let carpeta = destino.deletingLastPathComponent()
        let temporal = carpeta.appendingPathComponent(".\(Marca.nombre)-\(UUID().uuidString).app", isDirectory: true)
        do {
            try fm.createDirectory(at: carpeta, withIntermediateDirectories: true)
            // Copia aparte y después el cambio: si algo falla a mitad, la instalada sigue entera.
            try fm.copyItem(at: actual, to: temporal)
            quitarCuarentena(temporal)
            if fm.fileExists(atPath: destino.path) {
                _ = try fm.replaceItemAt(destino, withItemAt: temporal)
            } else {
                try fm.moveItem(at: temporal, to: destino)
            }
        } catch {
            try? fm.removeItem(at: temporal)
            return false
        }
        // La copia instalada tiene que encontrar libre el lugar de "programa único".
        Instancia.soltar()
        return abrir(destino, argumentos: Array(CommandLine.arguments.dropFirst()))
    }

    // La copia ya es de confianza: Gatekeeper no vuelve a preguntar por ella. Lo recibido por Tachán no se toca.
    static func quitarCuarentena(_ app: URL) {
        removexattr(app.path, "com.apple.quarantine", XATTR_NOFOLLOW)
        guard let todos = FileManager.default.enumerator(at: app, includingPropertiesForKeys: nil) else { return }
        for case let ruta as URL in todos { removexattr(ruta.path, "com.apple.quarantine", XATTR_NOFOLLOW) }
    }

    // Por Launch Services, no como proceso hijo: así la nueva no hereda nada de esta, ni el puerto.
    static func abrir(_ app: URL, argumentos: [String]) -> Bool {
        let configuracion = NSWorkspace.OpenConfiguration()
        configuracion.createsNewApplicationInstance = true
        configuracion.arguments = argumentos
        configuracion.activates = false
        let listo = DispatchSemaphore(value: 0)
        var bien = false
        NSWorkspace.shared.openApplication(at: app, configuration: configuracion) { abierta, _ in
            bien = abierta != nil
            listo.signal()
        }
        _ = listo.wait(timeout: .now() + 15)
        return bien
    }
}
