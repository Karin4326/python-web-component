# Path Component Case Conflict Checker

Detects case-insensitive path collisions within a directory tree. Use it before
transferring files from a case-sensitive filesystem (Linux ext4) to a
case-insensitive one (macOS APFS, Windows NTFS), where `Foo.txt` would silently
overwrite `foo.txt`.

## Usage

```python
from path_component_case_conflict_checker import find_case_conflicts

conflicts = find_case_conflicts(".")
for c in conflicts:
    print(f"{c.parent}: {c.variants}  (key: {c.lowercase_key})")
```

## Why

Moving a tree from ext4 to NTFS or APFS silently merges directories and
overwrites files whose names differ only in case. There is no warning, no log
entry — the destination simply ends up with whichever variant the filesystem
copied last. This library walks the source tree and reports those collisions
up front so you can rename before the transfer.

The trade-off: only *immediate siblings* within the same parent directory are
compared. Two files in different directories never conflict with each other;
they only conflict with their own siblings. This matches how
case-insensitive filesystems actually resolve names.

## Edge cases

- Unicode normalization: macOS APFS normalizes filenames to NFC on write, so
  a decomposed form (`cafe\u0301.txt`) and a precomposed form (`caf\u00e9.txt`)
  collide. This library normalizes via NFC before lowercasing, so it reports
  those as conflicts. Linux ext4 does not normalize, so both can coexist there
  and the library catches that mismatch.
- Casefolding is ASCII-only (`.lower()`), matching what NTFS and APFS do, not
  full Unicode casefolding (so Turkish dotted-i is not special-cased).
- Symlinks to directories are not followed by default, to avoid cycles. Pass
  `ignore_symlinks=False` to follow them with cycle protection.

## Exported names

- `find_case_conflicts(root, *, ignore_symlinks=True) -> list[ConflictingPathComponent]`
- `ConflictingPathComponent` (frozen dataclass with fields `lowercase_key`,
  `parent`, `variants`, and an `as_dict()` method)
