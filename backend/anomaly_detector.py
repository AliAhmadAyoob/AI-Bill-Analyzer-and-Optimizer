# anomaly_detector.py
# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — Anomaly Detection
#
# Uses Isolation Forest (a real unsupervised ML algorithm) to detect
# unusual electricity consumption. This answers the question:
# "Is this bill normal for a household like mine?"
#
# Two modes:
#   A) Single-bill check  — compares one reading against trained population norms
#   B) History check      — detects sudden spikes within a user's own past bills
# ─────────────────────────────────────────────────────────────────────────────

import os
import numpy as np
import joblib
from sklearn.ensemble         import IsolationForest
from sklearn.preprocessing    import StandardScaler

MODEL_PATH  = os.path.join('model', 'anomaly_model.pkl')
SCALER_PATH = os.path.join('model', 'anomaly_scaler.pkl')

_iso_model = None
_scaler    = None

if os.path.exists(MODEL_PATH) and os.path.exists(SCALER_PATH):
    _iso_model = joblib.load(MODEL_PATH)
    _scaler    = joblib.load(SCALER_PATH)
    print('[anomaly_detector] Isolation Forest loaded.')


# ─────────────────────────────────────────────────────────────────────────────
# Detect — called by the API for each user request
# ─────────────────────────────────────────────────────────────────────────────

def detect(
    actual_units:     float,
    predicted_units:  float,
    appliances:       list,
    family_members:   int,
    season:           int,
    bill_history:     list = None,   # optional: list of past monthly units
) -> dict:
    """
    Returns:
      {
        is_anomaly:      bool
        severity:        'none' | 'mild' | 'high'
        score:           float   (Isolation Forest score, lower = more anomalous)
        reasons:         list[str]
        suggestions:     list[str]
      }
    """
    reasons     = []
    suggestions = []
    iso_score   = None

    # ── Check 1: Ratio of actual vs ML predicted ──────────────────────────
    if predicted_units > 0:
        ratio = actual_units / predicted_units
        if ratio > 1.5:
            reasons.append(
                f'Your bill shows {int(actual_units)} units but your appliances '
                f'suggest only ~{int(predicted_units)} units. '
                f'That is {ratio:.1f}× higher than expected.'
            )
            suggestions.append('Check for unlisted heavy appliances (old fridge, extra AC, water heater).')
            suggestions.append('Ask your electricity provider to inspect your meter for accuracy.')
        elif ratio < 0.6:
            reasons.append(
                f'Your bill is much lower than your appliance usage suggests. '
                f'Check if all appliances were active this month.'
            )

    # ── Check 2: Isolation Forest score ──────────────────────────────────
    if _iso_model is not None and _scaler is not None:
        try:
            ac_hours = max(
                (a.get('hours', 0) for a in appliances
                 if 'AC' in a.get('type', '') or 'ac' in a.get('type', '')),
                default=0
            )
            geyser_hours = next(
                (a.get('hours', 0) for a in appliances if a.get('type') == 'geyser'), 0
            )
            wm_hours = next(
                (a.get('hours', 0) for a in appliances if a.get('type') == 'washing_machine'), 0
            )

            row      = np.array([[ac_hours, geyser_hours, wm_hours,
                                   family_members, season, actual_units]])
            scaled   = _scaler.transform(row)
            iso_score = float(_iso_model.decision_function(scaled)[0])
            label    = _iso_model.predict(scaled)[0]  # -1 = anomaly, 1 = normal

            if label == -1:
                reasons.append(
                    f'The AI anomaly model flagged this consumption as unusual '
                    f'compared to similar households (anomaly score: {iso_score:.3f}).'
                )
                suggestions.append('Compare your bill with the same month last year.')
        except Exception as e:
            print(f'[anomaly_detector] Scoring error: {e}')

    # ── Check 3: Spike in user's own history ─────────────────────────────
    if bill_history and len(bill_history) >= 2:
        avg_history = np.mean(bill_history)
        std_history = np.std(bill_history)
        z_score     = (actual_units - avg_history) / (std_history + 1e-9)
        if z_score > 2.0:
            reasons.append(
                f'This month\'s usage ({int(actual_units)} units) is '
                f'{z_score:.1f} standard deviations above your personal average '
                f'({int(avg_history)} units). That is a significant spike.'
            )
            suggestions.append('Check if you had extra guests, left AC running overnight, or a device malfunction.')

    # ── Severity ──────────────────────────────────────────────────────────
    is_anomaly = len(reasons) > 0
    if len(reasons) >= 2:
        severity = 'high'
    elif len(reasons) == 1:
        severity = 'mild'
    else:
        severity = 'none'

    return {
        'is_anomaly':  is_anomaly,
        'severity':    severity,
        'iso_score':   iso_score,
        'reasons':     reasons,
        'suggestions': suggestions,
    }
