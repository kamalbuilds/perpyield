from __future__ import annotations
import json
import base58
from solders.keypair import Keypair


def _sort_json_keys(value):
    if isinstance(value, dict):
        return {k: _sort_json_keys(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return [_sort_json_keys(item) for item in value]
    return value


def prepare_message(header: dict, payload: dict) -> str:
    for key in ("type", "timestamp", "expiry_window"):
        if key not in header:
            raise ValueError(f"Header missing required field: {key}")
    data = {**header, "data": payload}
    return json.dumps(_sort_json_keys(data), separators=(",", ":"))


def sign_message(header: dict, payload: dict, keypair: Keypair) -> tuple[str, str]:
    message = prepare_message(header, payload)
    sig = keypair.sign_message(message.encode("utf-8"))
    return message, base58.b58encode(bytes(sig)).decode("ascii")
