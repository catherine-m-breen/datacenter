import os
import glob
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import warnings

warnings.filterwarnings('ignore')

# ==========================================
# CONFIGURATION TOGGLES
# ==========================================
PROCESS_ALL_STATIONS = False  # False = VA & TX only, True = All stations in directory

STATION_DIR = '/discover/nobackup/cmbreen/datacenters/uscrn_independent_data'
OUTPUT_DIR = './station_qaqc_reports'

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Define the columns we want to inspect
VARS_TO_CHECK = ['temperature', 'relative_humidity', 'precipitation']

# Define units for plotting
UNITS = {
    'temperature': '°C',
    'relative_humidity': '%',
    'precipitation': 'mm'
}

# Define meteorological "extreme" thresholds to flag suspicious data
THRESHOLDS = {
    'temperature': {'low': -40.0, 'high': 50.0},        # °C
    'relative_humidity': {'low': 0.0, 'high': 100.0},   # %
    'precipitation': {'low': 0.0, 'high': 150.0}        # mm/hr
}

# ==========================================
# GATHER FILES
# ==========================================
if PROCESS_ALL_STATIONS:
    # Grabs all CSVs but ignores the combined summary file
    station_files = [f for f in glob.glob(os.path.join(STATION_DIR, '*.csv')) 
                     if not os.path.basename(f).startswith('all_')]
else:
    # Grabs only VA and TX
    station_files = glob.glob(os.path.join(STATION_DIR, 'VA_*.csv')) + \
                    glob.glob(os.path.join(STATION_DIR, 'TX_*.csv'))

print(f"Total stations queued for QA/QC processing: {len(station_files)}\n")

summary_stats = []

# ==========================================
# PROCESSING LOOP
# ==========================================
for file_idx, stn_file in enumerate(station_files):
    stn_name = os.path.basename(stn_file).replace('.csv', '')
    print(f"[{file_idx+1}/{len(station_files)}] Inspecting {stn_name}...")
    
    # Load data
    df = pd.read_csv(stn_file)
    total_rows = len(df)
    
    station_record = {
        'station_name': stn_name,
        'total_records': total_rows
    }
    
    # --- ISOLATE AND SAVE MISSING TIMESTAMPS ---
    # Find columns that actually exist in the dataframe
    available_vars = [v for v in VARS_TO_CHECK if v in df.columns]
    
    # Filter for any row where at least one of the variables is NaN
    if available_vars:
        missing_mask = df[available_vars].isna().any(axis=1)
        df_missing = df[missing_mask]
        
        if not df_missing.empty:
            missing_csv_path = os.path.join(OUTPUT_DIR, f"{stn_name}_missing_timestamps.csv")
            # Save just the datetime and the variables to keep it clean
            cols_to_save = ['datetime'] + available_vars
            df_missing[cols_to_save].to_csv(missing_csv_path, index=False)
    
    # --- GENERATE PDF REPORT ---
    pdf_path = os.path.join(OUTPUT_DIR, f"{stn_name}_distributions.pdf")
    
    with PdfPages(pdf_path) as pdf:
        fig, axes = plt.subplots(2, 3, figsize=(16, 10))
        fig.suptitle(f"Data Distribution & Outliers\nStation: {stn_name} | Total Records: {total_rows:,}", fontsize=18, fontweight='bold')
        
        for i, var in enumerate(VARS_TO_CHECK):
            if var in df.columns:
                data = df[var]
                unit_str = UNITS.get(var, '')
                
                # Calculate Missing Values
                missing_count = data.isna().sum()
                missing_pct = (missing_count / total_rows) * 100
                valid_data = data.dropna()
                
                station_record[f'{var}_missing_count'] = missing_count
                station_record[f'{var}_missing_pct'] = round(missing_pct, 2)
                
                if not valid_data.empty:
                    # Calculate Extremes & Stats
                    v_min, v_max = valid_data.min(), valid_data.max()
                    v_mean, v_median = valid_data.mean(), valid_data.median()
                    
                    low_thresh = THRESHOLDS[var]['low']
                    high_thresh = THRESHOLDS[var]['high']
                    extreme_low_count = (valid_data < low_thresh).sum()
                    extreme_high_count = (valid_data > high_thresh).sum()
                    
                    station_record[f'{var}_min'] = round(v_min, 2)
                    station_record[f'{var}_max'] = round(v_max, 2)
                    station_record[f'{var}_mean'] = round(v_mean, 2)
                    station_record[f'{var}_extreme_lows'] = extreme_low_count
                    station_record[f'{var}_extreme_highs'] = extreme_high_count
                    
                    # Plot Histograms (Top Row)
                    ax_hist = axes[0, i]
                    ax_hist.hist(valid_data, bins=50, color='skyblue', edgecolor='black', alpha=0.7)
                    ax_hist.set_title(f"{var.capitalize()}\nMissing: {missing_pct:.1f}%", fontsize=14)
                    ax_hist.set_xlabel(f"Value ({unit_str})")
                    ax_hist.set_ylabel("Frequency")
                    ax_hist.grid(axis='y', alpha=0.3)
                    
                    ax_hist.axvline(low_thresh, color='red', linestyle='--', alpha=0.6, label='Low Thresh')
                    ax_hist.axvline(high_thresh, color='red', linestyle='--', alpha=0.6, label='High Thresh')
                    
                    # Plot Boxplots (Bottom Row)
                    ax_box = axes[1, i]
                    ax_box.boxplot(valid_data, vert=False, flierprops={'marker': 'o', 'markerfacecolor': 'red', 'markersize': 4, 'alpha': 0.5})
                    ax_box.set_title(f"{var.capitalize()} Spread\nMin: {v_min:.1f} | Max: {v_max:.1f}", fontsize=12)
                    ax_box.set_xlabel(f"Value ({unit_str})")
                    ax_box.set_yticks([])
                    ax_box.grid(axis='x', alpha=0.3)
                    
                else:
                    # All data is missing
                    station_record[f'{var}_min'] = np.nan
                    station_record[f'{var}_max'] = np.nan
                    station_record[f'{var}_mean'] = np.nan
                    station_record[f'{var}_extreme_lows'] = 0
                    station_record[f'{var}_extreme_highs'] = 0
                    
                    axes[0, i].text(0.5, 0.5, 'ALL DATA MISSING', ha='center', va='center', color='red', weight='bold')
                    axes[0, i].set_title(var.capitalize())
                    axes[0, i].axis('off')
                    axes[1, i].axis('off')
            else:
                print(f"  -> Warning: Column '{var}' not found in {stn_name}")
                
        plt.tight_layout(rect=[0, 0.03, 1, 0.90]) 
        pdf.savefig(fig)
        plt.close(fig) 
        
    summary_stats.append(station_record)

# ==========================================
# EXPORT SUMMARY CSV
# ==========================================
summary_df = pd.DataFrame(summary_stats)
csv_output_path = os.path.join(OUTPUT_DIR, 'ALL_STATIONS_qaqc_summary.csv')
summary_df.to_csv(csv_output_path, index=False)

print(f"\nDone! QA/QC Checks complete.")
print(f"1. Individual Station PDF Distributions saved in: {OUTPUT_DIR}/")
print(f"2. Individual Station Missing Timestamps CSVs saved in: {OUTPUT_DIR}/")
print(f"3. Master Statistical Summary Table saved to: {csv_output_path}")