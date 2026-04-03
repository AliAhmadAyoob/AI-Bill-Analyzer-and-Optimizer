# app.py — Smart Energy Optimizer  v3
# All 3 AI modules wired:
#   ml_predictor     -> predicts kWh from appliances  (ML regression)
#   anomaly_detector -> flags unusual bills            (Isolation Forest)
#   user_classifier  -> household profile              (KMeans clustering)

import os, uuid
from flask      import Flask, request, jsonify ,render_template
from flask_cors import CORS

from bill_reader      import extract_bill_data
from bill_calculator  import calculate_bill
from optimizer        import optimize, simulate, APPLIANCE_DB
from ml_predictor     import predict_from_appliances
from anomaly_detector import detect   as detect_anomaly
from user_classifier  import classify as classify_user

app = Flask(
    __name__,
    template_folder='../frontend/templates',  
    static_folder='../frontend/static'     
)

CORS(app)
os.makedirs('uploads', exist_ok=True)


def err(msg, code=400):
    return jsonify({'success': False, 'error': msg}), code

@app.route('/')
def index():
    return render_template('index.html')
# ─────────────────────────────────────────────────────────────────
# POST /api/upload-bill
# ─────────────────────────────────────────────────────────────────
@app.route('/api/upload-bill', methods=['POST'])
def upload_bill():
    if 'bill' not in request.files:
        return err('No file sent. Use key "bill".')

    file = request.files['bill']

    # Reject empty filename
    if not file.filename:
        return err('No file selected. Please choose a bill image.')

    # Check allowed extensions
    allowed = {'.jpg', '.jpeg', '.png', '.pdf', '.bmp', '.webp', '.tiff', '.tif'}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed:
        return jsonify({
            'success':     True,
            'ocr_success': False,
            'units':       None,
            'amount':      None,
            'message':     'Could not read bill automatically. Please enter values manually.',
            'error': (
                f'File type "{ext}" is not supported. '
                f'Please upload a JPG, PNG, or PDF image of your bill.'
            ),
        })

    filepath = os.path.join('uploads', f"{uuid.uuid4()}{ext}")
    file.save(filepath)

    result = extract_bill_data(filepath)

    # Always clean up — even on error
    try:
        os.remove(filepath)
    except Exception:
        pass

    # Determine message shown to user
    if result['ocr_success']:
        message = 'Bill read successfully — please confirm the values below.'
    elif result['error']:
        message = result['error']    # already a user-friendly string
    else:
        message = 'Could not read bill automatically. Please enter your units and amount manually.'

    return jsonify({
        'success':     True,          # server worked fine — OCR may or may not have worked
        'ocr_success': result['ocr_success'],
        'units':       result['units'],
        'amount':      result['amount'],
        'message':     message,
        'error':       result['error'],
    })


# ─────────────────────────────────────────────────────────────────
# POST /api/analyze    <-- MAIN ENDPOINT
#
# Runs all 3 AI models + optimizer in one request.
#
# Body:
# {
#   actual_units:   320,
#   target_amount:  5000,
#   family_members: 5,
#   season:         1,
#   appliances:     [{ type, hours, quantity }, ...],
#   bill_history:   [280, 310, 295]   (optional)
# }
# ─────────────────────────────────────────────────────────────────
@app.route('/api/analyze', methods=['POST'])
def analyze():
    data = request.get_json()
    if not data:
        return err('No JSON received.')

    actual_units   = data.get('actual_units')
    target_amount  = data.get('target_amount')
    appliances     = data.get('appliances', [])
    family_members = int(data.get('family_members', 4))
    season         = int(data.get('season', 1))
    bill_history   = data.get('bill_history', [])

    if actual_units  is None: return err('actual_units is required.')
    if target_amount is None: return err('target_amount is required.')
    if not appliances:        return err('appliances list is required.')

    actual_units  = float(actual_units)
    target_amount = float(target_amount)

    # ── AI Step 1: ML model predicts kWh from appliance inputs ───
    prediction = predict_from_appliances(appliances, family_members, season)

    # ── AI Step 2: Isolation Forest anomaly detection ────────────
    anomaly = detect_anomaly(
        actual_units    = actual_units,
        predicted_units = prediction['monthly_kwh'],
        appliances      = appliances,
        family_members  = family_members,
        season          = season,
        bill_history    = bill_history,
    )

    # ── AI Step 3: KMeans household classification ────────────────
    profile = classify_user(actual_units, appliances, family_members)

    # ── Optimizer: rule-based on top of AI outputs ────────────────
    opt = optimize(actual_units, appliances, target_amount)
    if 'error' in opt:
        return err(opt['error'])

    return jsonify({
        'success':    True,
        'prediction': prediction,   # AI Step 1
        'anomaly':    anomaly,      # AI Step 2
        'profile':    profile,      # AI Step 3
        **{k: v for k, v in opt.items()},
    })


# ─────────────────────────────────────────────────────────────────
# POST /api/simulate
# ─────────────────────────────────────────────────────────────────
@app.route('/api/simulate', methods=['POST'])
def simulate_route():
    data = request.get_json()
    if not data: return err('No JSON.')
    result = simulate(
        float(data.get('actual_units', 0)),
        data.get('appliances', []),
        data.get('modified_type', ''),
        float(data.get('new_hours', 0)),
    )
    return jsonify({'success': True, 'bill': result})


# ─────────────────────────────────────────────────────────────────
# GET /api/appliances
# ─────────────────────────────────────────────────────────────────
@app.route('/api/appliances', methods=['GET'])
def get_appliances():
    return jsonify({
        'success':    True,
        'appliances': [
            {'type': k, 'label': v['label'], 'wattage': v['wattage'], 'priority': v['priority']}
            for k, v in APPLIANCE_DB.items()
        ]
    })


# ─────────────────────────────────────────────────────────────────
# POST /api/bill-only
# ─────────────────────────────────────────────────────────────────
@app.route('/api/bill-only', methods=['POST'])
def bill_only():
    data  = request.get_json()
    units = float(data.get('units', 0)) if data else 0
    if units <= 0: return err('units must be > 0.')
    return jsonify({'success': True, 'bill': calculate_bill(units)})


if __name__ == '__main__':
    app.run(debug=True)
