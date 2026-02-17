import re
from typing import List, Set, Optional
from urllib.parse import urlparse

_TS_MASK_RE = re.compile(r'^(\d{3}):(\d{2}):(\d{2})$')
_COLON_TAG_RE = re.compile(r':([^:]+):')
_QUOTE_TAG_RE = re.compile(r'\{quote:"([^"]+)"\}')

_ALLOWED_SCHEMES = {"http", "https"}

# Timestamp
def parse_masked_timestamp(mask_text: str) -> Optional[int]:
    if not mask_text:
        return None

    t = mask_text.strip()
    m = _TS_MASK_RE.match(t)
    if not m:
        return None

    h = int(m.group(1))
    mm = int(m.group(2))
    ss = int(m.group(3))

    if mm < 0 or mm > 59 or ss < 0 or ss > 59:
        return None

    return h * 3600 + mm * 60 + ss


def seconds_to_mask_string(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:03}:{m:02}:{s:02}"


# URL
def is_valid_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return False
        return parsed.scheme.lower() in _ALLOWED_SCHEMES
    except Exception:
        return False


# Tag handling
def find_colon_tags(text: str) -> List[str]:
    return [m.group(1) for m in _COLON_TAG_RE.finditer(text)]


def find_quote_tag_names(text: str) -> List[str]:
    return [m.group(1) for m in _QUOTE_TAG_RE.finditer(text)]


def ensure_first_is_quote_tag(text: str) -> bool:
    s = text.lstrip()
    return bool(s.startswith('{quote:"'))


def names_to_create_from_colon_tags(text: str, existing_people: Set[str]) -> Set[str]:
    names = set(find_colon_tags(text))
    return {n for n in names if n not in existing_people}


# Newline removal
def remove_newlines(text: str) -> str:
    # Replace newlines with a single space
    if not text:
        return text

    # Normalize Windows/Mac line endings
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    return text.replace("\n", " ")


# Space normalization
def remove_one_space_around_tags(text: str) -> str:
    # Remove one space immediately before/after each {quote:"name"} tag
    result = []
    i = 0

    for match in _QUOTE_TAG_RE.finditer(text):
        start, end = match.span()

        before = text[i:start]

        # remove exactly one trailing space
        if before.endswith(" "):
            before = before[:-1]

        result.append(before)
        result.append(match.group())
        i = end

        # remove exactly one leading space
        if i < len(text) and text[i] == " ":
            i += 1

    result.append(text[i:])
    return "".join(result)


def replace_colon_tags_with_quote_tags(text: str, convert_names: Set[str]) -> str:
    # remove newlines first
    text = remove_newlines(text)

    out_parts = []
    pos = 0

    for m in _COLON_TAG_RE.finditer(text):
        start, end = m.span()
        name = m.group(1)

        out_parts.append(text[pos:start])

        if name in convert_names:
            out_parts.append(f'{{quote:"{name}"}}')
        else:
            out_parts.append(text[start:end])

        pos = end

    out_parts.append(text[pos:])

    result = "".join(out_parts)

    # normalize spacing once
    result = remove_one_space_around_tags(result)

    return result


# Quote content validation
def has_real_text_outside_tags(text: str) -> bool:
    # True if there is non-whitespace text outside {quote:"name"} tags
    if not text:
        return False

    text_without_tags = _QUOTE_TAG_RE.sub("", text)
    return bool(text_without_tags.strip())