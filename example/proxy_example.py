#!/usr/bin/env python3
"""
Run Chrome via undetected-chromedriver through a proxy.

Use ``proxy_server=`` on ``uc.Chrome`` — authenticated HTTP proxies use a small
local forwarder (Chrome often ignores user:pass in ``--proxy-server``).

By default the script opens **api.ipify.org** (JSON) to verify egress IP — not Google.
Use ``--google`` to open **https://www.google.com** instead.

Examples:
  python proxy_example.py --proxy http://USER:PASS@HOST:PORT
  python proxy_example.py --proxy 'http://USER:PASS@HOST:PORT' --google --keep-open
  python proxy_example.py --expected-ip 203.0.113.50
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Optional

# Run from example/ without pip install -e: use the repo's package (includes proxy helpers).
_repo_root = Path(__file__).resolve().parents[1]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from selenium.common.exceptions import NoSuchWindowException
from selenium.webdriver.common.by import By

import undetected_chromedriver as uc
from undetected_chromedriver import (
    fetch_direct_public_ip,
    normalize_proxy_url,
    parse_ipify_json_text,
    verify_proxy_egress,
)


def resolve_proxy(cli_proxy: Optional[str]) -> Optional[str]:
    if cli_proxy and cli_proxy.strip():
        return normalize_proxy_url(cli_proxy.strip())
    raw = (os.environ.get("UC_PROXY") or os.environ.get("PROXY") or "").strip()
    return normalize_proxy_url(raw) if raw else None


def wait_for_browser_window(driver, timeout: float = 20.0) -> None:
    """Poll until Chrome exposes at least one window (avoids racing the first ``get``)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if driver.window_handles:
                return
        except Exception:
            pass
        time.sleep(0.15)
    raise RuntimeError(
        "Chrome did not open a window in time (or the session died). "
        "Check that the proxy is reachable, credentials are correct, and Chrome is not crashing."
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Open a page through a proxy (use uc.Chrome proxy_server=)."
    )
    parser.add_argument(
        "--proxy",
        default=None,
        help="Proxy URL (http://user:pass@host:port). Scheme optional; http:// is assumed.",
    )
    parser.add_argument(
        "--url",
        default="https://api.ipify.org?format=json",
        help="Page to open (default: ipify JSON for IP check). Ignored if --google.",
    )
    parser.add_argument(
        "--google",
        action="store_true",
        help="Open https://www.google.com instead of the default ipify URL.",
    )
    parser.add_argument(
        "--keep-open",
        action="store_true",
        help="Wait for Enter before closing the browser (so you can see the window).",
    )
    parser.add_argument(
        "--expected-ip",
        default=None,
        help="If set, browser egress must match this IP (from your provider).",
    )
    parser.add_argument(
        "--skip-direct-check",
        action="store_true",
        help="Do not fetch a direct (non-proxy) IP for comparison.",
    )
    args = parser.parse_args()

    proxy = resolve_proxy(args.proxy)
    if not proxy:
        print(
            "error: set --proxy or export UC_PROXY (or PROXY), e.g.\n"
            "  export UC_PROXY='http://user:pass@host:port'",
            file=sys.stderr,
        )
        return 2

    if args.google:
        open_url = "https://www.google.com"
        do_ipify_check = False
    else:
        open_url = args.url
        do_ipify_check = True

    direct_ip: Optional[str] = None
    if not args.skip_direct_check and do_ipify_check:
        direct_ip = fetch_direct_public_ip()
        if direct_ip:
            print("Direct egress (Python, no proxy): %s" % direct_ip, file=sys.stderr)
        else:
            print(
                "Could not fetch direct egress IP (offline or blocked); "
                "comparison will be limited.",
                file=sys.stderr,
            )

    driver = uc.Chrome(proxy_server=proxy)
    try:
        wait_for_browser_window(driver)
        print("Opening: %s" % open_url, file=sys.stderr)
        try:
            driver.get(open_url)
        except NoSuchWindowException as e:
            print(
                "Chrome lost its window during navigation (often: bad proxy, blocked TLS, or browser crash).\n"
                "Try the default ipify URL without --google, test the proxy in a normal browser, "
                "or run without a proxy to confirm Chrome starts.\n"
                "Original error: %s" % e,
                file=sys.stderr,
            )
            raise

        if args.google:
            print(
                "Google should be visible. Default script uses ipify.org for IP checks; "
                "omit --google to verify egress IP.",
                file=sys.stderr,
            )
            if args.keep_open:
                input("Press Enter to close the browser... ")
            return 0

        body = driver.find_element(By.TAG_NAME, "body").text
        print(body)
        browser_ip = parse_ipify_json_text(body)
        ok, report = verify_proxy_egress(
            browser_ip,
            direct_ip,
            args.expected_ip,
            direct_check_skipped=args.skip_direct_check,
        )
        print(report, file=sys.stderr)
        if args.keep_open:
            input("Press Enter to close the browser... ")
        return 0 if ok else 1
    finally:
        driver.quit()


if __name__ == "__main__":
    raise SystemExit(main())
