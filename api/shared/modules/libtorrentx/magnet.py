import re
import urllib.parse
import libtorrent as lt


class MagnetUtils:
    def _validate_magnet_uri(self, magnet):
        """Validate magnet uri

        Args:
            magnet (str): magnet uri

        Returns:
            bool: True if valid
        """

        try:
            return lt.parse_magnet_uri(magnet).info_hashes.has_v1()
        except Exception:
            return False

    def _clean_magnet_uri(self, magnet):
        """Clean magnet uri

        Args:
            magnet (str): magnet uri

        Raises:
            ValueError: invalid magnet uri

        Returns:
            str: cleaned magnet uri
        """
        magnet = magnet.strip()
        marker = re.search(r"magnet:\?", magnet, re.I)
        if marker:
            magnet = "magnet:?" + magnet[marker.end():]
        else:
            magnet = f"magnet:?xt=urn:btih:{magnet}"
        try:
            params = lt.parse_magnet_uri(magnet)
            if not params.info_hashes.has_v1():
                raise ValueError("A v1 info hash is required")
            # Canonical hash/parameter ordering, without changing case-sensitive
            # tracker paths, passkeys or the display name.
            return lt.make_magnet_uri(params)
        except Exception as error:
            raise ValueError("invalid magnet uri") from error

    def _get_magnet_from_torrent_file(self, torrent_file):
        """Get magnet uri from torrent file

        Args:
            torrent_file (str): torrent file

        Returns:
            str: magnet uri
        """

        torrent_info = lt.torrent_info(torrent_file)
        magnet = lt.make_magnet_uri(torrent_info)
        return magnet
