# Hydraulic Press Simulation & Analysis – Group 2 (Danfoss Assignment)

An engineering analysis and interactive dashboard for evaluating, comparing, and diagnosing hydraulic press circuits designed in Hopsan according to Danfoss industrial design specifications.

---

## 📁 Repository Structure

```
DANFOSS_2/
├── models/                     # Hopsan simulation circuit models (.hmf)
│   ├── Circuit1_Regenerative_counterbalancing.hmf
│   ├── Circuit2_High_Low_pump.hmf
│   └── Circuit3_Transverse_and_feed_meter_out.hmf
├── data/                       # Simulation export results (.csv) & reference (.xlsx)
│   ├── Circuit1_Regenerative_counterbalancing_results.csv
│   ├── Circuit2_High_Low_pump_results.csv
│   ├── Circuit3_Transverse_and_feed_meter_out_results.csv
│   └── Concept_Comparison.xlsx
├── videos/                     # Hopsan simulation recordings (.mp4)
│   ├── Circuit1_Regenerative_counterbalancing.mp4
│   ├── Circuit2_High_Low_pump_results.mp4
│   └── Circuit3_Transverse_and_feed_meter_out.mp4
├── analyze.py                  # Python analysis engine & metric calculation
├── dashboard_template.html     # Dashboard layout, Chart.js visualizer & styling
├── dashboard.html              # Generated standalone interactive dashboard
├── .gitignore                  # Git ignore rules for Python, OS & editor files
└── README.md                   # Project documentation
```

---

## 🎯 Design Requirements (Group 2 Brief)

The hydraulic press must execute a four-phase cycle:
- **Cylinder Dimensions**: 85 mm Bore / 50 mm Rod
- **Dead Load**: 3 t (3,000 kg)
- **Holding Load**: 9 t
- **Phase 1 (Fast Down)**: 200 mm/s for 200 mm
- **Phase 2 (Working / Pressing)**: 10 mm/s for 50 mm
- **Phase 3 (Holding)**: 2.0 s duration
- **Phase 4 (Fast Up / Return)**: 200 mm/s

---

## ⚙️ Evaluated Hydraulic Circuits

1. **Circuit 1 – Regenerative Counterbalancing**  
   `models/Circuit1_Regenerative_counterbalancing.hmf`  
   Employs a counterbalance valve and regenerative line to return rod-side oil to the cap end during rapid descent, reducing pump displacement requirements.

2. **Circuit 2 – High-Low Pump System**  
   `models/Circuit2_High_Low_pump.hmf`  
   Two-pump architecture: a high-flow low-pressure pump for rapid traverse phases and a low-flow high-pressure pump for pressing. Achieves the lowest energy consumption (~79% reduction vs Circuit 1).

3. **Circuit 3 – Transverse and Feed + Meter-Out**  
   `models/Circuit3_Transverse_and_feed_meter_out.hmf`  
   Meter-out speed control with transverse feed valve. Simplest topology with return-side throttling.

---

## 🚀 How to Run

### 1. Prerequisites
Install required Python libraries:
```bash
pip install pandas numpy openpyxl
```

### 2. Run Analysis & Generate Dashboard
Run the analysis script from the repository root:
```bash
python analyze.py
```
This reads the simulation results from `data/`, inspects the Hopsan models in `models/`, computes key engineering metrics, and generates `dashboard.html`.

### 3. View the Interactive Dashboard
Open `dashboard.html` in any modern web browser (Edge, Chrome, Firefox).

---

## 📊 Dashboard Capabilities

- **Overview & Cycle Replay**: Smooth 60 FPS real-time stroke cycle animation with dynamic ram position, live gauges (pressure, flow, velocity, power, energy), and model validation checks.
- **Circuit Comparison**: Weighted decision matrix with customizable priority sliders (Energy, Dynamics, Pressure, Cost/Simplicity), sensitivity rankings, and side-by-side performance tables.
- **Best Circuit Deep-Dive**: Target-vs-simulated verification and 8 detailed engineering curves.
- **Sensor Architecture**: 4-column physical-to-digital sensor mapping and multi-channel telemetry.
- **Data Science / Anomaly Detection**: Statistical residual-based fault detector with interactive synthetic fault injection (leakage, wear, friction) and real-time physical diagnostics.
- **Simulation Evidence**: Direct embedded video playback of Hopsan simulation recordings.
