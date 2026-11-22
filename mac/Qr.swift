import AppKit

// Generador de QR en modo byte, corrección M, versiones 1 a 9: el mismo de pc/Qr.cs, para que el lector del celu vea lo mismo.
final class Qr {
    static let eccPorBloque = [-1, 10, 16, 26, 18, 24, 16, 18, 22, 22]
    static let bloques = [-1, 1, 1, 1, 2, 2, 4, 4, 4, 5]

    let version: Int
    let lado: Int
    private var modulos: [[Bool]]
    private var funcion: [[Bool]]

    private init(version: Int) {
        self.version = version
        lado = version * 4 + 17
        modulos = Array(repeating: Array(repeating: false, count: lado), count: lado)
        funcion = modulos
    }

    func negro(_ x: Int, _ y: Int) -> Bool { modulos[y][x] }

    static func modulosCrudos(_ v: Int) -> Int {
        var r = (16 * v + 128) * v + 64
        if v >= 2 {
            let a = v / 7 + 2
            r -= (25 * a - 10) * a - 55
            if v >= 7 { r -= 36 }
        }
        return r
    }

    static func capacidad(_ v: Int) -> Int { modulosCrudos(v) / 8 - eccPorBloque[v] * bloques[v] }

    static func crear(_ texto: String) -> Qr? {
        let datos = Array(texto.utf8)
        var v = 1
        while v <= 9 && datos.count + 2 > capacidad(v) { v += 1 }
        if v > 9 { return nil }

        var bits: [Bool] = []
        func agregar(_ valor: Int, _ cuantos: Int) {
            if cuantos <= 0 { return }
            for i in stride(from: cuantos - 1, through: 0, by: -1) { bits.append((valor >> i) & 1 != 0) }
        }
        agregar(4, 4)
        agregar(datos.count, 8)
        for b in datos { agregar(Int(b), 8) }
        let capacidadBits = capacidad(v) * 8
        agregar(0, min(4, capacidadBits - bits.count))
        agregar(0, (8 - bits.count % 8) % 8)
        var relleno = 0xEC
        while bits.count < capacidadBits {
            agregar(relleno, 8)
            relleno ^= 0xEC ^ 0x11
        }
        var palabras = [UInt8](repeating: 0, count: capacidad(v))
        for i in 0..<bits.count where bits[i] { palabras[i >> 3] |= UInt8(1 << (7 - (i & 7))) }

        let qr = Qr(version: v)
        qr.dibujarFijos()
        qr.dibujarDatos(qr.conCorreccion(palabras))
        qr.elegirMascara()
        return qr
    }

    private func poner(_ x: Int, _ y: Int, _ negro: Bool) {
        modulos[y][x] = negro
        funcion[y][x] = true
    }

    private func dibujarFijos() {
        for i in 0..<lado {
            poner(6, i, i % 2 == 0)
            poner(i, 6, i % 2 == 0)
        }
        buscador(3, 3)
        buscador(lado - 4, 3)
        buscador(3, lado - 4)
        let pos = posicionesAlineacion()
        for i in 0..<pos.count {
            for j in 0..<pos.count where !(i == 0 && j == 0 || i == 0 && j == pos.count - 1 || i == pos.count - 1 && j == 0) {
                alineacion(pos[i], pos[j])
            }
        }
        formato(0)
        versionBits()
    }

    private func posicionesAlineacion() -> [Int] {
        if version == 1 { return [] }
        let cantidad = version / 7 + 2
        let paso = (version * 8 + cantidad * 3 + 5) / (cantidad * 4 - 4) * 2
        var r = [Int](repeating: 0, count: cantidad)
        r[0] = 6
        var p = lado - 7
        for i in stride(from: cantidad - 1, through: 1, by: -1) {
            r[i] = p
            p -= paso
        }
        return r
    }

    private func buscador(_ x: Int, _ y: Int) {
        for dy in -4...4 {
            for dx in -4...4 {
                let d = max(abs(dx), abs(dy))
                let xx = x + dx, yy = y + dy
                if xx >= 0 && xx < lado && yy >= 0 && yy < lado { poner(xx, yy, d != 2 && d != 4) }
            }
        }
    }

    private func alineacion(_ x: Int, _ y: Int) {
        for dy in -2...2 {
            for dx in -2...2 { poner(x + dx, y + dy, max(abs(dx), abs(dy)) != 1) }
        }
    }

    private func formato(_ mascara: Int) {
        let datos = mascara  // los bits de nivel M son 00
        var resto = datos
        for _ in 0..<10 { resto = (resto << 1) ^ ((resto >> 9) * 0x537) }
        let bits = (datos << 10 | resto) ^ 0x5412
        let b = { (i: Int) in (bits >> i) & 1 != 0 }
        for i in 0...5 { poner(8, i, b(i)) }
        poner(8, 7, b(6))
        poner(8, 8, b(7))
        poner(7, 8, b(8))
        for i in 9..<15 { poner(14 - i, 8, b(i)) }
        for i in 0..<8 { poner(lado - 1 - i, 8, b(i)) }
        for i in 8..<15 { poner(8, lado - 15 + i, b(i)) }
        poner(8, lado - 8, true)
    }

    private func versionBits() {
        if version < 7 { return }
        var resto = version
        for _ in 0..<12 { resto = (resto << 1) ^ ((resto >> 11) * 0x1F25) }
        let bits = version << 12 | resto
        for i in 0..<18 {
            let b = (bits >> i) & 1 != 0
            let a = lado - 11 + i % 3, c = i / 3
            poner(a, c, b)
            poner(c, a, b)
        }
    }

    private func conCorreccion(_ datos: [UInt8]) -> [UInt8] {
        let cantidad = Qr.bloques[version], ecc = Qr.eccPorBloque[version]
        let crudas = Qr.modulosCrudos(version) / 8
        let cortos = cantidad - crudas % cantidad
        let largoCorto = crudas / cantidad
        var bloques: [[UInt8]] = []
        let divisor = Qr.divisor(ecc)
        var k = 0
        for i in 0..<cantidad {
            let largoDatos = largoCorto - ecc + (i < cortos ? 0 : 1)
            let d = Array(datos[k..<min(datos.count, k + largoDatos)])
            k += largoDatos
            let e = Qr.resto(d, divisor)
            var b = [UInt8](repeating: 0, count: largoCorto + 1)
            for j in 0..<d.count { b[j] = d[j] }
            for j in 0..<ecc { b[largoCorto + 1 - ecc + j] = e[j] }
            bloques.append(b)
        }
        var salida: [UInt8] = []
        for i in 0...largoCorto {
            for j in 0..<cantidad where i != largoCorto - ecc || j >= cortos { salida.append(bloques[j][i]) }
        }
        return salida
    }

    private static func divisor(_ grado: Int) -> [UInt8] {
        var r = [UInt8](repeating: 0, count: grado)
        r[grado - 1] = 1
        var raiz: UInt8 = 1
        for _ in 0..<grado {
            for j in 0..<grado {
                r[j] = mult(r[j], raiz)
                if j + 1 < grado { r[j] ^= r[j + 1] }
            }
            raiz = mult(raiz, 2)
        }
        return r
    }

    private static func resto(_ datos: [UInt8], _ divisor: [UInt8]) -> [UInt8] {
        var r = [UInt8](repeating: 0, count: divisor.count)
        for b in datos {
            let factor = b ^ r[0]
            r.removeFirst()
            r.append(0)
            for i in 0..<r.count { r[i] ^= mult(divisor[i], factor) }
        }
        return r
    }

    private static func mult(_ x: UInt8, _ y: UInt8) -> UInt8 {
        var z = 0
        for i in stride(from: 7, through: 0, by: -1) {
            z = (z << 1) ^ ((z >> 7) * 0x11D)
            z ^= Int((y >> UInt8(i)) & 1) * Int(x)
        }
        return UInt8(z & 255)
    }

    private func dibujarDatos(_ datos: [UInt8]) {
        var i = 0
        var derecha = lado - 1
        while derecha >= 1 {
            if derecha == 6 { derecha = 5 }
            for vert in 0..<lado {
                for j in 0..<2 {
                    let x = derecha - j
                    let sube = ((derecha + 1) & 2) == 0
                    let y = sube ? lado - 1 - vert : vert
                    if !funcion[y][x] && i < datos.count * 8 {
                        modulos[y][x] = (datos[i >> 3] >> UInt8(7 - (i & 7))) & 1 != 0
                        i += 1
                    }
                }
            }
            derecha -= 2
        }
    }

    private func aplicarMascara(_ m: Int) {
        for y in 0..<lado {
            for x in 0..<lado {
                let invertir: Bool
                switch m {
                case 0: invertir = (x + y) % 2 == 0
                case 1: invertir = y % 2 == 0
                case 2: invertir = x % 3 == 0
                case 3: invertir = (x + y) % 3 == 0
                case 4: invertir = (x / 3 + y / 2) % 2 == 0
                case 5: invertir = x * y % 2 + x * y % 3 == 0
                case 6: invertir = (x * y % 2 + x * y % 3) % 2 == 0
                default: invertir = ((x + y) % 2 + x * y % 3) % 2 == 0
                }
                if !funcion[y][x] && invertir { modulos[y][x].toggle() }
            }
        }
    }

    private func elegirMascara() {
        var mejor = 0, menor = Int.max
        for m in 0..<8 {
            aplicarMascara(m)
            formato(m)
            let p = penalidad()
            if p < menor {
                menor = p
                mejor = m
            }
            aplicarMascara(m)
        }
        aplicarMascara(mejor)
        formato(mejor)
    }

    private func penalidad() -> Int {
        var total = 0
        for eje in 0..<2 {
            for a in 0..<lado {
                var corrida = 0, color = false, ventana = 0
                for b in 0..<lado {
                    let m = eje == 0 ? modulos[a][b] : modulos[b][a]
                    if b > 0 && m == color {
                        corrida += 1
                        if corrida == 5 { total += 3 } else if corrida > 5 { total += 1 }
                    } else {
                        color = m
                        corrida = 1
                    }
                    ventana = ((ventana << 1) | (m ? 1 : 0)) & 0x7FF
                    if b >= 10 && (ventana == 0x5D0 || ventana == 0x05D) { total += 40 }
                }
            }
        }
        var negros = 0
        for y in 0..<lado {
            for x in 0..<lado {
                if modulos[y][x] { negros += 1 }
                if x + 1 < lado && y + 1 < lado && modulos[y][x] == modulos[y][x + 1] && modulos[y][x] == modulos[y + 1][x] && modulos[y][x] == modulos[y + 1][x + 1] {
                    total += 3
                }
            }
        }
        let pasos = (abs(negros * 20 - lado * lado * 10) + lado * lado - 1) / (lado * lado) - 1
        return total + pasos * 10
    }

    // Píxeles exactos, sin suavizar: escala módulos por punto y un margen blanco alrededor.
    func imagen(escala: Int, margen: Int) -> NSBitmapImageRep {
        let px = (lado + margen * 2) * escala
        let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: px, pixelsHigh: px, bitsPerSample: 8, samplesPerPixel: 3,
                                   hasAlpha: false, isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
        let datos = rep.bitmapData!
        let fila = rep.bytesPerRow
        for y in 0..<px {
            for x in 0..<px {
                let mx = x / escala - margen, my = y / escala - margen
                let n = mx >= 0 && my >= 0 && mx < lado && my < lado && negro(mx, my)
                let v: UInt8 = n ? 0 : 255
                datos[y * fila + x * 3] = v
                datos[y * fila + x * 3 + 1] = v
                datos[y * fila + x * 3 + 2] = v
            }
        }
        return rep
    }
}
