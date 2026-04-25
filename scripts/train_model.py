"""
Train Model Script — One-off script to train and save the anomaly detection model.

USAGE:
    python scripts/train_model.py

WHAT IT DOES:
    1. Generates 2000 synthetic logs using log_generator
    2. Extracts numeric features from each log
    3. Trains an Isolation Forest model on those features
    4. Saves the trained model to model/isolation_forest.joblib
    5. Runs a quick validation to verify the model detects anomalies

This script should be run ONCE before deploying the Lambda function.
The saved .joblib file is what gets packaged with the Lambda deployment.
"""

import sys
import os

# Add project root to path so we can import from src/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.log_generator import generate_logs
from src.anomaly_model import train, predict, save_model, anomaly_scores


def main():
    print("=" * 60)
    print("  TRAINING ANOMALY DETECTION MODEL")
    print("=" * 60)

    # ── Step 1: Generate training data ──────────────────────
    print("\n📊 Step 1: Generating 2000 synthetic logs...")
    logs = generate_logs(count=2000, anomaly_ratio=0.05)
    print(f"   Generated {len(logs)} logs")

    # Count anomalies in generated data
    anomalies_generated = sum(
        1 for log in logs
        if log["status_code"] >= 500 or log["response_time_ms"] > 1000
    )
    print(f"   Anomalies injected: ~{anomalies_generated} ({anomalies_generated/len(logs)*100:.1f}%)")

    # ── Step 2: Extract features ────────────────────────────
    print("\n🔧 Step 2: Extracting features...")
    features = []
    for log in logs:
        feature_vector = [
            float(log["response_time_ms"]),
            1.0 if log["status_code"] >= 500 else 0.0,
            1.0 if log["level"] == "WARN" else 0.0,
            float(log["status_code"]),
        ]
        features.append(feature_vector)
    print(f"   Feature matrix shape: {len(features)} x {len(features[0])}")
    print(f"   Features: [response_time_ms, is_error, is_warning, status_code]")

    # ── Step 3: Train model ─────────────────────────────────
    print("\n🤖 Step 3: Training Isolation Forest model...")
    model = train(features, contamination=0.05)

    # ── Step 4: Save model ──────────────────────────────────
    model_path = os.path.join(os.path.dirname(__file__), "..", "model", "isolation_forest.joblib")
    model_path = os.path.abspath(model_path)
    print(f"\n💾 Step 4: Saving model...")
    save_model(model, model_path)

    # ── Step 5: Validation ──────────────────────────────────
    print("\n✅ Step 5: Running validation...")
    predictions = predict(model, features)
    detected_anomalies = sum(1 for p in predictions if p == -1)
    print(f"   Model detected {detected_anomalies} anomalies out of {len(features)} samples")
    print(f"   Detection rate: {detected_anomalies/len(features)*100:.1f}%")

    # Test with known anomalous input
    test_anomaly = [[5000.0, 1.0, 0.0, 500.0]]  # High latency + 500 error
    test_normal = [[100.0, 0.0, 0.0, 200.0]]     # Normal request
    print(f"\n   Test anomaly [5000ms, 500 error]: {predict(model, test_anomaly)[0]}")
    print(f"   Test normal  [100ms, 200 OK]:     {predict(model, test_normal)[0]}")

    print("\n" + "=" * 60)
    print("  TRAINING COMPLETE ✅")
    print("=" * 60)


if __name__ == "__main__":
    main()
