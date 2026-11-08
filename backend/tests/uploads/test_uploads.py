"""Upload storage: type sniffing, size limit, metadata stripping, delete; and the API wiring."""

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from haven.api.engines import EngineBackend
from haven.config import CONTRACT_EXAMPLES_DIR
from haven.domain import UploadKind
from haven.store import UploadRejected, UploadStore
from haven.store.uploads import sniff
from tests.api.auth_helpers import signed_in

GPS_IFD = 0x8825


def image_bytes(
    fmt: str, *, exif: bool = True, orientation: int | None = None, size=(40, 20)
) -> bytes:
    image = Image.new("RGB", size, (200, 30, 30))
    data = image.getexif()
    if exif:
        data[0x010F] = "PhoneMaker"  # Make
        data[GPS_IFD] = {1: "N", 2: (55.0, 57.0, 1.0), 3: "W", 4: (3.0, 11.0, 0.0)}
    if orientation is not None:
        data[0x0112] = orientation
    out = io.BytesIO()
    image.save(out, format=fmt, exif=data.tobytes())
    return out.getvalue()


@pytest.fixture
def store(tmp_path: Path) -> UploadStore:
    return UploadStore(tmp_path, max_bytes=1024 * 1024)


def save(store: UploadStore, content: bytes, filename: str = "photo.jpg"):
    return store.save(kind=UploadKind.photo, filename=filename, content=content, property_id=None)


@pytest.mark.parametrize("fmt", ["JPEG", "PNG", "WEBP"])
def test_images_are_stored_without_exif_or_gps(store: UploadStore, fmt: str) -> None:
    original = image_bytes(fmt)
    with Image.open(io.BytesIO(original)) as im:
        assert im.getexif().get(0x010F) == "PhoneMaker"  # the test image really has EXIF
    upload = save(store, original)
    assert upload.metadata_stripped is True
    path = store.file_path(upload.id)
    assert path is not None and path.is_file()
    with Image.open(path) as stored:
        assert stored.format == fmt
        assert dict(stored.getexif()) == {}
        assert "exif" not in stored.info and "xmp" not in stored.info
    assert upload.size_bytes == path.stat().st_size


def test_orientation_is_applied_before_stripping(store: UploadStore) -> None:
    upload = save(store, image_bytes("JPEG", orientation=6, size=(40, 20)))  # rotate 90°
    path = store.file_path(upload.id)
    assert path is not None
    with Image.open(path) as stored:
        assert stored.size == (20, 40)


def test_type_comes_from_bytes_not_name(store: UploadStore) -> None:
    upload = save(store, image_bytes("PNG"), filename="sneaky.pdf")
    assert upload.content_type == "image/png"
    assert upload.filename == "sneaky.pdf"
    with pytest.raises(UploadRejected) as rejected:
        save(store, b"MZ\x90\x00 not an image", filename="photo.jpg")
    assert rejected.value.reason == "unsupported"


def test_fake_jpeg_header_is_rejected(store: UploadStore) -> None:
    with pytest.raises(UploadRejected, match="can't be read"):
        save(store, b"\xff\xd8\xff\xe0" + b"garbage" * 20)


def test_pdf_stored_unchanged(store: UploadStore) -> None:
    pdf = b"%PDF-1.4\n%fake but minimal\n%%EOF\n"
    upload = store.save(
        kind=UploadKind.document, filename="lease.pdf", content=pdf, property_id=None
    )
    assert upload.content_type == "application/pdf"
    assert upload.metadata_stripped is False
    path = store.file_path(upload.id)
    assert path is not None and path.read_bytes() == pdf


def test_size_limit(tmp_path: Path) -> None:
    small = UploadStore(tmp_path, max_bytes=100)
    with pytest.raises(UploadRejected) as rejected:
        save(small, b"%PDF-" + b"x" * 200)
    assert rejected.value.reason == "too_large"
    assert list(tmp_path.iterdir()) == []


def test_decompression_bomb_rejected(store: UploadStore, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 100)
    with pytest.raises(UploadRejected) as rejected:
        save(store, image_bytes("PNG", exif=False, size=(40, 20)))
    assert rejected.value.reason == "too_large"


def test_delete_removes_file_and_record(store: UploadStore, tmp_path: Path) -> None:
    upload = save(store, image_bytes("JPEG"))
    assert store.get(upload.id) == upload
    assert len(list(tmp_path.iterdir())) == 2
    assert store.delete(upload.id) is True
    assert list(tmp_path.iterdir()) == []
    assert store.get(upload.id) is None
    assert store.delete(upload.id) is False
    assert store.get("../../etc/passwd") is None


def test_sniff() -> None:
    assert sniff(b"RIFF\x00\x00\x00\x00WEBPVP8 ") is not None
    assert sniff(b"RIFF\x00\x00\x00\x00WAVE") is None
    assert sniff(b"") is None


# --- API -------------------------------------------------------------------------------


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    backend = EngineBackend(
        CONTRACT_EXAMPLES_DIR, uploads=UploadStore(tmp_path, max_bytes=1024 * 1024)
    )
    return signed_in(backend)


def post(client: TestClient, content: bytes, name: str = "p.jpg", ctype: str = "image/jpeg"):
    return client.post(
        "/v1/uploads", files={"file": (name, content, ctype)}, data={"kind": "photo"}
    )


def test_api_upload_and_delete(client: TestClient, tmp_path: Path) -> None:
    response = post(client, image_bytes("JPEG"))
    assert response.status_code == 201
    body = response.json()
    assert body["metadata_stripped"] is True and body["content_type"] == "image/jpeg"
    assert len(list(tmp_path.iterdir())) == 2
    assert client.delete(f"/v1/uploads/{body['id']}").status_code == 204
    assert list(tmp_path.iterdir()) == []
    assert client.delete(f"/v1/uploads/{body['id']}").status_code == 404


def test_api_rejections(client: TestClient) -> None:
    unsupported = post(client, b"just text", name="notes.jpg")
    assert unsupported.status_code == 415
    assert unsupported.headers["content-type"].startswith("application/problem+json")
    too_big = post(
        client, b"%PDF-" + b"x" * (1024 * 1024 + 1), name="big.pdf", ctype="application/pdf"
    )
    assert too_big.status_code == 413


def test_api_unknown_property_is_404(client: TestClient) -> None:
    response = client.post(
        "/v1/uploads",
        files={"file": ("p.jpg", image_bytes("JPEG"), "image/jpeg")},
        data={"kind": "photo", "property_id": "nope"},
    )
    assert response.status_code == 404
