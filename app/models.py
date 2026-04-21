from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

@dataclass
class QuoteSegment:
    speaker: str | None
    text: str

@dataclass
class Quote:
    date: str
    url: str
    timestamp: str
    tags: List[str]
    note: str
    segments: list[QuoteSegment]
    raw_line: str
    source_file: Path
    line_number: int
    # New field to track person tags separately
    global_tags: List[str] = None

@dataclass
class QuoteIndex:
    date: str
    url: str
    timestamp: str
    tags: List[str]
    note: str
    source_file: Path
    line_number: int

    def __hash__(self):
        return hash((self.date, self.url, self.timestamp, tuple(self.tags), self.note, self.source_file, self.line_number))

    def __eq__(self, other):
        if not isinstance(other, QuoteIndex):
            return False
        return (self.date, self.url, self.timestamp, tuple(self.tags), self.note, self.source_file, self.line_number) == (
            other.date, other.url, other.timestamp, tuple(other.tags), other.note, other.source_file, other.line_number
        )