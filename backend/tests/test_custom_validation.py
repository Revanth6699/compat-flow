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
