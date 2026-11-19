'''

nov 18 2026
initial notebook 

mimicking analysis from 
tmy_comparison_all_datacenters.ipynb

this is parallelized so it should run through ~400 datacenters in va and tx; 
the ones we have extracted nldas3 for 


'''

# import os
# import time
# import pandas as pd
# import numpy as np
# import xarray as xr
# import matplotlib.pyplot as plt
# import seaborn as sns
# import metpy.calc as mpcalc
# from metpy.units import units
# from matplotlib.backends.backend_pdf import PdfPages
# import concurrent.futures
# from tqdm import tqdm
# import warnings

# warnings.filterwarnings('ignore')

# # ---------------------------------------------------------
# # 1. HELPER FUNCTIONS & CONFIGURATIONS
# # ---------------------------------------------------------
# def get_season(month):
#     if month in [12, 1, 2]: return 'Winter'
#     elif month in [3, 4, 5]: return 'Spring'
#     elif month in [6, 7, 8]: return 'Summer'
#     else: return 'Fall'

# TABLE_CONFIGS = {
#     'dry_bulb': {'tmy': 'Temperature', 'nldas_base': 'Tair_C', 'name': 'Dry Bulb Temp', 'unit': '°C'},
#     'wet_bulb': {'tmy': 'Wet_Bulb', 'nldas_base': 'Twb_C', 'name': 'Wet Bulb Temp', 'unit': '°C'},
#     'rh': {'tmy': 'Relative Humidity', 'nldas_base': 'RH', 'name': 'Relative Humidity', 'unit': '%'},
#     'enthalpy': {'tmy': 'Enthalpy', 'nldas_base': 'Enthalpy', 'name': 'Enthalpy', 'unit': 'kJ/kg'}
# }
# SEASON_ORDER = ['Winter', 'Spring', 'Summer', 'Fall']
# PERCENTILES = [90, 95, 99]

# # ---------------------------------------------------------
# # 2. THE WORKER FUNCTION (Runs on individual CPU cores)
# # ---------------------------------------------------------
# def process_datacenter(dc_info, tmy_file, nldas_file, out_dir):
#     """Processes a single datacenter, creates a 2-page PDF, and returns raw metrics."""
#     try:
#         dc_id = int(dc_info['id'])
#         dc_name = dc_info['name'] if pd.notna(dc_info['name']) else f"DC_{dc_id}"
#         dc_state = dc_info['state_abb']
#         lat, lon = dc_info['lat'], dc_info['lon']

#         # --- 1. TMY PROCESSING ---
#         tmy_df = pd.read_csv(tmy_file, header=2)
#         tmy_df['Temperature'] = pd.to_numeric(tmy_df['Temperature'], errors='coerce')
#         tmy_df['Relative Humidity'] = pd.to_numeric(tmy_df['Relative Humidity'], errors='coerce')
#         tmy_df['Pressure'] = pd.to_numeric(tmy_df.get('Pressure', 1013), errors='coerce')

#         temp_tmy = tmy_df['Temperature'].values * units.degC
#         rh_tmy = tmy_df['Relative Humidity'].values * units.percent
#         press_tmy = tmy_df['Pressure'].values * units.mbar  

#         dewpoint_tmy = mpcalc.dewpoint_from_relative_humidity(temp_tmy, rh_tmy)
#         tmy_df['Wet_Bulb'] = mpcalc.wet_bulb_temperature(press_tmy, temp_tmy, dewpoint_tmy).m
#         mixing_ratio_tmy = mpcalc.mixing_ratio_from_relative_humidity(press_tmy, temp_tmy, rh_tmy)
#         tmy_df['Enthalpy'] = 1.006 * temp_tmy.m + mixing_ratio_tmy.m * (2501 + 1.86 * temp_tmy.m)

#         tmy_df = tmy_df[~((tmy_df['Month'] == 2) & (tmy_df['Day'] == 29))].reset_index(drop=True)
#         tmy_df['Month_Day_Hour'] = tmy_df['Month'].astype(str) + '_' + tmy_df['Day'].astype(str) + '_' + tmy_df['Hour'].astype(str)

#         # --- 2. NLDAS PROCESSING (Opened inside worker to prevent memory lockups) ---
#         with xr.open_dataset(nldas_file) as nldas_ds:
#             nldas_pt = nldas_ds.sel(lat=lat, lon=lon, method='nearest').compute()
        
#         nldas_df = nldas_pt.to_dataframe().reset_index()
#         nldas_df = nldas_df[~((nldas_df['time'].dt.month == 2) & (nldas_df['time'].dt.day == 29))]
#         nldas_df['Month_Day_Hour'] = (nldas_df['time'].dt.month.astype(str) + '_' + 
#                                       nldas_df['time'].dt.day.astype(str) + '_' + 
#                                       nldas_df['time'].dt.hour.astype(str))

#         if 'RH' not in nldas_df.columns:
#             temp_nldas = nldas_df['Tair_C'].values * units.degC
#             press_nldas = nldas_df.get('PSurf', np.full(len(nldas_df), 101325)).values * units.Pa
#             if 'Qair' in nldas_df.columns:
#                 mixing_ratio_nldas = nldas_df['Qair'].values * units('kg/kg')
#                 rh_nldas = mpcalc.relative_humidity_from_specific_humidity(press_nldas, temp_nldas, mixing_ratio_nldas) * 100 * units.percent
#                 nldas_df['RH'] = rh_nldas.m
#                 dewpt_nldas = mpcalc.dewpoint_from_relative_humidity(temp_nldas, rh_nldas)
#                 nldas_df['Twb_C'] = mpcalc.wet_bulb_temperature(press_nldas, temp_nldas, dewpt_nldas).m
#                 nldas_df['Enthalpy'] = 1.006 * temp_nldas.m + mixing_ratio_nldas.m * (2501 + 1.86 * temp_nldas.m)

#         nldas_cols = ['Tair_C', 'Twb_C', 'RH', 'Enthalpy']
#         nldas_quantiles = nldas_df.groupby('Month_Day_Hour')[nldas_cols].quantile([0.90, 0.95, 0.99]).unstack()
#         nldas_quantiles.columns = [f"{c}_{int(q*100)}" for c, q in nldas_quantiles.columns]

#         # --- 3. ALIGNMENT ---
#         aligned_df = tmy_df.merge(nldas_quantiles, left_on='Month_Day_Hour', right_index=True, how='left')
#         aligned_df['Season'] = aligned_df['Month'].map(get_season)

#         # --- 4. CREATE INDIVIDUAL PDF ---
#         pdf_path = os.path.join(out_dir, f'DC_Report_{dc_id}.pdf')
#         raw_metrics = [] # To return for master state averages
        
#         with PdfPages(pdf_path) as pdf:
#             # --- PAGE 1: TIMESERIES PLOT ---
#             sns.set_theme(style="whitegrid")
#             fig_ts, axes = plt.subplots(4, 1, figsize=(18, 16), sharex=True)
#             x_hours = range(len(aligned_df))

#             plot_configs = [
#                 ('Dry Bulb Temperature', 'Temperature', 'Tair_C', 'Temp (°C)'),
#                 ('Wet Bulb Temperature', 'Wet_Bulb', 'Twb_C', 'Temp (°C)'),
#                 ('Relative Humidity', 'Relative Humidity', 'RH', 'RH (%)'),
#                 ('Enthalpy', 'Enthalpy', 'Enthalpy', 'Enthalpy (kJ/kg)')
#             ]

#             for i, (title, tmy_col, nldas_prefix, ylabel) in enumerate(plot_configs):
#                 ax = axes[i]
#                 if f"{nldas_prefix}_99" in aligned_df.columns:
#                     ax.plot(x_hours, aligned_df[f"{nldas_prefix}_99"], color='darkred', linewidth=1.5, alpha=0.9, label='NLDAS 99th Pct')
#                     ax.plot(x_hours, aligned_df[f"{nldas_prefix}_95"], color='red', linewidth=1, alpha=0.6, label='NLDAS 95th Pct')
#                     ax.plot(x_hours, aligned_df[f"{nldas_prefix}_90"], color='orange', linewidth=1, alpha=0.6, label='NLDAS 90th Pct')
#                 if tmy_col in aligned_df.columns:
#                     ax.plot(x_hours, aligned_df[tmy_col], color='blue', linewidth=1.2, alpha=0.8, label='TMY (Typical Year)')

#                 if i == 0:
#                     for label, temp in {'A1 Max (32°C)': 32, 'A3 Max (40°C)': 40}.items():
#                         ax.text(100, temp + 1, label, color='black', fontweight='bold', bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))

#                 ax.set_title(f"{title}", fontsize=14, fontweight='bold')
#                 ax.set_ylabel(ylabel, fontsize=12)
#                 ax.legend(loc='upper right')
                
#                 if tmy_col in aligned_df.columns and f"{nldas_prefix}_99" in aligned_df.columns:
#                     ax.set_ylim(aligned_df[tmy_col].min() - 5, aligned_df[f"{nldas_prefix}_99"].max() + 5)

#             month_starts = aligned_df[(aligned_df['Day'] == 1) & (aligned_df['Hour'] == 0)].index
#             axes[-1].set_xticks(month_starts)
#             axes[-1].set_xticklabels(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'], rotation=0, ha='left')
#             axes[-1].set_xlim(0, 8760)
#             plt.suptitle(f'Hourly Time Series: TMY vs NLDAS-3 Extremes\n{dc_name} ({dc_state})', fontsize=18, fontweight='bold', y=0.98)
#             plt.tight_layout()
#             pdf.savefig(fig_ts) # Save Page 1
#             plt.close(fig_ts)   # Free memory

#             # --- PAGE 2: 2x2 VOLATILITY TABLES ---
#             fig_tbl, axes_tbl = plt.subplots(nrows=2, ncols=2, figsize=(18, 10))
#             axes_tbl = axes_tbl.flatten()
            
#             for i, (var_key, info) in enumerate(TABLE_CONFIGS.items()):
#                 ax = axes_tbl[i]
#                 ax.axis('off')
#                 results = []

#                 if info['tmy'] not in aligned_df.columns or f"{info['nldas_base']}_99" not in aligned_df.columns:
#                     ax.text(0.5, 0.5, f"Missing data for {info['name']}", ha='center', va='center', fontsize=14)
#                     continue

#                 for season in SEASON_ORDER:
#                     s_df = aligned_df[aligned_df['Season'] == season]
#                     if s_df.empty: continue
#                     tmy = s_df[info['tmy']]
#                     peak_tmy = tmy.max()

#                     for pct in PERCENTILES:
#                         nldas = s_df[f"{info['nldas_base']}_{pct}"]
#                         gap = nldas - tmy               
                        
#                         # Store RAW numerics for State Averages return
#                         raw_metrics.append({
#                             'state': dc_state, 'var_key': var_key, 'season': season, 'pct': pct,
#                             'avg_gap': gap.mean(), 'max_gap': gap.max(), 'peak_nldas': nldas.max(), 'peak_tmy': peak_tmy
#                         })

#                         results.append({
#                             'Season': season if pct == 90 else "",
#                             'NLDAS Pct': f"{pct}th",
#                             f'Avg Gap\n(NLDAS-TMY)': f"+{gap.mean():.1f} {info['unit']}",
#                             f'Max Gap\n(NLDAS-TMY)': f"+{gap.max():.1f} {info['unit']}",
#                             f'Peak NLDAS\nValue': f"{nldas.max():.1f}",
#                             f'Peak TMY\nValue': f"{peak_tmy:.1f}" if pct == 90 else "" 
#                         })

#                 # Draw Table
#                 summary_df = pd.DataFrame(results)
#                 table = ax.table(cellText=summary_df.values, colLabels=summary_df.columns, cellLoc='center', loc='center', bbox=[0, 0, 1, 1])
#                 table.auto_set_font_size(False)
#                 table.set_fontsize(11)

#                 row_colors = ['#F9F9F9']*3 + ['#E8F0F8']*3 + ['#F9F9F9']*3 + ['#E8F0F8']*3
#                 for (row, col), cell in table.get_celld().items():
#                     cell.set_edgecolor('white')
#                     cell.set_linewidth(1.0)
#                     if row == 0: 
#                         cell.set_facecolor('#4C72B0')
#                         cell.set_text_props(weight='bold', color='white')
#                         cell.set_height(0.20)
#                     else: 
#                         cell.set_facecolor(row_colors[row - 1])
#                         cell.set_height(0.15)
#                         if "99th" in summary_df.iloc[row-1]['NLDAS Pct']: cell.set_text_props(weight='bold')
#                         if col == 4: cell.set_text_props(color='darkred', weight='bold')
#                         if col in [0, 1]:
#                             cell.set_text_props(ha='left')
#                             cell._text.set_position((0.10, 0.5))

#                 ax.set_title(f"{info['name']}", fontweight="bold", fontsize=16, pad=10)

#             plt.suptitle(f"Volatility Overview: NLDAS Extremes vs TMY\n{dc_name} ({dc_state})", fontsize=20, fontweight='bold', y=1.02)
#             plt.tight_layout()
#             pdf.savefig(fig_tbl) # Save Page 2
#             plt.close(fig_tbl)   # Free memory

#         return dc_id, dc_state, raw_metrics

#     except Exception as e:
#         print(f"Error processing DC {dc_info.get('id', 'Unknown')}: {e}")
#         return None

# # ---------------------------------------------------------
# # 3. MAIN EXECUTION BLOCK (Queue Creation & Parallel Run)
# # ---------------------------------------------------------
# if __name__ == '__main__':
#     start_time = time.time()
#     out_dir = '/discover/nobackup/cmbreen/datacenters/datacenter/tmy_comparison/'
#     os.makedirs(out_dir, exist_ok=True)

#     tx_nldas3 = '/discover/nobackup/cmbreen/datacenters/texas_pure_hourly/tx_Pure_Hourly_Summary_FIXED.nc'
#     va_nldas3 = '/discover/nobackup/cmbreen/datacenters/va_pure_hourly/va_Pure_Hourly_Summary_FIXED.nc'

#     # Build task list
#     tasks = []
#     for idx, row in datacenter_information.iterrows():
#         dc_id = int(row['id'])
#         state_abb = row['state_abb']
        
#         if dc_id not in tmy_file_dict: continue

#         if state_abb == 'TX': nldas_file = tx_nldas3
#         elif state_abb == 'VA': nldas_file = va_nldas3
#         else: continue # Skip if not TX or VA

#         tasks.append((row.to_dict(), tmy_file_dict[dc_id], nldas_file, out_dir))

#     print(f"Queue populated with {len(tasks)} Datacenters. Starting multiprocessing pool...")

#     all_raw_metrics = []
    
#     # Run the multiprocessing pool
#     with concurrent.futures.ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:
#         futures = [executor.submit(process_datacenter, *task) for task in tasks]
        
#         # Display progress bar and worker logs
#         for future in tqdm(concurrent.futures.as_completed(futures), total=len(tasks), desc="Processing Datacenters"):
#             res = future.result()
#             if res is not None:
#                 dc_id, dc_state, raw_metrics = res
                
#                 # Use tqdm.write so it doesn't mess up the visual progress bar layout
#                 tqdm.write(f"Worker completed Datacenter {dc_id} in state {dc_state}")
                
#                 all_raw_metrics.extend(raw_metrics)

#     print(f"Finished generating individual PDFs in {round(time.time() - start_time, 2)} seconds.")

#     # ---------------------------------------------------------
#     # 4. GENERATE MASTER STATE-LEVEL AVERAGE PDF
#     # ---------------------------------------------------------
#     print("Generating Master State Average PDF...")
#     if all_raw_metrics:
#         # Convert all returned numbers to a DataFrame
#         metrics_df = pd.DataFrame(all_raw_metrics)
        
#         # Group by State, Variable, Season, and Percentile, then take the mean
#         state_avg = metrics_df.groupby(['state', 'var_key', 'season', 'pct']).mean().reset_index()

#         master_pdf_path = os.path.join(out_dir, 'Master_State_Averages.pdf')
        
#         with PdfPages(master_pdf_path) as master_pdf:
#             # We process TX first, then VA. Each gets one page in the PDF.
#             for state in ['TX', 'VA']:
                
#                 # Check if we have data for this state
#                 if state not in state_avg['state'].unique():
#                     continue

#                 fig, axes = plt.subplots(nrows=2, ncols=2, figsize=(18, 10))
#                 axes = axes.flatten()

#                 for i, (var_key, info) in enumerate(TABLE_CONFIGS.items()):
#                     ax = axes[i]
#                     ax.axis('off')
                    
#                     # Filter down to the specific state and variable
#                     var_df = state_avg[(state_avg['state'] == state) & (state_avg['var_key'] == var_key)]
#                     if var_df.empty: continue
                    
#                     results = []
#                     for season in SEASON_ORDER:
#                         s_df = var_df[var_df['season'] == season]
#                         for pct in PERCENTILES:
#                             # Catch missing percentiles safely
#                             if s_df[s_df['pct'] == pct].empty: continue
#                             row = s_df[s_df['pct'] == pct].iloc[0]
                            
#                             results.append({
#                                 'Season': season if pct == 90 else "",
#                                 'NLDAS Pct': f"{pct}th",
#                                 f'Avg Gap\n(NLDAS-TMY)': f"+{row['avg_gap']:.1f} {info['unit']}",
#                                 f'Max Gap\n(NLDAS-TMY)': f"+{row['max_gap']:.1f} {info['unit']}",
#                                 f'Avg Peak NLDAS\nValue': f"{row['peak_nldas']:.1f}",
#                                 f'Avg Peak TMY\nValue': f"{row['peak_tmy']:.1f}" if pct == 90 else "" 
#                             })

#                     # Draw Table
#                     summary_df = pd.DataFrame(results)
#                     table = ax.table(cellText=summary_df.values, colLabels=summary_df.columns, cellLoc='center', loc='center', bbox=[0, 0, 1, 1])
#                     table.auto_set_font_size(False)
#                     table.set_fontsize(11)

#                     row_colors = ['#F9F9F9']*3 + ['#E8F0F8']*3 + ['#F9F9F9']*3 + ['#E8F0F8']*3
#                     for (r, c), cell in table.get_celld().items():
#                         cell.set_edgecolor('white')
#                         cell.set_linewidth(1.0)
#                         if r == 0: 
#                             cell.set_facecolor('#4C72B0')
#                             cell.set_text_props(weight='bold', color='white')
#                             cell.set_height(0.20)
#                         else: 
#                             cell.set_facecolor(row_colors[r - 1])
#                             cell.set_height(0.15)
#                             if "99th" in summary_df.iloc[r-1]['NLDAS Pct']: cell.set_text_props(weight='bold')
#                             if c == 4: cell.set_text_props(color='darkred', weight='bold')
#                             if c in [0, 1]:
#                                 cell.set_text_props(ha='left')
#                                 cell._text.set_position((0.10, 0.5))

#                     ax.set_title(f"{info['name']}", fontweight="bold", fontsize=16, pad=10)

#                 plt.suptitle(f"STATE AVERAGE Volatility: NLDAS Extremes vs TMY ({state})", fontsize=20, fontweight='bold', y=1.02)
#                 plt.tight_layout()
                
#                 # Append this state's 2x2 grid as a page to the master PDF
#                 master_pdf.savefig(fig)
#                 plt.close(fig) # Free memory
                
#         print(f"Master PDF successfully saved to: {master_pdf_path}")

#     print("All tasks completed successfully!")


'''
new try as standalone script 


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

# ---------------------------------------------------------
# 1. HELPER FUNCTIONS & CONFIGURATIONS
# ---------------------------------------------------------
def get_season(month):
    if month in [12, 1, 2]: return 'Winter'
    elif month in [3, 4, 5]: return 'Spring'
    elif month in [6, 7, 8]: return 'Summer'
    else: return 'Fall'

TABLE_CONFIGS = {
    'dry_bulb': {'tmy': 'Temperature', 'nldas_base': 'Tair_C', 'name': 'Dry Bulb Temp', 'unit': '°C'},
    'wet_bulb': {'tmy': 'Wet_Bulb', 'nldas_base': 'Twb_C', 'name': 'Wet Bulb Temp', 'unit': '°C'},
    'rh': {'tmy': 'Relative Humidity', 'nldas_base': 'RH', 'name': 'Relative Humidity', 'unit': '%'},
    'enthalpy': {'tmy': 'Enthalpy', 'nldas_base': 'Enthalpy', 'name': 'Enthalpy', 'unit': 'kJ/kg'}
}
SEASON_ORDER = ['Winter', 'Spring', 'Summer', 'Fall']
PERCENTILES = [90, 95, 99]

# ---------------------------------------------------------
# 2. THE WORKER FUNCTION (Runs on individual CPU cores)
# ---------------------------------------------------------
def process_datacenter(dc_info, tmy_file, nldas_file, out_dir):
    """Processes a single datacenter, creates a 2-page PDF, and returns raw metrics."""
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

        tmy_df = tmy_df[~((tmy_df['Month'] == 2) & (tmy_df['Day'] == 29))].reset_index(drop=True)
        tmy_df['Month_Day_Hour'] = tmy_df['Month'].astype(str) + '_' + tmy_df['Day'].astype(str) + '_' + tmy_df['Hour'].astype(str)

        # --- 2. NLDAS PROCESSING (Opened inside worker to prevent memory lockups) ---
        with xr.open_dataset(nldas_file) as nldas_ds:
            nldas_pt = nldas_ds.sel(lat=lat, lon=lon, method='nearest').compute()
        
        nldas_df = nldas_pt.to_dataframe().reset_index()
        
        # Strip out frequency metadata to prevent "Invalid frequency: H" errors in newer pandas
        if isinstance(nldas_df['time'].dtype, pd.DatetimeTZDtype) or hasattr(nldas_df['time'].dt, 'freq'):
            nldas_df['time'] = nldas_df['time'].dt.tz_localize(None)

        nldas_df = nldas_df[~((nldas_df['time'].dt.month == 2) & (nldas_df['time'].dt.day == 29))]
        nldas_df['Month_Day_Hour'] = (nldas_df['time'].dt.month.astype(str) + '_' + 
                                      nldas_df['time'].dt.day.astype(str) + '_' + 
                                      nldas_df['time'].dt.hour.astype(str))

        if 'RH' not in nldas_df.columns:
            temp_nldas = nldas_df['Tair_C'].values * units.degC
            press_nldas = nldas_df.get('PSurf', np.full(len(nldas_df), 101325)).values * units.Pa
            if 'Qair' in nldas_df.columns:
                mixing_ratio_nldas = nldas_df['Qair'].values * units('kg/kg')
                rh_nldas = mpcalc.relative_humidity_from_specific_humidity(press_nldas, temp_nldas, mixing_ratio_nldas) * 100 * units.percent
                nldas_df['RH'] = rh_nldas.m
                dewpt_nldas = mpcalc.dewpoint_from_relative_humidity(temp_nldas, rh_nldas)
                nldas_df['Twb_C'] = mpcalc.wet_bulb_temperature(press_nldas, temp_nldas, dewpt_nldas).m
                nldas_df['Enthalpy'] = 1.006 * temp_nldas.m + mixing_ratio_nldas.m * (2501 + 1.86 * temp_nldas.m)

        nldas_cols = ['Tair_C', 'Twb_C', 'RH', 'Enthalpy']
        nldas_quantiles = nldas_df.groupby('Month_Day_Hour')[nldas_cols].quantile([0.90, 0.95, 0.99]).unstack()
        nldas_quantiles.columns = [f"{c}_{int(q*100)}" for c, q in nldas_quantiles.columns]

        # --- 3. ALIGNMENT ---
        aligned_df = tmy_df.merge(nldas_quantiles, left_on='Month_Day_Hour', right_index=True, how='left')
        aligned_df['Season'] = aligned_df['Month'].map(get_season)

        # --- 4. CREATE INDIVIDUAL PDF ---
        pdf_path = os.path.join(out_dir, f'DC_Report_{dc_id}.pdf')
        raw_metrics = [] # To return for master state averages
        
        with PdfPages(pdf_path) as pdf:
            # --- PAGE 1: TIMESERIES PLOT ---
            sns.set_theme(style="whitegrid")
            fig_ts, axes = plt.subplots(4, 1, figsize=(18, 16), sharex=True)
            x_hours = range(len(aligned_df))

            plot_configs = [
                ('Dry Bulb Temperature', 'Temperature', 'Tair_C', 'Temp (°C)'),
                ('Wet Bulb Temperature', 'Wet_Bulb', 'Twb_C', 'Temp (°C)'),
                ('Relative Humidity', 'Relative Humidity', 'RH', 'RH (%)'),
                ('Enthalpy', 'Enthalpy', 'Enthalpy', 'Enthalpy (kJ/kg)')
            ]

            for i, (title, tmy_col, nldas_prefix, ylabel) in enumerate(plot_configs):
                ax = axes[i]
                if f"{nldas_prefix}_99" in aligned_df.columns:
                    ax.plot(x_hours, aligned_df[f"{nldas_prefix}_99"], color='darkred', linewidth=1.5, alpha=0.9, label='NLDAS 99th Pct')
                    ax.plot(x_hours, aligned_df[f"{nldas_prefix}_95"], color='red', linewidth=1, alpha=0.6, label='NLDAS 95th Pct')
                    ax.plot(x_hours, aligned_df[f"{nldas_prefix}_90"], color='orange', linewidth=1, alpha=0.6, label='NLDAS 90th Pct')
                if tmy_col in aligned_df.columns:
                    ax.plot(x_hours, aligned_df[tmy_col], color='blue', linewidth=1.2, alpha=0.8, label='TMY (Typical Year)')

                if i == 0:
                    for label, temp in {'A1 Max (32°C)': 32, 'A3 Max (40°C)': 40}.items():
                        ax.text(100, temp + 1, label, color='black', fontweight='bold', bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))

                ax.set_title(f"{title}", fontsize=14, fontweight='bold')
                ax.set_ylabel(ylabel, fontsize=12)
                ax.legend(loc='upper right')
                
                if tmy_col in aligned_df.columns and f"{nldas_prefix}_99" in aligned_df.columns:
                    ax.set_ylim(aligned_df[tmy_col].min() - 5, aligned_df[f"{nldas_prefix}_99"].max() + 5)

            month_starts = aligned_df[(aligned_df['Day'] == 1) & (aligned_df['Hour'] == 0)].index
            axes[-1].set_xticks(month_starts)
            axes[-1].set_xticklabels(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'], rotation=0, ha='left')
            axes[-1].set_xlim(0, 8760)
            plt.suptitle(f'Hourly Time Series: TMY vs NLDAS-3 Extremes\n{dc_name} ({dc_state})', fontsize=18, fontweight='bold', y=0.98)
            plt.tight_layout()
            pdf.savefig(fig_ts) # Save Page 1
            plt.close(fig_ts)   # Free memory

            # --- PAGE 2: 2x2 VOLATILITY TABLES ---
            fig_tbl, axes_tbl = plt.subplots(nrows=2, ncols=2, figsize=(18, 10))
            axes_tbl = axes_tbl.flatten()
            
            for i, (var_key, info) in enumerate(TABLE_CONFIGS.items()):
                ax = axes_tbl[i]
                ax.axis('off')
                results = []

                if info['tmy'] not in aligned_df.columns or f"{info['nldas_base']}_99" not in aligned_df.columns:
                    ax.text(0.5, 0.5, f"Missing data for {info['name']}", ha='center', va='center', fontsize=14)
                    continue

                for season in SEASON_ORDER:
                    s_df = aligned_df[aligned_df['Season'] == season]
                    if s_df.empty: continue
                    tmy = s_df[info['tmy']]
                    peak_tmy = tmy.max()

                    for pct in PERCENTILES:
                        nldas = s_df[f"{info['nldas_base']}_{pct}"]
                        gap = nldas - tmy               
                        
                        # Store RAW numerics for State Averages return
                        raw_metrics.append({
                            'state': dc_state, 'var_key': var_key, 'season': season, 'pct': pct,
                            'avg_gap': gap.mean(), 'max_gap': gap.max(), 'peak_nldas': nldas.max(), 'peak_tmy': peak_tmy
                        })

                        results.append({
                            'Season': season if pct == 90 else "",
                            'NLDAS Pct': f"{pct}th",
                            f'Avg Gap\n(NLDAS-TMY)': f"+{gap.mean():.1f} {info['unit']}",
                            f'Max Gap\n(NLDAS-TMY)': f"+{gap.max():.1f} {info['unit']}",
                            f'Peak NLDAS\nValue': f"{nldas.max():.1f}",
                            f'Peak TMY\nValue': f"{peak_tmy:.1f}" if pct == 90 else "" 
                        })

                # Draw Table
                summary_df = pd.DataFrame(results)
                table = ax.table(cellText=summary_df.values, colLabels=summary_df.columns, cellLoc='center', loc='center', bbox=[0, 0, 1, 1])
                table.auto_set_font_size(False)
                table.set_fontsize(11)

                row_colors = ['#F9F9F9']*3 + ['#E8F0F8']*3 + ['#F9F9F9']*3 + ['#E8F0F8']*3
                for (row, col), cell in table.get_celld().items():
                    cell.set_edgecolor('white')
                    cell.set_linewidth(1.0)
                    if row == 0: 
                        cell.set_facecolor('#4C72B0')
                        cell.set_text_props(weight='bold', color='white')
                        cell.set_height(0.20)
                    else: 
                        cell.set_facecolor(row_colors[row - 1])
                        cell.set_height(0.15)
                        if "99th" in summary_df.iloc[row-1]['NLDAS Pct']: cell.set_text_props(weight='bold')
                        if col == 4: cell.set_text_props(color='darkred', weight='bold')
                        if col in [0, 1]:
                            cell.set_text_props(ha='left')
                            cell._text.set_position((0.10, 0.5))

                ax.set_title(f"{info['name']}", fontweight="bold", fontsize=16, pad=10)

            plt.suptitle(f"Volatility Overview: NLDAS Extremes vs TMY\n{dc_name} ({dc_state})", fontsize=20, fontweight='bold', y=1.02)
            plt.tight_layout()
            pdf.savefig(fig_tbl) # Save Page 2
            plt.close(fig_tbl)   # Free memory

        return dc_id, dc_state, raw_metrics

    except Exception as e:
        return dc_info.get('id', 'Unknown'), dc_info.get('state_abb', 'Unknown'), str(e)

# ---------------------------------------------------------
# 3. MAIN EXECUTION BLOCK (Queue Creation & Parallel Run)
# ---------------------------------------------------------
if __name__ == '__main__':
    start_time = time.time()
    print("Loading global datasets...")

    # Load Information Dataframes
    datacenter_information = pd.read_csv('/discover/nobackup/cmbreen/datacenters/data/im3_open_source_data_center_atlas_v2026.02.09.csv')
    tmy_data = glob.glob('/discover/nobackup/cmbreen/datacenters/noaa_tmy_downloads_datacenterslocs/zip/**/*.csv')
    
    tmy_file_dict = {}
    for filepath in tmy_data:
        if not filepath.endswith('-metadata.csv'): 
            folder_name = os.path.basename(os.path.dirname(filepath))
            try:
                folder_id_int = int(folder_name.split('_')[-1])
                tmy_file_dict[folder_id_int] = filepath
            except ValueError:
                continue

    out_dir = '/discover/nobackup/cmbreen/datacenters/datacenter/tmy_comparison/'
    os.makedirs(out_dir, exist_ok=True)

    tx_nldas3 = '/discover/nobackup/cmbreen/datacenters/texas_pure_hourly/tx_Pure_Hourly_Summary_FIXED.nc'
    va_nldas3 = '/discover/nobackup/cmbreen/datacenters/virginia_pure_hourly/va_Pure_Hourly_Summary_FIXED.nc'

    # Build task list
    tasks = []
    for idx, row in datacenter_information.iterrows():
        dc_id = int(row['id'])
        state_abb = row['state_abb']
        
        if dc_id not in tmy_file_dict: continue

        if state_abb == 'TX': nldas_file = tx_nldas3
        elif state_abb == 'VA': nldas_file = va_nldas3
        else: continue # Skip if not TX or VA

        tasks.append((row.to_dict(), tmy_file_dict[dc_id], nldas_file, out_dir))

    print(f"Queue populated with {len(tasks)} Datacenters (TX/VA). Starting multiprocessing pool...")

    all_raw_metrics = []
    
    # Run the multiprocessing pool
    with concurrent.futures.ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:
        futures = [executor.submit(process_datacenter, *task) for task in tasks]
        
        # Display progress bar and worker logs
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(tasks), desc="Processing Datacenters"):
            res = future.result()
            
            if isinstance(res, tuple) and len(res) == 3:
                dc_id, dc_state, raw_metrics_or_error = res
                
                # Success
                if isinstance(raw_metrics_or_error, list):
                    tqdm.write(f"Worker completed Datacenter {dc_id} in {dc_state}")
                    all_raw_metrics.extend(raw_metrics_or_error)
                # Failure
                else:
                    tqdm.write(f"ERROR on Datacenter {dc_id} in {dc_state}: {raw_metrics_or_error}")

    print(f"\nFinished generating individual PDFs in {round(time.time() - start_time, 2)} seconds.")

    # ---------------------------------------------------------
    # 4. GENERATE MASTER STATE-LEVEL AVERAGE PDF
    # ---------------------------------------------------------
    print("Generating Master State Average PDF...")
    if all_raw_metrics:
        metrics_df = pd.DataFrame(all_raw_metrics)
        state_avg = metrics_df.groupby(['state', 'var_key', 'season', 'pct']).mean().reset_index()

        master_pdf_path = os.path.join(out_dir, 'Master_State_Averages.pdf')
        
        with PdfPages(master_pdf_path) as master_pdf:
            # We process TX first, then VA. Each gets one page in the PDF.
            for state in ['TX', 'VA']:
                
                if state not in state_avg['state'].unique():
                    continue

                fig, axes = plt.subplots(nrows=2, ncols=2, figsize=(18, 10))
                axes = axes.flatten()

                for i, (var_key, info) in enumerate(TABLE_CONFIGS.items()):
                    ax = axes[i]
                    ax.axis('off')
                    
                    var_df = state_avg[(state_avg['state'] == state) & (state_avg['var_key'] == var_key)]
                    if var_df.empty: continue
                    
                    results = []
                    for season in SEASON_ORDER:
                        s_df = var_df[var_df['season'] == season]
                        for pct in PERCENTILES:
                            if s_df[s_df['pct'] == pct].empty: continue
                            row = s_df[s_df['pct'] == pct].iloc[0]
                            
                            results.append({
                                'Season': season if pct == 90 else "",
                                'NLDAS Pct': f"{pct}th",
                                f'Avg Gap\n(NLDAS-TMY)': f"+{row['avg_gap']:.1f} {info['unit']}",
                                f'Max Gap\n(NLDAS-TMY)': f"+{row['max_gap']:.1f} {info['unit']}",
                                f'Avg Peak NLDAS\nValue': f"{row['peak_nldas']:.1f}",
                                f'Avg Peak TMY\nValue': f"{row['peak_tmy']:.1f}" if pct == 90 else "" 
                            })

                    summary_df = pd.DataFrame(results)
                    table = ax.table(cellText=summary_df.values, colLabels=summary_df.columns, cellLoc='center', loc='center', bbox=[0, 0, 1, 1])
                    table.auto_set_font_size(False)
                    table.set_fontsize(11)

                    row_colors = ['#F9F9F9']*3 + ['#E8F0F8']*3 + ['#F9F9F9']*3 + ['#E8F0F8']*3
                    for (r, c), cell in table.get_celld().items():
                        cell.set_edgecolor('white')
                        cell.set_linewidth(1.0)
                        if r == 0: 
                            cell.set_facecolor('#4C72B0')
                            cell.set_text_props(weight='bold', color='white')
                            cell.set_height(0.20)
                        else: 
                            cell.set_facecolor(row_colors[r - 1])
                            cell.set_height(0.15)
                            if "99th" in summary_df.iloc[r-1]['NLDAS Pct']: cell.set_text_props(weight='bold')
                            if c == 4: cell.set_text_props(color='darkred', weight='bold')
                            if c in [0, 1]:
                                cell.set_text_props(ha='left')
                                cell._text.set_position((0.10, 0.5))

                    ax.set_title(f"{info['name']}", fontweight="bold", fontsize=16, pad=10)

                plt.suptitle(f"STATE AVERAGE Volatility: NLDAS Extremes vs TMY ({state})", fontsize=20, fontweight='bold', y=1.02)
                plt.tight_layout()
                
                # Append this state's 2x2 grid as a page to the master PDF
                master_pdf.savefig(fig)
                plt.close(fig) # Free memory
                
        print(f"Master PDF successfully saved to: {master_pdf_path}")

    print("All tasks completed successfully!")