"""
test_forge_utils.py — Unit tests for the Forge deterministic scoring engine.
Replaces test_m3_recommend_utils.py.
"""

import math
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import forge


def test_sigmoid():
    assert abs(forge._sigmoid(0) - 0.5) < 1e-6
    assert forge._sigmoid(100) > 0.99
    assert forge._sigmoid(-100) < 0.01


def test_skill_overlap_exact():
    required = ["handpump repair and maintenance", "plumbing"]
    skills   = ["plumbing", "construction"]
    score, covered = forge._skill_overlap(skills, required)
    assert covered == {"plumbing"}
    assert abs(score - 0.5) < 1e-6


def test_skill_overlap_partial():
    required = ["pump maintenance"]
    skills   = ["handpump pump maintenance kit"]
    score, covered = forge._skill_overlap(skills, required)
    assert score > 0.0      # partial credit
    assert score <= 1.0


def test_skill_overlap_no_match():
    required = ["solar energy"]
    skills   = ["plumbing", "construction"]
    score, covered = forge._skill_overlap(skills, required)
    assert score == 0.0
    assert len(covered) == 0


def test_estimate_severity():
    assert forge.estimate_severity("This is an urgent emergency") == 2   # HIGH
    assert forge.estimate_severity("Critical water failure") == 2        # HIGH
    assert forge.estimate_severity("Routine repair of road") == 0        # LOW — "routine" matches
    assert forge.estimate_severity("The handpump needs attention") == 1  # NORMAL — no signal words


def test_extract_required_skills_handpump():
    skills = forge.extract_required_skills("Broken handpump near the school needs repair")
    assert "plumbing" in skills
    assert "handpump repair and maintenance" in skills


def test_extract_required_skills_solar():
    skills = forge.extract_required_skills("Solar panel installation for rural electrification")
    assert "solar microgrid design and maintenance" in skills


def test_score_volunteer_domain_zero():
    v = {
        "person_id": "V1", "name": "Test",
        "skills": ["solar panels", "wiring"],
        "willingness_eff": 0.9, "willingness_bias": 0.9,
        "availability": "immediately available",
        "home_location": "Lakshmipur", "overwork_hours": 0,
    }
    required = ["plumbing", "handpump repair and maintenance"]
    result = forge.score_volunteer(v, required, "Lakshmipur", {}, 1)
    # DOMAIN = 0 → forge_score = 0 (multiplicative kills it)
    assert result["forge_score"] == 0.0
    assert result["domain_score"] == 0.0
    assert result["match_score"] == 0.0


def test_score_volunteer_full_match():
    v = {
        "person_id": "V2", "name": "Plumber",
        "skills": ["plumbing", "handpump repair and maintenance"],
        "willingness_eff": 0.9, "willingness_bias": 0.7,
        "availability": "immediately available",
        "home_location": "Lakshmipur", "overwork_hours": 0,
    }
    required = ["plumbing", "handpump repair and maintenance"]
    result = forge.score_volunteer(v, required, "Lakshmipur", {}, 1)
    assert result["domain_score"] == 1.0
    assert result["forge_score"] > 0.5
    assert result["match_score"] == round(result["forge_score"], 4)


def test_team_coverage():
    team = [
        {"covered_skills": {"plumbing", "construction"}},
        {"covered_skills": {"water quality assessment"}},
    ]
    required = ["plumbing", "construction", "water quality assessment", "gis"]
    coverage = forge._team_coverage(team, required)
    assert abs(coverage - 3/4) < 1e-6


def test_geometric_mean():
    assert abs(forge._geometric_mean([1.0, 1.0, 1.0]) - 1.0) < 1e-6
    # One zero member tanks the team
    assert forge._geometric_mean([1.0, 1.0, 0.0]) < 0.01


def test_build_one_team_selects_relevant():
    """Plumber should be picked over solar engineer for handpump task."""
    required = ["plumbing", "handpump repair and maintenance"]

    def make_vol(pid, skills, avail="immediately available"):
        v = {
            "person_id": pid, "name": pid, "skills": skills,
            "willingness_eff": 0.8, "willingness_bias": 0.6,
            "availability": avail, "home_location": "Lakshmipur", "overwork_hours": 0,
        }
        return forge.score_volunteer(v, required, "Lakshmipur", {}, 1)

    plumber = make_vol("P1", ["plumbing", "handpump repair and maintenance"])
    solar   = make_vol("P2", ["solar panels", "rural electrification"])

    scored  = sorted([plumber, solar], key=lambda x: x["forge_score"], reverse=True)
    team    = forge._build_one_team(scored, required, 1, set())
    assert team[0]["person_id"] == "P1"
