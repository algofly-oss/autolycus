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

        # Parse the magnet link into its individual components
        parsed_link = urllib.parse.urlparse(magnet)

        # Check that the scheme is "magnet"
        if parsed_link.scheme != "magnet":
            return False

        # Check that the link includes a "xt" (exact topic) parameter
        # with a value that starts with "urn:btih:"
        query_dict = urllib.parse.parse_qs(parsed_link.query)
        if "xt" not in query_dict or not query_dict["xt"][0].startswith("urn:btih:"):
            return False

        # Check that the info hash is a base32-encoded string of 40 characters
        info_hash = query_dict["xt"][0][9:]
        if len(info_hash) != 40 or any(
            c not in "0123456789abcdefghijklmnopqrstuvwxyz" for c in info_hash
        ):
            return False

        # Check that the "dn" (display name) parameter, if present, is a valid UTF-8 string
        if "dn" in query_dict:
            try:
                query_dict["dn"][0].encode("utf-8")
            except UnicodeEncodeError:
                return False

        # Check that the "tr" (tracker) parameters, if present, are valid URLs
        if "tr" in query_dict:
            for tracker in query_dict["tr"]:
                try:
                    urllib.parse.urlparse(tracker)
                except ValueError:
                    return False

        # If all checks pass, the magnet link is valid
        return True

    def _clean_magnet_uri(self, magnet):
        """Clean magnet uri

        Args:
            magnet (str): magnet uri

        Raises:
            ValueError: invalid magnet uri

        Returns:
            str: cleaned magnet uri
        """
        magnet = magnet.strip().lower()

        if ("magnet:?xt=urn:btih:" in magnet) and (
            not magnet.startswith("magnet:?xt=urn:btih:")
        ):
            # Most probably magnet link is from vidmate
            # where file name is pre appended to magnet link
            magnet = magnet.split("magnet:?xt=urn:btih:")[1]
            magnet = f"magnet:?xt=urn:btih:{magnet}"

        elif not magnet.startswith("magnet:?xt=urn:btih:"):
            # Most probably magnet link is from TPB
            # where only info_hash is present
            magnet = f"magnet:?xt=urn:btih:{magnet}"

        if self._validate_magnet_uri(magnet):
            return magnet
        else:
            raise ValueError("invalid magnet uri")

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
