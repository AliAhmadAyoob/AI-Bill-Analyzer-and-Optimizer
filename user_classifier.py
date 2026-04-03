# user_classifier.py
# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — Usage Pattern Classification
#
# Uses KMeans clustering to classify each household into one of three
# energy consumption profiles:
#
#   Light User   — below 200 units/month, few heavy appliances
#   Medium User  — 200–400 units/month, AC used moderately
#   Heavy User   — 400+ units/month, multiple ACs or heavy usage
#
# Why this matters for FYP:
#   Different households need different advice. A Light User household
#   does not benefit from AC reduction tips if they barely use AC.
#   A Heavy User needs aggressive structural changes, not minor tweaks.
#   The classifier makes recommendations PERSONALISED — that is real AI.
# ─────────────────────────────────────────────────────────────────────────────

import os
import numpy as np
import joblib
from sklearn.cluster        import KMeans
from sklearn.preprocessing  import StandardScaler

MODEL_PATH  = os.path.join('model', 'cluster_model.pkl')
SCALER_PATH = os.path.join('model', 'cluster_scaler.pkl')

_kmeans = None
_scaler = None

if os.path.exists(MODEL_PATH) and os.path.exists(SCALER_PATH):
    _kmeans = joblib.load(MODEL_PATH)
    _scaler = joblib.load(SCALER_PATH)
    print('[user_classifier] KMeans cluster model loaded.')


# ─────────────────────────────────────────────────────────────────────────────
# Profile definitions — one for each cluster
# ─────────────────────────────────────────────────────────────────────────────

PROFILES = {
    'light': {
        'label':       'Light User',
        'color':       'green',
        'unit_range':  '< 200 units/month',
        'description': 'Your household uses electricity conservatively. Small gains are still possible.',
        'focus':       'Focus on off-peak usage scheduling and LED upgrades.',
        'tips': [
            'Switch all remaining bulbs to LED if not already done.',
            'Run washing machine during off-peak hours (after 11 PM).',
            'Unplug chargers and standby devices — phantom load adds up.',
            'Check fridge door seals — a worn seal makes the compressor work harder.',
        ],
        'priority_appliance': 'geyser',
    },
    'medium': {
        'label':       'Medium User',
        'color':       'amber',
        'unit_range':  '200 – 400 units/month',
        'description': 'Typical Karachi household. Significant savings are possible with targeted changes.',
        'focus':       'Focus on AC temperature and scheduling.',
        'tips': [
            'Set AC to 26°C instead of 22°C — each degree saves ~6% energy.',
            'Use ceiling fans with AC — allows setting AC 2°C higher.',
            'Service your AC before summer — dirty filters use 15% more power.',
            'Install a timer on geyser — heat only during morning and evening.',
            'Run heavy appliances before 7 PM or after 11 PM.',
        ],
        'priority_appliance': 'AC_1.5_ton',
    },
    'heavy': {
        'label':       'Heavy User',
        'color':       'red',
        'unit_range':  '> 400 units/month',
        'description': 'High consumption household. Structural changes needed for meaningful savings.',
        'focus':       'Focus on replacing old appliances and considering solar.',
        'tips': [
            'Consider replacing non-inverter ACs — inverter models use 40–60% less.',
            'Solar panels are financially viable at your consumption level — payback in 3–4 years.',
            'Check if you have old non-inverter refrigerator — new 5-star models save Rs 2,000+/year.',
            'Separate high-load appliances on dedicated circuits to reduce energy waste.',
            'Audit your geyser — a solar water heater pays back in under 2 years at this usage level.',
        ],
        'priority_appliance': 'AC_2_ton',
    },
}

# def train_classifier(daily_df):
#     """
#     Train KMeans (k=3) on the daily dataset to learn 3 consumption clusters.
#     Call at end of model_preparation.ipynb:

#         from user_classifier import train_classifier
#         train_classifier(ml_data)

#     Saves cluster_model.pkl and cluster_scaler.pkl.
#     """
#     os.makedirs('model', exist_ok=True)

#     feature_cols = [c for c in
#         ['AC_Hours', 'Geyser_Hours', 'WashingMachine_Hours',
#          'Family_Members', 'Total_kWh']
#         if c in daily_df.columns]

#     X = daily_df[feature_cols].fillna(0).values

#     scaler  = StandardScaler()
#     X_sc    = scaler.fit_transform(X)

#     kmeans  = KMeans(n_clusters=3, random_state=42, n_init=20)
#     labels  = kmeans.fit_predict(X_sc)

#     # Map cluster indices to profile names by their mean Total_kWh
#     cluster_means = {}
#     for i in range(3):
#         mask = labels == i
#         cluster_means[i] = daily_df['Total_kWh'][mask].mean() if 'Total_kWh' in daily_df.columns else 0

#     sorted_clusters = sorted(cluster_means, key=cluster_means.get)
#     cluster_map     = {
#         sorted_clusters[0]: 'light',
#         sorted_clusters[1]: 'medium',
#         sorted_clusters[2]: 'heavy',
#     }
#     # Save cluster map alongside model
#     import json
#     with open(os.path.join('model', 'cluster_map.json'), 'w') as f:
#         json.dump({str(k): v for k, v in cluster_map.items()}, f)

#     joblib.dump(kmeans, MODEL_PATH)
#     joblib.dump(scaler, SCALER_PATH)

#     counts = {v: int((labels == k).sum()) for k, v in cluster_map.items()}
#     print(f'[user_classifier] Trained. Cluster distribution: {counts}')
#     return kmeans, scaler, cluster_map

# ─────────────────────────────────────────────────────────────────────────────
# Train — call from the model_preparation notebook
# ─────────────────────────────────────────────────────────────────────────────



# ─────────────────────────────────────────────────────────────────────────────
# Classify — called by the API
# ─────────────────────────────────────────────────────────────────────────────

def classify(
    actual_units:   float,
    appliances:     list,
    family_members: int,
) -> dict:
    """
    Classifies this household into light / medium / heavy user.
    Returns the full profile including tailored tips.
    """
    profile_key = _rule_based_classify(actual_units)

    # Override with ML cluster model if available
    if _kmeans is not None and _scaler is not None:
        profile_key = _ml_classify(actual_units, appliances, family_members)

    profile = PROFILES[profile_key].copy()

    # Add per-unit comparison context
    per_person = round(actual_units / max(family_members, 1), 1)
    profile['actual_units']  = int(actual_units)
    profile['per_person']    = per_person
    profile['profile_key']   = profile_key
    profile['method'] = 'kmeans_cluster' if _kmeans is not None else 'rule_based'

    return profile


def _rule_based_classify(units: float) -> str:
    if units < 200:
        return 'light'
    elif units <= 400:
        return 'medium'
    else:
        return 'heavy'


def _ml_classify(actual_units, appliances, family_members) -> str:
    try:
        import json
        map_path = os.path.join('model', 'cluster_map.json')

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

        row    = np.array([[ac_hours, geyser_hours, wm_hours,
                            family_members, actual_units]])
        scaled = _scaler.transform(row)
        label  = int(_kmeans.predict(scaled)[0])

        if os.path.exists(map_path):
            with open(map_path) as f:
                cluster_map = json.load(f)
            return cluster_map.get(str(label), _rule_based_classify(actual_units))

    except Exception as e:
        print(f'[user_classifier] ML classify error: {e}')

    return _rule_based_classify(actual_units)
