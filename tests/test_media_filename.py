"""PTN-backed queue identity and public-title regression cases."""
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'api'))
from shared.modules.media_filename import episode_identity, public_file_title
from shared.modules.torrent_name_parser import parse_title

class MediaFilenameTests(unittest.TestCase):
    def test_scene_formats_and_season_context(self):
        for name, season, episode in [
            ('Show/Show.S01E02.Pilot.1080p.mkv',1,2),
            ('Show/Show.1x01.Pilot.mkv',1,1),
            ('Show/Season 2/Episode 10.mp4',2,10),
            ('Show/Season 2/Episode 02 - Pilot.mkv',2,2),
            ('Show/Season 2/02 - Pilot.mkv',2,2),
            ('Show/Season 2/E02.The.Pilot.mkv',2,2),
            ('Show/Season 1/S02E01.mkv',2,1),
            ('Show/Show.S00E01.Special.mkv',0,1),
            ('Show/[Group] Show.S01E102.mkv',1,102),
        ]:
            with self.subTest(name=name):
                info=episode_identity(name)
                self.assertEqual((info['series'],info['season'],info['episode']),('Show',season,episode))

    def test_anime_absolute_episode_and_multi_episode_ranges(self):
        self.assertEqual(episode_identity('[SubsPlease] Anime - 102 [1080p].mkv')['episode'],102)
        self.assertIn('.E102.',public_file_title('[SubsPlease] Anime - 102 [1080p].mkv'))
        self.assertIn('S01.E02-E04',parse_title('Show.S01E02-E04.mkv'))
        self.assertIn('S01.E02-E03',parse_title('Show.S01E02E03.mkv'))

    def test_movies_years_and_quality_are_not_episodes(self):
        for path in ['Movie.2024.1080p.mkv','1917.2019.1080p.mkv','Movie.2160p.10bit.mkv','2024.mkv','Movie/1080p.mkv']:
            self.assertIsNone(episode_identity(path),path)

    def test_public_title_file_overrides_pack_episode(self):
        title=public_file_title('/downloads/'+'a'*24+'/'+'b'*40+'/Episode 02 - Pilot.mkv','Show.S01E01-E10.Complete.1080p')
        self.assertEqual(title,'Show.S01.E02.1080p.mkv')
        self.assertEqual(public_file_title('Show.S02E03.720p.mkv','Show.S01.1080p'),'Show.S02.E03.720p.mkv')
        self.assertEqual(public_file_title('Movie.2024.1080p.mp4','Movie.2023'), 'Movie.2024.1080p.mp4')

if __name__ == '__main__':
    unittest.main()
