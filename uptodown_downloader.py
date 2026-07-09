"""
uptodown_downloader.py
======================
Downloads APK files from uptodown.com — NO authentication required,
NO Google account, NO AAS token.

Uptodown typically repackages App Bundle apps into a single universal
APK that works on all architectures (arm64-v8a, armeabi-v7a, x86, x86_64).
So instead of architecture variants, we expose VERSION variants:
the latest version + a handful of older versions, each with its own
download button.
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

    BASE = "https://en.uptodown.com"

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
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })

    # ------------------------------------------------------------------ #
    #  Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _slug_from_url(url: str) -> Optional[str]:
        """Extract the app slug from an Uptodown URL.

        Example: https://whatsapp-messenger.en.uptodown.com/android
                 -> 'whatsapp-messenger'
        """
        m = re.search(r"https?://([^.]+)\.[a-z]{2}\.uptodown\.com/android", url)
        if m:
            return m.group(1)
        return None

    def _get(self, url: str, timeout: int = 30) -> Optional[requests.Response]:
        try:
            r = self.session.get(url, timeout=timeout)
            r.raise_for_status()
            return r
        except Exception as exc:  # noqa: BLE001
            logger.exception("GET %s failed: %s", url, exc)
            return None

    # ------------------------------------------------------------------ #
    #  Search
    # ------------------------------------------------------------------ #
    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search uptodown.com for an app. Returns a list of dicts."""
        url = f"{self.BASE}/search?searchlang={UPTODOWN_LANG}&q={quote(query)}"
        r = self._get(url)
        if not r:
            return []

        soup = BeautifulSoup(r.text, "lxml")
        apps: List[Dict[str, Any]] = []
        seen_slugs = set()

        # Uptodown search layout: each result is a link to <slug>.<lang>.uptodown.com/android
        for a in soup.select("a[href*='.uptodown.com/android']"):
            href = a.get("href", "")
            slug = self._slug_from_url(href)
            if not slug or slug in seen_slugs:
                continue
            # Skip the main site / category links
            if "uptodown.com/android" not in href:
                continue
            # Title: look in nested elements
            title = ""
            for sel in ("h2", "h3", ".name", ".title", "[itemprop=name]"):
                el = a.select_one(sel)
                if el and el.get_text(strip=True):
                    title = el.get_text(strip=True)
                    break
            if not title:
                # Try title attribute on the link itself
                title = a.get("title", "") or slug.replace("-", " ").title()
            # Icon
            icon_el = a.select_one("img")
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

    # ------------------------------------------------------------------ #
    #  App info + versions
    # ------------------------------------------------------------------ #
    def get_app_info(self, slug_or_url: str) -> Optional[Dict[str, Any]]:
        """Fetch app info + available versions for an Uptodown app."""
        if "uptodown.com" in slug_or_url:
            slug = self._slug_from_url(slug_or_url)
            if not slug:
                return None
            url = slug_or_url.rstrip("/")
        else:
            slug = slug_or_url
            url = f"https://{slug}.{UPTODOWN_LANG}.uptodown.com/android"

        r = self._get(url)
        if not r:
            return None

        soup = BeautifulSoup(r.text, "lxml")

        # --- Title ---
        title = slug
        for sel in ("h1", ".app-name", "[itemprop=name]", "h1.name"):
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

        # --- Latest version info from the main download button ---
        latest_version_name = ""
        latest_version_id: Optional[str] = None
        latest_size = ""
        latest_min_android = ""

        # The main download button usually links to /download/<id> or has data-version-id
        dl_btn = soup.select_one("a#detail-download-button, a.download-button, a.button.download")
        if dl_btn:
            href = dl_btn.get("href", "")
            m = re.search(r"/(?:download|post-download)/(\d+)", href)
            if m:
                latest_version_id = m.group(1)
            # Also try data-url
            data_url = dl_btn.get("data-url", "")
            if not latest_version_id and data_url:
                m = re.search(r"/(\d+)", data_url)
                if m:
                    latest_version_id = m.group(1)

        # Version name (often shown near the download button as "Version X.Y.Z")
        for sel in (".version", ".app-version", "[data-version]", ".detail .version"):
            el = soup.select_one(sel)
            if el:
                txt = el.get_text(strip=True)
                if txt:
                    latest_version_name = txt
                    break

        # --- Versions list ---
        versions = self._parse_versions(soup, slug)

        # If we couldn't parse any versions but have a latest_version_id, use that
        if not versions and latest_version_id:
            versions = [{
                "version_id": latest_version_id,
                "version_name": latest_version_name or "Latest",
                "size": latest_size,
                "date": "",
                "min_android": latest_min_android,
                "is_latest": True,
            }]

        # Make sure the first version is marked as latest
        if versions:
            versions[0]["is_latest"] = True

        return {
            "slug": slug,
            "title": title,
            "developer": developer,
            "url": url,
            "versions": versions[:MAX_VERSIONS],
        }

    def _parse_versions(self, soup: BeautifulSoup, slug: str) -> List[Dict[str, Any]]:
        """Try to parse the versions list from the app page; if not present,
        fetch the dedicated /versions page."""
        versions = self._parse_versions_from_soup(soup)
        if versions:
            return versions

        # Fetch /versions page
        versions_url = f"https://{slug}.{UPTODOWN_LANG}.uptodown.com/android/versions"
        r = self._get(versions_url)
        if not r:
            return []
        soup2 = BeautifulSoup(r.text, "lxml")
        return self._parse_versions_from_soup(soup2)

    def _parse_versions_from_soup(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Parse a list of versions from a BeautifulSoup soup."""
        versions: List[Dict[str, Any]] = []
        # Uptodown version list: each item has a link to /download/<id>
        # and metadata about version name, size, date.
        candidates = soup.select(
            "#versions-items > div, "
            ".version-item, "
            "#versions-list li, "
            "div[data-version-id], "
            "div.version"
        )
        # Fallback: any link with /download/<id> in href
        if not candidates:
            candidates = []
            for a in soup.select("a[href*='/download/']"):
                # Wrap in a fake parent div for selector compatibility
                parent = a.find_parent()
                if parent and parent not in candidates:
                    candidates.append(parent)

        for v in candidates:
            # Find the version link
            link = v.select_one("a[href*='/download/']") or v.select_one("a[href*='/post-download/']")
            if not link:
                # Maybe v itself is an <a>
                if v.name == "a" and ("/download/" in v.get("href", "") or "/post-download/" in v.get("href", "")):
                    link = v
                else:
                    continue
            href = link.get("href", "")
            m = re.search(r"/(?:download|post-download)/(\d+)", href)
            if not m:
                continue
            version_id = m.group(1)
            if any(x["version_id"] == version_id for x in versions):
                continue

            # Extract version name, size, date — try multiple selector patterns
            version_name = ""
            for sel in (".version", ".name", "span.version", "h3", ".title"):
                el = v.select_one(sel)
                if el and el.get_text(strip=True):
                    txt = el.get_text(strip=True)
                    # Strip leading "Version " prefix
                    txt = re.sub(r"^Version\s+", "", txt, flags=re.I)
                    if txt and txt != "Download":
                        version_name = txt
                        break

            size = ""
            for sel in (".size", ".file-size", "span.size"):
                el = v.select_one(sel)
                if el and el.get_text(strip=True):
                    size = el.get_text(strip=True)
                    break

            date = ""
            for sel in (".date", ".release-date", "span.date", "time"):
                el = v.select_one(sel)
                if el and el.get_text(strip=True):
                    date = el.get_text(strip=True)
                    break

            min_android = ""
            for sel in (".min-android", ".requires", ".requirement"):
                el = v.select_one(sel)
                if el and el.get_text(strip=True):
                    min_android = el.get_text(strip=True)
                    break

            versions.append({
                "version_id": version_id,
                "version_name": version_name or f"v.{version_id}",
                "size": size,
                "date": date,
                "min_android": min_android,
                "is_latest": len(versions) == 0,
            })
        return versions

    # ------------------------------------------------------------------ #
    #  Download
    # ------------------------------------------------------------------ #
    def get_direct_download_url(self, slug: str, version_id: str) -> Optional[str]:
        """Resolve the direct .apk URL from a version's post-download page."""
        url = f"https://{slug}.{UPTODOWN_LANG}.uptodown.com/android/post-download/{version_id}"
        try:
            r = self.session.get(url, timeout=30, allow_redirects=False)
        except Exception as exc:  # noqa: BLE001
            logger.exception("post-download failed: %s", exc)
            return None

        # Uptodown usually responds with a redirect (302) to the actual file
        if r.status_code in (301, 302, 303, 307, 308):
            location = r.headers.get("Location", "")
            if location:
                return urljoin(url, location)

        # Otherwise parse the HTML for a data-url attribute
        try:
            soup = BeautifulSoup(r.text, "lxml")
        except Exception:
            return None

        # Common patterns: a download button with data-url
        for el in soup.select("[data-url]"):
            data_url = el.get("data-url", "")
            if data_url:
                return urljoin(url, data_url)

        # Or a meta refresh
        meta = soup.select_one("meta[http-equiv=refresh]")
        if meta:
            content = meta.get("content", "")
            m = re.search(r"url=(.+)$", content, re.I)
            if m:
                return urljoin(url, m.group(1).strip().strip("'\""))

        # Or a direct link
        for a in soup.select("a[href*='.apk'], a.download"):
            href = a.get("href", "")
            if href:
                return urljoin(url, href)

        return None

    def download_apk(self, slug: str, version_id: str) -> Optional[bytes]:
        """Download the APK file and return its raw bytes."""
        direct_url = self.get_direct_download_url(slug, version_id)
        if not direct_url:
            logger.error("Could not resolve direct download URL for %s v%s", slug, version_id)
            return None
        try:
            r = self.session.get(direct_url, timeout=300, stream=True)
            r.raise_for_status()
            # Read into memory (APK files are typically <200MB)
            content = b""
            for chunk in r.iter_content(chunk_size=65536):
                if chunk:
                    content += chunk
            if not content:
                logger.error("Empty download for %s v%s", slug, version_id)
                return None
            return content
        except Exception as exc:  # noqa: BLE001
            logger.exception("Download failed: %s", exc)
            return None
