import AppKit

// El aviso que aparece al llegar algo. Nunca toma el foco: seguís escribiendo donde estabas.
final class Aviso: NSPanel {
    static let segundosVisible = 6.0
    static let ancho: CGFloat = 300
    static let altoMaximoImagen: CGFloat = 320
    static let ladoMiniaturaSistema: CGFloat = 128

    final class Accion {
        let icono: String
        let ayuda: String
        let hacer: () -> Void
        var caja = NSRect.zero

        init(_ icono: String, _ ayuda: String, _ hacer: @escaping () -> Void) {
            self.icono = icono
            self.ayuda = ayuda
            self.hacer = hacer
        }
    }

    private(set) var tanda: [Recibido] = []
    var imagen: NSImage?
    var imagenDeArchivo = false
    var copiado = false
    var acciones: [Accion] = []
    var bajoElMouse: Accion?
    var confirmadoEn: Date?
    var arrastrando = false
    var visto = false
    var zonaContenido = NSRect.zero
    private var reloj: Timer?
    private var ocultarEn = Date()
    private var mostradoEn = Date()
    private var yFinal: CGFloat = 0
    var alOcultar: (() -> Void)?
    var alMostrar: ((Aviso) -> Void)?
    private let vista = VistaAviso()

    init() {
        super.init(contentRect: NSRect(x: 0, y: 0, width: Aviso.ancho, height: 100), styleMask: [.borderless, .nonactivatingPanel],
                   backing: .buffered, defer: true)
        isFloatingPanel = true
        // Arriba de todo, también de una app a pantalla completa y en cualquier escritorio.
        level = .statusBar
        collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .stationary, .ignoresCycle]
        hidesOnDeactivate = false
        becomesKeyOnlyIfNeeded = true
        isOpaque = false
        backgroundColor = .clear
        hasShadow = true
        isReleasedWhenClosed = false
        appearance = Tema.apariencia
        vista.aviso = self
        contentView = vista
    }

    override var canBecomeKey: Bool { false }
    override var canBecomeMain: Bool { false }

    var demorada: Bool { tanda.last?.demorado == true }

    // Un texto no queda en ninguna carpeta: si llegó con la cola, espera a que pases el mouse.
    var textoDemoradoSinVer: Recibido? {
        isVisible && demorada && tanda.last?.texto != nil && !visto ? tanda.last : nil
    }

    // Arrastrás y copiás lo que ves. La cola junta cosas que mandaste por separado: esas se agarran de a una.
    var elegidos: [Recibido] { demorada ? Array(tanda.suffix(1)) : tanda }

    // miniatura: la de la imagen recibida; si no hay, se busca la del sistema.
    func mostrar(_ nueva: [Recibido], seCopio: Bool, miniatura: NSImage? = nil, deArchivo: Bool = false) {
        tanda = nueva
        copiado = seCopio
        visto = false
        confirmadoEn = nil
        imagen = nil
        imagenDeArchivo = false
        if nueva.last?.texto == nil, nueva.last(where: { $0.ruta != nil }) != nil {
            imagen = miniatura
            imagenDeArchivo = deArchivo && miniatura != nil
        }
        armarAcciones()
        acomodar()
        ocultarEn = Date().addingTimeInterval(Aviso.segundosVisible)
        mostradoEn = Date()
        if reloj == nil {
            let r = Timer(timeInterval: 0.06, repeats: true) { [weak self] _ in self?.latido() }
            RunLoop.main.add(r, forMode: .common)
            reloj = r
        }
        if !isVisible {
            setFrameOrigin(NSPoint(x: frame.minX, y: yFinal + 16))
            alphaValue = 0
        }
        orderFrontRegardless()
        vista.needsDisplay = true
        vista.window?.invalidateCursorRects(for: vista)
        alMostrar?(self)
    }

    // Para confirmar algo sin contenido, como un celu recién vinculado.
    func mostrarTexto(_ texto: String) {
        mostrar([Recibido(texto: texto)], seCopio: true)
        acciones = []
        vista.needsDisplay = true
    }

    func ocultar() {
        reloj?.invalidate()
        reloj = nil
        orderOut(nil)
        imagen = nil
        imagenDeArchivo = false
        tanda = []
        acciones = []
        bajoElMouse = nil
        alOcultar?()
    }

    func enlaceDeTexto() -> URL? {
        guard let t = tanda.last?.texto?.trimmingCharacters(in: .whitespacesAndNewlines), !t.contains(" "),
              let u = URL(string: t), u.scheme == "http" || u.scheme == "https", u.host != nil else { return nil }
        return u
    }

    private func armarAcciones() {
        acciones = []
        if let enlace = enlaceDeTexto() {
            acciones.append(Accion("abrir", Textos.t("abrir")) { NSWorkspace.shared.open(enlace) })
        }
        acciones.append(Accion("copiar", Textos.t("copiar")) { [weak self] in self?.copiarDeNuevo() })
        if let ruta = tanda.last(where: { $0.ruta != nil })?.ruta, tanda.last?.texto == nil {
            acciones.append(Accion("carpeta", Textos.t("carpeta")) { NSWorkspace.shared.activateFileViewerSelecting([ruta]) })
        }
    }

    func copiarDeNuevo() {
        copiado = Portapapeles.copiar(elegidos, imagen: Portapapeles.ultimaImagen(elegidos))
        confirmadoEn = Date()
        vista.needsDisplay = true
    }

    static let fuenteTexto = NSFont.systemFont(ofSize: 14)

    private func altoContenido() -> CGFloat {
        let ancho = Aviso.ancho
        if imagenDeArchivo, let i = imagen, i.size.width > 0 {
            return min(Aviso.altoMaximoImagen, max(90, ancho * i.size.height / i.size.width))
        }
        if let texto = tanda.last?.texto {
            let medida = NSAttributedString(string: texto, attributes: [.font: Aviso.fuenteTexto])
                .boundingRect(with: NSSize(width: ancho - 28, height: .greatestFiniteMagnitude), options: [.usesLineFragmentOrigin, .usesFontLeading])
            return min(130, ceil(medida.height) + 28)
        }
        return 74
    }

    private func acomodar() {
        let alto = altoContenido() + 44
        let raton = NSEvent.mouseLocation
        let pantalla = (NSScreen.screens.first { NSMouseInRect(raton, $0.frame, false) } ?? NSScreen.main ?? NSScreen.screens[0]).visibleFrame
        // Arriba a la derecha, donde macOS pone sus avisos.
        yFinal = pantalla.maxY - alto - 14
        setFrame(NSRect(x: pantalla.maxX - Aviso.ancho - 14, y: isVisible ? yFinal : frame.minY, width: Aviso.ancho, height: alto), display: false)
        vista.frame = NSRect(x: 0, y: 0, width: Aviso.ancho, height: alto)
        zonaContenido = NSRect(x: 0, y: 0, width: Aviso.ancho, height: alto - 44)
        var x = Aviso.ancho - 8
        for a in acciones.reversed() {
            x -= 32
            a.caja = NSRect(x: x, y: alto - 38, width: 32, height: 32)
            x -= 2
        }
        vista.armarAyudas()
    }

    private func latido() {
        let transcurrido = Date().timeIntervalSince(mostradoEn)
        let t = min(1, transcurrido / 0.18)
        let suave = 1 - (1 - t) * (1 - t)
        alphaValue = suave
        let y = yFinal + (1 - suave) * 16
        if frame.minY != y { setFrameOrigin(NSPoint(x: frame.minX, y: y)) }

        let adentro = NSMouseInRect(NSEvent.mouseLocation, frame, false)
        if adentro { visto = true }
        if adentro || arrastrando || textoDemoradoSinVer != nil { ocultarEn = Date().addingTimeInterval(2) }
        if !adentro && bajoElMouse != nil {
            bajoElMouse = nil
            vista.needsDisplay = true
        }
        if Date() > ocultarEn {
            ocultar()
            return
        }
        if let c = confirmadoEn, Date().timeIntervalSince(c) > 0.8 {
            confirmadoEn = nil
            vista.needsDisplay = true
        }
    }

    // Para las pruebas: lo que se ve, sin el resto de la pantalla.
    func foto() -> Data? {
        guard let rep = vista.bitmapImageRepForCachingDisplay(in: vista.bounds) else { return nil }
        vista.cacheDisplay(in: vista.bounds, to: rep)
        return rep.representation(using: .png, properties: [:])
    }
}

final class VistaAviso: NSView, NSDraggingSource {
    weak var aviso: Aviso!
    private var apretadoEn: NSPoint?

    override var isFlipped: Bool { true }
    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }

    override init(frame: NSRect) {
        super.init(frame: frame)
        wantsLayer = true
        layer?.cornerRadius = 14
        layer?.masksToBounds = true
    }

    required init?(coder: NSCoder) { fatalError() }

    override func updateTrackingAreas() {
        super.updateTrackingAreas()
        trackingAreas.forEach(removeTrackingArea)
        addTrackingArea(NSTrackingArea(rect: bounds, options: [.activeAlways, .mouseMoved, .mouseEnteredAndExited, .inVisibleRect], owner: self))
    }

    func armarAyudas() {
        removeAllToolTips()
        for a in aviso.acciones { addToolTip(a.caja, owner: a.ayuda as NSString, userData: nil) }
    }

    override func draw(_ dirtyRect: NSRect) {
        Tema.fondo.setFill()
        bounds.fill()
        guard let ultima = aviso.tanda.last else { return }
        if aviso.imagenDeArchivo, let i = aviso.imagen { pintarEntera(i, en: aviso.zonaContenido) }
        else if let texto = ultima.texto { pintarTexto(texto) }
        else if let ruta = ultima.ruta { pintarArchivo(ruta) }

        if aviso.tanda.count > 1 { pintarCantidad(aviso.tanda.count) }

        let y = bounds.height - 22
        let okCaja = NSRect(x: 12, y: y - 10, width: 20, height: 20)
        if aviso.copiado {
            Tema.icono("ok", en: okCaja, color: Tema.ok, grosor: 2.6)
        } else if aviso.demorada {
            Tema.icono("reloj", en: okCaja, color: Tema.tenue)
            let estilo = NSMutableParagraphStyle()
            estilo.lineBreakMode = .byTruncatingTail
            let texto = NSAttributedString(string: Textos.t("demorado"), attributes: [.font: NSFont.systemFont(ofSize: 11.5), .foregroundColor: Tema.tenue, .paragraphStyle: estilo])
            let alto = texto.size().height
            texto.draw(in: NSRect(x: okCaja.maxX + 4, y: okCaja.midY - alto / 2, width: 170, height: alto))
        }

        for accion in aviso.acciones {
            if accion === aviso.bajoElMouse {
                Tema.fondo2.setFill()
                NSBezierPath(roundedRect: accion.caja, xRadius: 8, yRadius: 8).fill()
            }
            let caja = accion.caja.insetBy(dx: 7, dy: 7)
            let color = accion.icono == "abrir" ? Tema.acento : Tema.tenue
            if accion.icono == "copiar" && aviso.confirmadoEn != nil { Tema.icono("ok", en: caja, color: Tema.ok, grosor: 2.6) }
            else { Tema.icono(accion.icono, en: caja, color: color) }
        }
    }

    // Se ve siempre entera: lo que llegó tiene que reconocerse de un vistazo, aunque sea largo.
    private func pintarEntera(_ i: NSImage, en zona: NSRect) {
        Tema.fondo2.setFill()
        zona.fill()
        let escala = min(zona.width / i.size.width, zona.height / i.size.height)
        let w = i.size.width * escala, h = i.size.height * escala
        i.draw(in: NSRect(x: zona.minX + (zona.width - w) / 2, y: zona.minY + (zona.height - h) / 2, width: w, height: h),
               from: .zero, operation: .sourceOver, fraction: 1, respectFlipped: true, hints: [.interpolation: NSImageInterpolation.high.rawValue])
    }

    private func pintarTexto(_ texto: String) {
        let estilo = NSMutableParagraphStyle()
        estilo.lineBreakMode = .byWordWrapping
        let a = NSAttributedString(string: texto, attributes: [.font: Aviso.fuenteTexto, .foregroundColor: Tema.texto, .paragraphStyle: estilo])
        a.draw(with: NSRect(x: 14, y: 14, width: bounds.width - 28, height: aviso.zonaContenido.height - 20),
               options: [.usesLineFragmentOrigin, .truncatesLastVisibleLine, .usesFontLeading])
    }

    private func pintarArchivo(_ ruta: URL) {
        let mini = NSRect(x: 14, y: 14, width: 46, height: 46)
        Tema.fondo2.setFill()
        NSBezierPath(roundedRect: mini, xRadius: 9, yRadius: 9).fill()
        if let i = aviso.imagen {
            i.draw(in: mini.insetBy(dx: 5, dy: 5), from: .zero, operation: .sourceOver, fraction: 1, respectFlipped: true, hints: nil)
        }
        let x = mini.maxX + 12
        let ancho = bounds.width - x - 14
        let estilo = NSMutableParagraphStyle()
        estilo.lineBreakMode = .byTruncatingMiddle
        NSAttributedString(string: ruta.lastPathComponent, attributes: [.font: NSFont.systemFont(ofSize: 13), .foregroundColor: Tema.texto, .paragraphStyle: estilo])
            .draw(in: NSRect(x: x, y: mini.minY + 3, width: ancho, height: 20))
        let tamano = (try? ruta.resourceValues(forKeys: [.fileSizeKey]).fileSize).map { VistaAviso.tamano(Int64($0)) } ?? ""
        NSAttributedString(string: tamano, attributes: [.font: NSFont.systemFont(ofSize: 11.5), .foregroundColor: Tema.tenue, .paragraphStyle: estilo])
            .draw(in: NSRect(x: x, y: mini.minY + 25, width: ancho, height: 18))
    }

    static func tamano(_ bytes: Int64) -> String {
        if bytes >= 1 << 30 { return String(format: "%.1f GB", Double(bytes) / Double(1 << 30)) }
        if bytes >= 1 << 20 { return String(format: "%.1f MB", Double(bytes) / Double(1 << 20)) }
        return "\(max(1, bytes / 1024)) KB"
    }

    private func pintarCantidad(_ cantidad: Int) {
        let texto = NSAttributedString(string: "\(cantidad)", attributes: [.font: NSFont.boldSystemFont(ofSize: 11.5), .foregroundColor: NSColor.white])
        let m = texto.size()
        let caja = NSRect(x: bounds.width - m.width - 20, y: 8, width: m.width + 12, height: m.height + 2)
        NSColor(white: 0, alpha: 170 / 255).setFill()
        NSBezierPath(roundedRect: caja, xRadius: caja.height / 2, yRadius: caja.height / 2).fill()
        texto.draw(at: NSPoint(x: caja.minX + 6, y: caja.minY + 1))
    }

    private func accion(en p: NSPoint) -> Aviso.Accion? { aviso.acciones.first { $0.caja.contains(p) } }

    override func mouseMoved(with event: NSEvent) {
        let p = convert(event.locationInWindow, from: nil)
        let nueva = accion(en: p)
        if nueva !== aviso.bajoElMouse {
            aviso.bajoElMouse = nueva
            needsDisplay = true
        }
        (nueva != nil || aviso.zonaContenido.contains(p) ? NSCursor.pointingHand : NSCursor.arrow).set()
    }

    override func mouseExited(with event: NSEvent) {
        NSCursor.arrow.set()
    }

    override func rightMouseDown(with event: NSEvent) {
        aviso.ocultar()
    }

    override func mouseDown(with event: NSEvent) {
        let p = convert(event.locationInWindow, from: nil)
        if event.clickCount == 2, let ruta = aviso.tanda.last?.ruta, Imagenes.seguroDeAbrir(ruta), aviso.zonaContenido.contains(p) {
            NSWorkspace.shared.open(ruta)
            apretadoEn = nil
            return
        }
        apretadoEn = accion(en: p) == nil ? p : nil
    }

    override func mouseDragged(with event: NSEvent) {
        guard let inicio = apretadoEn else { return }
        let p = convert(event.locationInWindow, from: nil)
        if max(abs(p.x - inicio.x), abs(p.y - inicio.y)) > 5 {
            apretadoEn = nil
            arrastrar(event)
        }
    }

    override func mouseUp(with event: NSEvent) {
        let p = convert(event.locationInWindow, from: nil)
        if let a = accion(en: p) { a.hacer() }
        else if apretadoEn != nil && aviso.zonaContenido.contains(p) && event.clickCount < 2 { aviso.copiarDeNuevo() }
        apretadoEn = nil
    }

    private func arrastrar(_ event: NSEvent) {
        let elegidos = aviso.elegidos
        var items: [NSDraggingItem] = []
        let figura = aviso.imagen ?? Icono.app(48)
        let marco = NSRect(origin: convert(event.locationInWindow, from: nil), size: NSSize(width: 48, height: 48 * max(0.3, figura.size.height / max(1, figura.size.width))))
            .offsetBy(dx: -24, dy: -24)
        for ruta in elegidos.compactMap({ $0.ruta }) {
            let item = NSDraggingItem(pasteboardWriter: ruta as NSURL)
            item.setDraggingFrame(marco, contents: figura)
            items.append(item)
        }
        if let texto = elegidos.last(where: { $0.texto != nil })?.texto, !texto.isEmpty {
            let item = NSDraggingItem(pasteboardWriter: texto as NSString)
            item.setDraggingFrame(marco, contents: Icono.app(48))
            items.append(item)
        }
        if items.isEmpty { return }
        aviso.arrastrando = true
        beginDraggingSession(with: items, event: event, source: self)
    }

    func draggingSession(_ session: NSDraggingSession, sourceOperationMaskFor context: NSDraggingContext) -> NSDragOperation { .copy }

    func draggingSession(_ session: NSDraggingSession, endedAt screenPoint: NSPoint, operation: NSDragOperation) {
        aviso.arrastrando = false
    }
}
