"""Opt-in live verification; contacts the Tor Project over each supported route."""
import requests

for label, url, proxies in (
    ("SOCKS", "https://check.torproject.org/api/ip", {"https": "socks5h://127.0.0.1:9050"}),
    ("HTTP proxy", "https://check.torproject.org/api/ip", {"https": "http://127.0.0.1:8118"}),
    ("browser proxy", "http://127.0.0.1/tor/https://check.torproject.org/api/ip", {}),
):
    response = requests.get(url, proxies=proxies,
                            headers={"User-Agent": "Mozilla/5.0 AutolycusIntegration"}, timeout=90)
    response.raise_for_status()
    assert response.json().get("IsTor") is True, label + " did not use a Tor exit"
    print("PASS:", label, "uses a verified Tor exit", flush=True)
