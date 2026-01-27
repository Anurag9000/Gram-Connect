import pytest
import sys
import os
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import m3_recommend

def test_sigmoid():
    assert m3_recommend.sigmoid(0) == 0.5
    assert m3_recommend.sigmoid(100) > 0.99
    assert m3_recommend.sigmoid(-100) < 0.01

def test_normalize_phrase():
    assert m3_recommend.normalize_phrase("  Hello  World!  ") == "hello world"

def test_estimate_severity():
    # SEVERITY_KEYWORDS are internal but we can test known words
    assert m3_recommend.estimate_severity("This is a medical emergency") == 2 # HIGH
    assert m3_recommend.estimate_severity("This is critical") == 2 # HIGH
    assert m3_recommend.estimate_severity("Routine repair") == 1 # NORMAL
    assert m3_recommend.estimate_severity("Small issue") == 0 # LOW

def test_severity_penalty():
    # SEVERITY_AVAILABILITY_PENALTIES is 2: {"generally available": 0.2, "rarely available": 0.4}
    assert m3_recommend.severity_penalty("rarely available", 2) == 0.4
    assert m3_recommend.severity_penalty("immediately available", 2) == 0.0

def test_parse_size_buckets():
    spec = "small:1-2:10,large:10-inf:5"
    buckets = m3_recommend.parse_size_buckets(spec)
    assert len(buckets) == 2
    assert buckets[0]["label"] == "small"
    assert buckets[0]["min"] == 1
    assert buckets[0]["max"] == 2
    assert buckets[0]["limit"] == 10
    
    assert buckets[1]["label"] == "large"
    assert buckets[1]["max"] == float('inf')

def test_goodness():
    metrics = {
        "coverage": 0.8,
        "k_robustness": 0.5,
        "redundancy": 0.2,
        "set_size": 0.1,
        "willingness_avg": 0.9
    }
    # goodness calculation:
    # s = 0.8 + 0.5 + 0.9*0.5 - 0.2*1 - 0.1*1 = 1.3 + 0.45 - 0.2 - 0.1 = 1.45
    # goodness = (1.45 + 2.0) / 4.0 = 3.45 / 4.0 = 0.8625
    score = m3_recommend.goodness(metrics)
    assert abs(score - 0.8625) < 1e-9

def test_intervals_overlap():
    i1 = (datetime(2023, 1, 1, 10), datetime(2023, 1, 1, 12))
    i2 = (datetime(2023, 1, 1, 11), datetime(2023, 1, 1, 13))
    assert m3_recommend.intervals_overlap([i1], i2) is True
    
    i3 = (datetime(2023, 1, 1, 13), datetime(2023, 1, 1, 14))
    assert m3_recommend.intervals_overlap([i1], i3) is False

if __name__ == "__main__":
    pytest.main([__file__])
