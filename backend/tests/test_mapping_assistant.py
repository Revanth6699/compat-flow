import asyncio
import json

import pytest

from app.services import mapping_assistant
from app.services.mapping_assistant import suggest_field_mappings


def test_mapping_assistant_requires_explicit_opt_in(monkeypatch):
    monkeypatch.setenv("MAPPING_AI_API_KEY", "should-not-be-used")

    class NoCallClient:
        def __init__(self, **kwargs):
            raise AssertionError("Provider must not be called without consent.")

    monkeypatch.setattr(mapping_assistant.httpx, "AsyncClient", NoCallClient)
    result = asyncio.run(suggest_field_mappings(
        record_type="products",
        headers=["sku"],
        sample_records=[{"sku": "001"}],
        user_opted_in=False,
    ))
    assert result.status == "consent_required"
    assert result.suggestions == []
    assert result.classification is None


def test_mapping_assistant_falls_back_when_provider_is_not_configured(monkeypatch):
    for key in ("MAPPING_AI_BASE_URL", "MAPPING_AI_API_KEY", "MAPPING_AI_MODEL"):
        monkeypatch.delenv(key, raising=False)
    result = asyncio.run(suggest_field_mappings(
        record_type="products",
        headers=["item_ref"],
        sample_records=[{"item_ref": "001"}],
        user_opted_in=True,
    ))
    assert result.status == "provider_unconfigured"
    assert result.suggestions == []
    assert result.classification is None
    assert "no data was sent" in result.message.lower()


def test_mapping_assistant_rejects_unknown_record_type():
    with pytest.raises(ValueError, match="record type"):
        asyncio.run(suggest_field_mappings(
            record_type="unknown", headers=[], sample_records=[], user_opted_in=True
        ))


def test_ai_classification_and_mapping_are_source_backed_and_require_confirmation(monkeypatch):
    monkeypatch.setenv("MAPPING_AI_BASE_URL", "https://mapping.example/v1")
    monkeypatch.setenv("MAPPING_AI_API_KEY", "test-provider-key")
    monkeypatch.setenv("MAPPING_AI_MODEL", "test-model")
    calls = {}

    provider_content = {
        "classification": {
            "record_type": "products",
            "confidence": 0.91,
            "rationale": "The sample contains product SKU and descriptive fields.",
            "evidence": ["SKU", "Item Name"],
        },
        "suggestions": [
            {
                "source_header": "SKU",
                "candidate_field": "sku",
                "confidence": 0.99,
                "rationale": "The header explicitly identifies the SKU.",
                "evidence": ["SKU", "001"],
            },
            {
                "source_header": "Item Name",
                "candidate_field": "name",
                "confidence": 0.95,
                "rationale": "The header identifies the product name.",
                "evidence": ["Item Name", "Widget"],
            },
        ],
    }

    class FakeResponse:
        content = json.dumps({
            "choices": [{"message": {"content": json.dumps(provider_content)}}]
        }).encode()

        def raise_for_status(self):
            return None

        def json(self):
            return json.loads(self.content)

    class FakeClient:
        def __init__(self, **kwargs):
            calls["client_options"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, headers, json):
            calls["url"] = url
            calls["headers"] = headers
            calls["payload"] = json
            return FakeResponse()

    monkeypatch.setattr(mapping_assistant.httpx, "AsyncClient", FakeClient)
    result = asyncio.run(suggest_field_mappings(
        record_type="products",
        headers=["SKU", "Item Name"],
        sample_records=[
            {"SKU": "001", "Item Name": "Widget"},
            {"SKU": "002", "Item Name": "Gear"},
        ],
        user_opted_in=True,
    ))

    assert result.status == "suggestions_ready"
    assert result.classification is not None
    assert result.classification.record_type == "products"
    assert result.classification.confidence == 0.91
    assert result.classification.evidence == ["SKU", "Item Name"]
    assert result.classification.requires_confirmation is True
    assert [(item.source_header, item.candidate_field) for item in result.suggestions] == [
        ("SKU", "sku"),
        ("Item Name", "name"),
    ]
    assert all(item.requires_confirmation for item in result.suggestions)
    assert calls["url"] == "https://mapping.example/v1/chat/completions"
    assert calls["client_options"]["follow_redirects"] is False
    assert calls["client_options"]["trust_env"] is False
    submitted = json.loads(calls["payload"]["messages"][1]["content"])
    assert submitted["allowed_record_types"]["product_identifiers"]
    assert submitted["headers_and_sample_values"]["SKU"] == ["001", "002"]
    assert "test-provider-key" not in calls["payload"]["messages"][1]["content"]


def test_ai_rejects_hallucinated_evidence_and_mapping_fields(monkeypatch):
    monkeypatch.setenv("MAPPING_AI_BASE_URL", "https://mapping.example/v1")
    monkeypatch.setenv("MAPPING_AI_API_KEY", "test-provider-key")
    monkeypatch.setenv("MAPPING_AI_MODEL", "test-model")

    provider_content = {
        "classification": {
            "record_type": "supplier_offers",
            "confidence": 0.99,
            "rationale": "Unsupported claim.",
            "evidence": ["not present in source"],
        },
        "suggestions": [
            {
                "source_header": "SKU",
                "candidate_field": "supplier_id",
                "confidence": 0.99,
                "rationale": "Wrong record-type field.",
                "evidence": ["SKU"],
            },
            {
                "source_header": "SKU",
                "candidate_field": "sku",
                "confidence": 0.99,
                "rationale": "Invented evidence.",
                "evidence": ["fabricated-value"],
            },
        ],
    }

    class FakeResponse:
        content = json.dumps({
            "choices": [{"message": {"content": json.dumps(provider_content)}}]
        }).encode()

        def raise_for_status(self):
            return None

        def json(self):
            return json.loads(self.content)

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(mapping_assistant.httpx, "AsyncClient", FakeClient)
    result = asyncio.run(suggest_field_mappings(
        record_type="products",
        headers=["SKU"],
        sample_records=[{"SKU": "001"}],
        user_opted_in=True,
    ))
    assert result.classification is None
    assert result.suggestions == []


def test_ai_evidence_is_bounded_before_provider_call(monkeypatch):
    monkeypatch.setenv("MAPPING_AI_BASE_URL", "https://mapping.example/v1")
    monkeypatch.setenv("MAPPING_AI_API_KEY", "test-provider-key")
    monkeypatch.setenv("MAPPING_AI_MODEL", "test-model")

    with pytest.raises(ValueError, match="header or sample-record limit"):
        asyncio.run(suggest_field_mappings(
            record_type="products",
            headers=[f"column_{index}" for index in range(81)],
            sample_records=[],
            user_opted_in=True,
        ))

    with pytest.raises(ValueError, match="bounded source headers"):
        asyncio.run(suggest_field_mappings(
            record_type="products",
            headers=["x" * 129],
            sample_records=[],
            user_opted_in=True,
        ))
