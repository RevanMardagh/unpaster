import pytest

from unpaster import dpapi

ENTROPY = b"unpaster-test-entropy"


def test_round_trip():
    blob = dpapi.protect(b"secret payload", ENTROPY)
    assert dpapi.unprotect(blob, ENTROPY) == b"secret payload"


def test_ciphertext_differs_from_plaintext():
    blob = dpapi.protect(b"secret payload", ENTROPY)
    assert b"secret payload" not in blob


def test_round_trip_unicode_payload():
    payload = "pässwörd — 密码".encode("utf-8")
    assert dpapi.unprotect(dpapi.protect(payload, ENTROPY), ENTROPY) == payload


def test_round_trip_empty_payload():
    assert dpapi.unprotect(dpapi.protect(b"", ENTROPY), ENTROPY) == b""


def test_wrong_entropy_fails():
    blob = dpapi.protect(b"secret payload", ENTROPY)
    with pytest.raises(dpapi.DpapiError):
        dpapi.unprotect(blob, b"different-entropy")


def test_garbage_blob_fails():
    with pytest.raises(dpapi.DpapiError):
        dpapi.unprotect(b"not a dpapi blob at all", ENTROPY)


def test_large_payload_round_trips():
    payload = b"x" * 1_000_000
    assert dpapi.unprotect(dpapi.protect(payload, ENTROPY), ENTROPY) == payload
