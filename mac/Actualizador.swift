import CryptoKit
import Foundation
import Security

// Solo se conecta a internet si lo pedís: Tachán no consulta nada por su cuenta.
enum Actualizador {
    static var prueba: String? { Datos.entorno["TACHAN_ACTUALIZAR"] }
    static var base: String { prueba ?? "https://kvothesson.com/tachan/" }
    static let archivo = "actualizar-Tachan-mac.zip"

    // La app nueva sale de la release en GitHub, en un archivo aparte del que baja el botón de la web.
    // GitHub cuenta cuántas veces se baja: así sabemos cuántos la siguen usando, sin que Tachán mande nada.
    static func descarga(_ nombre: String) -> URL? {
        if let p = prueba { return URL(string: p + archivo) }
        if nombre.range(of: #"^\d+(\.\d+)*$"#, options: .regularExpression) != nil {
            return URL(string: "https://github.com/kvothesson/tachan/releases/download/v\(nombre)/\(archivo)")
        }
        return URL(string: base + "Tachan-mac.zip")
    }

    static func bajar(_ url: URL) throws -> Data {
        let sesion = URLSession(configuration: .ephemeral)
        let listo = DispatchSemaphore(value: 0)
        var resultado: Data?
        var falla: Error?
        sesion.dataTask(with: URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 30)) { d, r, e in
            if let h = r as? HTTPURLResponse, h.statusCode == 200 { resultado = d } else { falla = e ?? URLError(.badServerResponse) }
            listo.signal()
        }.resume()
        listo.wait()
        sesion.finishTasksAndInvalidate()
        if let d = resultado { return d }
        throw falla!
    }

    enum Falla: Error { case datos, firma, descarga }

    static func buscar(_ avisar: @escaping (String) -> Void) {
        Thread {
            do {
                let crudo = try bajar(URL(string: base + "version.json?t=\(Int(Date().timeIntervalSince1970 * 1000))")!)
                guard let datos = try JSONSerialization.jsonObject(with: crudo) as? [String: Any], let codigo = datos["codigo"] as? Int else { throw Falla.datos }
                if codigo <= VersionApp.codigo {
                    avisar(Textos.t("ultima") + ": " + VersionApp.nombre)
                    return
                }
                guard let esperado = datos["mac_sha256"] as? String, esperado.range(of: "^[0-9a-f]{64}$", options: .regularExpression) != nil,
                      let firma = datos["firma_mac"] as? String, let nombre = datos["nombre"] as? String else { throw Falla.datos }
                // El hash solo descubre una descarga rota: quien controle el sitio lo cambia junto con el zip. La firma, no.
                if !firmaValida(codigo: codigo, sha256: esperado, firma: firma) { throw Falla.firma }
                guard let url = descarga(nombre) else { throw Falla.datos }
                let zip = try bajar(url)
                if Datos.hex(Array(SHA256.hash(data: zip))) != esperado { throw Falla.descarga }
                let carpeta = FileManager.default.temporaryDirectory.appendingPathComponent("\(Marca.nombre)-\(UUID().uuidString)", isDirectory: true)
                try FileManager.default.createDirectory(at: carpeta, withIntermediateDirectories: true)
                let rutaZip = carpeta.appendingPathComponent(archivo)
                try zip.write(to: rutaZip)
                let ditto = Process()
                ditto.executableURL = URL(fileURLWithPath: "/usr/bin/ditto")
                ditto.arguments = ["-x", "-k", rutaZip.path, carpeta.path]
                try ditto.run()
                ditto.waitUntilExit()
                let app = carpeta.appendingPathComponent(Marca.nombre + ".app", isDirectory: true)
                guard ditto.terminationStatus == 0, FileManager.default.fileExists(atPath: Instalador.ejecutable(app).path) else { throw Falla.descarga }
                avisar(Textos.t("actualizando"))
                // La versión nueva cierra esta y toma su lugar, igual que si la abrieras a mano.
                if !Instalador.abrir(app, argumentos: []) { throw Falla.descarga }
            } catch {
                avisar(Textos.t("sinred"))
            }
        }.start()
    }

    // La parte pública de ~/.tachan/actualizar.pem, la misma que usa Windows (sale de pc/Actualizador.cs).
    static func llave() -> SecKey? {
        guard let n = Data(base64Encoded: LlaveActualizar.modulo), let e = Data(base64Encoded: LlaveActualizar.exponente) else { return nil }
        func entero(_ d: Data) -> Data {
            var v = [UInt8](d)
            if let primero = v.first, primero & 0x80 != 0 { v.insert(0, at: 0) }
            return der(0x02, Data(v))
        }
        let publica = der(0x30, entero(n) + entero(e))
        let atributos: [String: Any] = [kSecAttrKeyType as String: kSecAttrKeyTypeRSA, kSecAttrKeyClass as String: kSecAttrKeyClassPublic]
        return SecKeyCreateWithData(publica as CFData, atributos as CFDictionary, nil)
    }

    static func der(_ etiqueta: UInt8, _ contenido: Data) -> Data {
        var d = Data([etiqueta])
        let n = contenido.count
        if n < 128 { d.append(UInt8(n)) }
        else {
            var bytes: [UInt8] = []
            var resto = n
            while resto > 0 {
                bytes.insert(UInt8(resto & 255), at: 0)
                resto >>= 8
            }
            d.append(0x80 | UInt8(bytes.count))
            d.append(contentsOf: bytes)
        }
        d.append(contenido)
        return d
    }

    // Cubre el número de versión y el hash del zip, para que no se pueda hacer pasar una versión vieja por nueva.
    static func firmaValida(codigo: Int, sha256: String, firma: String) -> Bool {
        guard let k = llave(), let f = Data(base64Encoded: firma) else { return false }
        return SecKeyVerifySignature(k, .rsaSignatureMessagePKCS1v15SHA256, Data("\(codigo)\n\(sha256)".utf8) as CFData, f as CFData, nil)
    }
}
