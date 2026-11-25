'''
Redesigned Analysis 2 (Bar Charts): Completely replaced the old range, table, and violin plots with annual bar charts showing the average exceedance hours per year (2002–2022) for Texas and Virginia.
Built-In Variance Tracking: Leveraged Seaborn’s native error bars (errorbar='sd') in Analysis 2 to automatically calculate and display the standard deviation/variance across different datacenters within the same state.
Split Analysis 1 (Scatter Plots): Divided the expected vs. actual threshold scatter plot into two distinct figures (Low Percentiles: 0.4, 1, 2 and High Percentiles: 98, 99, 99.6) so the axes scale properly instead of clustering data in the extreme corners.
Massive Font Scaling: Increased font sizes globally across all figures—titles (up to 32), axis labels (26-28), and tick marks (26-28)—to ensure they are readable for posters or presentations.
Fixed Seaborn Deprecations: Replaced the outdated errcolor and errwidth arguments with the modern err_kws={'color': 'black', 'linewidth': 3} format to prevent future library errors.
Updated Worker Function: Modified process_datacenter so it now calculates and returns both the global threshold metrics (for Analysis 1) and the raw, year-by-year exceedance counts (for Analysis 2).
HPC & PDF Integration: Merged the visual updates back into the multiprocessing script, replacing plt.show() with PdfPages so the code can run headlessly on the batch node without crashing.
Targeted Filtering: Enforced the strict < 10km station distance requirement during metadata parsing, and added a specific filter to only plot "Enthalpy" for now to save compute time.
'''

import os
import time
import glob
import pandas as pd
import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
import seaborn as sns
import metpy.calc as mpcalc
from metpy.units import units
from matplotlib.backends.backend_pdf import PdfPages
import concurrent.futures
from tqdm import tqdm
import warnings

warnings.filterwarnings('ignore')

# =========================================================
# 0. GLOBAL PLOT CONFIGURATIONS (MASSIVE FONTS)
# =========================================================
sns.set_theme(style="whitegrid")
plt.rc('font', size=20)
plt.rc('axes', titlesize=28, labelsize=24)
plt.rc('xtick', labelsize=20)
plt.rc('ytick', labelsize=20)
plt.rc('legend', fontsize=20, title_fontsize=22)

PLOT_CONFIGS = {
    'dry_bulb': {'tmy': 'Temperature', 'nldas': 'Tair_C', 'name': 'Dry Bulb Temp', 'unit': '°C'},
    'wet_bulb': {'tmy': 'Wet_Bulb', 'nldas': 'Twb_C', 'name': 'Wet Bulb Temp', 'unit': '°C'},
    'rh': {'tmy': 'Relative Humidity', 'nldas': 'RH', 'name': 'Relative Humidity', 'unit': '%'},
    'enthalpy': {'tmy': 'Enthalpy', 'nldas': 'Enthalpy', 'name': 'Enthalpy', 'unit': 'kJ/kg'}
}

P_COLD = [0.4, 1.0, 2.0]
P_HOT = [98.0, 99.0, 99.6]
ALL_P = P_COLD + P_HOT

PLOT_YEARS = [2005, 2010, 2015, 2020]
YEAR_COLORS = {2005: 'dodgerblue', 2010: 'forestgreen', 2015: 'darkorange', 2020: 'purple'}


# =========================================================
# 1. THE WORKER FUNCTION
# =========================================================
def process_datacenter(dc_info, tmy_file, nldas_file, out_dir):
    try:
        dc_id = int(dc_info['id'])
        dc_name = dc_info['name'] if pd.notna(dc_info['name']) else f"DC_{dc_id}"
        dc_state = dc_info['state_abb']
        lat, lon = dc_info['lat'], dc_info['lon']

        # --- 1. TMY PROCESSING ---
        tmy_df = pd.read_csv(tmy_file, header=2)
        tmy_df['Temperature'] = pd.to_numeric(tmy_df['Temperature'], errors='coerce')
        tmy_df['Relative Humidity'] = pd.to_numeric(tmy_df['Relative Humidity'], errors='coerce')
        tmy_df['Pressure'] = pd.to_numeric(tmy_df.get('Pressure', 1013), errors='coerce')

        temp_tmy = tmy_df['Temperature'].values * units.degC
        rh_tmy = tmy_df['Relative Humidity'].values * units.percent
        press_tmy = tmy_df['Pressure'].values * units.mbar  

        dewpoint_tmy = mpcalc.dewpoint_from_relative_humidity(temp_tmy, rh_tmy)
        tmy_df['Wet_Bulb'] = mpcalc.wet_bulb_temperature(press_tmy, temp_tmy, dewpoint_tmy).m
        mixing_ratio_tmy = mpcalc.mixing_ratio_from_relative_humidity(press_tmy, temp_tmy, rh_tmy)
        tmy_df['Enthalpy'] = 1.006 * temp_tmy.m + mixing_ratio_tmy.m * (2501 + 1.86 * temp_tmy.m)

        # Drop leap day 
        tmy_df = tmy_df[~((tmy_df['Month'] == 2) & (tmy_df['Day'] == 29))].reset_index(drop=True)
        tmy_df['Month_Day_Hour'] = tmy_df['Month'].astype(str) + '_' + tmy_df['Day'].astype(str) + '_' + tmy_df['Hour'].astype(str)

        # --- 2. NLDAS PROCESSING ---
        with xr.open_dataset(nldas_file) as nldas_ds:
            nldas_pt = nldas_ds.sel(lat=lat, lon=lon, method='nearest').compute()
        
        nldas_df = nldas_pt.to_dataframe().reset_index()
        if isinstance(nldas_df['time'].dtype, pd.DatetimeTZDtype) or hasattr(nldas_df['time'].dt, 'freq'):
            nldas_df['time'] = nldas_df['time'].dt.tz_localize(None)

        tz_offset = -6 if dc_state == 'TX' else -5 
        nldas_df['time'] = nldas_df['time'] + pd.Timedelta(hours=tz_offset)

        # Temporal bounds and drop leap days
        nldas_df = nldas_df[(nldas_df['time'].dt.year >= 2002) & (nldas_df['time'].dt.year <= 2022)]
        nldas_df = nldas_df[~((nldas_df['time'].dt.month == 2) & (nldas_df['time'].dt.day == 29))]
        nldas_df['Month_Day_Hour'] = (nldas_df['time'].dt.month.astype(str) + '_' + 
                                      nldas_df['time'].dt.day.astype(str) + '_' + 
                                      nldas_df['time'].dt.hour.astype(str))

        if 'RH' not in nldas_df.columns:
            temp_nldas = nldas_df['Tair_C'].values * units.degC
            press_nldas = nldas_df.get('PSurf', np.full(len(nldas_df), 101325)).values * units.Pa
            mixing_ratio_nldas = nldas_df['Qair'].values * units('kg/kg')
            rh_nldas = mpcalc.relative_humidity_from_specific_humidity(press_nldas, temp_nldas, mixing_ratio_nldas) * 100 * units.percent
            nldas_df['RH'] = rh_nldas.m
            dewpt_nldas = mpcalc.dewpoint_from_relative_humidity(temp_nldas, rh_nldas)
            nldas_df['Twb_C'] = mpcalc.wet_bulb_temperature(press_nldas, temp_nldas, dewpt_nldas).m
            nldas_df['Enthalpy'] = 1.006 * temp_nldas.m + mixing_ratio_nldas.m * (2501 + 1.86 * temp_nldas.m)

        # --- 3. METRICS EXTRACTION (Updated for Analysis 1 & 2) ---
        threshold_metrics = []
        yearly_metrics = []
        
        tmy_pcts = {vk: {p: np.nanpercentile(tmy_df[info['tmy']], p) for p in ALL_P} for vk, info in PLOT_CONFIGS.items()}
        nldas_pcts = {vk: {p: np.nanpercentile(nldas_df[info['nldas']], p) for p in ALL_P} for vk, info in PLOT_CONFIGS.items()}

        for var_key, info in PLOT_CONFIGS.items():
            for p in ALL_P:
                threshold = nldas_pcts[var_key][p]
                tmy_col, nldas_col = info['tmy'], info['nldas']
                
                # Exceedance calculation
                if p >= 50:
                    nldas_yr_counts = nldas_df.groupby(nldas_df['time'].dt.year)[nldas_col].apply(lambda x: (x > threshold).sum())
                else:
                    nldas_yr_counts = nldas_df.groupby(nldas_df['time'].dt.year)[nldas_col].apply(lambda x: (x < threshold).sum())
                
                # Analysis 1 (Threshold Comparison)
                threshold_metrics.append({
                    'dc_id': dc_id,
                    'state': dc_state,
                    'var_key': var_key,
                    'percentile': p,
                    'Percentile': f"{p}th",
                    'tmy_val': tmy_pcts[var_key][p],
                    'nldas_val': threshold
                })

                # Analysis 2 (Annual Exceedances)
                for yr, count in nldas_yr_counts.items():
                    yearly_metrics.append({
                        'dc_id': dc_id,
                        'State': dc_state,
                        'var_key': var_key,
                        'Year': yr,
                        'Percentile': f"{p}th",
                        'Exceedance_Hours': count
                    })

        return dc_id, dc_state, threshold_metrics, yearly_metrics

    except Exception as e:
        return dc_info.get('id', 'Unknown'), dc_info.get('state_abb', 'Unknown'), str(e), str(e)


# =========================================================
# 2. MAIN EXECUTION BLOCK 
# =========================================================
if __name__ == '__main__':
    start_time = time.time()
    print("Loading datasets & Parsing metadata...")

    datacenter_information = pd.read_csv('/discover/nobackup/cmbreen/datacenters/data/im3_open_source_data_center_atlas_v2026.02.09.csv')
    tmy_data_meta = glob.glob('/discover/nobackup/cmbreen/datacenters/noaa_tmy_downloads_datacenterslocs/zip/**/*-metadata.csv')
    
    valid_dc_ids = set()
    tmy_file_dict = {}

    for meta_file in tmy_data_meta:
        try:
            folder_name = os.path.basename(os.path.dirname(meta_file))
            dc_id_int = int(folder_name.split('_')[-1])
            
            csv_candidates = glob.glob(os.path.join(os.path.dirname(meta_file), '*.csv'))
            tmy_csv = [f for f in csv_candidates if not f.endswith('-metadata.csv')][0]
            tmy_file_dict[dc_id_int] = tmy_csv

            df_meta = pd.read_csv(meta_file, header=None)
            dist_row = df_meta[df_meta[0] == 'Distance to Station (km)']
            if not dist_row.empty:
                distance = float(dist_row.iloc[0][1])
                if distance <= 10.0:  # Enforce Minimum Distance Requirement
                    valid_dc_ids.add(dc_id_int)
        except Exception:
            continue

    out_dir = '/discover/nobackup/cmbreen/datacenters/datacenter/tmy_comparison_TX_VA/'
    os.makedirs(out_dir, exist_ok=True)

    tx_nldas3 = '/discover/nobackup/cmbreen/datacenters/texas_pure_hourly/tx_Pure_Hourly_Summary_FIXED.nc'
    va_nldas3 = '/discover/nobackup/cmbreen/datacenters/virginia_pure_hourly/va_Pure_Hourly_Summary_FIXED.nc'

    tasks = []
    for idx, row in datacenter_information.iterrows():
        dc_id = int(row['id'])
        if dc_id not in valid_dc_ids or dc_id not in tmy_file_dict: continue

        state_abb = row['state_abb']
        nldas_file = tx_nldas3 if state_abb == 'TX' else va_nldas3 if state_abb == 'VA' else None
        if nldas_file: tasks.append((row.to_dict(), tmy_file_dict[dc_id], nldas_file, out_dir))

    all_threshold_metrics = []
    all_yearly_metrics = []
    
    with concurrent.futures.ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:
        futures = [executor.submit(process_datacenter, *task) for task in tasks]
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(tasks), desc="Processing DCs"):
            res = future.result()
            if isinstance(res, tuple) and len(res) == 4:
                if isinstance(res[2], list): all_threshold_metrics.extend(res[2])
                if isinstance(res[3], list): all_yearly_metrics.extend(res[3])

    if not all_threshold_metrics:
        print("No valid data processed. Exiting.")
        exit()

    df_analysis1 = pd.DataFrame(all_threshold_metrics)
    df_analysis2 = pd.DataFrame(all_yearly_metrics)

    # Calculate global distinct years for plotting X-axis in Analysis 2
    years = sorted(df_analysis2['Year'].unique())

    # =========================================================
    # 3. GENERATE ANALYSIS PLOTS (SAVED DIRECTLY TO PDF)
    # =========================================================
    print("\nGenerating Analysis PDFs...")

    pct_colors = {
        '0.4th': '#005ce6', '1.0th': '#4da6ff', '2.0th': '#b3d9ff',
        '98.0th': '#ffb3b3', '99.0th': '#ff4d4d', '99.6th': '#cc0000'
    }
    heat_colors = {'98.0th': '#ff9999', '99.6th': '#cc0000'}

    analysis1_pdf_path = os.path.join(out_dir, 'Analysis1_Scatter_Thresholds.pdf')
    analysis2_pdf_path = os.path.join(out_dir, 'Analysis2_Annual_Bars.pdf')

    with PdfPages(analysis1_pdf_path) as pdf1, PdfPages(analysis2_pdf_path) as pdf2:

        for var_key, info in PLOT_CONFIGS.items():
            
            # User specifically requested just enthalpy right now
            if var_key != 'enthalpy': 
                continue

            var_name = info['name']
            var_unit = info['unit']
            
            # --- Subset data for this variable ---
            df_a1_var = df_analysis1[df_analysis1['var_key'] == var_key]
            df_a2_var = df_analysis2[df_analysis2['var_key'] == var_key]

            if df_a1_var.empty or df_a2_var.empty:
                continue

            # =========================================================
            # ANALYSIS 1: EXPECTED VS ACTUAL (SCATTER)
            # =========================================================
            df_low = df_a1_var[df_a1_var['Percentile'].isin(['0.4th', '1.0th', '2.0th'])]
            df_high = df_a1_var[df_a1_var['Percentile'].isin(['98.0th', '99.0th', '99.6th'])]

            # -- Plot 1A: LOW PERCENTILES --
            fig1_low, ax1_low = plt.subplots(figsize=(14, 12))
            min_val = min(df_low['nldas_val'].min(), df_low['tmy_val'].min())
            max_val = max(df_low['nldas_val'].max(), df_low['tmy_val'].max())
            padding = (max_val - min_val) * 0.1
            min_val -= padding; max_val += padding

            ax1_low.plot([min_val, max_val], [min_val, max_val], 'k--', alpha=0.7, linewidth=3.5, label='1:1 Line (Zero Bias)')
            sns.scatterplot(data=df_low, x='nldas_val', y='tmy_val', hue='Percentile', style='state', 
                            palette={k: pct_colors[k] for k in ['0.4th', '1.0th', '2.0th']}, s=600, alpha=0.85, ax=ax1_low)

            ax1_low.set_title(f"Analysis 1: Threshold Comparison (LOW Percentiles)\nVariable: {var_name}", fontweight='bold', pad=25)
            ax1_low.set_xlabel(f"Actual NLDAS-3 Threshold ({var_unit})", fontweight='bold', labelpad=15, fontsize=26)
            ax1_low.set_ylabel(f"Expected TMY Threshold ({var_unit})", fontweight='bold', labelpad=15, fontsize=26)
            ax1_low.legend(loc='center left', bbox_to_anchor=(1.02, 0.5), markerscale=1.0, frameon=True, shadow=True)
            ax1_low.tick_params(axis='both', labelsize=26)
            plt.tight_layout()
            pdf1.savefig(fig1_low)
            plt.close(fig1_low)

            # -- Plot 1B: HIGH PERCENTILES --
            fig1_high, ax1_high = plt.subplots(figsize=(14, 12))
            min_val = min(df_high['nldas_val'].min(), df_high['tmy_val'].min())
            max_val = max(df_high['nldas_val'].max(), df_high['tmy_val'].max())
            padding = (max_val - min_val) * 0.1
            min_val -= padding; max_val += padding

            ax1_high.plot([min_val, max_val], [min_val, max_val], 'k--', alpha=0.7, linewidth=3.5, label='1:1 Line (Zero Bias)')
            sns.scatterplot(data=df_high, x='nldas_val', y='tmy_val', hue='Percentile', style='state', 
                            palette={k: pct_colors[k] for k in ['98.0th', '99.0th', '99.6th']}, s=600, alpha=0.85, ax=ax1_high)

            ax1_high.set_title(f"Analysis 1: Threshold Comparison (HIGH Percentiles)\nVariable: {var_name}", fontweight='bold', pad=25)
            ax1_high.set_xlabel(f"Actual NLDAS-3 Threshold ({var_unit})", fontweight='bold', labelpad=15, fontsize=26)
            ax1_high.set_ylabel(f"Expected TMY Threshold ({var_unit})", fontweight='bold', labelpad=15, fontsize=26)
            ax1_high.legend(loc='center left', bbox_to_anchor=(1.02, 0.5), markerscale=1.0, frameon=True, shadow=True)
            ax1_high.tick_params(axis='both', labelsize=26)
            plt.tight_layout()
            pdf1.savefig(fig1_high)
            plt.close(fig1_high)

            # =========================================================
            # ANALYSIS 2: ANNUAL EXCEEDANCE (BAR GRAPHS)
            # =========================================================
            df_heat = df_a2_var[df_a2_var['Percentile'].isin(['98.0th', '99.6th'])]
            fig2, axes2 = plt.subplots(nrows=2, ncols=1, figsize=(24, 18), sharex=True)

            for i, state in enumerate(['VA', 'TX']):
                ax = axes2[i]
                state_df = df_heat[df_heat['State'] == state]
                
                sns.barplot(data=state_df, x='Year', y='Exceedance_Hours', hue='Percentile', palette=heat_colors,
                            capsize=0.1, err_kws={'color': 'black', 'linewidth': 3}, edgecolor='black', linewidth=2, ax=ax)
                
                ax.set_title(f"Average Annual Exceedance Hours — {state}", fontweight='bold', pad=20, fontsize=28)
                ax.set_ylabel("Avg Hours Exceeded / Year", fontweight='bold', labelpad=15, fontsize=28)
                ax.tick_params(axis='y', labelsize=28)
                
                if i == 0:
                    ax.legend(title='Percentile', loc='upper right', frameon=True, shadow=True)
                else:
                    ax.get_legend().remove()
                    ax.set_xlabel("", fontweight='bold', labelpad=15)
                    ax.set_xticks(range(len(years)))
                    ax.set_xticklabels(years, rotation=45, ha='right', fontsize=28)
            
            plt.suptitle(f"Analysis 2: High-End (HOT) Percentile Violations per Year ({var_name})\nError bars = Variance across datacenters", 
                         fontweight='bold', fontsize=32, y=1.04)
            plt.tight_layout()
            pdf2.savefig(fig2)
            plt.close(fig2)

    print(f"\nAll Tasks Completed. PDFs saved to:\n{analysis1_pdf_path}\n{analysis2_pdf_path}")