import AppKit

// Los textos salen de pc/Marca.cs (los copia mac/compilar.py). Acá solo van los que en Mac se dicen distinto.
enum Textos {
    static let mac: [String: [String: String]] = [
        "es": ["inicio": "Abrir al iniciar sesión", "pegar_permiso": "Para pegar solo, permití Tachán en Accesibilidad."],
        "en": ["inicio": "Open at login", "pegar_permiso": "To paste automatically, allow Tachán in Accessibility."],
        "pt": ["inicio": "Abrir ao iniciar sessão", "pegar_permiso": "Para colar automaticamente, permita o Tachán em Acessibilidade."],
        "fr": ["inicio": "Ouvrir à l'ouverture de session", "pegar_permiso": "Pour coller automatiquement, autorisez Tachán dans Accessibilité."],
        "de": ["inicio": "Beim Anmelden öffnen", "pegar_permiso": "Zum automatischen Einfügen erlaube Tachán unter Bedienungshilfen."],
        "it": ["inicio": "Apri al login", "pegar_permiso": "Per incollare automaticamente, consenti Tachán in Accessibilità."],
    ]

    static let idioma: String = {
        let preferido = String((Locale.preferredLanguages.first ?? "en").prefix(2))
        return textosPc[preferido] != nil ? preferido : "en"
    }()

    static func t(_ clave: String) -> String {
        mac[idioma]?[clave] ?? textosPc[idioma]?[clave] ?? textosPc["en"]?[clave] ?? clave
    }
}

// Siempre de noche, con cualquier tema de macOS. Los valores salen de pc/marca.json.
enum Tema {
    static var acento: NSColor { Colores.accent }
    static var ok: NSColor { Colores.ok }
    static var suelo: NSColor { Colores.ground }
    static var fondo: NSColor { Colores.surface }
    static var fondo2: NSColor { Colores.surfaceRaised }
    static var texto: NSColor { Colores.ink }
    static var tenue: NSColor { Colores.muted }
    static let apariencia = NSAppearance(named: .darkAqua)

    // Íconos en una grilla de 24, con el eje y hacia abajo: los mismos trazos que pc/Aviso.cs.
    static func icono(_ cual: String, en caja: NSRect, color: NSColor, grosor: CGFloat = 2) {
        guard let g = NSGraphicsContext.current else { return }
        g.saveGraphicsState()
        let t = NSAffineTransform()
        t.translateX(by: caja.minX, yBy: caja.minY)
        t.scaleX(by: caja.width / 24, yBy: caja.height / 24)
        t.concat()
        color.setStroke()
        func linea(_ puntos: [(CGFloat, CGFloat)], cerrar: Bool = false) {
            let p = NSBezierPath()
            p.lineWidth = grosor
            p.lineCapStyle = .round
            p.lineJoinStyle = .round
            p.move(to: NSPoint(x: puntos[0].0, y: puntos[0].1))
            for q in puntos.dropFirst() { p.line(to: NSPoint(x: q.0, y: q.1)) }
            if cerrar { p.close() }
            p.stroke()
        }
        switch cual {
        case "copiar":
            let c = NSBezierPath(roundedRect: NSRect(x: 9, y: 9, width: 11, height: 11), xRadius: 2.5, yRadius: 2.5)
            c.lineWidth = grosor
            c.stroke()
            linea([(15, 5.5), (14, 4), (5.5, 4), (4, 5.5), (4, 14), (5.5, 15)])
        case "carpeta":
            linea([(3.5, 6), (9, 6), (11, 8.5), (20.5, 8.5), (20.5, 19), (3.5, 19)], cerrar: true)
        case "abrir":
            linea([(9, 5), (5, 5), (5, 19), (19, 19), (19, 15)])
            linea([(13, 5), (19, 5), (19, 11)])
            linea([(19, 5), (11, 13)])
        case "ok":
            linea([(5, 12.5), (9.5, 17), (19, 7.5)])
        case "reloj":
            let c = NSBezierPath(ovalIn: NSRect(x: 4, y: 4, width: 16, height: 16))
            c.lineWidth = grosor
            c.stroke()
            linea([(12, 7.5), (12, 12), (15, 14)])
        default:
            break
        }
        g.restoreGraphicsState()
    }
}

// El ícono de la app: la flecha en arco, recortada por el hexágono del cristal. Los trazos de pc/compilar.py.
enum Icono {
    static func dibujar(lado: CGFloat, plantilla: Bool) {
        let u = lado / 24
        // Dibuja con el eje y hacia abajo, como PIL.
        let pt = { (x: CGFloat, y: CGFloat) in NSPoint(x: x * u, y: lado - y * u) }
        let hexagono = NSBezierPath()
        hexagono.move(to: pt(12, 0.4))
        for (x, y) in [(22.2, 6.2), (22.2, 17.8), (12, 23.6), (1.8, 17.8), (1.8, 6.2)] as [(CGFloat, CGFloat)] { hexagono.line(to: pt(x, y)) }
        hexagono.close()
        (plantilla ? NSColor.black : Colores.accent).setFill()
        hexagono.fill()

        let chico = { (x: CGFloat, y: CGFloat) in pt(12 + (x - 12) * 0.68, 12 + (y - 10.5) * 0.68) }
        let trazo = NSBezierPath()
        trazo.lineWidth = max(2 * u, plantilla ? 1.6 : 2)
        trazo.lineCapStyle = .round
        trazo.lineJoinStyle = .round
        for i in 0...24 {
            let t = CGFloat(i) / 24
            let p = chico(4.5 + 15 * t, 18.5 - 13 * (1 - (1 - t) * (1 - t)))
            if i == 0 { trazo.move(to: p) } else { trazo.line(to: p) }
        }
        trazo.move(to: chico(15, 2.8))
        trazo.line(to: chico(19.7, 5.8))
        trazo.line(to: chico(17, 11))
        if plantilla {
            // En la barra de menú el trazo se recorta: macOS pinta la plantilla con el color de la barra.
            NSGraphicsContext.current?.compositingOperation = .clear
            NSColor.black.setStroke()
        } else {
            Colores.onAccent.setStroke()
        }
        trazo.stroke()
        NSGraphicsContext.current?.compositingOperation = .sourceOver
    }

    static func barra() -> NSImage {
        let imagen = NSImage(size: NSSize(width: 18, height: 18), flipped: false) { _ in
            dibujar(lado: 18, plantilla: true)
            return true
        }
        imagen.isTemplate = true
        return imagen
    }

    static func app(_ lado: CGFloat) -> NSImage {
        NSImage(size: NSSize(width: lado, height: lado), flipped: false) { _ in
            dibujar(lado: lado, plantilla: false)
            return true
        }
    }

    // Para mac/compilar.py: el juego de PNG que iconutil convierte en Tachan.icns.
    static func guardarJuego(_ carpeta: String) {
        try? FileManager.default.createDirectory(atPath: carpeta, withIntermediateDirectories: true)
        // Hasta 256: más grande casi no se ve y el ícono pesaría cinco veces más.
        for (base, doble) in [(16, 1), (16, 2), (32, 1), (32, 2), (128, 1), (128, 2), (256, 1)] {
            do {
                let px = base * doble
                let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: px, pixelsHigh: px, bitsPerSample: 8, samplesPerPixel: 4,
                                           hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
                NSGraphicsContext.saveGraphicsState()
                NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
                // El hexágono ocupa casi todo el lado, como en el .ico de Windows; macOS deja algo de aire alrededor.
                let margen = CGFloat(px) * 0.06
                let t = NSAffineTransform()
                t.translateX(by: margen, yBy: margen)
                t.concat()
                dibujar(lado: CGFloat(px) - margen * 2, plantilla: false)
                NSGraphicsContext.restoreGraphicsState()
                let nombre = "icon_\(base)x\(base)" + (doble == 2 ? "@2x" : "") + ".png"
                try? rep.representation(using: .png, properties: [:])?.write(to: URL(fileURLWithPath: carpeta).appendingPathComponent(nombre))
            }
        }
    }
}

enum Sonido {
    static let datos = sintetizar()
    static var reproductor: NSSound? = NSSound(data: datos)

    static func sonar() {
        guard Datos.sonido, let r = reproductor else { return }
        r.stop()
        r.play()
    }

    static func guardar(_ ruta: URL) { try? datos.write(to: ruta) }

    // Suave como una marimba: un ta grave y corto, y un chán de dos notas que se apaga solo. Igual que en Windows.
    static func nota(_ segundos: Double, _ inicio: Double, _ duracion: Double, _ tono: Double, _ caida: Double) -> Double {
        let s = segundos - inicio
        if s < 0 || s >= duracion { return 0 }
        let ataque = min(1, s / 0.012)
        let final = min(1, (duracion - s) / 0.06)
        let onda = sin(2 * .pi * tono * s) + 0.08 * sin(4 * .pi * tono * s)
        return onda / 1.08 * ataque * final * exp(-s * caida)
    }

    static func sintetizar() -> Data {
        let frecuencia = 44100
        let muestras = Int(Double(frecuencia) * 0.45)
        var d = Data()
        func u32(_ v: Int) { withUnsafeBytes(of: UInt32(v).littleEndian) { d.append(contentsOf: $0) } }
        func u16(_ v: Int) { withUnsafeBytes(of: UInt16(v).littleEndian) { d.append(contentsOf: $0) } }
        d.append(contentsOf: Array("RIFF".utf8)); u32(36 + muestras * 2)
        d.append(contentsOf: Array("WAVEfmt ".utf8)); u32(16); u16(1); u16(1); u32(frecuencia); u32(frecuencia * 2); u16(2); u16(16)
        d.append(contentsOf: Array("data".utf8)); u32(muestras * 2)
        for i in 0..<muestras {
            let s = Double(i) / Double(frecuencia)
            let onda = nota(s, 0, 0.09, 392.00, 14) + nota(s, 0.10, 0.35, 523.25, 8) + 0.5 * nota(s, 0.10, 0.35, 659.25, 10)
            withUnsafeBytes(of: Int16(truncatingIfNeeded: Int(onda * 5200)).littleEndian) { d.append(contentsOf: $0) }
        }
        return d
    }
}
