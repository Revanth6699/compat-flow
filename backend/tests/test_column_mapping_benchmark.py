import json
from pathlib import Path

from app.services.catalog_csv import HEADER_ALIASES, _normalize_header


def test_reviewed_benchmark_positive_examples_match_alias_map():
    benchmark_path = (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "column-mapping-benchmark-seed.json"
    )
    benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
    alias_lookup = {
        alias: field
        for field, aliases in HEADER_ALIASES.items()
        for alias in aliases
    }

    positive = [
        record
        for record in benchmark["records"]
        if record["decision"] in {"auto_alias", "source_specific_alias"}
    ]
    assert positive, "Benchmark must include reviewed positive mapping examples."

    for record in positive:
        normalized = _normalize_header(record["header"])
        assert alias_lookup.get(normalized) == record["canonical_field"], (
            f"Dataset {record['source_dataset']} header {record['header']!r} "
            f"should map to {record['canonical_field']!r}."
        )


def test_reviewed_negative_and_ambiguous_examples_are_not_auto_mapped():
    benchmark_path = (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "column-mapping-benchmark-seed.json"
    )
    benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
    alias_lookup = {
        alias: field
        for field, aliases in HEADER_ALIASES.items()
        for alias in aliases
    }

    negative = [
        record
        for record in benchmark["records"]
        if record["decision"] in {"do_not_auto_map", "manual_review", "do_not_map"}
        and record["header"] not in {"headerless_file", "unquoted_comma"}
    ]
    assert negative, "Benchmark must include reviewed negative mapping examples."

    for record in negative:
        normalized = _normalize_header(record["header"])
        assert normalized not in alias_lookup, (
            f"Dataset {record['source_dataset']} header {record['header']!r} "
            "must remain unmapped or require review."
        )
