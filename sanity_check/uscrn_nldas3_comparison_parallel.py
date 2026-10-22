import os
import glob
import pandas as pd
import xarray as xr
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from sklearn.metrics import mean_squared_error, r2_score
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing

warnings.filterwarnings('ignore')

# ==========================================
# CONFIGURATION TOGGLES
# ==========================================
PROCESS_ALL_YEARS = True     
PLOT_EVERY_YEAR_TS = True     
PROCESS_ALL_STATIONS = False  

NLDAS_DIR = '/discover/nobackup/projects/eis_nldas3/DATA/forcing/hourly'
STATION_DIR = '/discover/nobackup/cmbreen/datacenters/uscrn_independent_data'
OUTPUT_DIR = './nldas_station_reports'

# NLDAS Variable names
NLDAS_TMP = 'Tair'      
NLDAS_SPFH = 'Qair'    

P_HPA = 1013.25  

VARS_TO_PLOT = [('T_C_obs', 'T_C_sim', 'Temp (°C)', 'T_C'),
                ('RH_obs', 'RH_derived', 'Rel. Humidity (%)', 'RH'),
                ('Enthalpy_kJ_kg_obs', 'Enthalpy_kJ_kg_sim', 'Enthalpy (kJ/kg)', 'Enthalpy')]

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

# ==========================================
# PARALLEL WORKER FUNCTION (Processes 1 Station)
# ==========================================
def process_station(stn_file, nldas_files, output_dir, process_all_years, plot_every_year_ts):
    stn_name = os.path.basename(stn_file).replace('.csv', '')
    
    # 1. Load Station Data
    df_stn = pd.read_csv(stn_file)
    df_stn = df_stn.rename(columns={'temperature': 'T_C', 'relative_humidity': 'RH_obs'})
    df_stn['T_C'] = pd.to_numeric(df_stn['T_C'], errors='coerce')
    df_stn['RH_obs'] = pd.to_numeric(df_stn['RH_obs'], errors='coerce')
    
    # Filter USCRN Errors
    df_stn.loc[df_stn['T_C'] < -80, 'T_C'] = np.nan       
    df_stn.loc[df_stn['RH_obs'] < 0, 'RH_obs'] = np.nan   
    df_stn.loc[df_stn['RH_obs'] > 105, 'RH_obs'] = np.nan 
    
    df_stn['datetime'] = pd.to_datetime(df_stn['datetime'], errors='coerce').dt.tz_localize(None)
    df_stn['datetime'] = df_stn['datetime'].dt.round('h') 
    
    stn_lat = df_stn['latitude'].iloc[0]
    stn_lon = df_stn['longitude'].iloc[0]
    
    df_stn = calc_psychrometrics(df_stn, source='station')
    df_stn = df_stn.set_index('datetime')
    
    # 2. Load NLDAS Data
    df_list = []
    for f in nldas_files:
        try:
            with xr.open_dataset(f, engine='netcdf4') as ds:
                lat_var = 'lat' if 'lat' in ds.coords else 'latitude'
                lon_var = 'lon' if 'lon' in ds.coords else 'longitude'
                pt = ds.sel({lat_var: stn_lat, lon_var: stn_lon}, method='nearest')
                df_pt = pt[[NLDAS_TMP, NLDAS_SPFH]].to_dataframe().reset_index()
                df_list.append(df_pt)
        except Exception:
            pass
            
    if not df_list:
        return stn_name, None
        
    df_nldas = pd.concat(df_list, ignore_index=True)
    df_nldas = df_nldas.rename(columns={'time': 'datetime'})
    df_nldas['datetime'] = df_nldas['datetime'].dt.round('h')
    
    if df_nldas[NLDAS_TMP].mean() > 200: 
        df_nldas['T_C'] = df_nldas[NLDAS_TMP] - 273.15
    else:
        df_nldas['T_C'] = df_nldas[NLDAS_TMP]
        
    df_nldas['Q_kg_kg'] = df_nldas[NLDAS_SPFH]
    df_nldas = calc_psychrometrics(df_nldas, source='nldas')
    df_nldas = df_nldas.set_index('datetime')
    
    # 3. Merge Datasets
    merged = df_stn[['T_C', 'RH_obs', 'Enthalpy_kJ_kg']].join(
        df_nldas[['T_C', 'RH_derived', 'Enthalpy_kJ_kg']], 
        lsuffix='_obs', rsuffix='_sim', how='inner'
    )
    
    if merged.empty:
        return stn_name, None
        
    merged['season'] = merged.index.month.map(get_season)
    merged['Station'] = stn_name

    # 4. Individual Station PDF Generation
    pdf_path = os.path.join(output_dir, f"{stn_name}_analysis.pdf")
    with PdfPages(pdf_path) as pdf:
        if process_all_years and plot_every_year_ts:
            years_to_plot = sorted(merged.index.year.unique())
        else:
            sample_year = 2018
            years_to_plot = [sample_year] if sample_year in merged.index.year else [merged.index.year[0]]
                
        # TIMESERIES
        for yr in years_to_plot:
            merged_yr = merged[merged.index.year == yr]
            if not merged_yr.empty:
                fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
                axes[0].plot(merged_yr.index, merged_yr['T_C_obs'], label='Station', alpha=0.7)
                axes[0].plot(merged_yr.index, merged_yr['T_C_sim'], label='NLDAS3', alpha=0.7)
                axes[0].set_ylabel("Temp (°C)"); axes[0].legend(); axes[0].set_title(f"{yr} Time Series")
                
                axes[1].plot(merged_yr.index, merged_yr['RH_obs'], alpha=0.7)
                axes[1].plot(merged_yr.index, merged_yr['RH_derived'], alpha=0.7)
                axes[1].set_ylabel("RH (%)")
                
                axes[2].plot(merged_yr.index, merged_yr['Enthalpy_kJ_kg_obs'], alpha=0.7)
                axes[2].plot(merged_yr.index, merged_yr['Enthalpy_kJ_kg_sim'], alpha=0.7)
                axes[2].set_ylabel("Enthalpy (kJ/kg)"); axes[2].set_xlabel("Date")
                
                plt.tight_layout(); pdf.savefig(fig); plt.close(fig)
            
        # OVERALL SCATTER
        fig, axes = plt.subplots(1, 3, figsize=(18, 5))
        for ax, (obs_col, sim_col, title, dict_key) in zip(axes, VARS_TO_PLOT):
            clean = merged.dropna(subset=[obs_col, sim_col])
            if len(clean) > 10:
                obs, sim = clean[obs_col], clean[sim_col]
                r2, bias = r2_score(obs, sim), np.mean(sim - obs)
                ax.scatter(obs, sim, alpha=0.1, s=2, c='purple')
                mn, mx = min(obs.min(), sim.min()), max(obs.max(), sim.max())
                ax.plot([mn, mx], [mn, mx], 'k--')
                ax.set_title(f"{title}\nR²: {r2:.3f} | Bias: {bias:.3f}")
                ax.grid(True, alpha=0.3)
        plt.tight_layout(); pdf.savefig(fig); plt.close(fig)

    # Return the merged data to the main thread
    return stn_name, merged

# ==========================================
# MAIN EXECUTION THREAD
# ==========================================
if __name__ == '__main__':
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    if PROCESS_ALL_STATIONS:
        station_files = [f for f in glob.glob(os.path.join(STATION_DIR, '*.csv')) if not os.path.basename(f).startswith('all_')]
    else:
        station_files = glob.glob(os.path.join(STATION_DIR, 'VA_*.csv')) + glob.glob(os.path.join(STATION_DIR, 'TX_*.csv'))

    print(f"Total stations queued for processing: {len(station_files)}")

    # Gather NLDAS files ONCE
    if PROCESS_ALL_YEARS:
        nldas_pattern = os.path.join(NLDAS_DIR, '*', '*.nc')
    else:
        nldas_pattern = os.path.join(NLDAS_DIR, '2018*', '*.nc')
        
    nldas_files = sorted(glob.glob(nldas_pattern))
    if not nldas_files:
        print("  -> [ERROR] No NLDAS files found for pattern. Exiting.")
        exit()
    
    print(f"Located {len(nldas_files)} NLDAS files. Starting Parallel Pool...")

    # Data structures to collect from workers
    station_dfs = {}
    master_df_list = []

    # Run stations in Parallel
    max_cores = min(multiprocessing.cpu_count(), len(station_files), 32) # Cap at 32 cores so we don't crash Discover
    with ProcessPoolExecutor(max_workers=max_cores) as executor:
        # Submit all jobs
        futures = {
            executor.submit(process_station, stn, nldas_files, OUTPUT_DIR, PROCESS_ALL_YEARS, PLOT_EVERY_YEAR_TS): stn 
            for stn in station_files
        }
        
        # Collect results as they finish
        completed = 0
        for future in as_completed(futures):
            stn_name, merged_df = future.result()
            completed += 1
            if merged_df is not None:
                station_dfs[stn_name] = merged_df
                master_df_list.append(merged_df)
                print(f"[{completed}/{len(station_files)}] Successfully processed {stn_name}")
            else:
                print(f"[{completed}/{len(station_files)}] Failed/Skipped {stn_name} (Insufficient data)")

    # ==========================================
    # GENERATE COMBINED PDFS (Sequentially on Main Thread)
    # ==========================================
    print("\n=======================================================")
    print("Generating COMBINED Station PDFs...")
    
    comb_scatter_pdf = PdfPages(os.path.join(OUTPUT_DIR, 'COMBINED_Scatter_Plots.pdf'))
    comb_ts_pdf = PdfPages(os.path.join(OUTPUT_DIR, 'COMBINED_Timeseries_Plots.pdf'))
    
    valid_stn_count = 0
    pending_save = False
    
    # Sort alphabetical for neatness
    for stn_name in sorted(station_dfs.keys()):
        merged = station_dfs[stn_name]
        
        sample_year = 2018
        merged_sample = merged[merged.index.year == sample_year]
        if merged_sample.empty: merged_sample = merged[merged.index.year == merged.index.year[0]]
            
        if valid_stn_count % 2 == 0:
            scatter_fig, scatter_axes = plt.subplots(2, 3, figsize=(18, 12))
            scatter_fig.suptitle("Station Scatter Plots Comparison", fontsize=18, fontweight='bold', y=0.98)
            ts_fig, ts_axes = plt.subplots(3, 2, figsize=(20, 12))
            ts_fig.suptitle("Station Time Series Comparison", fontsize=18, fontweight='bold', y=0.95)
        
        row_idx = valid_stn_count % 2   
        col_idx = valid_stn_count % 2   
        
        for j, (obs_col, sim_col, title, dict_key) in enumerate(VARS_TO_PLOT):
            clean = merged.dropna(subset=[obs_col, sim_col])
            ax = scatter_axes[row_idx, j]
            if len(clean) > 10:
                obs, sim = clean[obs_col], clean[sim_col]
                r2, bias = r2_score(obs, sim), np.mean(sim - obs)
                ax.scatter(obs, sim, alpha=0.1, s=2, c='purple')
                mn, mx = min(obs.min(), sim.min()), max(obs.max(), sim.max())
                ax.plot([mn, mx], [mn, mx], 'k--')
                ax_title = f"{stn_name}\n{title}" if j == 0 else title
                ax.set_title(f"{ax_title} | R²: {r2:.3f} | Bias: {bias:.3f}", fontsize=11)
                ax.grid(True, alpha=0.3)
            else:
                ax.axis('off')

        if not merged_sample.empty:
            ts_axes[0, col_idx].plot(merged_sample.index, merged_sample['T_C_obs'], label='Station', alpha=0.7)
            ts_axes[0, col_idx].plot(merged_sample.index, merged_sample['T_C_sim'], label='NLDAS3', alpha=0.7)
            ts_axes[0, col_idx].set_ylabel("Temp (°C)"); ts_axes[0, col_idx].legend()
            ts_axes[0, col_idx].set_title(f"{stn_name} - {sample_year}", fontsize=14, fontweight='bold')
            
            ts_axes[1, col_idx].plot(merged_sample.index, merged_sample['RH_obs'], alpha=0.7)
            ts_axes[1, col_idx].plot(merged_sample.index, merged_sample['RH_derived'], alpha=0.7)
            ts_axes[1, col_idx].set_ylabel("RH (%)")
            
            ts_axes[2, col_idx].plot(merged_sample.index, merged_sample['Enthalpy_kJ_kg_obs'], alpha=0.7)
            ts_axes[2, col_idx].plot(merged_sample.index, merged_sample['Enthalpy_kJ_kg_sim'], alpha=0.7)
            ts_axes[2, col_idx].set_ylabel("Enthalpy"); ts_axes[2, col_idx].set_xlabel("Date")
        else:
            for r in range(3): ts_axes[r, col_idx].axis('off')

        pending_save = True
        valid_stn_count += 1
        
        if valid_stn_count % 2 == 0:
            scatter_fig.tight_layout(rect=[0, 0.03, 1, 0.95]); comb_scatter_pdf.savefig(scatter_fig); plt.close(scatter_fig)
            ts_fig.tight_layout(rect=[0, 0.03, 1, 0.93]); comb_ts_pdf.savefig(ts_fig); plt.close(ts_fig)
            pending_save = False

    if pending_save:
        for r in range(3): 
            scatter_axes[1, r].axis('off')
            ts_axes[r, 1].axis('off')
        scatter_fig.tight_layout(rect=[0, 0.03, 1, 0.95]); comb_scatter_pdf.savefig(scatter_fig); plt.close(scatter_fig)
        ts_fig.tight_layout(rect=[0, 0.03, 1, 0.93]); comb_ts_pdf.savefig(ts_fig); plt.close(ts_fig)

    comb_scatter_pdf.close()
    comb_ts_pdf.close()

    # ==========================================
    # MASTER OVERALL SUMMARY PLOT
    # ==========================================
    print("\n=======================================================")
    print("Generating ALL STATIONS Master Summary...")
    master_pdf_path = os.path.join(OUTPUT_DIR, "ALL_STATIONS_MASTER_SUMMARY.pdf")

    if master_df_list:
        df_global = pd.concat(master_df_list, ignore_index=True)
        
        with PdfPages(master_pdf_path) as pdf:
            # PAGE 1: GLOBAL HEXBIN SCATTERS (1x3)
            fig, axes = plt.subplots(1, 3, figsize=(18, 5))
            fig.suptitle("Global NLDAS-3 Validation (All Data Combined)", fontsize=20, fontweight='bold', y=1.05)
            
            for ax, (obs_col, sim_col, title, dict_key) in zip(axes, VARS_TO_PLOT):
                clean = df_global.dropna(subset=[obs_col, sim_col])
                if len(clean) > 10:
                    obs, sim = clean[obs_col], clean[sim_col]
                    r2, bias = r2_score(obs, sim), np.mean(sim - obs)
                    hb = ax.hexbin(obs, sim, gridsize=50, cmap='inferno', mincnt=1, bins='log')
                    mn, mx = min(obs.min(), sim.min()), max(obs.max(), sim.max())
                    ax.plot([mn, mx], [mn, mx], 'cyan', linestyle='--', lw=2, label='1:1 Line')
                    ax.set_title(f"Overall {title}\nR²: {r2:.3f} | Bias: {bias:.3f}")
                    ax.set_xlabel("Observation"); ax.set_ylabel("NLDAS")
                    cb = plt.colorbar(hb, ax=ax); cb.set_label('log10(count)')
                    
            plt.tight_layout(rect=[0, 0.03, 1, 0.95])
            pdf.savefig(fig); plt.close(fig)

            # PAGE 2: GLOBAL SEASONAL BIAS TABLE
            fig, ax = plt.subplots(figsize=(12, 8))
            ax.axis('off')
            
            table_data = []
            for season in ['Winter', 'Spring', 'Summer', 'Fall']:
                season_data = df_global[df_global['season'] == season]
                row = [season]
                for obs_col, sim_col, _, _ in VARS_TO_PLOT:
                    clean = season_data.dropna(subset=[obs_col, sim_col])
                    if len(clean) > 10:
                        r2, bias = r2_score(clean[obs_col], clean[sim_col]), np.mean(clean[sim_col] - clean[obs_col])
                        row.append(f"R²: {r2:.2f}\nBias: {bias:.2f}")
                    else:
                        row.append("N/A")
                table_data.append(row)
                
            table = ax.table(cellText=table_data, 
                             colLabels=["Season", "Temperature", "Rel. Humidity", "Enthalpy"],
                             loc='center', cellLoc='center', bbox=[0, 0, 1, 1])
            table.auto_set_font_size(False)
            table.set_fontsize(14)
            ax.set_title("GLOBAL SYSTEMIC SEASONAL BIAS\n(All Data Combined)", pad=20, fontsize=18, fontweight='bold')
            pdf.savefig(fig); plt.close(fig)
            
            # PAGES 3+: INDIVIDUAL STATION SCATTER PLOTS
            for stn in sorted(df_global['Station'].unique()):
                stn_df = df_global[df_global['Station'] == stn]
                fig, axes = plt.subplots(1, 3, figsize=(18, 5))
                fig.suptitle(f"Station Bias Summary: {stn} (All Processed Years)", fontsize=16, fontweight='bold', y=1.05)
                
                for ax, (obs_col, sim_col, title, dict_key) in zip(axes, VARS_TO_PLOT):
                    clean = stn_df.dropna(subset=[obs_col, sim_col])
                    if len(clean) > 10:
                        obs, sim = clean[obs_col], clean[sim_col]
                        r2, bias = r2_score(obs, sim), np.mean(sim - obs)
                        ax.scatter(obs, sim, alpha=0.1, s=2, c='purple')
                        mn, mx = min(obs.min(), sim.min()), max(obs.max(), sim.max())
                        ax.plot([mn, mx], [mn, mx], 'k--')
                        ax.set_title(f"{title}\nR²: {r2:.3f} | Bias: {bias:.3f}")
                        ax.grid(True, alpha=0.3)
                    else:
                        ax.text(0.5, 0.5, "Insufficient Data", ha='center', va='center')
                        ax.axis('off')
                plt.tight_layout(rect=[0, 0.03, 1, 0.95])
                pdf.savefig(fig); plt.close(fig)

    print(f"\nAll operations complete! Outputs saved in: {OUTPUT_DIR}")