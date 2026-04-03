# Smart Energy Optimizer

**Live Demo:** [AI Bill Analyzer and Optimizer](https://ai-bill-analyzer-and-optimizer.onrender.com/)

## Project Overview

The Smart Energy Optimizer is a web-based application designed to **analyze electricity bills** and **provide optimized energy recommendations**. It combines OCR-based bill reading, HESCO slab rate calculations, and advanced machine learning models to help users reduce electricity consumption and cost.

---

## Features

- **Bill Analysis:** Upload electricity bills and extract key information automatically.  
- **Slab Rate Calculation:** Calculates electricity cost according to HESCO slab rates.  
- **Recommendation Engine:** Suggests energy optimization strategies based on usage patterns.  
- **Machine Learning Models:** Uses clustering and anomaly detection to identify unusual consumption patterns.

---


## Project Structure

```
smart_energy_optimizer_project/
│
├── frontend/
│   └── static/
│       ├── css/
│       ├── js/
│       └── templates/
│
├── backend/
│   └── smart_energy_optimizer/
│       ├── notebooks/           # Data preparation & model training
│       ├── backend/             # Flask API and modules
│       │   ├── app.py
│       │   ├── bill_reader.py
│       │   ├── bill_calculator.py
│       │   ├── optimizer.py
│       │   └── model/           # Trained AI models
└── README.md                         
```

---


---

## How It Works

1. Users **upload their electricity bill** through the web interface.  
2. The **OCR module** reads and extracts consumption data from the bill.  
3. The **bill calculator** applies HESCO slab rates to compute costs.  
4. The **optimizer module** uses ML models to analyze usage patterns and detect anomalies.  
5. Users receive **personalized recommendations** to optimize energy consumption and reduce costs.

---
## Benefits

- Save money by identifying inefficient electricity usage.  
- Get actionable energy-saving suggestions without manual calculations.  
- Easy-to-use web interface suitable for non-technical users.  
- Insightful analysis with machine learning for better decision-making.  

---
## Technologies Used

- Python, Flask  
- HTML, CSS, JavaScript  
- Pandas, NumPy, scikit-learn (for ML models)  
- OCR tools for bill extraction  
- Render.com for deployment

---

