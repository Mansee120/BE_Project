"""Tests for the baselines/ablation study runner."""
from backend.ablation import AblationRunner
from backend.pipeline import Pipeline


def test_ablation_returns_all_variants():
    runner = AblationRunner(Pipeline())
    result = runner.run()
    names = [c["variant"] for c in result["comparison"]]
    assert names == ["full", "no_verification", "llm_math", "no_counterfactuals"]
    assert set(result["variants"].keys()) == set(names)


def test_full_variant_is_strong():
    runner = AblationRunner(Pipeline())
    full = runner.run()["variants"]["full"]
    assert full["verdict_accuracy"] >= 0.9
    assert full["entitlement_error_abs"] == 0


def test_no_verification_degrades_verdict_accuracy():
    runner = AblationRunner(Pipeline())
    data = runner.run()
    full = data["variants"]["full"]["verdict_accuracy"]
    no_ver = data["variants"]["no_verification"]["verdict_accuracy"]
    # Removing the cross-check/document gate should cost accuracy
    assert no_ver < full


def test_llm_math_introduces_entitlement_error():
    runner = AblationRunner(Pipeline())
    llm_math = runner.run()["variants"]["llm_math"]
    # Naive maths should produce non-zero entitlement error
    assert llm_math["entitlement_error_abs"] > 0


def test_no_counterfactuals_scores_fewer_items():
    runner = AblationRunner(Pipeline())
    data = runner.run()
    full = data["variants"]["full"]["count"]
    base = data["variants"]["no_counterfactuals"]["count"]
    assert base < full


def test_entitlement_naive_flag_changes_value():
    p = Pipeline()
    # IGNOAPS has a tiered pension: naive picks the first (Rs.500) rule
    normal = p.run_case("IGNOAPS-2023", {"age": 65, "bpl": True})
    naive = p.run_case("IGNOAPS-2023", {"age": 65, "bpl": True},
                       deterministic_entitlement=False)
    assert normal["verdict"]["computed_entitlement"] == 200
    assert naive["verdict"]["computed_entitlement"] == 500
    assert naive["entitlement"]["entitlement"].get("naive") is True
