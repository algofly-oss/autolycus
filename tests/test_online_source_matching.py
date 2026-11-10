"""Provider matching must not substitute another movie, year or episode kind."""
import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('online_sources',Path(__file__).resolve().parents[1]/'api/shared/modules/online_sources.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class SourceMatching(unittest.TestCase):
 def test_exact_title_with_language_edition(self):
  item={'title':'WALL·E [Hindi]','releaseDate':'2008-06-22','subjectType':1}
  self.assertTrue(m.matches(item,'WALL-E',2008,'movie'))
  for change in [{'title':'Wall Street'},{'releaseDate':'2026-01-01'},{'subjectType':2}]:
   self.assertFalse(m.matches({**item,**change},'WALL-E',2008,'movie'))
  self.assertFalse(m.matches(item,'WALL-E',None,'movie'))
 def test_media_urls_are_provider_https_only(self):
  self.assertIsNotNone(m.media_url('https://cdn.hakunaymatata.com/video.mp4?x=1'))
  for url in ['http://cdn.hakunaymatata.com/a','https://127.0.0.1/a','https://evil.example/a','https://cdn.hakunaymatata.com.evil.example/a','https://user:pass@cdn.hakunaymatata.com/a','https://cdn.hakunaymatata.com:8080/a']:
   self.assertIsNone(m.media_url(url),url)
 def test_series_requires_explicit_episode_before_network(self):
  import asyncio
  self.assertEqual(asyncio.run(m.lookup('Orbit',2024,'series')),[])

if __name__=='__main__':unittest.main()
