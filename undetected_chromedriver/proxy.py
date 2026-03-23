#!/usr/bin/env python3


from __future__ import annotations

import json
from typing import TYPE_CHECKING, NamedTuple, Optional
from urllib.parse import unquote, urlparse

from .auth_forward_proxy import start_auth_forward_proxy

if TYPE_CHECKING:
    from .auth_forward_proxy import AuthForwardProxy


class ProxySetup(NamedTuple):

    forward_proxy: Optional["AuthForwardProxy"] = None


def normalize_proxy_url(proxy_url: str) -> str:
    raw = proxy_url.strip()
    if not raw:
        raise ValueError("empty proxy URL")
    if "://" not in raw:
        raw = "http://" + raw
    return raw


def parse_proxy_url(proxy_url: str):

    raw = normalize_proxy_url(proxy_url)
    p = urlparse(raw)
    host = p.hostname
    if not host:
        raise ValueError("proxy URL must include a host")
    port = p.port
    if port is None:
        port = 443 if (p.scheme or "").lower() == "https" else 80
    scheme = (p.scheme or "http").lower()
    if scheme in ("socks", "socks5"):
        scheme = "socks5"
    user = unquote(p.username) if p.username else None
    password = unquote(p.password) if p.password else None
    return scheme, host, port, user, password


def apply_proxy_to_options(
    options,
    proxy_server: Optional[str],
    *,
    devtools_host: str = "127.0.0.1",
    devtools_port: Optional[int] = None,
) -> Optional[ProxySetup]:

    if not proxy_server or not str(proxy_server).strip():
        return None

    scheme, host, port, user, password = parse_proxy_url(proxy_server)

    if scheme == "socks5" and (user or password):
        raise ValueError(
            "SOCKS5 proxy with username/password is not supported by this helper; "
            "use a local forwarder or an HTTP proxy."
        )

    if devtools_port is not None:

        dp = int(devtools_port)
        bypass = [
            "127.0.0.1:%d" % dp,
            "localhost:%d" % dp,
            "[::1]:%d" % dp,
        ]
        if devtools_host not in ("127.0.0.1", "localhost", "::1"):
            bypass.insert(0, "%s:%d" % (devtools_host, dp))
        options.add_argument("--proxy-bypass-list=" + ",".join(bypass))
    else:
        options.add_argument("--proxy-bypass-list=<-loopback>")

    if user is not None or password is not None:
        if scheme == "socks5":
            raise ValueError("SOCKS5 with auth requires an external SOCKS forwarder.")
        fp = start_auth_forward_proxy(host, port, user or "", password or "")
        options.add_argument("--proxy-server=http://127.0.0.1:%d" % fp.port)
        return ProxySetup(forward_proxy=fp)

    if scheme == "socks5":
        options.add_argument("--proxy-server=socks5://%s:%d" % (host, port))
    elif scheme == "https":
        options.add_argument("--proxy-server=https://%s:%d" % (host, port))
    else:
        options.add_argument("--proxy-server=http://%s:%d" % (host, port))
    return ProxySetup()


def fetch_direct_public_ip(timeout: float = 15.0) -> Optional[str]:

    try:
        import requests

        r = requests.get(
            "https://api.ipify.org?format=json",
            timeout=timeout,
            headers={"User-Agent": "undetected-chromedriver-proxy-check/1"},
        )
        r.raise_for_status()
        ip = r.json().get("ip")
        return str(ip).strip() if ip else None
    except Exception:
        return None


def parse_ipify_json_text(body: str) -> Optional[str]:
    if not body or not body.strip():
        return None
    try:
        data = json.loads(body.strip())
        ip = data.get("ip")
        return str(ip).strip() if ip else None
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def verify_proxy_egress(
    browser_ip: Optional[str],
    direct_ip: Optional[str],
    expected_ip: Optional[str] = None,
    *,
    direct_check_skipped: bool = False,
) -> tuple[bool, str]:

    lines = []

    if not browser_ip:
        return False, "Could not read egress IP from the page (expected JSON with an \"ip\" field)."

    lines.append("Browser egress IP: %s" % browser_ip)

    if expected_ip:
        exp = expected_ip.strip()
        if browser_ip == exp:
            lines.append("Matches --expected-ip (%s)." % exp)
            return True, "\n".join(lines)
        lines.append(
            "FAIL: does not match --expected-ip (%s). Proxy may be wrong or not used."
            % exp
        )
        return False, "\n".join(lines)

    if direct_check_skipped:
        lines.append(
            "Direct comparison skipped; use --expected-ip to assert a provider IP."
        )
        return True, "\n".join(lines)

    if direct_ip is not None:
        lines.append("Direct (non-browser) egress IP: %s" % direct_ip)
        if browser_ip == direct_ip:
            lines.append(
                "WARNING: same as direct IP — Chrome may not be using the proxy, "
                "or your proxy exits at the same network as this machine."
            )
            return False, "\n".join(lines)
        lines.append("OK: browser IP differs from direct IP — proxy is likely in use.")
        return True, "\n".join(lines)

    lines.append(
        "Could not fetch direct IP for comparison; only browser egress is shown. "
        "Pass --expected-ip to assert a provider IP, or fix network/firewall."
    )
    return True, "\n".join(lines)
