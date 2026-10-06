from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional, Union


@dataclass(frozen=True)
class ConflictingPathComponent:
    """A path component (directory or file name) that collides with another component
    in the same parent directory when compared case-insensitively.

    The two variants may differ only in case, or may also differ in their Unicode
    representation (NFC vs NFD decomposition), so each variant is stored verbatim
    rather than reduced to a normalized form.
    """
    lowercase_key: str
    parent: str
    variants: List[str]

    def as_dict(self) -> dict:
        return {
            "lowercase_key": self.lowercase_key,
            "parent": self.parent,
            "variants": list(self.variants),
        }


def find_case_conflicts(
    root: Union[str, bytes, "os.PathLike"],
    *,
    ignore_symlinks: bool = True,
) -> List[ConflictingPathComponent]:
    """Walk a directory tree and detect path components that collide
    case-insensitively within the same parent directory.

    WHY: Moving files from a case-sensitive filesystem (Linux ext4) to a
    case-insensitive one (macOS APFS, Windows NTFS) silently overwrites
    ``Foo.txt`` with ``foo.txt``. This function finds those collisions before
    transfer so the user can rename.

    Interpretation choices (documented because the brief is ambiguous):
      - Only *immediate siblings* within the same parent directory are
        compared. Two files in different directories with the same name never
        conflict with each other; they only conflict with siblings in their
        own directory.
      - Comparison is case-insensitive ASCII lowercasing. We intentionally do
        NOT do full Unicode casefolding (e.g. Turkish dotted-i) because the
        target filesystems (NTFS, APFS) also use simple byte-wise lowercasing.
      - Precomposed and decomposed Unicode forms (NFC/NFD) are treated as
        the same character via ``unicodedata.normalize('NFC', ...)`` before
        lowercasing, because that is what happens on macOS APFS.
      - By default, symlinks are NOT followed. A symlink pointing at an
        ancestor could cause infinite recursion. Passing
        ``ignore_symlinks=False`` follows them but guards against revisiting
        the same real path.

    Args:
        root: Directory to scan. Must be a string, bytes, or path-like object
            pointing at an existing directory.
        ignore_symlinks: If True (default), do not traverse into symlinked
            directories. If False, follow symlinks but skip already-visited
            real paths.

    Returns:
        A list of :class:`ConflictingPathComponent`. Empty list if no
        collisions. The list is sorted by parent path and then lowercase key
        for determinism.
    """
    import unicodedata

    root_path = os.fspath(root)
    if isinstance(root_path, bytes):
        root_str = os.fsdecode(root_path)
    else:
        root_str = root_path

    if not os.path.isdir(root_str):
        raise NotADirectoryError(f"root is not a directory: {root_str!r}")

    results: List[ConflictingPathComponent] = []
    visited: set = set()

    def _norm_key(name: str) -> str:
        # NFC-normalize then lowercase. NFC so NFD and NFC forms collide
        # (macOS APFS behavior). ASCII-lowercase so we match what NTFS/APFS
        # actually do, rather than locale-dependent Unicode casefolding.
        return unicodedata.normalize("NFC", name).lower()

    def _walk(directory: str) -> None:
        try:
            entries = sorted(os.listdir(directory))
        except PermissionError:
            return

        # Map normalized key -> list of original variant names.
        siblings: dict = {}
        subdirs: List[str] = []

        for name in entries:
            key = _norm_key(name)
            siblings.setdefault(key, []).append(name)

            full = os.path.join(directory, name)
            if ignore_symlinks and os.path.islink(full):
                continue
            if os.path.isdir(full) and not os.path.islink(full):
                subdirs.append(full)
            elif (
                not ignore_symlinks
                and os.path.islink(full)
                and os.path.isdir(full)
            ):
                # Resolve and guard against cycles.
                try:
                    real = os.path.realpath(full)
                except OSError:
                    continue
                if real in visited:
                    continue
                visited.add(real)
                subdirs.append(full)

        # Record collisions among immediate siblings.
        for key, variants in siblings.items():
            if len(variants) > 1:
                results.append(
                    ConflictingPathComponent(
                        lowercase_key=key,
                        parent=directory,
                        variants=variants,
                    )
                )

        for sub in subdirs:
            _walk(sub)

    root_real = os.path.realpath(root_str)
    visited.add(root_real)
    _walk(root_str)

    results.sort(key=lambda c: (c.parent, c.lowercase_key))
    return results
