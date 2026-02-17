import re
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from typing import Optional, Tuple

# helpers
def _hms_to_seconds(h: int, m: int, s: int) -> int:
    return h * 3600 + m * 60 + s

def seconds_to_hms_string(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:03}:{m:02}:{s:02}"

# YouTube support
class YouTubePlatform:
    YT_DOMAINS = ("youtube.com", "www.youtube.com", "youtu.be", "m.youtube.com")

    def extract_seconds(self, url: str) -> Optional[int]:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        if "t" in qs:
            t = qs["t"][0]
            if t.isdigit():
                return int(t)
            # support 1h2m3s
            m = re.match(r'(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$', t)
            if m:
                h = int(m.group(1) or 0)
                mm = int(m.group(2) or 0)
                s = int(m.group(3) or 0)
                return _hms_to_seconds(h, mm, s)
        return None

    def insert_seconds(self, url: str, seconds: int) -> str:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        if "t" in qs:
            return url  # keep existing
        qs["t"] = [str(seconds)]
        # rebuild query
        query = urlencode({k: v[0] for k, v in qs.items()}, doseq=False)
        new = parsed._replace(query=query)
        return urlunparse(new)

# Twitch support
class TwitchPlatform:
    TWITCH_DOMAINS = ("twitch.tv", "www.twitch.tv")
    TWITCH_TS_RE = re.compile(r't=(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?')

    def extract_seconds(self, url: str) -> Optional[int]:
        m = self.TWITCH_TS_RE.search(url)
        if not m:
            return None
        h = int(m.group(1) or 0)
        mm = int(m.group(2) or 0)
        s = int(m.group(3) or 0)
        return _hms_to_seconds(h, mm, s)

    def insert_seconds(self, url: str, seconds: int) -> str:
        parsed = urlparse(url)
        if "t=" in parsed.query:
            return url
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        tparam = f"t={h}h{m}m{s}s"
        if parsed.query:
            new_query = parsed.query + "&" + tparam
        else:
            new_query = tparam
        new = parsed._replace(query=new_query)
        return urlunparse(new)

# registry
_YT = YouTubePlatform()
_TW = TwitchPlatform()
PLATFORMS = [_YT, _TW]

def find_timestamp_seconds(url: str) -> Tuple[Optional[int], str]:
    """
    Try to extract a timestamp (seconds) from the url.
    Returns (seconds_or_None, original_url).
    """
    # try youtube first
    try:
        sec = _YT.extract_seconds(url)
        if sec is not None:
            return sec, url
    except Exception:
        log.exception("sec = _YT.extract_seconds(url) failed")
        raise
    try:
        sec = _TW.extract_seconds(url)
        if sec is not None:
            return sec, url
    except Exception:
        log.exception("sec = _TW.extract_seconds(url)")
        raise
    return None, url

def ensure_timestamp_in_url(url: str, seconds: int) -> str:
    """
    Insert a platform-appropriate timestamp into the URL if none exists.
    Currently supports YouTube and Twitch. If platform unknown, return original URL.
    """
    parsed = urlparse(url)
    domain = (parsed.netloc or "").lower()

    if any(d in domain for d in YouTubePlatform.YT_DOMAINS):
        return _YT.insert_seconds(url, seconds)
    if any(d in domain for d in TwitchPlatform.TWITCH_DOMAINS):
        return _TW.insert_seconds(url, seconds)
    return url