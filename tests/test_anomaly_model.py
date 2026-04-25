"""
Tests for anomaly_model.py

WHAT WE'RE TESTING:
  1. Training — Does the model train without errors?
  2. Predictions — Does it return the correct format (1 or -1)?
  3. Anomaly detection — Does it actually flag obvious anomalies?
  4. Save/Load — Can we serialize and deserialize the model?
"""

import os
import tempfile
import numpy as np
import pytest

from src.anomaly_model import train, predict, anomaly_scores, save_model, load_model


def make_training_data(n_normal=200, n_anomalous=10):
    """
    Generate simple training data for tests.
    Normal: response_time ~100ms, status 200
    Anomalous: response_time ~5000ms, status 500
    """
    normal = [
        [np.random.uniform(50, 200), 0.0, 0.0, 200.0]
        for _ in range(n_normal)
    ]
    anomalous = [
        [np.random.uniform(3000, 8000), 1.0, 0.0, 500.0]
        for _ in range(n_anomalous)
    ]
    return normal + anomalous


class TestTrain:
    """Test model training."""

    def test_trains_successfully(self):
        """Model should train without errors on valid data."""
        data = make_training_data()
        model = train(data)
        assert model is not None

    def test_trains_with_custom_contamination(self):
        """Should accept custom contamination parameter."""
        data = make_training_data()
        model = train(data, contamination=0.1)
        assert model is not None


class TestPredict:
    """Test model predictions."""

    def test_returns_correct_format(self):
        """Predictions should be numpy array of 1s and -1s."""
        data = make_training_data()
        model = train(data)
        preds = predict(model, data)
        assert all(p in (1, -1) for p in preds)

    def test_detects_obvious_anomaly(self):
        """Extreme outlier should be classified as anomaly (-1)."""
        data = make_training_data()
        model = train(data)
        # This is so far from normal it MUST be an anomaly
        extreme_anomaly = [[10000.0, 1.0, 1.0, 500.0]]
        result = predict(model, extreme_anomaly)
        assert result[0] == -1

    def test_classifies_normal_correctly(self):
        """Clearly normal input should be classified as normal (1)."""
        data = make_training_data()
        model = train(data)
        normal_input = [[100.0, 0.0, 0.0, 200.0]]
        result = predict(model, normal_input)
        assert result[0] == 1

    def test_single_sample_prediction(self):
        """Should handle single-sample (1D) input correctly."""
        data = make_training_data()
        model = train(data)
        result = predict(model, [100.0, 0.0, 0.0, 200.0])
        assert len(result) == 1


class TestAnomalyScores:
    """Test anomaly scoring."""

    def test_anomaly_has_lower_score(self):
        """Anomalies should have lower (more negative) scores than normal."""
        data = make_training_data()
        model = train(data)
        normal_score = anomaly_scores(model, [[100.0, 0.0, 0.0, 200.0]])[0]
        anomaly_score = anomaly_scores(model, [[8000.0, 1.0, 1.0, 500.0]])[0]
        assert anomaly_score < normal_score


class TestSaveLoad:
    """Test model serialization."""

    def test_save_and_load(self):
        """Model should produce same predictions after save/load cycle."""
        data = make_training_data()
        model = train(data)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test_model.joblib")
            save_model(model, path)

            loaded_model = load_model(path)
            original_preds = predict(model, data)
            loaded_preds = predict(loaded_model, data)
            np.testing.assert_array_equal(original_preds, loaded_preds)

    def test_load_nonexistent_raises(self):
        """Loading a missing file should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_model("/nonexistent/path/model.joblib")
