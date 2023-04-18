from pydantic import BaseModel
from libtorrentx import LibTorrentSession
from libtorrentx.magnet import MagnetUtils


class MagnetDto(BaseModel):
    magnet: str


lt_session = LibTorrentSession()
magnet_utils = MagnetUtils()
