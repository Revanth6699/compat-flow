"""Opt-in AI-assisted field mapping. Suggestions never authorize persistence."""
from __future__ import annotations

import json
import os
from urllib.parse import urlsplit
from dataclasses import dataclass
from typing import Any

import httpx


RECORD_FIELDS = {
    "products": {"sku", "name", "manufacturer", "part_number", "category", "replacement_sku"},
    "product_variants": {"product_id", "variant_sku", "attributes", "is_active"},
    "supplier_offers": {"supplier_id", "product_id", "supplier_sku", "supplier_product_id",
                        "unit_price", "currency", "unit_of_measure", "minimum_order_quantity",
                        "lead_time_days", "source_url", "status"},
    "inventory_snapshots": {"product_id", "supplier_offer_id", "warehouse_code", "quantity_on_hand",
                            "quantity_reserved", "quantity_available", "snapshot_at", "source_reference"},
    "product_identifiers": {"product_id", "identifier_type", "namespace", "value",
                            "source_reference", "is_primary"},
}


@dataclass(frozen=True)
class FieldMappingSuggestion:
    source_header: str
    candidate_field: str
    confidence: float
    rationale: str
    evidence: list[str]
    requires_confirmation: bool = True


@dataclass(frozen=True)
class MappingAssistantResult:
    status: str
    suggestions: list[FieldMappingSuggestion]
    message: str


async def suggest_field_mappings(
    *,
    record_type: str,
    headers: list[str],
    sample_records: list[dict[str, Any]],
    user_opted_in: bool,
    timeout_seconds: float = 15,
) -> MappingAssistantResult:
    """Request bounded, opt-in suggestions from an OpenAI-compatible provider.

    Only header names and up to five bounded sample values per header are sent.
    The caller must obtain consent before invoking this function with opt-in.
    """
    if record_type not in RECORD_FIELDS:
        raise ValueError("Unsupported catalog record type.")
    if not user_opted_in:
        return MappingAssistantResult("consent_required", [], "AI mapping is opt-in; no source data was sent.")
    if len(headers) > 200 or len(sample_records) > 5:
        raise ValueError("Mapping evidence exceeds the configured bounds.")

    base_url = os.getenv("MAPPING_AI_BASE_URL", "").rstrip("/")
    api_key = os.getenv("MAPPING_AI_API_KEY", "")
    model = os.getenv("MAPPING_AI_MODEL", "")
    parsed_url = urlsplit(base_url)
    if (not base_url or parsed_url.scheme != "https" or not parsed_url.hostname
            or parsed_url.username or parsed_url.password or parsed_url.fragment):
        return MappingAssistantResult("provider_unconfigured", [], "Configure an HTTPS AI provider endpoint. No source data was sent.")
    if not api_key or not model:
        return MappingAssistantResult(
            "provider_unconfigured", [],
            "No AI provider is configured. Use deterministic/manual mapping; no data was sent.",
        )

    evidence = {
        header: [str(row.get(header, ""))[:160] for row in sample_records if row.get(header) is not None][:5]
        for header in headers
    }
    allowed_fields = sorted(RECORD_FIELDS[record_type])
    system = (
        "You suggest catalog field mappings. Return JSON only with a top-level suggestions array. "
        "Each suggestion must contain source_header, candidate_field, confidence (0..1), rationale, "
        "and evidence (array of exact observations from the supplied headers or values). "
        "Only use allowed candidate fields. Do not infer relationships or invent evidence. "
        "If uncertain, return no suggestion. Suggestions always require human confirmation."
    )
    payload = {
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps({
                "record_type": record_type,
                "allowed_fields": allowed_fields,
                "headers_and_sample_values": evidence,
            }, ensure_ascii=False)},
        ],
    }
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=False) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            parsed = json.loads(content)
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
        return MappingAssistantResult("provider_error", [], "AI provider request failed; deterministic/manual mapping remains available.")

    raw_suggestions = parsed.get("suggestions", [])
    if not isinstance(raw_suggestions, list):
        return MappingAssistantResult("invalid_provider_output", [], "AI provider returned an invalid suggestion structure.")
    header_set = set(headers)
    suggestions = []
    for item in raw_suggestions[:len(headers)]:
        if not isinstance(item, dict):
            continue
        source_header = item.get("source_header")
        candidate = item.get("candidate_field")
        confidence = item.get("confidence")
        rationale = item.get("rationale")
        evidence_items = item.get("evidence")
        if (not isinstance(source_header, str) or source_header not in header_set
                or not isinstance(candidate, str) or candidate not in RECORD_FIELDS[record_type]
                or isinstance(confidence, bool) or not isinstance(confidence, (int, float))
                or not 0 <= confidence <= 1 or not isinstance(rationale, str)
                or not isinstance(evidence_items, list)):
            continue
        allowed_evidence = set(headers)
        allowed_evidence.update(
            str(row[source_header])[:160]
            for row in sample_records
            if row.get(source_header) is not None
        )
        verified_evidence = [
            value[:240] for value in evidence_items[:5]
            if isinstance(value, str) and value in allowed_evidence
        ]
        if not verified_evidence:
            continue
        suggestions.append(FieldMappingSuggestion(
            source_header=source_header,
            candidate_field=candidate,
            confidence=float(confidence),
            rationale=rationale[:500],
            evidence=verified_evidence,
        ))
    return MappingAssistantResult("suggestions_ready", suggestions, "Review every suggestion before applying a mapping.")
