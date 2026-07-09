"""
uptodown_downloader.py
======================
Downloads APK files from uptodown.com — NO authentication required,
NO Google account, NO AAS token.

How Uptodown's download actually works (reverse-engineered from their JS):
  1. Each version has a unique numeric ID (visible as data-version-id
     on the app page, e.g. 1185815794).
  2. Clicking the download button reveals an encrypted "data-url"
     attribute on the #detail-download-button element. This is NOT
     a real URL — it's a token.
  3. The real APK URL is:  https://dw.uptodown.com/dwn/<data-url>
     which 302-redirects to dw.uptodown.net and serves the .apk file.

So the flow is:
  - GET https://<slug>.uptodown.com/android  (app page, contains version list)
  - Parse version IDs + names from [data-version-id] elements
  - GET https://<slug>.uptodown.com/android/descargar/<version_id>
    to obtain the per-version data-url token
  - GET https://dw.uptodown.com/dwn/<data-url>
    which redirects to the actual .apk file
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup

from config import MAX_VERSIONS, UPTODOWN_LANG

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)


class UptodownDownloader:
    """Singleton wrapper around HTTP + BeautifulSoup for uptodown.com."""

    # NOTE: Uptodown's site is structured around the Spanish word "descargar"
    # (= "download"). Even on the English version, URL paths use /descargar/.
    # The search endpoint is /android/buscar (Spanish: "buscar" = "to search").

    _instance: Optional["UptodownDownloader"] = None

    @classmethod
    def get_instance(cls) -> "UptodownDownloader":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept-Language": f"{UPTODOWN_LANG},en;q=0.9",
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,*/*;q=0.8"
            ),
            "Accept-Encoding": "gzip, deflate, br",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Upgrade-Insecure-Requests": "1",
        })

    # ------------------------------------------------------------------ #
    #  Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _slug_from_url(url: str) -> Optional[str]:
        """Extract the app slug from an Uptodown URL.

        Examples:
            https://whatsapp-messenger.en.uptodown.com/android
            https://whatsapp-messenger.uptodown.com/android
            https://whatsapp-messenger.uptodown.com/android/versions
                 -> 'whatsapp-messenger'
        """
        m = re.search(
            r"https?://([^.]+)\.(?:[a-z]{2}\.)?uptodown\.com/android",
            url,
        )
        if m:
            return m.group(1)
        return None

    def _get(self, url: str, timeout: int = 30, allow_redirects: bool = True) -> Optional[requests.Response]:
        try:
            r = self.session.get(url, timeout=timeout, allow_redirects=allow_redirects)
            # Uptodown sometimes returns 410 for search but still serves
            # valid HTML in the body. We accept 200, 410 (search), and
            # only fail on 404/5xx.
            if r.status_code in (200, 410):
                return r
            if 400 <= r.status_code < 500 and r.status_code != 410:
                logger.warning("GET %s returned %s", url, r.status_code)
                return None
            r.raise_for_status()
            return r
        except Exception as exc:  # noqa: BLE001
            logger.exception("GET %s failed: %s", url, exc)
            return None

    # ------------------------------------------------------------------ #
    #  Search
    # ------------------------------------------------------------------ #
    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search uptodown.com for an app. Returns a list of dicts.

        Uptodown's real search endpoint is /android/buscar (Spanish "buscar").
        Despite returning HTTP 410, the body still contains the search
        results HTML.
        """
        # Sanitize query - uptodown doesn't like very long queries or
        # queries containing " - Apps on Google Play" (which we get when
        # the user sends a Play Store URL and we extract the page title).
        query = self._sanitize_search_query(query)
        if not query:
            return []

        url = f"https://www.uptodown.com/android/buscar?q={quote(query)}"
        r = self._get(url)
        if r is None:
            return []

        soup = BeautifulSoup(r.text, "lxml")
        apps: List[Dict[str, Any]] = []
        seen_slugs = set()

        # Each search result is an <a href="https://<slug>.uptodown.com/android">
        # (the URL ends with /android and the subdomain is the app slug).
        # Category links look like https://www.uptodown.com/android/juegos — we skip those.
        app_link_re = re.compile(
            r"^https?://([^.]+)\.uptodown\.com/android/?$"
        )
        for a in soup.select("a[href]"):
            href = a.get("href", "")
            m = app_link_re.match(href)
            if not m:
                continue
            slug = m.group(1)
            # Skip the "Uptodown App Store" self-promo
            if slug in ("uptodown-android", "uptodown-app-store"):
                continue
            if slug in seen_slugs:
                continue

            # Title: prefer the inner text, fall back to title attribute
            title = a.get_text(" ", strip=True)
            if not title or len(title) > 100:
                title_attr = a.get("title", "")
                # title attr is like "Descargar WhatsApp Messenger"
                title = re.sub(r"^Descargar\s+", "", title_attr, flags=re.I).strip()
            if not title:
                title = slug.replace("-", " ").title()

            # Icon
            icon_el = a.find("img")
            icon = ""
            if icon_el:
                icon = icon_el.get("src") or icon_el.get("data-src") or ""

            apps.append({
                "slug": slug,
                "title": title,
                "url": href,
                "icon": icon,
                "developer": "",
            })
            seen_slugs.add(slug)
            if len(apps) >= limit:
                break

        return apps

    @staticmethod
    def _sanitize_search_query(query: str) -> str:
        """Clean up a search query (especially Play Store titles).

        Uptodown search doesn't handle these well:
          - 'WhatsApp Messenger - Apps on Google Play'  ->  'WhatsApp Messenger'
          - 'com.whatsapp'                              ->  'whatsapp'
          - URLs                                        ->  extract slug
        """
        if not query:
            return ""
        # Strip " - Apps on Google Play" suffix that comes from Play Store titles
        query = re.sub(r"\s*[-–—]\s*Apps on Google Play\s*$", "", query, flags=re.I)
        # Strip bare package name prefix
        query = re.sub(r"^com\.([a-z0-9_]+)$", r"\1", query.strip(), flags=re.I)
        # Limit length
        query = query.strip()
        if len(query) > 80:
            query = query[:80]
        return query

    # ------------------------------------------------------------------ #
    #  App info + versions
    # ------------------------------------------------------------------ #
    def get_app_info(self, slug_or_url: str) -> Optional[Dict[str, Any]]:
        """Fetch app info + available versions for an Uptodown app."""
        if "uptodown.com" in slug_or_url:
            slug = self._slug_from_url(slug_or_url)
            if not slug:
                return None
        else:
            slug = slug_or_url

        url = f"https://{slug}.uptodown.com/android"
        r = self._get(url)
        if r is None:
            return None

        soup = BeautifulSoup(r.text, "lxml")

        # --- Title ---
        title = slug.replace("-", " ").title()
        for sel in ("#detail-app-name", "h1", ".app-name", "[itemprop=name]"):
            el = soup.select_one(sel)
            if el and el.get_text(strip=True):
                title = el.get_text(strip=True)
                break

        # --- Developer ---
        developer = ""
        for sel in ("[itemprop=author]", ".developer", ".author", ".publisher"):
            el = soup.select_one(sel)
            if el and el.get_text(strip=True):
                developer = el.get_text(strip=True)
                break

        # --- Parse versions ---
        versions = self._parse_versions(soup, slug)

        if not versions:
            return None

        # Mark the first as latest
        versions[0]["is_latest"] = True

        return {
            "slug": slug,
            "title": title,
            "developer": developer,
            "url": url,
            "versions": versions[:MAX_VERSIONS],
        }

    def _parse_versions(self, soup: BeautifulSoup, slug: str) -> List[Dict[str, Any]]:
        """Parse the versions list from the app page.

        Uptodown embeds each version as a div[data-version-id] element
        with text like:
          "apk 2.26.26.72 Android + 5.0 4 jul. 2026"
        """
        versions: List[Dict[str, Any]] = []

        # Each version is a div[data-version-id]
        # The div's data-url attribute links back to the app page,
        # but the version ID itself is what we need.
        for el in soup.select("[data-version-id]"):
            version_id = el.get("data-version-id", "")
            if not version_id or not version_id.isdigit():
                continue
            if any(v["version_id"] == version_id for v in versions):
                continue

            # The text content of the element typically looks like:
            # "apk 2.26.26.72 Android + 5.0 4 jul. 2026"
            # We want to extract version name + Android requirement + date.
            raw_text = el.get_text(" | ", strip=True)
            version_name = ""
            min_android = ""
            date = ""

            # Try to extract version name (looks like x.y.z)
            m = re.search(r"(\d+\.\d+\.\d+(?:\.\d+)?)", raw_text)
            if m:
                version_name = m.group(1)

            # Try to extract Android requirement
            m = re.search(r"Android\s*\+?\s*([\d.]+)", raw_text, re.I)
            if m:
                min_android = f"Android {m.group(1)}+"

            # Try to extract date (spanish months)
            m = re.search(
                r"(\d{1,2}\s+[a-zç]{3,4}\.?\s+\d{4})", raw_text, re.I
            )
            if m:
                date = m.group(1)

            if not version_name:
                version_name = f"v.{version_id}"

            versions.append({
                "version_id": version_id,
                "version_name": version_name,
                "size": "",
                "date": date,
                "min_android": min_android,
                "is_latest": len(versions) == 0,
            })

        return versions

    # ------------------------------------------------------------------ #
    #  Download
    # ------------------------------------------------------------------ #
    def _get_data_url_token(self, slug: str, version_id: str) -> Optional[str]:
        """Fetch the per-version data-url token from the descargar page.

        The page at https://<slug>.uptodown.com/android/descargar/<version_id>
        contains the #detail-download-button element with a data-url
        attribute that is the token we need.
        """
        url = f"https://{slug}.uptodown.com/android/descargar/{version_id}"
        r = self._get(url)
        if r is None:
            return None

        soup = BeautifulSoup(r.text, "lxml")
        # Try the main download button first
        btn = soup.select_one("#detail-download-button")
        if btn:
            data_url = btn.get("data-url", "")
            if data_url and len(data_url) > 20:
                return data_url

        # Fallback: any element with data-url that looks like an encrypted token
        for el in soup.select("[data-url]"):
            u = el.get("data-url", "")
            # The token is base64-ish, no http prefix, length > 50
            if u and not u.startswith("http") and len(u) > 50:
                return u

        return None

    def download_apk(self, slug: str, version_id: str) -> Optional[bytes]:
        """Download the APK file and return its raw bytes."""
        # Step 1: get the data-url token
        token = self._get_data_url_token(slug, version_id)
        if not token:
            logger.error("Could not get data-url token for %s v%s", slug, version_id)
            return None

        # Step 2: hit https://dw.uptodown.com/dwn/<token>
        # This 302-redirects to the actual APK file on dw.uptodown.net
        download_url = f"https://dw.uptodown.com/dwn/{token}"
        try:
            r = self.session.get(
                download_url,
                timeout=300,
                stream=True,
                allow_redirects=True,
            )
            r.raise_for_status()

            # Verify it's actually an APK (magic bytes: PK\x03\x04 = ZIP/APK)
            first_chunk = next(r.iter_content(chunk_size=65536), b"")
            if not first_chunk:
                logger.error("Empty response from %s", download_url)
                return None

            # If the response is HTML (e.g., another redirect page),
            # we got an error - bail out
            content_type = r.headers.get("content-type", "").lower()
            if "text/html" in content_type and not first_chunk.startswith(b"PK"):
                logger.error("Got HTML instead of APK from %s", download_url)
                return None

            # Read the rest
            content = first_chunk
            for chunk in r.iter_content(chunk_size=65536):
                if chunk:
                    content += chunk

            if not content or not content.startswith(b"PK"):
                logger.error(
                    "Downloaded file is not a valid APK (first bytes: %r)",
                    content[:8] if content else b"",
                )
                return None

            return content
        except Exception as exc:  # noqa: BLE001
            logger.exception("Download failed for %s v%s: %s", slug, version_id, exc)
            return None
