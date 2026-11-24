'''

nov 18 2026
initial notebook 

mimicking analysis from 
tmy_comparison_all_datacenters.ipynb

this is parallelized so it should run through ~400 datacenters in va and tx; 
the ones we have extracted nldas3 for 


1. Compare the extreme percentiles from TMY and NLDAS-3

For each data-center location, calculate the following percentiles independently for both datasets:

98th percentile (2% annual cooling exceedance)

99th percentile (1% annual cooling exceedance)

99.6th percentile (0.4% annual cooling exceedance)

For NLDAS-3, use the complete historical hourly record for the reference period, rather than calculating a separate percentile for each calendar hour. For TMY, calculate the corresponding percentiles from its 8,760 hourly observations.

This will allow us to compare the magnitude of the extreme conditions represented in each dataset.

For example, if the NLDAS-3 99.6th-percentile temperature is 40°C and the corresponding TMY value is 37°C, we can quantify that difference directly.

Let's do this initially for dry-bulb temperature, wet-bulb temperature, and enthalpy.




'''

'''

adding bar plot 


'''


# import os
# import time
# import glob
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

# # Color palette for bar charts to match line plots
# BAR_PALETTE = {90: 'orange', 95: 'red', 99: 'darkred'}

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
        
#         # Strip out frequency metadata to prevent "Invalid frequency: H" errors in newer pandas
#         if isinstance(nldas_df['time'].dtype, pd.DatetimeTZDtype) or hasattr(nldas_df['time'].dt, 'freq'):
#             nldas_df['time'] = nldas_df['time'].dt.tz_localize(None)

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
#         return dc_info.get('id', 'Unknown'), dc_info.get('state_abb', 'Unknown'), str(e)

# # ---------------------------------------------------------
# # 3. MAIN EXECUTION BLOCK (Queue Creation & Parallel Run)
# # ---------------------------------------------------------
# if __name__ == '__main__':
#     start_time = time.time()
#     print("Loading global datasets...")

#     # Load Information Dataframes
#     datacenter_information = pd.read_csv('/discover/nobackup/cmbreen/datacenters/data/im3_open_source_data_center_atlas_v2026.02.09.csv')
#     tmy_data = glob.glob('/discover/nobackup/cmbreen/datacenters/noaa_tmy_downloads_datacenterslocs/zip/**/*.csv')
    
#     tmy_file_dict = {}
#     for filepath in tmy_data:
#         if not filepath.endswith('-metadata.csv'): 
#             folder_name = os.path.basename(os.path.dirname(filepath))
#             try:
#                 folder_id_int = int(folder_name.split('_')[-1])
#                 tmy_file_dict[folder_id_int] = filepath
#             except ValueError:
#                 continue

#     out_dir = '/discover/nobackup/cmbreen/datacenters/datacenter/tmy_comparison_TX_VA/'
#     os.makedirs(out_dir, exist_ok=True)

#     tx_nldas3 = '/discover/nobackup/cmbreen/datacenters/texas_pure_hourly/tx_Pure_Hourly_Summary_FIXED.nc'
#     va_nldas3 = '/discover/nobackup/cmbreen/datacenters/virginia_pure_hourly/va_Pure_Hourly_Summary_FIXED.nc'

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

#     print(f"Queue populated with {len(tasks)} Datacenters (TX/VA). Starting multiprocessing pool...")

#     all_raw_metrics = []
    
#     # Run the multiprocessing pool
#     with concurrent.futures.ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:
#         futures = [executor.submit(process_datacenter, *task) for task in tasks]
        
#         # Display progress bar and worker logs
#         for future in tqdm(concurrent.futures.as_completed(futures), total=len(tasks), desc="Processing Datacenters"):
#             res = future.result()
            
#             if isinstance(res, tuple) and len(res) == 3:
#                 dc_id, dc_state, raw_metrics_or_error = res
                
#                 # Success
#                 if isinstance(raw_metrics_or_error, list):
#                     tqdm.write(f"Worker completed Datacenter {dc_id} in {dc_state}")
#                     all_raw_metrics.extend(raw_metrics_or_error)
#                 # Failure
#                 else:
#                     tqdm.write(f"ERROR on Datacenter {dc_id} in {dc_state}: {raw_metrics_or_error}")

#     print(f"\nFinished generating individual PDFs in {round(time.time() - start_time, 2)} seconds.")

#     # ---------------------------------------------------------
#     # 4. GENERATE MASTER STATE-LEVEL AVERAGE PDF
#     # ---------------------------------------------------------
#     print("Generating Master State Average PDF...")
#     if all_raw_metrics:
#         metrics_df = pd.DataFrame(all_raw_metrics)
#         # Aggregated table for standard means
#         state_avg = metrics_df.groupby(['state', 'var_key', 'season', 'pct']).mean(numeric_only=True).reset_index()

#         # --- PRE-CALCULATE GLOBAL Y-AXIS LIMITS FOR BAR CHARTS ---
#         # This ensures TX and VA share the exact same scale for each variable
#         y_limits = {}
#         for var_key in TABLE_CONFIGS.keys():
#             var_data = metrics_df[metrics_df['var_key'] == var_key]
#             if not var_data.empty:
#                 # Calculate mean + std for each group to find the highest point of the error bars
#                 grouped = var_data.groupby(['state', 'season', 'pct'])['max_gap'].agg(['mean', 'std']).fillna(0)
#                 upper_bound = (grouped['mean'] + grouped['std']).max()
#                 lower_bound = (grouped['mean'] - grouped['std']).min()
                
#                 # Add 10% padding to the top. Keep bottom at 0 unless there are negative gaps.
#                 y_min = min(0, lower_bound * 1.1 if lower_bound < 0 else 0)
#                 y_max = upper_bound * 1.1 if upper_bound > 0 else 1.0
#                 y_limits[var_key] = (y_min, y_max)

#         master_pdf_path = os.path.join(out_dir, 'Master_State_Averages.pdf')
        
#         with PdfPages(master_pdf_path) as master_pdf:
#             # We process TX first, then VA. Each gets TWO pages in the PDF (1 table grid, 1 bar chart grid).
#             for state in ['TX', 'VA']:
                
#                 if state not in state_avg['state'].unique():
#                     continue

#                 # ==========================================
#                 # PAGE 1: 2x2 GRID OF STATE AVERAGE TABLES
#                 # ==========================================
#                 fig_tbl, axes_tbl = plt.subplots(nrows=2, ncols=2, figsize=(18, 10))
#                 axes_tbl = axes_tbl.flatten()

#                 for i, (var_key, info) in enumerate(TABLE_CONFIGS.items()):
#                     ax = axes_tbl[i]
#                     ax.axis('off')
                    
#                     var_df = state_avg[(state_avg['state'] == state) & (state_avg['var_key'] == var_key)]
#                     if var_df.empty: continue
                    
#                     results = []
#                     for season in SEASON_ORDER:
#                         s_df = var_df[var_df['season'] == season]
#                         for pct in PERCENTILES:
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

#                     ax.set_title(f"{info['name']} (Tables)", fontweight="bold", fontsize=16, pad=10)

#                 plt.suptitle(f"STATE AVERAGE Volatility: NLDAS Extremes vs TMY ({state})", fontsize=20, fontweight='bold', y=1.02)
#                 plt.tight_layout()
#                 master_pdf.savefig(fig_tbl)
#                 plt.close(fig_tbl)

#                 # ==========================================
#                 # PAGE 2: 2x2 GRID OF STATE AVERAGE BAR CHARTS
#                 # ==========================================
#                 fig_bar, axes_bar = plt.subplots(nrows=2, ncols=2, figsize=(18, 10))
#                 axes_bar = axes_bar.flatten()
#                 sns.set_theme(style="whitegrid")

#                 # Get RAW un-aggregated metrics for this state to calculate standard deviations properly
#                 state_raw_df = metrics_df[metrics_df['state'] == state]

#                 for i, (var_key, info) in enumerate(TABLE_CONFIGS.items()):
#                     ax = axes_bar[i]
#                     var_raw_df = state_raw_df[state_raw_df['var_key'] == var_key]

#                     if var_raw_df.empty: 
#                         ax.axis('off')
#                         continue

#                     # Plot grouped bar chart with std dev error bars
#                     sns.barplot(
#                         data=var_raw_df,
#                         x='season',
#                         y='max_gap',
#                         hue='pct',
#                         order=SEASON_ORDER,
#                         palette=BAR_PALETTE,
#                         errorbar='sd',     # Calculates and plots standard deviation bars
#                         capsize=0.1,       # Adds caps to the error bars
#                         ax=ax
#                     )

#                     # Apply the pre-calculated global y-axis limits
#                     if var_key in y_limits:
#                         ax.set_ylim(y_limits[var_key])

#                     ax.set_title(f"{info['name']} (Max Gap)", fontweight="bold", fontsize=16)
#                     ax.set_xlabel("Season", fontweight="bold", fontsize=12)
#                     ax.set_ylabel(f"Max Gap ({info['unit']})", fontweight="bold", fontsize=12)
#                     ax.legend(title="NLDAS Pct", loc="upper left", bbox_to_anchor=(1, 1))
#                     ax.grid(axis='y', linestyle='--', alpha=0.7)

#                 plt.suptitle(f"STATE AVERAGE Max Gap: NLDAS Extremes vs TMY ({state})\n(Bar Heights = Mean, Error Bars = ±1 Std Dev)", fontsize=20, fontweight='bold', y=1.02)
#                 plt.tight_layout()
#                 master_pdf.savefig(fig_bar)
#                 plt.close(fig_bar)

#         print(f"Master PDF successfully saved to: {master_pdf_path}")

#     print("All tasks completed successfully!")

'''

## Analysis 1 

'''

# import os
# import time
# import glob
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

# PLOT_CONFIGS = {
#     'dry_bulb': {'tmy': 'Temperature', 'nldas': 'Tair_C', 'name': 'Dry Bulb Temp', 'unit': '°C'},
#     'wet_bulb': {'tmy': 'Wet_Bulb', 'nldas': 'Twb_C', 'name': 'Wet Bulb Temp', 'unit': '°C'},
#     'rh': {'tmy': 'Relative Humidity', 'nldas': 'RH', 'name': 'Relative Humidity', 'unit': '%'},
#     'enthalpy': {'tmy': 'Enthalpy', 'nldas': 'Enthalpy', 'name': 'Enthalpy', 'unit': 'kJ/kg'}
# }

# P_COLD = [0.4, 1.0, 2.0]
# P_HOT = [98.0, 99.0, 99.6]
# ALL_P = P_COLD + P_HOT

# plt.rc('font', size=16)
# plt.rc('axes', titlesize=16, labelsize=16)
# plt.rc('xtick', labelsize=16)
# plt.rc('ytick', labelsize=16)
# plt.rc('legend', fontsize=14)

# # ---------------------------------------------------------
# # 2. THE WORKER FUNCTION (Runs on individual CPU cores)
# # ---------------------------------------------------------
# def process_datacenter(dc_info, tmy_file, nldas_file, out_dir):
#     """Processes a single datacenter, creates a timeseries + percentile PDF, and returns raw metrics."""
#     try:
#         dc_id = int(dc_info['id'])
#         dc_name = dc_info['name'] if pd.notna(dc_info['name']) else f"DC_{dc_id}"
#         dc_state = dc_info['state_abb']
#         lat, lon = dc_info['lat'], dc_info['lon']

#         # --- 1. TMY PROCESSING ---
#         tmy_df = pd.read_csv(tmy_file, header=2)
        
#         # (No temporal filtering applied to TMY to preserve the full 8760-hour synthetic year)

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

#         # --- 2. NLDAS PROCESSING ---
#         with xr.open_dataset(nldas_file) as nldas_ds:
#             nldas_pt = nldas_ds.sel(lat=lat, lon=lon, method='nearest').compute()
        
#         nldas_df = nldas_pt.to_dataframe().reset_index()
        
#         if isinstance(nldas_df['time'].dtype, pd.DatetimeTZDtype) or hasattr(nldas_df['time'].dt, 'freq'):
#             nldas_df['time'] = nldas_df['time'].dt.tz_localize(None)

#         # TIMEZONE SHIFT: UTC to Local Standard Time
#         # TX is Central Time (UTC-6), VA is Eastern Time (UTC-5)
#         tz_offset = -6 if dc_state == 'TX' else -5 
#         nldas_df['time'] = nldas_df['time'] + pd.Timedelta(hours=tz_offset)

#         # TEMPORAL FILTER: Narrow NLDAS-3 to 2002-2022 
#         # (Applied after timezone shift to ensure boundary hours are strictly correct locally)
#         nldas_df = nldas_df[(nldas_df['time'].dt.year >= 2002) & (nldas_df['time'].dt.year <= 2022)]

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

#         # --- 3. CALCULATE GLOBAL PERCENTILES ---
#         raw_metrics = []
#         tmy_pcts_dict = {}
#         nldas_pcts_dict = {}

#         for var_key, info in PLOT_CONFIGS.items():
#             tmy_col, nldas_col = info['tmy'], info['nldas']
            
#             tmy_pcts_dict[var_key] = {p: np.nanpercentile(tmy_df[tmy_col], p) for p in ALL_P}
#             nldas_pcts_dict[var_key] = {p: np.nanpercentile(nldas_df[nldas_col], p) for p in ALL_P}
            
#             for p in ALL_P:
#                 raw_metrics.append({
#                     'dc_id': dc_id,
#                     'state': dc_state,
#                     'var_key': var_key,
#                     'percentile': p,
#                     'tmy_val': tmy_pcts_dict[var_key][p],
#                     'nldas_val': nldas_pcts_dict[var_key][p]
#                 })

#         # --- 4. CREATE ALIGNED TIMESERIES ---
#         nldas_cols = [cfg['nldas'] for cfg in PLOT_CONFIGS.values()]
#         nldas_mean = nldas_df.groupby('Month_Day_Hour')[nldas_cols].mean()
#         aligned_df = tmy_df.merge(nldas_mean, left_on='Month_Day_Hour', right_index=True, how='left')

#         # --- 5. CREATE INDIVIDUAL PDF ---
#         pdf_path = os.path.join(out_dir, f'DC_Report_{dc_id}.pdf')
        
#         with PdfPages(pdf_path) as pdf:
#             sns.set_theme(style="whitegrid")
#             fig_ts, axes = plt.subplots(4, 1, figsize=(22, 28), sharex=True)
#             x_hours = range(len(aligned_df)) # Will be exactly 8760

#             for i, (var_key, info) in enumerate(PLOT_CONFIGS.items()):
#                 ax = axes[i]
#                 tmy_col = info['tmy']
#                 nldas_col = info['nldas']
#                 title = info['name']
#                 ylabel = f"{info['name']} ({info['unit']})"

#                 if nldas_col in aligned_df.columns:
#                     ax.plot(x_hours, aligned_df[nldas_col], color='gray', linewidth=1, alpha=0.6, label='NLDAS3 Hist. Mean')
#                 if tmy_col in aligned_df.columns:
#                     ax.plot(x_hours, aligned_df[tmy_col], color='black', linewidth=1.2, alpha=0.9, label='TMY (Typical Year)')

#                 hot_colors = {98.0: '#ffb3b3', 99.0: '#ff4d4d', 99.6: '#cc0000'}
#                 cold_colors = {2.0: '#b3d9ff', 1.0: '#4da6ff', 0.4: '#005ce6'}

#                 for p in P_COLD:
#                     ax.axhline(tmy_pcts_dict[var_key][p], color=cold_colors[p], linestyle='-', linewidth=2.5, label=f'TMY {p}th' if p==0.4 else "")
#                     ax.axhline(nldas_pcts_dict[var_key][p], color=cold_colors[p], linestyle='--', linewidth=2.5, label=f'NLDAS {p}th' if p==0.4 else "")
#                 for p in P_HOT:
#                     ax.axhline(tmy_pcts_dict[var_key][p], color=hot_colors[p], linestyle='-', linewidth=2.5, label=f'TMY {p}th' if p==99.6 else "")
#                     ax.axhline(nldas_pcts_dict[var_key][p], color=hot_colors[p], linestyle='--', linewidth=2.5, label=f'NLDAS {p}th' if p==99.6 else "")

#                 ax.set_title(f"{title}", fontweight='bold')
#                 ax.set_ylabel(ylabel)
#                 ax.legend(loc='center left', bbox_to_anchor=(1.01, 0.5), ncol=1, frameon=True)

#             month_starts = aligned_df[(aligned_df['Day'] == 1) & (aligned_df['Hour'] == 0)].index
#             axes[-1].set_xticks(month_starts)
#             axes[-1].set_xticklabels(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'], rotation=0, ha='left')
#             axes[-1].set_xlim(0, 8760)
            
#             plt.suptitle(f'8760-Hour Timeseries w/ Global Thresholds\nTMY (Full) vs NLDAS-3 (2002-2022)\n{dc_name} ({dc_state})', fontweight='bold', y=0.99)
#             plt.tight_layout(rect=[0, 0, 0.88, 0.98])
#             pdf.savefig(fig_ts) 
#             plt.close(fig_ts)

#         return dc_id, dc_state, raw_metrics

#     except Exception as e:
#         return dc_info.get('id', 'Unknown'), dc_info.get('state_abb', 'Unknown'), str(e)


# # ---------------------------------------------------------
# # 3. MAIN EXECUTION BLOCK 
# # ---------------------------------------------------------
# if __name__ == '__main__':
#     start_time = time.time()
#     print("Loading global datasets & Parsing metadata for Distance filter...")

#     datacenter_information = pd.read_csv('/discover/nobackup/cmbreen/datacenters/data/im3_open_source_data_center_atlas_v2026.02.09.csv')
    
#     tmy_data_meta = glob.glob('/discover/nobackup/cmbreen/datacenters/noaa_tmy_downloads_datacenterslocs/zip/**/*-metadata.csv')
#     valid_dc_ids = set()
#     tmy_file_dict = {}

#     for meta_file in tmy_data_meta:
#         try:
#             folder_name = os.path.basename(os.path.dirname(meta_file))
#             dc_id_int = int(folder_name.split('_')[-1])
            
#             csv_candidates = glob.glob(os.path.join(os.path.dirname(meta_file), '*.csv'))
#             tmy_csv = [f for f in csv_candidates if not f.endswith('-metadata.csv')][0]
#             tmy_file_dict[dc_id_int] = tmy_csv

#             df_meta = pd.read_csv(meta_file, header=None)
#             dist_row = df_meta[df_meta[0] == 'Distance to Station (km)']
#             if not dist_row.empty:
#                 distance = float(dist_row.iloc[0][1])
#                 if distance <= 10.0:
#                     valid_dc_ids.add(dc_id_int)
#         except Exception:
#             continue

#     print(f"Distance Filter Applied: Found {len(valid_dc_ids)} Data Centers <= 10km from their station.")

#     out_dir = '/discover/nobackup/cmbreen/datacenters/datacenter/tmy_comparison_TX_VA/'
#     os.makedirs(out_dir, exist_ok=True)

#     tx_nldas3 = '/discover/nobackup/cmbreen/datacenters/texas_pure_hourly/tx_Pure_Hourly_Summary_FIXED.nc'
#     va_nldas3 = '/discover/nobackup/cmbreen/datacenters/virginia_pure_hourly/va_Pure_Hourly_Summary_FIXED.nc'

#     tasks = []
#     for idx, row in datacenter_information.iterrows():
#         dc_id = int(row['id'])
#         state_abb = row['state_abb']
        
#         if dc_id not in valid_dc_ids: continue
#         if dc_id not in tmy_file_dict: continue

#         if state_abb == 'TX': nldas_file = tx_nldas3
#         elif state_abb == 'VA': nldas_file = va_nldas3
#         else: continue 

#         tasks.append((row.to_dict(), tmy_file_dict[dc_id], nldas_file, out_dir))

#     print(f"Queue populated with {len(tasks)} Datacenters. Starting multiprocessing pool...")

#     all_raw_metrics = []
    
#     with concurrent.futures.ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:
#         futures = [executor.submit(process_datacenter, *task) for task in tasks]
        
#         for future in tqdm(concurrent.futures.as_completed(futures), total=len(tasks), desc="Processing Datacenters"):
#             res = future.result()
#             if isinstance(res, tuple) and len(res) == 3:
#                 dc_id, dc_state, raw_metrics_or_error = res
                
#                 if isinstance(raw_metrics_or_error, list):
#                     all_raw_metrics.extend(raw_metrics_or_error)
#                 else:
#                     tqdm.write(f"ERROR on Datacenter {dc_id} in {dc_state}: {raw_metrics_or_error}")

#     print(f"\nFinished generating individual PDFs in {round(time.time() - start_time, 2)} seconds.")

#     # ---------------------------------------------------------
#     # 4. GENERATE MASTER SCATTERPLOT SUMMARY PDF
#     # ---------------------------------------------------------
#     print("Generating Master Scatterplot Summary PDF...")
#     if all_raw_metrics:
#         metrics_df = pd.DataFrame(all_raw_metrics)
#         master_pdf_path = os.path.join(out_dir, 'Master_Scatterplot_Summary.pdf')
        
#         with PdfPages(master_pdf_path) as master_pdf:
#             sns.set_theme(style="whitegrid")
#             plt.rc('font', size=16)
            
#             for var_key, info in PLOT_CONFIGS.items():
#                 var_df = metrics_df[metrics_df['var_key'] == var_key]
#                 if var_df.empty: continue
                
#                 fig, axes = plt.subplots(nrows=2, ncols=3, figsize=(22, 14))
#                 axes = axes.flatten()
                
#                 for idx, p in enumerate(P_COLD + P_HOT):
#                     ax = axes[idx]
#                     data_p = var_df[var_df['percentile'] == p]
                    
#                     if data_p.empty: continue

#                     min_val = min(data_p['nldas_val'].min(), data_p['tmy_val'].min())
#                     max_val = max(data_p['nldas_val'].max(), data_p['tmy_val'].max())
#                     padding = (max_val - min_val) * 0.1
#                     min_val -= padding
#                     max_val += padding

#                     ax.plot([min_val, max_val], [min_val, max_val], 'k--', alpha=0.5, label='y=x (Zero Bias)')
                    
#                     sns.scatterplot(
#                         data=data_p, x='nldas_val', y='tmy_val', 
#                         hue='state', s=120, alpha=0.8, ax=ax
#                     )

#                     ax.set_title(f"{p}th Percentile", fontweight='bold')
#                     ax.set_xlabel(f"NLDAS-3 Percentile ({info['unit']})")
#                     ax.set_ylabel(f"TMY Percentile ({info['unit']})")

#                     if idx == 0:
#                         ax.legend(title="State", loc='upper left')
#                     else:
#                         if ax.get_legend() is not None:
#                             ax.get_legend().remove()

#                 plt.suptitle(f"Global Percentile Bias: TMY (Full) vs NLDAS-3 Historical (2002-2022)\nVariable: {info['name']}", fontweight='bold', fontsize=20, y=1.02)
#                 plt.tight_layout()
#                 master_pdf.savefig(fig)
#                 plt.close(fig)

#         print(f"Master Summary Scatterplots successfully saved to: {master_pdf_path}")
#     print("All tasks completed successfully!")


'''

analysis 1 and 2

'''

# import os
# import time
# import glob
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

# PLOT_CONFIGS = {
#     'dry_bulb': {'tmy': 'Temperature', 'nldas': 'Tair_C', 'name': 'Dry Bulb Temp', 'unit': '°C'},
#     'wet_bulb': {'tmy': 'Wet_Bulb', 'nldas': 'Twb_C', 'name': 'Wet Bulb Temp', 'unit': '°C'},
#     'rh': {'tmy': 'Relative Humidity', 'nldas': 'RH', 'name': 'Relative Humidity', 'unit': '%'},
#     'enthalpy': {'tmy': 'Enthalpy', 'nldas': 'Enthalpy', 'name': 'Enthalpy', 'unit': 'kJ/kg'}
# }

# P_COLD = [0.4, 1.0, 2.0]
# P_HOT = [98.0, 99.0, 99.6]
# ALL_P = P_COLD + P_HOT

# plt.rc('font', size=16)
# plt.rc('axes', titlesize=16, labelsize=16)
# plt.rc('xtick', labelsize=14)
# plt.rc('ytick', labelsize=16)
# plt.rc('legend', fontsize=14)

# # ---------------------------------------------------------
# # 2. THE WORKER FUNCTION
# # ---------------------------------------------------------
# def process_datacenter(dc_info, tmy_file, nldas_file, out_dir):
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

#         # --- 2. NLDAS PROCESSING ---
#         with xr.open_dataset(nldas_file) as nldas_ds:
#             nldas_pt = nldas_ds.sel(lat=lat, lon=lon, method='nearest').compute()
        
#         nldas_df = nldas_pt.to_dataframe().reset_index()
#         if isinstance(nldas_df['time'].dtype, pd.DatetimeTZDtype) or hasattr(nldas_df['time'].dt, 'freq'):
#             nldas_df['time'] = nldas_df['time'].dt.tz_localize(None)

#         tz_offset = -6 if dc_state == 'TX' else -5 
#         nldas_df['time'] = nldas_df['time'] + pd.Timedelta(hours=tz_offset)

#         # 2002-2022 Filter for NLDAS
#         nldas_df = nldas_df[(nldas_df['time'].dt.year >= 2002) & (nldas_df['time'].dt.year <= 2022)]
#         nldas_df = nldas_df[~((nldas_df['time'].dt.month == 2) & (nldas_df['time'].dt.day == 29))]
#         nldas_df['Month_Day_Hour'] = (nldas_df['time'].dt.month.astype(str) + '_' + 
#                                       nldas_df['time'].dt.day.astype(str) + '_' + 
#                                       nldas_df['time'].dt.hour.astype(str))

#         if 'RH' not in nldas_df.columns:
#             temp_nldas = nldas_df['Tair_C'].values * units.degC
#             press_nldas = nldas_df.get('PSurf', np.full(len(nldas_df), 101325)).values * units.Pa
#             mixing_ratio_nldas = nldas_df['Qair'].values * units('kg/kg')
#             rh_nldas = mpcalc.relative_humidity_from_specific_humidity(press_nldas, temp_nldas, mixing_ratio_nldas) * 100 * units.percent
#             nldas_df['RH'] = rh_nldas.m
#             dewpt_nldas = mpcalc.dewpoint_from_relative_humidity(temp_nldas, rh_nldas)
#             nldas_df['Twb_C'] = mpcalc.wet_bulb_temperature(press_nldas, temp_nldas, dewpt_nldas).m
#             nldas_df['Enthalpy'] = 1.006 * temp_nldas.m + mixing_ratio_nldas.m * (2501 + 1.86 * temp_nldas.m)

#         # --- 3. METRICS EXTRACTION (Used for both Analysis 1 & 2) ---
#         raw_metrics = []
#         tmy_pcts = {vk: {p: np.nanpercentile(tmy_df[info['tmy']], p) for p in ALL_P} for vk, info in PLOT_CONFIGS.items()}
#         nldas_pcts = {vk: {p: np.nanpercentile(nldas_df[info['nldas']], p) for p in ALL_P} for vk, info in PLOT_CONFIGS.items()}

#         for var_key, info in PLOT_CONFIGS.items():
#             for p in ALL_P:
#                 threshold = nldas_pcts[var_key][p]
#                 tmy_col, nldas_col = info['tmy'], info['nldas']
                
#                 # Exceedance hours calculation
#                 if p >= 50:
#                     tmy_exceed = (tmy_df[tmy_col] > threshold).sum()
#                     nldas_yr_counts = nldas_df.groupby(nldas_df['time'].dt.year)[nldas_col].apply(lambda x: (x > threshold).sum())
#                 else:
#                     tmy_exceed = (tmy_df[tmy_col] < threshold).sum()
#                     nldas_yr_counts = nldas_df.groupby(nldas_df['time'].dt.year)[nldas_col].apply(lambda x: (x < threshold).sum())
                
#                 raw_metrics.append({
#                     'dc_id': dc_id,
#                     'dc_name': dc_name,
#                     'state': dc_state,
#                     'var_key': var_key,
#                     'percentile': p,
#                     'tmy_val': tmy_pcts[var_key][p],
#                     'nldas_val': threshold,
#                     'tmy_count': tmy_exceed,
#                     'nldas_med': nldas_yr_counts.median(),
#                     'nldas_mean': nldas_yr_counts.mean(),
#                     'nldas_min': nldas_yr_counts.min(),
#                     'nldas_max': nldas_yr_counts.max()
#                 })

#         return dc_id, dc_state, raw_metrics

#     except Exception as e:
#         return dc_info.get('id', 'Unknown'), dc_info.get('state_abb', 'Unknown'), str(e)


# # ---------------------------------------------------------
# # 3. MAIN EXECUTION BLOCK 
# # ---------------------------------------------------------
# if __name__ == '__main__':
#     start_time = time.time()
#     print("Loading datasets & Parsing metadata...")

#     datacenter_information = pd.read_csv('/discover/nobackup/cmbreen/datacenters/data/im3_open_source_data_center_atlas_v2026.02.09.csv')
#     tmy_data_meta = glob.glob('/discover/nobackup/cmbreen/datacenters/noaa_tmy_downloads_datacenterslocs/zip/**/*-metadata.csv')
    
#     valid_dc_ids = set()
#     tmy_file_dict = {}

#     for meta_file in tmy_data_meta:
#         try:
#             folder_name = os.path.basename(os.path.dirname(meta_file))
#             dc_id_int = int(folder_name.split('_')[-1])
            
#             csv_candidates = glob.glob(os.path.join(os.path.dirname(meta_file), '*.csv'))
#             tmy_csv = [f for f in csv_candidates if not f.endswith('-metadata.csv')][0]
#             tmy_file_dict[dc_id_int] = tmy_csv

#             df_meta = pd.read_csv(meta_file, header=None)
#             dist_row = df_meta[df_meta[0] == 'Distance to Station (km)']
#             if not dist_row.empty:
#                 distance = float(dist_row.iloc[0][1])
#                 if distance <= 10.0:
#                     valid_dc_ids.add(dc_id_int)
#         except Exception:
#             continue

#     out_dir = '/discover/nobackup/cmbreen/datacenters/datacenter/tmy_comparison_TX_VA/'
#     os.makedirs(out_dir, exist_ok=True)

#     tx_nldas3 = '/discover/nobackup/cmbreen/datacenters/texas_pure_hourly/tx_Pure_Hourly_Summary_FIXED.nc'
#     va_nldas3 = '/discover/nobackup/cmbreen/datacenters/virginia_pure_hourly/va_Pure_Hourly_Summary_FIXED.nc'

#     tasks = []
#     for idx, row in datacenter_information.iterrows():
#         dc_id = int(row['id'])
#         if dc_id not in valid_dc_ids or dc_id not in tmy_file_dict: continue

#         state_abb = row['state_abb']
#         nldas_file = tx_nldas3 if state_abb == 'TX' else va_nldas3 if state_abb == 'VA' else None
#         if nldas_file: tasks.append((row.to_dict(), tmy_file_dict[dc_id], nldas_file, out_dir))

#     all_raw_metrics = []
#     with concurrent.futures.ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:
#         futures = [executor.submit(process_datacenter, *task) for task in tasks]
#         for future in tqdm(concurrent.futures.as_completed(futures), total=len(tasks), desc="Processing DCs"):
#             res = future.result()
#             if isinstance(res, tuple) and len(res) == 3:
#                 if isinstance(res[2], list): all_raw_metrics.extend(res[2])

#     if not all_raw_metrics:
#         print("No valid data processed. Exiting.")
#         exit()

#     metrics_df = pd.DataFrame(all_raw_metrics)

#     # ---------------------------------------------------------
#     # ANALYSIS 2: Specific Table & Range Plots
#     # ---------------------------------------------------------
#     print("\n--- Generating Analysis 2 Outputs ---")
    
#     # 2.1: CREATE THE EXACT TABLE FORMAT
#     table_df = metrics_df.copy()
#     # Create the text string for the Range column
#     table_df['NLDAS Range'] = table_df.apply(lambda row: f"{int(row['nldas_min'])} - {int(row['nldas_max'])}", axis=1)
    
#     # Rename and select columns to perfectly match PI request
#     table_export = table_df[['dc_id', 'state', 'var_key', 'percentile', 'tmy_count', 'nldas_med', 'nldas_mean', 'NLDAS Range']]
#     table_export.columns = ['Datacenter', 'State', 'Variable', 'Percentile', 'TMY Count', 'NLDAS Med', 'NLDAS Mean', 'NLDAS Range']
    
#     analysis2_csv = os.path.join(out_dir, 'Analysis2_Exceedance_Table.csv')
#     table_export.to_csv(analysis2_csv, index=False)
#     print(f"Analysis 2 Table saved to: {analysis2_csv}")

#     # 2.2: CREATE THE RANGE PLOT (VA on Left, TX on Right)
#     analysis2_pdf = os.path.join(out_dir, 'Analysis2_Exceedance_Range_Plots.pdf')
    
#     with PdfPages(analysis2_pdf) as pdf:
#         for var_key, info in PLOT_CONFIGS.items():
#             var_df = metrics_df[metrics_df['var_key'] == var_key].copy()
#             if var_df.empty: continue
            
#             # Explicitly force VA to be 0 and TX to be 1 so VA is plotted on the left
#             var_df['sort_order'] = var_df['state'].map({'VA': 0, 'TX': 1})
#             var_df = var_df.sort_values(by=['sort_order', 'dc_id'])
            
#             fig, axes = plt.subplots(nrows=2, ncols=3, figsize=(24, 16))
#             axes = axes.flatten()
            
#             for idx, p in enumerate(P_COLD + P_HOT):
#                 ax = axes[idx]
#                 data_p = var_df[var_df['percentile'] == p].reset_index(drop=True)
#                 if data_p.empty: continue

#                 x_positions = np.arange(len(data_p))
                
#                 # Draw the vertical range line (min to max)
#                 ax.vlines(x=x_positions, ymin=data_p['nldas_min'], ymax=data_p['nldas_max'], 
#                           color='gray', alpha=0.5, linewidth=4, label='NLDAS Range (Min-Max)', zorder=1)
                
#                 # Draw Markers
#                 ax.scatter(x_positions, data_p['nldas_mean'], color='blue', marker='s', s=80, label='NLDAS Mean', zorder=2)
#                 ax.scatter(x_positions, data_p['nldas_med'], color='green', marker='^', s=80, label='NLDAS Median', zorder=3)
#                 ax.scatter(x_positions, data_p['tmy_count'], color='red', marker='*', s=300, edgecolor='black', linewidth=0.5, label='TMY Count', zorder=4)

#                 # Add a vertical dashed line separating VA and TX
#                 va_count = (data_p['state'] == 'VA').sum()
#                 if 0 < va_count < len(data_p):
#                     ax.axvline(x=va_count - 0.5, color='black', linestyle='--', alpha=0.6, zorder=0)
#                     # Add State Text Annotations
#                     ax.text(va_count/2 - 0.5, ax.get_ylim()[1]*0.95, 'Virginia (VA)', ha='center', fontweight='bold', alpha=0.7)
#                     ax.text((va_count + len(data_p))/2 - 0.5, ax.get_ylim()[1]*0.95, 'Texas (TX)', ha='center', fontweight='bold', alpha=0.7)

#                 ax.set_title(f"{p}th Percentile Exceedances", fontweight='bold')
#                 ax.set_ylabel("Total Hours")
                
#                 # Simplify X-axis to just DC IDs rotated
#                 ax.set_xticks(x_positions)
#                 ax.set_xticklabels(data_p['dc_id'].astype(str), rotation=90, fontsize=10)
                
#                 if idx == 0:
#                     ax.legend(loc='upper right', bbox_to_anchor=(1, 1), fancybox=True, shadow=True)

#             plt.suptitle(f"ANALYSIS 2: Exceedance Hours Distribution per Datacenter\nVariable: {info['name']}", fontweight='bold', fontsize=22, y=1.03)
#             plt.tight_layout()
#             pdf.savefig(fig)
#             plt.close(fig)

#     print(f"Analysis 2 Range Plots saved to: {analysis2_pdf}")
#     print("\nAll tasks completed successfully!")


'''

analysis 1 and 2
should actually output both now 

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

plt.rc('font', size=16)
plt.rc('axes', titlesize=16, labelsize=16)
plt.rc('xtick', labelsize=14)
plt.rc('ytick', labelsize=16)
plt.rc('legend', fontsize=14)

# ---------------------------------------------------------
# 2. THE WORKER FUNCTION (Runs on individual CPU cores)
# ---------------------------------------------------------
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

        # Drop leap day to force 8760 hours and create alignment key
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

        # Apply temporal bounds to NLDAS and drop leap days
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

        # --- 3. METRICS EXTRACTION & PERCENTILES ---
        raw_metrics = []
        tmy_pcts = {vk: {p: np.nanpercentile(tmy_df[info['tmy']], p) for p in ALL_P} for vk, info in PLOT_CONFIGS.items()}
        nldas_pcts = {vk: {p: np.nanpercentile(nldas_df[info['nldas']], p) for p in ALL_P} for vk, info in PLOT_CONFIGS.items()}

        for var_key, info in PLOT_CONFIGS.items():
            for p in ALL_P:
                threshold = nldas_pcts[var_key][p]
                tmy_col, nldas_col = info['tmy'], info['nldas']
                
                # Exceedance calculation
                if p >= 50:
                    tmy_exceed = (tmy_df[tmy_col] > threshold).sum()
                    nldas_yr_counts = nldas_df.groupby(nldas_df['time'].dt.year)[nldas_col].apply(lambda x: (x > threshold).sum())
                else:
                    tmy_exceed = (tmy_df[tmy_col] < threshold).sum()
                    nldas_yr_counts = nldas_df.groupby(nldas_df['time'].dt.year)[nldas_col].apply(lambda x: (x < threshold).sum())
                
                raw_metrics.append({
                    'dc_id': dc_id,
                    'dc_name': dc_name,
                    'state': dc_state,
                    'var_key': var_key,
                    'percentile': p,
                    'tmy_val': tmy_pcts[var_key][p],
                    'nldas_val': threshold,
                    'tmy_count': tmy_exceed,
                    'nldas_med': nldas_yr_counts.median(),
                    'nldas_mean': nldas_yr_counts.mean(),
                    'nldas_min': nldas_yr_counts.min(),
                    'nldas_max': nldas_yr_counts.max()
                })

        # --- 4. ALIGN 8760 TIMESERIES (TMY + NLDAS target years) ---
        aligned_df = tmy_df.copy()
        nldas_cols = [cfg['nldas'] for cfg in PLOT_CONFIGS.values()]
        
        for yr in PLOT_YEARS:
            yr_data = nldas_df[nldas_df['time'].dt.year == yr][['Month_Day_Hour'] + nldas_cols].set_index('Month_Day_Hour')
            yr_data.columns = [f"{col}_{yr}" for col in yr_data.columns]
            aligned_df = aligned_df.merge(yr_data, on='Month_Day_Hour', how='left')

        # --- 5. CREATE INDIVIDUAL PDF (Analysis 1 timeseries style) ---
        pdf_path = os.path.join(out_dir, f'DC_Report_{dc_id}.pdf')
        
        with PdfPages(pdf_path) as pdf:
            sns.set_theme(style="whitegrid")
            fig_ts, axes = plt.subplots(4, 1, figsize=(22, 28), sharex=True)
            x_hours = range(len(aligned_df)) # 8760 hours

            for i, (var_key, info) in enumerate(PLOT_CONFIGS.items()):
                ax = axes[i]
                tmy_col = info['tmy']
                nldas_col = info['nldas']
                
                # Plot Specific NLDAS Years
                for yr in PLOT_YEARS:
                    yr_col = f"{nldas_col}_{yr}"
                    if yr_col in aligned_df.columns:
                        ax.plot(x_hours, aligned_df[yr_col], color=YEAR_COLORS[yr], linewidth=1.2, alpha=0.7, label=f'NLDAS {yr}')
                
                # Plot TMY
                if tmy_col in aligned_df.columns:
                    ax.plot(x_hours, aligned_df[tmy_col], color='black', linewidth=1.8, alpha=1.0, label='TMY (Typical Year)')

                # Plot Threshold Lines
                hot_colors = {98.0: '#ffb3b3', 99.0: '#ff4d4d', 99.6: '#cc0000'}
                cold_colors = {2.0: '#b3d9ff', 1.0: '#4da6ff', 0.4: '#005ce6'}

                for p in P_COLD:
                    ax.axhline(tmy_pcts[var_key][p], color=cold_colors[p], linestyle='-', linewidth=2.5, label=f'TMY {p}th' if p==0.4 else "")
                    ax.axhline(nldas_pcts[var_key][p], color=cold_colors[p], linestyle='--', linewidth=2.5, label=f'NLDAS {p}th' if p==0.4 else "")
                for p in P_HOT:
                    ax.axhline(tmy_pcts[var_key][p], color=hot_colors[p], linestyle='-', linewidth=2.5, label=f'TMY {p}th' if p==99.6 else "")
                    ax.axhline(nldas_pcts[var_key][p], color=hot_colors[p], linestyle='--', linewidth=2.5, label=f'NLDAS {p}th' if p==99.6 else "")

                ax.set_title(f"{info['name']}", fontweight='bold')
                ax.set_ylabel(f"{info['name']} ({info['unit']})")
                ax.legend(loc='center left', bbox_to_anchor=(1.01, 0.5), ncol=1, frameon=True)

            # Format X-axis
            month_starts = aligned_df[(aligned_df['Day'] == 1) & (aligned_df['Hour'] == 0)].index
            axes[-1].set_xticks(month_starts)
            axes[-1].set_xticklabels(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'], rotation=0, ha='left')
            axes[-1].set_xlim(0, 8760)
            
            plt.suptitle(f'8760-Hour Timeseries w/ Global Thresholds\nTMY vs NLDAS-3 Target Years\n{dc_name} ({dc_state})', fontweight='bold', y=0.99)
            plt.tight_layout(rect=[0, 0, 0.88, 0.98])
            pdf.savefig(fig_ts) 
            plt.close(fig_ts)

        return dc_id, dc_state, raw_metrics

    except Exception as e:
        return dc_info.get('id', 'Unknown'), dc_info.get('state_abb', 'Unknown'), str(e)


# ---------------------------------------------------------
# 3. MAIN EXECUTION BLOCK 
# ---------------------------------------------------------
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
                if distance <= 10.0:
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

    all_raw_metrics = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:
        futures = [executor.submit(process_datacenter, *task) for task in tasks]
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(tasks), desc="Processing DCs"):
            res = future.result()
            if isinstance(res, tuple) and len(res) == 3:
                if isinstance(res[2], list): all_raw_metrics.extend(res[2])

    if not all_raw_metrics:
        print("No valid data processed. Exiting.")
        exit()

    metrics_df = pd.DataFrame(all_raw_metrics)

    # # ---------------------------------------------------------
    # # ANALYSIS 1: Master Summary Threshold Scatterplots
    # # ---------------------------------------------------------
    # print("\n--- Generating Analysis 1 Outputs ---")
    # master_pdf_path = os.path.join(out_dir, 'Analysis1_summary_threshold.pdf')
        
    # with PdfPages(master_pdf_path) as master_pdf:
    #     sns.set_theme(style="whitegrid")
        
    #     for var_key, info in PLOT_CONFIGS.items():
    #         var_df = metrics_df[metrics_df['var_key'] == var_key]
    #         if var_df.empty: continue
            
    #         fig, axes = plt.subplots(nrows=2, ncols=3, figsize=(22, 14))
    #         axes = axes.flatten()
            
    #         for idx, p in enumerate(P_COLD + P_HOT):
    #             ax = axes[idx]
    #             data_p = var_df[var_df['percentile'] == p]
    #             if data_p.empty: continue

    #             min_val = min(data_p['nldas_val'].min(), data_p['tmy_val'].min())
    #             max_val = max(data_p['nldas_val'].max(), data_p['tmy_val'].max())
    #             padding = (max_val - min_val) * 0.1
    #             min_val -= padding
    #             max_val += padding

    #             ax.plot([min_val, max_val], [min_val, max_val], 'k--', alpha=0.5, label='y=x (Zero Bias)')
                
    #             sns.scatterplot(
    #                 data=data_p, x='nldas_val', y='tmy_val', 
    #                 hue='state', s=120, alpha=0.8, ax=ax
    #             )

    #             ax.set_title(f"{p}th Percentile", fontweight='bold')
    #             ax.set_xlabel(f"NLDAS-3 Percentile ({info['unit']})")
    #             ax.set_ylabel(f"TMY Percentile ({info['unit']})")

    #             if idx == 0:
    #                 ax.legend(title="State", loc='upper left')
    #             else:
    #                 if ax.get_legend() is not None:
    #                     ax.get_legend().remove()

    #         plt.suptitle(f"Global Percentile Bias: TMY vs NLDAS-3 Historical\nVariable: {info['name']}", fontweight='bold', fontsize=20, y=1.02)
    #         plt.tight_layout()
    #         master_pdf.savefig(fig)
    #         plt.close(fig)

    # print(f"Analysis 1 Threshold Scatterplots saved to: {master_pdf_path}")

    # ---------------------------------------------------------
    # ANALYSIS 1: Master Summary Threshold Scatterplots (Poster Ready)
    # ---------------------------------------------------------
    print("\n--- Generating Analysis 1 Outputs ---")
    master_pdf_path = os.path.join(out_dir, 'Analysis1_summary_threshold.pdf')
        
    with PdfPages(master_pdf_path) as master_pdf:
        
        # Enforce Poster-Size Fonts globally for this section
        sns.set_theme(style="whitegrid")
        plt.rc('font', size=16)
        plt.rc('axes', titlesize=20, labelsize=18)
        plt.rc('xtick', labelsize=16)
        plt.rc('ytick', labelsize=16)
        plt.rc('legend', fontsize=16, title_fontsize=16)
        
        # Custom color map to color-code the thresholds (cold=blues, hot=reds)
        pct_colors = {
            '0.4th': '#005ce6', '1.0th': '#4da6ff', '2.0th': '#b3d9ff',
            '98.0th': '#ffb3b3', '99.0th': '#ff4d4d', '99.6th': '#cc0000'
        }

        for var_key, info in PLOT_CONFIGS.items():
            var_df = metrics_df[metrics_df['var_key'] == var_key].copy()
            if var_df.empty: continue
            
            # Convert percentile to string for categorical coloring in the legend
            var_df['Percentile'] = var_df['percentile'].astype(str) + 'th'
            
            # Create a single large, high-resolution figure per variable
            fig, ax = plt.subplots(figsize=(12, 10))
            
            # Calculate global min and max to draw a perfect 1:1 line across all data
            min_val = min(var_df['nldas_val'].min(), var_df['tmy_val'].min())
            max_val = max(var_df['nldas_val'].max(), var_df['tmy_val'].max())
            padding = (max_val - min_val) * 0.05
            min_val -= padding
            max_val += padding

            # Plot 1:1 Line
            ax.plot([min_val, max_val], [min_val, max_val], 'k--', alpha=0.7, linewidth=2.5, label='1:1 Line (Zero Bias)')
            
            # Plot the scatter points
            sns.scatterplot(
                data=var_df, 
                x='nldas_val', 
                y='tmy_val', 
                hue='Percentile', 
                style='state',      # Uses different shapes for TX vs VA
                palette=pct_colors,
                s=300,              # Very large dots for poster visibility
                alpha=0.85, 
                ax=ax
            )

            # Poster-ready labels
            ax.set_title(f"Threshold Comparison: NLDAS-3 vs TMY\nVariable: {info['name']}", fontweight='bold', pad=20)
            ax.set_xlabel(f"NLDAS-3 Threshold ({info['unit']})", fontweight='bold')
            ax.set_ylabel(f"TMY Threshold ({info['unit']})", fontweight='bold')

            # Format the legend (move it slightly outside the plot so it doesn't cover data)
            ax.legend(loc='center left', bbox_to_anchor=(1.02, 0.5), markerscale=1.5, frameon=True, shadow=True)

            # Adjust layout to fit the external legend
            plt.tight_layout()
            master_pdf.savefig(fig)
            plt.close(fig)

    print(f"Analysis 1 Threshold Scatterplots saved to: {master_pdf_path}")

    # # ---------------------------------------------------------
    # # ANALYSIS 2: Specific Table & Range Plots
    # # ---------------------------------------------------------
    # print("\n--- Generating Analysis 2 Outputs ---")
    
    # # 2.1: CREATE THE EXACT TABLE FORMAT
    # table_df = metrics_df.copy()
    # table_df['NLDAS Range'] = table_df.apply(lambda row: f"{int(row['nldas_min'])} - {int(row['nldas_max'])}", axis=1)
    
    # table_export = table_df[['dc_id', 'state', 'var_key', 'percentile', 'tmy_count', 'nldas_med', 'nldas_mean', 'NLDAS Range']]
    # table_export.columns = ['Datacenter', 'State', 'Variable', 'Percentile', 'TMY Count', 'NLDAS Med', 'NLDAS Mean', 'NLDAS Range']
    
    # analysis2_csv = os.path.join(out_dir, 'Analysis2_Exceedance_Table.csv')
    # table_export.to_csv(analysis2_csv, index=False)
    # print(f"Analysis 2 Table saved to: {analysis2_csv}")

    # # 2.2: CREATE THE RANGE PLOT (VA on Left, TX on Right)
    # analysis2_pdf = os.path.join(out_dir, 'Analysis2_Exceedance_Range_Plots.pdf')
    
    # with PdfPages(analysis2_pdf) as pdf:
    #     for var_key, info in PLOT_CONFIGS.items():
    #         var_df = metrics_df[metrics_df['var_key'] == var_key].copy()
    #         if var_df.empty: continue
            
    #         var_df['sort_order'] = var_df['state'].map({'VA': 0, 'TX': 1})
    #         var_df = var_df.sort_values(by=['sort_order', 'dc_id'])
            
    #         fig, axes = plt.subplots(nrows=2, ncols=3, figsize=(24, 16))
    #         axes = axes.flatten()
            
    #         for idx, p in enumerate(P_COLD + P_HOT):
    #             ax = axes[idx]
    #             data_p = var_df[var_df['percentile'] == p].reset_index(drop=True)
    #             if data_p.empty: continue

    #             x_positions = np.arange(len(data_p))
                
    #             ax.vlines(x=x_positions, ymin=data_p['nldas_min'], ymax=data_p['nldas_max'], 
    #                       color='gray', alpha=0.5, linewidth=4, label='NLDAS Range (Min-Max)', zorder=1)
                
    #             ax.scatter(x_positions, data_p['nldas_mean'], color='blue', marker='s', s=80, label='NLDAS Mean', zorder=2)
    #             ax.scatter(x_positions, data_p['nldas_med'], color='green', marker='^', s=80, label='NLDAS Median', zorder=3)
    #             ax.scatter(x_positions, data_p['tmy_count'], color='red', marker='*', s=300, edgecolor='black', linewidth=0.5, label='TMY Count', zorder=4)

    #             va_count = (data_p['state'] == 'VA').sum()
    #             if 0 < va_count < len(data_p):
    #                 ax.axvline(x=va_count - 0.5, color='black', linestyle='--', alpha=0.6, zorder=0)
    #                 ax.text(va_count/2 - 0.5, ax.get_ylim()[1]*0.95, 'Virginia (VA)', ha='center', fontweight='bold', alpha=0.7)
    #                 ax.text((va_count + len(data_p))/2 - 0.5, ax.get_ylim()[1]*0.95, 'Texas (TX)', ha='center', fontweight='bold', alpha=0.7)

    #             ax.set_title(f"{p}th Percentile Exceedances", fontweight='bold')
    #             ax.set_ylabel("Total Hours")
                
    #             ax.set_xticks(x_positions)
    #             ax.set_xticklabels(data_p['dc_id'].astype(str), rotation=90, fontsize=10)
                
    #             if idx == 0:
    #                 ax.legend(loc='upper right', bbox_to_anchor=(1, 1), fancybox=True, shadow=True)

    #         plt.suptitle(f"ANALYSIS 2: Exceedance Hours Distribution per Datacenter\nVariable: {info['name']}", fontweight='bold', fontsize=22, y=1.03)
    #         plt.tight_layout()
    #         pdf.savefig(fig)
    #         plt.close(fig)

        # ---------------------------------------------------------
    # ANALYSIS 2: Specific Table & Range Plots (Poster Ready)
    # ---------------------------------------------------------
    print("\n--- Generating Analysis 2 Outputs ---")
    
    # =========================================================
    # 2.1: CREATE THE EXACT TABLE FORMAT (ALL DATACENTERS)
    # =========================================================
    table_df = metrics_df.copy()
    table_df['NLDAS Range'] = table_df.apply(lambda row: f"{int(row['nldas_min'])} - {int(row['nldas_max'])}", axis=1)
    
    table_export = table_df[['dc_id', 'state', 'var_key', 'percentile', 'tmy_count', 'nldas_med', 'nldas_mean', 'NLDAS Range']]
    table_export.columns = ['Datacenter', 'State', 'Variable', 'Percentile', 'TMY Count', 'NLDAS Med', 'NLDAS Mean', 'NLDAS Range']
    
    analysis2_csv = os.path.join(out_dir, 'Analysis2_Exceedance_Table.csv')
    table_export.to_csv(analysis2_csv, index=False)
    print(f"Analysis 2 Table (All Data) saved to: {analysis2_csv}")

    # =========================================================
    # SUBSAMPLE LOGIC (Seed 42: 10 VA, 10 TX)
    # =========================================================
    np.random.seed(42)
    va_dcs = metrics_df[metrics_df['state'] == 'VA']['dc_id'].unique()
    tx_dcs = metrics_df[metrics_df['state'] == 'TX']['dc_id'].unique()
    
    va_sample = np.random.choice(va_dcs, min(10, len(va_dcs)), replace=False)
    tx_sample = np.random.choice(tx_dcs, min(10, len(tx_dcs)), replace=False)
    sampled_dcs = np.concatenate([va_sample, tx_sample])
    
    # Create a filtered dataframe just for the range plots
    range_plot_df = metrics_df[metrics_df['dc_id'].isin(sampled_dcs)].copy()

    # =========================================================
    # 2.2: CREATE THE RANGE PLOT (Subsampled 20 DCs)
    # =========================================================
    analysis2_pdf = os.path.join(out_dir, 'Analysis2_Exceedance_Range_Plots.pdf')
    
    with PdfPages(analysis2_pdf) as pdf:
        sns.set_theme(style="whitegrid")
        plt.rc('font', size=16)
        plt.rc('axes', titlesize=20, labelsize=18)
        plt.rc('xtick', labelsize=16) # Larger now that it's less crowded
        plt.rc('ytick', labelsize=16)
        plt.rc('legend', fontsize=16)

        for var_key, info in PLOT_CONFIGS.items():
            var_df = range_plot_df[range_plot_df['var_key'] == var_key].copy()
            if var_df.empty: continue
            
            var_df['sort_order'] = var_df['state'].map({'VA': 0, 'TX': 1})
            var_df = var_df.sort_values(by=['sort_order', 'dc_id'])
            
            fig, axes = plt.subplots(nrows=2, ncols=3, figsize=(28, 18))
            axes = axes.flatten()
            
            for idx, p in enumerate(P_COLD + P_HOT):
                ax = axes[idx]
                data_p = var_df[var_df['percentile'] == p].reset_index(drop=True)
                if data_p.empty: continue

                x_positions = np.arange(len(data_p))
                
                if p >= 50:
                    expected_hours = 8760 * ((100 - p) / 100)
                else:
                    expected_hours = 8760 * (p / 100)
                
                # Plot 1: The Historical Range (Thick Gray Bars)
                ax.vlines(x=x_positions, ymin=data_p['nldas_min'], ymax=data_p['nldas_max'], 
                          color='gray', alpha=0.5, linewidth=10, label='NLDAS Historical Range', zorder=1)
                
                # Plot 2: NLDAS Mean
                ax.scatter(x_positions, data_p['nldas_mean'], color='dodgerblue', marker='s', s=150, 
                           edgecolor='black', label='NLDAS Mean', zorder=3)
                
                # Plot 3: TMY Count
                ax.scatter(x_positions, data_p['tmy_count'], color='crimson', marker='*', s=600, 
                           edgecolor='black', linewidth=1, label='TMY Actual Count', zorder=4)

                # Plot 4: Theoretical Expectation
                ax.axhline(expected_hours, color='black', linestyle='--', linewidth=2.5, 
                           label=f'Theoretical Exp. ({expected_hours:.1f} hrs)', zorder=2)

                # State Dividers
                va_count = (data_p['state'] == 'VA').sum()
                if 0 < va_count < len(data_p):
                    ax.axvline(x=va_count - 0.5, color='black', linestyle='-', linewidth=2, alpha=0.8, zorder=0)
                    ax.text(va_count/2 - 0.5, ax.get_ylim()[1]*0.95, 'Virginia (VA)', ha='center', fontweight='bold', fontsize=18, alpha=0.8)
                    ax.text((va_count + len(data_p))/2 - 0.5, ax.get_ylim()[1]*0.95, 'Texas (TX)', ha='center', fontweight='bold', fontsize=18, alpha=0.8)

                ax.set_title(f"{p}th Percentile Exceedances", fontweight='bold', pad=15)
                ax.set_ylabel("Total Hours / Year", fontweight='bold')
                
                # Setup cleaner X-ticks (angled)
                ax.set_xticks(x_positions)
                ax.set_xticklabels(data_p['dc_id'].astype(str), rotation=45, ha='right')
                
                if idx == 0:
                    ax.legend(loc='upper left', bbox_to_anchor=(0.02, 0.95), framealpha=0.9, shadow=True)

            plt.suptitle(f"Expected vs. Actual Exceedance Hours (Subsample: 10 VA, 10 TX)\nVariable: {info['name']}", fontweight='bold', fontsize=26, y=1.03)
            plt.tight_layout()
            pdf.savefig(fig, bbox_inches='tight')
            plt.close(fig)

    print(f"Analysis 2 Range Plots saved to: {analysis2_pdf}")

   # =========================================================
    # 2.3: NEW SUMMARY PLOT (Violin Plot of Differences)
    # USE ALL DATA
    # =========================================================
    analysis2_summary_pdf = os.path.join(out_dir, 'Analysis2_Summary_Violin.pdf')
    
    with PdfPages(analysis2_summary_pdf) as pdf:
        sns.set_theme(style="whitegrid")
        plt.rc('font', size=16)
        plt.rc('axes', titlesize=22, labelsize=18)
        plt.rc('xtick', labelsize=16)
        plt.rc('ytick', labelsize=16)
        plt.rc('legend', fontsize=16)
        
        for var_key, info in PLOT_CONFIGS.items():
            var_df = metrics_df[metrics_df['var_key'] == var_key].copy()
            if var_df.empty: continue
            
            # Calculate the difference (TMY - NLDAS Mean)
            # Positive = TMY overestimates hours
            # Negative = TMY underestimates hours
            var_df['Hour_Difference'] = var_df['tmy_count'] - var_df['nldas_mean']
            var_df['Percentile_Label'] = var_df['percentile'].astype(str) + 'th'
            
            # Force the correct order on the X-axis
            pct_order = [f"{p}th" for p in (P_COLD + P_HOT)]
            
            fig, ax = plt.subplots(figsize=(16, 10))
            
            # Split Violin Plot
            sns.violinplot(
                data=var_df, 
                x='Percentile_Label', 
                y='Hour_Difference', 
                hue='state', 
                split=True,           # Puts VA on the left, TX on the right of each violin!
                inner="quartile",     # Draws dashed lines inside for the quartiles
                palette={'VA': '#4da6ff', 'TX': '#ff4d4d'}, 
                order=pct_order,
                linewidth=2,
                ax=ax
            )
            
            # Draw the Perfect Agreement Line (Y = 0)
            ax.axhline(0, color='black', linestyle='--', linewidth=3, zorder=0)
            
            # Add text annotations for Over/Under estimation context
            y_max = ax.get_ylim()[1]
            y_min = ax.get_ylim()[0]
            ax.text(0, y_max * 0.9, 'TMY Overestimates Hours', color='gray', fontweight='bold', fontsize=16, ha='left')
            ax.text(0, y_min * 0.9, 'TMY Underestimates Hours', color='gray', fontweight='bold', fontsize=16, ha='left')

            # Formatting
            ax.set_title(f"Bias Spread: Difference Between TMY and Historical Mean\nVariable: {info['name']}", fontweight='bold', pad=20)
            ax.set_xlabel("Percentile Threshold", fontweight='bold', labelpad=15)
            ax.set_ylabel("Hour Difference (TMY - NLDAS Mean)", fontweight='bold', labelpad=15)
            
            # Clean up the legend
            handles, labels = ax.get_legend_handles_labels()
            ax.legend(handles=handles, labels=['Virginia (VA)', 'Texas (TX)'], title="State", loc='best', frameon=True, shadow=True)

            plt.tight_layout()
            pdf.savefig(fig, bbox_inches='tight')
            plt.close(fig)


    print(f"Analysis 2 Summary Scatter Plots saved to: {analysis2_summary_pdf}")
    print("\nAll tasks completed successfully!")

    # print(f"Analysis 2 Range Plots saved to: {analysis2_pdf}")
    # print("\nAll tasks completed successfully!")