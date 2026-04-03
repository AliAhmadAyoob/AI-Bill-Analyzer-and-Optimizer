# ml_predictor.py
# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — Proper ML model integration
#
# The ML model is now the PRIMARY source of energy predictions.
# It takes the user's appliance inputs, predicts daily kWh,
# scales it to monthly, and that number drives EVERYTHING else
# (bill calculation, optimizer, recommendations).
#
# If the model file is missing, we fall back to physics-based math
# so the app never breaks.
# ─────────────────────────────────────────────────────────────────────────────

import os
import json
import numpy as np
import joblib

MODEL_PATH   = os.path.join('model', 'electricity_model.pkl')
FEATURE_PATH = os.path.join('model', 'feature_cols.json')

# Load once at import time
_model        = None
_feature_cols = None

if os.path.exists(MODEL_PATH):
    _model = joblib.load(MODEL_PATH)
    print(f'[ml_predictor] Model loaded: {type(_model).__name__}')

if os.path.exists(FEATURE_PATH):
    with open(FEATURE_PATH) as f:
        _feature_cols = json.load(f)


# ─────────────────────────────────────────────────────────────────────────────
# Public function: predict_from_appliances
# ─────────────────────────────────────────────────────────────────────────────

def predict_from_appliances(appliances: list, family_members: int, season: int) -> dict:
    """
    Given a list of appliance dicts (type, hours, quantity),
    returns a prediction dict:
      {
        daily_kwh:        float   — predicted daily kWh
        monthly_kwh:      float   — daily × 30
        method:           str     — 'ml_model' or 'physics_fallback'
        model_name:       str     — e.g. 'RandomForestRegressor'
        confidence:       str     — 'high' / 'medium' / 'low'
        feature_vector:   dict    — the inputs sent to the model (for transparency)
      }
    """
    features = _build_feature_vector(appliances, family_members, season)

    if _model is not None:
        return _predict_with_model(features)
    else:
        return _predict_with_physics(appliances)


# ─────────────────────────────────────────────────────────────────────────────
# Feature engineering — mirrors exactly what the training notebook produced
# ─────────────────────────────────────────────────────────────────────────────

WATTAGE = {
    'AC_1_ton': 1200, 'AC_1.5_ton': 1800, 'AC_2_ton': 2400,
    'inverter_ac': 1100, 'geyser': 3000, 'washing_machine': 500,
    'iron': 1000, 'microwave': 1200, 'water_pump': 750,
    'tv': 120, 'computer': 150, 'refrigerator': 150,
    'fans': 75, 'led_lights': 50,
}


def _build_feature_vector(appliances: list, family_members: int, season: int) -> dict:
    """
    Converts the raw appliance list into the exact feature columns
    the model was trained on.
    """
    # Collect hours per appliance type
    hours = {}
    qty   = {}
    for a in appliances:
        t = a.get('type', '')
        hours[t] = float(a.get('hours', 0))
        qty[t]   = int(a.get('quantity', 1))

    # AC — use the heaviest AC type present
    ac_hours  = max(hours.get('AC_2_ton', 0), hours.get('AC_1.5_ton', 0),
                    hours.get('AC_1_ton', 0), hours.get('inverter_ac', 0))
    ac_ton    = 2.0 if hours.get('AC_2_ton', 0) > 0 else \
                1.5 if hours.get('AC_1.5_ton', 0) > 0 or hours.get('inverter_ac', 0) > 0 else \
                1.0 if hours.get('AC_1_ton', 0) > 0 else 0.0

    geyser_hrs = hours.get('geyser', 0)
    fridge_hrs = hours.get('refrigerator', 24)
    wm_hrs     = hours.get('washing_machine', 0)

    # Fridge size: 1=small,2=medium,3=large (estimate from hours — always on)
    fridge_size = 2  # default medium

    peak_usage = 1 if ac_hours > 5 else 0

    import datetime
    now = datetime.datetime.now()

    fv = {
        'AC_Hours':             ac_hours,
        'AC_Tonnage':           ac_ton,
        'Fridge_Hours':         fridge_hrs,
        'Fridge_Size':          fridge_size,
        'Geyser_Hours':         geyser_hrs,
        'WashingMachine_Hours': wm_hrs,
        'Family_Members':       float(family_members),
        'Season':               int(season),
        'Month':                now.month,
        'DayOfWeek':            now.weekday(),
        'Peak_Usage':           peak_usage,
    }
    return fv


def _predict_with_model(feature_vector: dict) -> dict:
    """Run the trained ML model and return prediction."""
    # Build numpy row in the correct column order
    cols = _feature_cols if _feature_cols else list(feature_vector.keys())
    row  = np.array([[feature_vector.get(c, 0) for c in cols]])

    daily_kwh   = float(_model.predict(row)[0])
    daily_kwh   = max(0.5, daily_kwh)          # floor at 0.5 kWh/day

    # Confidence based on feature completeness
    non_zero = sum(1 for v in feature_vector.values() if v > 0)
    confidence = 'high' if non_zero >= 7 else ('medium' if non_zero >= 4 else 'low')

    return {
        'daily_kwh':      round(daily_kwh, 3),
        'monthly_kwh':    round(daily_kwh * 30, 2),
        'method':         'ml_model',
        'model_name':     type(_model).__name__,
        'confidence':     confidence,
        'feature_vector': feature_vector,
    }


def _predict_with_physics(appliances: list) -> dict:
    """
    Fallback: simple physics — wattage × hours / 1000.
    Used when model file is not found.
    """
    daily = sum(
        WATTAGE.get(a.get('type', ''), 0) * float(a.get('hours', 0))
        * int(a.get('quantity', 1)) / 1000
        for a in appliances
    )
    daily = max(0.5, daily)
    return {
        'daily_kwh':      round(daily, 3),
        'monthly_kwh':    round(daily * 30, 2),
        'method':         'physics_fallback',
        'model_name':     'Rule-based (no model file)',
        'confidence':     'medium',
        'feature_vector': {},
    }
