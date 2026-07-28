"""Windows DPAPI wrappers.

Keys derive from the logged-on user account, so a copied file cannot be
decrypted by another user or on another machine. This does not protect
against code already running as the same user.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes

CRYPTPROTECT_UI_FORBIDDEN = 0x01


class DpapiError(Exception):
    """A DPAPI call failed. Message includes the Windows error code."""


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_char)),
    ]


_crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

_BLOB_P = ctypes.POINTER(_DataBlob)

_crypt32.CryptProtectData.argtypes = [
    _BLOB_P, wintypes.LPCWSTR, _BLOB_P, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, _BLOB_P
]
_crypt32.CryptProtectData.restype = wintypes.BOOL

_crypt32.CryptUnprotectData.argtypes = [
    _BLOB_P, ctypes.POINTER(wintypes.LPWSTR), _BLOB_P, ctypes.c_void_p, ctypes.c_void_p,
    wintypes.DWORD, _BLOB_P
]
_crypt32.CryptUnprotectData.restype = wintypes.BOOL

_kernel32.LocalFree.argtypes = [ctypes.c_void_p]
_kernel32.LocalFree.restype = ctypes.c_void_p


def _make_blob(data: bytes) -> tuple[_DataBlob, ctypes.Array]:
    """Return a blob plus the buffer backing it; the caller must keep both alive."""
    buffer = ctypes.create_string_buffer(data, len(data))
    blob = _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
    return blob, buffer


def _take_blob(blob: _DataBlob) -> bytes:
    try:
        return ctypes.string_at(blob.pbData, blob.cbData)
    finally:
        _kernel32.LocalFree(blob.pbData)


def protect(data: bytes, entropy: bytes) -> bytes:
    in_blob, in_buffer = _make_blob(data)
    ent_blob, ent_buffer = _make_blob(entropy)
    out_blob = _DataBlob()
    ok = _crypt32.CryptProtectData(
        ctypes.byref(in_blob), None, ctypes.byref(ent_blob), None, None,
        CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out_blob),
    )
    del in_buffer, ent_buffer
    if not ok:
        raise DpapiError(f"CryptProtectData failed with error {ctypes.get_last_error()}")
    return _take_blob(out_blob)


def unprotect(blob: bytes, entropy: bytes) -> bytes:
    in_blob, in_buffer = _make_blob(blob)
    ent_blob, ent_buffer = _make_blob(entropy)
    out_blob = _DataBlob()
    ok = _crypt32.CryptUnprotectData(
        ctypes.byref(in_blob), None, ctypes.byref(ent_blob), None, None,
        CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out_blob),
    )
    del in_buffer, ent_buffer
    if not ok:
        raise DpapiError(f"CryptUnprotectData failed with error {ctypes.get_last_error()}")
    return _take_blob(out_blob)
