import os, json, getpass, base64, pathlib
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

STORE = "secrets.json"

def _derive_key(password: bytes, salt: bytes) -> bytes:
    kdf = Scrypt(salt=salt, length=32, n=2**14, r=8, p=1)
    return kdf.derive(password)

def save_secret(name: str, secret: str, password: str):
    salt = os.urandom(16)
    key = _derive_key(password.encode(), salt)
    aes = AESGCM(key)
    nonce = os.urandom(12)
    ct = aes.encrypt(nonce, secret.encode(), None)
    rec = {"salt": base64.b64encode(salt).decode(), "nonce": base64.b64encode(nonce).decode(), "ct": base64.b64encode(ct).decode()}
    store = {}
    if os.path.exists(STORE):
        store = json.loads(open(STORE,"r").read())
    store[name] = rec
    pathlib.Path(STORE).write_text(json.dumps(store), encoding="utf-8")
    os.chmod(STORE, 0o600)

def load_secret(name: str, password: str) -> str:
    store = json.loads(open(STORE,"r").read())
    rec = store[name]
    salt = base64.b64decode(rec["salt"])
    nonce = base64.b64decode(rec["nonce"])
    ct = base64.b64decode(rec["ct"])
    key = _derive_key(password.encode(), salt)
    aes = AESGCM(key)
    pt = aes.decrypt(nonce, ct, None)
    return pt.decode()
