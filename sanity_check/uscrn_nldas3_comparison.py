import os
import glob
import pandas as pd
import xarray as xr
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from sklearn.metrics import mean_squared_error, r2_score
import warnings

warnings.filterwarnings('ignore')

# ==========================================
# CONFIGURATION TOGGLES
# ==========================================
PROCESS_ALL_YEARS = False     # False = 2018 only, True = All available years
PROCESS_ALL_STATIONS = False  # False = VA & TX only, True = All stations in directory

NLDAS_DIR = '/discover/nobackup/projects/eis_nldas3/DATA/forcing/hourly'
STATION_DIR = '/discover/nobackup/cmbreen/datacenters/uscrn_independent_data'
OUTPUT_DIR = './nldas_station_reports'

os.makedirs(OUTPUT_DIR, exist_ok=True)

# NLDAS Variable names
NLDAS_TMP = 'Tair'      
NLDAS_SPFH = 'Qair'    

REGIONS = {
    'VA': {'lat': (38.5, 39.5), 'lon': (-78.0, -77.0)},
    'TX': {'lat': (32.3, 33.3), 'lon': (-97.5, -96.5)}
}

P_HPA = 1013.25  

# ==========================================
# HELPER FUNCTIONS
# ==========================================
def calc_psychrometrics(df, source='station'):
    """Calculates RH, Specific Humidity, and Enthalpy for a dataframe."""
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

# ==========================================
# MAIN PROCESSING LOOP
# ==========================================
if PROCESS_ALL_STATIONS:
    station_files = [f for f in glob.glob(os.path.join(STATION_DIR, '*.csv')) 
                     if not os.path.basename(f).startswith('all_')]
else:
    station_files = glob.glob(os.path.join(STATION_DIR, 'VA_*.csv')) + \
                    glob.glob(os.path.join(STATION_DIR, 'TX_*.csv'))

print(f"Total stations queued for processing: {len(station_files)}")

master_data = {'T_C': {'obs': [], 'sim': []}, 'RH': {'obs': [], 'sim': []}, 'Enthalpy': {'obs': [], 'sim': []}}

for file_idx, stn_file in enumerate(station_files):
    stn_name = os.path.basename(stn_file).replace('.csv', '')
    state = stn_name[:2]
    print(f"\n=======================================================")
    print(f"--- Processing [{file_idx+1}/{len(station_files)}] {stn_name} ---")
    
    # --- 1. Load Station Data ---
    df_stn = pd.read_csv(stn_file)
    print(f"  -> [DEBUG] Loaded {len(df_stn)} raw rows from Station CSV.")
    
    # Automatically filter out -99.0 and -9999.0 error flags
    df_stn.replace([-99.0, -99.000, -9999.0], np.nan, inplace=True)
    
    df_stn['datetime'] = pd.to_datetime(df_stn['datetime'], errors='coerce').dt.tz_localize(None)
    df_stn['datetime'] = df_stn['datetime'].dt.round('H') 
    
    stn_lat = df_stn['latitude'].iloc[0]
    stn_lon = df_stn['longitude'].iloc[0]
    
    df_stn = df_stn.rename(columns={'temperature': 'T_C', 'relative_humidity': 'RH_obs'})
    df_stn = calc_psychrometrics(df_stn, source='station')
    df_stn = df_stn.set_index('datetime')
    
    print(f"  -> [DEBUG] Station Time Range: {df_stn.index.min()} to {df_stn.index.max()}")
    print(f"  -> [DEBUG] Valid Station Temps available: {df_stn['T_C'].count()} / {len(df_stn)}")
    
    # --- 2. Load NLDAS Data ---
    if PROCESS_ALL_YEARS:
        nldas_pattern = os.path.join(NLDAS_DIR, '*', '*.nc')
    else:
        nldas_pattern = os.path.join(NLDAS_DIR, '2018*', '*.nc')
        
    nldas_files = sorted(glob.glob(nldas_pattern))
    if not nldas_files:
        print("  -> [ERROR] No NLDAS files found for pattern. Skipping.")
        continue

    print(f"  -> [DEBUG] Found {len(nldas_files)} NLDAS files. Extracting point sequentially...")
    
    df_list = []
    for f in nldas_files:
        try:
            with xr.open_dataset(f, engine='netcdf4') as ds:
                lat_var = 'lat' if 'lat' in ds.coords else 'latitude'
                lon_var = 'lon' if 'lon' in ds.coords else 'longitude'
                
                pt = ds.sel({lat_var: stn_lat, lon_var: stn_lon}, method='nearest')
                df_pt = pt[[NLDAS_TMP, NLDAS_SPFH]].to_dataframe().reset_index()
                df_list.append(df_pt)
        except Exception as e:
            pass
            
    if not df_list:
        print(f"  -> [ERROR] Could not extract valid data for {stn_name}. Skipping.")
        continue
        
    df_nldas = pd.concat(df_list, ignore_index=True)
    df_nldas = df_nldas.rename(columns={'time': 'datetime'})
    
    print(f"  -> [DEBUG] Extracted {len(df_nldas)} raw rows from NLDAS files.")
    
    # ROUND TO NEAREST HOUR TO GUARANTEE MATCH
    df_nldas['datetime'] = df_nldas['datetime'].dt.round('H')
    
    if df_nldas[NLDAS_TMP].mean() > 200: 
        df_nldas['T_C'] = df_nldas[NLDAS_TMP] - 273.15
    else:
        df_nldas['T_C'] = df_nldas[NLDAS_TMP]
        
    df_nldas['Q_kg_kg'] = df_nldas[NLDAS_SPFH]
    df_nldas = calc_psychrometrics(df_nldas, source='nldas')
    df_nldas = df_nldas.set_index('datetime')
    
    print(f"  -> [DEBUG] NLDAS Time Range: {df_nldas.index.min()} to {df_nldas.index.max()}")
    print(f"  -> [DEBUG] Checking alignment formats:")
    print(f"       Station index type: {type(df_stn.index[0])} | Sample: {df_stn.index[0]}")
    print(f"       NLDAS index type:   {type(df_nldas.index[0])} | Sample: {df_nldas.index[0]}")
    
    # --- 3. Merge Datasets ---
    print("  -> Aligning time series...")
    merged = df_stn[['T_C', 'RH_obs', 'Enthalpy_kJ_kg']].join(
        df_nldas[['T_C', 'RH_derived', 'Enthalpy_kJ_kg']], 
        lsuffix='_obs', rsuffix='_sim', how='inner'
    )
    
    print(f"  -> [DEBUG] INNER JOIN Result: {len(merged)} overlapping rows found.")
    
    if merged.empty:
        print("  -> [ERROR] Merged dataset is empty! No overlapping hours found between Station and NLDAS.")
        print("  -> PDFs will be blank. Check the date ranges above to ensure they overlap.")
        continue
        
    merged['season'] = merged.index.month.map(get_season)

    # --- 4. Output PDF ---
    pdf_path = os.path.join(OUTPUT_DIR, f"{stn_name}_analysis.pdf")
    print(f"  -> Generating PDF: {pdf_path}")
    
    with PdfPages(pdf_path) as pdf:
        
        # --- PAGE 1: MAP ---
        fig, ax = plt.subplots(figsize=(8, 6))
        
        lat_min, lat_max = stn_lat - 2, stn_lat + 2
        lon_min, lon_max = stn_lon - 2, stn_lon + 2
        
        if state in REGIONS:
            bounds = REGIONS[state]
            rect = plt.Rectangle((bounds['lon'][0], bounds['lat'][0]), 
                                 bounds['lon'][1]-bounds['lon'][0], bounds['lat'][1]-bounds['lat'][0],
                                 fill=False, color='blue', lw=2, label=f'{state} Target Grid Box')
            ax.add_patch(rect)
            lat_min, lat_max = bounds['lat'][0]-2, bounds['lat'][1]+2
            lon_min, lon_max = bounds['lon'][0]-2, bounds['lon'][1]+2
            
        ax.scatter(stn_lon, stn_lat, c='red', marker='*', s=200, label=f'Station: {stn_name}')
        ax.set_title(f"Location of {stn_name}")
        ax.set_xlabel("Longitude"); ax.set_ylabel("Latitude")
        ax.set_xlim(lon_min, lon_max)
        ax.set_ylim(lat_min, lat_max)
        ax.grid(True, linestyle='--')
        ax.legend()
        pdf.savefig(fig); plt.close()
        
        # --- PAGE 2: TIMESERIES ---
        # Look for overlap in 2018. If none, grab the first available year in the merged data
        sample_year = 2018
        merged_sample = merged[merged.index.year == sample_year]
        if merged_sample.empty:
            sample_year = merged.index.year[0]
            merged_sample = merged[merged.index.year == sample_year]
            
        if not merged_sample.empty:
            fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
            
            axes[0].plot(merged_sample.index, merged_sample['T_C_obs'], label='Station', alpha=0.7)
            axes[0].plot(merged_sample.index, merged_sample['T_C_sim'], label='NLDAS3', alpha=0.7)
            axes[0].set_ylabel("Temperature (°C)")
            axes[0].legend()
            axes[0].set_title(f"{sample_year} Time Series Comparison")
            
            axes[1].plot(merged_sample.index, merged_sample['RH_obs'], alpha=0.7)
            axes[1].plot(merged_sample.index, merged_sample['RH_derived'], alpha=0.7)
            axes[1].set_ylabel("Relative Humidity (%)")
            
            axes[2].plot(merged_sample.index, merged_sample['Enthalpy_kJ_kg_obs'], alpha=0.7)
            axes[2].plot(merged_sample.index, merged_sample['Enthalpy_kJ_kg_sim'], alpha=0.7)
            axes[2].set_ylabel("Enthalpy (kJ/kg)")
            axes[2].set_xlabel("Date")
            
            plt.tight_layout()
            pdf.savefig(fig); plt.close()
            
        # --- PAGE 3: OVERALL SCATTER ---
        fig, axes = plt.subplots(1, 3, figsize=(18, 5))
        vars_to_plot = [
            ('T_C_obs', 'T_C_sim', 'Temperature (°C)', 'T_C'),
            ('RH_obs', 'RH_derived', 'Relative Humidity (%)', 'RH'),
            ('Enthalpy_kJ_kg_obs', 'Enthalpy_kJ_kg_sim', 'Enthalpy (kJ/kg)', 'Enthalpy')
        ]
        
        for ax, (obs_col, sim_col, title, dict_key) in zip(axes, vars_to_plot):
            clean = merged.dropna(subset=[obs_col, sim_col])
            print(f"    -> [DEBUG] Scatter {dict_key}: {len(clean)} valid pairs found (after dropping NaNs).")
            
            if len(clean) > 10:
                obs, sim = clean[obs_col], clean[sim_col]
                
                master_data[dict_key]['obs'].extend(obs.tolist())
                master_data[dict_key]['sim'].extend(sim.tolist())
                
                r2 = r2_score(obs, sim)
                bias = np.mean(sim - obs)
                
                ax.scatter(obs, sim, alpha=0.1, s=2, c='purple')
                mn, mx = min(obs.min(), sim.min()), max(obs.max(), sim.max())
                ax.plot([mn, mx], [mn, mx], 'k--')
                ax.set_title(f"{title}\nR²: {r2:.3f} | Bias: {bias:.3f}")
                ax.set_xlabel("Station Observation")
                ax.set_ylabel("NLDAS Estimation")
                ax.grid(True, alpha=0.3)
        plt.tight_layout()
        pdf.savefig(fig); plt.close()
        
        # --- PAGE 4: SEASONAL BREAKDOWN ---
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.axis('off')
        
        table_data = []
        for season in ['Winter', 'Spring', 'Summer', 'Fall']:
            season_data = merged[merged['season'] == season]
            row = [season]
            for obs_col, sim_col, _, _ in vars_to_plot:
                clean = season_data.dropna(subset=[obs_col, sim_col])
                if len(clean) > 10:
                    r2 = r2_score(clean[obs_col], clean[sim_col])
                    bias = np.mean(clean[sim_col] - clean[obs_col])
                    row.append(f"R²: {r2:.2f}\nBias: {bias:.2f}")
                else:
                    row.append("N/A")
            table_data.append(row)
            
        table = ax.table(cellText=table_data, 
                         colLabels=["Season", "Temperature", "Rel. Humidity", "Enthalpy"],
                         loc='center', cellLoc='center', bbox=[0, 0, 1, 1])
        table.auto_set_font_size(False)
        table.set_fontsize(12)
        ax.set_title(f"Seasonal Metrics - {stn_name}", pad=20)
        pdf.savefig(fig); plt.close()

# ==========================================
# MASTER OVERALL SUMMARY PLOT
# ==========================================
print("\n=======================================================")
print("Generating ALL STATIONS Master Summary...")
master_pdf_path = os.path.join(OUTPUT_DIR, "ALL_STATIONS_MASTER_SUMMARY.pdf")

with PdfPages(master_pdf_path) as pdf:
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    vars_to_plot = [
        ('Temperature (°C)', 'T_C'),
        ('Relative Humidity (%)', 'RH'),
        ('Enthalpy (kJ/kg)', 'Enthalpy')
    ]
    
    for ax, (title, dict_key) in zip(axes, vars_to_plot):
        obs = np.array(master_data[dict_key]['obs'])
        sim = np.array(master_data[dict_key]['sim'])
        
        if len(obs) > 10:
            r2 = r2_score(obs, sim)
            bias = np.mean(sim - obs)
            
            hb = ax.hexbin(obs, sim, gridsize=50, cmap='inferno', mincnt=1, bins='log')
            mn, mx = min(obs.min(), sim.min()), max(obs.max(), sim.max())
            ax.plot([mn, mx], [mn, mx], 'cyan', linestyle='--', lw=2, label='1:1 Line')
            
            ax.set_title(f"Overall {title}\nR²: {r2:.3f} | Bias: {bias:.3f}")
            ax.set_xlabel("All Stations Observations")
            ax.set_ylabel("All NLDAS Estimations")
            cb = plt.colorbar(hb, ax=ax)
            cb.set_label('log10(count)')
            
    plt.tight_layout()
    pdf.savefig(fig); plt.close()

print(f"\nAll operations complete! Outputs saved in: {OUTPUT_DIR}")