"""
Hydraulic press analyzer:
reads Hopsan result CSVs -> metrics (JSON/console) -> dashboard.html.

Usage:
    python analyze.py [csv1 csv2 ...]

Same columns are expected for every concept.
Add a CSV and it appears everywhere.
"""

import sys
import glob
import json
import os

import math
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

A1 = 0.0056745  # head-side area [m²]

COLS = [
    "time_s",
    "position_mm",
    "velocity_mm_s",
    "head_pressure_bar",
    "rod_pressure_bar",
    "pump_pressure_bar",
    "pump_flow_L_min",
]

LABELS = {
    "Circuit3": "Circuit 3 (transverse and feed + meter out)",
    "Circuit1": "Circuit 1 (regenerative counterbalancing)",
    "Circuit2": "Circuit 2 (high-low pump)",
}

WIN = {
    "fast_down": (2.3, 2.9),
    "working": (3.6, 8.0),
    "fast_up": (10.4, 11.2),
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def mean_in_window(df, time_values, start, end, column):
    """Return the mean value of a column inside a time window."""
    mask = (time_values >= start) & (time_values <= end)

    if not np.any(mask):
        return float("nan")

    return df.loc[mask, column].mean()


def energy_in_window(power_w, time_s, start, end):
    """Calculate hydraulic energy in kJ using trapezoidal integration."""
    mask = (time_s >= start) & (time_s <= end)

    if np.count_nonzero(mask) < 2:
        return float("nan")

    return np.trapezoid(
        power_w[mask],
        time_s[mask]
    ) / 1000.0


def first_home_time(df):
    """Return the first time after 10.5 s where position is above -1 mm."""
    t = df["time_s"].to_numpy()
    position = df["position_mm"].to_numpy()

    mask = (t > 10.5) & (position > -1)

    if np.any(mask):
        return t[mask][0]

    return float("nan")


# ---------------------------------------------------------------------------
# Hydraulic analysis
# ---------------------------------------------------------------------------

def analyze(df):
    """Calculate hydraulic press performance metrics."""

    t = df["time_s"].to_numpy()

    # Hydraulic pump power:
    #
    # Pressure [bar] -> Pa:
    #     bar * 1e5
    #
    # Flow [L/min] -> m³/s:
    #     L/min / 60000
    #
    # Power [W] = Pressure [Pa] * Flow [m³/s]
    #
    pressure_pa = df["pump_pressure_bar"].to_numpy() * 1e5
    flow_m3_s = df["pump_flow_L_min"].to_numpy() / 60000.0

    pump_power_w = pressure_pa * flow_m3_s

    # Position at end of working stroke
    working_end_mask = (t >= 8.2) & (t <= 8.3)

    if np.any(working_end_mask):
        position_end_working = df.loc[
            working_end_mask,
            "position_mm"
        ].mean()
    else:
        position_end_working = float("nan")

    # Position near the end of the hold period
    hold_end_mask = (t >= 9.9) & (t <= 10.0)

    if np.any(hold_end_mask):
        position_hold_end = df.loc[
            hold_end_mask,
            "position_mm"
        ].mean()
    else:
        position_hold_end = float("nan")

    # Calculate metrics
    result = {
        "Fast-down speed [mm/s]":
            -mean_in_window(
                df, t,
                *WIN["fast_down"],
                "velocity_mm_s"
            ),

        "Working speed [mm/s]":
            -mean_in_window(
                df, t,
                *WIN["working"],
                "velocity_mm_s"
            ),

        "Fast-up speed [mm/s]":
            mean_in_window(
                df, t,
                *WIN["fast_up"],
                "velocity_mm_s"
            ),

        "Position at end of working [mm]":
            position_end_working,

        "Hold drift 8.2-10 s [mm]":
            position_hold_end - position_end_working,

        "Home reached at [s]":
            first_home_time(df),

        "Peak downward speed [mm/s]":
            -df["velocity_mm_s"].min(),

        "Peak head pressure [bar]":
            df["head_pressure_bar"].max(),

        "Peak rod pressure [bar]":
            df["rod_pressure_bar"].max(),

        "Peak pump flow [L/min]":
            df["pump_flow_L_min"].max(),

        "Pump hydraulic energy 2-11.35 s [kJ]":
            energy_in_window(
                pump_power_w,
                t,
                2.0,
                11.35
            ),

        "Pump hydraulic energy 0-14 s [kJ]":
            energy_in_window(
                pump_power_w,
                t,
                0.0,
                14.0
            ),
    }

    # Extra metrics for the target-vs-actual block (all computed from the CSV)
    pos = df["position_mm"].to_numpy()
    result["Total stroke 2-10 s [mm]"] = float((-pos[(t >= 2) & (t <= 9.9)]).max())
    result["Working stroke 3.2-8.2 s [mm]"] = float(np.interp(3.2, t, pos) - np.interp(8.2, t, pos))
    result["Steady working head pressure 5-8 s [bar]"] = mean_in_window(df, t, 5, 8, "head_pressure_bar")
    result["Peak pump pressure [bar]"] = df["pump_pressure_bar"].max()

    # Convert NumPy values to normal Python floats and round them.
    cleaned = {}

    for key, value in result.items():
        try:
            cleaned[key] = round(float(value), 2)
        except (TypeError, ValueError):
            cleaned[key] = None

    return cleaned


# ---------------------------------------------------------------------------
# Power / cumulative energy series and model-file (.hmf) facts
# ---------------------------------------------------------------------------

def power_series(df):
    """P = p x Q [kW] and cumulative hydraulic energy E = integral(P dt) [kJ], single-pressure basis."""
    t = df["time_s"].to_numpy()
    p_w = df["pump_pressure_bar"].to_numpy() * 1e5 * df["pump_flow_L_min"].to_numpy() / 60000.0
    cum = np.concatenate([[0.0], np.cumsum(0.5 * (p_w[1:] + p_w[:-1]) * np.diff(t))]) / 1000.0
    return p_w / 1000.0, cum


def read_hmf(csv_path, here):
    """Read verifiable facts from the Hopsan model file that belongs to a results CSV."""
    base = os.path.basename(csv_path).replace("_results.csv", ".hmf")
    for d in (os.path.join(here, "models"), os.path.dirname(os.path.abspath(csv_path)), here, "/mnt/user-data/uploads"):
        path = os.path.join(d, base)
        if os.path.isfile(path):
            break
    else:
        return {"found": False, "file": base}
    root = ET.parse(path).getroot()
    comps = {}
    for c in root.iter("component"):
        comps.setdefault(c.get("name"), c)
    par = lambda c: {q.get("name"): q.get("value") for q in c.iter("parameter")}
    v = {"found": True, "file": base, "pumps": [], "counterbalance": None, "forces": []}
    for name, c in comps.items():
        tn, p = c.get("typename"), par(c)
        if tn == "HydraulicCylinderC":
            a1, a2 = float(p["A_1#Value"]), float(p["A_2#Value"])
            v.update(A1_cm2=a1 * 1e4, A2_cm2=a2 * 1e4, stroke_mm=float(p["s_l#Value"]) * 1000,
                     bore_mm=math.sqrt(4 * a1 / math.pi) * 1000, rod_mm=math.sqrt(4 * (a1 - a2) / math.pi) * 1000)
        elif tn == "MechanicTranslationalMass":
            v["mass_kg"] = float(p["m"])
        elif tn == "HydraulicFixedDisplacementPump":
            v["pumps"].append({"name": name, "cc_rev": float(p["D_p#Value"]) * 1e6,
                               "rpm": float(p["n_p#Value"]) * 60 / (2 * math.pi)})
        elif tn == "HydraulicPressureReliefValve":
            v["relief_bar"] = float(p["p_max#Value"]) / 1e5
        elif tn == "HydraulicCounterBalanceValveG":
            v["counterbalance"] = float(p["pref#Value"]) / 1e5 if "pref#Value" in p else True
        elif tn == "SignalPulse" and "y_A#Value" in p and abs(float(p["y_A#Value"])) > 10000:
            v["forces"].append({"base_N": float(p["y_0#Value"]), "pulse_N": float(p["y_A#Value"]),
                                "t0": float(p["t_start#Value"]), "t1": float(p["t_end#Value"])})
    sim = root.find(".//simulationtime")
    v["sim_stop_s"] = float(sim.get("stop")) if sim is not None else None
    v["n_pumps"] = len(v["pumps"])
    v["total_cc_rev"] = round(sum(x["cc_rev"] for x in v["pumps"]), 2)
    return v


# ---------------------------------------------------------------------------
# File handling
# ---------------------------------------------------------------------------

def find_input_files(here):
    """Find Concept*_results.csv files when no files are supplied."""
    candidates = []

    # User-upload directory
    candidates.extend(
        glob.glob("/mnt/user-data/uploads/Circuit*_results.csv")
    )

    # data/ subdirectory
    candidates.extend(
        glob.glob(
            os.path.join(here, "data", "Circuit*_results.csv")
        )
    )

    # Same directory as this script
    candidates.extend(
        glob.glob(
            os.path.join(here, "Circuit*_results.csv")
        )
    )

    # Remove duplicates while preserving order
    return sorted(set(candidates))


def validate_dataframe(df, filename):
    """Check that the CSV contains exactly the expected columns."""

    actual = list(df.columns)

    if actual != COLS:
        raise ValueError(
            f"\nCSV columns differ in:\n"
            f"  {filename}\n\n"
            f"Expected:\n"
            f"  {COLS}\n\n"
            f"Found:\n"
            f"  {actual}\n"
        )


# ---------------------------------------------------------------------------
# Excel correction
# ---------------------------------------------------------------------------

def apply_excel_energy_correction(out, here):
    """
    Read model-derived energy values from Concept_Comparison.xlsx.

    Concept 3 may have two pumps, one of which is dumped to tank.
    Therefore p × Q_total from a single CSV pressure column can overstate
    the useful hydraulic energy.

    If the Excel value differs from the CSV estimate by more than 5%,
    replace the CSV estimate with the Excel value.
    """

    excel_candidates = (
        glob.glob("/mnt/user-data/uploads/Concept_Comparison.xlsx")
        + glob.glob(
            os.path.join(here, "data", "Concept_Comparison.xlsx")
        )
        + glob.glob(
            os.path.join(here, "Concept_Comparison.xlsx")
        )
    )

    if not excel_candidates:
        return

    xlsx_file = excel_candidates[0]

    try:
        import openpyxl
    except ImportError:
        print(
            "Warning: openpyxl is not installed; "
            "Excel energy correction skipped."
        )
        return

    try:
        workbook = openpyxl.load_workbook(
            xlsx_file,
            data_only=True
        )

        worksheet = workbook.active

        for row in worksheet.iter_rows(values_only=True):

            if not row or not row[0]:
                continue

            label = str(row[0])

            if not label.startswith("Pump hydraulic energy"):
                continue

            if "2-11.35" in label:
                metric_key = (
                    "Pump hydraulic energy 2-11.35 s [kJ]"
                )
            elif "0-14" in label:
                metric_key = (
                    "Pump hydraulic energy 0-14 s [kJ]"
                )
            else:
                continue

            # Map Excel columns: row[2]=Concept1(Circuit3), row[3]=Concept2(Circuit1), row[4]=Concept3(Circuit2)
            mapping = {
                "Circuit3": row[2] if len(row) > 2 else None,
                "Circuit1": row[3] if len(row) > 3 else None,
                "Circuit2": row[4] if len(row) > 4 else None,
            }

            for concept in out:
                excel_value = mapping.get(concept["key"])

                if not isinstance(
                    excel_value,
                    (int, float)
                ):
                    continue

                csv_value = concept["metrics"].get(metric_key)

                if csv_value is None:
                    continue

                if excel_value == 0:
                    continue

                difference = abs(
                    excel_value - csv_value
                ) / abs(excel_value)

                if difference > 0.05:

                    print(
                        f"note: {concept['name']} "
                        f"{metric_key}: "
                        f"CSV {csv_value} -> "
                        f"Excel {excel_value}"
                    )

                    concept["metrics"][metric_key] = round(
                        float(excel_value),
                        2
                    )
                    concept["energy_corrected"] = True

    except Exception as exc:
        print(
            f"Warning: could not read "
            f"{xlsx_file}: {exc}"
        )


# ---------------------------------------------------------------------------
# Energy savings
# ---------------------------------------------------------------------------

def calculate_energy_savings(out):
    """Calculate energy saving relative to Concept 1."""

    if not out:
        return

    base = out[0]["metrics"].get(
        "Pump hydraulic energy 2-11.35 s [kJ]"
    )

    if base is None or base == 0:
        for concept in out:
            concept["metrics"][
                "Energy saving vs first circuit [%]"
            ] = None

        return

    for concept in out:

        energy = concept["metrics"].get(
            "Pump hydraulic energy 2-11.35 s [kJ]"
        )

        if energy is None:
            saving = None
        else:
            saving = 100.0 * (
                1.0 - energy / base
            )

        concept["metrics"][
            "Energy saving vs first circuit [%]"
        ] = (
            round(saving, 1)
            if saving is not None
            else None
        )


# ---------------------------------------------------------------------------
# Dashboard generation
# ---------------------------------------------------------------------------

def generate_dashboard(out, here):
    """Create dashboard.html from dashboard_template.html."""

    template_file = os.path.join(
        here,
        "dashboard_template.html"
    )

    output_file = os.path.join(
        here,
        "dashboard.html"
    )

    if not os.path.isfile(template_file):
        raise FileNotFoundError(
            f"Dashboard template not found:\n"
            f"  {template_file}"
        )

    # IMPORTANT:
    # Explicit UTF-8 prevents Windows cp1252 decoding errors.
    with open(
        template_file,
        "r",
        encoding="utf-8"
    ) as f:
        template = f.read()

    json_data = json.dumps(
        out,
        separators=(",", ":"),
        ensure_ascii=False
    )

    dashboard = template.replace(
        "__DATA__",
        json_data
    )

    # IMPORTANT:
    # Explicit UTF-8 prevents errors caused by characters such as:
    # ▶  → U+25B6
    # –  → U+2013
    # °  → U+00B0
    # ²  → U+00B2
    with open(
        output_file,
        "w",
        encoding="utf-8",
        newline=""
    ) as f:
        f.write(dashboard)

    print()
    print("Dashboard created successfully:")
    print(f"  {output_file}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():

    here = os.path.dirname(
        os.path.abspath(__file__)
    )

    # -------------------------------------------------------
    # Determine input CSV files
    # -------------------------------------------------------

    if len(sys.argv) > 1:
        files = sys.argv[1:]
    else:
        files = find_input_files(here)

    if not files:
        raise FileNotFoundError(
            "No Circuit*_results.csv files found.\n"
            "Either place the CSV files beside analyze.py "
            "or provide them as command-line arguments."
        )

    print()
    print("Hydraulic press analysis")
    print("=" * 80)

    # -------------------------------------------------------
    # Analyze each concept
    # -------------------------------------------------------

    out = []

    for filename in files:

        if not os.path.isfile(filename):
            raise FileNotFoundError(
                f"CSV file not found:\n  {filename}"
            )

        print(f"Reading: {filename}")

        df = pd.read_csv(filename)

        validate_dataframe(
            df,
            filename
        )

        # Downsample dashboard data to reduce HTML size.
        dashboard_df = (
            df.iloc[::5]
            .round(2)
        )

        # Concept key:
        # Concept1_results.csv -> Concept1
        key = os.path.basename(
            filename
        ).split("_")[0]

        p_kw, e_cum = power_series(df)
        out.append({
            "name": LABELS.get(
                key,
                key
            ),
            "key": key,
            "csv": os.path.basename(filename),
            "val": read_hmf(filename, here),
            "energy_corrected": False,
            "power_kw": [round(x, 3) for x in p_kw[::5]],
            "energy_cum_kj": [round(x, 3) for x in e_cum[::5]],

            "metrics": analyze(df),

            "data": {
                column: dashboard_df[column].tolist()
                for column in COLS
            },
        })

    # -------------------------------------------------------
    # Apply Excel model-derived energy corrections
    # -------------------------------------------------------

    apply_excel_energy_correction(
        out,
        here
    )

    # -------------------------------------------------------
    # Calculate energy savings
    # -------------------------------------------------------

    calculate_energy_savings(out)
    for c in out:
        v = c["val"]
        c["val"]["reasons"] = [
            "9 t load interpretation (tool force vs cylinder force) is unconfirmed",
            *(["Relief valve is %.0f bar in the model; the team stated 175 bar" % v["relief_bar"]]
              if v.get("relief_bar") and abs(v["relief_bar"] - 175) > 1 else []),
            *(["Energy uses an unverified Excel value (CSV has one pressure for two pumps)"] if c["energy_corrected"] else []),
        ]

    # -------------------------------------------------------
    # Print results
    # -------------------------------------------------------

    print()
    print("=" * 80)
    print()

    print(
        pd.DataFrame({
            concept["name"]: concept["metrics"]
            for concept in out
        }).to_string()
    )

    # -------------------------------------------------------
    # Generate dashboard
    # -------------------------------------------------------

    generate_dashboard(
        out,
        here
    )

    print()
    print("Analysis completed successfully.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    main()
