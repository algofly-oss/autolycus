"""Shared aria2 arguments; URLs and paths are argv entries, never shell code."""
import os
from urllib.parse import urlsplit


def validate_url(url):
    parsed=urlsplit(url)
    if parsed.scheme.lower() not in {"http","https","ftp","sftp"} or not parsed.hostname:
        raise ValueError("A HTTP, HTTPS, FTP or SFTP URL is required")
    if any(char in url for char in ('\r','\n','\0')):
        raise ValueError("Invalid URL")
    return url


def aria2_command(url, save_dir=None, dry_run=False):
    validate_url(url)
    connections=min(16,max(1,int(os.getenv("URL_DOWNLOAD_CONNECTIONS","8"))))
    verify=os.getenv("URL_VERIFY_TLS","1").lower() not in {"0","false","no"}
    args=["aria2c","--no-conf=true","--enable-color=false","--file-allocation=none","--continue=true",
          f"--max-connection-per-server={connections}",f"--split={connections}","--disk-cache=8M","--summary-interval=1",
          "--auto-file-renaming=false","--allow-overwrite=false","--follow-torrent=false","--follow-metalink=false",
          "--connect-timeout=10","--timeout=20","--max-tries=5","--retry-wait=2",f"--check-certificate={'true' if verify else 'false'}"]
    if dry_run:
        args += ["--dry-run=true","--console-log-level=info"]
    else:
        args += ["--console-log-level=warn","--dir",str(save_dir)]
    return [*args,"--",url]
