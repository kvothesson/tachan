import CoreServices
import Foundation
import Network

final class Recibido {
    let ruta: URL?    // nil si es texto
    let texto: String?  // nil si es archivo
    let demorado: Bool  // se mandó antes, con la compu apagada: salió solo de la cola del celu

    init(ruta: URL? = nil, texto: String? = nil, demorado: Bool = false) {
        self.ruta = ruta
        self.texto = texto
        self.demorado = demorado
    }
}

// Una conexión TLS que se lee de corrido, como un stream: cada pedido se atiende en su propio hilo.
final class Canal {
    let conexion: NWConnection
    private var pendiente = Data()
    private var terminado = false

    init(_ conexion: NWConnection) { self.conexion = conexion }

    func abrir(hasta plazo: DispatchTime) -> Bool {
        let listo = DispatchSemaphore(value: 0)
        var avisado = false, bien = false
        let cola = DispatchQueue(label: "tachan.canal")
        conexion.stateUpdateHandler = { estado in
            if avisado { return }
            switch estado {
            case .ready: bien = true
            case .failed, .cancelled: bien = false
            default: return
            }
            avisado = true
            listo.signal()
        }
        conexion.start(queue: cola)
        if listo.wait(timeout: plazo) == .timedOut {
            conexion.cancel()
            return false
        }
        return bien
    }

    private func recibir(hasta plazo: DispatchTime) -> Bool {
        if terminado { return false }
        let listo = DispatchSemaphore(value: 0)
        var nuevo: Data?
        var fin = false
        conexion.receive(minimumIncompleteLength: 1, maximumLength: 256 * 1024) { datos, _, completo, error in
            nuevo = datos
            fin = completo || error != nil
            listo.signal()
        }
        if listo.wait(timeout: plazo) == .timedOut {
            terminado = true
            conexion.cancel()
            return false
        }
        if fin { terminado = true }
        guard let d = nuevo, !d.isEmpty else { return false }
        pendiente.append(d)
        return true
    }

    // La cabecera HTTP hasta la línea vacía. Lo que sobra queda para el cuerpo.
    func leerCabecera(maximo: Int, hasta plazo: DispatchTime) -> String? {
        let separador = Data("\r\n\r\n".utf8)
        while true {
            if let r = pendiente.range(of: separador) {
                let cabecera = pendiente.subdata(in: pendiente.startIndex..<r.lowerBound)
                pendiente = pendiente.subdata(in: r.upperBound..<pendiente.endIndex)
                return String(decoding: cabecera, as: UTF8.self)
            }
            if pendiente.count > maximo || !recibir(hasta: plazo) { return nil }
        }
    }

    // Entrega el cuerpo de a trozos. Devuelve false si se cortó antes de completar.
    func leerCuerpo(largo: Int64, esperaPorTrozo: Double, _ entregar: (Data) throws -> Void) rethrows -> Bool {
        var restante = largo
        while restante > 0 {
            if pendiente.isEmpty && !recibir(hasta: .now() + esperaPorTrozo) { return false }
            let n = Int(min(Int64(pendiente.count), restante))
            try entregar(pendiente.prefix(n))
            pendiente = pendiente.dropFirst(n)
            if pendiente.isEmpty { pendiente = Data() }
            restante -= Int64(n)
        }
        return true
    }

    func escribir(_ datos: Data, final: Bool) {
        let listo = DispatchSemaphore(value: 0)
        conexion.send(content: datos, contentContext: final ? .finalMessage : .defaultMessage, isComplete: final,
                      completion: .contentProcessed { _ in listo.signal() })
        _ = listo.wait(timeout: .now() + 30)
    }

    func cerrar() { conexion.cancel() }
}

final class Servidor {
    static let margenDisco: Int64 = 200 * 1024 * 1024
    static let maximoTexto = 2 * 1024 * 1024
    static let maximoCabecera = 16 * 1024
    static let maximoIntentos = 5
    static let maximoPorDireccion = 4
    static let plazoCabecera = 10.0
    static let esperaLectura = 30.0
    static let intentosPuerto = 20

    let identidad: SecIdentity
    let huella: [UInt8]
    private let cupos = DispatchSemaphore(value: 16)
    private var porDireccion: [String: Int] = [:]
    private let cerrojoDirecciones = NSLock()
    private var oyente: NWListener?
    private var udp: Int32 = -1
    private var apagando = false
    private var secretoVinculo: [UInt8]?
    private var intentosVinculo = 0
    private let cerrojoVinculo = NSLock()

    private(set) var puerto = 0
    var llegada: ((Recibido) -> Void)?
    var vinculado: ((Dispositivo) -> Void)?
    var secretoAgotado: (() -> Void)?

    init(identidad: SecIdentity) {
        self.identidad = identidad
        huella = Datos.huella(identidad)
    }

    enum Falla: Error { case puertoOcupado }

    func arrancar() throws {
        let pedido = Int(Datos.entorno["TACHAN_PUERTO"] ?? "") ?? Marca.puertoTcp
        // Si la versión vieja todavía está soltando el puerto, se espera un poco en vez de caerse.
        for intento in 1... {
            if escuchar(pedido) { break }
            if intento >= Servidor.intentosPuerto { throw Falla.puertoOcupado }
            Thread.sleep(forTimeInterval: 0.5)
        }
        let hilo = Thread { [weak self] in self?.bucleUdp() }
        hilo.start()
    }

    private func escuchar(_ pedido: Int) -> Bool {
        let tls = NWProtocolTLS.Options()
        sec_protocol_options_set_local_identity(tls.securityProtocolOptions, sec_identity_create(identidad)!)
        sec_protocol_options_set_min_tls_protocol_version(tls.securityProtocolOptions, .TLSv12)
        let parametros = NWParameters(tls: tls)
        guard let puertoNw = NWEndpoint.Port(rawValue: UInt16(pedido)), let o = try? NWListener(using: parametros, on: puertoNw) else { return false }
        let listo = DispatchSemaphore(value: 0)
        var bien = false, avisado = false
        o.stateUpdateHandler = { estado in
            if avisado { return }
            switch estado {
            case .ready: bien = true
            case .failed, .cancelled, .waiting: bien = false
            default: return
            }
            avisado = true
            listo.signal()
        }
        o.newConnectionHandler = { [weak self] c in self?.aceptar(c) }
        o.start(queue: DispatchQueue(label: "tachan.oyente"))
        if listo.wait(timeout: .now() + 5) == .timedOut || !bien {
            o.cancel()
            return false
        }
        let real = Int(o.port?.rawValue ?? 0)
        guard abrirUdp(real + 1) else {
            o.cancel()
            return false
        }
        oyente = o
        puerto = real
        return true
    }

    func apagar() {
        apagando = true
        oyente?.cancel()
        if udp >= 0 {
            shutdown(udp, SHUT_RDWR)
            close(udp)
            udp = -1
        }
    }

    // Mientras la ventana de vincular está abierta hay un secreto válido; al cerrarla, ninguno.
    func abrirVinculo() -> String {
        cerrojoVinculo.lock()
        defer { cerrojoVinculo.unlock() }
        let secreto = Datos.azar(6)
        secretoVinculo = secreto
        intentosVinculo = 0
        return CodigoVinculo.armar(ip: Servidor.ipLocal(), puerto: puerto, secreto: secreto, huella: huella)
    }

    func cerrarVinculo() {
        cerrojoVinculo.lock()
        secretoVinculo = nil
        cerrojoVinculo.unlock()
    }

    static func ipLocal() -> [UInt8] {
        let s = socket(AF_INET, SOCK_DGRAM, 0)
        defer { close(s) }
        var destino = sockaddr_in()
        destino.sin_family = sa_family_t(AF_INET)
        destino.sin_port = in_port_t(9).bigEndian
        inet_pton(AF_INET, "192.0.2.1", &destino.sin_addr)  // no manda nada: solo elige la placa de red
        _ = withUnsafePointer(to: &destino) { $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { connect(s, $0, socklen_t(MemoryLayout<sockaddr_in>.size)) } }
        var local = sockaddr_in()
        var largo = socklen_t(MemoryLayout<sockaddr_in>.size)
        _ = withUnsafeMutablePointer(to: &local) { $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { getsockname(s, $0, &largo) } }
        return withUnsafeBytes(of: local.sin_addr.s_addr) { Array($0) }
    }

    private func abrirUdp(_ puertoUdp: Int) -> Bool {
        let s = socket(AF_INET, SOCK_DGRAM, 0)
        if s < 0 { return false }
        var direccion = sockaddr_in()
        direccion.sin_family = sa_family_t(AF_INET)
        direccion.sin_port = in_port_t(UInt16(puertoUdp)).bigEndian
        direccion.sin_addr.s_addr = INADDR_ANY
        let r = withUnsafePointer(to: &direccion) { $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { bind(s, $0, socklen_t(MemoryLayout<sockaddr_in>.size)) } }
        if r != 0 {
            close(s)
            return false
        }
        udp = s
        return true
    }

    // Responde solo a quien ya conoce esta compu: el pedido lleva el comienzo de su huella.
    private func bucleUdp() {
        let esperado = Array(("TCHN?" + Datos.hex(huella).prefix(16)).utf8)
        let respuesta = Array("TCHN!\(puerto)".utf8)
        let s = udp
        var buffer = [UInt8](repeating: 0, count: 512)
        while !apagando {
            var origen = sockaddr_storage()
            var largo = socklen_t(MemoryLayout<sockaddr_storage>.size)
            let n = withUnsafeMutablePointer(to: &origen) {
                $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { recvfrom(s, &buffer, buffer.count, 0, $0, &largo) }
            }
            if n < 0 {
                if errno == EINTR { continue }
                return
            }
            if Array(buffer[0..<n]) == esperado {
                _ = withUnsafePointer(to: &origen) {
                    $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { sendto(s, respuesta, respuesta.count, 0, $0, largo) }
                }
            }
        }
    }

    private func direccion(_ c: NWConnection) -> String {
        if case let .hostPort(host, _) = c.endpoint { return "\(host)" }
        return "?"
    }

    private func aceptar(_ c: NWConnection) {
        let d = direccion(c)
        if apagando || !entrar(d) {
            c.cancel()
            return
        }
        if cupos.wait(timeout: .now()) == .timedOut {
            salir(d)
            c.cancel()
            return
        }
        let hilo = Thread { [weak self] in
            let canal = Canal(c)
            self?.atender(canal)
            canal.cerrar()
            self?.salir(d)
            self?.cupos.signal()
        }
        hilo.start()
    }

    // Una sola máquina no puede ocupar todos los lugares.
    private func entrar(_ d: String) -> Bool {
        cerrojoDirecciones.lock()
        defer { cerrojoDirecciones.unlock() }
        let n = porDireccion[d] ?? 0
        if n >= Servidor.maximoPorDireccion { return false }
        porDireccion[d] = n + 1
        return true
    }

    private func salir(_ d: String) {
        cerrojoDirecciones.lock()
        defer { cerrojoDirecciones.unlock() }
        let n = (porDireccion[d] ?? 1) - 1
        porDireccion[d] = n == 0 ? nil : n
    }

    private func atender(_ canal: Canal) {
        // Sin este plazo, mandar un byte cada tanto alcanza para ocupar un lugar para siempre.
        let plazo = DispatchTime.now() + Servidor.plazoCabecera
        guard canal.abrir(hasta: plazo), let texto = canal.leerCabecera(maximo: Servidor.maximoCabecera, hasta: plazo) else { return }
        var lineas = texto.components(separatedBy: "\r\n")
        let primera = lineas.removeFirst().split(separator: " ")
        var cabeceras: [String: String] = [:]
        for linea in lineas {
            guard let i = linea.firstIndex(of: ":"), i != linea.startIndex else { continue }
            cabeceras[linea[..<i].trimmingCharacters(in: .whitespaces).lowercased()] = linea[linea.index(after: i)...].trimmingCharacters(in: .whitespaces)
        }
        if primera.count < 2 {
            responder(canal, 400, "{}")
            return
        }
        let ruta = primera[0] + " " + primera[1]
        if ruta == "POST /vincular" { vincular(canal, cabeceras) }
        else if autorizado(cabeceras) == nil { responder(canal, 401, "{}") }
        else if ruta == "GET /hola" { responder(canal, 200, "{\"nombre\":\"" + Servidor.json(Datos.nombreEquipo) + "\"}") }
        else if ruta == "POST /enviar" { enviar(canal, cabeceras) }
        else if ruta == "POST /desvincular" { desvincular(canal, cabeceras) }
        else { responder(canal, 404, "{}") }
    }

    private func responder(_ canal: Canal, _ codigo: Int, _ json: String) {
        let cuerpo = Data(json.utf8)
        var datos = Data("HTTP/1.1 \(codigo) X\r\nContent-Type: application/json\r\nContent-Length: \(cuerpo.count)\r\nConnection: close\r\n\r\n".utf8)
        datos.append(cuerpo)
        canal.escribir(datos, final: true)
    }

    static func json(_ texto: String) -> String {
        texto.replacingOccurrences(of: "\\", with: "\\\\").replacingOccurrences(of: "\"", with: "\\\"")
            .replacingOccurrences(of: "\n", with: " ").replacingOccurrences(of: "\r", with: " ")
    }

    private static func iguales(_ a: [UInt8], _ b: [UInt8]) -> Bool {
        if a.count != b.count { return false }
        var diferencia: UInt8 = 0
        for i in 0..<a.count { diferencia |= a[i] ^ b[i] }
        return diferencia == 0
    }

    private func autorizado(_ cabeceras: [String: String]) -> Dispositivo? {
        guard let valor = cabeceras["authorization"], valor.hasPrefix("Bearer ") else { return nil }
        let hash = Array(Datos.hashToken(String(valor.dropFirst(7))).utf8)
        Datos.cerrojo.lock()
        defer { Datos.cerrojo.unlock() }
        var hallado: Dispositivo?
        for d in Datos.dispositivos where Servidor.iguales(hash, Array(d.huellaToken.utf8)) { hallado = d }
        return hallado
    }

    private func desvincular(_ canal: Canal, _ cabeceras: [String: String]) {
        guard let d = autorizado(cabeceras) else { return }
        Datos.cerrojo.lock()
        Datos.dispositivos.removeAll { $0.id == d.id }
        Datos.cerrojo.unlock()
        Datos.guardarDispositivos()
        responder(canal, 200, "{}")
    }

    private func vincular(_ canal: Canal, _ cabeceras: [String: String]) {
        var secreto = cabeceras["x-secreto"]
        var agotado = false
        cerrojoVinculo.lock()
        if let esperado = secretoVinculo, let s = secreto, Servidor.iguales(Array(s.utf8), Array(Datos.hex(esperado).utf8)) {
            secretoVinculo = nil  // de un solo uso
        } else {
            if secretoVinculo != nil {
                intentosVinculo += 1
                if intentosVinculo >= Servidor.maximoIntentos {
                    secretoVinculo = nil  // demasiados intentos: el QR deja de valer
                    agotado = true
                }
            }
            secreto = nil
        }
        cerrojoVinculo.unlock()
        if agotado { secretoAgotado?() }
        if secreto == nil {
            responder(canal, 401, "{}")
            return
        }
        let crudo = cabeceras["x-dispositivo"] ?? ""
        var nombre = String(String.UnicodeScalarView((crudo.removingPercentEncoding ?? crudo).unicodeScalars.filter { !CharacterSet.controlCharacters.contains($0) }))
        nombre = String(nombre.prefix(60))
        if nombre.isEmpty { nombre = "Android" }
        let token = Data(Datos.azar(32)).base64EncodedString().replacingOccurrences(of: "+", with: "-")
            .replacingOccurrences(of: "/", with: "_").replacingOccurrences(of: "=", with: "")
        let nuevo = Dispositivo(id: UUID().uuidString.replacingOccurrences(of: "-", with: "").lowercased(), nombre: nombre, huellaToken: Datos.hashToken(token))
        Datos.cerrojo.lock()
        Datos.dispositivos.append(nuevo)
        Datos.cerrojo.unlock()
        Datos.guardarDispositivos()
        responder(canal, 200, "{\"token\":\"\(token)\",\"huella\":\"\(Datos.hex(huella))\",\"nombre\":\"\(Servidor.json(Datos.nombreEquipo))\"}")
        vinculado?(nuevo)
    }

    private func enviar(_ canal: Canal, _ cabeceras: [String: String]) {
        guard let crudo = cabeceras["content-length"], let largo = Int64(crudo), largo >= 0 else {
            responder(canal, 411, "{}")
            return
        }
        let clase = cabeceras["x-clase"]
        let demorado = cabeceras["x-demorado"] != nil
        if clase == "texto" {
            if largo > Servidor.maximoTexto {
                responder(canal, 413, "{}")
                return
            }
            var datos = Data()
            guard canal.leerCuerpo(largo: largo, esperaPorTrozo: Servidor.esperaLectura, { datos.append($0) }) else { return }
            responder(canal, 200, "{\"ok\":true}")
            llegada?(Recibido(texto: String(decoding: datos, as: UTF8.self), demorado: demorado))
            return
        }

        let carpeta = Datos.recibidos
        try? FileManager.default.createDirectory(at: carpeta, withIntermediateDirectories: true)
        let libre = (try? carpeta.resourceValues(forKeys: [.volumeAvailableCapacityForImportantUsageKey]).volumeAvailableCapacityForImportantUsage) ?? 0
        if largo + Servidor.margenDisco > libre {
            responder(canal, 507, "{}")
            return
        }
        let parcial = carpeta.appendingPathComponent(".recibiendo_" + UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: parcial) }
        guard FileManager.default.createFile(atPath: parcial.path, contents: nil), let archivo = try? FileHandle(forWritingTo: parcial) else { return }
        let completo = (try? canal.leerCuerpo(largo: largo, esperaPorTrozo: Servidor.esperaLectura) { try archivo.write(contentsOf: $0) }) ?? false
        try? archivo.close()
        guard completo else { return }
        let final = Servidor.rutaLibre(Servidor.nombreSeguro(cabeceras["x-nombre"]), en: carpeta)
        guard (try? FileManager.default.moveItem(at: parcial, to: final)) != nil else { return }
        Servidor.marcarDeInternet(final)
        responder(canal, 200, "{\"ok\":true}")
        llegada?(Recibido(ruta: final, demorado: demorado))
    }

    static let reservados: Set<String> = ["CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
                                          "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"]
    // Los mismos que prohíbe Windows: así un archivo se llama igual en las dos compus.
    static let invalidos = Set("\"<>|:*?\\/".unicodeScalars)

    static func nombreSeguro(_ crudo: String?) -> String {
        let decodificado = crudo.map { $0.removingPercentEncoding ?? $0 } ?? ""
        // Los invisibles pueden disfrazar la extensión.
        var nombre = String(String.UnicodeScalarView(decodificado.unicodeScalars.filter { $0.properties.generalCategory != .format }))
        nombre = nombre.replacingOccurrences(of: "\\", with: "/")
        if let barra = nombre.lastIndex(of: "/") { nombre = String(nombre[nombre.index(after: barra)...]) }
        nombre = String(String.UnicodeScalarView(nombre.unicodeScalars.map { invalidos.contains($0) || $0.value < 32 ? "_" : $0 }))
        nombre = nombre.trimmingCharacters(in: CharacterSet(charactersIn: " ."))
        if nombre.isEmpty {
            let f = DateFormatter()
            f.dateFormat = "yyyyMMdd_HHmmss"
            nombre = "archivo_" + f.string(from: Date())
        }
        if reservados.contains(partir(nombre).0.uppercased()) { nombre = "_" + nombre }
        // 120 como en Windows, y nunca más de 255 bytes, que es lo que acepta APFS.
        if nombre.count > 120 || nombre.utf8.count > 240 {
            let ext = partir(nombre).1
            let e = ext.count > 20 ? "" : ext
            var corto = String(nombre.prefix(120 - e.count))
            while (corto + e).utf8.count > 240 { corto.removeLast() }
            nombre = corto + e
        }
        return nombre
    }

    // Como Path.GetFileNameWithoutExtension y Path.GetExtension de .NET: la extensión incluye el punto.
    static func partir(_ nombre: String) -> (String, String) {
        guard let punto = nombre.lastIndex(of: "."), punto != nombre.startIndex else { return (nombre, "") }
        return (String(nombre[..<punto]), String(nombre[punto...]))
    }

    static func rutaLibre(_ nombre: String, en carpeta: URL) -> URL {
        var ruta = carpeta.appendingPathComponent(nombre)
        let (base, ext) = partir(nombre)
        var n = 2
        while FileManager.default.fileExists(atPath: ruta.path) {
            ruta = carpeta.appendingPathComponent("\(base)_\(n)\(ext)")
            n += 1
        }
        return ruta
    }

    // macOS trata lo recibido como bajado de internet: Gatekeeper revisa un programa antes de abrirlo.
    static func marcarDeInternet(_ ruta: URL) {
        let propiedades: [String: Any] = [kLSQuarantineTypeKey as String: kLSQuarantineTypeOtherDownload as String,
                                          kLSQuarantineAgentNameKey as String: Marca.visible]
        try? (ruta as NSURL).setResourceValue(propiedades, forKey: .quarantinePropertiesKey)
    }
}
