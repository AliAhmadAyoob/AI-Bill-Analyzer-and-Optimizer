# bill_calculator.py
# Calculates electricity bill using official HESCO/NEPRA slab rates (2024-25)

SLABS = [
    (50,  3.95),    # 1 - 50 units
    (100, 7.74),    # 51 - 100 units
    (200, 10.06),   # 101 - 200 units
    (300, 12.44),   # 201 - 300 units
    (700, 19.55),   # 301 - 700 units
    (float('inf'), 22.65),  # 700+ units
]

FIXED_CHARGE       = 400    # Rs per month (approximate HESCO fixed charge)
GST_RATE           = 0.18   # 18% General Sales Tax
FC_SURCHARGE_RATE  = 0.043  # Fuel Cost Adjustment surcharge


def calculate_bill(monthly_units: float) -> dict:
    """
    Given monthly units consumed, return a full bill breakdown.
    Returns a dict with energy_charges, taxes, fixed_charge, total, and slab_breakdown.
    """
    monthly_units = round(monthly_units)
    energy_charges = 0.0
    slab_breakdown = []
    remaining = monthly_units
    prev_limit = 0

    for limit, rate in SLABS:
        if remaining <= 0:
            break
        slab_start = prev_limit + 1
        slab_end   = int(limit) if limit != float('inf') else '700+'
        units_in_slab = min(remaining, limit - prev_limit)
        charge = units_in_slab * rate
        energy_charges += charge

        slab_breakdown.append({
            'slab':    f"{slab_start} – {slab_end}",
            'units':   round(units_in_slab),
            'rate':    rate,
            'charge':  round(charge, 2),
        })

        remaining  -= units_in_slab
        prev_limit  = limit

    gst              = round(energy_charges * GST_RATE, 2)
    fc_surcharge     = round(energy_charges * FC_SURCHARGE_RATE, 2)
    total            = round(energy_charges + gst + fc_surcharge + FIXED_CHARGE, 2)

    return {
        'monthly_units':   monthly_units,
        'energy_charges':  round(energy_charges, 2),
        'fixed_charge':    FIXED_CHARGE,
        'gst':             gst,
        'fc_surcharge':    fc_surcharge,
        'total_bill':      total,
        'slab_breakdown':  slab_breakdown,
    }


def units_from_bill_amount(target_amount: float) -> int:
    """
    Reverse lookup — given a target bill amount, estimate how many units
    correspond to that amount (used by optimizer to find the target unit count).
    Binary search approach.
    """
    lo, hi = 0, 5000
    for _ in range(50):          # 50 iterations is more than enough
        mid = (lo + hi) / 2
        if calculate_bill(mid)['total_bill'] < target_amount:
            lo = mid
        else:
            hi = mid
    return int((lo + hi) / 2)


if __name__ == '__main__':
    # Quick test
    for units in [100, 200, 350, 500, 750]:
        b = calculate_bill(units)
        print(f"{units} units → Rs. {b['total_bill']}")
