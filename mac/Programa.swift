import AppKit
import CryptoKit
import ServiceManagement

// Programa único por carpeta de datos: un candado en la carpeta y avisos entre procesos para abrir o cerrar.
enum Instancia {
    static var candado: Int32 = -1

    static func nombre(_ que: String) -> String {
        let carpeta = Datos.hex(Array(SHA256.hash(data: Data(Datos.carpeta.path.lowercased().utf8)))).prefix(12)
        return "com.kvothesson.tachan.\(que)." + (Datos.esPrueba ? String(carpeta) : "real")
    }

    static func tomar() -> Bool {
        if candado >= 0 { return true }
        let fd = open(Datos.carpeta.appendingPathComponent(".instancia").path, O_CREAT | O_RDWR | O_CLOEXEC, 0o600)
        if fd < 0 { return true }  // sin candado igual anda
        if flock(fd, LOCK_EX | LOCK_NB) != 0 {
            close(fd)
            return false
        }
        candado = fd
        return true
    }

    static func soltar() {
        if candado >= 0 { close(candado) }
        candado = -1
    }

    static func avisar(_ que: String) {
        DistributedNotificationCenter.default().postNotificationName(NSNotification.Name(nombre(que)), object: nil, userInfo: nil, deliverImmediately: true)
    }

    static func escuchar(_ que: String, _ hacer: @escaping () -> Void) {
        DistributedNotificationCenter.default().addObserver(forName: NSNotification.Name(nombre(que)), object: nil, queue: .main) { _ in hacer() }
    }

    // Si abrís una versión distinta con otra prendida, esa cierra para dejarle el lugar. Tus datos no se tocan.
    static func pedirQueCierre() -> Bool {
        if !Instalador.haceFalta || !Instalador.esOtraVersion { return false }
        avisar("cerrar")
        let limite = Date().addingTimeInterval(8)
        while Date() < limite {
            if tomar() { return true }
            Thread.sleep(forTimeInterval: 0.2)
        }
        return false
    }
}

// Arranque con la sesión: Ajustes del Sistema lo muestra en Ítems de inicio.
enum Inicio {
    static var activo: Bool { SMAppService.mainApp.status == .enabled }

    static func poner(_ activo: Bool) {
        if Datos.esPrueba { return }
        if activo { try? SMAppService.mainApp.register() } else { try? SMAppService.mainApp.unregister() }
    }
}

// Solo con TACHAN_DATOS puesto: deja el enlace, el QR y una foto de cada aviso para las pruebas automáticas.
enum Prueba {
    static var avisos = 0

    static func enganchar(_ servidor: Servidor) {
        if !Datos.esPrueba { return }
        Datos.escribir(String(servidor.puerto), en: Datos.carpeta.appendingPathComponent("puerto.txt"))
        Sonido.guardar(Datos.carpeta.appendingPathComponent("sonido.wav"))
    }

    static func anotarCodigo(_ enlace: String, _ qr: NSBitmapImageRep) {
        if !Datos.esPrueba { return }
        try? qr.representation(using: .png, properties: [:])?.write(to: Datos.carpeta.appendingPathComponent("qr.png"))
        Datos.escribir(enlace, en: Datos.carpeta.appendingPathComponent("enlace.txt"))
    }

    static func fotoAviso(_ aviso: Aviso) {
        if !Datos.esPrueba { return }
        avisos += 1
        let n = avisos
        // Un momento después: así la foto sale con la imagen ya pintada.
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
            try? aviso.foto()?.write(to: Datos.carpeta.appendingPathComponent(String(format: "aviso_%02d.png", n)))
        }
    }
}

// El programa vive en el ícono de la barra de menú.
final class Bandeja: NSObject, NSApplicationDelegate, NSMenuDelegate {
    static let esperaTanda = 0.7  // lo que llega junto se copia junto

    let item = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
    let aviso = Aviso()
    let servidor: Servidor
    var espera: Timer?
    var tanda: [Recibido] = []
    var demorados: [Recibido] = []
    let menu = NSMenu()
    let menuCelus = NSMenuItem(title: Textos.t("vinculados"), action: nil, keyEquivalent: "")
    var ventana: VentanaVinculo?

    init(oculto: Bool) throws {
        servidor = Servidor(identidad: try Datos.identidad())
        super.init()
        servidor.llegada = { r in DispatchQueue.main.async { self.lleno(r) } }
        servidor.vinculado = { d in DispatchQueue.main.async { self.alVincular(d) } }
        servidor.secretoAgotado = { DispatchQueue.main.async { self.ventana?.refrescar() } }
        try servidor.arrancar()

        aviso.alOcultar = { [weak self] in DispatchQueue.main.async { self?.mostrarDemorados() } }
        aviso.alMostrar = { Prueba.fotoAviso($0) }

        menu.appearance = Tema.apariencia
        menu.delegate = self
        menu.autoenablesItems = false
        agregar(Textos.t("vincular"), #selector(abrirVinculo))
        menuCelus.submenu = NSMenu()
        menu.addItem(menuCelus)
        menu.addItem(.separator())
        agregar(Textos.t("carpeta"), #selector(abrirCarpeta))
        menu.addItem(.separator())
        agregar(Textos.t("pegar"), #selector(cambiarPegar)).tag = 1
        agregar(Textos.t("sonido"), #selector(cambiarSonido)).tag = 2
        agregar(Textos.t("inicio"), #selector(cambiarInicio)).tag = 3
        menu.addItem(.separator())
        agregar(Textos.t("salir"), #selector(salir))
        menu.addItem(.separator())
        agregar(Textos.t("buscar"), #selector(buscarActualizacion))
        let firma = NSMenuItem(title: Marca.visible + " " + VersionApp.nombre + " · " + Textos.t("firma"), action: nil, keyEquivalent: "")
        firma.isEnabled = false
        menu.addItem(firma)

        item.button?.image = Icono.barra()
        item.button?.toolTip = Marca.visible + " " + VersionApp.nombre
        item.menu = menu

        // Otra instancia abierta (doble clic en la app) pide mostrar la ventana; una versión distinta, que cierre esta.
        Instancia.escuchar("abrir") { [weak self] in self?.abrirVinculo() }
        Instancia.escuchar("cerrar") { [weak self] in self?.salir() }

        Prueba.enganchar(servidor)
        if !oculto && Datos.dispositivos.isEmpty { abrirVinculo() }
        if CommandLine.arguments.contains("--buscar-actualizacion") { buscarActualizacion() }
    }

    @discardableResult
    private func agregar(_ titulo: String, _ accion: Selector) -> NSMenuItem {
        let i = NSMenuItem(title: titulo, action: accion, keyEquivalent: "")
        i.target = self
        menu.addItem(i)
        return i
    }

    func menuNeedsUpdate(_ m: NSMenu) {
        guard m === menu else { return }
        m.item(withTag: 1)?.state = Datos.pegarSolo ? .on : .off
        m.item(withTag: 2)?.state = Datos.sonido ? .on : .off
        m.item(withTag: 3)?.state = Inicio.activo ? .on : .off
        m.item(withTag: 3)?.isEnabled = !Datos.esPrueba
        let sub = menuCelus.submenu!
        sub.removeAllItems()
        Datos.cerrojo.lock()
        let lista = Datos.dispositivos
        Datos.cerrojo.unlock()
        if lista.isEmpty {
            let ninguno = NSMenuItem(title: Textos.t("ninguno"), action: nil, keyEquivalent: "")
            ninguno.isEnabled = false
            sub.addItem(ninguno)
        }
        for d in lista {
            let celu = NSMenuItem(title: d.nombre, action: nil, keyEquivalent: "")
            celu.submenu = NSMenu()
            let quitar = NSMenuItem(title: Textos.t("desvincular"), action: #selector(desvincular(_:)), keyEquivalent: "")
            quitar.target = self
            quitar.representedObject = d.id
            celu.submenu?.addItem(quitar)
            sub.addItem(celu)
        }
    }

    @objc func desvincular(_ i: NSMenuItem) {
        guard let id = i.representedObject as? String else { return }
        Datos.cerrojo.lock()
        Datos.dispositivos.removeAll { $0.id == id }
        Datos.cerrojo.unlock()
        Datos.guardarDispositivos()
    }

    @objc func cambiarPegar() {
        Datos.pegarSolo.toggle()
        Datos.guardarAjustes()
        if Datos.pegarSolo && !Portapapeles.pedirPermisoPegar() { aviso.mostrarTexto(Textos.t("pegar_permiso")) }
    }

    @objc func cambiarSonido() {
        Datos.sonido.toggle()
        Datos.guardarAjustes()
    }

    @objc func cambiarInicio() { Inicio.poner(!Inicio.activo) }

    @objc func abrirCarpeta() {
        try? FileManager.default.createDirectory(at: Datos.recibidos, withIntermediateDirectories: true)
        NSWorkspace.shared.open(Datos.recibidos)
    }

    @objc func abrirVinculo() {
        if let v = ventana {
            NSApp.activate()
            v.makeKeyAndOrderFront(nil)
            return
        }
        let v = VentanaVinculo(servidor: servidor)
        v.alCerrar = { [weak self] in
            self?.servidor.cerrarVinculo()
            self?.ventana = nil
        }
        ventana = v
        NSApp.activate()
        v.makeKeyAndOrderFront(nil)
    }

    @objc func buscarActualizacion() {
        Actualizador.buscar { texto in DispatchQueue.main.async { self.aviso.mostrarTexto(texto) } }
    }

    func alVincular(_ d: Dispositivo) {
        ventana?.close()
        if Datos.dispositivos.count == 1 { Inicio.poner(true) }
        Sonido.sonar()
        aviso.mostrarTexto(Textos.t("listo") + ": " + d.nombre)
    }

    func lleno(_ r: Recibido) {
        tanda.append(r)
        espera?.invalidate()
        espera = Timer.scheduledTimer(withTimeInterval: Bandeja.esperaTanda, repeats: false) { [weak self] _ in self?.entregar() }
    }

    func entregar() {
        espera = nil
        let copia = tanda.filter { !$0.demorado }
        demorados += tanda.filter { $0.demorado }
        tanda = []
        if copia.isEmpty {
            mostrarDemorados()
            return
        }
        // Decodificar tarda: se hace afuera del hilo principal.
        DispatchQueue.global(qos: .userInitiated).async {
            let imagen = Portapapeles.ultimaImagen(copia)
            let (miniatura, deArchivo) = Bandeja.miniatura(copia.last?.ruta)
            DispatchQueue.main.async {
                let seCopio = Portapapeles.copiar(copia, imagen: imagen)
                Sonido.sonar()
                if let sinVer = self.aviso.textoDemoradoSinVer { self.demorados.insert(sinVer, at: 0) }
                self.aviso.mostrar(copia, seCopio: seCopio, miniatura: miniatura, deArchivo: deArchivo)
                // Un salto de línea en una terminal abierta ejecutaría lo recibido: eso se pega a mano.
                if seCopio && Datos.pegarSolo && !copia.contains(where: { $0.texto?.contains(where: { $0 == "\n" || $0 == "\r" }) == true }) {
                    Portapapeles.apretarPegar()
                }
            }
        }
    }

    // Para el aviso alcanza con algo chico. Una imagen se ve entera; otro archivo, con su miniatura del sistema.
    static func miniatura(_ ruta: URL?) -> (NSImage?, Bool) {
        guard let ruta = ruta else { return (nil, false) }
        if let cg = Imagenes.abrir(ruta, maximo: Int(Aviso.altoMaximoImagen * 2)) {
            return (NSImage(cgImage: cg, size: NSSize(width: CGFloat(cg.width) / 2, height: CGFloat(cg.height) / 2)), true)
        }
        return (Imagenes.miniaturaDeSistema(ruta, lado: Aviso.ladoMiniaturaSistema), false)
    }

    // Lo que se mandó con la compu apagada puede llegar en cualquier momento: se avisa, pero no pisa el
    // portapapeles, no se pega solo y no se suma a lo que acabás de mandar. Los archivos ya están en la carpeta.
    func mostrarDemorados() {
        if aviso.isVisible || demorados.isEmpty { return }
        let archivos = demorados.filter { $0.ruta != nil }
        let copia = archivos.isEmpty ? Array(demorados.prefix(1)) : archivos
        demorados.removeAll { r in copia.contains { $0 === r } }
        DispatchQueue.global(qos: .userInitiated).async {
            let (miniatura, deArchivo) = Bandeja.miniatura(copia.last?.ruta)
            DispatchQueue.main.async {
                if self.aviso.isVisible {
                    self.demorados.insert(contentsOf: copia, at: 0)
                    return
                }
                Sonido.sonar()
                self.aviso.mostrar(copia, seCopio: false, miniatura: miniatura, deArchivo: deArchivo)
            }
        }
    }

    @objc func salir() {
        servidor.apagar()
        NSApp.terminate(nil)
    }

    func applicationWillTerminate(_ notification: Notification) {
        servidor.apagar()
    }
}

final class VentanaVinculo: NSWindow, NSWindowDelegate {
    static let minutosValidez = 5.0

    let servidor: Servidor
    let qr = NSImageView()
    let codigo = NSTextField(labelWithString: "")
    let verCodigo = NSButton()
    var renovar: Timer?
    var alCerrar: (() -> Void)?

    init(servidor: Servidor) {
        self.servidor = servidor
        super.init(contentRect: NSRect(x: 0, y: 0, width: 320, height: 380), styleMask: [.titled, .closable], backing: .buffered, defer: false)
        title = Marca.visible
        isReleasedWhenClosed = false
        appearance = Tema.apariencia
        backgroundColor = Tema.suelo
        delegate = self
        let contenido = VistaVolteada(frame: NSRect(x: 0, y: 0, width: 320, height: 380))
        contentView = contenido

        qr.frame = NSRect(x: 40, y: 24, width: 240, height: 240)
        qr.imageScaling = .scaleProportionallyUpOrDown
        qr.wantsLayer = true
        qr.layer?.backgroundColor = NSColor.white.cgColor
        qr.layer?.magnificationFilter = .nearest

        let frase = NSTextField(labelWithString: Textos.t("escanea"))
        frase.font = NSFont.systemFont(ofSize: 15, weight: .semibold)
        frase.textColor = Tema.texto
        frase.alignment = .center
        frase.frame = NSRect(x: 0, y: 280, width: 320, height: 22)

        verCodigo.title = ""
        verCodigo.attributedTitle = NSAttributedString(string: Textos.t("codigo"), attributes: [.foregroundColor: Tema.tenue, .font: NSFont.systemFont(ofSize: 12)])
        verCodigo.isBordered = false
        verCodigo.frame = NSRect(x: 0, y: 312, width: 320, height: 22)
        verCodigo.target = self
        verCodigo.action = #selector(mostrarCodigo)

        codigo.font = NSFont.monospacedSystemFont(ofSize: 11.5, weight: .regular)
        codigo.textColor = Tema.texto
        codigo.alignment = .center
        codigo.isSelectable = true
        codigo.frame = NSRect(x: 10, y: 314, width: 300, height: 20)
        codigo.isHidden = true

        [qr, frase, verCodigo, codigo].forEach(contenido.addSubview)
        center()
        refrescar()
        let r = Timer(timeInterval: VentanaVinculo.minutosValidez * 60, repeats: true) { [weak self] _ in self?.refrescar() }
        RunLoop.main.add(r, forMode: .common)
        renovar = r
    }

    @objc func mostrarCodigo() {
        verCodigo.isHidden = true
        codigo.isHidden = false
    }

    // Cada QR dura 5 minutos: si alguien lo fotografía después, ya no sirve.
    func refrescar() {
        let c = servidor.abrirVinculo()
        let nombre = Datos.nombreEquipo.addingPercentEncoding(withAllowedCharacters: .alphanumerics.union(CharacterSet(charactersIn: "-._~"))) ?? ""
        let enlace = Marca.enlace + "c=" + c + "&n=" + nombre
        codigo.stringValue = c
        guard let q = Qr.crear(enlace) else { return }
        let rep = q.imagen(escala: 8, margen: 3)
        let imagen = NSImage(size: rep.size)
        imagen.addRepresentation(rep)
        qr.image = imagen
        Prueba.anotarCodigo(enlace, rep)
    }

    func windowWillClose(_ notification: Notification) {
        renovar?.invalidate()
        alCerrar?()
    }
}

final class VistaVolteada: NSView {
    override var isFlipped: Bool { true }
}
