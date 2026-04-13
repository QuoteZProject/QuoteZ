from pathlib import Path
import json
from .parser import HEADER_RE, parse_quote_line
from .models import QuoteIndex, Quote, QuoteSegment
from .settings import Settings
from .xdg_data import get_config_file, get_data_dir, is_flatpak, get_resource_file

_package_root = Path(__file__).resolve().parent.parent
default_avatar = get_resource_file("default.png", package_root=_package_root)

class QuoteStorage:
    def __init__(self):
        # package root
        self._package_root = Path(__file__).resolve().parent.parent

        # config path
        self.config_path = get_config_file(
            filename="settings.json", package_root=self._package_root
        )

        # load settings
        self.settings = Settings(self.config_path)

        # determine root
        configured_location = self.settings.data.get("quotez_location", None)

        if configured_location:
            # use configured path
            candidate = Path(configured_location)

            # expand user
            candidate = candidate.expanduser()
            if candidate.is_absolute():
                self.root = candidate.resolve()
            else:
                # handle relative path
                if is_flatpak():
                    # flatpak: path relative to xdg data
                    self.root = (get_data_dir(package_root=self._package_root) / candidate).resolve()
                else:
                    # local: resolve relative to config or cwd
                    try:
                        self.root = (self.config_path.parent / candidate).resolve()
                    except Exception:
                        self.root = (Path.cwd() / candidate).resolve()
        else:
            # no configured location
            if is_flatpak():
                # flatpak default
                self.root = get_data_dir(package_root=self._package_root)
            else:
                # local default
                self.root = (self._package_root / "quotez").resolve()

        # ensure root dir exists
        if not self.root.is_dir():
            # set default_dir
            if is_flatpak():
                default_dir = get_data_dir(package_root=self._package_root)
            else:
                default_dir = (self._package_root / "quotez").resolve()
                default_dir.mkdir(parents=True, exist_ok=True)

            # try saving path in settings
            try:
                if is_flatpak():
                    self.settings.data["quotez_location"] = str(default_dir)
                    self.settings.save()
                else:
                    try:
                        rel = default_dir.relative_to(Path.cwd())
                        self.settings.data["quotez_location"] = str(rel)
                        self.settings.save()
                    except Exception:
                        self.settings.data["quotez_location"] = str(default_dir)
                        self.settings.save()
            except Exception:
                # ignore save errors
                pass

            self.root = default_dir

        self.base_path = self.root
        self.index: list[QuoteIndex] = []
        self.people: dict[str, Path] = {}

    # reload settings and rebuild index
    def load_index(self):
        # reload settings
        try:
            self.settings = Settings(self.config_path)
        except Exception:
            # log exception if needed
            raise

        # resolve root from settings
        raw = self.settings.data.get("quotez_location", "quotez")
        configured = Path(raw).expanduser()

        if not configured.is_absolute():
            if is_flatpak():
                # flatpak: use data dir
                configured = (get_data_dir(package_root=self._package_root) / configured).resolve()
            else:
                # local: resolve relative to config or cwd
                try:
                    configured = (self.config_path.parent / configured).resolve()
                except Exception:
                    configured = (Path.cwd() / configured).resolve()

        if configured != self.root:
            # ensure absolute path
            try:
                if not configured.is_absolute():
                    configured = (Path.cwd() / configured).resolve()
            except Exception:
                configured = configured.resolve()

            # create dir or fallback
            try:
                if not configured.is_dir():
                    configured.mkdir(parents=True, exist_ok=True)
            except Exception:
                # fallback dir
                if is_flatpak():
                    configured = get_data_dir(package_root=self._package_root)
                else:
                    configured = self._package_root / "quotez"
                    configured.mkdir(parents=True, exist_ok=True)

            self.root = configured

        # clear in-memory data
        self.index.clear()
        self.people.clear()

        # stop if root missing
        if not self.root.exists():
            return

        # scan filesystem for quotes
        for folder in self.root.iterdir():
            if not folder.is_dir():
                continue

            qfile = folder / "quotes.jsonl"

            # skip if missing quotes file
            if not qfile.exists():
                continue

            avatar = folder / "avatar.png"
            self.people[folder.name] = (
                avatar if avatar.exists() else default_avatar
            )

            # read file safely
            try:
                with qfile.open(encoding="utf-8") as f:
                    for i, line in enumerate(f):
                        # Skip empty or whitespace-only lines
                        if not line.strip():
                            continue
                        
                        try:
                            # Parse JSONL line
                            data = json.loads(line.strip())
                            metadata = data.get("metadata", {})
                            date = metadata.get("date", "")
                            time = metadata.get("time", "")
                            url = metadata.get("url", "")
                            timestamp = metadata.get("timestamp", "")
                            tags = metadata.get("tags", [])
                            note = metadata.get("note", "")
                            
                            self.index.append(
                                QuoteIndex(
                                    date,
                                    time,
                                    url,
                                    timestamp,
                                    tags,
                                    note,
                                    qfile,
                                    i
                                )
                            )
                        except json.JSONDecodeError:
                            # Skip invalid JSON lines
                            continue
            except (FileNotFoundError, OSError):
                # file gone skip
                continue

    # load single quote
    def load_quote(self, idx: QuoteIndex):
        # reload index if missing
        if not idx.source_file.exists():
            # reload to refresh state
            self.load_index()
            return None

        try:
            with idx.source_file.open(encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if i == idx.line_number:
                        try:
                            data = json.loads(line.strip())
                            return self._parse_json_quote(data, idx.source_file, i)
                        except json.JSONDecodeError:
                            # If this line could not be parsed as JSON, fallback to legacy parser
                            return parse_quote_line(line, idx.source_file, i)
        except (FileNotFoundError, OSError):
            # file disappeared reload index
            self.load_index()
            return None

        return None

    def _parse_json_quote(self, data, source_file, line_no):
        """Parses a JSON quote object into a Quote model."""
        # Extract metadata
        metadata = data.get("metadata", {})
        date = metadata.get("date", "")
        time = metadata.get("time", "")
        url = metadata.get("url", "")
        timestamp = metadata.get("timestamp", "")
        tags = metadata.get("tags", [])
        note = metadata.get("note", "")
        
        # Extract quotes
        quote_data = data.get("quote", [])
        segments = []
        for item in quote_data:
            speaker = item.get("speaker", None)
            text = item.get("text", "")
            segments.append(QuoteSegment(speaker, text))
        
        # Create a quote object with new fields
        quote = Quote(
            date=date,
            time=time,
            url=url,
            timestamp=timestamp,
            tags=tags,
            note=note,
            segments=segments,
            raw_line=json.dumps(data),
            source_file=source_file,
            line_number=line_no
        )
        return quote

    def quote_key(self, quote: Quote) -> tuple[str, str, str, str]:
        text = "".join(seg.text for seg in quote.segments)
        return (quote.date, quote.timestamp, quote.url, text)

    # quote counts
    def get_quote_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}

        for idx in self.index:
            # skip stale
            if not idx.source_file.exists():
                continue

            person = idx.source_file.parent.name
            counts[person] = counts.get(person, 0) + 1

        for person in self.people:
            counts.setdefault(person, 0)

        return counts

    # groups
    def load_groups(self):
        # build mapping group->members
        groups: dict[str, list[str]] = {}

        # return empty if root missing
        if not self.root or not self.root.exists():
            return groups

        for folder in self.root.iterdir():
            if not folder.is_dir():
                continue

            attr_file = folder / "attributes.json"
            try:
                if attr_file.exists():
                    with attr_file.open("r", encoding="utf-8") as f:
                        data = json.load(f)
                    person_groups = data.get("groups", []) or []
                else:
                    person_groups = []
            except Exception:
                # skip corrupt attributes
                person_groups = []

            for g in person_groups:
                groups.setdefault(g, []).append(folder.name)

        return groups