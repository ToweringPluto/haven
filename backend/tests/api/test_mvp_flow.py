"""The full renter journey on the engine backend: screened uploads, photo screening, reports
for any property/profile pair, saved records and the rent context."""

import io
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlmodel import create_engine

from haven.api.app import create_app
from haven.api.engines import EngineBackend
from haven.config import CONTRACT_EXAMPLES_DIR
from haven.explain import HEADINGS, certainty_phrases
from haven.gemini import GeminiError
from haven.screening.gemini import GeminiScreener
from haven.store import SqlRecordStore, UploadStore

SEED_PROPERTY = "seed-prop-leith"  # council tax band C in the seed file

PROFILE = {
    "label": "Test renter",
    "monthly_budget_gbp": 1400,
    "priorities": ["total_cost", "step_free_access"],
    "access": {"step_free_entrance_required": True},
}


class FakeGemini:
    model = "gemini-test"

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    def generate_json(
        self, *, prompt: str, schema: dict[str, Any], image: tuple[bytes, str] | None = None
    ) -> Any:
        if self.error is not None:
            raise self.error
        return {
            "possible_damp": {"likelihood": "unlikely", "what_is_visible": "Clean walls"},
            "possible_mould": {"likelihood": "possible", "what_is_visible": "Dark corner"},
            "entrance_step": {"likelihood": "insufficient_evidence", "what_is_visible": ""},
        }


def jpeg() -> bytes:
    rng = np.random.default_rng(3)
    blocks = rng.integers(60, 200, size=(96, 128), dtype=np.uint8)
    image = Image.fromarray(np.kron(blocks, np.ones((8, 8), dtype=np.uint8))).convert("RGB")
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=95)
    return out.getvalue()


def pdf(lines: list[str]) -> bytes:
    out = io.BytesIO()
    page = canvas.Canvas(out, pagesize=A4, invariant=1)
    y = A4[1] - 72
    for line in lines:
        page.drawString(72, y, line)
        y -= 18
    page.save()
    return out.getvalue()


def make_backend(tmp_path: Path, *, error: Exception | None = None, db: str = "") -> EngineBackend:
    records = SqlRecordStore(create_engine(db or f"sqlite:///{tmp_path / 'records.db'}"))
    return EngineBackend(
        CONTRACT_EXAMPLES_DIR,
        uploads=UploadStore(tmp_path / "uploads", max_bytes=5 * 1024 * 1024),
        records=records,
        screener=GeminiScreener(FakeGemini(error)),
    )


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(backend=make_backend(tmp_path)))


def upload(client: TestClient, content: bytes, name: str, ctype: str, kind: str) -> Any:
    response = client.post(
        "/v1/uploads",
        files={"file": (name, content, ctype)},
        data={"kind": kind, "property_id": SEED_PROPERTY},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_photo_upload_is_screened(client: TestClient) -> None:
    body = upload(client, jpeg(), "kitchen.jpg", "image/jpeg", "photo")
    assert body["evidence_quality"] == "good"
    by_kind = {s["kind"]: s for s in body["signals"]}
    assert by_kind["possible_mould"]["likelihood"] == "possible"
    assert by_kind["possible_mould"]["upload_id"] == body["id"]
    assert all(s["confidence"] is None for s in body["signals"])


def test_floor_plan_gets_quality_only(client: TestClient) -> None:
    body = upload(client, jpeg(), "plan.jpg", "image/jpeg", "floor_plan")
    assert body["evidence_quality"] == "good"
    assert body["signals"] == []


def test_document_upload_has_extracted_facts(client: TestClient) -> None:
    body = upload(
        client,
        pdf(["Tenancy agreement", "Your property is in council tax band E."]),
        "lease.pdf",
        "application/pdf",
        "document",
    )
    facts = {f["name"]: f["evidence"]["value"] for f in body["extracted_facts"]}
    assert facts["council_tax_band"] == "E"


def test_gemini_failure_never_fails_an_upload(tmp_path: Path) -> None:
    client = TestClient(create_app(backend=make_backend(tmp_path, error=GeminiError("down"))))
    body = upload(client, jpeg(), "kitchen.jpg", "image/jpeg", "photo")
    assert body["evidence_quality"] == "good"
    assert {s["likelihood"] for s in body["signals"]} == {"insufficient_evidence"}


def test_report_for_new_profile_and_seed_property(client: TestClient) -> None:
    profile = client.post("/v1/profiles", json=PROFILE).json()
    photo = upload(client, jpeg(), "kitchen.jpg", "image/jpeg", "photo")
    lease = upload(
        client,
        pdf(["Tenancy agreement", "Your property is in council tax band E."]),
        "lease.pdf",
        "application/pdf",
        "document",
    )
    response = client.post(
        "/v1/assessments",
        json={
            "profile_id": profile["id"],
            "property_id": SEED_PROPERTY,
            "upload_ids": [photo["id"], lease["id"]],
        },
    )
    assert response.status_code == 201, response.text
    report = response.json()

    assert report["illustrative"] is True  # seed properties are fictional
    assert report["cost"]["rent_context"]["median_gbp_pcm"] > 0
    assert [s["heading"] for s in report["sections"]] == list(HEADINGS)
    rule_ids = {f["rule_id"] for f in report["findings"]}
    assert "document_conflict" in rule_ids
    assert {s["upload_id"] for s in report["signals"]} == {photo["id"]}

    known = {f["id"] for f in report["findings"]} | {s["id"] for s in report["signals"]}
    sentences = [s for section in report["sections"] for s in section["sentences"]]
    assert sentences
    for sentence in sentences:
        assert sentence["cites"] and set(sentence["cites"]) <= known
        assert certainty_phrases(sentence["text"]) == [], sentence["text"]
    mould = next(s["id"] for s in report["signals"] if s["kind"] == "possible_mould")
    assert any(mould in s["cites"] for s in sentences)

    assert client.get(f"/v1/reports/{report['id']}").json() == report


def test_records_survive_a_restart(tmp_path: Path) -> None:
    first = TestClient(create_app(backend=make_backend(tmp_path)))
    profile = first.post("/v1/profiles", json=PROFILE).json()
    report = first.post(
        "/v1/assessments", json={"profile_id": profile["id"], "property_id": SEED_PROPERTY}
    ).json()

    second = TestClient(create_app(backend=make_backend(tmp_path)))
    assert second.get(f"/v1/profiles/{profile['id']}").json() == profile
    assert second.get(f"/v1/reports/{report['id']}").json() == report


def test_unknown_upload_in_assessment_is_404(client: TestClient) -> None:
    profile = client.post("/v1/profiles", json=PROFILE).json()
    response = client.post(
        "/v1/assessments",
        json={"profile_id": profile["id"], "property_id": SEED_PROPERTY, "upload_ids": ["x"]},
    )
    assert response.status_code == 404


def test_cost_carries_rent_context(client: TestClient) -> None:
    body = client.post(f"/v1/properties/{SEED_PROPERTY}/cost", json={"profile_id": None}).json()
    context = body["rent_context"]
    assert context["lower_quartile_gbp_pcm"] <= context["median_gbp_pcm"]
    assert context["rent_vs_median"] in {"below", "similar", "above"}
    assert context["caveats"]
