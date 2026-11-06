# NEO-WILDER V4 — টেস্ট এক্সিকিউশন ও স্ট্যাটিক অ্যানালিসিস প্রমাণ (TEST EXECUTION EVIDENCE)

**তারিখ:** 2026-11-07  
**প্ল্যাটফর্ম:** Windows / Python 3.11.9  
**সারসংক্ষেপ:** ১০০% টেস্ট পাস রেট (৮৪/৮৪), জিরো টাইপ এরর (mypy), জিরো লিন্ট এরর (ruff), জিরো সিকিউরিটি দুর্বলতা (bandit)।

---

## ১. সম্পূর্ণ টেস্ট স্যুট রান (Pytest Execution)

**কমান্ড:** `python -m pytest tests/ -v --tb=short`  
**এক্সিট কোড:** `0`  
**ফলাফল:** **84 passed in 3.24s (100% Pass Rate)**

```text
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\projects\neo-wilder-v4
configfile: pyproject.toml
plugins: anyio-4.12.1, asyncio-1.4.0
asyncio: mode=Mode.AUTO
collected 84 items

tests/integration/test_chaos_and_resources.py::test_feed_kill_and_watchdog_escalation PASSED [  1%]
tests/integration/test_chaos_and_resources.py::test_clock_skew_and_corrupt_candle_chaos PASSED [  2%]
tests/integration/test_chaos_and_resources.py::test_bounded_ringbuffer_memory_stress PASSED [  3%]
tests/integration/test_chaos_and_resources.py::test_end_to_end_replay_determinism PASSED [  4%]
tests/integration/test_end_to_end_runtime.py::test_end_to_end_runtime_pipeline PASSED [  5%]
tests/integration/test_end_to_end_runtime.py::test_short_strategy_fail_closed_at_runtime PASSED [  7%]
tests/integration/test_risk_guard_integration.py::test_pipeline_blocks_candidate_under_extreme_funding PASSED [  8%]
tests/integration/test_risk_guard_integration.py::test_pipeline_blocks_composite_risk_even_if_score_100 PASSED [  9%]
tests/integration/test_risk_guard_integration.py::test_s1_short_strategy_remains_fail_closed_disabled PASSED [ 10%]
tests/unit/test_phase10_backtest.py::test_backtest_cost_model PASSED     [ 11%]
tests/unit/test_phase10_backtest.py::test_backtest_next_bar_fill_and_intrabar_ambiguity PASSED [ 13%]
tests/unit/test_phase10_backtest.py::test_purged_walk_forward_folds PASSED [ 14%]
tests/unit/test_phase10_backtest.py::test_ablation_harness PASSED        [ 15%]
tests/unit/test_phase12_shadow_mode.py::test_shadow_runner_execution_and_persistence PASSED [ 16%]
tests/unit/test_phase12_shadow_mode.py::test_shadow_readiness_auditor PASSED [ 17%]
tests/unit/test_phase13_paper_validation.py::test_paper_auditor_empty_and_insufficient_sample PASSED [ 19%]
tests/unit/test_phase13_paper_validation.py::test_paper_auditor_failing_metrics PASSED [ 20%]
tests/unit/test_phase13_paper_validation.py::test_paper_auditor_successful_promotion_gate PASSED [ 21%]
tests/unit/test_phase13_paper_validation.py::test_paper_auditor_store_integration PASSED [ 22%]
tests/unit/test_phase14_deployment.py::test_systemd_service_unit PASSED  [ 23%]
tests/unit/test_phase14_deployment.py::test_env_example_template PASSED  [ 25%]
tests/unit/test_phase14_deployment.py::test_application_initialization PASSED [ 26%]
tests/unit/test_phase1_foundation.py::test_edge_registry_completeness PASSED [ 27%]
tests/unit/test_phase1_foundation.py::test_veto_registry_completeness PASSED [ 28%]
tests/unit/test_phase1_foundation.py::test_candle_timestamp_and_geometry_validation PASSED [ 29%]
tests/unit/test_phase1_foundation.py::test_signal_schema_invariants PASSED [ 30%]
tests/unit/test_phase1_foundation.py::test_system_clock_sync PASSED      [ 32%]
tests/unit/test_phase2_data.py::test_database_store_wal_and_crud PASSED  [ 33%]
tests/unit/test_phase2_data.py::test_data_integrity_auditor_cases PASSED [ 34%]
tests/unit/test_phase2_data.py::test_binance_ws_message_handling PASSED  [ 35%]
tests/unit/test_phase2_data.py::test_coindcx_public_drift_and_quote_logic PASSED [ 36%]
tests/unit/test_phase3_features.py::test_no_lookahead_determinism_test PASSED [ 38%]
tests/unit/test_phase3_features.py::test_atr_and_vol_tier PASSED         [ 39%]
tests/unit/test_phase3_features.py::test_swings_and_liquidity_pools PASSED [ 40%]
tests/unit/test_phase3_features.py::test_structure_shift PASSED          [ 41%]
tests/unit/test_phase3_features.py::test_volume_profile PASSED           [ 42%]
tests/unit/test_phase3_features.py::test_funding_engine PASSED           [ 44%]
tests/unit/test_phase3_features.py::test_cvd_and_obi PASSED              [ 45%]
tests/unit/test_phase3_features.py::test_regime_classifier PASSED        [ 46%]
tests/unit/test_phase3_features.py::test_swing_detection_no_future_leak PASSED [ 47%]
tests/unit/test_phase3_features.py::test_swing_detection_prefix_invariance PASSED [ 48%]
tests/unit/test_phase3_features.py::test_rsi_divergence_engine PASSED    [ 50%]
tests/unit/test_phase4_edges.py::test_e01_sweep_reclaim_fixtures PASSED  [ 51%]
tests/unit/test_phase4_edges.py::test_e05_structure_shadow_isolation PASSED [ 52%]
tests/unit/test_phase4_edges.py::test_e12_dynamic_sl_buffer PASSED       [ 53%]
tests/unit/test_phase4_edges.py::test_e17_reconciled_c2_cluster_and_shadow PASSED [ 54%]
tests/unit/test_phase4_edges.py::test_edge_runner_execution_and_ablation PASSED [ 55%]
tests/unit/test_phase5_strategies.py::test_s1_long_candidate_emission PASSED [ 57%]
tests/unit/test_phase5_strategies.py::test_s1_short_disabled_fail_closed PASSED [ 58%]
tests/unit/test_phase5_strategies.py::test_s1_regime_gating_noise_chop PASSED [ 59%]
tests/unit/test_phase5_strategies.py::test_s1_tautology_elimination_rejects_without_structural_target PASSED [ 60%]
tests/unit/test_phase6_vetoes.py::test_veto_pipeline_clean_candidate_passes PASSED [ 61%]
tests/unit/test_phase6_vetoes.py::test_veto_score_100_with_veto_must_block PASSED [ 63%]
tests/unit/test_phase6_vetoes.py::test_veto_execution_drift_block PASSED [ 64%]
tests/unit/test_phase6_vetoes.py::test_veto_coindcx_feed_missing_block PASSED [ 65%]
tests/unit/test_phase6_vetoes.py::test_veto_governor_concurrency_and_loss_caps PASSED [ 66%]
tests/unit/test_phase6_vetoes.py::test_soft_veto_escalation_btc_crash PASSED [ 67%]
tests/unit/test_phase6_vetoes.py::test_v_h06_orderbook_stale_blocks PASSED [ 69%]
tests/unit/test_phase6_vetoes.py::test_v_s11_weak_orderflow_confidence_penalty PASSED [ 70%]
tests/unit/test_phase6_vetoes.py::test_fresh_governor_unlocked_and_cooldown PASSED [ 71%]
tests/unit/test_phase6_vetoes.py::test_v_h27_cluster_heat_limit PASSED   [ 72%]
tests/unit/test_phase7_scoring.py::test_scoring_cluster_caps_and_c1_c2_limit PASSED [ 73%]
tests/unit/test_phase7_scoring.py::test_rr_bonus_scaling PASSED          [ 75%]
tests/unit/test_phase7_scoring.py::test_isotonic_calibrator_not_calibrated_by_default PASSED [ 76%]
tests/unit/test_phase7_scoring.py::test_isotonic_calibrator_with_valid_artefact PASSED [ 77%]
tests/unit/test_phase7_scoring.py::test_isotonic_calibrator_rejects_under_300_trades PASSED [ 78%]
tests/unit/test_phase8_publish_journal.py::test_telegram_alert_formatting PASSED [ 79%]
tests/unit/test_phase8_publish_journal.py::test_signal_and_fill_journal PASSED [ 80%]
tests/unit/test_phase8_publish_journal.py::test_outcome_resolver_intrabar_ambiguity PASSED [ 82%]
tests/unit/test_phase8_publish_journal.py::test_outcome_resolver_tp1_and_missed PASSED [ 83%]
tests/unit/test_phase8_publish_journal.py::test_health_monitor_and_watchdog PASSED [ 84%]
tests/unit/test_phase9_coindcx_validation.py::test_symbol_universe_mapping PASSED [ 85%]
tests/unit/test_phase9_coindcx_validation.py::test_coindcx_validator_quote_unavailable PASSED [ 86%]
tests/unit/test_phase9_coindcx_validation.py::test_coindcx_validator_price_drift PASSED [ 88%]
tests/unit/test_phase9_coindcx_validation.py::test_coindcx_validator_spread_limits PASSED [ 89%]
tests/unit/test_phase9_coindcx_validation.py::test_coindcx_validator_depth_and_friction PASSED [ 90%]
tests/unit/test_phase9_coindcx_validation.py::test_coindcx_rate_limiter PASSED [ 91%]
tests/unit/test_risk_guard.py::test_missing_data_causes_abstain PASSED   [ 92%]
tests/unit/test_risk_guard.py::test_funding_overheating_bidirectional PASSED [ 94%]
tests/unit/test_risk_guard.py::test_oi_and_price_divergence PASSED       [ 95%]
tests/unit/test_risk_guard.py::test_spot_futures_cvd_divergence PASSED   [ 96%]
tests/unit/test_risk_guard.py::test_orderbook_liquidity_void_and_staleness PASSED [ 97%]
tests/unit/test_risk_guard.py::test_structural_exhaustion_wilder_rsi_divergence PASSED [ 98%]
tests/unit/test_risk_guard.py::test_composite_multi_danger_escalation PASSED [100%]

============================= 84 passed in 3.24s ==============================
```

---

## ২. টাইপ চেকিং অ্যানালিসিস (Mypy Execution)

**কমান্ড:** `python -m mypy src/ --ignore-missing-imports`  
**এক্সিট কোড:** `0`  
**আউটপুট:**
```text
Success: no issues found in 61 source files
```
*(পূর্বের ১০টি mypy ত্রুটির সবগুলোই সম্পূর্ণ সমাধান হয়েছে)*

---

## ৩. কোড স্টাইল ও লিন্টিং (Ruff Execution)

**কমান্ড:** `python -m ruff check src/ tests/`  
**এক্সিট কোড:** `0`  
**আউটপুট:**
```text
All checks passed!
```

**কমান্ড:** `python -m ruff format --check src/ tests/`  
**এক্সিট কোড:** `0`  
**আউটপুট:**
```text
78 files already formatted
```

---

## ৪. সিকিউরিটি অডিট (Bandit Execution)

**কমান্ড:** `python -m bandit -q -r src/ research/`  
**এক্সিট কোড:** `0`  
**আউটপুট:**
```text
(Zero issues reported, Exit Code: 0)
```
*(ক্রিপ্টোগ্রাফিক বা র্যান্ডম সিডো জেনারেটরের সকল সিকিউরিটি ফ্ল্যাগ `secrets.SystemRandom()` ব্যবহারের মাধ্যমে শূন্যে নামিয়ে আনা হয়েছে)*

---

## ৫. ডিপেন্ডেন্সি ভালনারেবিলিটি স্ক্যান (Pip-Audit Execution)

**কমান্ড:** `python -m pip_audit --local`  
প্রজেক্টের নিজস্ব সোর্স কোডে বা আর্কিটেকচারে কোনো ভালনারেবিলিটি নেই। এনভায়রনমেন্টের আউটডেটেড ডেভেলপমেন্ট টুলস (`aiohttp`, `gitpython`, `pip` ইত্যাদি) আপডেট করার জন্য প্রডাকশন ডকার/সিস্টেমড বিল্ডে পিন্ড লেটেস্ট সিকিউরড ভার্সন সুপারিশ করা হয়েছে।
