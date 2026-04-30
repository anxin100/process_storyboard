import base64

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)


def main() -> int:
    priv = ed25519.Ed25519PrivateKey.generate()
    pub = priv.public_key()

    priv_raw = priv.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    pub_raw = pub.public_bytes(Encoding.Raw, PublicFormat.Raw)

    print("key_id 建议：K1")
    print(f"ED25519_PRIVATE_KEY_B64={base64.b64encode(priv_raw).decode('ascii')}")
    print(f"ED25519_PUBLIC_KEY_B64={base64.b64encode(pub_raw).decode('ascii')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

