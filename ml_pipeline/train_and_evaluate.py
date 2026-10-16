"""
Crowd Prediction Model Training and Evaluation Pipeline
Project: Smart Polling Booth & Time-Slot Allocation Platform (One Nation One Election)
Module: ml_pipeline/train_and_evaluate.py

Trains and compares two predictive models on an 80/20 train-test split:
  1. Baseline Model (HistoricalSlotBaseline): Heuristic based on historical arrival rate and slot capacity.
  2. Machine Learning Model (RandomForestRegressor): StandardScaler + RandomForestRegressor(n_estimators=150, max_depth=10, random_state=42).

Outputs:
  - ml_pipeline/artifacts/rf_crowd_model.joblib
  - ml_pipeline/artifacts/feature_scaler.joblib
  - ml_pipeline/artifacts/evaluation_metrics.json
"""

import os
import json
import datetime
import joblib
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

FEATURE_COLUMNS = [
    "booth_id",
    "hour_of_day",
    "slot_max_capacity",
    "priority_reserved_capacity",
    "historical_avg_arrivals",
    "confirmed_bookings_count",
    "is_peak_morning_wave",
    "is_post_lunch_wave",
    "weather_comfort_index",
    "onoe_dual_ballot_factor"
]

TARGET_COLUMN = "expected_crowd_arrivals"

class HistoricalSlotBaseline:
    """
    Baseline Forecasting Model:
    Estimates demand using historical mean arrival rate adjusted by slot capacity booking ratio.
    """
    def __init__(self):
        self.mean_demand_ratio = 1.0

    def fit(self, X: pd.DataFrame, y: pd.Series):
        # Calculate overall mean arrival to historical ratio
        hist_series = X["historical_avg_arrivals"].replace(0, 1)
        ratios = y / hist_series
        self.mean_demand_ratio = float(np.mean(ratios))
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        # Heuristic: base historical scaled by ratio of confirmed bookings to capacity
        booking_ratio = X["confirmed_bookings_count"] / X["slot_max_capacity"]
        heuristic_factor = 0.6 + 0.4 * booking_ratio
        predictions = X["historical_avg_arrivals"] * self.mean_demand_ratio * heuristic_factor
        return predictions.to_numpy()

def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """Computes MAE, RMSE, and R2 score."""
    mae = float(mean_absolute_error(y_true, y_pred))
    mse = float(mean_squared_error(y_true, y_pred))
    rmse = float(np.sqrt(mse))
    r2 = float(r2_score(y_true, y_pred))
    return {
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "r2_score": round(r2, 4)
    }

def train_and_evaluate_models(data_path: str, artifacts_dir: str) -> Dict[str, Any]:
    """
    Executes model training, quantitative comparison, and artifact serialization.
    """
    df = pd.read_csv(data_path)
    X = df[FEATURE_COLUMNS]
    y = df[TARGET_COLUMN]

    # 80/20 train-test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42
    )

    # 1. Baseline Model
    baseline_model = HistoricalSlotBaseline()
    baseline_model.fit(X_train, y_train)
    baseline_preds = baseline_model.predict(X_test)
    baseline_metrics = compute_metrics(y_test.to_numpy(), baseline_preds)

    # 2. Scikit-Learn Random Forest Model with Feature Scaler
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    rf_model = RandomForestRegressor(
        n_estimators=150,
        max_depth=10,
        random_state=42,
        n_jobs=-1
    )
    rf_model.fit(X_train_scaled, y_train)
    rf_preds = rf_model.predict(X_test_scaled)
    rf_metrics = compute_metrics(y_test.to_numpy(), rf_preds)

    # Compute Feature Importances
    feature_importances = {
        col: round(float(imp), 4)
        for col, imp in zip(FEATURE_COLUMNS, rf_model.feature_importances_)
    }

    # Verify Random Forest outperforms Baseline
    mae_improvement_pct = round(
        ((baseline_metrics["mae"] - rf_metrics["mae"]) / baseline_metrics["mae"]) * 100, 2
    )
    rmse_improvement_pct = round(
        ((baseline_metrics["rmse"] - rf_metrics["rmse"]) / baseline_metrics["rmse"]) * 100, 2
    )

    evaluation_report = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "dataset_rows": len(df),
        "train_rows": len(X_train),
        "test_rows": len(X_test),
        "feature_columns": FEATURE_COLUMNS,
        "target_column": TARGET_COLUMN,
        "baseline_model": {
            "model_type": "HistoricalSlotBaseline",
            "metrics": baseline_metrics
        },
        "random_forest_model": {
            "model_type": "RandomForestRegressor(n_estimators=150, max_depth=10)",
            "metrics": rf_metrics,
            "feature_importances": feature_importances
        },
        "comparison": {
            "mae_improvement_pct": mae_improvement_pct,
            "rmse_improvement_pct": rmse_improvement_pct,
            "rf_outperforms_baseline": bool(
                rf_metrics["mae"] < baseline_metrics["mae"] and rf_metrics["rmse"] < baseline_metrics["rmse"]
            )
        }
    }

    # Save artifacts
    rf_model_path = os.path.join(artifacts_dir, "rf_crowd_model.joblib")
    scaler_path = os.path.join(artifacts_dir, "feature_scaler.joblib")
    metrics_path = os.path.join(artifacts_dir, "evaluation_metrics.json")

    joblib.dump(rf_model, rf_model_path)
    joblib.dump(scaler, scaler_path)

    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(evaluation_report, f, indent=2)

    return evaluation_report

def main():
    base_dir = os.path.dirname(__file__)
    artifacts_dir = os.path.join(base_dir, "artifacts")
    data_path = os.path.join(artifacts_dir, "synthetic_crowd_history.csv")

    if not os.path.exists(data_path):
        print(f"Dataset not found at {data_path}. Generating synthetic data first...")
        from ml_pipeline.generate_synthetic_history import generate_synthetic_crowd_data
        df = generate_synthetic_crowd_data(1500, 42)
        os.makedirs(artifacts_dir, exist_ok=True)
        df.to_csv(data_path, index=False)

    print("Training and Evaluating Baseline vs. Random Forest Crowd Models...")
    report = train_and_evaluate_models(data_path, artifacts_dir)

    print("\n" + "=" * 60)
    print("AI/ML CROWD PREDICTION EVALUATION REPORT")
    print("=" * 60)
    print(f"Timestamp: {report['timestamp']}")
    print(f"Train samples: {report['train_rows']} | Test samples: {report['test_rows']}")
    print("-" * 60)
    print("1. BASELINE MODEL (HistoricalSlotBaseline):")
    print(f"   MAE:     {report['baseline_model']['metrics']['mae']:.4f}")
    print(f"   RMSE:    {report['baseline_model']['metrics']['rmse']:.4f}")
    print(f"   R2:      {report['baseline_model']['metrics']['r2_score']:.4f}")
    print("-" * 60)
    print("2. MACHINE LEARNING MODEL (RandomForestRegressor):")
    print(f"   MAE:     {report['random_forest_model']['metrics']['mae']:.4f}")
    print(f"   RMSE:    {report['random_forest_model']['metrics']['rmse']:.4f}")
    print(f"   R2:      {report['random_forest_model']['metrics']['r2_score']:.4f}")
    print("-" * 60)
    print("COMPARATIVE IMPROVEMENT:")
    print(f"   MAE Improvement:  {report['comparison']['mae_improvement_pct']}%")
    print(f"   RMSE Improvement: {report['comparison']['rmse_improvement_pct']}%")
    print(f"   RF Outperforms:   {report['comparison']['rf_outperforms_baseline']}")
    print("=" * 60)
    print(f"Saved artifacts to {artifacts_dir}")

if __name__ == "__main__":
    main()
