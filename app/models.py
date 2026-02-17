from dataclasses import dataclass
from pathlib import Path

@dataclass
class QuoteSegment:
    speaker: str | None
    text: str

@dataclass
class Quote:
    date: str
    timestamp: str
    url: str
    segments: list[QuoteSegment]
    raw_line: str
    source_file: Path
    line_number: int

@dataclass
class QuoteIndex:
    date: str
    timestamp: str
    url: str
    source_file: Path
    line_number: int

    def __hash__(self):
        return hash((self.date, self.timestamp, self.url, self.source_file, self.line_number))

    def __eq__(self, other):
        if not isinstance(other, QuoteIndex):
            return False
        return (self.date, self.timestamp, self.url, self.source_file, self.line_number) == (
            other.date, other.timestamp, other.url, other.source_file, other.line_number
        )