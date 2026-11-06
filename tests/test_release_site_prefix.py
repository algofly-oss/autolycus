"""Release website prefixes must not contaminate metadata lookup titles."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))
from shared.modules.torrent_name_parser import parse


class ReleaseSitePrefixTests(unittest.TestCase):
    def test_release_website_prefix_is_not_part_of_movie_title(self):
        name = 'www.5MovieRulz.company - Mirzapur - The Movie (2026) 1080p Hindi HQ HDRip - x264 - (DD+5.1 - 640Kbps & AAC 2.0) - 3.3GB - ESub.mkv'
        info = parse(name)
        self.assertEqual(info['title'], 'Mirzapur - The Movie')
        self.assertEqual(info['year'], 2026)
        self.assertEqual(info['resolution'], '1080p')
        self.assertNotIn('season', info)
        self.assertEqual(parse('www.Movie.2026.mkv')['title'], 'www Movie')
        for prefix in ('OtherSite.company - ', 'https://www.OtherSite.company/ - ', '[www.OtherSite.company] ', '[OtherSite.company] - '):
            with self.subTest(prefix=prefix):
                self.assertEqual(parse(prefix + 'Mirzapur - The Movie (2026) 1080p.mkv')['title'], 'Mirzapur - The Movie')


if __name__ == "__main__":
    unittest.main()
