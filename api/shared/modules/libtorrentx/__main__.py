# python -m libtorrentx -m magnet:?xt=urn:btih:4C9B41D664D7B6B23F0BF39AE185858CBADDA3FF

from libtorrentx import LibTorrentSession
import argparse
import time


def main(args):
    session = LibTorrentSession()

    handle = session.add_torrent(args.magnet, args.output)

    while True:
        props = handle.props()

        if not props.ok:
            print("waiting for torrent to start...")
            time.sleep(1)
            continue

        print(props.string)

        if props.is_finished:
            break

        time.sleep(1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "-m", "--magnet", help="torrent file path or magnet link", required=True
    )
    ap.add_argument("-o", "--output", help="download path", default="./downloads")
    args = ap.parse_args()

    main(args)
