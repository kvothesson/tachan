import AppKit
import ImageIO
import QuickLookThumbnailing

enum Imagenes {
    static let abribles: Set<String> = ["jpg", "jpeg", "png", "gif", "bmp", "webp", "heic", "heif", "tif", "tiff",
                                        "mp4", "mov", "m4v", "webm", "mkv", "avi", "3gp", "mp3", "m4a", "ogg", "wav", "opus"]

    // Solo medios se abren con doble clic: un archivo cualquiera puede ser un programa.
    static func seguroDeAbrir(_ ruta: URL) -> Bool { abribles.contains(ruta.pathExtension.lowercased()) }

    // La foto derecha (respeta la orientación de la cámara), o nil si no es una imagen. Con maximo, ya achicada.
    static func abrir(_ ruta: URL, maximo: Int? = nil) -> CGImage? {
        guard let fuente = CGImageSourceCreateWithURL(ruta as CFURL, [kCGImageSourceShouldCache: false] as CFDictionary),
              CGImageSourceGetCount(fuente) > 0,
              let props = CGImageSourceCopyPropertiesAtIndex(fuente, 0, nil) as? [CFString: Any],
              let ancho = props[kCGImagePropertyPixelWidth] as? Int, let alto = props[kCGImagePropertyPixelHeight] as? Int else { return nil }
        // Un video o un PDF también pueden tener "imagen": solo valen los tipos de imagen.
        guard let tipo = CGImageSourceGetType(fuente) as String?, !tipo.contains("pdf") else { return nil }
        let opciones: [CFString: Any] = [kCGImageSourceCreateThumbnailFromImageAlways: true, kCGImageSourceCreateThumbnailWithTransform: true,
                                         kCGImageSourceShouldCacheImmediately: true, kCGImageSourceThumbnailMaxPixelSize: maximo ?? max(ancho, alto)]
        return CGImageSourceCreateThumbnailAtIndex(fuente, 0, opciones as CFDictionary)
    }

    // La miniatura del sistema: sirve para videos, PDF, etc. Si no hay, el ícono del tipo.
    static func miniaturaDeSistema(_ ruta: URL, lado: CGFloat) -> NSImage {
        let pedido = QLThumbnailGenerator.Request(fileAt: ruta, size: NSSize(width: lado, height: lado), scale: 2, representationTypes: .thumbnail)
        let listo = DispatchSemaphore(value: 0)
        var hallada: NSImage?
        QLThumbnailGenerator.shared.generateBestRepresentation(for: pedido) { r, _ in
            hallada = r?.nsImage
            listo.signal()
        }
        _ = listo.wait(timeout: .now() + 2)
        return hallada ?? NSWorkspace.shared.icon(forFile: ruta.path)
    }
}

// Da la imagen recién cuando alguien la pega como imagen: copiar una foto de 12 MP no frena nada.
final class ProveedorImagen: NSObject, NSPasteboardItemDataProvider {
    let ruta: URL

    init(_ ruta: URL) { self.ruta = ruta }

    func pasteboard(_ pasteboard: NSPasteboard?, item: NSPasteboardItem, provideDataForType type: NSPasteboard.PasteboardType) {
        guard let imagen = Imagenes.abrir(ruta) else { return }
        let rep = NSBitmapImageRep(cgImage: imagen)
        let datos = type == .png ? rep.representation(using: .png, properties: [:]) : rep.tiffRepresentation
        if let d = datos { item.setData(d, forType: type) }
    }
}

enum Portapapeles {
    // El portapapeles no guarda al proveedor: se lo guarda acá hasta la próxima copia.
    static var proveedor: ProveedorImagen?

    // La última imagen de la tanda, o nil.
    static func ultimaImagen(_ tanda: [Recibido]) -> URL? {
        tanda.compactMap { $0.ruta }.reversed().first { Imagenes.abrir($0, maximo: 64) != nil }
    }

    // Las rutas como archivos, la última imagen también como dibujo y el último texto: sirve en cualquier programa.
    @discardableResult
    static func copiar(_ tanda: [Recibido], imagen: URL? = nil) -> Bool {
        let pb = NSPasteboard.general
        // Lo que viaja por tu red no sale a otros equipos por el portapapeles universal.
        pb.prepareForNewContents(with: .currentHostOnly)
        var items: [NSPasteboardItem] = []
        proveedor = nil
        for ruta in tanda.compactMap({ $0.ruta }) {
            let item = NSPasteboardItem()
            item.setString(ruta.absoluteString, forType: .fileURL)
            if ruta == imagen {
                let p = ProveedorImagen(ruta)
                proveedor = p
                item.setDataProvider(p, forTypes: [.png, .tiff])
            }
            items.append(item)
        }
        if let texto = tanda.last(where: { $0.texto != nil })?.texto, !texto.isEmpty {
            if items.isEmpty { items.append(NSPasteboardItem()) }
            items[0].setString(texto, forType: .string)
        }
        return pb.writeObjects(items)
    }

    // Cmd+V. macOS lo permite solo si Tachán está en Accesibilidad; si no, no hace nada.
    static func apretarPegar() {
        guard AXIsProcessTrusted() else { return }
        let fuente = CGEventSource(stateID: .combinedSessionState)
        let v: CGKeyCode = 9
        let baja = CGEvent(keyboardEventSource: fuente, virtualKey: v, keyDown: true)
        let sube = CGEvent(keyboardEventSource: fuente, virtualKey: v, keyDown: false)
        baja?.flags = .maskCommand
        sube?.flags = .maskCommand
        baja?.post(tap: .cghidEventTap)
        sube?.post(tap: .cghidEventTap)
    }

    static func pedirPermisoPegar() -> Bool {
        AXIsProcessTrustedWithOptions([kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true] as CFDictionary)
    }
}
