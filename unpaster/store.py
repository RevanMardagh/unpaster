"""Snippet model and encrypted persistence.

The whole snippet file is DPAPI-encrypted as one blob. ENTROPY is compiled
into the binary as a second DPAPI factor so the file cannot be decrypted by
a bare CryptUnprotectData call from another program running as the same
user. It is a speed bump, not a barrier -- anyone holding the executable can
extract it.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import dpapi, fsutil

ENTROPY = b"unpaster/v1/snippet-store"
SCHEMA_VERSION = 1


@dataclass
class Snippet:
    id: str
    name: str
    body: str
    secret: bool = False
    order: int = 0
    send_keys: bool = False  # interpret {ctrl+a}, {enter}, {wait:500} in the body


def snippets_path() -> Path:
    return fsutil.app_dir() / "snippets.dat"


def _next_backup_path(path: Path) -> Path:
    index = 1
    while True:
        candidate = path.with_name(f"{path.name}.bad-{index}")
        if not candidate.exists():
            return candidate
        index += 1


class SnippetStore:
    def __init__(self, path: Path, snippets: list[Snippet] | None = None) -> None:
        self.path = path
        self.snippets: list[Snippet] = snippets or []
        self._renumber()

    @classmethod
    def load(cls, path: Path) -> tuple["SnippetStore", list[str]]:
        if not path.exists():
            return cls(path), []
        raw = path.read_bytes()
        try:
            payload = json.loads(dpapi.unprotect(raw, ENTROPY).decode("utf-8"))
            items = payload["snippets"]
            snippets = [
                Snippet(
                    id=str(item["id"]),
                    name=str(item["name"]),
                    body=str(item["body"]),
                    secret=bool(item.get("secret", False)),
                    order=int(item.get("order", index)),
                    send_keys=bool(item.get("send_keys", False)),
                )
                for index, item in enumerate(items)
            ]
        except (dpapi.DpapiError, ValueError, KeyError, TypeError):
            backup = _next_backup_path(path)
            path.replace(backup)
            return cls(path), [
                f"Snippet file could not be read. It was kept as {backup.name} and unpaster started empty."
            ]
        return cls(path, snippets), []

    def save(self) -> None:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "snippets": [asdict(s) for s in self.snippets],
        }
        blob = dpapi.protect(json.dumps(payload).encode("utf-8"), ENTROPY)
        fsutil.atomic_write_bytes(self.path, blob)

    def _renumber(self) -> None:
        self.snippets.sort(key=lambda s: s.order)
        for index, snippet in enumerate(self.snippets):
            snippet.order = index

    def get(self, sid: str) -> Snippet:
        for snippet in self.snippets:
            if snippet.id == sid:
                return snippet
        raise KeyError(sid)

    def add(self, name: str, body: str, secret: bool = False,
            send_keys: bool = False) -> Snippet:
        snippet = Snippet(id=str(uuid.uuid4()), name=name, body=body,
                          secret=secret, order=len(self.snippets), send_keys=send_keys)
        self.snippets.append(snippet)
        return snippet

    def update(self, sid: str, *, name: str | None = None, body: str | None = None,
               secret: bool | None = None, send_keys: bool | None = None) -> Snippet:
        snippet = self.get(sid)
        if name is not None:
            snippet.name = name
        if body is not None:
            snippet.body = body
        if secret is not None:
            snippet.secret = secret
        if send_keys is not None:
            snippet.send_keys = send_keys
        return snippet

    def delete(self, sid: str) -> None:
        snippet = self.get(sid)
        self.snippets.remove(snippet)
        self._renumber()

    def move(self, sid: str, new_index: int) -> None:
        snippet = self.get(sid)
        self.snippets.remove(snippet)
        new_index = max(0, min(new_index, len(self.snippets)))
        snippet.order = new_index
        self.snippets.insert(new_index, snippet)
        self._renumber()

    def search(self, query: str) -> list[Snippet]:
        """Substring match on name only. Bodies may be secrets and are never searched."""
        needle = query.strip().lower()
        if not needle:
            return list(self.snippets)
        return [s for s in self.snippets if needle in s.name.lower()]
