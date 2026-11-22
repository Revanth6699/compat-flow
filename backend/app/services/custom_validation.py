"""Validation and normalization for customer-authored declarative rules.

Rules are data, never Python expressions or SQL. Only a small allowlist of
operations and bounded configuration shapes is accepted.
"""
from __future__ import annotations

import math
from typing import Any


SUPPORTED_RULE_TYPES = {
    "required", "unique", "numeric_min", "numeric_max",
    "allowed_values", "min_length", "max_length",
}


class CustomRuleError(ValueError):
    pass


def validate_rule_config(rule_type: str, config: dict[str, Any] | None) -> dict[str, Any]:
    if rule_type not in SUPPORTED_RULE_TYPES:
        raise CustomRuleError("Unsupported custom validation rule type.")
    if not isinstance(config, dict):
        raise CustomRuleError("Rule configuration must be an object.")

    if rule_type in {"required", "unique"}:
        if config:
            raise CustomRuleError("This rule type does not accept configuration values.")
        return {}

    if rule_type in {"numeric_min", "numeric_max"}:
        if set(config) != {"value"}:
            raise CustomRuleError("Numeric rules require exactly one 'value' setting.")
        value = config["value"]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise CustomRuleError("Numeric rule value must be a finite number.")
        return {"value": value}

    if rule_type == "allowed_values":
        if set(config) != {"values"}:
            raise CustomRuleError("Allowed-values rules require exactly one 'values' setting.")
        values = config["values"]
        if (
            not isinstance(values, list)
            or not 1 <= len(values) <= 100
            or any(not isinstance(value, str) or not value.strip() for value in values)
        ):
            raise CustomRuleError("Allowed values must contain 1 to 100 non-empty strings.")
        normalized = [value.strip() for value in values]
        if len({value.casefold() for value in normalized}) != len(normalized):
            raise CustomRuleError("Allowed values must be unique, ignoring case.")
        return {"values": normalized}

    if rule_type in {"min_length", "max_length"}:
        if set(config) != {"value"}:
            raise CustomRuleError("Length rules require exactly one 'value' setting.")
        value = config["value"]
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 1_000_000:
            raise CustomRuleError("Length rule value must be an integer between 0 and 1,000,000.")
        return {"value": value}

    raise CustomRuleError("Unsupported custom validation rule type.")
