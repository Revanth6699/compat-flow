import pytest

from app.services.mapping_assistant import suggest_field_mappings


@pytest.mark.asyncio
async def test_mapping_assistant_requires_explicit_opt_in(monkeypatch):
    monkeypatch.setenv("MAPPING_AI_API_KEY", "should-not-be-used")
    result = await suggest_field_mappings(
        record_type="products",
        headers=["sku"],
        sample_records=[{"sku": "001"}],
        user_opted_in=False,
    )
    assert result.status == "consent_required"
    assert result.suggestions == []


@pytest.mark.asyncio
async def test_mapping_assistant_falls_back_when_provider_is_not_configured(monkeypatch):
    for key in ("MAPPING_AI_BASE_URL", "MAPPING_AI_API_KEY", "MAPPING_AI_MODEL"):
        monkeypatch.delenv(key, raising=False)
    result = await suggest_field_mappings(
        record_type="products",
        headers=["item_ref"],
        sample_records=[{"item_ref": "001"}],
        user_opted_in=True,
    )
    assert result.status == "provider_unconfigured"
    assert result.suggestions == []


@pytest.mark.asyncio
async def test_mapping_assistant_rejects_unknown_record_type():
    with pytest.raises(ValueError, match="record type"):
        await suggest_field_mappings(
            record_type="unknown", headers=[], sample_records=[], user_opted_in=True
        )
