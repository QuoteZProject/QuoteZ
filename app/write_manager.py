from pathlib import Path
import json
import shutil
import re
from typing import Optional, List
from collections import OrderedDict

from .quote_utils import find_quote_tag_names
from .avatar_manager import avatarManager


class QuoteModifier:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

        self.avatar_manager = avatarManager(self.root)

    # Quote methods
    def write_quote(self, metadata: Dict[str, any], quote: List[Dict[str, str]]) -> None:

        metadata = {k: v for k, v in metadata.items() if v is not None and v != ""}
        data = {"metadata": metadata,"quote": quote}
        line = json.dumps(data, ensure_ascii=False) + "\n"
        
        # Write to each speaker's file
        speakers = set()
        for segment in quote:
            speaker = segment.get('speaker')
            text = segment.get('text')
            if not speaker:
                raise ValueError(f"Quote segment missing speaker: {segment}")
            if not text:
                raise ValueError(f"Quote segment missing text: {segment}")

            speakers.add(speaker)
        
        # Write to each speaker's file
        for speaker in speakers:
            folder = self.root / speaker
            folder.mkdir(parents=True, exist_ok=True)
            qfile = folder / "quotes.jsonl"
            
            with qfile.open("a", encoding="utf-8") as f:
                f.write(line)

    def add_quote(self, date: str, url: str, timestamp: str, tags: List[str], note: str, text: str):
        if not text.startswith('{quote:'):
            raise ValueError('Quote must start with {quote:"name"}')
        
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
        
        # Construct metadata (tags are for user organization, not speakers)
        metadata = {
            "date": date,
            "url": url,
            "timestamp": timestamp,
            "tags": tags,
            "note": note
        }
        
        self.write_quote(metadata, segments)

    def find_quote_line(self, date: str, url: str, timestamp: str, tags: List[str], note: str) -> tuple[str, int] | None:
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
                        old_url = metadata.get("url", "")
                        old_timestamp = metadata.get("timestamp", "")
                        old_tags = metadata.get("tags", [])
                        old_note = metadata.get("note", "")
                        
                        if (old_date == date and old_url == url and old_timestamp == timestamp and old_tags == tags and old_note == note):
                            return line, i
                except (json.JSONDecodeError, Exception):
                    continue
        return None

    def remove_quote(self, date: str, url: str, timestamp: str, tags: List[str], note: str):
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
                        old_url = metadata.get("url", "")
                        old_timestamp = metadata.get("timestamp", "")
                        old_tags = metadata.get("tags", [])
                        old_note = metadata.get("note", "")
                        
                        if (old_date == date and old_url == url and old_timestamp == timestamp and old_tags == tags and old_note == note):
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
        old_url: str,
        old_timestamp: str,
        old_tags: List[str],
        old_note: str,
        new_date: str,
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
                        old_url_check = metadata.get("url", "")
                        old_timestamp_check = metadata.get("timestamp", "")
                        old_tags_check = metadata.get("tags", [])
                        old_note_check = metadata.get("note", "")
                        
                        # Check if this is the quote line we're looking to edit
                        if (old_date_check == old_date and old_url_check == old_url and old_timestamp_check == old_timestamp and old_tags_check == old_tags and old_note_check == old_note):
                            # This is the quote we want to edit - update its metadata
                            new_metadata_raw = {
                                "date": new_date,
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

    # overwrite nicknames in attributes.json, preserve other keys
    def set_nicknames(self, person: str, nicknames: List[str]):
        self._update_attributes(person, "nicknames", nicknames)

    # overwrite tags in attributes.json, preserve other keys
    def set_tags(self, person: str, tags: List[str]):
        self._update_attributes(person, "tags", tags)

    def set_dont_copy(self, person: str, dont_copy: bool):
        self._update_attributes(person, "dont_copy", dont_copy)

    def _update_attributes(self, person: str, key: str, value: any):
        attr_file = self.root / person / "attributes.json"
        try:
            existing = json.loads(attr_file.read_text(encoding="utf-8")) if attr_file.exists() else {}
        except Exception:
            log.exception("Failed to parse attributes.json for %s", person)
            existing = {}

        # Logic for Boolean keys
        if key == "dont_copy":
            if value is True:
                existing[key] = True
            else:
                # If False, remove it from the dictionary entirely
                existing.pop(key, None)
        
        # Logic for List keys
        else:
            cleaned: List[str] = []
            seen = set()
            for n in (value or []):
                s = (n or "").strip()
                if not s or s in seen:
                    continue
                seen.append(s)
                cleaned.append(s)
            existing[key] = cleaned

        ordered_data = {}
        
        # List of keys to attempt to preserve in order
        keys_to_preserve = ['dont_copy', 'groups', 'nicknames', 'tags']
        
        for k in keys_to_preserve:
            if k in existing:
                val = existing[k]
                if val is not False and val != [] and val != "":
                    ordered_data[k] = val

        # If no data remains, delete the file entirely
        if not ordered_data:
            try:
                if attr_file.exists():
                    attr_file.unlink()
            except Exception:
                log.exception("Failed to delete empty attributes.json for %s", person)
        else:
            try:
                attr_file.write_text(json.dumps(ordered_data, indent=4, ensure_ascii=False), encoding="utf-8")
            except Exception:
                log.exception("Failed to write attributes.json for %s", person)
                raise

    # Remove all references to a speaker from a JSONL line.
    def _remove_speaker_from_line(self, line: str, name: str) -> str:
        try:
            data = json.loads(line)
            # If this is a quote entry, remove any speaker references
            if 'quote' in data:
                new_quote = []
                for speaker_entry in data['quote']:
                    # Only keep entries that don't have the removed speaker
                    if speaker_entry.get('speaker') != name:
                        new_quote.append(speaker_entry)
                # Update the quote list, removing the person
                if new_quote:
                    data['quote'] = new_quote
                else:
                    # If no speakers left, remove the entire quote entry
                    return ""
            return json.dumps(data, ensure_ascii=False)
        except (json.JSONDecodeError, Exception):
            # If we can't parse the JSON, return the original line
            return line

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

                # Keep line only if it still contains quote data
                if updated.strip():  # Only keep non-empty lines
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

    def remove_tag(self, tag_to_remove: str):
        """Remove a tag from all quote files, and remove the tags key if it becomes empty"""
        for folder in self.root.iterdir():
            if not folder.is_dir():
                continue
                
            qfile = folder / "quotes.jsonl"
            if not qfile.exists():
                continue
                
            lines = qfile.read_text(encoding="utf-8").splitlines()
            new_lines = []
            modified = False
            
            for line in lines:
                try:
                    data = json.loads(line.strip())
                    if "metadata" in data:
                        metadata = data["metadata"]
                        tags = metadata.get("tags", [])
                        
                        # Remove the tag if it exists
                        if tag_to_remove in tags:
                            tags.remove(tag_to_remove)
                            modified = True
                            
                            # Update the metadata with cleaned tags
                            metadata["tags"] = tags
                            
                            # Remove tags key if empty
                            if not tags:
                                metadata.pop("tags", None)
                                
                            # Update the line
                            new_lines.append(json.dumps(data, ensure_ascii=False))
                        else:
                            new_lines.append(line)
                    else:
                        new_lines.append(line)
                except (json.JSONDecodeError, Exception):
                    new_lines.append(line)
            
            # Only rewrite file if changes were made
            if modified:
                qfile.write_text(
                    "\n".join(new_lines) + ("\n" if new_lines else ""),
                    encoding="utf-8"
                )

    def rename_tag(self, old_tag: str, new_tag: str):
        """Rename a tag in all quote files, and remove the tags key if it becomes empty"""
        for folder in self.root.iterdir():
            if not folder.is_dir():
                continue
                
            qfile = folder / "quotes.jsonl"
            if not qfile.exists():
                continue
                
            lines = qfile.read_text(encoding="utf-8").splitlines()
            new_lines = []
            modified = False
            
            for line in lines:
                try:
                    data = json.loads(line.strip())
                    if "metadata" in data:
                        metadata = data["metadata"]
                        tags = metadata.get("tags", [])
                        
                        # Rename the tag if it exists
                        if old_tag in tags:
                            # Replace old tag with new tag
                            tags = [new_tag if tag == old_tag else tag for tag in tags]
                            modified = True
                            
                            # Update the metadata with cleaned tags
                            metadata["tags"] = tags
                            
                            # Remove tags key if empty
                            if not tags:
                                metadata.pop("tags", None)
                                
                            # Update the line
                            new_lines.append(json.dumps(data, ensure_ascii=False))
                        else:
                            new_lines.append(line)
                    else:
                        new_lines.append(line)
                except (json.JSONDecodeError, Exception):
                    new_lines.append(line)
            
            # Only rewrite file if changes were made
            if modified:
                qfile.write_text(
                    "\n".join(new_lines) + ("\n" if new_lines else ""),
                    encoding="utf-8"
                )

    def _synchronize_speakers(self, all_quotes_by_speaker: dict[str, set[str]]):
        # Avoid self-reference by making a local copy
        speaker_quotes = all_quotes_by_speaker.copy()
        all_quotes_by_speaker.clear()  # Clear for next run
        
        for speaker_name, quote_lines in speaker_quotes.items():
            # Target directory for this speaker
            speaker_dir = self.root / speaker_name
            speaker_dir.mkdir(parents=True, exist_ok=True)
            
            # Target file
            speaker_file = speaker_dir / "quotes.jsonl"
            
            # Load existing content to avoid duplicates
            existing_lines = set()
            if speaker_file.exists():
                with speaker_file.open("r", encoding="utf-8") as f:
                    for line in f:
                        existing_lines.add(line.strip())
            
            # Find quotes that are NOT already in this speaker's file
            missing_quotes = quote_lines - existing_lines
            
            # Only write missing quotes (append them)
            if missing_quotes:
                with speaker_file.open("a", encoding="utf-8") as f:
                    for line in missing_quotes:
                        if line:  # Only write non-empty lines
                            f.write(line + "\n")

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

        # Update each person's attributes.json by redirecting to _update_attributes
        for folder in self.root.iterdir():
            if not folder.is_dir():
                continue

            name = folder.name
            # For each person, update their groups attribute specifically
            self._update_attributes(name, "groups", person_to_groups.get(name, []))

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

    # Distructive Functions

    def sort_quotes(self):
        for folder in self.root.iterdir():
            if not folder.is_dir():
                continue
                
            qfile = folder / "quotes.jsonl"
            if not qfile.exists():
                continue
                
            try:
                with qfile.open("r", encoding="utf-8") as f:
                    lines = [line.strip() for line in f if line.strip()]
                sorted_lines = sorted(lines)
                
                with qfile.open("w", encoding="utf-8") as f:
                    for line in sorted_lines:
                        if line:  # Only write non-empty lines
                            f.write(line + "\n")
                            
            except Exception as e:
                print(f"Error sorting quotes for {folder.name}: {e}")
                continue

    def remove_all_quotes(self):
        for folder in self.root.iterdir():
            if folder.is_dir():
                shutil.rmtree(folder)