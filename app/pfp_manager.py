from pathlib import Path
from PySide6.QtGui import QImageReader, QImage
from PySide6.QtCore import QSize, Qt

# PFP manager: safe decode, center-crop, final 256x256
class PFPManager:
    MAX_PIXEL_COUNT = 80_000_000
    SAFE_DECODE_LIMIT = 2048
    FINAL_SIZE = 256

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def set_pfp(self, person_name: str, image_path: Path) -> Path:
        image_path = Path(image_path)

        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        reader = QImageReader(str(image_path))
        reader.setAutoTransform(True)  # apply EXIF rotation

        if not reader.canRead():
            raise ValueError("File is not a valid image")

        # Inspect original size without decoding full image
        original_size = reader.size()
        if original_size.isValid():
            width = original_size.width()
            height = original_size.height()

            pixel_count = max(0, width) * max(0, height)
            if pixel_count > self.MAX_PIXEL_COUNT:
                raise ValueError("Image resolution is dangerously large")

            # pre-scale to avoid memory spikes
            max_dim = max(width, height)
            if max_dim > self.SAFE_DECODE_LIMIT:
                scale_factor = self.SAFE_DECODE_LIMIT / float(max_dim)
                scaled_w = max(1, int(round(width * scale_factor)))
                scaled_h = max(1, int(round(height * scale_factor)))
                reader.setScaledSize(QSize(scaled_w, scaled_h))

        image = reader.read()
        if image.isNull():
            raise ValueError("Failed to load image")

        image = self._square_crop(image)

        # final resize to 256x256 (image is already square)
        image = image.scaled(
            self.FINAL_SIZE,
            self.FINAL_SIZE,
            Qt.IgnoreAspectRatio,
            Qt.SmoothTransformation
        )

        person_folder = self.root / person_name
        person_folder.mkdir(parents=True, exist_ok=True)
        target_path = person_folder / "pfp.png"
        image.save(str(target_path), "PNG", 9)
        if not image.save(str(target_path), "PNG", 9):
            raise IOError("Failed to save avatar")

        return target_path

    def remove_pfp(self, person_name: str):
        pfp_path = self.root / person_name / "pfp.png"
        if pfp_path.exists():
            pfp_path.unlink()

    def _square_crop(self, image: QImage) -> QImage:
        width = image.width()
        height = image.height()
        size = min(width, height)
        x = (width - size) // 2
        y = (height - size) // 2
        return image.copy(x, y, size, size)