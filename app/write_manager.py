from pathlib import Path
import json
import shutil
import re
from typing import Optional, List

from .quote_utils import find_quote_tag_names
from .avatar_manager import avatarManager


class QuoteModifier:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

        self.avatar_manager = avatarManager(self.root)

    # Quote methods
    def _build_json_line(self, date: str, time: str, url: str, timestamp: str, tags: List[str], note: str, text: str) -> str:
        """Constructs a JSONL line for a quote"""
        # Parse the text to extract segments
        segments = []
        pos = 0
        current_speaker = None
        tag_re = re.compile(r'\{quote:"([^"]+)"\}')
        
        for tag in tag_re.finditer(text):
            # Extract any text before this tag
            text_before = text[pos:tag.start()]
            if text_before:
                segments.append({"speaker": current_speaker, "text": text_before})
            # Extract speaker
            current_speaker = tag.group(1)
            pos = tag.end()
        
        # Add remaining text after last tag
        final_text = text[pos:]
        if final_text:
            segments.append({"speaker": current_speaker, "text": final_text})
        
        # Construct metadata
        metadata = {
            "date": date,
            "time": time,
            "url": url,
            "timestamp": timestamp,
            "tags": tags,
            "note": note
        }

        metadata = {k: v for k, v in metadata.items() if v}
        
        # Construct JSON structure
        data = {
            "metadata": metadata,
            "quote": segments
        }
        
        return json.dumps(data, ensure_ascii=False) + "\n"

    def add_quote(self, date: str, time: str, url: str, timestamp: str, tags: List[str], note: str, text: str):
        if not text.startswith('{quote:'):
            raise ValueError('Quote must start with {quote:"name"}')

        speakers = set(find_quote_tag_names(text))
        if not speakers:
            raise ValueError("No speaker tags found")

        line = self._build_json_line(date, time, url, timestamp, tags, note, text)

        for speaker in speakers:
            folder = self.root / speaker
            folder.mkdir(parents=True, exist_ok=True)
            qfile = folder / "quotes.jsonl"

            with qfile.open("a", encoding="utf-8") as f:
                f.write(line)

    def find_quote_line(self, date: str, time: str, url: str, timestamp: str, tags: List[str], note: str) -> tuple[str, int] | None:
        """Find a specific quote line in all files and return (line_content, line_number) or None"""
        for folder in self.root.iterdir():
            if not folder.is_dir():
                continue

            qfile = folder / "quotes.jsonl"
            if not qfile.exists():
                continue

            lines = qfile.read_text(encoding="utf-8").splitlines()
            for i, line in enumerate(lines):
                try:
                    data = json.loads(line.strip())
                    if "metadata" in data:
                        metadata = data["metadata"]
                        
                        old_date = metadata.get("date", "")
                        old_time = metadata.get("time", "")
                        old_url = metadata.get("url", "")
                        old_timestamp = metadata.get("timestamp", "")
                        old_tags = metadata.get("tags", [])
                        old_note = metadata.get("note", "")
                        
                        if (old_date == date and old_time == time and old_url == url and 
                            old_timestamp == timestamp and old_tags == tags and old_note == note):
                            return line, i
                except (json.JSONDecodeError, Exception):
                    continue
        return None

    def remove_quote(self, date: str, time: str, url: str, timestamp: str, tags: List[str], note: str):
        # Find and remove the specific quote line
        for folder in self.root.iterdir():
            if not folder.is_dir():
                continue

            qfile = folder / "quotes.jsonl"
            if not qfile.exists():
                continue

            lines = qfile.read_text(encoding="utf-8").splitlines()
            new_lines = []
            found_and_removed = False
            
            for line in lines:
                try:
                    data = json.loads(line.strip())
                    if "metadata" in data:
                        metadata = data["metadata"]
                        
                        old_date = metadata.get("date", "")
                        old_time = metadata.get("time", "")
                        old_url = metadata.get("url", "")
                        old_timestamp = metadata.get("timestamp", "")
                        old_tags = metadata.get("tags", [])
                        old_note = metadata.get("note", "")
                        
                        if (old_date == date and old_time == time and old_url == url and 
                            old_timestamp == timestamp and old_tags == tags and old_note == note):
                            found_and_removed = True
                            continue  # Skip this line (remove the quote)
                        else:
                            new_lines.append(line)
                    else:
                        new_lines.append(line)
                except (json.JSONDecodeError, Exception):
                    new_lines.append(line)

            if found_and_removed:
                qfile.write_text(
                    "\n".join(new_lines) + ("\n" if new_lines else ""),
                    encoding="utf-8"
                )

    def edit_quote(
        self,
        old_date: str,
        old_time: str,
        old_url: str,
        old_timestamp: str,
        old_tags: List[str],
        old_note: str,
        new_date: str,
        new_time: str,
        new_url: str,
        new_timestamp: str,
        new_tags: List[str],
        new_note: str,
        new_text: str,
    ):
        # Find the original quote line and update it in-place
        for folder in self.root.iterdir():
            if not folder.is_dir():
                continue

            qfile = folder / "quotes.jsonl"
            if not qfile.exists():
                continue

            lines = qfile.read_text(encoding="utf-8").splitlines()
            new_lines = []
            found_and_updated = False
            
            for line in lines:
                try:
                    data = json.loads(line.strip())
                    if "metadata" in data:
                        metadata = data["metadata"]
                        
                        old_date_check = metadata.get("date", "")
                        old_time_check = metadata.get("time", "")
                        old_url_check = metadata.get("url", "")
                        old_timestamp_check = metadata.get("timestamp", "")
                        old_tags_check = metadata.get("tags", [])
                        old_note_check = metadata.get("note", "")
                        
                        # Check if this is the quote line we're looking to edit
                        if (old_date_check == old_date and old_time_check == old_time and 
                            old_url_check == old_url and old_timestamp_check == old_timestamp and 
                            old_tags_check == old_tags and old_note_check == old_note):
                            # This is the quote we want to edit - update its metadata
                            new_metadata_raw = {
                                "date": new_date,
                                "time": new_time,
                                "url": new_url,
                                "timestamp": new_timestamp,
                                "tags": new_tags,
                                "note": new_note
                            }

                            # Ensures we DON'T introduce empty keys into the JSONL
                            data["metadata"] = {k: v for k, v in new_metadata_raw.items() if v}
                            
                            # Update the quote segments with the new text
                            segments = []
                            pos = 0
                            current_speaker = None
                            tag_re = re.compile(r'\{quote:"([^"]+)"\}')
                            
                            for tag in tag_re.finditer(new_text):
                                text_before = new_text[pos:tag.start()]
                                if text_before:
                                    segments.append({"speaker": current_speaker, "text": text_before})
                                # Extract speaker
                                current_speaker = tag.group(1)
                                pos = tag.end()
                            
                            # Add remaining text after last tag
                            final_text = new_text[pos:]
                            if final_text:
                                segments.append({"speaker": current_speaker, "text": final_text})
                            
                            data["quote"] = segments
                            
                            # Update the line
                            new_lines.append(json.dumps(data, ensure_ascii=False))
                            found_and_updated = True
                        else:
                            new_lines.append(line)
                    else:
                        new_lines.append(line)
                except (json.JSONDecodeError, Exception):
                    new_lines.append(line)
            
            if found_and_updated:
                qfile.write_text(
                    "\n".join(new_lines) + ("\n" if new_lines else ""),
                    encoding="utf-8"
                )
                return  # We've found and updated the correct quote

        # If we get here, we didn't find the quote to edit - that's an issue
        raise ValueError("Quote not found for editing")

    # Person methods
    def _person_exists(self, name: str) -> bool:
        return (self.root / name).exists()

    def add_person(self, name: str, avatar_path: Optional[Path] = None):
        if self._person_exists(name):
            raise ValueError(f"Person '{name}' already exists")

        folder = self.root / name
        folder.mkdir(parents=True, exist_ok=False)

        # Create the quotes.jsonl file
        qfile = folder / "quotes.jsonl"
        qfile.write_text("", encoding="utf-8")

        if avatar_path:
            self.avatar_manager.set_avatar(name, avatar_path)

    def set_person_avatar(self, name: str, avatar_path: Path):
        return self.avatar_manager.set_avatar(name, avatar_path)

    def remove_person_avatar(self, name: str):
        return self.avatar_manager.remove_avatar(name)

    # Nickname methods
    # return nicknames for person from attributes.json or [] on error
    def get_nicknames(self, person: str) -> List[str]:
        attr_file = self.root / person / "attributes.json"
        try:
            if attr_file.exists():
                data = json.loads(attr_file.read_text(encoding="utf-8"))
            else:
                data = {}
        except Exception:
            # best-effort: if file is corrupt/unreadable, return empty
            try:
                log.exception("Failed to read attributes.json for %s", person)
            except Exception:
                pass
            data = {}
        nicks = data.get("nicknames", []) or []
        return [str(n) for n in nicks if n is not None]

    # overwrite nicknames in attributes.json, preserve other keys
    def set_nicknames(self, person: str, nicknames: List[str]):
        attr_file = self.root / person / "attributes.json"
        try:
            existing = json.loads(attr_file.read_text(encoding="utf-8")) if attr_file.exists() else {}
        except Exception:
            try:
                log.exception("Failed to parse attributes.json for %s", person)
            except Exception:
                pass
            existing = {}

        # sanitize: strip, drop empty, unique preserving order
        cleaned: List[str] = []
        seen = set()
        for n in (nicknames or []):
            s = (n or "").strip()
            if not s:
                continue
            if s in seen:
                continue
            seen.add(s)
            cleaned.append(s)

        existing["nicknames"] = cleaned

        try:
            attr_file.write_text(json.dumps(existing, indent=4, ensure_ascii=False), encoding="utf-8")
        except Exception:
            try:
                log.exception("Failed to write attributes.json for %s", person)
            except Exception:
                pass
            raise

    # remove speaker {quote:"name"} segments including their text
    def _remove_speaker_from_line(self, line: str, speaker: str) -> str:
        pattern = r'(\{quote:"([^"]+)"\})'
        parts = re.split(pattern, line)

        if len(parts) <= 1:
            return line

        rebuilt = parts[0]
        i = 1

        while i < len(parts):
            full_tag = parts[i]
            name = parts[i + 1]
            text_after = parts[i + 2]

            if name != speaker:
                rebuilt += full_tag + text_after

            i += 3

        return rebuilt

    def remove_person(self, name: str):
        if not self._person_exists(name):
            return

        # remove speaker from all quote files
        for folder in self.root.iterdir():
            if not folder.is_dir():
                continue

            qfile = folder / "quotes.jsonl"
            if not qfile.exists():
                continue

            lines = qfile.read_text(encoding="utf-8").splitlines()
            new_lines = []

            for line in lines:
                updated = self._remove_speaker_from_line(line, name)

                # Keep line only if it still contains quotes
                if '{quote:' in updated:
                    new_lines.append(updated)

            qfile.write_text(
                "\n".join(new_lines) + ("\n" if new_lines else ""),
                encoding="utf-8"
            )

        # remove their folder
        person_folder = self.root / name
        if person_folder.exists():
            shutil.rmtree(person_folder)

    def rename_person(self, old: str, new: str):
        if old == new:
            return

        if not self._person_exists(old):
            raise ValueError(f"Person '{old}' does not exist")

        if self._person_exists(new):
            raise ValueError(f"Person '{new}' already exists")

        old_folder = self.root / old
        new_folder = self.root / new
        new_folder.mkdir(parents=True, exist_ok=False)

        # update .jsonl files
        for folder in self.root.iterdir():
            if not folder.is_dir():
                continue

            qfile = folder / "quotes.jsonl"
            if not qfile.exists():
                continue

            content = qfile.read_text(encoding="utf-8")
            if f'{"speaker": "{old},"}' in content:
                content = content.replace(
                    f'{"speaker": "{old},"}',
                    f'{"speaker": "{new},"}'
                )
                qfile.write_text(content, encoding="utf-8")

        # move quotes file
        old_file = old_folder / "quotes.jsonl"
        new_file = new_folder / "quotes.jsonl"

        if old_file.exists():
            shutil.move(str(old_file), str(new_file))

        # move avatar
        old_avatar = old_folder / "avatar.png"
        new_avatar = new_folder / "avatar.png"

        if old_avatar.exists():
            shutil.move(str(old_avatar), str(new_avatar))

        # move attributes
        old_attr = old_folder / "attributes.json"
        new_attr = new_folder / "attributes.json"

        if old_attr.exists():
            shutil.move(str(old_attr), str(new_attr))

        # remove old folder
        try:
            old_folder.rmdir()
        except Exception:
            log.exception("old_folder.rmdir() failed")
            raise

    # Group methods
    # build map group -> [members] by scanning attributes.json
    def _load_groups(self) -> dict:
        groups: dict[str, list[str]] = {}

        for folder in self.root.iterdir():
            if not folder.is_dir():
                continue

            name = folder.name
            attr_file = folder / "attributes.json"

            try:
                if attr_file.exists():
                    data = json.loads(attr_file.read_text(encoding="utf-8"))
                    person_groups = data.get("groups", []) or []
                else:
                    person_groups = []
            except Exception:
                person_groups = []

            for g in person_groups:
                groups.setdefault(g, []).append(name)

        return groups

    # write group -> [members] by updating each person's attributes.json
    def _save_groups(self, data: dict):
        # Build reverse mapping: person -> [groups]
        person_to_groups: dict[str, list[str]] = {}
        for group, members in data.items():
            for m in members:
                person_to_groups.setdefault(m, []).append(group)

        # Ensure deterministic ordering
        for m, gl in person_to_groups.items():
            person_to_groups[m] = sorted(gl)

        # Update each person's attributes.json
        for folder in self.root.iterdir():
            if not folder.is_dir():
                continue

            name = folder.name
            attr_file = folder / "attributes.json"

            try:
                existing = json.loads(attr_file.read_text(encoding="utf-8")) if attr_file.exists() else {}
            except Exception:
                existing = {}

            # Set groups for this person (empty list if none)
            existing['groups'] = person_to_groups.get(name, [])

            # Ensure nicknames key remains present if it was present (preserve content)
            if 'nicknames' not in existing:
                existing['nicknames'] = existing.get('nicknames', [])

            try:
                attr_file.write_text(
                    json.dumps(existing, indent=4, ensure_ascii=False),
                    encoding="utf-8"
                )
            except Exception:
                # Best-effort: skip writing failures silently
                log.exception("Failed to write attributes.json for %s", name)

    def add_group(self, name: str, members: Optional[List[str]] = None):
        data = self._load_groups()
        if name in data:
            raise ValueError(f"Group '{name}' already exists")

        data[name] = members or []
        self._save_groups(data)

    def remove_group(self, name: str):
        data = self._load_groups()
        if name not in data:
            return
        del data[name]
        self._save_groups(data)

    def edit_group(self, name: str, members: List[str]):
        data = self._load_groups()
        if name not in data:
            raise ValueError(f"Group '{name}' does not exist")
        data[name] = members
        self._save_groups(data)

    def rename_group(self, old: str, new: str):
        if old == new:
            return

        data = self._load_groups()
        if old not in data:
            raise ValueError(f"Group '{old}' does not exist")
        if new in data:
            raise ValueError(f"Group '{new}' already exists")

        # Move member list to new name
        data[new] = data.pop(old)
        self._save_groups(data)