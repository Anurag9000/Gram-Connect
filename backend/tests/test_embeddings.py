import pytest
import numpy as np
from unittest.mock import MagicMock, patch
import sys
import os

# Add parent directory to sys.path to import embeddings
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import embeddings

def test_cosine_sim():
    a = np.array([[1, 0]])
    b = np.array([[1, 0]])
    sim = embeddings.cosine_sim(a, b)
    assert np.isclose(sim[0][0], 1.0)

    c = np.array([[0, 1]])
    sim_bc = embeddings.cosine_sim(b, c)
    assert np.isclose(sim_bc[0][0], 0.0)

@patch('sentence_transformers.SentenceTransformer')
def test_embed_texts_st_success(mock_st):
    # Mock the SentenceTransformer instance
    instance = mock_st.return_value
    instance.encode.return_value = np.array([[0.1, 0.2]])
    
    texts = ["hello world"]
    model, embs, backend = embeddings.embed_texts(texts)
    
    assert backend == "sentence-transformers"
    assert embs.shape == (1, 2)
    assert np.all(embs == np.array([[0.1, 0.2]]))

@patch('sentence_transformers.SentenceTransformer', side_effect=ImportError)
def test_embed_texts_tfidf_fallback(mock_st):
    texts = ["hello world", "foo bar"]
    model, embs, backend = embeddings.embed_texts(texts)
    
    assert backend == "tfidf"
    # TF-IDF returns a sparse matrix by default in sklearn, 
    # but embed_texts fits a TfidfVectorizer and returns X.
    # Check if we can use it to transform
    assert hasattr(model, 'transform')

def test_embed_with_st():
    mock_model = MagicMock()
    mock_model.encode.return_value = np.array([[0.5]])
    
    texts = ["test"]
    res = embeddings.embed_with(mock_model, texts, "sentence-transformers")
    assert res[0][0] == 0.5

def test_embed_with_tfidf():
    from sklearn.feature_extraction.text import TfidfVectorizer
    vec = TfidfVectorizer()
    vec.fit(["hello", "world"])
    
    texts = ["hello"]
    res = embeddings.embed_with(vec, texts, "tfidf")
    # Result should be a sparse matrix usually, but embeddings.py normalizes it
    assert res.shape[1] == 2
