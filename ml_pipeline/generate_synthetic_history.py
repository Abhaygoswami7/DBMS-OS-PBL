"""
Synthetic Crowd Arrival History Generator
Project: Smart Polling Booth & Time-Slot Allocation Platform (One Nation One Election)
Module: ml_pipeline/generate_synthetic_history.py

Generates a realistic, privacy-safe synthetic historical polling arrival dataset
modeled around our 8 seeded Uttarakhand polling booths and time slots.
Target: Continuous numeric voter arrival count per slot window.
"""

import os
import random
import numpy as np
import pandas as pd

# Seeded Polling Booth Specifications from Uttarakhand Election Schema
BOOTH_SPECS = {
    1: {"station_id": 1, "max_capacity": 40, "priority_cap": 10, "base_demand": 28.0},
    2: {"station_id": 1, "max_capacity": 40, "priority_cap": 10, "base_demand": 26.5},
    3: {"station_id": 2, "max_capacity": 45, "priority_cap": 12, "base_demand": 32.0},
    4: {"station_id": 2, "max_capacity": 45, "priority_cap": 12, "base_demand": 30.5},
    5: {"station_id": 3, "max_capacity": 50, "priority_cap": 15, "base_demand": 36.0},
    6: {"station_id": 3, "max_capacity": 50, "priority_cap": 15, "base_demand": 35.0},
    7: {"station_id": 4, "max_capacity": 50, "priority_cap": 15, "base_demand": 38.0},
    8: {"station_id": 4, "max_capacity": 50, "priority_cap": 15, "base_demand": 37.0},
}

def generate_synthetic_crowd_data(num_samples: int = 1500, random_seed: int = 42) -> pd.DataFrame:
    """
    Generates synthetic historical crowd arrivals with realistic operational distributions:
    - Peak waves in morning (08:00 - 11:00) and post-lunch (14:00 - 16:00)
    - Weather comfort index (0.5 to 1.0)
    - ONOE dual ballot verification factor (1.15 to 1.30)
    - Historical baseline vs. actual booked capacity
    """
    np.random.seed(random_seed)
    random.seed(random_seed)

    rows = []
    booth_ids = list(BOOTH_SPECS.keys())

    for i in range(num_samples):
        booth_id = int(np.random.choice(booth_ids))
        spec = BOOTH_SPECS[booth_id]
        max_cap = spec["max_capacity"]
        priority_cap = spec["priority_cap"]
        base_demand = spec["base_demand"]

        # Election day operational hours: 8 to 17
        hour_of_day = int(np.random.randint(8, 18))

        # Peak waves
        is_peak_morning_wave = 1 if 8 <= hour_of_day <= 11 else 0
        is_post_lunch_wave = 1 if 14 <= hour_of_day <= 16 else 0

        # Weather comfort index: 0.50 to 1.00 (cooler mornings higher, hot afternoons lower)
        if 8 <= hour_of_day <= 10:
            weather_comfort_index = round(float(np.random.uniform(0.85, 1.00)), 3)
        elif 12 <= hour_of_day <= 14:
            weather_comfort_index = round(float(np.random.uniform(0.55, 0.75)), 3)
        else:
            weather_comfort_index = round(float(np.random.uniform(0.70, 0.90)), 3)

        # ONOE Dual Ballot Factor: 1.15 to 1.30 (EVM dual unit processing)
        onoe_dual_ballot_factor = round(float(np.random.uniform(1.15, 1.30)), 3)

        # Historical baseline arrivals with natural booth variance
        hist_noise = np.random.normal(0, 2.5)
        historical_avg_arrivals = round(float(np.clip(base_demand + hist_noise, 15.0, max_cap)), 2)

        # Confirmed bookings count in the platform for that slot
        booking_ratio = np.random.beta(a=4, b=2) if is_peak_morning_wave else np.random.beta(a=2, b=3)
        confirmed_bookings_count = int(np.clip(round(booking_ratio * max_cap), 2, max_cap))

        # Ground truth arrival calculation modeling voter turnout behavior:
        # Base demand + morning wave burst + weather boost + walk-in factor influenced by dual ballot queueing
        wave_boost = 6.5 * is_peak_morning_wave + 3.8 * is_post_lunch_wave
        weather_factor = (weather_comfort_index - 0.75) * 8.0
        booking_contribution = 0.55 * confirmed_bookings_count
        hist_contribution = 0.35 * historical_avg_arrivals
        dual_ballot_impact = (onoe_dual_ballot_factor - 1.15) * 12.0
        stochastic_noise = np.random.normal(0, 1.8)

        expected_arrivals = (
            booking_contribution +
            hist_contribution +
            wave_boost +
            weather_factor +
            dual_ballot_impact +
            stochastic_noise
        )

        # Clip expected arrivals between 5 and 1.25 * max_capacity (allowing realistic mild over-demand)
        expected_arrivals = round(float(np.clip(expected_arrivals, 5.0, max_cap * 1.25)), 2)

        rows.append({
            "booth_id": booth_id,
            "hour_of_day": hour_of_day,
            "slot_max_capacity": max_cap,
            "priority_reserved_capacity": priority_cap,
            "historical_avg_arrivals": historical_avg_arrivals,
            "confirmed_bookings_count": confirmed_bookings_count,
            "is_peak_morning_wave": is_peak_morning_wave,
            "is_post_lunch_wave": is_post_lunch_wave,
            "weather_comfort_index": weather_comfort_index,
            "onoe_dual_ballot_factor": onoe_dual_ballot_factor,
            "expected_crowd_arrivals": expected_arrivals
        })

    df = pd.DataFrame(rows)
    return df

def main():
    artifact_dir = os.path.join(os.path.dirname(__file__), "artifacts")
    os.makedirs(artifact_dir, exist_ok=True)
    output_path = os.path.join(artifact_dir, "synthetic_crowd_history.csv")

    df = generate_synthetic_crowd_data(num_samples=1500, random_seed=42)
    df.to_csv(output_path, index=False)
    print(f"Generated {len(df)} synthetic crowd history records at: {output_path}")
    print("Dataset Summary:")
    print(df.describe().round(2))

if __name__ == "__main__":
    main()
