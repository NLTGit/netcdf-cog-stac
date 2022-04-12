import argparse
import pathlib
import unittest

from netcdf_cog_stac import __main__


class TestMain(unittest.TestCase):
    def test_automatic_or_custom_temp_dir_returns_automatic_tempdir_path(self):
        args = argparse.Namespace(temp_dir=None)
        with __main__.automatic_or_custom_temp_dir(args) as actual:
            self.assertTrue(actual.is_dir())
        self.assertFalse(actual.exists())

    def test_automatic_or_custom_temp_dir_creates_and_leaves_custom_path(self):
        temp_dir = pathlib.Path('tests/tmpdir')
        args = argparse.Namespace(temp_dir=temp_dir)
        try:
            with __main__.automatic_or_custom_temp_dir(args) as actual:
                self.assertEqual(actual, temp_dir)
            self.assertTrue(temp_dir.is_dir())
        finally:
            if temp_dir.exists():
                temp_dir.rmdir()


if __name__ == '__main__':
    unittest.main()
