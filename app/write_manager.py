from pathlib import Path
import json
import shutil
import re
from typing import Optional, List

from .quote_utils import find_quote_tag_names
from .pfp_manager import PFPManager


class QuoteModifier:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

        self.pfp_manager = PFPManager(self.root)

    # Quote methods
    def _build_line(self, date: str, timestamp: str, url: str, text: str) -> str:
        text = text.rstrip("\n")
        return f"[{date};{timestamp};{url}]{text}\n"

    def add_quote(self, date: str, timestamp: str, url: str, text: str):
        if not text.startswith('{quote:'):
            raise ValueError('Quote must start with {quote:"name"}')

        speakers = set(find_quote_tag_names(text))
        if not speakers:
            raise ValueError("No speaker tags found")

        line = self._build_line(date, timestamp, url, text)

        for speaker in speakers:
            folder = self.root / speaker
            folder.mkdir(parents=True, exist_ok=True)
            qfile = folder / f"{speaker}.quotes"

            with qfile.open("a", encoding="utf-8") as f:
                f.write(line)

    def remove_quote(self, date: str, timestamp: str, url: str):
        header = f"[{date};{timestamp};{url}]"

        for folder in self.root.iterdir():
            if not folder.is_dir():
                continue

            qfile = folder / f"{folder.name}.quotes"
            if not qfile.exists():
                continue

            lines = qfile.read_text(encoding="utf-8").splitlines()
            new_lines = [l for l in lines if not l.startswith(header)]

            qfile.write_text(
                "\n".join(new_lines) + ("\n" if new_lines else ""),
                encoding="utf-8"
            )

    def edit_quote(
        self,
        old_date: str,
        old_timestamp: str,
        old_url: str,
        new_date: str,
        new_timestamp: str,
        new_url: str,
        new_text: str,
    ):
        self.remove_quote(old_date, old_timestamp, old_url)
        self.add_quote(new_date, new_timestamp, new_url, new_text)

    # Person methods
    def _person_exists(self, name: str) -> bool:
        return (self.root / name).exists()

    def add_person(self, name: str, avatar_path: Optional[Path] = None):
        if self._person_exists(name):
            raise ValueError(f"Person '{name}' already exists")

        folder = self.root / name
        folder.mkdir(parents=True, exist_ok=False)

        qfile = folder / f"{name}.quotes"
        qfile.write_text("", encoding="utf-8")

        if avatar_path:
            self.pfp_manager.set_pfp(name, avatar_path)

    def set_person_pfp(self, name: str, avatar_path: Path):
        return self.pfp_manager.set_pfp(name, avatar_path)

    def remove_person_pfp(self, name: str):
        return self.pfp_manager.remove_pfp(name)

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

            qfile = folder / f"{folder.name}.quotes"
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

        # remove from groups
        if self.groups_file.exists():
            data = self._load_groups()
            changed = False
            for group in data:
                new_members = [p for p in data[group] if p != name]
                if len(new_members) != len(data[group]):
                    data[group] = new_members
                    changed = True
            if changed:
                self._save_groups(data)

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

        # update .quotes files
        for folder in self.root.iterdir():
            if not folder.is_dir():
                continue

            qfile = folder / f"{folder.name}.quotes"
            if not qfile.exists():
                continue

            content = qfile.read_text(encoding="utf-8")
            if f'{{quote:"{old}"}}' in content:
                content = content.replace(
                    f'{{quote:"{old}"}}',
                    f'{{quote:"{new}"}}'
                )
                qfile.write_text(content, encoding="utf-8")

        # move quotes file
        old_file = old_folder / f"{old}.quotes"
        new_file = new_folder / f"{new}.quotes"

        if old_file.exists():
            shutil.move(str(old_file), str(new_file))

        # move avatar
        old_avatar = old_folder / "pfp.png"
        new_avatar = new_folder / "pfp.png"

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