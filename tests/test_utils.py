import unittest

from netcdf_cog_stac import utils


class TestUtils(unittest.TestCase):
    def test_path_or_url_join_with_s3_url(self):
        self.assertEqual(utils.path_or_url_join('s3://foobar', 'baz', 'blop'),
                         's3://foobar/baz/blop')


if __name__ == '__main__':
    unittest.main()
