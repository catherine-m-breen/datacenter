'''
old script 
'''
# import os
# import glob
# import pandas as pd
# import xarray as xr
# import numpy as np
# import matplotlib.pyplot as plt
# from matplotlib.backends.backend_pdf import PdfPages
# from sklearn.metrics import mean_squared_error, r2_score
# import warnings
# from concurrent.futures import ProcessPoolExecutor, as_completed
# import multiprocessing

# warnings.filterwarnings('ignore')

# # ==========================================
# # CONFIGURATION TOGGLES
# # ==========================================
# PROCESS_ALL_YEARS = True     
# PLOT_EVERY_YEAR_TS = True     
# PROCESS_ALL_STATIONS = True  

# NLDAS_DIR = '/discover/nobackup/projects/eis_nldas3/DATA/forcing/hourly'
# STATION_DIR = '/discover/nobackup/cmbreen/datacenters/uscrn_independent_data'
# OUTPUT_DIR = './nldas_station_reports'

# # NLDAS Variable names
# NLDAS_TMP = 'Tair'      
# NLDAS_SPFH = 'Qair'    

# P_HPA = 1013.25  

# VARS_TO_PLOT = [('T_C_obs', 'T_C_sim', 'Temp (°C)', 'T_C'),
#                 ('RH_obs', 'RH_derived', 'Rel. Humidity (%)', 'RH'),
#                 ('Enthalpy_kJ_kg_obs', 'Enthalpy_kJ_kg_sim', 'Enthalpy (kJ/kg)', 'Enthalpy')]

# # ==========================================
# # HELPER FUNCTIONS
# # ==========================================
# def calc_psychrometrics(df, source='station'):
#     e_s = 6.112 * np.exp((17.67 * df['T_C']) / (df['T_C'] + 243.5))
#     if source == 'nldas':
#         e = (df['Q_kg_kg'] * P_HPA) / (0.622 + 0.378 * df['Q_kg_kg'])
#         df['RH_derived'] = np.clip(100.0 * (e / e_s), 0, 100)
#     elif source == 'station':
#         e = e_s * (df['RH_obs'] / 100.0)
#         df['Q_derived'] = (0.622 * e) / (P_HPA - 0.378 * e)
#         df['Q_kg_kg'] = df['Q_derived'] 
        
#     df['Enthalpy_kJ_kg'] = 1.006 * df['T_C'] + df['Q_kg_kg'] * (2501 + 1.86 * df['T_C'])
#     return df

# def get_season(month):
#     if month in [12, 1, 2]: return 'Winter'
#     elif month in [3, 4, 5]: return 'Spring'
#     elif month in [6, 7, 8]: return 'Summer'
#     else: return 'Fall'

# # ==========================================
# # PARALLEL WORKER FUNCTION (Processes 1 Station)
# # ==========================================
# def process_station(stn_file, nldas_files, output_dir, process_all_years, plot_every_year_ts):
#     stn_name = os.path.basename(stn_file).replace('.csv', '')
    
#     pid = os.getpid()
#     print(f"  [Worker PID: {pid}] ---> STARTING: {stn_name}", flush=True)
    
#     # 1. Load Station Data
#     df_stn = pd.read_csv(stn_file)
#     df_stn = df_stn.rename(columns={'temperature': 'T_C', 'relative_humidity': 'RH_obs'})
#     df_stn['T_C'] = pd.to_numeric(df_stn['T_C'], errors='coerce')
#     df_stn['RH_obs'] = pd.to_numeric(df_stn['RH_obs'], errors='coerce')
    
#     # Filter USCRN Errors
#     df_stn.loc[df_stn['T_C'] < -80, 'T_C'] = np.nan       
#     df_stn.loc[df_stn['RH_obs'] < 0, 'RH_obs'] = np.nan   
#     df_stn.loc[df_stn['RH_obs'] > 105, 'RH_obs'] = np.nan 
    
#     df_stn['datetime'] = pd.to_datetime(df_stn['datetime'], errors='coerce').dt.tz_localize(None)
#     df_stn['datetime'] = df_stn['datetime'].dt.round('h') 
    
#     stn_lat = df_stn['latitude'].iloc[0]
#     stn_lon = df_stn['longitude'].iloc[0]
    
#     df_stn = calc_psychrometrics(df_stn, source='station')
#     df_stn = df_stn.set_index('datetime')
    
#     # 2. Load NLDAS Data
#     df_list = []
#     for f in nldas_files:
#         try:
#             with xr.open_dataset(f, engine='netcdf4') as ds:
#                 lat_var = 'lat' if 'lat' in ds.coords else 'latitude'
#                 lon_var = 'lon' if 'lon' in ds.coords else 'longitude'
#                 pt = ds.sel({lat_var: stn_lat, lon_var: stn_lon}, method='nearest')
#                 df_pt = pt[[NLDAS_TMP, NLDAS_SPFH]].to_dataframe().reset_index()
#                 df_list.append(df_pt)
#         except Exception:
#             pass
            
#     if not df_list:
#         print(f"  [Worker PID: {pid}] <--- FINISHED (No NLDAS Data): {stn_name}")
#         return stn_name, None, []  # Return empty list for anomalies
        
#     df_nldas = pd.concat(df_list, ignore_index=True)
#     df_nldas = df_nldas.rename(columns={'time': 'datetime'})
#     df_nldas['datetime'] = df_nldas['datetime'].dt.round('h')
    
#     if df_nldas[NLDAS_TMP].mean() > 200: 
#         df_nldas['T_C'] = df_nldas[NLDAS_TMP] - 273.15
#     else:
#         df_nldas['T_C'] = df_nldas[NLDAS_TMP]
        
#     df_nldas['Q_kg_kg'] = df_nldas[NLDAS_SPFH]
#     df_nldas = calc_psychrometrics(df_nldas, source='nldas')
#     df_nldas = df_nldas.set_index('datetime')
    
#     # 3. Merge Datasets
#     merged = df_stn[['T_C', 'RH_obs', 'Enthalpy_kJ_kg']].join(
#         df_nldas[['T_C', 'RH_derived', 'Enthalpy_kJ_kg']], 
#         lsuffix='_obs', rsuffix='_sim', how='inner'
#     )
    
#     if merged.empty:
#         print(f"  [Worker PID: {pid}] <--- FINISHED (Empty Merge): {stn_name}")
#         return stn_name, None, [] # Return empty list for anomalies
        
#     merged['season'] = merged.index.month.map(get_season)
#     merged['Station'] = stn_name

#     # ==========================================
#     # NEW: FLAG ANOMALOUS RH YEARS
#     # ==========================================
#     suspicious_years = []
#     for yr in merged.index.year.unique():
#         yr_data = merged[merged.index.year == yr]
#         valid_rh = yr_data['RH_obs'].dropna()
        
#         # If more than 75% of the valid RH data for this year is <= 1%
#         if len(valid_rh) > 0 and (valid_rh <= 1.0).mean() > 0.75:
#             suspicious_years.append(yr)

#     # 4. Individual Station PDF Generation
#     pdf_path = os.path.join(output_dir, f"{stn_name}_analysis.pdf")
#     with PdfPages(pdf_path) as pdf:
#         if process_all_years and plot_every_year_ts:
#             years_to_plot = sorted(merged.index.year.unique())
#         else:
#             sample_year = 2018
#             years_to_plot = [sample_year] if sample_year in merged.index.year else [merged.index.year[0]]
                
#         # TIMESERIES
#         for yr in years_to_plot:
#             merged_yr = merged[merged.index.year == yr]
#             if not merged_yr.empty:
#                 fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
#                 axes[0].plot(merged_yr.index, merged_yr['T_C_obs'], label='Station', alpha=0.7)
#                 axes[0].plot(merged_yr.index, merged_yr['T_C_sim'], label='NLDAS3', alpha=0.7)
#                 axes[0].set_ylabel("Temp (°C)"); axes[0].legend(); axes[0].set_title(f"{yr} Time Series")
                
#                 axes[1].plot(merged_yr.index, merged_yr['RH_obs'], alpha=0.7)
#                 axes[1].plot(merged_yr.index, merged_yr['RH_derived'], alpha=0.7)
#                 axes[1].set_ylabel("RH (%)")
                
#                 axes[2].plot(merged_yr.index, merged_yr['Enthalpy_kJ_kg_obs'], alpha=0.7)
#                 axes[2].plot(merged_yr.index, merged_yr['Enthalpy_kJ_kg_sim'], alpha=0.7)
#                 axes[2].set_ylabel("Enthalpy (kJ/kg)"); axes[2].set_xlabel("Date")
                
#                 plt.tight_layout(); pdf.savefig(fig); plt.close(fig)
            
#         # OVERALL SCATTER
#         fig, axes = plt.subplots(1, 3, figsize=(18, 5))
#         for ax, (obs_col, sim_col, title, dict_key) in zip(axes, VARS_TO_PLOT):
#             clean = merged.dropna(subset=[obs_col, sim_col])
#             if len(clean) > 10:
#                 obs, sim = clean[obs_col], clean[sim_col]
#                 r2, bias = r2_score(obs, sim), np.mean(sim - obs)
#                 ax.scatter(obs, sim, alpha=0.1, s=2, c='purple')
#                 mn, mx = min(obs.min(), sim.min()), max(obs.max(), sim.max())
#                 ax.plot([mn, mx], [mn, mx], 'k--')
#                 ax.set_title(f"{title}\nR²: {r2:.3f} | Bias: {bias:.3f}")
#                 ax.grid(True, alpha=0.3)
#         plt.tight_layout(); pdf.savefig(fig); plt.close(fig)

#     print(f"  [Worker PID: {pid}] <--- FINISHED: {stn_name}")
#     # Return suspicious years to main thread
#     return stn_name, merged, suspicious_years

# # ==========================================
# # MAIN EXECUTION THREAD
# # ==========================================
# if __name__ == '__main__':
#     try:
#         multiprocessing.set_start_method('spawn')
#     except RuntimeError:
#         pass # Prevents error if already set

#     os.makedirs(OUTPUT_DIR, exist_ok=True)
    
#     if PROCESS_ALL_STATIONS:
#         station_files = [f for f in glob.glob(os.path.join(STATION_DIR, '*.csv')) if not os.path.basename(f).startswith('all_')]
#     else:
#         station_files = glob.glob(os.path.join(STATION_DIR, 'VA_*.csv')) + glob.glob(os.path.join(STATION_DIR, 'TX_*.csv'))

#     print(f"Total stations queued for processing: {len(station_files)}", flush=True)

#     if PROCESS_ALL_YEARS:
#         nldas_pattern = os.path.join(NLDAS_DIR, '*', '*.nc')
#     else:
#         nldas_pattern = os.path.join(NLDAS_DIR, '2018*', '*.nc')
        
#     nldas_files = sorted(glob.glob(nldas_pattern))
#     if not nldas_files:
#         print("  -> [ERROR] No NLDAS files found for pattern. Exiting.", flush=True)
#         exit()
    
#     print(f"Located {len(nldas_files)} NLDAS files. Starting Parallel Pool...", flush=True)

#     station_dfs = {}
#     master_df_list = []
#     anomaly_report = {} 

#     max_cores = min(multiprocessing.cpu_count(), len(station_files), 32)
#     print(f"*** Spinning up {max_cores} parallel workers ***\n", flush=True)
    
#     with ProcessPoolExecutor(max_workers=max_cores) as executor:
#         futures = {
#             executor.submit(process_station, stn, nldas_files, OUTPUT_DIR, PROCESS_ALL_YEARS, PLOT_EVERY_YEAR_TS): stn 
#             for stn in station_files
#         }
        
#         completed = 0
#         for future in as_completed(futures):
#             # Unpack the 3rd variable (suspicious_years)
#             stn_name, merged_df, suspicious_years = future.result()
#             completed += 1
            
#             if merged_df is not None:
#                 station_dfs[stn_name] = merged_df
#                 master_df_list.append(merged_df)
                
#                 if suspicious_years:
#                     anomaly_report[stn_name] = suspicious_years
                    
#                 print(f"[MAIN THREAD] Progress: {completed}/{len(station_files)} stations fully collected.", flush=True)
#             else:
#                 print(f"[MAIN THREAD] Failed/Skipped {stn_name} (Insufficient data)", flush=True)

#     # ==========================================
#     # GENERATE COMBINED PDFS (Sequentially on Main Thread)
#     # ==========================================
#     print("\n=======================================================")
#     print("Generating COMBINED Station PDFs...")
    
#     comb_scatter_pdf = PdfPages(os.path.join(OUTPUT_DIR, 'COMBINED_Scatter_Plots.pdf'))
#     comb_ts_pdf = PdfPages(os.path.join(OUTPUT_DIR, 'COMBINED_Timeseries_Plots.pdf'))
    
#     valid_stn_count = 0
#     pending_save = False
    
#     for stn_name in sorted(station_dfs.keys()):
#         merged = station_dfs[stn_name]
        
#         sample_year = 2018
#         merged_sample = merged[merged.index.year == sample_year]
#         if merged_sample.empty: merged_sample = merged[merged.index.year == merged.index.year[0]]
            
#         if valid_stn_count % 2 == 0:
#             scatter_fig, scatter_axes = plt.subplots(2, 3, figsize=(18, 12))
#             scatter_fig.suptitle("Station Scatter Plots Comparison", fontsize=18, fontweight='bold', y=0.98)
#             ts_fig, ts_axes = plt.subplots(3, 2, figsize=(20, 12))
#             ts_fig.suptitle("Station Time Series Comparison", fontsize=18, fontweight='bold', y=0.95)
        
#         row_idx = valid_stn_count % 2   
#         col_idx = valid_stn_count % 2   
        
#         for j, (obs_col, sim_col, title, dict_key) in enumerate(VARS_TO_PLOT):
#             clean = merged.dropna(subset=[obs_col, sim_col])
#             ax = scatter_axes[row_idx, j]
#             if len(clean) > 10:
#                 obs, sim = clean[obs_col], clean[sim_col]
#                 r2, bias = r2_score(obs, sim), np.mean(sim - obs)
#                 ax.scatter(obs, sim, alpha=0.1, s=2, c='purple')
#                 mn, mx = min(obs.min(), sim.min()), max(obs.max(), sim.max())
#                 ax.plot([mn, mx], [mn, mx], 'k--')
#                 ax_title = f"{stn_name}\n{title}" if j == 0 else title
#                 ax.set_title(f"{ax_title} | R²: {r2:.3f} | Bias: {bias:.3f}", fontsize=11)
#                 ax.grid(True, alpha=0.3)
#             else:
#                 ax.axis('off')

#         if not merged_sample.empty:
#             ts_axes[0, col_idx].plot(merged_sample.index, merged_sample['T_C_obs'], label='Station', alpha=0.7)
#             ts_axes[0, col_idx].plot(merged_sample.index, merged_sample['T_C_sim'], label='NLDAS3', alpha=0.7)
#             ts_axes[0, col_idx].set_ylabel("Temp (°C)"); ts_axes[0, col_idx].legend()
#             ts_axes[0, col_idx].set_title(f"{stn_name} - {sample_year}", fontsize=14, fontweight='bold')
            
#             ts_axes[1, col_idx].plot(merged_sample.index, merged_sample['RH_obs'], alpha=0.7)
#             ts_axes[1, col_idx].plot(merged_sample.index, merged_sample['RH_derived'], alpha=0.7)
#             ts_axes[1, col_idx].set_ylabel("RH (%)")
            
#             ts_axes[2, col_idx].plot(merged_sample.index, merged_sample['Enthalpy_kJ_kg_obs'], alpha=0.7)
#             ts_axes[2, col_idx].plot(merged_sample.index, merged_sample['Enthalpy_kJ_kg_sim'], alpha=0.7)
#             ts_axes[2, col_idx].set_ylabel("Enthalpy"); ts_axes[2, col_idx].set_xlabel("Date")
#         else:
#             for r in range(3): ts_axes[r, col_idx].axis('off')

#         pending_save = True
#         valid_stn_count += 1
        
#         if valid_stn_count % 2 == 0:
#             scatter_fig.tight_layout(rect=[0, 0.03, 1, 0.95]); comb_scatter_pdf.savefig(scatter_fig); plt.close(scatter_fig)
#             ts_fig.tight_layout(rect=[0, 0.03, 1, 0.93]); comb_ts_pdf.savefig(ts_fig); plt.close(ts_fig)
#             pending_save = False

#     if pending_save:
#         for r in range(3): 
#             scatter_axes[1, r].axis('off')
#             ts_axes[r, 1].axis('off')
#         scatter_fig.tight_layout(rect=[0, 0.03, 1, 0.95]); comb_scatter_pdf.savefig(scatter_fig); plt.close(scatter_fig)
#         ts_fig.tight_layout(rect=[0, 0.03, 1, 0.93]); comb_ts_pdf.savefig(ts_fig); plt.close(ts_fig)

#     comb_scatter_pdf.close()
#     comb_ts_pdf.close()

#     # ==========================================
#     # MASTER OVERALL SUMMARY PLOT
#     # ==========================================
#     print("\n=======================================================")
#     print("Generating ALL STATIONS Master Summary...")
#     master_pdf_path = os.path.join(OUTPUT_DIR, "ALL_STATIONS_MASTER_SUMMARY.pdf")

#     if master_df_list:
#         df_global = pd.concat(master_df_list, ignore_index=True)
        
#         with PdfPages(master_pdf_path) as pdf:
#             fig, axes = plt.subplots(1, 3, figsize=(18, 5))
#             fig.suptitle("Global NLDAS-3 Validation (All Data Combined)", fontsize=20, fontweight='bold', y=1.05)
            
#             for ax, (obs_col, sim_col, title, dict_key) in zip(axes, VARS_TO_PLOT):
#                 clean = df_global.dropna(subset=[obs_col, sim_col])
#                 if len(clean) > 10:
#                     obs, sim = clean[obs_col], clean[sim_col]
#                     r2, bias = r2_score(obs, sim), np.mean(sim - obs)
#                     hb = ax.hexbin(obs, sim, gridsize=50, cmap='inferno', mincnt=1, bins='log')
#                     mn, mx = min(obs.min(), sim.min()), max(obs.max(), sim.max())
#                     ax.plot([mn, mx], [mn, mx], 'cyan', linestyle='--', lw=2, label='1:1 Line')
#                     ax.set_title(f"Overall {title}\nR²: {r2:.3f} | Bias: {bias:.3f}")
#                     ax.set_xlabel("Observation"); ax.set_ylabel("NLDAS")
#                     cb = plt.colorbar(hb, ax=ax); cb.set_label('log10(count)')
                    
#             plt.tight_layout(rect=[0, 0.03, 1, 0.95])
#             pdf.savefig(fig); plt.close(fig)

#             fig, ax = plt.subplots(figsize=(12, 8))
#             ax.axis('off')
            
#             table_data = []
#             for season in ['Winter', 'Spring', 'Summer', 'Fall']:
#                 season_data = df_global[df_global['season'] == season]
#                 row = [season]
#                 for obs_col, sim_col, _, _ in VARS_TO_PLOT:
#                     clean = season_data.dropna(subset=[obs_col, sim_col])
#                     if len(clean) > 10:
#                         r2, bias = r2_score(clean[obs_col], clean[sim_col]), np.mean(clean[sim_col] - clean[obs_col])
#                         row.append(f"R²: {r2:.2f}\nBias: {bias:.2f}")
#                     else:
#                         row.append("N/A")
#                 table_data.append(row)
                
#             table = ax.table(cellText=table_data, 
#                              colLabels=["Season", "Temperature", "Rel. Humidity", "Enthalpy"],
#                              loc='center', cellLoc='center', bbox=[0, 0, 1, 1])
#             table.auto_set_font_size(False)
#             table.set_fontsize(14)
#             ax.set_title("GLOBAL SYSTEMIC SEASONAL BIAS\n(All Data Combined)", pad=20, fontsize=18, fontweight='bold')
#             pdf.savefig(fig); plt.close(fig)
            
#             for stn in sorted(df_global['Station'].unique()):
#                 stn_df = df_global[df_global['Station'] == stn]
#                 fig, axes = plt.subplots(1, 3, figsize=(18, 5))
#                 fig.suptitle(f"Station Bias Summary: {stn} (All Processed Years)", fontsize=16, fontweight='bold', y=1.05)
                
#                 for ax, (obs_col, sim_col, title, dict_key) in zip(axes, VARS_TO_PLOT):
#                     clean = stn_df.dropna(subset=[obs_col, sim_col])
#                     if len(clean) > 10:
#                         obs, sim = clean[obs_col], clean[sim_col]
#                         r2, bias = r2_score(obs, sim), np.mean(sim - obs)
#                         ax.scatter(obs, sim, alpha=0.1, s=2, c='purple')
#                         mn, mx = min(obs.min(), sim.min()), max(obs.max(), sim.max())
#                         ax.plot([mn, mx], [mn, mx], 'k--')
#                         ax.set_title(f"{title}\nR²: {r2:.3f} | Bias: {bias:.3f}")
#                         ax.grid(True, alpha=0.3)
#                     else:
#                         ax.text(0.5, 0.5, "Insufficient Data", ha='center', va='center')
#                         ax.axis('off')
#                 plt.tight_layout(rect=[0, 0.03, 1, 0.95])
#                 pdf.savefig(fig); plt.close(fig)

#     print(f"\nAll operations complete! Outputs saved in: {OUTPUT_DIR}")

#     # ==========================================
#     # FINAL ANOMALY REPORT OUTPUT
#     # ==========================================
#     if anomaly_report:
#         print("\n" + "="*60)
#         print("!!! SUSPICIOUS RH DATA DETECTED !!!")
#         print("The following stations have specific years where >75% of")
#         print("the relative humidity observations read near 0% (<= 1.0%):")
#         print("="*60)
#         for stn, years in sorted(anomaly_report.items()):
#             print(f"  -> {stn}: {years}")
#         print("="*60 + "\n")
#     else:
#         print("\nAll Good: No systemic ~0% RH anomalies detected in the processed dataset.\n")

'''
new script that reads the json 
outputs: 

'''

# import os
# import glob
# import json
# import pandas as pd
# import numpy as np
# import matplotlib.pyplot as plt
# from matplotlib.backends.backend_pdf import PdfPages
# from sklearn.metrics import mean_squared_error, r2_score
# import warnings
# from concurrent.futures import ProcessPoolExecutor, as_completed
# import multiprocessing

# warnings.filterwarnings('ignore')

# # ==========================================
# # CONFIGURATION TOGGLES
# # ==========================================
# PROCESS_ALL_YEARS = True     
# PLOT_EVERY_YEAR_TS = True     

# JSON_DATA_PATH = './nldas_station_reports_sequential/PRIORITY_STATIONS_NLDAS.json'
# STATION_DIR = '/discover/nobackup/cmbreen/datacenters/uscrn_independent_data'
# OUTPUT_DIR = './nldas_station_reports_sequential'

# P_HPA = 1013.25  

# VARS_TO_PLOT = [('T_C_obs', 'T_C_sim', 'Temp (°C)', 'T_C'),
#                 ('RH_obs', 'RH_derived', 'Rel. Humidity (%)', 'RH'),
#                 ('Enthalpy_kJ_kg_obs', 'Enthalpy_kJ_kg_sim', 'Enthalpy (kJ/kg)', 'Enthalpy')]

# # ==========================================
# # HELPER FUNCTIONS
# # ==========================================
# def calc_psychrometrics(df, source='station'):
#     e_s = 6.112 * np.exp((17.67 * df['T_C']) / (df['T_C'] + 243.5))
#     if source == 'nldas':
#         e = (df['Q_kg_kg'] * P_HPA) / (0.622 + 0.378 * df['Q_kg_kg'])
#         df['RH_derived'] = np.clip(100.0 * (e / e_s), 0, 100)
#     elif source == 'station':
#         e = e_s * (df['RH_obs'] / 100.0)
#         df['Q_derived'] = (0.622 * e) / (P_HPA - 0.378 * e)
#         df['Q_kg_kg'] = df['Q_derived'] 
        
#     df['Enthalpy_kJ_kg'] = 1.006 * df['T_C'] + df['Q_kg_kg'] * (2501 + 1.86 * df['T_C'])
#     return df

# def get_season(month):
#     if month in [12, 1, 2]: return 'Winter'
#     elif month in [3, 4, 5]: return 'Spring'
#     elif month in [6, 7, 8]: return 'Summer'
#     else: return 'Fall'

# # ==========================================
# # PARALLEL WORKER FUNCTION (Processes 1 Station)
# # ==========================================
# def process_station(worker_payload):
#     stn_name, stn_file, stn_json_data, output_dir, process_all_years, plot_every_year_ts = worker_payload
#     pid = os.getpid()
    
#     # 1. Load Station Data (Observations)
#     df_stn = pd.read_csv(stn_file)
#     df_stn = df_stn.rename(columns={'temperature': 'T_C', 'relative_humidity': 'RH_obs'})
#     df_stn['T_C'] = pd.to_numeric(df_stn['T_C'], errors='coerce')
#     df_stn['RH_obs'] = pd.to_numeric(df_stn['RH_obs'], errors='coerce')
    
#     # Filter USCRN Errors
#     df_stn.loc[df_stn['T_C'] < -80, 'T_C'] = np.nan       
#     df_stn.loc[df_stn['RH_obs'] < 0, 'RH_obs'] = np.nan   
#     df_stn.loc[df_stn['RH_obs'] > 105, 'RH_obs'] = np.nan 
    
#     df_stn['datetime'] = pd.to_datetime(df_stn['datetime'], errors='coerce').dt.tz_localize(None)
#     df_stn['datetime'] = df_stn['datetime'].dt.round('h') 
    
#     df_stn = calc_psychrometrics(df_stn, source='station')
#     df_stn = df_stn.set_index('datetime')
    
#     # 2. Parse NLDAS JSON Data into a DataFrame
#     records = []
#     for ym, days in stn_json_data.items():
#         for date_str, data_dict in days.items():
#             base_dt = pd.to_datetime(date_str, format="%Y%m%d")
#             n_hours = len(data_dict['tair']) # Usually 24
            
#             for h in range(n_hours):
#                 records.append({
#                     'datetime': base_dt + pd.Timedelta(hours=h),
#                     'Tair': data_dict['tair'][h],
#                     'Qair': data_dict['qair'][h]
#                 })
                
#     if not records:
#         print(f"  [Worker PID: {pid}] <--- FINISHED (No JSON Data): {stn_name}")
#         return stn_name, None, []
        
#     df_nldas = pd.DataFrame(records).set_index('datetime')
    
#     # Handle Kelvin to Celsius
#     if df_nldas['Tair'].mean() > 200: 
#         df_nldas['T_C'] = df_nldas['Tair'] - 273.15
#     else:
#         df_nldas['T_C'] = df_nldas['Tair']
        
#     df_nldas['Q_kg_kg'] = df_nldas['Qair']
#     df_nldas = calc_psychrometrics(df_nldas, source='nldas')
    
#     # 3. Merge Datasets (Inner Join on Datetime)
#     merged = df_stn[['T_C', 'RH_obs', 'Enthalpy_kJ_kg']].join(
#         df_nldas[['T_C', 'RH_derived', 'Enthalpy_kJ_kg']], 
#         lsuffix='_obs', rsuffix='_sim', how='inner'
#     )
    
#     if merged.empty:
#         print(f"  [Worker PID: {pid}] <--- FINISHED (Empty Merge): {stn_name}")
#         return stn_name, None, [] 
        
#     merged['season'] = merged.index.month.map(get_season)
#     merged['Station'] = stn_name

#     # 4. Flag Anomalous RH Years
#     suspicious_years = []
#     for yr in merged.index.year.unique():
#         yr_data = merged[merged.index.year == yr]
#         valid_rh = yr_data['RH_obs'].dropna()
#         if len(valid_rh) > 0 and (valid_rh <= 1.0).mean() > 0.75:
#             suspicious_years.append(yr)

#     # 5. Individual Station PDF Generation
#     pdf_path = os.path.join(output_dir, f"{stn_name}_analysis.pdf")
#     with PdfPages(pdf_path) as pdf:
#         if process_all_years and plot_every_year_ts:
#             years_to_plot = sorted(merged.index.year.unique())
#         else:
#             sample_year = 2018
#             years_to_plot = [sample_year] if sample_year in merged.index.year else [merged.index.year[0]]
                
#         for yr in years_to_plot:
#             merged_yr = merged[merged.index.year == yr]
#             if not merged_yr.empty:
#                 fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
#                 axes[0].plot(merged_yr.index, merged_yr['T_C_obs'], label='Station', alpha=0.7)
#                 axes[0].plot(merged_yr.index, merged_yr['T_C_sim'], label='NLDAS3', alpha=0.7)
#                 axes[0].set_ylabel("Temp (°C)"); axes[0].legend(); axes[0].set_title(f"{stn_name} - {yr} Time Series")
                
#                 axes[1].plot(merged_yr.index, merged_yr['RH_obs'], alpha=0.7)
#                 axes[1].plot(merged_yr.index, merged_yr['RH_derived'], alpha=0.7)
#                 axes[1].set_ylabel("RH (%)")
                
#                 axes[2].plot(merged_yr.index, merged_yr['Enthalpy_kJ_kg_obs'], alpha=0.7)
#                 axes[2].plot(merged_yr.index, merged_yr['Enthalpy_kJ_kg_sim'], alpha=0.7)
#                 axes[2].set_ylabel("Enthalpy (kJ/kg)"); axes[2].set_xlabel("Date")
                
#                 plt.tight_layout(); pdf.savefig(fig); plt.close(fig)
            
#         fig, axes = plt.subplots(1, 3, figsize=(18, 5))
#         for ax, (obs_col, sim_col, title, dict_key) in zip(axes, VARS_TO_PLOT):
#             clean = merged.dropna(subset=[obs_col, sim_col])
#             if len(clean) > 10:
#                 obs, sim = clean[obs_col], clean[sim_col]
#                 r2, bias = r2_score(obs, sim), np.mean(sim - obs)
#                 ax.scatter(obs, sim, alpha=0.1, s=2, c='purple')
#                 mn, mx = min(obs.min(), sim.min()), max(obs.max(), sim.max())
#                 ax.plot([mn, mx], [mn, mx], 'k--')
#                 ax.set_title(f"{title}\nR²: {r2:.3f} | Bias: {bias:.3f}")
#                 ax.grid(True, alpha=0.3)
#         plt.tight_layout(); pdf.savefig(fig); plt.close(fig)

#     print(f"  [Worker PID: {pid}] <--- FINISHED: {stn_name}", flush=True)
#     return stn_name, merged, suspicious_years

# # ==========================================
# # MAIN EXECUTION THREAD
# # ==========================================
# if __name__ == '__main__':
#     try:
#         multiprocessing.set_start_method('spawn')
#     except RuntimeError:
#         pass 

#     os.makedirs(OUTPUT_DIR, exist_ok=True)
    
#     print("Loading extracted JSON dataset...")
#     with open(JSON_DATA_PATH, 'r') as jf:
#         all_nldas_data = json.load(jf)
        
#     print(f"Data loaded for {len(all_nldas_data)} stations.")

#     # Find the CSV paths for the stations that exist in our JSON
#     station_payloads = []
#     for stn_name in all_nldas_data.keys():
#         stn_file = os.path.join(STATION_DIR, f"{stn_name}.csv")
#         if os.path.exists(stn_file):
#             # Package everything the worker needs so we don't have to share memory
#             payload = (stn_name, stn_file, all_nldas_data[stn_name], OUTPUT_DIR, PROCESS_ALL_YEARS, PLOT_EVERY_YEAR_TS)
#             station_payloads.append(payload)

#     station_dfs = {}
#     master_df_list = []
#     anomaly_report = {} 

#     max_cores = min(multiprocessing.cpu_count(), len(station_payloads), 32)
#     print(f"\n*** Spinning up {max_cores} parallel workers to generate plots ***\n", flush=True)
    
#     with ProcessPoolExecutor(max_workers=max_cores) as executor:
#         futures = [executor.submit(process_station, payload) for payload in station_payloads]
        
#         completed = 0
#         for future in as_completed(futures):
#             stn_name, merged_df, suspicious_years = future.result()
#             completed += 1
            
#             if merged_df is not None:
#                 station_dfs[stn_name] = merged_df
#                 master_df_list.append(merged_df)
                
#                 if suspicious_years:
#                     anomaly_report[stn_name] = suspicious_years
                    
#             print(f"[MAIN THREAD] Progress: {completed}/{len(station_payloads)} stations fully processed.", flush=True)

#     # ==========================================
#     # GENERATE COMBINED PDFS (Sequentially on Main Thread)
#     # ==========================================
#     if master_df_list:
#         print("\n=======================================================")
#         print("Generating COMBINED Station PDFs...")
        
#         comb_scatter_pdf = PdfPages(os.path.join(OUTPUT_DIR, 'COMBINED_Scatter_Plots.pdf'))
#         comb_ts_pdf = PdfPages(os.path.join(OUTPUT_DIR, 'COMBINED_Timeseries_Plots.pdf'))
        
#         valid_stn_count = 0
#         pending_save = False
        
#         for stn_name in sorted(station_dfs.keys()):
#             merged = station_dfs[stn_name]
            
#             sample_year = 2018
#             merged_sample = merged[merged.index.year == sample_year]
#             if merged_sample.empty: merged_sample = merged[merged.index.year == merged.index.year[0]]
                
#             if valid_stn_count % 2 == 0:
#                 scatter_fig, scatter_axes = plt.subplots(2, 3, figsize=(18, 12))
#                 scatter_fig.suptitle("Station Scatter Plots Comparison", fontsize=18, fontweight='bold', y=0.98)
#                 ts_fig, ts_axes = plt.subplots(3, 2, figsize=(20, 12))
#                 ts_fig.suptitle("Station Time Series Comparison", fontsize=18, fontweight='bold', y=0.95)
            
#             row_idx = valid_stn_count % 2   
#             col_idx = valid_stn_count % 2   
            
#             for j, (obs_col, sim_col, title, dict_key) in enumerate(VARS_TO_PLOT):
#                 clean = merged.dropna(subset=[obs_col, sim_col])
#                 ax = scatter_axes[row_idx, j]
#                 if len(clean) > 10:
#                     obs, sim = clean[obs_col], clean[sim_col]
#                     r2, bias = r2_score(obs, sim), np.mean(sim - obs)
#                     ax.scatter(obs, sim, alpha=0.1, s=2, c='purple')
#                     mn, mx = min(obs.min(), sim.min()), max(obs.max(), sim.max())
#                     ax.plot([mn, mx], [mn, mx], 'k--')
#                     ax_title = f"{stn_name}\n{title}" if j == 0 else title
#                     ax.set_title(f"{ax_title} | R²: {r2:.3f} | Bias: {bias:.3f}", fontsize=11)
#                     ax.grid(True, alpha=0.3)
#                 else:
#                     ax.axis('off')

#             if not merged_sample.empty:
#                 ts_axes[0, col_idx].plot(merged_sample.index, merged_sample['T_C_obs'], label='Station', alpha=0.7)
#                 ts_axes[0, col_idx].plot(merged_sample.index, merged_sample['T_C_sim'], label='NLDAS3', alpha=0.7)
#                 ts_axes[0, col_idx].set_ylabel("Temp (°C)"); ts_axes[0, col_idx].legend()
#                 ts_axes[0, col_idx].set_title(f"{stn_name} - {sample_year}", fontsize=14, fontweight='bold')
                
#                 ts_axes[1, col_idx].plot(merged_sample.index, merged_sample['RH_obs'], alpha=0.7)
#                 ts_axes[1, col_idx].plot(merged_sample.index, merged_sample['RH_derived'], alpha=0.7)
#                 ts_axes[1, col_idx].set_ylabel("RH (%)")
                
#                 ts_axes[2, col_idx].plot(merged_sample.index, merged_sample['Enthalpy_kJ_kg_obs'], alpha=0.7)
#                 ts_axes[2, col_idx].plot(merged_sample.index, merged_sample['Enthalpy_kJ_kg_sim'], alpha=0.7)
#                 ts_axes[2, col_idx].set_ylabel("Enthalpy"); ts_axes[2, col_idx].set_xlabel("Date")
#             else:
#                 for r in range(3): ts_axes[r, col_idx].axis('off')

#             pending_save = True
#             valid_stn_count += 1
            
#             if valid_stn_count % 2 == 0:
#                 scatter_fig.tight_layout(rect=[0, 0.03, 1, 0.95]); comb_scatter_pdf.savefig(scatter_fig); plt.close(scatter_fig)
#                 ts_fig.tight_layout(rect=[0, 0.03, 1, 0.93]); comb_ts_pdf.savefig(ts_fig); plt.close(ts_fig)
#                 pending_save = False

#         if pending_save:
#             for r in range(3): 
#                 scatter_axes[1, r].axis('off')
#                 ts_axes[r, 1].axis('off')
#             scatter_fig.tight_layout(rect=[0, 0.03, 1, 0.95]); comb_scatter_pdf.savefig(scatter_fig); plt.close(scatter_fig)
#             ts_fig.tight_layout(rect=[0, 0.03, 1, 0.93]); comb_ts_pdf.savefig(ts_fig); plt.close(ts_fig)

#         comb_scatter_pdf.close()
#         comb_ts_pdf.close()

#         # ==========================================
#         # MASTER OVERALL SUMMARY PLOT
#         # ==========================================
#         print("\n=======================================================")
#         print("Generating ALL STATIONS Master Summary...")
#         master_pdf_path = os.path.join(OUTPUT_DIR, "ALL_STATIONS_MASTER_SUMMARY.pdf")
        
#         df_global = pd.concat(master_df_list, ignore_index=True)
        
#         with PdfPages(master_pdf_path) as pdf:
#             fig, axes = plt.subplots(1, 3, figsize=(18, 5))
#             fig.suptitle("Global NLDAS-3 Validation (All Data Combined)", fontsize=20, fontweight='bold', y=1.05)
            
#             for ax, (obs_col, sim_col, title, dict_key) in zip(axes, VARS_TO_PLOT):
#                 clean = df_global.dropna(subset=[obs_col, sim_col])
#                 if len(clean) > 10:
#                     obs, sim = clean[obs_col], clean[sim_col]
#                     r2, bias = r2_score(obs, sim), np.mean(sim - obs)
#                     hb = ax.hexbin(obs, sim, gridsize=50, cmap='inferno', mincnt=1, bins='log')
#                     mn, mx = min(obs.min(), sim.min()), max(obs.max(), sim.max())
#                     ax.plot([mn, mx], [mn, mx], 'cyan', linestyle='--', lw=2, label='1:1 Line')
#                     ax.set_title(f"Overall {title}\nR²: {r2:.3f} | Bias: {bias:.3f}")
#                     ax.set_xlabel("Observation"); ax.set_ylabel("NLDAS")
#                     cb = plt.colorbar(hb, ax=ax); cb.set_label('log10(count)')
                    
#             plt.tight_layout(rect=[0, 0.03, 1, 0.95])
#             pdf.savefig(fig); plt.close(fig)

#             fig, ax = plt.subplots(figsize=(12, 8))
#             ax.axis('off')
            
#             table_data = []
#             for season in ['Winter', 'Spring', 'Summer', 'Fall']:
#                 season_data = df_global[df_global['season'] == season]
#                 row = [season]
#                 for obs_col, sim_col, _, _ in VARS_TO_PLOT:
#                     clean = season_data.dropna(subset=[obs_col, sim_col])
#                     if len(clean) > 10:
#                         r2, bias = r2_score(clean[obs_col], clean[sim_col]), np.mean(clean[sim_col] - clean[obs_col])
#                         row.append(f"R²: {r2:.2f}\nBias: {bias:.2f}")
#                     else:
#                         row.append("N/A")
#                 table_data.append(row)
                
#             table = ax.table(cellText=table_data, 
#                              colLabels=["Season", "Temperature", "Rel. Humidity", "Enthalpy"],
#                              loc='center', cellLoc='center', bbox=[0, 0, 1, 1])
#             table.auto_set_font_size(False)
#             table.set_fontsize(14)
#             ax.set_title("GLOBAL SYSTEMIC SEASONAL BIAS\n(All Data Combined)", pad=20, fontsize=18, fontweight='bold')
#             pdf.savefig(fig); plt.close(fig)

#         print(f"\nAll operations complete! Outputs saved in: {OUTPUT_DIR}")

#     # ==========================================
#     # FINAL ANOMALY REPORT OUTPUT
#     # ==========================================
#     if anomaly_report:
#         print("\n" + "="*60)
#         print("!!! SUSPICIOUS RH DATA DETECTED !!!")
#         print("The following stations have specific years where >75% of")
#         print("the relative humidity observations read near 0% (<= 1.0%):")
#         print("="*60)
#         for stn, years in sorted(anomaly_report.items()):
#             print(f"  -> {stn}: {years}")
#         print("="*60 + "\n")
#     else:
#         print("\nAll Good: No systemic ~0% RH anomalies detected in the processed dataset.\n")


'''

this one also does the missing data checks. 

- It checks for missing data and saves a list of exact missing timestamps 
to a file ({stn_name}_missing_timestamps.csv) so you can track outages.
- tracks extreme values and years when RH is 0 more than 75% of the time
- converts NLDAS3 kelvin to celsius
- conducts inner join so that every USCRN value has a NLDAS3 value

Then for each station: 
1. Scatter plots, overall and seasonal bias
2. timeseries for every 5 years 

Overall
1. overall bias
2 breakdown by state
3. breakdown by climate 


'''
import os
import glob
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from sklearn.metrics import mean_squared_error, r2_score
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing

warnings.filterwarnings('ignore')

# ==========================================
# CONFIGURATION
# ==========================================
# Pointing directly to your folder of yearly JSONs:
JSON_DATA_DIR = './nldas_station_reports_sequential/yearly_checkpoints_ALL'
STATION_DIR = '/discover/nobackup/cmbreen/datacenters/uscrn_independent_data'
OUTPUT_DIR = './station_comprehensive_reports'
os.makedirs(OUTPUT_DIR, exist_ok=True)

P_HPA = 1013.25  

VARS_TO_PLOT = [('T_C_obs', 'T_C_sim', 'Temp (°C)', 'T_C'),
                ('RH_obs', 'RH_derived', 'Rel. Humidity (%)', 'RH'),
                ('Enthalpy_kJ_kg_obs', 'Enthalpy_kJ_kg_sim', 'Enthalpy (kJ/kg)', 'Enthalpy')]

TARGET_TS_YEARS = [2005, 2010, 2015, 2020, 2025]

# Standard US Climate Regions Mapping
STATE_TO_CLIMATE = {
    'WA': 'PNW', 'OR': 'PNW', 'ID': 'PNW',
    'IL': 'Midwest', 'IN': 'Midwest', 'IA': 'Midwest', 'MI': 'Midwest', 'MN': 'Midwest', 'OH': 'Midwest', 'WI': 'Midwest',
    'CT': 'New England', 'ME': 'New England', 'MA': 'New England', 'NH': 'New England', 'RI': 'New England', 'VT': 'New England', 'NY': 'New England', 'PA': 'New England', 'NJ': 'New England',
    'AZ': 'Southwest', 'NM': 'Southwest', 'UT': 'Southwest', 'NV': 'Southwest', 'CA': 'Southwest',
    'AR': 'South', 'LA': 'South', 'MS': 'South', 'AL': 'South', 'GA': 'South', 'FL': 'South', 'SC': 'South', 'NC': 'South', 'VA': 'South', 'TN': 'South', 'KY': 'South',
    'ND': 'Plains', 'SD': 'Plains', 'NE': 'Plains', 'KS': 'Plains', 'OK': 'Plains', 'TX': 'Plains', 'MO': 'Plains',
    'MT': 'Rockies', 'WY': 'Rockies', 'CO': 'Rockies'
}

# ==========================================
# HELPER FUNCTIONS
# ==========================================
def calc_psychrometrics(df, source='station'):
    e_s = 6.112 * np.exp((17.67 * df['T_C']) / (df['T_C'] + 243.5))
    if source == 'nldas':
        e = (df['Q_kg_kg'] * P_HPA) / (0.622 + 0.378 * df['Q_kg_kg'])
        df['RH_derived'] = np.clip(100.0 * (e / e_s), 0, 100)
    elif source == 'station':
        e = e_s * (df['RH_obs'] / 100.0)
        df['Q_derived'] = (0.622 * e) / (P_HPA - 0.378 * e)
        df['Q_kg_kg'] = df['Q_derived'] 
        
    df['Enthalpy_kJ_kg'] = 1.006 * df['T_C'] + df['Q_kg_kg'] * (2501 + 1.86 * df['T_C'])
    return df

def get_season(month):
    if month in [12, 1, 2]: return 'Winter'
    elif month in [3, 4, 5]: return 'Spring'
    elif month in [6, 7, 8]: return 'Summer'
    else: return 'Fall'

def calc_metrics(obs, sim):
    if len(obs) < 5: return np.nan, np.nan, np.nan
    r2 = r2_score(obs, sim)
    bias = np.mean(sim - obs)
    rmse = np.sqrt(mean_squared_error(obs, sim))
    return r2, bias, rmse

def render_table_page(pdf, df, title):
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.axis('tight')
    ax.axis('off')
    
    table = ax.table(cellText=df.values, colLabels=df.columns, loc='center', cellLoc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 1.5)
    
    # Bold the headers
    for (row, col), cell in table.get_celld().items():
        if row == 0:
            cell.set_text_props(weight='bold')
            
    fig.suptitle(title, fontsize=16, fontweight='bold')
    plt.tight_layout()
    pdf.savefig(fig)
    plt.close(fig)

# ==========================================
# PARALLEL WORKER FUNCTION
# ==========================================
def process_station(worker_payload):
    stn_name, stn_file, stn_json_data, output_dir = worker_payload
    state = stn_name.split('_')[0]
    climate = STATE_TO_CLIMATE.get(state, 'Unknown')
    
    # 1. LOAD OBSERVATIONS & IDENTIFY EXTREMES
    df_stn = pd.read_csv(stn_file)
    df_stn = df_stn.rename(columns={'temperature': 'T_C', 'relative_humidity': 'RH_obs'})
    df_stn['T_C'] = pd.to_numeric(df_stn['T_C'], errors='coerce')
    df_stn['RH_obs'] = pd.to_numeric(df_stn['RH_obs'], errors='coerce')
    
    total_records = len(df_stn)
    raw_missing_t = df_stn['T_C'].isna().sum()
    raw_missing_rh = df_stn['RH_obs'].isna().sum()
    
    # Isolate missing timestamps CSV
    missing_mask = df_stn[['T_C', 'RH_obs']].isna().any(axis=1)
    if missing_mask.any():
        df_missing = df_stn[missing_mask]
        df_missing[['datetime', 'T_C', 'RH_obs']].to_csv(
            os.path.join(output_dir, f"{stn_name}_missing_timestamps.csv"), index=False)

    df_stn['datetime'] = pd.to_datetime(df_stn['datetime'], errors='coerce').dt.tz_localize(None).dt.round('h')
    
    # Check if 2008-2010 is completely missing for RH
    rh_08_10 = df_stn[(df_stn['datetime'].dt.year >= 2008) & (df_stn['datetime'].dt.year <= 2010)]['RH_obs']
    is_missing_08_10 = (rh_08_10.isna().mean() > 0.85) if len(rh_08_10) > 0 else True

    # Track Extremes
    ext_mask = (df_stn['T_C'] < -40) | (df_stn['T_C'] > 50) | (df_stn['RH_obs'] < 0) | (df_stn['RH_obs'] > 100)
    df_extremes = df_stn[ext_mask][['datetime', 'T_C', 'RH_obs']].copy()
    df_extremes['Station'] = stn_name
    
    # Clean up station dataset
    df_stn.loc[ext_mask, ['T_C', 'RH_obs']] = np.nan
    df_stn = df_stn.set_index('datetime')
    df_stn = calc_psychrometrics(df_stn, source='station')
    
    # 2. PARSE NLDAS JSON
    records = []
    for ym, days in stn_json_data.items():
        for date_str, data_dict in days.items():
            base_dt = pd.to_datetime(date_str, format="%Y%m%d")
            for h in range(len(data_dict['tair'])):
                records.append({'datetime': base_dt + pd.Timedelta(hours=h), 'Tair': data_dict['tair'][h], 'Qair': data_dict['qair'][h]})
                
    if not records: return stn_name, None, df_extremes, [], None
        
    df_nldas = pd.DataFrame(records).set_index('datetime')
    df_nldas['T_C'] = df_nldas['Tair'] - 273.15 if df_nldas['Tair'].mean() > 200 else df_nldas['Tair']
    df_nldas['Q_kg_kg'] = df_nldas['Qair']
    df_nldas = calc_psychrometrics(df_nldas, source='nldas')
    
    # 3. MERGE & QAQC BAD YEARS
    merged = df_stn[['T_C', 'RH_obs', 'Enthalpy_kJ_kg']].join(
        df_nldas[['T_C', 'RH_derived', 'Enthalpy_kJ_kg']], lsuffix='_obs', rsuffix='_sim', how='inner'
    )
    
    merged['Year'] = merged.index.year
    merged['Season'] = merged.index.month.map(get_season)
    merged['Station'] = stn_name
    merged['State'] = state
    merged['Climate'] = climate
    
    # Drop years where RH is <= 0 for > 75% of the year
    bad_years = []
    for yr, group in merged.groupby('Year'):
        valid_rh = group['RH_obs'].dropna()
        if len(valid_rh) > 0 and (valid_rh <= 0).mean() > 0.75:
            bad_years.append({'Station': stn_name, 'Year': yr})
            
    bad_yr_list = [d['Year'] for d in bad_years]
    merged = merged[~merged['Year'].isin(bad_yr_list)].dropna()

    if merged.empty: return stn_name, None, df_extremes, bad_years, None

    # 4. PLOTTING INDIVIDUAL PDF
    pdf_path = os.path.join(output_dir, f"{stn_name}_analysis.pdf")
    with PdfPages(pdf_path) as pdf:
        
        years = sorted(merged['Year'].unique())
        
        # A. YEARLY SCATTER PLOTS (6 per page = 2 cols x 3 rows)
        for i in range(0, len(years), 2):
            yr1 = years[i]
            yr2 = years[i+1] if i+1 < len(years) else None
            
            fig, axes = plt.subplots(3, 2, figsize=(12, 14))
            fig.suptitle(f"Yearly Scatter Comparisons: {stn_name}", fontsize=16, fontweight='bold')
            
            for col, yr in enumerate([yr1, yr2]):
                if yr is None:
                    for r in range(3): axes[r, col].axis('off')
                    continue
                
                df_yr = merged[merged['Year'] == yr]
                
                for r, (obs_col, sim_col, title, _) in enumerate(VARS_TO_PLOT):
                    ax = axes[r, col]
                    obs, sim = df_yr[obs_col], df_yr[sim_col]
                    r2, bias, rmse = calc_metrics(obs, sim)
                    
                    ax.scatter(obs, sim, alpha=0.2, s=5, c='teal')
                    mn, mx = min(obs.min(), sim.min()), max(obs.max(), sim.max())
                    ax.plot([mn, mx], [mn, mx], 'k--', lw=1)
                    
                    ax.set_title(f"{yr} | {title}\nR²: {r2:.2f} | Bias: {bias:.2f} | RMSE: {rmse:.2f}")
                    ax.set_xlabel("USCRN Obs"); ax.set_ylabel("NLDAS3")
                    ax.grid(True, alpha=0.3)
                    
            plt.tight_layout(rect=[0, 0.03, 1, 0.95])
            pdf.savefig(fig); plt.close(fig)
            
        # B. TARGET TIMESERIES (2x2 Grid per target year)
        for yr in TARGET_TS_YEARS:
            if yr not in years: continue
            
            df_yr = merged[merged['Year'] == yr]
            fig, axes = plt.subplots(2, 2, figsize=(14, 10))
            fig.suptitle(f"{yr} Time Series: {stn_name}", fontsize=16, fontweight='bold')
            
            # Temp
            axes[0,0].plot(df_yr.index, df_yr['T_C_obs'], label='Obs', alpha=0.8)
            axes[0,0].plot(df_yr.index, df_yr['T_C_sim'], label='NLDAS3', alpha=0.8)
            axes[0,0].set_title("Temperature (°C)"); axes[0,0].legend()
            
            # RH
            axes[0,1].plot(df_yr.index, df_yr['RH_obs'], alpha=0.8)
            axes[0,1].plot(df_yr.index, df_yr['RH_derived'], alpha=0.8)
            axes[0,1].set_title("Relative Humidity (%)")
            
            # Enthalpy
            axes[1,0].plot(df_yr.index, df_yr['Enthalpy_kJ_kg_obs'], alpha=0.8)
            axes[1,0].plot(df_yr.index, df_yr['Enthalpy_kJ_kg_sim'], alpha=0.8)
            axes[1,0].set_title("Enthalpy (kJ/kg)")
            
            axes[1,1].axis('off') # Leave 4th quadrant empty
            plt.tight_layout(rect=[0, 0.03, 1, 0.95])
            pdf.savefig(fig); plt.close(fig)

        # C. STATION SUMMARY TABLE
        table_rows = []
        
        def build_row(df_slice, name):
            row = [name]
            for obs_col, sim_col, _, _ in VARS_TO_PLOT:
                r2, bias, rmse = calc_metrics(df_slice[obs_col], df_slice[sim_col])
                row.extend([f"{r2:.2f}", f"{bias:.2f}", f"{rmse:.2f}"])
            return row
            
        table_rows.append(build_row(merged, "OVERALL (All Years)"))
        for season in ['Winter', 'Spring', 'Summer', 'Fall']:
            table_rows.append(build_row(merged[merged['Season'] == season], season))
            
        cols = ["Period", "T R²", "T Bias", "T RMSE", "RH R²", "RH Bias", "RH RMSE", "Enth R²", "Enth Bias", "Enth RMSE"]
        df_table = pd.DataFrame(table_rows, columns=cols)
        render_table_page(pdf, df_table, f"{stn_name} Data Summary")

    # Compile Station Stats to send back
    station_stats = {
        'Station': stn_name,
        'State': state,
        'Total_Records': total_records,
        'Missing_T_Pct': (raw_missing_t / total_records) * 100,
        'Missing_RH_Pct': (raw_missing_rh / total_records) * 100,
        'Missing_08_10_RH': is_missing_08_10
    }
    
    for (obs_col, sim_col, _, key) in VARS_TO_PLOT:
        station_stats[f'{key}_Bias'] = np.mean(merged[sim_col] - merged[obs_col])
        station_stats[f'{key}_R2'] = r2_score(merged[obs_col], merged[sim_col])

    # To save RAM, convert float64 to float32 before sending to main thread
    for col in merged.select_dtypes(include=['float64']).columns:
        merged[col] = merged[col].astype('float32')

    return stn_name, merged, df_extremes, bad_years, station_stats

# ==========================================
# MAIN EXECUTION THREAD
# ==========================================
if __name__ == '__main__':
    print(f"Loading extracted JSON datasets from {JSON_DATA_DIR}...")
    
    # Read and merge all yearly checkpoints dynamically
    all_nldas_data = {}
    json_files = glob.glob(os.path.join(JSON_DATA_DIR, '*_extracted.json'))
    
    for jf_path in json_files:
        with open(jf_path, 'r') as jf:
            year_data = json.load(jf)
            for stn, stn_data in year_data.items():
                if stn not in all_nldas_data:
                    all_nldas_data[stn] = {}
                all_nldas_data[stn].update(stn_data)

    print(f"Data loaded for {len(all_nldas_data)} stations.")

    station_payloads = []
    for stn_name in all_nldas_data.keys():
        stn_file = os.path.join(STATION_DIR, f"{stn_name}.csv")
        if os.path.exists(stn_file):
            station_payloads.append((stn_name, stn_file, all_nldas_data[stn_name], OUTPUT_DIR))

    master_df_list = []
    all_extremes = []
    all_bad_years = []
    all_stats = []

    max_cores = min(multiprocessing.cpu_count(), len(station_payloads), 32)
    print(f"\n*** Starting Parallel Processing on {max_cores} Cores ***")
    
    with ProcessPoolExecutor(max_workers=max_cores) as executor:
        futures = [executor.submit(process_station, payload) for payload in station_payloads]
        for i, future in enumerate(as_completed(futures)):
            stn_name, merged_df, df_ext, bad_yrs, stats = future.result()
            
            if merged_df is not None: master_df_list.append(merged_df)
            if df_ext is not None and not df_ext.empty: all_extremes.append(df_ext)
            if bad_yrs: all_bad_years.extend(bad_yrs)
            if stats is not None: all_stats.append(stats)
                
            print(f"Processed {i+1}/{len(station_payloads)}: {stn_name}", end='\r')

    # SAVE QAQC CSVs
    print("\n\nSaving QA/QC tracking files...")
    if all_extremes:
        pd.concat(all_extremes).to_csv(os.path.join(OUTPUT_DIR, 'extreme_values_tracked.csv'), index=False)
    if all_bad_years:
        pd.DataFrame(all_bad_years).to_csv(os.path.join(OUTPUT_DIR, 'dropped_rh_years.csv'), index=False)

    # ==========================================
    # MASTER AGGREGATION PDF
    # ==========================================
    if master_df_list:
        print("Generating Master Aggregation PDF...")
        global_df = pd.concat(master_df_list, ignore_index=True)
        stats_df = pd.DataFrame(all_stats)
        
        master_pdf_path = os.path.join(OUTPUT_DIR, "ALL_STATIONS_MASTER_SUMMARY.pdf")
        
        def get_agg_row(df, label):
            row = [label, len(df['Station'].unique())]
            for obs_col, sim_col, _, _ in VARS_TO_PLOT:
                r2, bias, rmse = calc_metrics(df[obs_col], df[sim_col])
                row.extend([f"{r2:.2f}", f"{bias:.2f}", f"{rmse:.2f}"])
            return row
            
        cols = ["Region/State", "Stations", "T R²", "T Bias", "T RMSE", "RH R²", "RH Bias", "RH RMSE", "Enth R²", "Enth Bias", "Enth RMSE"]

        with PdfPages(master_pdf_path) as pdf:
            
            # 1. CONUS Overall Table
            conus_row = get_agg_row(global_df, "CONUS OVERALL")
            df_conus = pd.DataFrame([conus_row], columns=cols)
            render_table_page(pdf, df_conus, "CONUS Global Bias Summary")
            
            # 2. State-by-State Table
            state_rows = []
            for state, group in global_df.groupby('State'):
                state_rows.append(get_agg_row(group, state))
            df_state = pd.DataFrame(state_rows, columns=cols)
            render_table_page(pdf, df_state, "State-by-State Bias Summary")
            
            # 3. Climate Region Table
            climate_rows = []
            for clim, group in global_df.groupby('Climate'):
                climate_rows.append(get_agg_row(group, clim))
            df_climate = pd.DataFrame(climate_rows, columns=cols)
            render_table_page(pdf, df_climate, "Climate Region Bias Summary")
            
        print("\nAll operations complete! Check the output directory for your PDFs and CSVs.")
    else:
        print("\n[WARNING] No valid data found to generate master summary.")