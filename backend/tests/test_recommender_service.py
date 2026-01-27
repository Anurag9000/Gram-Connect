import pytest
import sys
import os
from unittest.mock import patch, MagicMock
import pickle

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import recommender_service
from m3_recommend import RecommendationConfig

def test_evaluate_team():
    # Mock team_metrics and goodness
    with patch('recommender_service.team_metrics') as mock_metrics:
        with patch('recommender_service.goodness') as mock_good:
            mock_metrics.return_value = {"coverage": 1.0, "k_robustness": 1.0, "redundancy": 0.0, "set_size": 0.5, "willingness_avg": 0.5}
            mock_good.return_value = 0.95
            
            res = recommender_service._evaluate_team(
                ["skill1"], [{"id": 1}], "backend", None, 0.35, 1, 1.0, 1.0, 0.5
            )
            assert res["score"] == 0.95
            assert res["metrics"]["coverage"] == 1.0

def test_enforce_unique_members():
    teams = [
        {"team_ids": "p1;p2", "members": [{"person_id": "p1", "name": "A"}, {"person_id": "p2", "name": "B"}], "goodness": 0.8},
        {"team_ids": "p2;p3", "members": [{"person_id": "p2", "name": "B"}, {"person_id": "p3", "name": "C"}], "goodness": 0.7}
    ]
    # p2 is in both, so second team should be modified
    with patch('recommender_service._evaluate_team') as mock_eval:
        mock_eval.return_value = {"score": 0.5, "metrics": {"coverage": 0.5, "k_robustness": 0.5, "redundancy": 0.1, "set_size": 0.1}}
        
        res = recommender_service._enforce_unique_members(
            teams, ["skill1"], "backend", None, 0.35, 1, 1.0, 1.0, 0.5
        )
        
        assert len(res) == 2
        assert res[0]["team_ids"] == "p1;p2"
        assert res[1]["team_ids"] == "p3" # p2 removed

@patch('recommender_service.load_village_names')
@patch('recommender_service.load_distance_lookup')
@patch('recommender_service.read_people')
@patch('recommender_service.embed_with')
@patch('pickle.load')
@patch('os.path.exists')
@patch('builtins.open', create=True)
def test_generate_recommendations_fusion(mock_open, mock_exists, mock_pickle, mock_embed, mock_people, mock_dist, mock_village):
    # Mock data
    mock_exists.return_value = True
    mock_pickle.return_value = {
        "model": MagicMock(),
        "backend": "tfidf",
        "prop_model": MagicMock(),
        "people_model": MagicMock()
    }
    mock_people.return_value = [{"person_id": "p1", "text": "skills", "W": 1.0, "availability": "immediately available"}]
    mock_embed.return_value = [[1.0]] # Sim matrix
    
    config = RecommendationConfig(
        model="fake.pkl",
        people="people.csv",
        proposal_text="Original text",
        transcription="Transcribed text",
        visual_tags=["Tag1"],
        task_start="2023-01-01T10:00:00",
        task_end="2023-01-01T12:00:00"
    )
    
    # We want to check if the text was fused
    # Since generate_recommendations is large, we check the result or sub-calls
    with patch('recommender_service.extract_location') as mock_loc:
        mock_loc.return_value = "Village X"
        with patch('recommender_service.estimate_severity') as mock_sev:
            mock_sev.return_value = 1
            res = recommender_service.generate_recommendations(config)
            
            # Check if text was passed to embed_with correctly (contains fused parts)
            # The first call to embed_with is for the proposal P
            args, kwargs = mock_embed.call_args_list[0]
            fused_text = args[1][0]
            assert "Original text" in fused_text
            assert "[Transcribed Audio]: Transcribed text" in fused_text
            assert "[Visual Tags]: Tag1" in fused_text

if __name__ == "__main__":
    pytest.main([__file__])