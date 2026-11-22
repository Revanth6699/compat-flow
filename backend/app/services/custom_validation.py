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



def evaluate_custom_rules(
    rows: list[dict[str, Any]],
    source_locations: list[str],
    rules: list[Any],
    *,
    error_limit: int = 500,
) -> dict[str, Any]:
    """Evaluate enabled declarative rules without executing customer-supplied code."""
    from decimal import Decimal, InvalidOperation

    from app.services.batch_processing import DiskBackedDuplicateTracker

    if len(rows) != len(source_locations):
        raise CustomRuleError("Source locations must match the number of records.")
    if not 1 <= error_limit <= 10_000:
        raise CustomRuleError("Custom rule error limit is outside the supported range.")

    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    with DiskBackedDuplicateTracker() as tracker:
        for rule in rules:
            if not rule.enabled:
                results.append({
                    "rule_id": str(rule.id), "code": rule.code, "name": rule.name,
                    "field": rule.field_name, "severity": rule.severity,
                    "status": "not_evaluated", "records_evaluated": 0,
                    "issue_records": None,
                })
                continue

            field_name = rule.field_name
            if not rows or field_name not in rows[0] and not any(field_name in row for row in rows):
                results.append({
                    "rule_id": str(rule.id), "code": rule.code, "name": rule.name,
                    "field": field_name, "severity": rule.severity,
                    "status": "not_evaluated", "records_evaluated": 0,
                    "issue_records": None,
                })
                continue

            issue_count = 0
            evaluated_count = 0
            config = rule.config or {}
            for row, source_location in zip(rows, source_locations):
                value = row.get(field_name)
                missing = value is None or (isinstance(value, str) and not value.strip())
                code = None
                message = None

                if rule.rule_type == "required":
                    evaluated_count += 1
                    if missing:
                        code, message = "REQUIRED_VALUE_MISSING", f"{field_name} is required."
                elif missing:
                    continue
                elif rule.rule_type == "unique":
                    evaluated_count += 1
                    duplicate = tracker.check_and_add(
                        (rule.code, str(value).strip().casefold()), source_location
                    )
                    if duplicate.duplicate:
                        code, message = "DUPLICATE_VALUE", (
                            f"{field_name} duplicates the value first seen at "
                            f"{duplicate.first_source_location}."
                        )
                elif rule.rule_type in {"numeric_min", "numeric_max"}:
                    evaluated_count += 1
                    try:
                        number = Decimal(str(value).strip())
                    except (InvalidOperation, ValueError):
                        code, message = "INVALID_NUMBER", f"{field_name} must contain a numeric value."
                    else:
                        if not number.is_finite():
                            code, message = "INVALID_NUMBER", f"{field_name} must contain a finite numeric value."
                            number = None
                        threshold = Decimal(str(config["value"])) if number is not None else None
                        if number is not None and rule.rule_type == "numeric_min" and number < threshold:
                            code, message = "BELOW_MINIMUM", f"{field_name} is below the configured minimum of {threshold}."
                        elif number is not None and rule.rule_type == "numeric_max" and number > threshold:
                            code, message = "ABOVE_MAXIMUM", f"{field_name} exceeds the configured maximum of {threshold}."
                elif rule.rule_type == "allowed_values":
                    evaluated_count += 1
                    allowed = {item.casefold() for item in config["values"]}
                    if str(value).strip().casefold() not in allowed:
                        code, message = "VALUE_NOT_ALLOWED", f"{field_name} is not in the configured allowed values."
                elif rule.rule_type == "min_length":
                    evaluated_count += 1
                    if len(str(value)) < config["value"]:
                        code, message = "VALUE_TOO_SHORT", f"{field_name} is shorter than {config['value']} characters."
                elif rule.rule_type == "max_length":
                    evaluated_count += 1
                    if len(str(value)) > config["value"]:
                        code, message = "VALUE_TOO_LONG", f"{field_name} exceeds {config['value']} characters."

                if code:
                    issue_count += 1
                    if len(errors) < error_limit:
                        errors.append({
                            "rule_id": str(rule.id), "rule_code": rule.code,
                            "source_location": source_location, "field": field_name,
                            "error_code": code, "message": message,
                            "severity": rule.severity,
                        })

            results.append({
                "rule_id": str(rule.id), "code": rule.code, "name": rule.name,
                "field": field_name, "severity": rule.severity,
                "status": "evaluated", "records_evaluated": evaluated_count,
                "issue_records": issue_count,
            })

    return {"rules": results, "errors": errors, "error_limit": error_limit}
