"""Firma lo que dice version.json con una llave que no está en el sitio: quien controle la web no puede hacer pasar otro programa.

La llave vive en ~/.tachan/actualizar.pem, junto a la de Android. La parte pública va adentro del programa (pc/Actualizador.cs).
"""
import base64
import sys
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

LLAVE = Path.home() / ".tachan" / "actualizar.pem"


def firmar(codigo, sha256, llave=LLAVE):
    """Cubre el número de versión y el hash del exe, para que no se pueda hacer pasar una versión vieja por nueva."""
    privada = serialization.load_pem_private_key(Path(llave).read_bytes(), None)
    return base64.b64encode(privada.sign(f"{codigo}\n{sha256}".encode(), padding.PKCS1v15(), hashes.SHA256())).decode()


def crear(ruta=LLAVE):
    """Solo una vez: cambiarla deja afuera a los programas ya instalados. Devuelve la parte pública para pc/Actualizador.cs."""
    if Path(ruta).exists():
        sys.exit("la llave ya existe")
    privada = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    Path(ruta).write_bytes(privada.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    n = privada.public_key().public_numbers().n
    modulo = base64.b64encode(n.to_bytes((n.bit_length() + 7) // 8, "big")).decode()
    return f"<RSAKeyValue><Modulus>{modulo}</Modulus><Exponent>AQAB</Exponent></RSAKeyValue>"
