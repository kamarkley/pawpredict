from app.services.model_monitoring import (
    FeatureDriftMetric,
    MonitoringThresholds,
    WindowMetrics,
    brier_score,
    classify_health,
    expected_calibration_error,
    population_stability_index,
)


def _metrics(
    *,
    predictions=500,
    resolved=450,
    positives=45,
    coverage=0.9,
    brier=0.08,
    ece=0.03,
    calibration_gap=0.02,
):
    return WindowMetrics(
        prediction_count=predictions,
        resolved_count=resolved,
        ineligible_count=50,
        pending_count=0,
        closed_count=500,
        coverage_rate=coverage,
        positive_count=positives,
        observed_positive_rate=positives / resolved,
        avg_probability=0.10,
        brier_score=brier,
        ece=ece,
        calibration_gap=calibration_gap,
    )


def test_brier_score():
    score = brier_score([0.1, 0.8], [0, 1])
    assert score is not None
    assert abs(score - 0.025) < 1e-12


def test_ece_is_zero_for_exact_bin_calibration():
    score = expected_calibration_error([0.0, 0.0, 1.0, 1.0], [0, 0, 1, 1])
    assert score is not None
    assert score < 1e-12


def test_psi_same_distribution_is_near_zero():
    reference = [0, 0, 1, 1, 1, 0] * 100
    recent = [0, 0, 1, 1, 1, 0] * 100
    psi = population_stability_index(reference, recent)
    assert psi is not None
    assert psi < 1e-12


def test_psi_detects_shift():
    reference = [0] * 900 + [1] * 100
    recent = [0] * 400 + [1] * 600
    psi = population_stability_index(reference, recent)
    assert psi is not None
    assert psi > 0.25


def test_health_is_insufficient_when_live_sample_is_small():
    recent = _metrics(predictions=20, resolved=18, positives=1)
    reference = _metrics(predictions=20, resolved=18, positives=1)
    overall, performance, drift, reasons = classify_health(recent, reference, None, [])
    assert overall == "INSUFFICIENT_DATA"
    assert performance == "INSUFFICIENT_DATA"
    assert drift == "INSUFFICIENT_DATA"
    assert reasons


def test_health_degrades_on_large_prediction_drift():
    recent = _metrics()
    reference = _metrics()
    feature = FeatureDriftMetric(
        feature_name="minutes_since_poop",
        recent_count=500,
        reference_count=500,
        recent_mean=50.0,
        reference_mean=30.0,
        recent_std=20.0,
        reference_std=10.0,
        psi=0.30,
        drift_status="DEGRADED",
    )
    overall, performance, drift, _ = classify_health(
        recent,
        reference,
        prediction_psi=0.30,
        feature_metrics=[feature],
        thresholds=MonitoringThresholds(),
    )
    assert overall == "DEGRADED"
    assert performance == "HEALTHY"
    assert drift == "DEGRADED"
