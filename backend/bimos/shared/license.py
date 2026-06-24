import hashlib
import hmac
import platform
import uuid
from datetime import date, datetime
from pathlib import Path

_SECRET_KEY = b"bimos_hmac_secret_2026_v1"
_LICENSE_FILE = Path.home() / ".bimos" / "license.lic"


def _machine_fingerprint_raw() -> str:
    parts = []
    mid = Path("/etc/machine-id")
    if mid.exists():
        parts.append(mid.read_text().strip())
    else:
        mid = Path("/var/lib/dbus/machine-id")
        if mid.exists():
            parts.append(mid.read_text().strip())
    parts.append(platform.node())
    parts.append(hex(uuid.getnode()))
    return "|".join(parts)


def machine_fingerprint() -> str:
    return hashlib.sha256(_machine_fingerprint_raw().encode()).hexdigest()


def _obfuscation_key(fp: str | None = None) -> bytes:
    if fp is None:
        fp = machine_fingerprint()
    return hashlib.sha256(fp.encode()).digest()


def _xor_obfuscate(data: bytes, key: bytes) -> bytes:
    return bytes(d ^ key[i % len(key)] for i, d in enumerate(data))


def _store_obfuscated(license_key: str) -> None:
    fp = machine_fingerprint()
    check = hashlib.sha256((license_key + fp).encode()).hexdigest()[:16]
    payload = (check + "::" + license_key).encode()
    obfuscated = _xor_obfuscate(payload, _obfuscation_key())
    _LICENSE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _LICENSE_FILE.write_bytes(obfuscated)


def _read_obfuscated() -> str | None:
    if not _LICENSE_FILE.exists():
        return None
    raw = _LICENSE_FILE.read_bytes()
    fp = machine_fingerprint()
    deob = _xor_obfuscate(raw, _obfuscation_key()).decode(errors="replace")
    if "::" not in deob:
        return None
    stored_check, license_key = deob.split("::", 1)
    expected_check = hashlib.sha256((license_key + fp).encode()).hexdigest()[:16]
    if stored_check != expected_check:
        return None
    return license_key


def generate_key(fingerprint: str, expiry: str) -> str:
    if not expiry or expiry.upper() in ("", "PERMANENT", "0000-00-00"):
        expiry = "PERMANENT"
    payload = f"{fingerprint}|{expiry}"
    sig = hmac.new(_SECRET_KEY, payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}|{sig}"


def validate_key(key: str) -> tuple[bool, str]:
    try:
        parts = key.split("|")
        if len(parts) != 3:
            return False, "invalid license format"
        fingerprint, expiry_str, sig = parts
        expected = hmac.new(
            _SECRET_KEY, f"{fingerprint}|{expiry_str}".encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return False, "invalid signature"

        if expiry_str == "PERMANENT":
            return True, "permanent license"

        expiry = datetime.strptime(expiry_str, "%Y-%m-%d").date()
        if expiry < date.today():
            return False, f"license expired on {expiry_str}"
        return True, f"valid until {expiry_str}"
    except Exception as e:
        return False, str(e)


def is_licensed() -> tuple[bool, str]:
    license_key = _read_obfuscated()
    if license_key is None:
        return False, "no license found. place the .lic file in ~/.bimos/"
    fp = machine_fingerprint()
    valid, msg = validate_key(license_key)
    if not valid:
        return False, msg
    parts = license_key.split("|")
    stored_fp = parts[0]
    if stored_fp != fp:
        return False, "license is tied to another machine"
    return True, msg


def generate_license_file(client_fingerprint: str, expiry: str, output: str | Path) -> Path:
    key = generate_key(client_fingerprint, expiry)
    check = hashlib.sha256((key + client_fingerprint).encode()).hexdigest()[:16]
    payload = (check + "::" + key).encode()
    obfuscated = _xor_obfuscate(payload, _obfuscation_key(client_fingerprint))
    out = Path(output)
    out.write_bytes(obfuscated)
    return out
