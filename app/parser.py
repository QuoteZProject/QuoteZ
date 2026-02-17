import re
from .models import Quote, QuoteSegment

HEADER_RE = re.compile(
    r'^\[(\d{4}-\d{2}-\d{2});(\d{3}:\d{2}:\d{2});([^\]]+)\]'
)
TAG_RE = re.compile(r'\{quote:"([^"]+)"\}')

def parse_quote_line(line, source_file, line_no):
    m = HEADER_RE.match(line)
    if not m:
        return None

    date, ts, url = m.groups()
    body = line[m.end():].rstrip("\r\n")

    segments = []
    pos = 0
    current_speaker = None

    for tag in TAG_RE.finditer(body):
        text = body[pos:tag.start()]
        if text:
            segments.append(QuoteSegment(current_speaker, text))
        current_speaker = tag.group(1)
        pos = tag.end()

    tail = body[pos:]
    if tail:
        segments.append(QuoteSegment(current_speaker, tail))

    if not segments:
        segments.append(QuoteSegment(None, ""))

    return Quote(
        date=date,
        timestamp=ts,
        url=url,
        segments=segments,
        raw_line=line.strip(),
        source_file=source_file,
        line_number=line_no
    )
