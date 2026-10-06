import os
import tempfile
import unittest

from path_component_case_conflict_checker import find_case_conflicts, ConflictingPathComponent


class TestFindCaseConflicts(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _make(self, *rel_parts: str):
        """Create an empty file or directory under tmp."""
        p = os.path.join(self.tmp.name, *rel_parts)
        if rel_parts and "." not in rel_parts[-1] and not os.path.splitext(rel_parts[-1])[1]:
            os.makedirs(p, exist_ok=True)
        else:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, "w").close()
        return p

    def test_no_conflicts_returns_empty(self):
        self._make("a.txt")
        self._make("b.txt")
        self._make("sub", "c.txt")
        self.assertEqual(find_case_conflicts(self.tmp.name), [])

    def test_same_name_different_dirs_no_conflict(self):
        self._make("dir1", "File.txt")
        self._make("dir2", "File.txt")
        self.assertEqual(find_case_conflicts(self.tmp.name), [])

    def test_basic_case_conflict(self):
        self._make("Foo.txt")
        self._make("foo.txt")
        result = find_case_conflicts(self.tmp.name)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].parent, self.tmp.name)
        self.assertEqual(result[0].lowercase_key, "foo.txt")
        self.assertEqual(sorted(result[0].variants), ["Foo.txt", "foo.txt"])

    def test_three_way_conflict(self):
        self._make("Readme.md")
        self._make("README.md")
        self._make("readme.md")
        result = find_case_conflicts(self.tmp.name)
        self.assertEqual(len(result), 1)
        self.assertEqual(sorted(result[0].variants),
                         ["README.md", "Readme.md", "readme.md"])

    def test_directory_name_conflict(self):
        self._make("Folder")
        self._make("folder", "inner.txt")
        result = find_case_conflicts(self.tmp.name)
        self.assertEqual(len(result), 1)
        self.assertEqual(sorted(result[0].variants), ["Folder", "folder"])

    def test_conflict_in_subdirectory(self):
        self._make("sub", "Bar.txt")
        self._make("sub", "bar.txt")
        result = find_case_conflicts(self.tmp.name)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].parent,
                         os.path.join(self.tmp.name, "sub"))
        self.assertEqual(sorted(result[0].variants), ["Bar.txt", "bar.txt"])

    def test_conflict_in_root_and_subdir_both_reported(self):
        self._make("Foo.txt")
        self._make("foo.txt")
        self._make("sub", "Foo.txt")
        self._make("sub", "foo.txt")
        result = find_case_conflicts(self.tmp.name)
        # Two distinct collisions in two distinct parent directories.
        self.assertEqual(len(result), 2)
        parents = {c.parent for c in result}
        self.assertEqual(parents,
                         {self.tmp.name, os.path.join(self.tmp.name, "sub")})

    def test_results_are_sorted(self):
        self._make("z", "Bar.txt")
        self._make("z", "bar.txt")
        self._make("Apple.txt")
        self._make("apple.txt")
        result = find_case_conflicts(self.tmp.name)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].parent, self.tmp.name)
        self.assertEqual(result[0].lowercase_key, "apple.txt")
        self.assertEqual(result[1].parent, os.path.join(self.tmp.name, "z"))
        self.assertEqual(result[1].lowercase_key, "bar.txt")

    def test_non_adirectory_raises(self):
        path = self._make("notadir.txt")
        with self.assertRaises(NotADirectoryError):
            find_case_conflicts(path)

    def test_as_dict(self):
        self._make("Foo.txt")
        self._make("foo.txt")
        result = find_case_conflicts(self.tmp.name)
        d = result[0].as_dict()
        self.assertEqual(d["lowercase_key"], "foo.txt")
        self.assertEqual(d["parent"], self.tmp.name)
        self.assertEqual(sorted(d["variants"]), ["Foo.txt", "foo.txt"])

    @unittest.skipUnless(
        hasattr(__import__('unicodedata'), 'normalize'),
        "unicodedata required"
    )
    def test_nfc_nfd_normalization_collides(self):
        # é as precomposed vs decomposed forms.
        precomposed = "caf\u00e9.txt"  # NFC: U+00E9
        decomposed = "cafe\u0301.txt"  # NFD: e + U+0301
        self._make(precomposed)
        self._make(decomposed)
        result = find_case_conflicts(self.tmp.name)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].lowercase_key, "café.txt")

    def test_symlink_not_followed_by_default(self):
        real = self._make("real", "Foo.txt")
        self._make("real", "foo.txt")
        link = os.path.join(self.tmp.name, "link")
        os.symlink(real, link)
        # Only the conflict inside 'real' should be reported once.
        result = find_case_conflicts(self.tmp.name)
        parents = [c.parent for c in result]
        self.assertEqual(parents, [os.path.join(self.tmp.name, "real")])

    def test_empty_directory(self):
        self.assertEqual(find_case_conflicts(self.tmp.name), [])


if __name__ == "__main__":
    unittest.main()
