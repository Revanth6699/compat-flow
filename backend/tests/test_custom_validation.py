import pytest

from app.services.custom_validation import CustomRuleError, validate_rule_config


@pytest.mark.parametrize("rule_type", ["required", "unique"])
def test_boolean_style_rules_accept_only_empty_configuration(rule_type):
    assert validate_rule_config(rule_type, {}) == {}
    with pytest.raises(CustomRuleError):
        validate_rule_config(rule_type, {"value": True})


@pytest.mark.parametrize("rule_type", ["numeric_min", "numeric_max"])
def test_numeric_rules_require_finite_numeric_thresholds(rule_type):
    assert validate_rule_config(rule_type, {"value": 0}) == {"value": 0}
    with pytest.raises(CustomRuleError):
        validate_rule_config(rule_type, {"value": float("nan")})
    with pytest.raises(CustomRuleError):
        validate_rule_config(rule_type, {"value": True})


def test_allowed_values_are_bounded_nonempty_and_case_insensitively_unique():
    assert validate_rule_config("allowed_values", {"values": ["Active", "Inactive"]}) == {
        "values": ["Active", "Inactive"]
    }
    with pytest.raises(CustomRuleError):
        validate_rule_config("allowed_values", {"values": ["Active", "active"]})
    with pytest.raises(CustomRuleError):
        validate_rule_config("allowed_values", {"values": []})


@pytest.mark.parametrize("rule_type", ["min_length", "max_length"])
def test_length_rules_accept_bounded_nonnegative_integers(rule_type):
    assert validate_rule_config(rule_type, {"value": 12}) == {"value": 12}
    with pytest.raises(CustomRuleError):
        validate_rule_config(rule_type, {"value": -1})
    with pytest.raises(CustomRuleError):
        validate_rule_config(rule_type, {"value": 1.5})


def test_custom_rule_config_rejects_unknown_rule_type_and_unknown_settings():
    with pytest.raises(CustomRuleError):
        validate_rule_config("python_expression", {})
    with pytest.raises(CustomRuleError):
        validate_rule_config("numeric_min", {"value": 1, "field": "sku"})



from types import SimpleNamespace

from app.services.custom_validation import evaluate_custom_rules


def make_rule(rule_id, code, field_name, rule_type, config=None, enabled=True, severity="warning"):
    return SimpleNamespace(
        id=rule_id, code=code, name=code.replace("_", " ").title(),
        field_name=field_name, rule_type=rule_type, config=config or {},
        enabled=enabled, severity=severity,
    )


def test_custom_rule_evaluator_runs_required_and_numeric_rules():
    rules = [
        make_rule("r1", "SKU_REQUIRED", "sku", "required", severity="critical"),
        make_rule("r2", "PRICE_MIN", "price", "numeric_min", {"value": 1}),
    ]
    result = evaluate_custom_rules(
        [{"sku": "A1", "price": "2.50"}, {"sku": "", "price": "0"}],
        ["row:2", "row:3"], rules,
    )
    assert [item["status"] for item in result["rules"]] == ["evaluated", "evaluated"]
    assert result["rules"][0]["issue_records"] == 1
    assert result["rules"][1]["issue_records"] == 1
    assert {item["error_code"] for item in result["errors"]} == {
        "REQUIRED_VALUE_MISSING", "BELOW_MINIMUM"
    }


def test_custom_unique_rule_detects_duplicates_across_rows():
    result = evaluate_custom_rules(
        [{"email": "A@example.com"}, {"email": "a@example.com"}],
        ["row:2", "row:3"],
        [make_rule("r1", "EMAIL_UNIQUE", "email", "unique")],
    )
    assert result["rules"][0]["issue_records"] == 1
    assert result["errors"][0]["source_location"] == "row:3"
    assert result["errors"][0]["error_code"] == "DUPLICATE_VALUE"


def test_disabled_or_unavailable_field_rule_is_not_evaluated():
    result = evaluate_custom_rules(
        [{"sku": "A1"}], ["row:2"],
        [
            make_rule("r1", "PRICE_MIN", "price", "numeric_min", {"value": 1}, enabled=False),
            make_rule("r2", "EMAIL_REQUIRED", "email", "required"),
        ],
    )
    assert [item["status"] for item in result["rules"]] == [
        "not_evaluated", "not_evaluated"
    ]
    assert all(item["issue_records"] is None for item in result["rules"])


def test_custom_numeric_rule_rejects_nan_source_value_as_invalid():
    result = evaluate_custom_rules(
        [{"price": "NaN"}], ["row:2"],
        [make_rule("r1", "PRICE_MIN", "price", "numeric_min", {"value": 0})],
    )
    assert result["rules"][0]["issue_records"] == 1
    assert result["errors"][0]["error_code"] == "INVALID_NUMBER"
