import pytest
import sys
import os
from unittest.mock import patch, MagicMock
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import m3_trainer

@patch('m3_trainer.read_csv_norm')
@patch('m3_trainer.embed_texts')
@patch('os.path.exists')
def test_train_model_flow(mock_exists, mock_embed, mock_read):
    # Mock exists check
    mock_exists.return_value = True
    
    # Mock CSV reads (10 pairs to be safe for train_test_split)
    mock_read.side_effect = [
        [{"id": "prop1", "text": "proposal"}], # proposals
        [{"person_id": "p1", "text": "skills", "W": 1.0, "home_location": "V1", "availability": "immediately available"}], # people
        [{"proposal_id": "prop1", "person_id": "p1", "label": (i % 2)} for i in range(10)] # pairs: 0, 1, 0, 1...
    ]
    
    # Mock embeddings
    mock_model = MagicMock()
    mock_embed.return_value = (mock_model, np.array([[1.0]]), "tfidf")
    
    config = m3_trainer.TrainingConfig(
        proposals="prop.csv",
        people="people.csv",
        pairs="pairs.csv",
        out="test_model.pkl"
    )
    
    with patch('pickle.dump') as mock_dump:
        with patch('builtins.open', create=True):
            with patch('m3_trainer.GradientBoostingClassifier.score') as mock_score:
                mock_score.return_value = 0.9
                # Patching roc_auc_score in m3_trainer namespace
                with patch('m3_trainer.roc_auc_score') as mock_auc:
                    mock_auc.return_value = 0.95
                    auc = m3_trainer.train_model(config)
                    assert auc == 0.95
                    assert mock_dump.called

def test_build_feature_matrix():
    props = [{"id": "pr1", "text": "text1"}]
    people = [{"person_id": "pe1", "text": "skills1", "W": 1.0, "home_location": "V1", "availability": "immediately available"}]
    pairs = [{"proposal_id": "pr1", "person_id": "pe1", "label": 1}]
    
    prop_model = MagicMock()
    people_model = MagicMock()
    backend = "sentence-transformers"
    
    with patch('m3_trainer.embed_with') as mock_embed_with:
        mock_embed_with.side_effect = [
            np.array([[1.0, 0.0]]), # P
            np.array([[0.8, 0.6]])  # S
        ]
        
        X, y = m3_trainer.build_feature_matrix(
            props, people, pairs, prop_model, people_model, backend,
            {"pr1": "V1"}, {"pr1": 1}, {}, 50.0, 30.0
        )
        
        assert X.shape[0] == 1
        assert np.isclose(X[0][0], 0.8)

if __name__ == "__main__":
    pytest.main([__file__])
