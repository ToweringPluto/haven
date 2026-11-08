"""Uploaded evidence on disk: ``<dir>/<upload_id>.<ext>`` plus a ``<upload_id>.json`` record.

* Only JPEG, PNG, WebP and PDF are accepted, decided by **magic bytes**, never by the file
  name or the declared content type.
* Files over ``max_bytes`` are rejected before anything is written.
* Images are decoded and **re-saved without metadata** (EXIF, GPS, XMP, text chunks), after
  applying the EXIF orientation so the photo isn't left rotated. Anything Pillow can't decode
  is rejected. PDFs are stored unchanged (``metadata_stripped`` is then ``False``).
* ``delete`` removes both the file and its record.
"""

import io
import json
import re
import warnings
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePath
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError

from haven.domain import Upload, UploadKind


@dataclass(frozen=True)
class FileType:
    content_type: str
    extension: str
    pillow_format: str | None  # None = stored as-is (PDF)


JPEG = FileType("image/jpeg", "jpg", "JPEG")
PNG = FileType("image/png", "png", "PNG")
WEBP = FileType("image/webp", "webp", "WEBP")
PDF = FileType("application/pdf", "pdf", None)
ACCEPTED = "JPEG, PNG, WebP or PDF"

_ID = re.compile(r"^upload-[0-9a-f]{32}$")


class UploadRejected(ValueError):
    """The file can't be stored. ``reason`` is ``too_large`` or ``unsupported``."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


def sniff(content: bytes) -> FileType | None:
    """The file type from its first bytes, or ``None`` if it isn't an accepted type."""
    if content.startswith(b"\xff\xd8\xff"):
        return JPEG
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return PNG
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return WEBP
    if content.startswith(b"%PDF-"):
        return PDF
    return None


def strip_metadata(content: bytes, file_type: FileType) -> bytes:
    """Re-encode an image with no metadata (orientation applied first).

    The pixels are copied into a fresh image, so nothing from the original's ``info``
    (EXIF, GPS, XMP, ICC, PNG text) can be written back on save.
    """
    assert file_type.pillow_format is not None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as opened:
                image_format = opened.format
                image = ImageOps.exif_transpose(opened)
                image.load()
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise UploadRejected("too_large", "The image has too many pixels.") from exc
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise UploadRejected("unsupported", f"The image can't be read: {exc}") from exc
    if image_format != file_type.pillow_format:
        raise UploadRejected("unsupported", f"The file isn't a valid {ACCEPTED}.")
    if image.mode in ("P", "PA"):
        image = image.convert("RGBA")
    clean = Image.new(image.mode, image.size)
    clean.paste(image)
    out = io.BytesIO()
    if file_type.pillow_format in ("JPEG", "WEBP"):
        clean.save(out, format=file_type.pillow_format, quality=95)
    else:
        clean.save(out, format=file_type.pillow_format)
    return out.getvalue()


class UploadStore:
    """Files and records under ``directory`` (created on first save)."""

    def __init__(self, directory: Path, *, max_bytes: int) -> None:
        self.directory = directory
        self.max_bytes = max_bytes

    def _record(self, upload_id: str) -> Path:
        if not _ID.fullmatch(upload_id):
            raise KeyError(upload_id)
        return self.directory / f"{upload_id}.json"

    def save(
        self, *, kind: UploadKind, filename: str, content: bytes, property_id: str | None
    ) -> Upload:
        if len(content) > self.max_bytes:
            limit = self.max_bytes / (1024 * 1024)
            raise UploadRejected("too_large", f"Uploads must be {limit:g} MB or smaller.")
        file_type = sniff(content)
        if file_type is None:
            raise UploadRejected("unsupported", f"Upload a {ACCEPTED} file.")
        stored = content
        stripped = False
        if file_type.pillow_format is not None:
            stored = strip_metadata(content, file_type)
            stripped = True
        upload_id = f"upload-{uuid4().hex}"
        self.directory.mkdir(parents=True, exist_ok=True)
        (self.directory / f"{upload_id}.{file_type.extension}").write_bytes(stored)
        upload = Upload(
            id=upload_id,
            kind=kind,
            filename=PurePath(filename).name or "upload",
            content_type=file_type.content_type,
            size_bytes=len(stored),
            uploaded_at=datetime.now(UTC),
            property_id=property_id,
            metadata_stripped=stripped,
            evidence_quality=None,
        )
        self._record(upload_id).write_text(upload.model_dump_json(), encoding="utf-8")
        return upload

    def update(self, upload: Upload) -> None:
        """Rewrite an existing upload's record (e.g. after screening). The file is untouched."""
        path = self._record(upload.id)
        if not path.is_file():
            raise KeyError(upload.id)
        path.write_text(upload.model_dump_json(), encoding="utf-8")

    def get(self, upload_id: str) -> Upload | None:
        try:
            path = self._record(upload_id)
        except KeyError:
            return None
        if not path.is_file():
            return None
        return Upload.model_validate(json.loads(path.read_text(encoding="utf-8")))

    def file_path(self, upload_id: str) -> Path | None:
        upload = self.get(upload_id)
        if upload is None:
            return None
        extension = next(
            t.extension for t in (JPEG, PNG, WEBP, PDF) if t.content_type == upload.content_type
        )
        return self.directory / f"{upload_id}.{extension}"

    def delete(self, upload_id: str) -> bool:
        """Remove the file and its record. ``False`` if there was no such upload."""
        path = self.file_path(upload_id)
        if path is None:
            return False
        path.unlink(missing_ok=True)
        self._record(upload_id).unlink()
        return True
