from pydantic import BaseModel
from shared.modules.libtorrentx import LibTorrentSession
from shared.modules.libtorrentx import MagnetUtils


class MagnetDto(BaseModel):
    magnet: str


lt_session = LibTorrentSession()
magnet_utils = MagnetUtils()
