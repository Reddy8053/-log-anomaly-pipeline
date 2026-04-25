"""
Anomaly Detection Model — Isolation Forest wrapper.

HOW ISOLATION FOREST WORKS:
============================
Isolation Forest is an UNSUPERVISED anomaly detection algorithm.
Unlike supervised models, it does NOT need labeled training data
(we don't need to tell it "this is normal" vs "this is anomalous").

The core idea is elegant:
  1. Randomly select a feature (e.g., response_time_ms)
  2. Randomly select a split value between the min and max of that feature
  3. This creates a partition — repeat recursively to build a tree
  4. ANOMALIES are isolated (end up alone) in FEWER splits
     because they have unusual feature values

  Think of it like this: if a data point is very different from others,
  a random split is likely to separate it early. Normal points, being
  clustered together, need more splits to isolate.

  ┌──────────────────────────────┐
  │     Normal points (many)     │
  │         ·  · ·               │  ← Needs many splits to isolate
  │        · · · ·               │     any single point
  │         · · ·                │
  │                              │
  │                   ★          │  ← Anomaly: isolated quickly
  └──────────────────────────────┘

KEY PARAMETERS:
  - contamination: Expected fraction of anomalies (we use 0.05 = 5%)
  - n_estimators: Number of trees in the forest (100 = good default)
  - random_state: For reproducibility

PREDICTIONS:
  -  1 = Normal
  - -1 = Anomaly
"""

import os
import numpy as np
from sklearn.ensemble import IsolationForest
import joblib


# ──────────────────────────────────────────────
# Default model parameters
# ──────────────────────────────────────────────
DEFAULT_CONTAMINATION = 0.05  # Expect ~5% anomalies
DEFAULT_N_ESTIMATORS = 100    # Number of isolation trees
DEFAULT_RANDOM_STATE = 42     # Reproducibility


def train(features, contamination=DEFAULT_CONTAMINATION):
    """
    Train an Isolation Forest model on the given features.

    Parameters
    ----------
    features : array-like of shape (n_samples, n_features)
        Training data — each row is a feature vector:
        [response_time_ms, is_error, is_warning, status_code]
    contamination : float
        Expected proportion of outliers in the training set.

    Returns
    -------
    IsolationForest
        Fitted model ready for predictions.
    """
    X = np.array(features)
    model = IsolationForest(
        contamination=contamination,
        n_estimators=DEFAULT_N_ESTIMATORS,
        random_state=DEFAULT_RANDOM_STATE,
    )
    model.fit(X)
    print(f"✅ Model trained on {X.shape[0]} samples, {X.shape[1]} features")
    return model


def predict(model, features):
    """
    Predict whether each sample is normal (1) or anomalous (-1).

    Parameters
    ----------
    model : IsolationForest
        Trained model.
    features : array-like of shape (n_samples, n_features)
        Feature vectors to classify.

    Returns
    -------
    numpy.ndarray
        Array of predictions: 1 (normal) or -1 (anomaly).
    """
    try:
        import numpy as np
        X_np = np.array(features)
        if X_np.ndim == 1:
            X_np = X_np.reshape(1, -1)
        return model.predict(X_np).tolist()
    except (ModuleNotFoundError, ImportError):
        # Fallback raw list processing
        return model.predict(features)


def anomaly_scores(model, features):
    """
    Get anomaly scores for each sample.
    Lower (more negative) scores indicate stronger anomalies.

    Parameters
    ----------
    model : IsolationForest
        Trained model.
    features : array-like

    Returns
    -------
    numpy.ndarray
        Anomaly scores (negative = more anomalous).
    """
    X = np.array(features)
    if X.ndim == 1:
        X = X.reshape(1, -1)
    return model.decision_function(X)


def save_model(model, path="model/isolation_forest.joblib"):
    """
    Serialize the trained model to disk using joblib.

    WHY JOBLIB?
    joblib is optimized for serializing numpy arrays and scikit-learn
    models. It's faster and more compact than pickle for these objects.
    """
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    joblib.dump(model, path)
    print(f"✅ Model saved → {path}")


def load_model(path="model/isolation_forest.joblib"):
    """
    Load a previously saved model from disk.

    In Lambda, the model is packaged as a Lambda Layer and
    available at /opt/model/isolation_forest.joblib
    """
    try:
        import joblib
        if not os.path.exists(path):
            raise FileNotFoundError(f"Model not found at {path}")
        model = joblib.load(path)
        print(f"✅ Model loaded ← {path}")
        return model
    except ModuleNotFoundError:
        # Fallback dummy model for AWS Lambda to avoid heavy C-extensions
        class FallbackModel:
            def predict(self, features):
                # Features: [response_time, is_error, is_warning, status_code]
                # Fallback heuristic: Mark 500+ errors or >2000ms latency as anomalies (-1)
                return [-1 if f[1] == 1.0 or f[0] > 2000 else 1 for f in features]
        return FallbackModel()
