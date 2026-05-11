from __future__ import annotations

import json
import os
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STORE_VERSION = 1
APP_NAME = "compliant-literature-access"


class CredentialStoreError(RuntimeError):
    pass


def store_path() -> Path:
    if platform.system() == "Windows":
        root = Path(os.environ.get("APPDATA", Path.home()))
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return root / APP_NAME / "credentials.json"


def _load_store() -> dict[str, Any]:
    path = store_path()
    if not path.exists():
        return {"version": STORE_VERSION, "services": {}}
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if "services" not in data:
        data["services"] = {}
    return data


def _save_store(data: dict[str, Any]) -> None:
    path = store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    if platform.system() != "Windows":
        path.chmod(0o600)


def _run_powershell(script: str, stdin: str) -> str:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        input=stdin,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise CredentialStoreError(result.stderr.strip() or "PowerShell credential operation failed")
    return result.stdout.rstrip("\r\n")


def _protect_password(password: str) -> tuple[str, str]:
    if platform.system() == "Windows":
        script = """
$plain = [Console]::In.ReadToEnd()
$secure = ConvertTo-SecureString $plain -AsPlainText -Force
$secure | ConvertFrom-SecureString
"""
        return "windows-dpapi-current-user", _run_powershell(script, password)

    try:
        import keyring  # type: ignore
    except Exception as exc:
        raise CredentialStoreError(
            "Non-Windows credential storage requires the 'keyring' package. "
            "Install keyring or run on Windows for DPAPI storage."
        ) from exc

    return "keyring", ""


def _unprotect_password(record: dict[str, Any]) -> str:
    storage = record.get("storage")
    if storage == "windows-dpapi-current-user":
        script = """
$blob = [Console]::In.ReadToEnd()
$secure = ConvertTo-SecureString $blob
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
  [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
} finally {
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
}
"""
        return _run_powershell(script, record["password_blob"])

    if storage == "keyring":
        try:
            import keyring  # type: ignore
        except Exception as exc:
            raise CredentialStoreError("The 'keyring' package is required to read this credential.") from exc
        password = keyring.get_password(APP_NAME, record["keyring_account"])
        if password is None:
            raise CredentialStoreError("Credential not found in keyring.")
        return password

    raise CredentialStoreError(f"Unsupported credential storage: {storage}")


def save_credentials(service: str, username: str, password: str) -> Path:
    if not service.strip():
        raise CredentialStoreError("Service name is required.")
    if not username.strip():
        raise CredentialStoreError("Username is required.")

    storage, blob = _protect_password(password)
    data = _load_store()
    record: dict[str, Any] = {
        "username": username,
        "storage": storage,
        "updated_utc": datetime.now(timezone.utc).isoformat(),
    }

    if storage == "windows-dpapi-current-user":
        record["password_blob"] = blob
    elif storage == "keyring":
        import keyring  # type: ignore

        account = f"{service}:{username}"
        keyring.set_password(APP_NAME, account, password)
        record["keyring_account"] = account
    else:
        raise CredentialStoreError(f"Unsupported credential storage: {storage}")

    data["services"][service] = record
    _save_store(data)
    return store_path()


def get_credentials(service: str) -> tuple[str, str] | None:
    data = _load_store()
    record = data.get("services", {}).get(service)
    if not record:
        return None
    return record["username"], _unprotect_password(record)


def delete_credentials(service: str) -> bool:
    data = _load_store()
    record = data.get("services", {}).pop(service, None)
    if not record:
        return False
    if record.get("storage") == "keyring":
        try:
            import keyring  # type: ignore

            keyring.delete_password(APP_NAME, record["keyring_account"])
        except Exception:
            pass
    _save_store(data)
    return True


def list_services() -> list[dict[str, str]]:
    data = _load_store()
    rows = []
    for service, record in sorted(data.get("services", {}).items()):
        rows.append(
            {
                "service": service,
                "username": record.get("username", ""),
                "storage": record.get("storage", ""),
                "updated_utc": record.get("updated_utc", ""),
            }
        )
    return rows
