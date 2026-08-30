import json
from pathlib import Path

MATRIX = Path(__file__).parents[1] / "host_tests" / "matrix.json"


def load_matrix() -> dict:
    return json.loads(MATRIX.read_text(encoding="utf-8"))


def test_phase65_matrix_is_closed_without_turning_q_into_pass() -> None:
    matrix = load_matrix()
    results = {item["id"]: item for item in matrix["results"]}

    assert matrix["qualification_phase"] == "6.5"
    assert matrix["phase_status"] == "CLOSED"
    assert set(results) == set("ABCDEFGHIJKLMNOPQRSTUV")
    assert all(results[row]["status"] == "PASS" for row in "ABCDEFGHIJKLMNOP")
    assert results["Q"]["status"] == "ROW_Q_HOST_CONDITION_UNAVAILABLE"
    assert all(results[row]["status"] == "PASS" for row in "RSTUV")


def test_phase65_final_classifications_and_consumption_are_frozen() -> None:
    closure = load_matrix()["phase65_closure"]
    final = closure["final_attempts"]

    assert final["T-v11"]["classification"] == (
        "ROW_T_FORMAL_PASS_ALTERNATE_PROFILE_PREVIEW_SAMPLE_COMMIT_CONSISTENT"
    )
    assert final["U-v1"]["classification"] == (
        "ROW_U_FORMAL_PASS_TWO_VIEWS_ONE_WINDOW_AMBIGUOUS_CANVAS_FAIL_CLOSED"
    )
    assert final["V-v2"]["classification"] == (
        "ROW_V_FORMAL_PASS_WORKER_ACTIVE_DOCKER_CLOSE_STALE_PUBLISH_SUPPRESSED"
    )
    for evidence in final.values():
        assert evidence["attempt_consumed_at"] == "HARNESS_RUN_CALL_STARTED"
        assert evidence["successful_return_boundaries"] == [
            "HARNESS_RUN_RETURNED",
            "LAUNCHER_RETURN_READY",
        ]


def test_phase65_governance_history_and_external_observations_are_separate() -> None:
    closure = load_matrix()["phase65_closure"]

    assert closure["governance"]["T"] == "ROW_T_DISPLAY_ORACLE_V2_GOVERNANCE_ADOPTED"
    assert closure["governance"]["V"] == (
        "ROW_V_WORKER_ACTIVE_SHUTDOWN_CONTRACT_V1_GOVERNANCE_ADOPTED"
    )
    observations = closure["operator_crash_observations"]
    assert observations["evidence_kind"] == (
        "external_operator_observation_not_formal_result_json"
    )
    assert {key: observations[key] for key in ("T-v11", "U-v1", "V-v2")} == {
        "T-v11": "NO",
        "U-v1": "NO",
        "V-v2": "NO",
    }
    assert closure["historical_attempts"]["T-v8"]["classification"] == (
        "ROW_T_SEMANTIC_CORE_FAIL_COLOR_CONVERSION"
    )
    assert closure["historical_attempts"]["V-v1"]["classification"] == (
        "ROW_V_V1_FORMAL_INVOCATION_CONSUMED_HARNESS_FAIL_CORE_UNJUDGED"
    )


def test_phase65_frozen_production_identities_and_limits() -> None:
    closure = load_matrix()["phase65_closure"]
    hashes = closure["frozen_hashes"]

    assert hashes["production_semantic_sha256"] == (
        "b3812c8a00aa359097d9395b13d27e55433b311584a00e6906de0f426f5acc38"
    )
    assert hashes["lifecycle_sha256"] == (
        "94b42368efc0df7c37333fe864f57593254557c2b181676106efd0a45e535e5f"
    )
    assert hashes["display_oracle_v2_sha256"] == (
        "a0d6a02bcc678ed316a18e26da17a693293e0ac22d4579d992de6eeb21844f35"
    )
    limits = "\n".join(closure["known_limitations"])
    assert "HiDPI condition was unavailable" in limits
    assert "full Krita application close" in limits
    assert "INSUFFICIENT_FOR_GAPFILL_PARITY" in limits
