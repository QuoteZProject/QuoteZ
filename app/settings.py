import json
from pathlib import Path

class Settings:
    def __init__(self, path: Path):
        self.path = path
        self.data = {"quotez_location": "quotez"}
        if path.exists():
            try:
                self.data.update(json.loads(path.read_text()))
            except Exception:
                log.exception("self.data.update(json.loads(path.read_text())) failed")
                raise

    def save(self):
        self.path.write_text(json.dumps(self.data, indent=2))