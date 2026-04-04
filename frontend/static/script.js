// app.js — Smart Energy Optimizer  v2
// Fixes: state management, empty recommendations, live simulator

const API = 'https://ai-bill-analyzer-and-optimizer.onrender.com/api';

// ── Global state ───────────────────────────────────────────────────────────
const S = {
  billUnits:    null,   // from uploaded bill or manual entry
  billAmount:   null,
  targetAmount: null,
  appliances:   [],     // from /api/appliances
  result:       null,   // last /api/optimize response
  simHours:     {},     // { appType: currentHours } for live simulator
};

let pieChart = null, barChart = null;

// ── Boot ───────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  setupDrop();
  document.getElementById('billFile').addEventListener('change', e => {
    if (e.target.files[0]) handleFile(e.target.files[0]);
  });
  loadAppliances();
});

// ── Page navigation ────────────────────────────────────────────────────────
function goPage(n) {
  document.querySelectorAll('.page').forEach((p, i) => p.classList.toggle('active', i + 1 === n));
  document.querySelectorAll('.step').forEach((s, i) => {
    s.classList.remove('active', 'done');
    if (i + 1 === n) s.classList.add('active');
    if (i + 1 < n)  s.classList.add('done');
  });
  window.scrollTo(0, 0);
}

// ── Step 1 validation & advance ────────────────────────────────────────────
function step1Next() {
  const units  = parseFloat(document.getElementById('inUnits').value);
  const amount = parseFloat(document.getElementById('inAmount').value) || null;
  const target = parseFloat(document.getElementById('inTarget').value);

  const errEl = document.getElementById('p1error');
  errEl.classList.add('hidden');

  if (!units || units <= 0) {
    return showError('p1error', 'Please enter the units consumed from your bill.');
  }
  if (!target || target <= 0) {
    return showError('p1error', 'Please enter your target bill amount (what you want to pay).');
  }
  if (target >= calculateRoughBill(units)) {
    return showError('p1error',
      `Your target Rs ${target.toLocaleString()} is already close to or above your current bill. ` +
      `Set a lower target to get meaningful recommendations.`);
  }

  S.billUnits    = units;
  S.billAmount   = amount;
  S.targetAmount = target;
  goPage(2);
}

function calculateRoughBill(units) {
  // Quick rough estimate for validation only
  return units * 20 + 400;
}

function showError(elId, msg) {
  const el = document.getElementById(elId);
  el.textContent = msg;
  el.classList.remove('hidden');
}

// ── Upload & OCR ───────────────────────────────────────────────────────────
function setupDrop() {
  const zone = document.getElementById('uploadZone');
  zone.addEventListener('click', () => document.getElementById('billFile').click());
  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('over'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('over'));
  zone.addEventListener('drop', e => {
    e.preventDefault(); zone.classList.remove('over');
    if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]);
  });
}

async function handleFile(file) {
  // Show image preview for images
  if (file.type.startsWith('image/')) {
    document.getElementById('previewImg').src = URL.createObjectURL(file);
    document.getElementById('previewWrap').classList.remove('hidden');
  }

  // Show bill fields immediately so user can always type manually
  document.getElementById('billCard').classList.remove('hidden');

  loading('Reading your bill...');
  try {
    const fd = new FormData();
    fd.append('bill', file);
    const res  = await fetch(`${API}/upload-bill`, { method: 'POST', body: fd });
    const data = await res.json();
    hideLoading();
    renderOcrResult(data);
  } catch (e) {
    // Network error or server down — show manual entry silently
    hideLoading();
    renderOcrResult({
      ocr_success: false,
      error: null,   // null = don't show error, just show manual entry
    });
  }
}

function renderOcrResult(data) {
  const msg = document.getElementById('ocrMsg');

  if (data.ocr_success) {
    // OCR worked — fill in fields and show success
    msg.innerHTML = '<p class="ocr-ok">✓ Bill read successfully — please confirm the values below.</p>';
    if (data.units)  document.getElementById('inUnits').value  = data.units;
    if (data.amount) document.getElementById('inAmount').value = data.amount;
  } else if (data.error && data.error.includes('HEIC')) {
    // Special case: iPhone format
    msg.innerHTML = `<p class="ocr-warn">⚠ iPhone photo format (HEIC) is not supported. Please take a screenshot of your bill instead, then upload the screenshot.</p>`;
  } else {
    // All other failures — just show manual entry quietly, no scary error
    msg.innerHTML = '<p class="ocr-warn">Please enter your units consumed and bill amount from the bill below.</p>';
  }
}

function showManual() {
  document.getElementById('ocrMsg').innerHTML =
    '<p class="ocr-warn">Manual entry mode — type the values from your bill.</p>';
}

// ── Load appliances from API (with fallback) ───────────────────────────────
async function loadAppliances() {
  const fallback = [
    { type:'AC_1.5_ton',      label:'AC (1.5 ton)',          wattage:1800, priority:'low'       },
    { type:'AC_1_ton',        label:'AC (1 ton)',            wattage:1200, priority:'low'       },
    { type:'AC_2_ton',        label:'AC (2 ton)',            wattage:2400, priority:'low'       },
    { type:'inverter_ac',     label:'Inverter AC (1.5 ton)', wattage:1100, priority:'low'       },
    { type:'geyser',          label:'Geyser',                wattage:3000, priority:'medium'    },
    { type:'washing_machine', label:'Washing machine',       wattage:500,  priority:'medium'    },
    { type:'iron',            label:'Iron',                  wattage:1000, priority:'medium'    },
    { type:'water_pump',      label:'Water pump',            wattage:750,  priority:'medium'    },
    { type:'microwave',       label:'Microwave',             wattage:1200, priority:'medium'    },
    { type:'tv',              label:'Television',            wattage:120,  priority:'medium'    },
    { type:'computer',        label:'Computer / laptop',     wattage:150,  priority:'medium'    },
    { type:'refrigerator',    label:'Refrigerator',          wattage:150,  priority:'essential' },
    { type:'fans',            label:'Fans (per fan)',         wattage:75,   priority:'essential' },
    { type:'led_lights',      label:'LED lights (per 10)',   wattage:50,   priority:'essential' },
  ];
  try {
    const res  = await fetch(`${API}/appliances`);
    const data = await res.json();
    S.appliances = data.success ? data.appliances : fallback;
  } catch {
    S.appliances = fallback;
  }
  renderAppGrid();
}

const DEFAULT_HOURS = {
  'AC_1.5_ton':8,'AC_1_ton':6,'AC_2_ton':8,'inverter_ac':8,
  'geyser':1,'washing_machine':0.5,'iron':0.3,'water_pump':1,
  'microwave':0.5,'tv':4,'computer':4,'refrigerator':24,
  'fans':12,'led_lights':6,
};

function renderAppGrid() {
  document.getElementById('appGrid').innerHTML = S.appliances.map(a => `
    <div class="app-card" id="card-${a.type}">
      <input class="app-check" type="checkbox" id="chk-${a.type}"
             ${['refrigerator','fans','led_lights'].includes(a.type) ? 'checked disabled' : 'checked'}
             onchange="toggleCard('${a.type}', this.checked)"/>
      <div class="app-info">
        <div class="app-name">${a.label}</div>
        <div class="app-watts">${a.wattage}W · ${a.priority}</div>
      </div>
      <div class="app-inputs">
        <div>
          <label>Qty</label>
          <input type="number" id="qty-${a.type}" value="1" min="0" max="10"/>
        </div>
        <div>
          <label>Hrs/day</label>
          <input type="number" id="hrs-${a.type}" value="${DEFAULT_HOURS[a.type] || 2}"
                 min="0" max="24" step="0.5"
                 ${['refrigerator'].includes(a.type) ? 'readonly' : ''}/>
        </div>
      </div>
    </div>
  `).join('');
}

function toggleCard(type, checked) {
  document.getElementById(`card-${type}`).classList.toggle('active-card', checked);
}

function getSelectedAppliances() {
  return S.appliances
    .filter(a => document.getElementById(`chk-${a.type}`)?.checked)
    .map(a => ({
      type:     a.type,
      hours:    parseFloat(document.getElementById(`hrs-${a.type}`)?.value || 0),
      quantity: parseInt(document.getElementById(`qty-${a.type}`)?.value || 1),
    }))
    .filter(a => a.hours > 0);
}

// ── Step 2 → call optimizer ────────────────────────────────────────────────
async function step2Analyze() {
  const apps = getSelectedAppliances();
  if (apps.length === 0) {
    return showError('p2error', 'Please select at least one appliance with hours > 0.');
  }

  loading('Running AI analysis...');

  try {
    const payload = {
      actual_units:   S.billUnits,
      target_amount:  S.targetAmount,
      appliances:     apps,
      family_members: parseInt(document.getElementById('inFamily').value) || 4,
      season:         parseInt(document.getElementById('inSeason').value),
    };

    const res  = await fetch(`${API}/analyze`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(payload),
    });

    if (!res.ok) {
      const txt = await res.text();
      throw new Error(`Server error ${res.status}: ${txt}`);
    }

    const data = await res.json();
    hideLoading();

    if (!data.success) {
      return showError('p2error', 'Server error: ' + (data.error || 'Unknown error'));
    }

    S.result = data;

    // Store current hours for simulator
    apps.forEach(a => { S.simHours[a.type] = a.hours; });

    renderResults(data, apps);
    goPage(3);

  } catch (e) {
    hideLoading();
    showError('p2error',
      'Could not connect to server. Make sure Flask is running on port 5000.\n' + e.message);
  }
}

// ── Render results ─────────────────────────────────────────────────────────
function renderResults(data, apps) {
  renderSubtitle(data);
  renderAIPanels(data);          // NEW: prediction + anomaly + profile
  renderKPIs(data);
  renderPie(data.appliance_breakdown);
  renderBar(data.current_bill);
  renderSlabs(data.current_bill);
  renderRecs(data.recommendations, data);
  renderSimulator(data.appliance_breakdown, apps);
}

// ── Result insight cards (clean, no technical labels) ─────────────────────
function renderAIPanels(data) {
  const existing = document.getElementById('aiPanels');
  if (existing) existing.remove();

  const wrap = document.createElement('div');
  wrap.id = 'aiPanels';
  wrap.style.cssText = 'display:grid;grid-template-columns:1fr 1fr 1fr;gap:.75rem;margin-bottom:1.2rem';

  // ── Card 1: Expected usage ──────────────────────────────────────
  // The ML model predicts kWh from appliance inputs.
  // We show how much of the actual bill each appliance accounts for,
  // not the raw kWh (which is from a French dataset and won't match Pakistani units directly).
  const p      = data.prediction || {};
  const actual = data.current_bill?.monthly_units ?? 0;

  // Total kWh from appliance breakdown (what user entered)
  const breakdown     = data.appliance_breakdown || [];
  const totalApplKwh  = breakdown.reduce((s, a) => s + (a.scaled_kwh || 0), 0);
  const topAppliance  = breakdown.length > 0 ? breakdown[0] : null;
  const topPct        = topAppliance ? topAppliance.share_percent : 0;
  const topLabel      = topAppliance ? topAppliance.label : '';

  // Appliance count
  const appCount = breakdown.length;

  wrap.innerHTML += `
    <div class="card" style="border-top:3px solid #2563eb;padding:1.1rem">
      <div style="font-size:.75rem;font-weight:600;color:#6b7280;text-transform:uppercase;letter-spacing:.05em;margin-bottom:.6rem">Appliance usage</div>
      <div style="font-size:1.6rem;font-weight:700;color:#2563eb;line-height:1">${actual}</div>
      <div style="font-size:.82rem;color:#6b7280;margin:.25rem 0 .6rem">total units on your bill this month</div>
      <div style="font-size:.82rem;color:#374151;margin-bottom:.4rem">
        We found <strong>${appCount}</strong> appliances in your home.
      </div>
      ${topAppliance ? `
      <div style="background:#eff6ff;border-radius:7px;padding:.4rem .65rem;font-size:.8rem;color:#1d4ed8">
        Biggest load: <strong>${topLabel}</strong> — ${topPct}% of your bill
      </div>` : ''}
    </div>`;

  // ── Card 2: Bill status ─────────────────────────────────────────
  const a = data.anomaly || {};
  const isOk     = !a.is_anomaly;
  const stColor  = isOk ? '#16a34a' : (a.severity === 'high' ? '#dc2626' : '#d97706');
  const stLabel  = isOk ? 'Looks normal' : (a.severity === 'high' ? 'Something looks off' : 'Slightly unusual');
  const stIcon   = isOk ? '✓' : '⚠';
  const stMsg    = isOk
    ? 'Your bill matches what your appliances should be using. No hidden loads detected.'
    : (a.reasons?.[0] ?? 'Your bill is higher than your listed appliances suggest.');
  const stTip    = a.suggestions?.[0] ?? '';

  wrap.innerHTML += `
    <div class="card" style="border-top:3px solid ${stColor};padding:1.1rem">
      <div style="font-size:.75rem;font-weight:600;color:#6b7280;text-transform:uppercase;letter-spacing:.05em;margin-bottom:.6rem">Bill status</div>
      <div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.5rem">
        <span style="font-size:1.3rem;color:${stColor}">${stIcon}</span>
        <span style="font-size:1.1rem;font-weight:700;color:${stColor}">${stLabel}</span>
      </div>
      <div style="font-size:.82rem;color:#374151;line-height:1.6">${stMsg}</div>
      ${stTip ? `<div style="margin-top:.6rem;font-size:.78rem;color:#6b7280;line-height:1.5">${stTip}</div>` : ''}
    </div>`;

  // ── Card 3: Household type ──────────────────────────────────────
  const pr = data.profile || {};
  const prColors  = { light:'#16a34a', medium:'#d97706', heavy:'#dc2626' };
  const prBg      = { light:'#f0fdf4', medium:'#fffbeb', heavy:'#fef2f2' };
  const prC       = prColors[pr.profile_key] || '#6b7280';
  const prBgC     = prBg[pr.profile_key]     || '#f9fafb';
  const prEmoji   = pr.profile_key === 'light' ? '🟢' : pr.profile_key === 'heavy' ? '🔴' : '🟡';
  const perPerson = pr.per_person ?? '—';

  wrap.innerHTML += `
    <div class="card" style="border-top:3px solid ${prC};padding:1.1rem">
      <div style="font-size:.75rem;font-weight:600;color:#6b7280;text-transform:uppercase;letter-spacing:.05em;margin-bottom:.6rem">Your household type</div>
      <div style="display:inline-block;background:${prBgC};color:${prC};border-radius:20px;padding:.25rem .85rem;font-size:.95rem;font-weight:700;margin-bottom:.55rem">${prEmoji} ${pr.label ?? '—'}</div>
      <div style="font-size:.82rem;color:#374151;line-height:1.6;margin-bottom:.5rem">${pr.description ?? ''}</div>
      <div style="font-size:.8rem;color:#6b7280">${perPerson} units per person · ${pr.unit_range ?? ''}</div>
    </div>`;

  const kpiRow = document.getElementById('kpiRow');
  kpiRow.parentNode.insertBefore(wrap, kpiRow);
}

// ── Household tips appended to recommendations ────────────────────────────
function renderProfileTips(profile) {
  if (!profile?.tips?.length) return;
  const card = document.getElementById('recCard');
  const div  = document.createElement('div');
  div.style.cssText = 'margin-top:1.3rem;padding-top:1rem;border-top:1px solid #f3f4f6';
  const prColors = { light:'#16a34a', medium:'#d97706', heavy:'#dc2626' };
  const c = prColors[profile.profile_key] || '#2563eb';
  div.innerHTML = `
    <div style="font-size:.88rem;font-weight:600;color:#374151;margin-bottom:.65rem">
      Additional tips for your household
    </div>
    ${profile.tips.map(t => `
      <div style="display:flex;gap:.6rem;align-items:flex-start;margin-bottom:.5rem">
        <span style="color:${c};font-size:1rem;flex-shrink:0;margin-top:.05rem">→</span>
        <span style="font-size:.83rem;color:#4b5563;line-height:1.55">${t}</span>
      </div>`).join('')}`;
  card.appendChild(div);
}

function renderSubtitle(data) {
  const saving = data.total_possible_saving ?? 0;
  document.getElementById('resultSubtitle').textContent =
    saving > 0
      ? `Here is your full energy breakdown. Follow the recommendations below to save up to Rs ${saving.toLocaleString()} per month.`
      : 'Here is your full energy breakdown. Your target is close to your current bill.';
}

function renderAnomaly(anomaly) {
  const el = document.getElementById('anomalyAlert');
  if (anomaly?.detected) {
    el.textContent = '⚠ ' + anomaly.message;
    el.classList.remove('hidden');
  } else {
    el.classList.add('hidden');
  }
}

function renderKPIs(data) {
  const b  = data.current_bill;
  const tb = data.target_bill;
  document.getElementById('kpiRow').innerHTML = `
    <div class="kpi red">
      <div class="kpi-label">Current bill</div>
      <div class="kpi-val">Rs ${b.total_bill.toLocaleString()}</div>
      <div class="kpi-sub">${b.monthly_units} units</div>
    </div>
    <div class="kpi blue">
      <div class="kpi-label">Your target</div>
      <div class="kpi-val">Rs ${tb.total_bill.toLocaleString()}</div>
      <div class="kpi-sub">${tb.monthly_units} units</div>
    </div>
    <div class="kpi green">
      <div class="kpi-label">Max possible saving</div>
      <div class="kpi-val">Rs ${data.total_possible_saving.toLocaleString()}</div>
      <div class="kpi-sub">per month</div>
    </div>
    <div class="kpi amber">
      <div class="kpi-label">Units to save</div>
      <div class="kpi-val">${data.units_to_save}</div>
      <div class="kpi-sub">to reach target</div>
    </div>
  `;
}

function renderPie(breakdown) {
  const ctx    = document.getElementById('pieChart').getContext('2d');
  const labels = breakdown.map(a => a.label);
  const vals   = breakdown.map(a => a.scaled_kwh);
  const colors = ['#2563eb','#dc2626','#d97706','#16a34a','#7c3aed','#0891b2','#be185d','#65a30d','#ea580c','#6366f1','#14b8a6','#f43f5e'];

  if (pieChart) pieChart.destroy();
  pieChart = new Chart(ctx, {
    type: 'doughnut',
    data: { labels, datasets: [{ data: vals, backgroundColor: colors, borderWidth: 2, borderColor: '#fff' }] },
    options: {
      plugins: { legend: { position: 'right', labels: { font: { size: 11 }, boxWidth: 14 } } },
      cutout: '58%',
    },
  });
}

function renderBar(bill) {
  const ctx = document.getElementById('barChart').getContext('2d');
  if (barChart) barChart.destroy();
  barChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: ['Energy charges', 'GST 18%', 'FC surcharge', 'Fixed charge'],
      datasets: [{
        data: [bill.energy_charges, bill.gst, bill.fc_surcharge, bill.fixed_charge],
        backgroundColor: ['#2563eb','#7c3aed','#d97706','#9ca3af'],
        borderRadius: 5,
      }],
    },
    options: {
      plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true, ticks: { callback: v => 'Rs ' + v.toLocaleString() } } },
    },
  });
}

function renderSlabs(bill) {
  const rows = bill.slab_breakdown.map(s => `
    <div class="slab-row">
      <div>${s.slab} units</div>
      <div>${s.units} units</div>
      <div>Rs ${s.rate}/unit</div>
      <div>Rs ${s.charge.toLocaleString()}</div>
    </div>
  `).join('');
  document.getElementById('slabTable').innerHTML = `
    <div class="slab-row head"><div>Slab</div><div>Units</div><div>Rate</div><div>Charge</div></div>
    ${rows}
  `;
}

function renderRecs(recs, data) {
  const badge  = document.getElementById('recBadge');
  const intro  = document.getElementById('recIntro');

  if (recs.length === 0) {
    badge.textContent = 'Nothing to reduce';
    badge.className   = 'badge amber';
    intro.textContent = 'All your appliances are already at minimal usage. Consider checking for any unlisted devices.';
    document.getElementById('recList').innerHTML = '';
    return;
  }

  badge.textContent = data.achievable ? 'Target is reachable ✓' : 'Partial saving possible';
  badge.className   = data.achievable ? 'badge' : 'badge amber';
  intro.textContent = `These are the changes that will reduce your bill the most. Sorted by highest saving first.`;

  // Render profile tips after the recs
  if (data.profile) {
    setTimeout(() => renderProfileTips(data.profile), 50);
  }

  document.getElementById('recList').innerHTML = recs.map((r, i) => {
    const impactDot = r.impact === 'High'   ? '#dc2626'
                    : r.impact === 'Medium' ? '#d97706' : '#16a34a';
    return `
    <div class="rec-item">
      <div class="rec-num" style="background:#f3f4f6;color:#374151;font-size:.85rem">${i + 1}</div>
      <div class="rec-body">
        <div class="rec-title">${r.label || r.appliance}</div>
        <div class="rec-change">
          Reduce from <strong>${r.current_hours} hrs/day</strong> to <strong>${r.new_hours} hrs/day</strong>
        </div>
        <div class="rec-tip">${r.tip}</div>
      </div>
      <div class="rec-saving">
        <div class="rec-rs">Rs ${r.money_saved.toLocaleString()}</div>
        <div class="rec-units">saves ${r.units_saved} units</div>
        <div class="rec-newbill">New bill ≈ Rs ${r.new_bill_total?.toLocaleString?.() ?? '—'}</div>
      </div>
    </div>`}).join('');
}

// ── Live simulator ─────────────────────────────────────────────────────────
function renderSimulator(breakdown, apps) {
  const reducible = breakdown.filter(a => a.priority !== 'essential' && a.hours > 0);

  document.getElementById('simList').innerHTML = reducible.map(a => `
    <div class="sim-item">
      <div>
        <div class="sim-label">${a.label}</div>
        <div class="sim-current">Currently ${a.hours} hrs/day</div>
      </div>
      <input type="range" min="0" max="${a.hours}" step="0.5" value="${a.hours}"
             id="sim-${a.type}"
             oninput="updateSim('${a.type}', parseFloat(this.value))"/>
      <div class="sim-hrs" id="simval-${a.type}">${a.hours} hrs</div>
    </div>
  `).join('');

  // Init simulator hours from current values
  reducible.forEach(a => { S.simHours[a.type] = a.hours; });
  updateSimTotal();
}

async function updateSim(type, newVal) {
  document.getElementById(`simval-${type}`).textContent = newVal + ' hrs';
  S.simHours[type] = newVal;
  updateSimTotal();
}

async function updateSimTotal() {
  // Calculate new units using rule-based math (instant, no API call needed)
  const result = S.result;
  if (!result) return;

  const currentUnits = result.current_bill.monthly_units;
  const breakdown    = result.appliance_breakdown;
  const totalPred    = breakdown.reduce((s, a) => s + a.monthly_kwh, 0);
  const scale        = currentUnits / totalPred;

  let newPredicted = 0;
  for (const a of breakdown) {
    const newH = S.simHours[a.type] !== undefined ? S.simHours[a.type] : a.hours;
    newPredicted += (a.wattage / 1000) * newH * 30;
  }

  const newUnits  = Math.max(0, Math.round(newPredicted * scale));
  const newBill   = roughBill(newUnits);
  const saving    = result.current_bill.total_bill - newBill;

  document.getElementById('simBill').textContent    = 'Rs ' + newBill.toLocaleString();
  document.getElementById('simSaving').textContent  =
    saving > 0 ? '– Rs ' + Math.round(saving).toLocaleString() : 'Rs 0';
}

function roughBill(units) {
  // Approximate HESCO bill for simulator (fast, no server round-trip)
  const slabs = [[50,3.95],[100,7.74],[200,10.06],[300,12.44],[700,19.55],[Infinity,22.65]];
  let e = 0, rem = units, prev = 0;
  for (const [lim, rate] of slabs) {
    if (rem <= 0) break;
    const u = Math.min(rem, lim - prev);
    e += u * rate; rem -= u; prev = lim;
  }
  return Math.round(e * 1.223 + 400); // GST + FC surcharge + fixed
}

// ── Loading helpers ────────────────────────────────────────────────────────
function loading(msg) {
  document.getElementById('loadMsg').textContent = msg || 'Loading...';
  document.getElementById('loadingOverlay').classList.remove('hidden');
}
function hideLoading() {
  document.getElementById('loadingOverlay').classList.add('hidden');
}
