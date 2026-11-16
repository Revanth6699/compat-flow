"""Opt-in AI-assisted record classification and field mapping.

Suggestions are source-backed, bounded, and never authorize persistence.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpx


RECORD_FIELDS = {
    "products": {"sku", "name", "manufacturer", "part_number", "category", "supplier_id", "replacement_sku"},
    "product_variants": {"product_id", "variant_sku", "attributes", "is_active"},
    "supplier_offers": {
        "supplier_id", "product_id", "supplier_sku", "supplier_product_id",
        "unit_price", "currency", "unit_of_measure", "minimum_order_quantity",
        "lead_time_days", "source_url", "status",
    },
    "inventory_snapshots": {
        "product_id", "supplier_offer_id", "warehouse_code", "quantity_on_hand",
        "quantity_reserved", "quantity_available", "snapshot_at", "source_reference",
    },
    "product_identifiers": {
        "product_id", "identifier_type", "namespace", "value",
        "source_reference", "is_primary",
    },
}

# AI evidence is deliberately much smaller than the parser's full input limits.
MAX_AI_HEADERS = 80
MAX_AI_SAMPLE_RECORDS = 5
MAX_AI_HEADER_CHARS = 128
MAX_AI_VALUE_CHARS = 120
MAX_AI_EVIDENCE_CHARS = 64_000
MAX_AI_RESPONSE_BYTES = 64 * 1024


@dataclass(frozen=True)
class FieldMappingSuggestion:
    source_header: str
    candidate_field: str
    confidence: float
    rationale: str
    evidence: list[str]
    requires_confirmation: bool = True


@dataclass(frozen=True)
class RecordTypeSuggestion:
    record_type: str
    confidence: float
    rationale: str
    evidence: list[str]
    requires_confirmation: bool = True


@dataclass(frozen=True)
class MappingAssistantResult:
    status: str
    suggestions: list[FieldMappingSuggestion]
    message: str
    classification: RecordTypeSuggestion | None = None


def _bounded_evidence(
    headers: list[str],
    sample_records: list[dict[str, Any]],
) -> tuple[dict[str, list[str]], set[str]]:
    if len(headers) > MAX_AI_HEADERS or len(sample_records) > MAX_AI_SAMPLE_RECORDS:
        raise ValueError("AI evidence exceeds the configured header or sample-record limit.")
    if not headers or any(
        not isinstance(header, str) or not header.strip() or len(header) > MAX_AI_HEADER_CHARS
        for header in headers
    ):
        raise ValueError("AI evidence requires non-empty, bounded source headers.")
    if len(set(headers)) != len(headers):
        raise ValueError("AI evidence cannot contain duplicate source headers.")
    if any(not isinstance(row, dict) for row in sample_records):
        raise ValueError("AI sample records must be objects.")

    evidence: dict[str, list[str]] = {}
    observed = set(headers)
    total_chars = sum(len(header) for header in headers)
    for header in headers:
        values: list[str] = []
        for row in sample_records:
            value = row.get(header)
            if value is None:
                continue
            try:
                rendered = (
                    json.dumps(value, ensure_ascii=False, default=str)
                    if isinstance(value, (dict, list))
                    else str(value)
                )
            except (TypeError, ValueError):
                continue
            bounded = rendered[:MAX_AI_VALUE_CHARS]
            if bounded:
                values.append(bounded)
                observed.add(bounded)
                total_chars += len(bounded)
            if len(values) == MAX_AI_SAMPLE_RECORDS:
                break
        evidence[header] = values
    if total_chars > MAX_AI_EVIDENCE_CHARS:
        raise ValueError("AI evidence exceeds the configured character budget.")
    return evidence, observed


def _provider_configuration() -> tuple[str, str, str] | None:
    base_url = os.getenv("MAPPING_AI_BASE_URL", "").rstrip("/")
    api_key = os.getenv("MAPPING_AI_API_KEY", "")
    model = os.getenv("MAPPING_AI_MODEL", "")
    parsed_url = urlsplit(base_url)
    if (
        not base_url
        or parsed_url.scheme != "https"
        or not parsed_url.hostname
        or parsed_url.username
        or parsed_url.password
        or parsed_url.query
        or parsed_url.fragment
        or not api_key
        or not model
    ):
        return None
    return base_url, api_key, model


def _parse_classification(
    item: Any,
    observed_evidence: set[str],
) -> RecordTypeSuggestion | None:
    if not isinstance(item, dict):
        return None
    record_type = item.get("record_type")
    confidence = item.get("confidence")
    rationale = item.get("rationale")
    evidence_items = item.get("evidence")
    if (
        not isinstance(record_type, str)
        or record_type not in RECORD_FIELDS
        or isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not 0 <= confidence <= 1
        or not isinstance(rationale, str)
        or not isinstance(evidence_items, list)
    ):
        return None
    verified = [
        value[:240]
        for value in evidence_items[:5]
        if isinstance(value, str) and value in observed_evidence
    ]
    if not verified:
        return None
    return RecordTypeSuggestion(
        record_type=record_type,
        confidence=float(confidence),
        rationale=rationale[:500],
        evidence=verified,
    )


async def suggest_field_mappings(
    *,
    record_type: str,
    headers: list[str],
    sample_records: list[dict[str, Any]],
    user_opted_in: bool,
    timeout_seconds: float = 15,
) -> MappingAssistantResult:
    """Suggest a record type and mappings using one bounded, opt-in provider call.

    The provider receives only source headers and at most five sample values per
    header. Values are clipped before serialization. The caller must obtain
    consent before invoking this function with opt-in.
    """
    if record_type not in RECORD_FIELDS:
        raise ValueError("Unsupported catalog record type.")
    if not user_opted_in:
        return MappingAssistantResult(
            "consent_required", [],
            "AI suggestions are opt-in; no source data was sent.",
        )

    evidence, observed_evidence = _bounded_evidence(headers, sample_records)
    configuration = _provider_configuration()
    if configuration is None:
        return MappingAssistantResult(
            "provider_unconfigured", [],
            "No valid HTTPS AI provider, API key, and model are configured. Use deterministic/manual mapping; no data was sent.",
        )
    base_url, api_key, model = configuration

    allowed_fields = sorted(RECORD_FIELDS[record_type])
    record_types = {
        name: sorted(fields)
        for name, fields in RECORD_FIELDS.items()
    }
    system = (
        "You assist with catalog ingestion. Return one JSON object with a classification "
        "object and a suggestions array. classification must contain record_type (one of "
        "the allowed record types), confidence (0..1), rationale, and evidence (up to five "
        "exact source headers or sample values). suggestions must contain source_header, "
        "candidate_field, confidence (0..1), rationale, and evidence (up to five exact "
        "observations for that source header). Mapping candidates must come only from the "
        "selected record type's allowed_fields. Classification candidates must come only "
        "from allowed_record_types. Never invent evidence, values, relationships, IDs, or "
        "foreign keys. If uncertain, return null classification or no mapping. Every "
        "suggestion requires explicit human confirmation and never authorizes persistence."
    )
    request_payload = {
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps({
                "selected_record_type": record_type,
                "allowed_fields": allowed_fields,
                "allowed_record_types": record_types,
                "headers_and_sample_values": evidence,
            }, ensure_ascii=False)},
        ],
    }
    try:
        async with httpx.AsyncClient(
            timeout=timeout_seconds,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=request_payload,
            )
            response.raise_for_status()
            if len(response.content) > MAX_AI_RESPONSE_BYTES:
                return MappingAssistantResult(
                    "invalid_provider_output", [],
                    "AI provider response exceeded the configured size limit.",
                )
            provider_response = response.json()
            content = provider_response["choices"][0]["message"]["content"]
            parsed = json.loads(content)
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
        return MappingAssistantResult(
            "provider_error", [],
            "AI provider request failed; deterministic/manual mapping remains available.",
        )

    if not isinstance(parsed, dict):
        return MappingAssistantResult(
            "invalid_provider_output", [],
            "AI provider returned an invalid suggestion structure.",
        )

    classification = _parse_classification(
        parsed.get("classification"),
        observed_evidence,
    )
    raw_suggestions = parsed.get("suggestions", [])
    if not isinstance(raw_suggestions, list):
        return MappingAssistantResult(
            "invalid_provider_output", [],
            "AI provider returned an invalid mapping suggestion structure.",
            classification,
        )

    suggestions: list[FieldMappingSuggestion] = []
    used_sources: set[str] = set()
    used_targets: set[str] = set()
    for item in raw_suggestions[:len(headers)]:
        if not isinstance(item, dict):
            continue
        source_header = item.get("source_header")
        candidate = item.get("candidate_field")
        confidence = item.get("confidence")
        rationale = item.get("rationale")
        evidence_items = item.get("evidence")
        if (
            not isinstance(source_header, str)
            or source_header not in evidence
            or not isinstance(candidate, str)
            or candidate not in RECORD_FIELDS[record_type]
            or isinstance(confidence, bool)
            or not isinstance(confidence, (int, float))
            or not 0 <= confidence <= 1
            or not isinstance(rationale, str)
            or not isinstance(evidence_items, list)
            or source_header in used_sources
            or candidate in used_targets
        ):
            continue
        allowed_evidence = {source_header, *evidence[source_header]}
        verified_evidence = [
            value[:240]
            for value in evidence_items[:5]
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
        used_sources.add(source_header)
        used_targets.add(candidate)

    return MappingAssistantResult(
        "suggestions_ready",
        suggestions,
        "Review the classification and every mapping suggestion before applying them.",
        classification,
    )
