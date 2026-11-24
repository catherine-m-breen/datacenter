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

this outputs files to : 

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
# # CONFIGURATION
# # ==========================================
# # Pointing directly to your folder of yearly JSONs:
# JSON_DATA_DIR = './nldas_station_reports_sequential/yearly_checkpoints_ALL'
# STATION_DIR = '/discover/nobackup/cmbreen/datacenters/uscrn_independent_data'
# OUTPUT_DIR = './station_comprehensive_reports'
# os.makedirs(OUTPUT_DIR, exist_ok=True)

# P_HPA = 1013.25  

# VARS_TO_PLOT = [('T_C_obs', 'T_C_sim', 'Temp (°C)', 'T_C'),
#                 ('RH_obs', 'RH_derived', 'Rel. Humidity (%)', 'RH'),
#                 ('Enthalpy_kJ_kg_obs', 'Enthalpy_kJ_kg_sim', 'Enthalpy (kJ/kg)', 'Enthalpy')]

# TARGET_TS_YEARS = [2005, 2010, 2015, 2020, 2025]

# # Standard US Climate Regions Mapping
# STATE_TO_CLIMATE = {
#     'WA': 'PNW', 'OR': 'PNW', 'ID': 'PNW',
#     'IL': 'Midwest', 'IN': 'Midwest', 'IA': 'Midwest', 'MI': 'Midwest', 'MN': 'Midwest', 'OH': 'Midwest', 'WI': 'Midwest',
#     'CT': 'New England', 'ME': 'New England', 'MA': 'New England', 'NH': 'New England', 'RI': 'New England', 'VT': 'New England', 'NY': 'New England', 'PA': 'New England', 'NJ': 'New England',
#     'AZ': 'Southwest', 'NM': 'Southwest', 'UT': 'Southwest', 'NV': 'Southwest', 'CA': 'Southwest',
#     'AR': 'South', 'LA': 'South', 'MS': 'South', 'AL': 'South', 'GA': 'South', 'FL': 'South', 'SC': 'South', 'NC': 'South', 'VA': 'South', 'TN': 'South', 'KY': 'South',
#     'ND': 'Plains', 'SD': 'Plains', 'NE': 'Plains', 'KS': 'Plains', 'OK': 'Plains', 'TX': 'Plains', 'MO': 'Plains',
#     'MT': 'Rockies', 'WY': 'Rockies', 'CO': 'Rockies'
# }

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

# def calc_metrics(obs, sim):
#     if len(obs) < 5: return np.nan, np.nan, np.nan
#     r2 = r2_score(obs, sim)
#     bias = np.mean(sim - obs)
#     rmse = np.sqrt(mean_squared_error(obs, sim))
#     return r2, bias, rmse

# def render_table_page(pdf, df, title):
#     fig, ax = plt.subplots(figsize=(14, 6))
#     ax.axis('tight')
#     ax.axis('off')
    
#     table = ax.table(cellText=df.values, colLabels=df.columns, loc='center', cellLoc='center')
#     table.auto_set_font_size(False)
#     table.set_fontsize(10)
#     table.scale(1, 1.5)
    
#     # Bold the headers
#     for (row, col), cell in table.get_celld().items():
#         if row == 0:
#             cell.set_text_props(weight='bold')
            
#     fig.suptitle(title, fontsize=16, fontweight='bold')
#     plt.tight_layout()
#     pdf.savefig(fig)
#     plt.close(fig)

# # ==========================================
# # PARALLEL WORKER FUNCTION
# # ==========================================
# def process_station(worker_payload):
#     stn_name, stn_file, stn_json_data, output_dir = worker_payload
#     state = stn_name.split('_')[0]
#     climate = STATE_TO_CLIMATE.get(state, 'Unknown')
    
#     # 1. LOAD OBSERVATIONS & IDENTIFY EXTREMES
#     df_stn = pd.read_csv(stn_file)
#     df_stn = df_stn.rename(columns={'temperature': 'T_C', 'relative_humidity': 'RH_obs'})
#     df_stn['T_C'] = pd.to_numeric(df_stn['T_C'], errors='coerce')
#     df_stn['RH_obs'] = pd.to_numeric(df_stn['RH_obs'], errors='coerce')
    
#     total_records = len(df_stn)
#     raw_missing_t = df_stn['T_C'].isna().sum()
#     raw_missing_rh = df_stn['RH_obs'].isna().sum()
    
#     # Isolate missing timestamps CSV
#     missing_mask = df_stn[['T_C', 'RH_obs']].isna().any(axis=1)
#     if missing_mask.any():
#         df_missing = df_stn[missing_mask]
#         df_missing[['datetime', 'T_C', 'RH_obs']].to_csv(
#             os.path.join(output_dir, f"{stn_name}_missing_timestamps.csv"), index=False)

#     df_stn['datetime'] = pd.to_datetime(df_stn['datetime'], errors='coerce').dt.tz_localize(None).dt.round('h')
    
#     # Check if 2008-2010 is completely missing for RH
#     rh_08_10 = df_stn[(df_stn['datetime'].dt.year >= 2008) & (df_stn['datetime'].dt.year <= 2010)]['RH_obs']
#     is_missing_08_10 = (rh_08_10.isna().mean() > 0.85) if len(rh_08_10) > 0 else True

#     # Track Extremes
#     ext_mask = (df_stn['T_C'] < -40) | (df_stn['T_C'] > 50) | (df_stn['RH_obs'] < 0) | (df_stn['RH_obs'] > 100)
#     df_extremes = df_stn[ext_mask][['datetime', 'T_C', 'RH_obs']].copy()
#     df_extremes['Station'] = stn_name
    
#     # Clean up station dataset
#     df_stn.loc[ext_mask, ['T_C', 'RH_obs']] = np.nan
#     df_stn = df_stn.set_index('datetime')
#     df_stn = calc_psychrometrics(df_stn, source='station')
    
#     # 2. PARSE NLDAS JSON
#     records = []
#     for ym, days in stn_json_data.items():
#         for date_str, data_dict in days.items():
#             base_dt = pd.to_datetime(date_str, format="%Y%m%d")
#             for h in range(len(data_dict['tair'])):
#                 records.append({'datetime': base_dt + pd.Timedelta(hours=h), 'Tair': data_dict['tair'][h], 'Qair': data_dict['qair'][h]})
                
#     if not records: return stn_name, None, df_extremes, [], None
        
#     df_nldas = pd.DataFrame(records).set_index('datetime')
#     df_nldas['T_C'] = df_nldas['Tair'] - 273.15 if df_nldas['Tair'].mean() > 200 else df_nldas['Tair']
#     df_nldas['Q_kg_kg'] = df_nldas['Qair']
#     df_nldas = calc_psychrometrics(df_nldas, source='nldas')
    
#     # 3. MERGE & QAQC BAD YEARS
#     merged = df_stn[['T_C', 'RH_obs', 'Enthalpy_kJ_kg']].join(
#         df_nldas[['T_C', 'RH_derived', 'Enthalpy_kJ_kg']], lsuffix='_obs', rsuffix='_sim', how='inner'
#     )
    
#     merged['Year'] = merged.index.year
#     merged['Season'] = merged.index.month.map(get_season)
#     merged['Station'] = stn_name
#     merged['State'] = state
#     merged['Climate'] = climate
    
#     # Drop years where RH is <= 0 for > 75% of the year
#     bad_years = []
#     for yr, group in merged.groupby('Year'):
#         valid_rh = group['RH_obs'].dropna()
#         if len(valid_rh) > 0 and (valid_rh <= 0).mean() > 0.75:
#             bad_years.append({'Station': stn_name, 'Year': yr})
            
#     bad_yr_list = [d['Year'] for d in bad_years]
#     merged = merged[~merged['Year'].isin(bad_yr_list)].dropna()

#     if merged.empty: return stn_name, None, df_extremes, bad_years, None

#     # 4. PLOTTING INDIVIDUAL PDF
#     pdf_path = os.path.join(output_dir, f"{stn_name}_analysis.pdf")
#     with PdfPages(pdf_path) as pdf:
        
#         years = sorted(merged['Year'].unique())
        
#         # A. YEARLY SCATTER PLOTS (6 per page = 2 cols x 3 rows)
#         for i in range(0, len(years), 2):
#             yr1 = years[i]
#             yr2 = years[i+1] if i+1 < len(years) else None
            
#             fig, axes = plt.subplots(3, 2, figsize=(12, 14))
#             fig.suptitle(f"Yearly Scatter Comparisons: {stn_name}", fontsize=16, fontweight='bold')
            
#             for col, yr in enumerate([yr1, yr2]):
#                 if yr is None:
#                     for r in range(3): axes[r, col].axis('off')
#                     continue
                
#                 df_yr = merged[merged['Year'] == yr]
                
#                 for r, (obs_col, sim_col, title, _) in enumerate(VARS_TO_PLOT):
#                     ax = axes[r, col]
#                     obs, sim = df_yr[obs_col], df_yr[sim_col]
#                     r2, bias, rmse = calc_metrics(obs, sim)
                    
#                     ax.scatter(obs, sim, alpha=0.2, s=5, c='teal')
#                     mn, mx = min(obs.min(), sim.min()), max(obs.max(), sim.max())
#                     ax.plot([mn, mx], [mn, mx], 'k--', lw=1)
                    
#                     ax.set_title(f"{yr} | {title}\nR²: {r2:.2f} | Bias: {bias:.2f} | RMSE: {rmse:.2f}")
#                     ax.set_xlabel("USCRN Obs"); ax.set_ylabel("NLDAS3")
#                     ax.grid(True, alpha=0.3)
                    
#             plt.tight_layout(rect=[0, 0.03, 1, 0.95])
#             pdf.savefig(fig); plt.close(fig)
            
#         # B. TARGET TIMESERIES (2x2 Grid per target year)
#         for yr in TARGET_TS_YEARS:
#             if yr not in years: continue
            
#             df_yr = merged[merged['Year'] == yr]
#             fig, axes = plt.subplots(2, 2, figsize=(14, 10))
#             fig.suptitle(f"{yr} Time Series: {stn_name}", fontsize=16, fontweight='bold')
            
#             # Temp
#             axes[0,0].plot(df_yr.index, df_yr['T_C_obs'], label='Obs', alpha=0.8)
#             axes[0,0].plot(df_yr.index, df_yr['T_C_sim'], label='NLDAS3', alpha=0.8)
#             axes[0,0].set_title("Temperature (°C)"); axes[0,0].legend()
            
#             # RH
#             axes[0,1].plot(df_yr.index, df_yr['RH_obs'], alpha=0.8)
#             axes[0,1].plot(df_yr.index, df_yr['RH_derived'], alpha=0.8)
#             axes[0,1].set_title("Relative Humidity (%)")
            
#             # Enthalpy
#             axes[1,0].plot(df_yr.index, df_yr['Enthalpy_kJ_kg_obs'], alpha=0.8)
#             axes[1,0].plot(df_yr.index, df_yr['Enthalpy_kJ_kg_sim'], alpha=0.8)
#             axes[1,0].set_title("Enthalpy (kJ/kg)")
            
#             axes[1,1].axis('off') # Leave 4th quadrant empty
#             plt.tight_layout(rect=[0, 0.03, 1, 0.95])
#             pdf.savefig(fig); plt.close(fig)

#         # C. STATION SUMMARY TABLE
#         table_rows = []
        
#         def build_row(df_slice, name):
#             row = [name]
#             for obs_col, sim_col, _, _ in VARS_TO_PLOT:
#                 r2, bias, rmse = calc_metrics(df_slice[obs_col], df_slice[sim_col])
#                 row.extend([f"{r2:.2f}", f"{bias:.2f}", f"{rmse:.2f}"])
#             return row
            
#         table_rows.append(build_row(merged, "OVERALL (All Years)"))
#         for season in ['Winter', 'Spring', 'Summer', 'Fall']:
#             table_rows.append(build_row(merged[merged['Season'] == season], season))
            
#         cols = ["Period", "T R²", "T Bias", "T RMSE", "RH R²", "RH Bias", "RH RMSE", "Enth R²", "Enth Bias", "Enth RMSE"]
#         df_table = pd.DataFrame(table_rows, columns=cols)
#         render_table_page(pdf, df_table, f"{stn_name} Data Summary")

#     # Compile Station Stats to send back
#     station_stats = {
#         'Station': stn_name,
#         'State': state,
#         'Total_Records': total_records,
#         'Missing_T_Pct': (raw_missing_t / total_records) * 100,
#         'Missing_RH_Pct': (raw_missing_rh / total_records) * 100,
#         'Missing_08_10_RH': is_missing_08_10
#     }
    
#     for (obs_col, sim_col, _, key) in VARS_TO_PLOT:
#         station_stats[f'{key}_Bias'] = np.mean(merged[sim_col] - merged[obs_col])
#         station_stats[f'{key}_R2'] = r2_score(merged[obs_col], merged[sim_col])

#     # To save RAM, convert float64 to float32 before sending to main thread
#     for col in merged.select_dtypes(include=['float64']).columns:
#         merged[col] = merged[col].astype('float32')

#     return stn_name, merged, df_extremes, bad_years, station_stats

# # ==========================================
# # MAIN EXECUTION THREAD
# # ==========================================
# if __name__ == '__main__':
#     print(f"Loading extracted JSON datasets from {JSON_DATA_DIR}...")
    
#     # Read and merge all yearly checkpoints dynamically
#     all_nldas_data = {}
#     json_files = glob.glob(os.path.join(JSON_DATA_DIR, '*_extracted.json'))
    
#     for jf_path in json_files:
#         with open(jf_path, 'r') as jf:
#             year_data = json.load(jf)
#             for stn, stn_data in year_data.items():
#                 if stn not in all_nldas_data:
#                     all_nldas_data[stn] = {}
#                 all_nldas_data[stn].update(stn_data)

#     print(f"Data loaded for {len(all_nldas_data)} stations.")

#     station_payloads = []
#     for stn_name in all_nldas_data.keys():
#         stn_file = os.path.join(STATION_DIR, f"{stn_name}.csv")
#         if os.path.exists(stn_file):
#             station_payloads.append((stn_name, stn_file, all_nldas_data[stn_name], OUTPUT_DIR))

#     master_df_list = []
#     all_extremes = []
#     all_bad_years = []
#     all_stats = []

#     max_cores = min(multiprocessing.cpu_count(), len(station_payloads), 32)
#     print(f"\n*** Starting Parallel Processing on {max_cores} Cores ***")
    
#     with ProcessPoolExecutor(max_workers=max_cores) as executor:
#         futures = [executor.submit(process_station, payload) for payload in station_payloads]
#         for i, future in enumerate(as_completed(futures)):
#             stn_name, merged_df, df_ext, bad_yrs, stats = future.result()
            
#             if merged_df is not None: master_df_list.append(merged_df)
#             if df_ext is not None and not df_ext.empty: all_extremes.append(df_ext)
#             if bad_yrs: all_bad_years.extend(bad_yrs)
#             if stats is not None: all_stats.append(stats)
                
#             print(f"Processed {i+1}/{len(station_payloads)}: {stn_name}", end='\r')

#     # SAVE QAQC CSVs
#     print("\n\nSaving QA/QC tracking files...")
#     if all_extremes:
#         pd.concat(all_extremes).to_csv(os.path.join(OUTPUT_DIR, 'extreme_values_tracked.csv'), index=False)
#     if all_bad_years:
#         pd.DataFrame(all_bad_years).to_csv(os.path.join(OUTPUT_DIR, 'dropped_rh_years.csv'), index=False)

#     # ==========================================
#     # MASTER AGGREGATION PDF
#     # ==========================================
#     if master_df_list:
#         print("Generating Master Aggregation PDF...")
#         global_df = pd.concat(master_df_list, ignore_index=True)
#         stats_df = pd.DataFrame(all_stats)
        
#         master_pdf_path = os.path.join(OUTPUT_DIR, "ALL_STATIONS_MASTER_SUMMARY.pdf")
        
#         def get_agg_row(df, label):
#             row = [label, len(df['Station'].unique())]
#             for obs_col, sim_col, _, _ in VARS_TO_PLOT:
#                 r2, bias, rmse = calc_metrics(df[obs_col], df[sim_col])
#                 row.extend([f"{r2:.2f}", f"{bias:.2f}", f"{rmse:.2f}"])
#             return row
            
#         cols = ["Region/State", "Stations", "T R²", "T Bias", "T RMSE", "RH R²", "RH Bias", "RH RMSE", "Enth R²", "Enth Bias", "Enth RMSE"]

#         with PdfPages(master_pdf_path) as pdf:
            
#             # 1. CONUS Overall Table
#             conus_row = get_agg_row(global_df, "CONUS OVERALL")
#             df_conus = pd.DataFrame([conus_row], columns=cols)
#             render_table_page(pdf, df_conus, "CONUS Global Bias Summary")
            
#             # 2. State-by-State Table
#             state_rows = []
#             for state, group in global_df.groupby('State'):
#                 state_rows.append(get_agg_row(group, state))
#             df_state = pd.DataFrame(state_rows, columns=cols)
#             render_table_page(pdf, df_state, "State-by-State Bias Summary")
            
#             # 3. Climate Region Table
#             climate_rows = []
#             for clim, group in global_df.groupby('Climate'):
#                 climate_rows.append(get_agg_row(group, clim))
#             df_climate = pd.DataFrame(climate_rows, columns=cols)
#             render_table_page(pdf, df_climate, "Climate Region Bias Summary")
            
#         print("\nAll operations complete! Check the output directory for your PDFs and CSVs.")
#     else:
#         print("\n[WARNING] No valid data found to generate master summary.")


'''
separates by state and climate and season 

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
# # CONFIGURATION
# # ==========================================
# JSON_DATA_DIR = './nldas_station_reports_sequential/yearly_checkpoints_ALL'
# STATION_DIR = '/discover/nobackup/cmbreen/datacenters/uscrn_independent_data'
# OUTPUT_DIR = './station_comprehensive_reports'
# os.makedirs(OUTPUT_DIR, exist_ok=True)

# P_HPA = 1013.25  

# VARS_TO_PLOT = [('T_C_obs', 'T_C_sim', 'Temp (°C)', 'T_C'),
#                 ('RH_obs', 'RH_derived', 'Rel. Humidity (%)', 'RH'),
#                 ('Enthalpy_kJ_kg_obs', 'Enthalpy_kJ_kg_sim', 'Enthalpy (kJ/kg)', 'Enthalpy')]

# TARGET_TS_YEARS = [2005, 2010, 2015, 2020, 2025]

# # Standard US Climate Regions Mapping
# STATE_TO_CLIMATE = {
#     'WA': 'PNW', 'OR': 'PNW', 'ID': 'PNW',
#     'IL': 'Midwest', 'IN': 'Midwest', 'IA': 'Midwest', 'MI': 'Midwest', 'MN': 'Midwest', 'OH': 'Midwest', 'WI': 'Midwest',
#     'CT': 'New England', 'ME': 'New England', 'MA': 'New England', 'NH': 'New England', 'RI': 'New England', 'VT': 'New England', 'NY': 'New England', 'PA': 'New England', 'NJ': 'New England',
#     'AZ': 'Southwest', 'NM': 'Southwest', 'UT': 'Southwest', 'NV': 'Southwest', 'CA': 'Southwest',
#     'AR': 'South', 'LA': 'South', 'MS': 'South', 'AL': 'South', 'GA': 'South', 'FL': 'South', 'SC': 'South', 'NC': 'South', 'VA': 'South', 'TN': 'South', 'KY': 'South',
#     'ND': 'Plains', 'SD': 'Plains', 'NE': 'Plains', 'KS': 'Plains', 'OK': 'Plains', 'TX': 'Plains', 'MO': 'Plains',
#     'MT': 'Rockies', 'WY': 'Rockies', 'CO': 'Rockies'
# }

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

# def calc_metrics(obs, sim):
#     if len(obs) < 5: return np.nan, np.nan, np.nan
#     r2 = r2_score(obs, sim)
#     bias = np.mean(sim - obs)
#     rmse = np.sqrt(mean_squared_error(obs, sim))
#     return r2, bias, rmse

# def render_table_page(pdf, df, title):
#     fig, ax = plt.subplots(figsize=(14, 6))
#     ax.axis('tight')
#     ax.axis('off')
    
#     table = ax.table(cellText=df.values, colLabels=df.columns, loc='center', cellLoc='center')
#     table.auto_set_font_size(False)
#     table.set_fontsize(10)
#     table.scale(1, 1.5)
    
#     # Bold the headers
#     for (row, col), cell in table.get_celld().items():
#         if row == 0:
#             cell.set_text_props(weight='bold')
            
#     fig.suptitle(title, fontsize=16, fontweight='bold')
#     plt.tight_layout()
#     pdf.savefig(fig)
#     plt.close(fig)

# # ==========================================
# # PARALLEL WORKER FUNCTION
# # ==========================================
# def process_station(worker_payload):
#     stn_name, stn_file, stn_json_data, output_dir = worker_payload
#     state = stn_name.split('_')[0]
#     climate = STATE_TO_CLIMATE.get(state, 'Unknown')
    
#     # 1. LOAD OBSERVATIONS & IDENTIFY EXTREMES
#     df_stn = pd.read_csv(stn_file)
#     df_stn = df_stn.rename(columns={'temperature': 'T_C', 'relative_humidity': 'RH_obs'})
#     df_stn['T_C'] = pd.to_numeric(df_stn['T_C'], errors='coerce')
#     df_stn['RH_obs'] = pd.to_numeric(df_stn['RH_obs'], errors='coerce')
    
#     total_records = len(df_stn)
#     raw_missing_t = df_stn['T_C'].isna().sum()
#     raw_missing_rh = df_stn['RH_obs'].isna().sum()
    
#     # Isolate missing timestamps CSV
#     missing_mask = df_stn[['T_C', 'RH_obs']].isna().any(axis=1)
#     if missing_mask.any():
#         df_missing = df_stn[missing_mask]
#         df_missing[['datetime', 'T_C', 'RH_obs']].to_csv(
#             os.path.join(output_dir, f"{stn_name}_missing_timestamps.csv"), index=False)

#     df_stn['datetime'] = pd.to_datetime(df_stn['datetime'], errors='coerce').dt.tz_localize(None).dt.round('h')
    
#     # Check if 2008-2010 is completely missing for RH
#     rh_08_10 = df_stn[(df_stn['datetime'].dt.year >= 2008) & (df_stn['datetime'].dt.year <= 2010)]['RH_obs']
#     is_missing_08_10 = (rh_08_10.isna().mean() > 0.85) if len(rh_08_10) > 0 else True

#     # Track Extremes
#     ext_mask = (df_stn['T_C'] < -40) | (df_stn['T_C'] > 50) | (df_stn['RH_obs'] < 0) | (df_stn['RH_obs'] > 100)
#     df_extremes = df_stn[ext_mask][['datetime', 'T_C', 'RH_obs']].copy()
#     df_extremes['Station'] = stn_name
    
#     # Clean up station dataset
#     df_stn.loc[ext_mask, ['T_C', 'RH_obs']] = np.nan
#     df_stn = df_stn.set_index('datetime')
#     df_stn = calc_psychrometrics(df_stn, source='station')
    
#     # 2. PARSE NLDAS JSON
#     records = []
#     for ym, days in stn_json_data.items():
#         for date_str, data_dict in days.items():
#             base_dt = pd.to_datetime(date_str, format="%Y%m%d")
#             for h in range(len(data_dict['tair'])):
#                 records.append({'datetime': base_dt + pd.Timedelta(hours=h), 'Tair': data_dict['tair'][h], 'Qair': data_dict['qair'][h]})
                
#     if not records: return stn_name, None, df_extremes, [], None
        
#     df_nldas = pd.DataFrame(records).set_index('datetime')
#     df_nldas['T_C'] = df_nldas['Tair'] - 273.15 if df_nldas['Tair'].mean() > 200 else df_nldas['Tair']
#     df_nldas['Q_kg_kg'] = df_nldas['Qair']
#     df_nldas = calc_psychrometrics(df_nldas, source='nldas')
    
#     # 3. MERGE & QAQC BAD YEARS
#     merged = df_stn[['T_C', 'RH_obs', 'Enthalpy_kJ_kg']].join(
#         df_nldas[['T_C', 'RH_derived', 'Enthalpy_kJ_kg']], lsuffix='_obs', rsuffix='_sim', how='inner'
#     )
    
#     merged['Year'] = merged.index.year
#     merged['Season'] = merged.index.month.map(get_season)
#     merged['Station'] = stn_name
#     merged['State'] = state
#     merged['Climate'] = climate
    
#     # Drop years where RH is <= 0 for > 75% of the year
#     bad_years = []
#     for yr, group in merged.groupby('Year'):
#         valid_rh = group['RH_obs'].dropna()
#         if len(valid_rh) > 0 and (valid_rh <= 0).mean() > 0.75:
#             bad_years.append({'Station': stn_name, 'Year': yr})
            
#     bad_yr_list = [d['Year'] for d in bad_years]
#     merged = merged[~merged['Year'].isin(bad_yr_list)].dropna()

#     if merged.empty: return stn_name, None, df_extremes, bad_years, None

#     # 4. PLOTTING INDIVIDUAL PDF
#     pdf_path = os.path.join(output_dir, f"{stn_name}_analysis.pdf")
#     with PdfPages(pdf_path) as pdf:
        
#         years = sorted(merged['Year'].unique())
        
#         # A. YEARLY SCATTER PLOTS (6 per page = 2 cols x 3 rows)
#         for i in range(0, len(years), 2):
#             yr1 = years[i]
#             yr2 = years[i+1] if i+1 < len(years) else None
            
#             fig, axes = plt.subplots(3, 2, figsize=(12, 14))
#             fig.suptitle(f"Yearly Scatter Comparisons: {stn_name}", fontsize=16, fontweight='bold')
            
#             for col, yr in enumerate([yr1, yr2]):
#                 if yr is None:
#                     for r in range(3): axes[r, col].axis('off')
#                     continue
                
#                 df_yr = merged[merged['Year'] == yr]
                
#                 for r, (obs_col, sim_col, title, _) in enumerate(VARS_TO_PLOT):
#                     ax = axes[r, col]
#                     obs, sim = df_yr[obs_col], df_yr[sim_col]
#                     r2, bias, rmse = calc_metrics(obs, sim)
                    
#                     ax.scatter(obs, sim, alpha=0.2, s=5, c='teal')
#                     mn, mx = min(obs.min(), sim.min()), max(obs.max(), sim.max())
#                     ax.plot([mn, mx], [mn, mx], 'k--', lw=1)
                    
#                     ax.set_title(f"{yr} | {title}\nR²: {r2:.2f} | Bias: {bias:.2f} | RMSE: {rmse:.2f}")
#                     ax.set_xlabel("USCRN Obs"); ax.set_ylabel("NLDAS3")
#                     ax.grid(True, alpha=0.3)
                    
#             plt.tight_layout(rect=[0, 0.03, 1, 0.95])
#             pdf.savefig(fig); plt.close(fig)
            
#         # B. TARGET TIMESERIES (2x2 Grid per target year)
#         for yr in TARGET_TS_YEARS:
#             if yr not in years: continue
            
#             df_yr = merged[merged['Year'] == yr]
#             fig, axes = plt.subplots(2, 2, figsize=(14, 10))
#             fig.suptitle(f"{yr} Time Series: {stn_name}", fontsize=16, fontweight='bold')
            
#             # Temp
#             axes[0,0].plot(df_yr.index, df_yr['T_C_obs'], label='Obs', alpha=0.8)
#             axes[0,0].plot(df_yr.index, df_yr['T_C_sim'], label='NLDAS3', alpha=0.8)
#             axes[0,0].set_title("Temperature (°C)"); axes[0,0].legend()
            
#             # RH
#             axes[0,1].plot(df_yr.index, df_yr['RH_obs'], alpha=0.8)
#             axes[0,1].plot(df_yr.index, df_yr['RH_derived'], alpha=0.8)
#             axes[0,1].set_title("Relative Humidity (%)")
            
#             # Enthalpy
#             axes[1,0].plot(df_yr.index, df_yr['Enthalpy_kJ_kg_obs'], alpha=0.8)
#             axes[1,0].plot(df_yr.index, df_yr['Enthalpy_kJ_kg_sim'], alpha=0.8)
#             axes[1,0].set_title("Enthalpy (kJ/kg)")
            
#             axes[1,1].axis('off') # Leave 4th quadrant empty
#             plt.tight_layout(rect=[0, 0.03, 1, 0.95])
#             pdf.savefig(fig); plt.close(fig)

#         # C. STATION SUMMARY TABLE
#         table_rows = []
        
#         def build_row(df_slice, name):
#             row = [name]
#             for obs_col, sim_col, _, _ in VARS_TO_PLOT:
#                 r2, bias, rmse = calc_metrics(df_slice[obs_col], df_slice[sim_col])
#                 row.extend([f"{r2:.2f}", f"{bias:.2f}", f"{rmse:.2f}"])
#             return row
            
#         table_rows.append(build_row(merged, "OVERALL (All Years)"))
#         for season in ['Winter', 'Spring', 'Summer', 'Fall']:
#             table_rows.append(build_row(merged[merged['Season'] == season], season))
            
#         cols = ["Period", "T R²", "T Bias", "T RMSE", "RH R²", "RH Bias", "RH RMSE", "Enth R²", "Enth Bias", "Enth RMSE"]
#         df_table = pd.DataFrame(table_rows, columns=cols)
#         render_table_page(pdf, df_table, f"{stn_name} Data Summary")

#     # Compile Station Stats to send back
#     station_stats = {
#         'Station': stn_name,
#         'State': state,
#         'Total_Records': total_records,
#         'Missing_T_Pct': (raw_missing_t / total_records) * 100,
#         'Missing_RH_Pct': (raw_missing_rh / total_records) * 100,
#         'Missing_08_10_RH': is_missing_08_10
#     }
    
#     for (obs_col, sim_col, _, key) in VARS_TO_PLOT:
#         station_stats[f'{key}_Bias'] = np.mean(merged[sim_col] - merged[obs_col])
#         station_stats[f'{key}_R2'] = r2_score(merged[obs_col], merged[sim_col])

#     # To save RAM, convert float64 to float32 before sending to main thread
#     for col in merged.select_dtypes(include=['float64']).columns:
#         merged[col] = merged[col].astype('float32')

#     return stn_name, merged, df_extremes, bad_years, station_stats

# # ==========================================
# # MAIN EXECUTION THREAD
# # ==========================================
# if __name__ == '__main__':
#     print(f"Loading extracted JSON datasets from {JSON_DATA_DIR}...")
    
#     # Read and merge all yearly checkpoints dynamically
#     all_nldas_data = {}
#     json_files = glob.glob(os.path.join(JSON_DATA_DIR, '*_extracted.json'))
    
#     for jf_path in json_files:
#         with open(jf_path, 'r') as jf:
#             year_data = json.load(jf)
#             for stn, stn_data in year_data.items():
#                 if stn not in all_nldas_data:
#                     all_nldas_data[stn] = {}
#                 all_nldas_data[stn].update(stn_data)

#     print(f"Data loaded for {len(all_nldas_data)} stations.")

#     station_payloads = []
#     for stn_name in all_nldas_data.keys():
#         stn_file = os.path.join(STATION_DIR, f"{stn_name}.csv")
#         if os.path.exists(stn_file):
#             station_payloads.append((stn_name, stn_file, all_nldas_data[stn_name], OUTPUT_DIR))

#     master_df_list = []
#     all_extremes = []
#     all_bad_years = []
#     all_stats = []

#     max_cores = min(multiprocessing.cpu_count(), len(station_payloads), 32)
#     print(f"\n*** Starting Parallel Processing on {max_cores} Cores ***")
    
#     with ProcessPoolExecutor(max_workers=max_cores) as executor:
#         futures = [executor.submit(process_station, payload) for payload in station_payloads]
#         for i, future in enumerate(as_completed(futures)):
#             stn_name, merged_df, df_ext, bad_yrs, stats = future.result()
            
#             if merged_df is not None: master_df_list.append(merged_df)
#             if df_ext is not None and not df_ext.empty: all_extremes.append(df_ext)
#             if bad_yrs: all_bad_years.extend(bad_yrs)
#             if stats is not None: all_stats.append(stats)
                
#             print(f"Processed {i+1}/{len(station_payloads)}: {stn_name}", end='\r')

#     # SAVE QAQC CSVs
#     print("\n\nSaving QA/QC tracking files...")
#     if all_extremes:
#         pd.concat(all_extremes).to_csv(os.path.join(OUTPUT_DIR, 'extreme_values_tracked.csv'), index=False)
#     if all_bad_years:
#         pd.DataFrame(all_bad_years).to_csv(os.path.join(OUTPUT_DIR, 'dropped_rh_years.csv'), index=False)

#     # ==========================================
#     # MASTER AGGREGATION PDF
#     # ==========================================
#     if master_df_list:
#         print("Generating Master Aggregation PDF...")
#         global_df = pd.concat(master_df_list, ignore_index=True)
#         stats_df = pd.DataFrame(all_stats)
        
#         master_pdf_path = os.path.join(OUTPUT_DIR, "ALL_STATIONS_MASTER_SUMMARY.pdf")
        
#         def get_agg_row(df, label):
#             row = [label, len(df['Station'].unique())]
#             for obs_col, sim_col, _, _ in VARS_TO_PLOT:
#                 r2, bias, rmse = calc_metrics(df[obs_col], df[sim_col])
#                 row.extend([f"{r2:.2f}", f"{bias:.2f}", f"{rmse:.2f}"])
#             return row
            
#         # Base columns, the first header gets swapped out dynamically
#         base_cols = ["Stations", "T R²", "T Bias", "T RMSE", "RH R²", "RH Bias", "RH RMSE", "Enth R²", "Enth Bias", "Enth RMSE"]

#         with PdfPages(master_pdf_path) as pdf:
            
#             # --- 1. OVERALL R2 HEXBIN PLOT (20% SAMPLE) ---
#             print("  -> Plotting Global Scatter (20% Sample)...")
#             df_sampled = global_df.sample(frac=0.4, random_state=42)
            
#             fig, axes = plt.subplots(1, 3, figsize=(18, 6))
#             fig.suptitle("Global CONUS Scatter Plots (20% Random Sample)", fontsize=18, fontweight='bold', y=1.02)
            
#             for ax, (obs_col, sim_col, title, _) in zip(axes, VARS_TO_PLOT):
#                 clean = df_sampled.dropna(subset=[obs_col, sim_col])
#                 if len(clean) > 10:
#                     obs, sim = clean[obs_col], clean[sim_col]
#                     r2, bias, rmse = calc_metrics(obs, sim)
                    
#                     # Hexbin prevents massive PDF file sizes for millions of points
#                     hb = ax.hexbin(obs, sim, gridsize=50, cmap='inferno', mincnt=1, bins='log')
#                     cb = plt.colorbar(hb, ax=ax)
#                     cb.set_label('log10(count)')
                    
#                     mn, mx = min(obs.min(), sim.min()), max(obs.max(), sim.max())
#                     ax.plot([mn, mx], [mn, mx], 'cyan', linestyle='--', lw=2, label='1:1 Line')
                    
#                     ax.set_title(f"Overall {title}\nR²: {r2:.3f} | Bias: {bias:.3f}")
#                     ax.set_xlabel("USCRN Observation"); ax.set_ylabel("NLDAS3")
                    
#                     # Add RMSE to Top Right Corner
#                     bbox_props = dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8, edgecolor='gray')
#                     ax.text(0.95, 0.95, f'RMSE: {rmse:.2f}', transform=ax.transAxes, 
#                             fontsize=12, fontweight='bold', color='black',
#                             ha='right', va='top', bbox=bbox_props)
                    
#                     ax.legend(loc='upper left')
                    
#             plt.tight_layout(rect=[0, 0.03, 1, 0.95])
#             pdf.savefig(fig); plt.close(fig)

#             # --- 2. CONUS Overall Table ---
#             conus_row = get_agg_row(global_df, "CONUS OVERALL")
#             df_conus = pd.DataFrame([conus_row], columns=["Region"] + base_cols)
#             render_table_page(pdf, df_conus, "CONUS Global Bias Summary")
            
#             # --- 3. Seasonal Table ---
#             print("  -> Generating Seasonal Tables...")
#             season_rows = []
#             for season in ['Winter', 'Spring', 'Summer', 'Fall']:
#                 season_data = global_df[global_df['Season'] == season]
#                 if not season_data.empty:
#                     season_rows.append(get_agg_row(season_data, season))
                    
#             if season_rows:
#                 df_season = pd.DataFrame(season_rows, columns=["Season"] + base_cols)
#                 render_table_page(pdf, df_season, "Seasonal Bias Summary (All Data)")

#             # --- 4. State-by-State Table ---
#             print("  -> Generating State Tables...")
#             state_rows = []
#             for state, group in global_df.groupby('State'):
#                 state_rows.append(get_agg_row(group, state))
#             df_state = pd.DataFrame(state_rows, columns=["State"] + base_cols)
#             render_table_page(pdf, df_state, "State-by-State Bias Summary")
            
#             # --- 5. Climate Region Table ---
#             print("  -> Generating Climate Region Tables...")
#             climate_rows = []
#             for clim, group in global_df.groupby('Climate'):
#                 climate_rows.append(get_agg_row(group, clim))
#             df_climate = pd.DataFrame(climate_rows, columns=["Climate Region"] + base_cols)
#             render_table_page(pdf, df_climate, "Climate Region Bias Summary")
            
#         print("\nAll operations complete! Check the output directory for your PDFs and CSVs.")
#     else:
#         print("\n[WARNING] No valid data found to generate master summary.")

'''

adds the statistically significant differences; 
if temp has all 0s it masks it out 
we still have figured out why it is 
not printing negative values for the main summary pdf 

plots everything 

'''

# import os
# import glob
# import json
# import pandas as pd
# import numpy as np
# import matplotlib.pyplot as plt
# from matplotlib.backends.backend_pdf import PdfPages
# from sklearn.metrics import mean_squared_error, r2_score
# import scipy.stats as stats
# import warnings
# from concurrent.futures import ProcessPoolExecutor, as_completed
# import multiprocessing

# warnings.filterwarnings('ignore')

# # ==========================================
# # CONFIGURATION
# # ==========================================
# JSON_DATA_DIR = './nldas_station_reports_sequential/yearly_checkpoints_ALL'
# STATION_DIR = '/discover/nobackup/cmbreen/datacenters/uscrn_independent_data'
# OUTPUT_DIR = './station_comprehensive_reports'
# os.makedirs(OUTPUT_DIR, exist_ok=True)

# P_HPA = 1013.25  

# VARS_TO_PLOT = [('T_C_obs', 'T_C_sim', 'Temp (°C)', 'T_C'),
#                 ('RH_obs', 'RH_derived', 'Rel. Humidity (%)', 'RH'),
#                 ('Enthalpy_kJ_kg_obs', 'Enthalpy_kJ_kg_sim', 'Enthalpy (kJ/kg)', 'Enthalpy')]

# TARGET_TS_YEARS = [2005, 2010, 2015, 2020, 2025]

# # Standard US Climate Regions Mapping
# STATE_TO_CLIMATE = {
#     'WA': 'PNW', 'OR': 'PNW', 'ID': 'PNW',
#     'IL': 'Midwest', 'IN': 'Midwest', 'IA': 'Midwest', 'MI': 'Midwest', 'MN': 'Midwest', 'OH': 'Midwest', 'WI': 'Midwest',
#     'CT': 'New England', 'ME': 'New England', 'MA': 'New England', 'NH': 'New England', 'RI': 'New England', 'VT': 'New England', 'NY': 'New England', 'PA': 'New England', 'NJ': 'New England',
#     'AZ': 'Southwest', 'NM': 'Southwest', 'UT': 'Southwest', 'NV': 'Southwest', 'CA': 'Southwest',
#     'AR': 'South', 'LA': 'South', 'MS': 'South', 'AL': 'South', 'GA': 'South', 'FL': 'South', 'SC': 'South', 'NC': 'South', 'VA': 'South', 'TN': 'South', 'KY': 'South',
#     'ND': 'Plains', 'SD': 'Plains', 'NE': 'Plains', 'KS': 'Plains', 'OK': 'Plains', 'TX': 'Plains', 'MO': 'Plains',
#     'MT': 'Rockies', 'WY': 'Rockies', 'CO': 'Rockies'
# }

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

# def calc_metrics(obs, sim):
#     if len(obs) < 5: return np.nan, np.nan, np.nan
#     r2 = r2_score(obs, sim)
#     bias = np.mean(sim - obs)
#     rmse = np.sqrt(mean_squared_error(obs, sim))
#     return r2, bias, rmse

# def render_table_page(pdf, df, title):
#     fig, ax = plt.subplots(figsize=(14, 6))
#     ax.axis('tight')
#     ax.axis('off')
    
#     table = ax.table(cellText=df.values, colLabels=df.columns, loc='center', cellLoc='center')
#     table.auto_set_font_size(False)
#     table.set_fontsize(10)
#     table.scale(1, 1.5)
    
#     # Bold the headers
#     for (row, col), cell in table.get_celld().items():
#         if row == 0:
#             cell.set_text_props(weight='bold')
            
#     fig.suptitle(title, fontsize=16, fontweight='bold')
#     plt.tight_layout()
#     pdf.savefig(fig)
#     plt.close(fig)

# # ==========================================
# # PARALLEL WORKER FUNCTION
# # ==========================================
# def process_station(worker_payload):
#     stn_name, stn_file, stn_json_data, output_dir = worker_payload
#     state = stn_name.split('_')[0]
#     climate = STATE_TO_CLIMATE.get(state, 'Unknown')
    
#     # 1. LOAD OBSERVATIONS & IDENTIFY EXTREMES
#     df_stn = pd.read_csv(stn_file)
#     df_stn = df_stn.rename(columns={'temperature': 'T_C', 'relative_humidity': 'RH_obs'})
#     df_stn['T_C'] = pd.to_numeric(df_stn['T_C'], errors='coerce')
#     df_stn['RH_obs'] = pd.to_numeric(df_stn['RH_obs'], errors='coerce')
    
#     total_records = len(df_stn)
#     raw_missing_t = df_stn['T_C'].isna().sum()
#     raw_missing_rh = df_stn['RH_obs'].isna().sum()
    
#     # Isolate missing timestamps CSV
#     missing_mask = df_stn[['T_C', 'RH_obs']].isna().any(axis=1)
#     if missing_mask.any():
#         df_missing = df_stn[missing_mask]
#         df_missing[['datetime', 'T_C', 'RH_obs']].to_csv(
#             os.path.join(output_dir, f"{stn_name}_missing_timestamps.csv"), index=False)

#     df_stn['datetime'] = pd.to_datetime(df_stn['datetime'], errors='coerce').dt.tz_localize(None).dt.round('h')
    
#     # Check if 2008-2010 is completely missing for RH
#     rh_08_10 = df_stn[(df_stn['datetime'].dt.year >= 2008) & (df_stn['datetime'].dt.year <= 2010)]['RH_obs']
#     is_missing_08_10 = (rh_08_10.isna().mean() > 0.85) if len(rh_08_10) > 0 else True

#     # SEPARATED EXTREME MASKS
#     ext_mask_T = (df_stn['T_C'] < -40) | (df_stn['T_C'] > 120)
#     ext_mask_RH = (df_stn['RH_obs'] < 0) | (df_stn['RH_obs'] > 100)
    
#     df_extremes = df_stn[ext_mask_T | ext_mask_RH][['datetime', 'T_C', 'RH_obs']].copy()
#     df_extremes['Station'] = stn_name
    
#     # Apply NaNs Independently
#     df_stn.loc[ext_mask_T, 'T_C'] = np.nan
#     df_stn.loc[ext_mask_RH, 'RH_obs'] = np.nan
    
#     df_stn = df_stn.set_index('datetime')
#     df_stn = calc_psychrometrics(df_stn, source='station')
    
#     # 2. PARSE NLDAS JSON
#     records = []
#     for ym, days in stn_json_data.items():
#         for date_str, data_dict in days.items():
#             base_dt = pd.to_datetime(date_str, format="%Y%m%d")
#             for h in range(len(data_dict['tair'])):
#                 records.append({'datetime': base_dt + pd.Timedelta(hours=h), 'Tair': data_dict['tair'][h], 'Qair': data_dict['qair'][h]})
                
#     if not records: return stn_name, None, df_extremes, [], None
        
#     df_nldas = pd.DataFrame(records).set_index('datetime')
#     df_nldas['T_C'] = df_nldas['Tair'] - 273.15 if df_nldas['Tair'].mean() > 200 else df_nldas['Tair']
#     df_nldas['Q_kg_kg'] = df_nldas['Qair']
#     df_nldas = calc_psychrometrics(df_nldas, source='nldas')
    
#     # 3. MERGE & QAQC BAD YEARS
#     merged = df_stn[['T_C', 'RH_obs', 'Enthalpy_kJ_kg']].join(
#         df_nldas[['T_C', 'RH_derived', 'Enthalpy_kJ_kg']], lsuffix='_obs', rsuffix='_sim', how='inner'
#     )
    
#     merged['Year'] = merged.index.year
#     merged['Season'] = merged.index.month.map(get_season)
#     merged['Station'] = stn_name
#     merged['State'] = state
#     merged['Climate'] = climate
    
#     # --- UPDATED QA/QC LOOP ---
#     bad_years = []
#     for yr, group in merged.groupby('Year'):
#         valid_rh = group['RH_obs'].dropna()
#         valid_t = group['T_C_obs'].dropna()
        
#         is_bad_rh = len(valid_rh) > 0 and (valid_rh <= 0).mean() > 0.75
#         is_bad_t = len(valid_t) > 0 and (valid_t == 0.0).all() # All valid records for the year are exactly 0.0
        
#         if is_bad_rh or is_bad_t:
#             reasons = []
#             if is_bad_rh: reasons.append("Bad RH")
#             if is_bad_t: reasons.append("Bad Temp (All 0s)")
            
#             bad_years.append({
#                 'Station': stn_name, 
#                 'Year': yr, 
#                 'Reason': " & ".join(reasons)
#             })
            
#     bad_yr_list = [d['Year'] for d in bad_years]
#     merged = merged[~merged['Year'].isin(bad_yr_list)].dropna(how='all', subset=['T_C_obs', 'RH_obs'])

#     if merged.empty: return stn_name, None, df_extremes, bad_years, None

#     # 4. PLOTTING INDIVIDUAL PDF
#     pdf_path = os.path.join(output_dir, f"{stn_name}_analysis.pdf")
#     with PdfPages(pdf_path) as pdf:
        
#         years = sorted(merged['Year'].unique())
        
#         # A. YEARLY SCATTER PLOTS 
#         for i in range(0, len(years), 2):
#             yr1 = years[i]
#             yr2 = years[i+1] if i+1 < len(years) else None
            
#             fig, axes = plt.subplots(3, 2, figsize=(12, 14))
#             fig.suptitle(f"Yearly Scatter Comparisons: {stn_name}", fontsize=16, fontweight='bold')
            
#             for col, yr in enumerate([yr1, yr2]):
#                 if yr is None:
#                     for r in range(3): axes[r, col].axis('off')
#                     continue
                
#                 df_yr = merged[merged['Year'] == yr]
                
#                 for r, (obs_col, sim_col, title, _) in enumerate(VARS_TO_PLOT):
#                     ax = axes[r, col]
#                     clean_yr = df_yr.dropna(subset=[obs_col, sim_col])
#                     if len(clean_yr) < 5: continue
                        
#                     obs, sim = clean_yr[obs_col], clean_yr[sim_col]
#                     r2, bias, rmse = calc_metrics(obs, sim)
                    
#                     ax.scatter(obs, sim, alpha=0.2, s=5, c='teal')
#                     mn, mx = min(obs.min(), sim.min()), max(obs.max(), sim.max())
#                     ax.plot([mn, mx], [mn, mx], 'k--', lw=1)
                    
#                     ax.set_title(f"{yr} | {title}\nR²: {r2:.2f} | Bias: {bias:.2f} | RMSE: {rmse:.2f}")
#                     ax.set_xlabel("USCRN Obs"); ax.set_ylabel("NLDAS3")
#                     ax.grid(True, alpha=0.3)
                    
#             plt.tight_layout(rect=[0, 0.03, 1, 0.95])
#             pdf.savefig(fig); plt.close(fig)
            
#         # B. TARGET TIMESERIES 
#         for yr in TARGET_TS_YEARS:
#             if yr not in years: continue
            
#             df_yr = merged[merged['Year'] == yr]
#             fig, axes = plt.subplots(2, 2, figsize=(14, 10))
#             fig.suptitle(f"{yr} Time Series: {stn_name}", fontsize=16, fontweight='bold')
            
#             axes[0,0].plot(df_yr.index, df_yr['T_C_obs'], label='Obs', alpha=0.8)
#             axes[0,0].plot(df_yr.index, df_yr['T_C_sim'], label='NLDAS3', alpha=0.8)
#             axes[0,0].set_title("Temperature (°C)"); axes[0,0].legend()
            
#             axes[0,1].plot(df_yr.index, df_yr['RH_obs'], alpha=0.8)
#             axes[0,1].plot(df_yr.index, df_yr['RH_derived'], alpha=0.8)
#             axes[0,1].set_title("Relative Humidity (%)")
            
#             axes[1,0].plot(df_yr.index, df_yr['Enthalpy_kJ_kg_obs'], alpha=0.8)
#             axes[1,0].plot(df_yr.index, df_yr['Enthalpy_kJ_kg_sim'], alpha=0.8)
#             axes[1,0].set_title("Enthalpy (kJ/kg)")
            
#             axes[1,1].axis('off') 
#             plt.tight_layout(rect=[0, 0.03, 1, 0.95])
#             pdf.savefig(fig); plt.close(fig)

#         # C. STATION SUMMARY TABLE
#         table_rows = []
        
#         def build_row(df_slice, name):
#             row = [name]
#             for obs_col, sim_col, _, _ in VARS_TO_PLOT:
#                 clean_slice = df_slice.dropna(subset=[obs_col, sim_col])
#                 r2, bias, rmse = calc_metrics(clean_slice[obs_col], clean_slice[sim_col])
#                 row.extend([f"{r2:.2f}", f"{bias:.2f}", f"{rmse:.2f}"])
#             return row
            
#         table_rows.append(build_row(merged, "OVERALL (All Years)"))
#         for season in ['Winter', 'Spring', 'Summer', 'Fall']:
#             table_rows.append(build_row(merged[merged['Season'] == season], season))
            
#         cols = ["Period", "T R²", "T Bias", "T RMSE", "RH R²", "RH Bias", "RH RMSE", "Enth R²", "Enth Bias", "Enth RMSE"]
#         df_table = pd.DataFrame(table_rows, columns=cols)
#         render_table_page(pdf, df_table, f"{stn_name} Data Summary")

#     # Compile Station Stats 
#     station_stats = {
#         'Station': stn_name,
#         'State': state,
#         'Total_Records': total_records,
#         'Missing_T_Pct': (raw_missing_t / total_records) * 100,
#         'Missing_RH_Pct': (raw_missing_rh / total_records) * 100,
#         'Missing_08_10_RH': is_missing_08_10
#     }
    
#     for (obs_col, sim_col, _, key) in VARS_TO_PLOT:
#         clean_merged = merged.dropna(subset=[obs_col, sim_col])
#         if len(clean_merged) > 0:
#             station_stats[f'{key}_Bias'] = np.mean(clean_merged[sim_col] - clean_merged[obs_col])
#             station_stats[f'{key}_R2'] = r2_score(clean_merged[obs_col], clean_merged[sim_col])

#     for col in merged.select_dtypes(include=['float64']).columns:
#         merged[col] = merged[col].astype('float32')

#     return stn_name, merged, df_extremes, bad_years, station_stats

# # ==========================================
# # MAIN EXECUTION THREAD
# # ==========================================
# if __name__ == '__main__':
#     print(f"Loading extracted JSON datasets from {JSON_DATA_DIR}...")
    
#     all_nldas_data = {}
#     json_files = glob.glob(os.path.join(JSON_DATA_DIR, '*_extracted.json'))
    
#     for jf_path in json_files:
#         with open(jf_path, 'r') as jf:
#             year_data = json.load(jf)
#             for stn, stn_data in year_data.items():
#                 if stn not in all_nldas_data:
#                     all_nldas_data[stn] = {}
#                 all_nldas_data[stn].update(stn_data)

#     print(f"Data loaded for {len(all_nldas_data)} stations.")

#     station_payloads = []
#     for stn_name in all_nldas_data.keys():
#         stn_file = os.path.join(STATION_DIR, f"{stn_name}.csv")
#         if os.path.exists(stn_file):
#             station_payloads.append((stn_name, stn_file, all_nldas_data[stn_name], OUTPUT_DIR))

#     master_df_list = []
#     all_extremes = []
#     all_bad_years = []
#     all_stats = []

#     max_cores = min(multiprocessing.cpu_count(), len(station_payloads), 32)
#     print(f"\n*** Starting Parallel Processing on {max_cores} Cores ***")
    
#     with ProcessPoolExecutor(max_workers=max_cores) as executor:
#         futures = [executor.submit(process_station, payload) for payload in station_payloads]
#         for i, future in enumerate(as_completed(futures)):
#             stn_name, merged_df, df_ext, bad_yrs, stats = future.result()
            
#             if merged_df is not None: master_df_list.append(merged_df)
#             if df_ext is not None and not df_ext.empty: all_extremes.append(df_ext)
#             if bad_yrs: all_bad_years.extend(bad_yrs)
#             if stats is not None: all_stats.append(stats)
                
#             print(f"Processed {i+1}/{len(station_payloads)}: {stn_name}", end='\r')

#     print("\n\nSaving QA/QC tracking files...")
#     if all_extremes:
#         pd.concat(all_extremes).to_csv(os.path.join(OUTPUT_DIR, 'extreme_values_tracked.csv'), index=False)
#     if all_bad_years:
#         pd.DataFrame(all_bad_years).to_csv(os.path.join(OUTPUT_DIR, 'dropped_station_years.csv'), index=False)

#     # ==========================================
#     # MASTER AGGREGATION PDF
#     # ==========================================
#     if master_df_list:
#         print("Generating Master Aggregation PDF...")
#         global_df = pd.concat(master_df_list, ignore_index=True)
#         stats_df = pd.DataFrame(all_stats)
        
#         master_pdf_path = os.path.join(OUTPUT_DIR, "ALL_STATIONS_MASTER_SUMMARY.pdf")
        
#         def get_agg_row(df, label):
#             row = [label, len(df['Station'].unique())]
#             for obs_col, sim_col, _, _ in VARS_TO_PLOT:
#                 clean_df = df.dropna(subset=[obs_col, sim_col])
#                 r2, bias, rmse = calc_metrics(clean_df[obs_col], clean_df[sim_col])
#                 row.extend([f"{r2:.2f}", f"{bias:.2f}", f"{rmse:.2f}"])
#             return row
            
#         base_cols = ["Stations", "T R²", "T Bias", "T RMSE", "RH R²", "RH Bias", "RH RMSE", "Enth R²", "Enth Bias", "Enth RMSE"]

#         with PdfPages(master_pdf_path) as pdf:
            
#             # --- 1. OVERALL SCATTER PLOT (100% OF DATA, NO SAMPLING) ---
#             print("  -> Plotting Global Scatter (100% Full Data)...")
            
#             fig, axes = plt.subplots(1, 3, figsize=(18, 6))
#             fig.suptitle("Global CONUS Scatter Plots (Full Dataset)", fontsize=18, fontweight='bold', y=1.02)
            
#             for ax, (obs_col, sim_col, title, _) in zip(axes, VARS_TO_PLOT):
#                 clean = global_df.dropna(subset=[obs_col, sim_col])
#                 if len(clean) > 10:
#                     obs, sim = clean[obs_col], clean[sim_col]
#                     r2, bias, rmse = calc_metrics(obs, sim)
                    
#                     mn, mx = min(obs.min(), sim.min()), max(obs.max(), sim.max())
                    
#                     hb = ax.hexbin(obs, sim, gridsize=100, cmap='turbo', mincnt=1, bins='log', extent=(mn, mx, mn, mx))
#                     cb = plt.colorbar(hb, ax=ax)
#                     cb.set_label('log10(count)')
                    
#                     ax.plot([mn, mx], [mn, mx], 'black', linestyle='--', lw=2, label='1:1 Line')
                    
#                     ax.set_xlim(mn, mx)
#                     ax.set_ylim(mn, mx)
                    
#                     ax.set_title(f"Overall {title}\nR²: {r2:.3f} | Bias: {bias:.3f}")
#                     ax.set_xlabel("USCRN Observation")
#                     ax.set_ylabel("NLDAS3")
                    
#                     bbox_props = dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.9, edgecolor='gray')
#                     ax.text(0.95, 0.05, f'RMSE: {rmse:.2f}', transform=ax.transAxes, 
#                             fontsize=12, fontweight='bold', color='black',
#                             ha='right', va='bottom', bbox=bbox_props)
                    
#                     ax.legend(loc='upper left')
                    
#             plt.tight_layout(rect=[0, 0.03, 1, 0.95])
#             pdf.savefig(fig); plt.close(fig)

#             # --- 2. CONUS Overall Table ---
#             conus_row = get_agg_row(global_df, "CONUS OVERALL")
#             df_conus = pd.DataFrame([conus_row], columns=["Region"] + base_cols)
#             render_table_page(pdf, df_conus, "CONUS Global Bias Summary")
            
#             # --- 3. Seasonal Table ---
#             print("  -> Generating Seasonal Tables...")
#             season_rows = []
#             for season in ['Winter', 'Spring', 'Summer', 'Fall']:
#                 season_data = global_df[global_df['Season'] == season]
#                 if not season_data.empty:
#                     season_rows.append(get_agg_row(season_data, season))
                    
#             if season_rows:
#                 df_season = pd.DataFrame(season_rows, columns=["Season"] + base_cols)
#                 render_table_page(pdf, df_season, "Seasonal Bias Summary (All Data)")

#             # --- 4. State-by-State Table ---
#             print("  -> Generating State Tables...")
#             state_rows = []
#             for state, group in global_df.groupby('State'):
#                 state_rows.append(get_agg_row(group, state))
#             df_state = pd.DataFrame(state_rows, columns=["State"] + base_cols)
#             render_table_page(pdf, df_state, "State-by-State Bias Summary")
            
#             # --- 5. Climate Region Table ---
#             print("  -> Generating Climate Region Tables...")
#             climate_rows = []
#             for clim, group in global_df.groupby('Climate'):
#                 climate_rows.append(get_agg_row(group, clim))
#             df_climate = pd.DataFrame(climate_rows, columns=["Climate Region"] + base_cols)
#             render_table_page(pdf, df_climate, "Climate Region Bias Summary")

#             # --- 6. STATISTICAL SIGNIFICANCE (ANOVA) TABLES ---
#             print("  -> Running Statistical Significance (ANOVA) Tests...")
#             sig_rows = []
            
#             for grouping in ['Season', 'State', 'Climate']:
#                 row = [grouping]
#                 for obs_col, sim_col, _, _ in VARS_TO_PLOT:
#                     err_series = global_df[sim_col] - global_df[obs_col]
                    
#                     grouped_errs = [group.dropna().values for name, group in err_series.groupby(global_df[grouping])]
#                     grouped_errs = [g for g in grouped_errs if len(g) > 1] 
                    
#                     if len(grouped_errs) >= 2:
#                         f_stat, p_val = stats.f_oneway(*grouped_errs)
#                         p_str = "< 0.001" if p_val < 0.001 else f"{p_val:.3f}"
#                     else:
#                         p_str = "N/A"
                        
#                     row.append(p_str)
#                 sig_rows.append(row)
                
#             df_sig = pd.DataFrame(sig_rows, columns=["Grouping", "Temp Bias P-Val", "RH Bias P-Val", "Enthalpy Bias P-Val"])
#             render_table_page(pdf, df_sig, "ANOVA P-Values: Are Mean Biases Significantly Different?")
            
#         print("\nAll operations complete! Check the output directory for your PDFs and CSVs.")
#     else:
#         print("\n[WARNING] No valid data found to generate master summary.")


'''

add elevation
statistically significant differences 
we still have figured out why it is 
not printing negative values for the main summary pdf 

if this gets slow, we can add the elevation to the uscrn data directly 

'''

# import os
# import glob
# import json
# import pandas as pd
# import numpy as np
# import requests
# import random
# import time
# import matplotlib.subplots
# import matplotlib.pyplot as plt
# from matplotlib.backends.backend_pdf import PdfPages
# from sklearn.metrics import mean_squared_error, r2_score
# import scipy.stats as stats
# import warnings
# from concurrent.futures import ProcessPoolExecutor, as_completed
# import multiprocessing

# warnings.filterwarnings('ignore')

# # ==========================================
# # CONFIGURATION
# # ==========================================
# JSON_DATA_DIR = './nldas_station_reports_sequential/yearly_checkpoints_ALL'
# STATION_DIR = '/discover/nobackup/cmbreen/datacenters/uscrn_independent_data'
# OUTPUT_DIR = './station_comprehensive_reports'
# os.makedirs(OUTPUT_DIR, exist_ok=True)

# VARS_TO_PLOT = [('T_C_obs', 'T_C_sim', 'Temp (°C)', 'T_C'),
#                 ('RH_obs', 'RH_derived', 'Rel. Humidity (%)', 'RH'),
#                 ('Enthalpy_kJ_kg_obs', 'Enthalpy_kJ_kg_sim', 'Enthalpy (kJ/kg)', 'Enthalpy')]

# TARGET_TS_YEARS = [2005, 2010, 2015, 2020, 2025]

# # Standard US Climate Regions Mapping
# STATE_TO_CLIMATE = {
#     'WA': 'PNW', 'OR': 'PNW', 'ID': 'PNW',
#     'IL': 'Midwest', 'IN': 'Midwest', 'IA': 'Midwest', 'MI': 'Midwest', 'MN': 'Midwest', 'OH': 'Midwest', 'WI': 'Midwest',
#     'CT': 'New England', 'ME': 'New England', 'MA': 'New England', 'NH': 'New England', 'RI': 'New England', 'VT': 'New England', 'NY': 'New England', 'PA': 'New England', 'NJ': 'New England',
#     'AZ': 'Southwest', 'NM': 'Southwest', 'UT': 'Southwest', 'NV': 'Southwest', 'CA': 'Southwest',
#     'AR': 'South', 'LA': 'South', 'MS': 'South', 'AL': 'South', 'GA': 'South', 'FL': 'South', 'SC': 'South', 'NC': 'South', 'VA': 'South', 'TN': 'South', 'KY': 'South',
#     'ND': 'Plains', 'SD': 'Plains', 'NE': 'Plains', 'KS': 'Plains', 'OK': 'Plains', 'TX': 'Plains', 'MO': 'Plains',
#     'MT': 'Rockies', 'WY': 'Rockies', 'CO': 'Rockies'
# }

# # ==========================================
# # HELPER FUNCTIONS
# # ==========================================
# def get_elevation(lat, lon):
#     """Fetches elevation from Open-Meteo with a slight delay to avoid rate limiting in parallel."""
#     time.sleep(random.uniform(0.1, 0.5))
#     try:
#         url = f"https://api.open-meteo.com/v1/elevation?latitude={lat}&longitude={lon}"
#         r = requests.get(url, timeout=10)
#         if r.status_code == 200:
#             return float(r.json()['elevation'][0])
#     except Exception:
#         pass
#     return 0.0  # Fallback to sea level if the API call fails

# def calc_psychrometrics(df, source='station', elevation_m=0):
#     """Calculates psychrometrics dynamically adjusted for station elevation."""
#     # Standard Barometric Formula to estimate station pressure
#     p_hpa_local = 1013.25 * (1 - 2.25577e-5 * elevation_m)**5.25588
    
#     e_s = 6.112 * np.exp((17.67 * df['T_C']) / (df['T_C'] + 243.5))
    
#     if source == 'nldas':
#         e = (df['Q_kg_kg'] * p_hpa_local) / (0.622 + 0.378 * df['Q_kg_kg'])
#         df['RH_derived'] = np.clip(100.0 * (e / e_s), 0, 100)
#     elif source == 'station':
#         e = e_s * (df['RH_obs'] / 100.0)
#         df['Q_derived'] = (0.622 * e) / (p_hpa_local - 0.378 * e)
#         df['Q_kg_kg'] = df['Q_derived'] 
        
#     df['Enthalpy_kJ_kg'] = 1.006 * df['T_C'] + df['Q_kg_kg'] * (2501 + 1.86 * df['T_C'])
#     return df

# def get_season(month):
#     if month in [12, 1, 2]: return 'Winter'
#     elif month in [3, 4, 5]: return 'Spring'
#     elif month in [6, 7, 8]: return 'Summer'
#     else: return 'Fall'

# def calc_metrics(obs, sim):
#     if len(obs) < 5: return np.nan, np.nan, np.nan
#     r2 = r2_score(obs, sim)
#     bias = np.mean(sim - obs)
#     rmse = np.sqrt(mean_squared_error(obs, sim))
#     return r2, bias, rmse

# def render_table_page(pdf, df, title):
#     fig, ax = plt.subplots(figsize=(14, 6))
#     ax.axis('tight')
#     ax.axis('off')
    
#     table = ax.table(cellText=df.values, colLabels=df.columns, loc='center', cellLoc='center')
#     table.auto_set_font_size(False)
#     table.set_fontsize(10)
#     table.scale(1, 1.5)
    
#     # Bold the headers
#     for (row, col), cell in table.get_celld().items():
#         if row == 0:
#             cell.set_text_props(weight='bold')
            
#     fig.suptitle(title, fontsize=16, fontweight='bold')
#     plt.tight_layout()
#     pdf.savefig(fig)
#     plt.close(fig)

# # ==========================================
# # PARALLEL WORKER FUNCTION
# # ==========================================
# def process_station(worker_payload):
#     stn_name, stn_file, stn_json_data, output_dir = worker_payload
#     state = stn_name.split('_')[0]
#     climate = STATE_TO_CLIMATE.get(state, 'Unknown')
    
#     # 1. LOAD OBSERVATIONS & IDENTIFY EXTREMES
#     df_stn = pd.read_csv(stn_file)
#     df_stn = df_stn.rename(columns={'temperature': 'T_C', 'relative_humidity': 'RH_obs'})
#     df_stn['T_C'] = pd.to_numeric(df_stn['T_C'], errors='coerce')
#     df_stn['RH_obs'] = pd.to_numeric(df_stn['RH_obs'], errors='coerce')
    
#     # Extract Latitude and Longitude to fetch Elevation
#     lat = df_stn['latitude'].dropna().iloc[0] if 'latitude' in df_stn.columns and not df_stn['latitude'].dropna().empty else np.nan
#     lon = df_stn['longitude'].dropna().iloc[0] if 'longitude' in df_stn.columns and not df_stn['longitude'].dropna().empty else np.nan
    
#     elevation_m = 0.0
#     if pd.notna(lat) and pd.notna(lon):
#         elevation_m = get_elevation(lat, lon)
    
#     total_records = len(df_stn)
#     raw_missing_t = df_stn['T_C'].isna().sum()
#     raw_missing_rh = df_stn['RH_obs'].isna().sum()
    
#     # Isolate missing timestamps CSV
#     missing_mask = df_stn[['T_C', 'RH_obs']].isna().any(axis=1)
#     if missing_mask.any():
#         df_missing = df_stn[missing_mask]
#         df_missing[['datetime', 'T_C', 'RH_obs']].to_csv(
#             os.path.join(output_dir, f"{stn_name}_missing_timestamps.csv"), index=False)

#     df_stn['datetime'] = pd.to_datetime(df_stn['datetime'], errors='coerce').dt.tz_localize(None).dt.round('h')
    
#     # Check if 2008-2010 is completely missing for RH
#     rh_08_10 = df_stn[(df_stn['datetime'].dt.year >= 2008) & (df_stn['datetime'].dt.year <= 2010)]['RH_obs']
#     is_missing_08_10 = (rh_08_10.isna().mean() > 0.85) if len(rh_08_10) > 0 else True

#     # SEPARATED EXTREME MASKS
#     ext_mask_T = (df_stn['T_C'] < -40) | (df_stn['T_C'] > 120)
#     ext_mask_RH = (df_stn['RH_obs'] < 0) | (df_stn['RH_obs'] > 100)
    
#     df_extremes = df_stn[ext_mask_T | ext_mask_RH][['datetime', 'T_C', 'RH_obs']].copy()
#     df_extremes['Station'] = stn_name
    
#     # Apply NaNs Independently
#     df_stn.loc[ext_mask_T, 'T_C'] = np.nan
#     df_stn.loc[ext_mask_RH, 'RH_obs'] = np.nan
    
#     df_stn = df_stn.set_index('datetime')
#     # Apply station psychrometrics WITH dynamically fetched elevation
#     df_stn = calc_psychrometrics(df_stn, source='station', elevation_m=elevation_m)
    
#     # 2. PARSE NLDAS JSON
#     records = []
#     for ym, days in stn_json_data.items():
#         for date_str, data_dict in days.items():
#             base_dt = pd.to_datetime(date_str, format="%Y%m%d")
#             for h in range(len(data_dict['tair'])):
#                 records.append({'datetime': base_dt + pd.Timedelta(hours=h), 'Tair': data_dict['tair'][h], 'Qair': data_dict['qair'][h]})
                
#     if not records: return stn_name, None, df_extremes, [], None
        
#     df_nldas = pd.DataFrame(records).set_index('datetime')
#     df_nldas['T_C'] = df_nldas['Tair'] - 273.15 if df_nldas['Tair'].mean() > 200 else df_nldas['Tair']
#     df_nldas['Q_kg_kg'] = df_nldas['Qair']
    
#     # Apply NLDAS psychrometrics WITH dynamically fetched elevation
#     df_nldas = calc_psychrometrics(df_nldas, source='nldas', elevation_m=elevation_m)
    
#     # 3. MERGE & QAQC BAD YEARS
#     merged = df_stn[['T_C', 'RH_obs', 'Enthalpy_kJ_kg']].join(
#         df_nldas[['T_C', 'RH_derived', 'Enthalpy_kJ_kg']], lsuffix='_obs', rsuffix='_sim', how='inner'
#     )
    
#     merged['Year'] = merged.index.year
#     merged['Season'] = merged.index.month.map(get_season)
#     merged['Station'] = stn_name
#     merged['State'] = state
#     merged['Climate'] = climate
    
#     # QA/QC LOOP
#     bad_years = []
#     for yr, group in merged.groupby('Year'):
#         valid_rh = group['RH_obs'].dropna()
#         valid_t = group['T_C_obs'].dropna()
        
#         is_bad_rh = len(valid_rh) > 0 and (valid_rh <= 0).mean() > 0.75
#         is_bad_t = len(valid_t) > 0 and (valid_t == 0.0).all()
        
#         if is_bad_rh or is_bad_t:
#             reasons = []
#             if is_bad_rh: reasons.append("Bad RH")
#             if is_bad_t: reasons.append("Bad Temp (All 0s)")
            
#             bad_years.append({
#                 'Station': stn_name, 
#                 'Year': yr, 
#                 'Reason': " & ".join(reasons)
#             })
            
#     bad_yr_list = [d['Year'] for d in bad_years]
#     merged = merged[~merged['Year'].isin(bad_yr_list)].dropna(how='all', subset=['T_C_obs', 'RH_obs'])

#     if merged.empty: return stn_name, None, df_extremes, bad_years, None

#     # 4. PLOTTING INDIVIDUAL PDF
#     pdf_path = os.path.join(output_dir, f"{stn_name}_analysis.pdf")
#     with PdfPages(pdf_path) as pdf:
        
#         years = sorted(merged['Year'].unique())
        
#         # A. YEARLY SCATTER PLOTS 
#         for i in range(0, len(years), 2):
#             yr1 = years[i]
#             yr2 = years[i+1] if i+1 < len(years) else None
            
#             fig, axes = plt.subplots(3, 2, figsize=(12, 14))
#             fig.suptitle(f"Yearly Scatter Comparisons: {stn_name}\nElevation: {elevation_m:.1f} m", fontsize=16, fontweight='bold')
            
#             for col, yr in enumerate([yr1, yr2]):
#                 if yr is None:
#                     for r in range(3): axes[r, col].axis('off')
#                     continue
                
#                 df_yr = merged[merged['Year'] == yr]
                
#                 for r, (obs_col, sim_col, title, _) in enumerate(VARS_TO_PLOT):
#                     ax = axes[r, col]
#                     clean_yr = df_yr.dropna(subset=[obs_col, sim_col])
#                     if len(clean_yr) < 5: continue
                        
#                     obs, sim = clean_yr[obs_col], clean_yr[sim_col]
#                     r2, bias, rmse = calc_metrics(obs, sim)
                    
#                     ax.scatter(obs, sim, alpha=0.2, s=5, c='teal')
#                     mn, mx = min(obs.min(), sim.min()), max(obs.max(), sim.max())
#                     ax.plot([mn, mx], [mn, mx], 'k--', lw=1)
                    
#                     ax.set_title(f"{yr} | {title}\nR²: {r2:.2f} | Bias: {bias:.2f} | RMSE: {rmse:.2f}")
#                     ax.set_xlabel("USCRN Obs"); ax.set_ylabel("NLDAS3")
#                     ax.grid(True, alpha=0.3)
                    
#             plt.tight_layout(rect=[0, 0.03, 1, 0.95])
#             pdf.savefig(fig); plt.close(fig)
            
#         # B. TARGET TIMESERIES 
#         for yr in TARGET_TS_YEARS:
#             if yr not in years: continue
            
#             df_yr = merged[merged['Year'] == yr]
#             fig, axes = plt.subplots(2, 2, figsize=(14, 10))
#             fig.suptitle(f"{yr} Time Series: {stn_name}", fontsize=16, fontweight='bold')
            
#             axes[0,0].plot(df_yr.index, df_yr['T_C_obs'], label='Obs', alpha=0.8)
#             axes[0,0].plot(df_yr.index, df_yr['T_C_sim'], label='NLDAS3', alpha=0.8)
#             axes[0,0].set_title("Temperature (°C)"); axes[0,0].legend()
            
#             axes[0,1].plot(df_yr.index, df_yr['RH_obs'], alpha=0.8)
#             axes[0,1].plot(df_yr.index, df_yr['RH_derived'], alpha=0.8)
#             axes[0,1].set_title("Relative Humidity (%)")
            
#             axes[1,0].plot(df_yr.index, df_yr['Enthalpy_kJ_kg_obs'], alpha=0.8)
#             axes[1,0].plot(df_yr.index, df_yr['Enthalpy_kJ_kg_sim'], alpha=0.8)
#             axes[1,0].set_title("Enthalpy (kJ/kg)")
            
#             axes[1,1].axis('off') 
#             plt.tight_layout(rect=[0, 0.03, 1, 0.95])
#             pdf.savefig(fig); plt.close(fig)

#         # C. STATION SUMMARY TABLE
#         table_rows = []
        
#         def build_row(df_slice, name):
#             row = [name]
#             for obs_col, sim_col, _, _ in VARS_TO_PLOT:
#                 clean_slice = df_slice.dropna(subset=[obs_col, sim_col])
#                 r2, bias, rmse = calc_metrics(clean_slice[obs_col], clean_slice[sim_col])
#                 row.extend([f"{r2:.2f}", f"{bias:.2f}", f"{rmse:.2f}"])
#             return row
            
#         table_rows.append(build_row(merged, "OVERALL (All Years)"))
#         for season in ['Winter', 'Spring', 'Summer', 'Fall']:
#             table_rows.append(build_row(merged[merged['Season'] == season], season))
            
#         cols = ["Period", "T R²", "T Bias", "T RMSE", "RH R²", "RH Bias", "RH RMSE", "Enth R²", "Enth Bias", "Enth RMSE"]
#         df_table = pd.DataFrame(table_rows, columns=cols)
#         render_table_page(pdf, df_table, f"{stn_name} Data Summary")

#     # Compile Station Stats 
#     station_stats = {
#         'Station': stn_name,
#         'State': state,
#         'Total_Records': total_records,
#         'Missing_T_Pct': (raw_missing_t / total_records) * 100,
#         'Missing_RH_Pct': (raw_missing_rh / total_records) * 100,
#         'Missing_08_10_RH': is_missing_08_10,
#         'Elevation_m': elevation_m
#     }
    
#     for (obs_col, sim_col, _, key) in VARS_TO_PLOT:
#         clean_merged = merged.dropna(subset=[obs_col, sim_col])
#         if len(clean_merged) > 0:
#             station_stats[f'{key}_Bias'] = np.mean(clean_merged[sim_col] - clean_merged[obs_col])
#             station_stats[f'{key}_R2'] = r2_score(clean_merged[obs_col], clean_merged[sim_col])

#     for col in merged.select_dtypes(include=['float64']).columns:
#         merged[col] = merged[col].astype('float32')

#     return stn_name, merged, df_extremes, bad_years, station_stats

# # ==========================================
# # MAIN EXECUTION THREAD
# # ==========================================
# if __name__ == '__main__':
#     print(f"Loading extracted JSON datasets from {JSON_DATA_DIR}...")
    
#     all_nldas_data = {}
#     json_files = glob.glob(os.path.join(JSON_DATA_DIR, '*_extracted.json'))
    
#     for jf_path in json_files:
#         with open(jf_path, 'r') as jf:
#             year_data = json.load(jf)
#             for stn, stn_data in year_data.items():
#                 if stn not in all_nldas_data:
#                     all_nldas_data[stn] = {}
#                 all_nldas_data[stn].update(stn_data)

#     print(f"Data loaded for {len(all_nldas_data)} stations.")

#     station_payloads = []
#     for stn_name in all_nldas_data.keys():
#         stn_file = os.path.join(STATION_DIR, f"{stn_name}.csv")
#         if os.path.exists(stn_file):
#             station_payloads.append((stn_name, stn_file, all_nldas_data[stn_name], OUTPUT_DIR))

#     master_df_list = []
#     all_extremes = []
#     all_bad_years = []
#     all_stats = []

#     max_cores = min(multiprocessing.cpu_count(), len(station_payloads), 32)
#     print(f"\n*** Starting Parallel Processing on {max_cores} Cores ***")
    
#     with ProcessPoolExecutor(max_workers=max_cores) as executor:
#         futures = [executor.submit(process_station, payload) for payload in station_payloads]
#         for i, future in enumerate(as_completed(futures)):
#             stn_name, merged_df, df_ext, bad_yrs, stats = future.result()
            
#             if merged_df is not None: master_df_list.append(merged_df)
#             if df_ext is not None and not df_ext.empty: all_extremes.append(df_ext)
#             if bad_yrs: all_bad_years.extend(bad_yrs)
#             if stats is not None: all_stats.append(stats)
                
#             print(f"Processed {i+1}/{len(station_payloads)}: {stn_name}", end='\r')

#     print("\n\nSaving QA/QC tracking files...")
#     if all_extremes:
#         pd.concat(all_extremes).to_csv(os.path.join(OUTPUT_DIR, 'extreme_values_tracked.csv'), index=False)
#     if all_bad_years:
#         pd.DataFrame(all_bad_years).to_csv(os.path.join(OUTPUT_DIR, 'dropped_station_years.csv'), index=False)

#     # ==========================================
#     # MASTER AGGREGATION PDF
#     # ==========================================
#     if master_df_list:
#         print("Generating Master Aggregation PDF...")
#         global_df = pd.concat(master_df_list, ignore_index=True)
#         stats_df = pd.DataFrame(all_stats)
        
#         # Save master statistics to CSV to easily review elevations later
#         stats_df.to_csv(os.path.join(OUTPUT_DIR, 'master_station_statistics.csv'), index=False)
        
#         master_pdf_path = os.path.join(OUTPUT_DIR, "ALL_STATIONS_MASTER_SUMMARY.pdf")
        
#         def get_agg_row(df, label):
#             row = [label, len(df['Station'].unique())]
#             for obs_col, sim_col, _, _ in VARS_TO_PLOT:
#                 clean_df = df.dropna(subset=[obs_col, sim_col])
#                 r2, bias, rmse = calc_metrics(clean_df[obs_col], clean_df[sim_col])
#                 row.extend([f"{r2:.2f}", f"{bias:.2f}", f"{rmse:.2f}"])
#             return row
            
#         base_cols = ["Stations", "T R²", "T Bias", "T RMSE", "RH R²", "RH Bias", "RH RMSE", "Enth R²", "Enth Bias", "Enth RMSE"]

#         with PdfPages(master_pdf_path) as pdf:
            
#             # --- 1. OVERALL SCATTER PLOT (100% OF DATA, NO SAMPLING) ---
#             print("  -> Plotting Global Scatter (100% Full Data)...")
            
#             fig, axes = plt.subplots(1, 3, figsize=(18, 6))
#             fig.suptitle("Global CONUS Scatter Plots (Full Dataset - Elevation Corrected)", fontsize=18, fontweight='bold', y=1.02)
            
#             for ax, (obs_col, sim_col, title, _) in zip(axes, VARS_TO_PLOT):
#                 clean = global_df.dropna(subset=[obs_col, sim_col])
#                 if len(clean) > 10:
#                     obs, sim = clean[obs_col], clean[sim_col]
#                     r2, bias, rmse = calc_metrics(obs, sim)
                    
#                     mn, mx = min(obs.min(), sim.min()), max(obs.max(), sim.max())
                    
#                     hb = ax.hexbin(obs, sim, gridsize=100, cmap='turbo', mincnt=1, bins='log', extent=(mn, mx, mn, mx))
#                     cb = plt.colorbar(hb, ax=ax)
#                     cb.set_label('log10(count)')
                    
#                     ax.plot([mn, mx], [mn, mx], 'black', linestyle='--', lw=2, label='1:1 Line')
                    
#                     ax.set_xlim(mn, mx)
#                     ax.set_ylim(mn, mx)
                    
#                     ax.set_title(f"Overall {title}\nR²: {r2:.3f} | Bias: {bias:.3f}")
#                     ax.set_xlabel("USCRN Observation")
#                     ax.set_ylabel("NLDAS3")
                    
#                     bbox_props = dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.9, edgecolor='gray')
#                     ax.text(0.95, 0.05, f'RMSE: {rmse:.2f}', transform=ax.transAxes, 
#                             fontsize=12, fontweight='bold', color='black',
#                             ha='right', va='bottom', bbox=bbox_props)
                    
#                     ax.legend(loc='upper left')
                    
#             plt.tight_layout(rect=[0, 0.03, 1, 0.95])
#             pdf.savefig(fig); plt.close(fig)

#             # --- 2. CONUS Overall Table ---
#             conus_row = get_agg_row(global_df, "CONUS OVERALL")
#             df_conus = pd.DataFrame([conus_row], columns=["Region"] + base_cols)
#             render_table_page(pdf, df_conus, "CONUS Global Bias Summary")
            
#             # --- 3. Seasonal Table ---
#             print("  -> Generating Seasonal Tables...")
#             season_rows = []
#             for season in ['Winter', 'Spring', 'Summer', 'Fall']:
#                 season_data = global_df[global_df['Season'] == season]
#                 if not season_data.empty:
#                     season_rows.append(get_agg_row(season_data, season))
                    
#             if season_rows:
#                 df_season = pd.DataFrame(season_rows, columns=["Season"] + base_cols)
#                 render_table_page(pdf, df_season, "Seasonal Bias Summary (All Data)")

#             # --- 4. State-by-State Table ---
#             print("  -> Generating State Tables...")
#             state_rows = []
#             for state, group in global_df.groupby('State'):
#                 state_rows.append(get_agg_row(group, state))
#             df_state = pd.DataFrame(state_rows, columns=["State"] + base_cols)
#             render_table_page(pdf, df_state, "State-by-State Bias Summary")
            
#             # --- 5. Climate Region Table ---
#             print("  -> Generating Climate Region Tables...")
#             climate_rows = []
#             for clim, group in global_df.groupby('Climate'):
#                 climate_rows.append(get_agg_row(group, clim))
#             df_climate = pd.DataFrame(climate_rows, columns=["Climate Region"] + base_cols)
#             render_table_page(pdf, df_climate, "Climate Region Bias Summary")

#             # --- 6. STATISTICAL SIGNIFICANCE (ANOVA) TABLES ---
#             print("  -> Running Statistical Significance (ANOVA) Tests...")
#             sig_rows = []
            
#             for grouping in ['Season', 'State', 'Climate']:
#                 row = [grouping]
#                 for obs_col, sim_col, _, _ in VARS_TO_PLOT:
#                     err_series = global_df[sim_col] - global_df[obs_col]
                    
#                     grouped_errs = [group.dropna().values for name, group in err_series.groupby(global_df[grouping])]
#                     grouped_errs = [g for g in grouped_errs if len(g) > 1] 
                    
#                     if len(grouped_errs) >= 2:
#                         f_stat, p_val = stats.f_oneway(*grouped_errs)
#                         p_str = "< 0.001" if p_val < 0.001 else f"{p_val:.3f}"
#                     else:
#                         p_str = "N/A"
                        
#                     row.append(p_str)
#                 sig_rows.append(row)
                
#             df_sig = pd.DataFrame(sig_rows, columns=["Grouping", "Temp Bias P-Val", "RH Bias P-Val", "Enthalpy Bias P-Val"])
#             render_table_page(pdf, df_sig, "ANOVA P-Values: Are Mean Biases Significantly Different?")
            
#         print("\nAll operations complete! Check the output directory for your PDFs and CSVs.")
#     else:
#         print("\n[WARNING] No valid data found to generate master summary.")


'''
- add in part about the extremes 
- add in the part of the missing data 

still has... 
add elevation
statistically significant differences 
we still have figured out why it is 
not printing negative values for the main summary pdf 

if this gets slow, we can add the elevation to the uscrn data directly 

fixed a one-way stat
'''

import os
import glob
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from sklearn.metrics import mean_squared_error, r2_score
import scipy.stats as stats
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing
import matplotlib.pyplot as plt

# Sets the default font size for EVERYTHING (titles, labels, ticks, legends) to 16
plt.rcParams.update({'font.size': 16})

warnings.filterwarnings('ignore')

# ==========================================
# CONFIGURATION
# ==========================================
JSON_DATA_DIR = './nldas_station_reports_sequential/yearly_checkpoints_ALL'
STATION_DIR = '/discover/nobackup/cmbreen/datacenters/uscrn_independent_data'
OUTPUT_DIR = './station_comprehensive_reports'
os.makedirs(OUTPUT_DIR, exist_ok=True)

VARS_TO_PLOT = [('T_C_obs', 'T_C_sim', 'Temp (°C)', 'T_C'),
                ('RH_obs', 'RH_derived', 'Rel. Humidity (%)', 'RH'),
                ('Enthalpy_kJ_kg_obs', 'Enthalpy_kJ_kg_sim', 'Enthalpy (kJ/kg)', 'Enthalpy')]

TARGET_TS_YEARS = [2005, 2010, 2015, 2020, 2025]

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
    """Calculates psychrometrics. NLDAS uses its own Psurf if available."""
    e_s = 6.112 * np.exp((17.67 * df['T_C']) / (df['T_C'] + 243.5))
    
    if source == 'nldas':
        p_hpa = df['P_hPa'] if 'P_hPa' in df.columns else 1013.25
        e = (df['Q_kg_kg'] * p_hpa) / (0.622 + 0.378 * df['Q_kg_kg'])
        df['RH_derived'] = np.clip(100.0 * (e / e_s), 0, 100)
        
    elif source == 'station':
        p_hpa = 1013.25  
        e = e_s * (df['RH_obs'] / 100.0)
        df['Q_derived'] = (0.622 * e) / (p_hpa - 0.378 * e)
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
    
    for (row, col), cell in table.get_celld().items():
        if row == 0: cell.set_text_props(weight='bold')
            
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
    
    # 1. LOAD OBSERVATIONS 
    df_stn = pd.read_csv(stn_file)
    df_stn = df_stn.rename(columns={'temperature': 'T_C', 'relative_humidity': 'RH_obs'})
    df_stn['T_C'] = pd.to_numeric(df_stn['T_C'], errors='coerce')
    df_stn['RH_obs'] = pd.to_numeric(df_stn['RH_obs'], errors='coerce')
    
    total_records = len(df_stn)
    raw_missing_t = df_stn['T_C'].isna().sum()
    raw_missing_rh = df_stn['RH_obs'].isna().sum()
    
    missing_mask = df_stn[['T_C', 'RH_obs']].isna().any(axis=1)
    if missing_mask.any():
        df_missing = df_stn[missing_mask]
        df_missing[['datetime', 'T_C', 'RH_obs']].to_csv(
            os.path.join(output_dir, f"{stn_name}_missing_timestamps.csv"), index=False)

    df_stn['datetime'] = pd.to_datetime(df_stn['datetime'], errors='coerce').dt.tz_localize(None).dt.round('h')
    
    rh_08_10 = df_stn[(df_stn['datetime'].dt.year >= 2008) & (df_stn['datetime'].dt.year <= 2010)]['RH_obs']
    is_missing_08_10 = (rh_08_10.isna().mean() > 0.85) if len(rh_08_10) > 0 else True

    ext_mask_T = (df_stn['T_C'] < -40) | (df_stn['T_C'] > 120)
    ext_mask_RH = (df_stn['RH_obs'] < 0) | (df_stn['RH_obs'] > 100)
    
    df_extremes = df_stn[ext_mask_T | ext_mask_RH][['datetime', 'T_C', 'RH_obs']].copy()
    df_extremes['Station'] = stn_name
    
    df_stn.loc[ext_mask_T, 'T_C'] = np.nan
    df_stn.loc[ext_mask_RH, 'RH_obs'] = np.nan
    
    df_stn = df_stn.set_index('datetime')
    df_stn = calc_psychrometrics(df_stn, source='station')
    
    # 2. PARSE NLDAS JSON (Now grabbing PSurf!)
    records = []
    for ym, days in stn_json_data.items():
        for date_str, data_dict in days.items():
            base_dt = pd.to_datetime(date_str, format="%Y%m%d")
            has_psurf = 'psurf' in data_dict
            for h in range(len(data_dict['tair'])):
                rec = {
                    'datetime': base_dt + pd.Timedelta(hours=h), 
                    'Tair': data_dict['tair'][h], 
                    'Qair': data_dict['qair'][h]
                }
                if has_psurf:
                    rec['Psurf'] = data_dict['psurf'][h]
                records.append(rec)
                
    if not records: return stn_name, None, df_extremes, [], None
        
    df_nldas = pd.DataFrame(records).set_index('datetime')
    df_nldas['T_C'] = df_nldas['Tair'] - 273.15 if df_nldas['Tair'].mean() > 200 else df_nldas['Tair']
    df_nldas['Q_kg_kg'] = df_nldas['Qair']
    if 'Psurf' in df_nldas.columns:
        df_nldas['P_hPa'] = df_nldas['Psurf'] / 100.0  # Convert Pa to hPa
        
    df_nldas = calc_psychrometrics(df_nldas, source='nldas')
    
    # 3. MERGE & QAQC
    merged = df_stn[['T_C', 'RH_obs', 'Enthalpy_kJ_kg']].join(
        df_nldas[['T_C', 'RH_derived', 'Enthalpy_kJ_kg']], lsuffix='_obs', rsuffix='_sim', how='inner'
    )
    
    merged['Year'] = merged.index.year
    merged['Season'] = merged.index.month.map(get_season)
    merged['Station'] = stn_name
    merged['State'] = state
    merged['Climate'] = climate
    
    bad_years = []
    for yr, group in merged.groupby('Year'):
        valid_rh = group['RH_obs'].dropna()
        valid_t = group['T_C_obs'].dropna()
        
        is_bad_rh = len(valid_rh) > 0 and (valid_rh <= 0).mean() > 0.75
        is_bad_t = len(valid_t) > 0 and (valid_t == 0.0).all()
        
        if is_bad_rh or is_bad_t:
            reasons = []
            if is_bad_rh: reasons.append("Bad RH")
            if is_bad_t: reasons.append("Bad Temp (All 0s)")
            bad_years.append({'Station': stn_name, 'Year': yr, 'Reason': " & ".join(reasons)})
            
    bad_yr_list = [d['Year'] for d in bad_years]
    merged = merged[~merged['Year'].isin(bad_yr_list)].dropna(how='all', subset=['T_C_obs', 'RH_obs'])

    if merged.empty: return stn_name, None, df_extremes, bad_years, None

    # 4. PLOTTING INDIVIDUAL PDF
    pdf_path = os.path.join(output_dir, f"{stn_name}_analysis.pdf")
    with PdfPages(pdf_path) as pdf:
        
        years = sorted(merged['Year'].unique())
        
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
                    clean_yr = df_yr.dropna(subset=[obs_col, sim_col])
                    if len(clean_yr) < 5: continue
                        
                    obs, sim = clean_yr[obs_col], clean_yr[sim_col]
                    r2, bias, rmse = calc_metrics(obs, sim)
                    
                    ax.scatter(obs, sim, alpha=0.2, s=5, c='teal')
                    mn, mx = min(obs.min(), sim.min()), max(obs.max(), sim.max())
                    ax.plot([mn, mx], [mn, mx], 'k--', lw=1)
                    
                    ax.set_title(f"{yr} | {title}\nR²: {r2:.2f} | Bias: {bias:.2f} | RMSE: {rmse:.2f}")
                    ax.set_xlabel("USCRN Obs"); ax.set_ylabel("NLDAS3")
                    ax.grid(True, alpha=0.3)
                    
            plt.tight_layout(rect=[0, 0.03, 1, 0.95])
            pdf.savefig(fig); plt.close(fig)
            
        for yr in TARGET_TS_YEARS:
            if yr not in years: continue
            
            df_yr = merged[merged['Year'] == yr]
            fig, axes = plt.subplots(2, 2, figsize=(14, 10))
            fig.suptitle(f"{yr} Time Series: {stn_name}", fontsize=16, fontweight='bold')
            
            axes[0,0].plot(df_yr.index, df_yr['T_C_obs'], label='Obs', alpha=0.8)
            axes[0,0].plot(df_yr.index, df_yr['T_C_sim'], label='NLDAS3', alpha=0.8)
            axes[0,0].set_title("Temperature (°C)"); axes[0,0].legend()
            
            axes[0,1].plot(df_yr.index, df_yr['RH_obs'], alpha=0.8)
            axes[0,1].plot(df_yr.index, df_yr['RH_derived'], alpha=0.8)
            axes[0,1].set_title("Relative Humidity (%)")
            
            axes[1,0].plot(df_yr.index, df_yr['Enthalpy_kJ_kg_obs'], alpha=0.8)
            axes[1,0].plot(df_yr.index, df_yr['Enthalpy_kJ_kg_sim'], alpha=0.8)
            axes[1,0].set_title("Enthalpy (kJ/kg)")
            
            axes[1,1].axis('off') 
            plt.tight_layout(rect=[0, 0.03, 1, 0.95])
            pdf.savefig(fig); plt.close(fig)

        table_rows = []
        def build_row(df_slice, name):
            row = [name]
            for obs_col, sim_col, _, _ in VARS_TO_PLOT:
                clean_slice = df_slice.dropna(subset=[obs_col, sim_col])
                r2, bias, rmse = calc_metrics(clean_slice[obs_col], clean_slice[sim_col])
                row.extend([f"{r2:.2f}", f"{bias:.2f}", f"{rmse:.2f}"])
            return row
            
        table_rows.append(build_row(merged, "OVERALL (All Years)"))
        for season in ['Winter', 'Spring', 'Summer', 'Fall']:
            table_rows.append(build_row(merged[merged['Season'] == season], season))
            
        cols = ["Period", "T R²", "T Bias", "T RMSE", "RH R²", "RH Bias", "RH RMSE", "Enth R²", "Enth Bias", "Enth RMSE"]
        df_table = pd.DataFrame(table_rows, columns=cols)
        render_table_page(pdf, df_table, f"{stn_name} Data Summary")

    stn_stats_dict = {
        'Station': stn_name,
        'State': state,
        'Total_Records': total_records,
        'Missing_T_Pct': (raw_missing_t / total_records) * 100,
        'Missing_RH_Pct': (raw_missing_rh / total_records) * 100,
        'Missing_08_10_RH': is_missing_08_10
    }
    
    for (obs_col, sim_col, _, key) in VARS_TO_PLOT:
        clean_merged = merged.dropna(subset=[obs_col, sim_col])
        if len(clean_merged) > 0:
            stn_stats_dict[f'{key}_Bias'] = np.mean(clean_merged[sim_col] - clean_merged[obs_col])
            stn_stats_dict[f'{key}_R2'] = r2_score(clean_merged[obs_col], clean_merged[sim_col])

    for col in merged.select_dtypes(include=['float64']).columns:
        merged[col] = merged[col].astype('float32')

    return stn_name, merged, df_extremes, bad_years, stn_stats_dict

# ==========================================
# MAIN EXECUTION THREAD
# ==========================================
if __name__ == '__main__':
    print(f"Loading extracted JSON datasets from {JSON_DATA_DIR}...")
    
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
            stn_name, merged_df, df_ext, bad_yrs, stn_stats = future.result()
            
            if merged_df is not None: master_df_list.append(merged_df)
            if df_ext is not None and not df_ext.empty: all_extremes.append(df_ext)
            if bad_yrs: all_bad_years.extend(bad_yrs)
            if stn_stats is not None: all_stats.append(stn_stats)
                
            print(f"Processed {i+1}/{len(station_payloads)}: {stn_name}", end='\r')

    print("\n\nSaving QA/QC tracking files...")
    if all_extremes:
        pd.concat(all_extremes).to_csv(os.path.join(OUTPUT_DIR, 'extreme_values_tracked.csv'), index=False)
    if all_bad_years:
        pd.DataFrame(all_bad_years).to_csv(os.path.join(OUTPUT_DIR, 'dropped_station_years.csv'), index=False)

    # ==========================================
    # MASTER AGGREGATION PDF
    # ==========================================
    if master_df_list:
        print("Generating Master Aggregation PDF...")
        global_df = pd.concat(master_df_list, ignore_index=True)
        stats_df = pd.DataFrame(all_stats)
        
        stats_df.to_csv(os.path.join(OUTPUT_DIR, 'master_station_statistics.csv'), index=False)
        
        master_pdf_path = os.path.join(OUTPUT_DIR, "ALL_STATIONS_MASTER_SUMMARY.pdf")
        
        def get_agg_row(df, label):
            row = [label, len(df['Station'].unique())]
            for obs_col, sim_col, _, _ in VARS_TO_PLOT:
                clean_df = df.dropna(subset=[obs_col, sim_col])
                r2, bias, rmse = calc_metrics(clean_df[obs_col], clean_df[sim_col])
                row.extend([f"{r2:.2f}", f"{bias:.2f}", f"{rmse:.2f}"])
            return row
            
        base_cols = ["Stations", "T R²", "T Bias", "T RMSE", "RH R²", "RH Bias", "RH RMSE", "Enth R²", "Enth Bias", "Enth RMSE"]

        with PdfPages(master_pdf_path) as pdf:
            
            # --- DIAGNOSTIC PRINT BLOCK ---
            print("\n--- DIAGNOSTICS FOR GLOBAL SCATTER PLOTS ---")
            for obs_col, sim_col, title, _ in VARS_TO_PLOT:
                clean = global_df.dropna(subset=[obs_col, sim_col])
                neg_obs = (clean[obs_col] < 0).sum()
                neg_sim = (clean[sim_col] < 0).sum()
                print(f"Variable: {title}")
                print(f"  Total valid points: {len(clean):,}")
                print(f"  Obs < 0 count: {neg_obs:,} | Min Obs: {clean[obs_col].min():.2f} | Max Obs: {clean[obs_col].max():.2f}")
                print(f"  Sim < 0 count: {neg_sim:,} | Min Sim: {clean[sim_col].min():.2f} | Max Sim: {clean[sim_col].max():.2f}")
            print("--------------------------------------------\n")
            
            # --- 1. OVERALL SCATTER PLOT ---
            print("  -> Plotting Global Scatter (100% Full Data)...")
            fig, axes = plt.subplots(1, 3, figsize=(18, 6))
            fig.suptitle("Global CONUS Scatter Plots (Full Dataset - NLDAS Psurf Corrected)", fontsize=18, fontweight='bold', y=1.02)
            
            for ax, (obs_col, sim_col, title, _) in zip(axes, VARS_TO_PLOT):
                clean = global_df.dropna(subset=[obs_col, sim_col])
                if len(clean) > 10:
                    obs, sim = clean[obs_col], clean[sim_col]
                    r2, bias, rmse = calc_metrics(obs, sim)
                    
                    mn, mx = min(obs.min(), sim.min()), max(obs.max(), sim.max())
                    
                    # Removed bins='log' so sparse dots don't vanish
                    hb = ax.hexbin(obs, sim, gridsize=100, cmap='turbo', mincnt=1, extent=(mn, mx, mn, mx))
                    cb = plt.colorbar(hb, ax=ax)
                    cb.set_label('Count')
                    
                    ax.plot([mn, mx], [mn, mx], 'black', linestyle='--', lw=2, label='1:1 Line')
                    ax.set_xlim(mn, mx); ax.set_ylim(mn, mx)
                    
                    ax.set_title(f"Overall {title}\nR²: {r2:.3f} | Bias: {bias:.3f}", fontsize=16)
                    ax.set_xlabel("USCRN Observation"); ax.set_ylabel("NLDAS3")
                    
                    bbox_props = dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.9, edgecolor='gray')
                    ax.text(0.95, 0.05, f'RMSE: {rmse:.2f}', transform=ax.transAxes, 
                            fontsize=16, fontweight='bold', color='black', ha='right', va='bottom', bbox=bbox_props)
                    ax.legend(loc='upper left')
                    
            plt.tight_layout(rect=[0, 0.03, 1, 0.95])
            fig.savefig(f"{title}_highres.png", dpi=300, bbox_inches='tight') 
            pdf.savefig(fig); plt.close(fig)

            # --- 2. CONUS Overall Table ---
            conus_row = get_agg_row(global_df, "CONUS OVERALL")
            df_conus = pd.DataFrame([conus_row], columns=["Region"] + base_cols)
            render_table_page(pdf, df_conus, "CONUS Global Bias Summary")
            
            # --- 3. Seasonal Table ---
            print("  -> Generating Seasonal Tables...")
            season_rows = []
            for season in ['Winter', 'Spring', 'Summer', 'Fall']:
                season_data = global_df[global_df['Season'] == season]
                if not season_data.empty: season_rows.append(get_agg_row(season_data, season))
            if season_rows:
                df_season = pd.DataFrame(season_rows, columns=["Season"] + base_cols)
                render_table_page(pdf, df_season, "Seasonal Bias Summary (All Data)")

            # --- 4. State-by-State Table ---
            print("  -> Generating State Tables...")
            state_rows = []
            for state, group in global_df.groupby('State'):
                state_rows.append(get_agg_row(group, state))
            df_state = pd.DataFrame(state_rows, columns=["State"] + base_cols)
            render_table_page(pdf, df_state, "State-by-State Bias Summary")
            
            # --- 5. Climate Region Table ---
            print("  -> Generating Climate Region Tables...")
            climate_rows = []
            for clim, group in global_df.groupby('Climate'):
                climate_rows.append(get_agg_row(group, clim))
            df_climate = pd.DataFrame(climate_rows, columns=["Climate Region"] + base_cols)
            render_table_page(pdf, df_climate, "Climate Region Bias Summary")
            
            # --- 6. EXTREMES ANALYSIS TABLE ---
            print("  -> Generating Extremes Analysis (Top & Bottom 5%)...")
            extreme_rows = []
            for obs_col, sim_col, title, _ in VARS_TO_PLOT:
                clean = global_df.dropna(subset=[obs_col, sim_col])
                if len(clean) > 20:
                    p05 = clean[obs_col].quantile(0.05)
                    p95 = clean[obs_col].quantile(0.95)
                    
                    bot_df = clean[clean[obs_col] <= p05]
                    top_df = clean[clean[obs_col] >= p95]
                    
                    bot_bias = np.mean(bot_df[sim_col] - bot_df[obs_col]) if not bot_df.empty else np.nan
                    bot_rmse = np.sqrt(mean_squared_error(bot_df[obs_col], bot_df[sim_col])) if not bot_df.empty else np.nan
                    
                    top_bias = np.mean(top_df[sim_col] - top_df[obs_col]) if not top_df.empty else np.nan
                    top_rmse = np.sqrt(mean_squared_error(top_df[obs_col], top_df[sim_col])) if not top_df.empty else np.nan
                    
                    extreme_rows.append([
                        title,
                        f"< {p05:.1f}", f"{bot_bias:.2f}", f"{bot_rmse:.2f}",
                        f"> {p95:.1f}", f"{top_bias:.2f}", f"{top_rmse:.2f}"
                    ])
                    
            ext_cols = ["Variable", "Bottom 5% Threshold", "Bot 5% Bias", "Bot 5% RMSE", "Top 5% Threshold", "Top 5% Bias", "Top 5% RMSE"]
            if extreme_rows:
                df_ext_summary = pd.DataFrame(extreme_rows, columns=ext_cols)
                render_table_page(pdf, df_ext_summary, "Bias at Extremes (Bottom 5% vs Top 5% Observed)")

            # --- 7. STATISTICAL SIGNIFICANCE (ANOVA) TABLES ---
            print("  -> Running Statistical Significance (ANOVA) Tests...")
            sig_rows = []
            
            for grouping in ['Season', 'State', 'Climate']:
                row = [grouping]
                for obs_col, sim_col, _, _ in VARS_TO_PLOT:
                    err_series = global_df[sim_col] - global_df[obs_col]
                    
                    grouped_errs = [group.dropna().values for name, group in err_series.groupby(global_df[grouping])]
                    grouped_errs = [g for g in grouped_errs if len(g) > 1] 
                    
                    if len(grouped_errs) >= 2:
                        f_stat, p_val = stats.f_oneway(*grouped_errs)
                        p_str = "< 0.001" if p_val < 0.001 else f"{p_val:.3f}"
                    else:
                        p_str = "N/A"
                        
                    row.append(p_str)
                sig_rows.append(row)
                
            df_sig = pd.DataFrame(sig_rows, columns=["Grouping", "Temp Bias P-Val", "RH Bias P-Val", "Enthalpy Bias P-Val"])
            render_table_page(pdf, df_sig, "ANOVA P-Values: Are Mean Biases Significantly Different?")
            
        print("\nAll operations complete! Check the output directory for your PDFs and CSVs.")
        
        # ==========================================
        # PRINT FINAL TEXT SUMMARY 
        # ==========================================
        avg_missing_t = stats_df['Missing_T_Pct'].mean()
        avg_missing_rh = stats_df['Missing_RH_Pct'].mean()
        missing_08_10_count = stats_df['Missing_08_10_RH'].sum()
        total_stations = len(stats_df)
        states_processed = ", ".join(sorted(stats_df['State'].unique()))
        
        print("\n" + "="*70)
        print("                 DATA MISSINGNESS SUMMARY")
        print("="*70)
        print(f"Missing data for temperatures at about ~{avg_missing_t:.1f}% and ~{avg_missing_rh:.1f}% for humidity")
        print(f"per station on average for all {total_stations} stations.")
        print(f"(Showing stations in: {states_processed})")
        print("-" * 70)
        
        if missing_08_10_count > 0:
            pct_affected = (missing_08_10_count / total_stations) * 100
            print(f"Missing almost all data between 2008 - 2010 for relative humidity")
            print(f"for {missing_08_10_count} stations ({pct_affected:.1f}% of processed stations).")
        else:
            print("No stations were entirely missing relative humidity data between 2008-2010.")
            
        print("="*70 + "\n")
        
    else:
        print("\n[WARNING] No valid data found to generate master summary.")