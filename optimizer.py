# optimizer.py  — v2 (fixes all bugs, adds scenario simulation + anomaly detection)

from bill_calculator import calculate_bill, units_from_bill_amount

APPLIANCE_DB = {
    'AC_1_ton':        {'label': 'AC (1 ton)',            'wattage': 1200, 'priority': 'low',       'icon': 'snowflake'},
    'AC_1.5_ton':      {'label': 'AC (1.5 ton)',          'wattage': 1800, 'priority': 'low',       'icon': 'snowflake'},
    'AC_2_ton':        {'label': 'AC (2 ton)',            'wattage': 2400, 'priority': 'low',       'icon': 'snowflake'},
    'inverter_ac':     {'label': 'Inverter AC (1.5 ton)', 'wattage': 1100, 'priority': 'low',       'icon': 'snowflake'},
    'geyser':          {'label': 'Geyser',                'wattage': 3000, 'priority': 'medium',    'icon': 'shower'},
    'washing_machine': {'label': 'Washing machine',       'wattage': 500,  'priority': 'medium',    'icon': 'washer'},
    'iron':            {'label': 'Iron',                  'wattage': 1000, 'priority': 'medium',    'icon': 'shirt'},
    'microwave':       {'label': 'Microwave',             'wattage': 1200, 'priority': 'medium',    'icon': 'microwave'},
    'water_pump':      {'label': 'Water pump',            'wattage': 750,  'priority': 'medium',    'icon': 'droplet'},
    'tv':              {'label': 'Television',            'wattage': 120,  'priority': 'medium',    'icon': 'tv'},
    'computer':        {'label': 'Computer / laptop',     'wattage': 150,  'priority': 'medium',    'icon': 'laptop'},
    'refrigerator':    {'label': 'Refrigerator',          'wattage': 150,  'priority': 'essential', 'icon': 'fridge'},
    'fans':            {'label': 'Fans (per fan)',         'wattage': 75,   'priority': 'essential', 'icon': 'fan'},
    'led_lights':      {'label': 'LED lights (per 10)',   'wattage': 50,   'priority': 'essential', 'icon': 'bulb'},
}


def _monthly_kwh(wattage, hours, qty=1):
    return (wattage * qty * hours * 30) / 1000


def build_appliance_list(user_appliances):
    result = []
    for item in user_appliances:
        db = APPLIANCE_DB.get(item.get('type', ''))
        if not db:
            continue
        hours = float(item.get('hours', 0))
        qty   = int(item.get('quantity', 1))
        if hours <= 0:
            continue
        mkwh = _monthly_kwh(db['wattage'], hours, qty)
        result.append({
            'type':        item['type'],
            'label':       db['label'],
            'icon':        db['icon'],
            'quantity':    qty,
            'wattage':     db['wattage'] * qty,
            'hours':       hours,
            'monthly_kwh': round(mkwh, 2),
            'priority':    db['priority'],
        })
    return sorted(result, key=lambda x: x['monthly_kwh'], reverse=True)


def optimize(actual_units, user_appliances, target_amount):
    """
    FIX 1: removed early break — ALL non-essential appliances get a recommendation.
    FIX 2: money_saved computed by comparing two actual HESCO bill calculations.
    FIX 3: returns anomaly flag when actual >> predicted.
    """
    current_bill  = calculate_bill(actual_units)
    target_units  = units_from_bill_amount(target_amount)
    target_bill   = calculate_bill(target_units)
    units_to_save = max(0.0, actual_units - target_units)

    appliances          = build_appliance_list(user_appliances)
    total_predicted_kwh = sum(a['monthly_kwh'] for a in appliances)

    if total_predicted_kwh == 0:
        return {'error': 'No appliances with hours > 0 found.'}

    # Calibration: scale predicted values to match actual bill units
    scale = actual_units / total_predicted_kwh

    for a in appliances:
        a['scaled_kwh']        = round(a['monthly_kwh'] * scale, 2)
        a['share_percent']     = round((a['scaled_kwh'] / actual_units) * 100, 1)
        a['bill_contribution'] = round((a['share_percent'] / 100) * current_bill['energy_charges'], 2)

    # Anomaly detection
    anomaly = None
    if scale > 1.4:
        anomaly = {
            'detected': True,
            'message': (
                f'Your bill shows {int(actual_units)} units but your listed appliances '
                f'should only use ~{int(total_predicted_kwh)} units. Possible causes: '
                'unlisted heavy appliance, old inefficient equipment, or meter issue.'
            )
        }

    # ── Generate recommendations ─────────────────────────────────────────
    # FIX: NO break statement. Every reducible appliance gets a recommendation.
    recommendations    = []
    running_saved_rs   = 0.0

    for appliance in appliances:
        if appliance['priority'] == 'essential':
            continue

        hours = appliance['hours']

        # Skip appliances already at very low usage — not worth reducing
        if hours < 1.0:
            continue

        # Always leave at least 0.5 hrs — never reduce to 0
        max_reducible = round(hours - 0.5, 1)
        if max_reducible <= 0:
            continue

        cut   = round(min(2.0, max(0.5, hours * 0.30), max_reducible), 1)
        new_h = round(hours - cut, 1)

        # Safety: new_h must never go below 0.5
        if new_h < 0.5:
            new_h = 0.5
            cut   = round(hours - new_h, 1)

        # Units saved from this cut (scaled to actual bill)
        units_saved = round((appliance['wattage'] / 1000) * cut * 30 * scale, 2)

        # Money saved: proper HESCO slab comparison
        new_units_total = max(0, actual_units - units_saved)
        new_bill        = calculate_bill(new_units_total)
        money_saved     = round(current_bill['total_bill'] - new_bill['total_bill'], 2)
        running_saved_rs += money_saved

        impact = 'High' if appliance['share_percent'] >= 30 else ('Medium' if appliance['share_percent'] >= 12 else 'Low')

        recommendations.append({
            'appliance':           appliance['label'],
            'type':                appliance['type'],
            'icon':                appliance['icon'],
            'current_hours':       hours,
            'reduce_by_hours':     cut,
            'new_hours':           new_h,
            'units_saved':         units_saved,
            'money_saved':         money_saved,
            'running_saved_rs':    round(running_saved_rs, 2),
            'new_bill_total':      new_bill['total_bill'],
            'share_percent':       appliance['share_percent'],
            'impact':              impact,
            'tip':                 _tip(appliance['type'], cut, new_h),
        })

    total_possible = sum(r['money_saved'] for r in recommendations)
    achievable     = total_possible >= (current_bill['total_bill'] - target_amount) * 0.75

    return {
        'current_bill':          current_bill,
        'target_bill':           target_bill,
        'units_to_save':         round(units_to_save, 1),
        'appliance_breakdown':   appliances,
        'recommendations':       recommendations,
        'achievable':            achievable,
        'projected_saving':      round(current_bill['total_bill'] - target_amount, 2),
        'total_possible_saving': round(total_possible, 2),
        'anomaly':               anomaly,
    }


def simulate(actual_units, user_appliances, modified_appliance_type, new_hours):
    """
    What-if simulator: change one appliance's hours and return new predicted bill.
    Used by the frontend live simulation sliders.
    """
    appliances          = build_appliance_list(user_appliances)
    total_predicted_kwh = sum(a['monthly_kwh'] for a in appliances)
    if total_predicted_kwh == 0:
        return calculate_bill(actual_units)

    scale = actual_units / total_predicted_kwh

    new_total = 0.0
    for a in appliances:
        h = new_hours if a['type'] == modified_appliance_type else a['hours']
        new_total += _monthly_kwh(a['wattage'], h)

    new_units = round(new_total * scale, 1)
    bill      = calculate_bill(max(0, new_units))
    bill['simulated_units'] = new_units
    bill['units_saved']     = round(actual_units - new_units, 1)
    return bill


def _tip(app_type, cut, new_hours):
    tips = {
        'AC_1_ton':        f'Set thermostat to 26°C and run for {new_hours} hrs. Use a timer at night.',
        'AC_1.5_ton':      f'Pre-cool the room early evening. Turn off {cut:.0f} hr before sleep.',
        'AC_2_ton':        f'2-ton ACs are the biggest single load. {cut:.0f} hr less = major savings.',
        'inverter_ac':     f'Inverter ACs are efficient but long hours still add up. Target {new_hours} hrs/day.',
        'geyser':          f'Heat water just before use. {new_hours} hrs/day is enough for most families.',
        'washing_machine': f'Run only full loads on cold water setting. Batch to {new_hours} hrs total.',
        'iron':            f'Iron clothes in one weekly session. Reduces standby heat loss.',
        'microwave':       f'Use microwave instead of oven for small portions — it is already efficient.',
        'water_pump':      f'Fill overhead tank once daily at night (off-peak). {new_hours} hrs is sufficient.',
        'tv':              f'Use sleep timer. Reduce background TV to {new_hours} hrs of active watching.',
        'computer':        f'Enable battery saver mode. A laptop uses 80% less than a desktop tower.',
    }
    return tips.get(app_type, f'Reduce daily usage by {cut} hours to achieve this saving.')