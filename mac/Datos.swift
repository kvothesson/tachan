import CryptoKit
import Foundation
import Security
import SystemConfiguration

final class Dispositivo {
    let id: String
    let nombre: String
    let huellaToken: String  // solo el hash: el token vive en el celu

    init(id: String, nombre: String, huellaToken: String) {
        self.id = id
        self.nombre = nombre
        self.huellaToken = huellaToken
    }
}

// Ajustes, celus vinculados y certificado. TACHAN_DATOS aísla las pruebas de los datos reales.
enum Datos {
    static let entorno = ProcessInfo.processInfo.environment
    static let esPrueba = entorno["TACHAN_DATOS"] != nil
    static let carpeta: URL = entorno["TACHAN_DATOS"].map { URL(fileURLWithPath: $0, isDirectory: true) }
        ?? FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0].appendingPathComponent(Marca.nombre, isDirectory: true)

    static var rutaAjustes: URL { carpeta.appendingPathComponent("ajustes.txt") }
    static var rutaDispositivos: URL { carpeta.appendingPathComponent("dispositivos.txt") }
    static var rutaIdentidad: URL { carpeta.appendingPathComponent("identidad.p12") }

    static var pegarSolo = false
    static var sonido = true
    static var dispositivos: [Dispositivo] = []
    static let cerrojo = NSLock()

    static var recibidos: URL {
        if esPrueba { return carpeta.appendingPathComponent("recibidos", isDirectory: true) }
        return FileManager.default.urls(for: .downloadsDirectory, in: .userDomainMask)[0].appendingPathComponent(Marca.nombre, isDirectory: true)
    }

    // El nombre que ve el celu. En las pruebas se puede fijar con TACHAN_NOMBRE, así no sale el nombre real en una captura.
    static var nombreEquipo: String {
        if esPrueba, let n = entorno["TACHAN_NOMBRE"] { return n }
        let nombre = (SCDynamicStoreCopyComputerName(nil, nil) as String?) ?? Host.current().localizedName ?? "Mac"
        return String(nombre.prefix(40))
    }

    static func cargar() {
        try? FileManager.default.createDirectory(at: carpeta, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        if let texto = try? String(contentsOf: rutaAjustes, encoding: .utf8) {
            for linea in texto.components(separatedBy: .newlines) {
                if linea == "pegar=1" { pegarSolo = true }
                if linea == "sonido=0" { sonido = false }
            }
        }
        if let texto = try? String(contentsOf: rutaDispositivos, encoding: .utf8) {
            dispositivos = texto.components(separatedBy: .newlines).map { $0.components(separatedBy: "\t") }.filter { $0.count == 3 }
                .map { Dispositivo(id: $0[0], nombre: $0[1], huellaToken: $0[2]) }
        }
    }

    static func guardarAjustes() {
        escribir("pegar=\(pegarSolo ? 1 : 0)\nsonido=\(sonido ? 1 : 0)\n", en: rutaAjustes)
    }

    static func guardarDispositivos() {
        cerrojo.lock()
        let texto = dispositivos.map { $0.id + "\t" + $0.nombre.replacingOccurrences(of: "\t", with: " ") + "\t" + $0.huellaToken + "\n" }.joined()
        cerrojo.unlock()
        escribir(texto, en: rutaDispositivos)
    }

    static func escribir(_ texto: String, en ruta: URL) {
        try? Data(texto.utf8).write(to: ruta, options: .atomic)
        try? FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: ruta.path)
    }

    // La identidad de esta compu: el celu la fija al vincular y después no confía en otra.
    // macOS solo da una identidad TLS desde el llavero o desde un .p12. Se usa el .p12, cargado solo en memoria:
    // así el llavero no pregunta nada cada vez que cambia la firma de la app.
    static func identidad() throws -> SecIdentity {
        if !FileManager.default.fileExists(atPath: rutaIdentidad.path) { try crearIdentidad() }
        var items: CFArray?
        let opciones: [String: Any] = [kSecImportExportPassphrase as String: clave, kSecImportToMemoryOnly as String: true]
        let estado = SecPKCS12Import(try Data(contentsOf: rutaIdentidad) as CFData, opciones as CFDictionary, &items)
        guard estado == errSecSuccess, let lista = items as? [[String: Any]], let primera = lista.first,
              let identidad = primera[kSecImportItemIdentity as String] else {
            throw NSError(domain: "Tachan", code: Int(estado), userInfo: [NSLocalizedDescriptionKey: "no se pudo leer la identidad"])
        }
        return identidad as! SecIdentity
    }

    // El .p12 queda solo para este usuario (0600). Su clave no protege nada: está para que macOS lo acepte.
    static let clave = "tachan"

    // RSA 2048, SHA-256, CN=Tachan, 30 años: lo mismo que la compu Windows. El openssl de macOS viene con el sistema.
    static func crearIdentidad() throws {
        let temporal = carpeta.appendingPathComponent(".nueva_" + UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: temporal, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        defer { try? FileManager.default.removeItem(at: temporal) }
        func openssl(_ argumentos: [String]) throws {
            let p = Process()
            p.executableURL = URL(fileURLWithPath: "/usr/bin/openssl")
            p.arguments = argumentos
            p.currentDirectoryURL = temporal
            p.standardOutput = FileHandle.nullDevice
            p.standardError = FileHandle.nullDevice
            try p.run()
            p.waitUntilExit()
            if p.terminationStatus != 0 { throw NSError(domain: "Tachan", code: Int(p.terminationStatus)) }
        }
        try openssl(["req", "-x509", "-newkey", "rsa:2048", "-sha256", "-days", "10958", "-nodes", "-subj", "/CN=" + Marca.nombre,
                     "-keyout", "clave.pem", "-out", "certificado.pem"])
        try openssl(["pkcs12", "-export", "-inkey", "clave.pem", "-in", "certificado.pem", "-out", "identidad.p12", "-passout", "pass:" + clave])
        let p12 = temporal.appendingPathComponent("identidad.p12")
        try FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: p12.path)
        try FileManager.default.moveItem(at: p12, to: rutaIdentidad)
    }

    static func huella(_ identidad: SecIdentity) -> [UInt8] {
        var certificado: SecCertificate?
        SecIdentityCopyCertificate(identidad, &certificado)
        return Array(SHA256.hash(data: SecCertificateCopyData(certificado!) as Data))
    }

    static func hex(_ datos: [UInt8]) -> String { datos.map { String(format: "%02x", $0) }.joined() }

    static func hashToken(_ token: String) -> String { hex(Array(SHA256.hash(data: Data(token.utf8)))) }

    static func azar(_ n: Int) -> [UInt8] {
        var bytes = [UInt8](repeating: 0, count: n)
        _ = SecRandomCopyBytes(kSecRandomDefault, n, &bytes)
        return bytes
    }
}

// Lo que trae el QR: dirección, secreto de un solo uso y el comienzo de la huella, en 22 bytes.
enum CodigoVinculo {
    static let alfabeto = Array("abcdefghijklmnopqrstuvwxyz234567")

    static func armar(ip: [UInt8], puerto: Int, secreto: [UInt8], huella: [UInt8]) -> String {
        var d = ip + [UInt8(puerto >> 8 & 255), UInt8(puerto & 255)] + secreto
        d += huella.prefix(10)
        var salida = ""
        var acumulado = 0, bits = 0
        for b in d {
            acumulado = (acumulado << 8) | Int(b)
            bits += 8
            while bits >= 5 {
                salida.append(alfabeto[(acumulado >> (bits - 5)) & 31])
                bits -= 5
            }
            acumulado &= (1 << bits) - 1
        }
        if bits > 0 { salida.append(alfabeto[(acumulado << (5 - bits)) & 31]) }
        return salida
    }
}
