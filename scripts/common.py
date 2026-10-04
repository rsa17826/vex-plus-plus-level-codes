"""Shared logic between validate_pr.py and build_manifest.py.

This re-implements the exact canonical-byte layout and signature check that
LevelServer.gd's canonicalLevelBytes() / verifyLevelSignature() use client
side. If you change the byte layout in LevelServer.gd, update this to match
or every PR will start failing validation.
"""
import base64

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


def canonical_level_bytes(level: dict) -> bytes:
    if "levelData" not in level:
        raise KeyError("levelData")
    return b"\x00".join([
        level["levelName"].encode("utf-8"),
        level["creatorName"].encode("utf-8"),
        str(level["gameVersion"]).encode("utf-8"),
        str(level["levelVersion"]).encode("utf-8"),
    ]) + b"\x00" + base64.b64decode(level["levelData"])


def verify_level(level: dict, registry_pubkey_b64: str) -> bool:
    """True only if: the level's embedded pubkey matches the registry entry
    for its creator AND the signature verifies against that key. Both must
    hold -- checking only one lets someone sign with their own unrelated
    key and claim someone else's username."""
    try:
        embedded_pub_b64 = level["publicKey"].strip()
        if embedded_pub_b64 != registry_pubkey_b64.strip():
            return False
        pub = Ed25519PublicKey.from_public_bytes(base64.b64decode(embedded_pub_b64))
        pub.verify(base64.b64decode(level["signature"]), canonical_level_bytes(level))
        return True
    except (InvalidSignature, KeyError, ValueError, TypeError):
        return False
