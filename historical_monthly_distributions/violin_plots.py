# '''
# this should give you the violin plots 
# '''

# import os
# import gc
# import numpy as np
# import pandas as pd
# import xarray as xr
# import matplotlib.pyplot as plt
# import seaborn as sns
# import metpy.calc as mpcalc
# from metpy.units import units
# from matplotlib.backends.backend_pdf import PdfPages
# import warnings
# import matplotlib.pyplot as plt

# # Sets the default font size for EVERYTHING (titles, labels, ticks, legends) to 16
# plt.rcParams.update({'font.size': 16})


# warnings.filterwarnings('ignore')

# # ==========================================
# # 1. CONFIGURATIONS & PATHS
# # ==========================================
# csv_path = '/discover/nobackup/cmbreen/datacenters/data/im3_open_source_data_center_atlas_v2026.02.09.csv'
# tx_nldas3 = '/discover/nobackup/cmbreen/datacenters/texas_pure_hourly/tx_Pure_Hourly_Summary_FIXED.nc'
# va_nldas3 = '/discover/nobackup/cmbreen/datacenters/virginia_pure_hourly/va_Pure_Hourly_Summary_FIXED.nc'
# out_pdf = './Monthly_DayNight_Violin_Distributions.pdf'

# PLOT_VARS = [
#     {'col': 'Tair_C', 'name': 'Dry Bulb Temp', 'unit': '°C'},
#     {'col': 'Twb_C', 'name': 'Wet Bulb Temp', 'unit': '°C'},
#     {'col': 'RH', 'name': 'Relative Humidity', 'unit': '%'},
#     {'col': 'Enthalpy', 'name': 'Enthalpy', 'unit': 'kJ/kg'}
# ]

# MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
# PALETTE = {'Day': '#ffb347', 'Night': '#2b5b84'}  # Sun Gold and Night Navy

# # ==========================================
# # 2. DATA PROCESSING FUNCTION
# # ==========================================
# def extract_and_compute_state(state_abb, nldas_file, dc_df):
#     print(f"\n--- Processing {state_abb} ---")
#     state_dcs = dc_df[dc_df['state_abb'] == state_abb]
    
#     print(f"Extracting {len(state_dcs)} datacenters from NetCDF...")
#     ds = xr.open_dataset(nldas_file)
    
#     lats = xr.DataArray(state_dcs['lat'].values, dims='datacenter')
#     lons = xr.DataArray(state_dcs['lon'].values, dims='datacenter')
    
#     ds_pts = ds.sel(lat=lats, lon=lons, method='nearest').compute()
#     df = ds_pts.to_dataframe().reset_index()
#     ds.close()
    
#     tz_offset = -6 if state_abb == 'TX' else -5
#     df['time'] = df['time'] + pd.Timedelta(hours=tz_offset)
    
#     df['Month'] = df['time'].dt.month
#     df['Hour'] = df['time'].dt.hour
    
#     # Define Day (7 AM to 6:59 PM) and Night (7 PM to 6:59 AM)
#     df['Day_Night'] = np.where((df['Hour'] >= 7) & (df['Hour'] < 19), 'Day', 'Night')
    
#     print("Computing MetPy variables (RH, Wet Bulb, Enthalpy)...")
#     temp = df['Tair_C'].values * units.degC
#     press = df.get('PSurf', np.full(len(df), 101325)).values * units.Pa
#     qair = df['Qair'].values * units('kg/kg')
    
#     if 'RH' not in df.columns:
#         rh = mpcalc.relative_humidity_from_specific_humidity(press, temp, qair) * 100 * units.percent
#         df['RH'] = rh.m
        
#     if 'Twb_C' not in df.columns:
#         dewpt = mpcalc.dewpoint_from_relative_humidity(temp, df['RH'].values * units.percent)
#         df['Twb_C'] = mpcalc.wet_bulb_temperature(press, temp, dewpt).m
        
#     if 'Enthalpy' not in df.columns:
#         df['Enthalpy'] = 1.006 * temp.m + qair.m * (2501 + 1.86 * temp.m)
        
#     cols_to_keep = ['Month', 'Day_Night', 'Tair_C', 'Twb_C', 'RH', 'Enthalpy']
#     df = df[cols_to_keep].dropna()
    
#     return df

# # ==========================================
# # 3. MAIN EXECUTION & PLOTTING
# # ==========================================
# print("Loading Datacenter Metadata...")
# dc_df = pd.read_csv(csv_path)

# with PdfPages(out_pdf) as pdf:
#     sns.set_theme(style="whitegrid")
    
#     for state_abb, nldas_file in [('VA', va_nldas3), ('TX', tx_nldas3)]:
#         df_state = extract_and_compute_state(state_abb, nldas_file, dc_df)
        
#         # ---> IF JUPYTER CRASHES, UNCOMMENT THE LINE BELOW <---
#         #print("Downsampling to 10% for KDE stability...")
#         #df_state = df_state.sample(frac=0.10, random_state=42)
        
#         print(f"Plotting 4x1 Violin Grid for {state_abb}...")
#         fig, axes = plt.subplots(nrows=4, ncols=1, figsize=(16, 24), sharex=True)
        
#         for idx, var_info in enumerate(PLOT_VARS):
#             ax = axes[idx]
            
#             sns.violinplot(
#                 data=df_state, 
#                 x='Month', 
#                 y=var_info['col'], 
#                 hue='Day_Night', 
#                 split=True,            # Left half is Day, Right half is Night
#                 inner="quartile",      # Show dashed lines for 25th, 50th, 75th percentiles
#                 palette=PALETTE,
#                 ax=ax,
#                 linewidth=1.2,
#                 cut=0                  # Stop the KDE at the strict bounds of the data (saves memory)
#             )
            
#             ax.set_ylabel(f"{var_info['name']} ({var_info['unit']})", fontweight='bold', fontsize=16)
#             ax.tick_params(axis='y', labelsize=14)
            
#             if idx == 0:
#                 ax.legend(title='Time of Day', fontsize=14, title_fontsize=14, loc='upper right')
#                 ax.set_title(f"{state_abb} Historical Monthly Distributions: Day vs Night", fontweight='bold', fontsize=22, pad=20)
#             else:
#                 if ax.get_legend() is not None:
#                     ax.get_legend().remove()

#         axes[-1].set_xlabel("Month", fontweight='bold', fontsize=18)
#         axes[-1].set_xticks(range(12))
#         axes[-1].set_xticklabels(MONTH_NAMES, fontsize=16)
        
#         plt.tight_layout()
#         pdf.savefig(fig)
#         plt.close(fig)
        
#         del df_state
#         gc.collect()

# print(f"\nDone! PDF saved to: {out_pdf}")

'''

same thing but parallelized 

'''

# import os
# import gc
# import numpy as np
# import pandas as pd
# import xarray as xr
# import matplotlib.pyplot as plt
# import seaborn as sns
# import warnings
# from matplotlib.backends.backend_pdf import PdfPages

# # Import concurrent.futures for parallel processing
# from concurrent.futures import ProcessPoolExecutor, as_completed

# # Sets the default font size for EVERYTHING
# plt.rcParams.update({'font.size': 16})
# warnings.filterwarnings('ignore')

# # ==========================================
# # 1. CONFIGURATIONS & PATHS
# # ==========================================
# csv_path = '/discover/nobackup/cmbreen/datacenters/data/im3_open_source_data_center_atlas_v2026.02.09.csv'
# tx_nldas3 = '/discover/nobackup/cmbreen/datacenters/texas_pure_hourly/tx_Pure_Hourly_Summary_FIXED.nc'
# va_nldas3 = '/discover/nobackup/cmbreen/datacenters/virginia_pure_hourly/va_Pure_Hourly_Summary_FIXED.nc'
# out_pdf = './Monthly_DayNight_Violin_Distributions.pdf'

# PLOT_VARS = [
#     {'col': 'Tair_C', 'name': 'Dry Bulb Temp', 'unit': '°C'},
#     {'col': 'Twb_C', 'name': 'Wet Bulb Temp', 'unit': '°C'},
#     {'col': 'RH', 'name': 'Relative Humidity', 'unit': '%'},
#     {'col': 'Enthalpy', 'name': 'Enthalpy', 'unit': 'kJ/kg'}
# ]

# MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
# PALETTE = {'Day': '#ffb347', 'Night': '#2b5b84'}

# # Detect available CPU cores (Safeguard for SLURM/Discover environments)
# NUM_CORES = int(os.environ.get('SLURM_CPUS_PER_TASK', os.cpu_count() or 4))

# # ==========================================
# # 2. PARALLEL WORKER FUNCTION (MetPy)
# # ==========================================
# def compute_metpy_chunk(df_chunk):
#     """
#     Worker function to calculate MetPy variables on a chunk of the dataframe.
#     By doing this in chunks, we bypass the single-thread bottleneck.
#     """
#     import metpy.calc as mpcalc
#     from metpy.units import units
#     import warnings
#     warnings.filterwarnings('ignore') # Suppress pint unit warnings in worker threads

#     temp = df_chunk['Tair_C'].values * units.degC
#     press = df_chunk.get('PSurf', np.full(len(df_chunk), 101325)).values * units.Pa
#     qair = df_chunk['Qair'].values * units('kg/kg')
    
#     if 'RH' not in df_chunk.columns:
#         rh = mpcalc.relative_humidity_from_specific_humidity(press, temp, qair) * 100 * units.percent
#         df_chunk['RH'] = rh.m
        
#     if 'Twb_C' not in df_chunk.columns:
#         dewpt = mpcalc.dewpoint_from_relative_humidity(temp, df_chunk['RH'].values * units.percent)
#         df_chunk['Twb_C'] = mpcalc.wet_bulb_temperature(press, temp, dewpt).m
        
#     if 'Enthalpy' not in df_chunk.columns:
#         df_chunk['Enthalpy'] = 1.006 * temp.m + qair.m * (2501 + 1.86 * temp.m)
        
#     return df_chunk

# # ==========================================
# # 3. DATA PROCESSING FUNCTION
# # ==========================================
# def extract_and_compute_state(state_abb, nldas_file, dc_df):
#     print(f"\n--- Processing {state_abb} ---")
#     state_dcs = dc_df[dc_df['state_abb'] == state_abb]
    
#     print(f"[{state_abb}] Extracting {len(state_dcs)} datacenters from NetCDF...")
    
#     # Use context manager to ensure xarray closes cleanly and frees RAM
#     with xr.open_dataset(nldas_file) as ds:
#         lats = xr.DataArray(state_dcs['lat'].values, dims='datacenter')
#         lons = xr.DataArray(state_dcs['lon'].values, dims='datacenter')
        
#         ds_pts = ds.sel(lat=lats, lon=lons, method='nearest').compute()
#         df = ds_pts.to_dataframe().reset_index()
    
#     tz_offset = -6 if state_abb == 'TX' else -5
#     df['time'] = df['time'] + pd.Timedelta(hours=tz_offset)
    
#     df['Month'] = df['time'].dt.month
#     df['Hour'] = df['time'].dt.hour
#     df['Day_Night'] = np.where((df['Hour'] >= 7) & (df['Hour'] < 19), 'Day', 'Night')
    
#     print(f"[{state_abb}] Computing MetPy variables in parallel across {NUM_CORES} cores...")
    
#     # Split the DataFrame into chunks (4 chunks per core prevents memory spiking and balances load)
#     # Split the DataFrame into chunks safely using pandas .iloc to preserve the DataFrame type
#     num_chunks = NUM_CORES * 4
#     indices = np.array_split(range(len(df)), num_chunks)
#     chunks = [df.iloc[idx] for idx in indices]
#     processed_chunks = []
    
#     # Launch Multiprocessing Pool
#     with ProcessPoolExecutor(max_workers=NUM_CORES) as executor:
#         futures = [executor.submit(compute_metpy_chunk, chunk) for chunk in chunks]
        
#         for future in as_completed(futures):
#             processed_chunks.append(future.result())
            
#     df = pd.concat(processed_chunks, ignore_index=True)
    
#     cols_to_keep = ['Month', 'Day_Night', 'Tair_C', 'Twb_C', 'RH', 'Enthalpy']
#     return df[cols_to_keep].dropna()

# # ==========================================
# # 4. MAIN EXECUTION & PLOTTING
# # ==========================================
# if __name__ == '__main__':
#     print("Loading Datacenter Metadata...")
#     dc_df = pd.read_csv(csv_path)

#     with PdfPages(out_pdf) as pdf:
#         sns.set_theme(style="whitegrid")
        
#         for state_abb, nldas_file in [('VA', va_nldas3), ('TX', tx_nldas3)]:
#             df_state = extract_and_compute_state(state_abb, nldas_file, dc_df)
            
#             # --- CRITICAL PLOTTING OPTIMIZATION ---
#             # Plotting KDEs on >500k rows is visually identical to full dataset but takes hours.
#             # Downsampling specifically for the plot step guarantees speed.
#             MAX_PLOT_SAMPLES = 250_000 
#             if len(df_state) > MAX_PLOT_SAMPLES:
#                 print(f"[{state_abb}] Downsampling from {len(df_state):,} to {MAX_PLOT_SAMPLES:,} rows strictly to speed up KDE drawing...")
#                 plot_df = df_state.sample(n=MAX_PLOT_SAMPLES, random_state=42)
#             else:
#                 plot_df = df_state
                
#             print(f"[{state_abb}] Plotting 4x1 Violin Grid...")
#             fig, axes = plt.subplots(nrows=4, ncols=1, figsize=(16, 24), sharex=True)
            
#             for idx, var_info in enumerate(PLOT_VARS):
#                 ax = axes[idx]
                
#                 sns.violinplot(
#                     data=plot_df, 
#                     x='Month', 
#                     y=var_info['col'], 
#                     hue='Day_Night', 
#                     split=True,            
#                     inner="quartile",      
#                     palette=PALETTE,
#                     ax=ax,
#                     linewidth=1.2,
#                     cut=0                  
#                 )
                
#                 ax.set_ylabel(f"{var_info['name']} ({var_info['unit']})", fontweight='bold', fontsize=16)
#                 ax.tick_params(axis='y', labelsize=16)
                
#                 if idx == 0:
#                     ax.legend(title='Time of Day', fontsize=16, title_fontsize=14, loc='upper right')
#                     ax.set_title(f"{state_abb} Historical Monthly Distributions: Day vs Night", fontweight='bold', fontsize=22, pad=20)
#                 else:
#                     if ax.get_legend() is not None:
#                         ax.get_legend().remove()

#             axes[-1].set_xlabel("Month", fontweight='bold', fontsize=18)
#             axes[-1].set_xticks(range(12))
#             axes[-1].set_xticklabels(MONTH_NAMES, fontsize=16)
            
#             plt.tight_layout()
#             pdf.savefig(fig)
#             plt.close(fig)
            
#             del df_state
#             del plot_df
#             gc.collect()

#     print(f"\nDone! PDF saved to: {out_pdf}")

'''

added split plot and normal plot
kept parallelized

'''

# import os
# import gc
# import numpy as np
# import pandas as pd
# import xarray as xr
# import matplotlib.pyplot as plt
# import seaborn as sns
# import warnings
# from matplotlib.backends.backend_pdf import PdfPages

# # Import concurrent.futures for parallel processing
# from concurrent.futures import ProcessPoolExecutor, as_completed

# # Sets the default font size for EVERYTHING
# plt.rcParams.update({'font.size': 16})
# warnings.filterwarnings('ignore')

# # ==========================================
# # 1. CONFIGURATIONS & PATHS
# # ==========================================
# csv_path = '/discover/nobackup/cmbreen/datacenters/data/im3_open_source_data_center_atlas_v2026.02.09.csv'
# tx_nldas3 = '/discover/nobackup/cmbreen/datacenters/texas_pure_hourly/tx_Pure_Hourly_Summary_FIXED.nc'
# va_nldas3 = '/discover/nobackup/cmbreen/datacenters/virginia_pure_hourly/va_Pure_Hourly_Summary_FIXED.nc'
# out_pdf = './Monthly_DayNight_Violin_Distributions.pdf'

# PLOT_VARS = [
#     {'col': 'Tair_C', 'name': 'Dry Bulb Temp', 'unit': '°C'},
#     {'col': 'Twb_C', 'name': 'Wet Bulb Temp', 'unit': '°C'},
#     {'col': 'RH', 'name': 'Relative Humidity', 'unit': '%'},
#     {'col': 'Enthalpy', 'name': 'Enthalpy', 'unit': 'kJ/kg'}
# ]

# MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

# # Using matplotlib's default tab colors: orange for Day, blue for Night
# PALETTE = {'Day': 'tab:orange', 'Night': 'tab:blue'}

# # Detect available CPU cores (Safeguard for SLURM/Discover environments)
# NUM_CORES = int(os.environ.get('SLURM_CPUS_PER_TASK', os.cpu_count() or 4))

# # ==========================================
# # 2. PARALLEL WORKER FUNCTION (MetPy)
# # ==========================================
# def compute_metpy_chunk(df_chunk):
#     """
#     Worker function to calculate MetPy variables on a chunk of the dataframe.
#     By doing this in chunks, we bypass the single-thread bottleneck.
#     """
#     import metpy.calc as mpcalc
#     from metpy.units import units
#     import warnings
#     warnings.filterwarnings('ignore') # Suppress pint unit warnings in worker threads

#     temp = df_chunk['Tair_C'].values * units.degC
#     press = df_chunk.get('PSurf', np.full(len(df_chunk), 101325)).values * units.Pa
#     qair = df_chunk['Qair'].values * units('kg/kg')
    
#     if 'RH' not in df_chunk.columns:
#         rh = mpcalc.relative_humidity_from_specific_humidity(press, temp, qair) * 100 * units.percent
#         df_chunk['RH'] = rh.m
        
#     if 'Twb_C' not in df_chunk.columns:
#         dewpt = mpcalc.dewpoint_from_relative_humidity(temp, df_chunk['RH'].values * units.percent)
#         df_chunk['Twb_C'] = mpcalc.wet_bulb_temperature(press, temp, dewpt).m
        
#     if 'Enthalpy' not in df_chunk.columns:
#         df_chunk['Enthalpy'] = 1.006 * temp.m + qair.m * (2501 + 1.86 * temp.m)
        
#     return df_chunk

# # ==========================================
# # 3. DATA PROCESSING FUNCTION
# # ==========================================
# def extract_and_compute_state(state_abb, nldas_file, dc_df):
#     print(f"\n--- Processing {state_abb} ---")
#     state_dcs = dc_df[dc_df['state_abb'] == state_abb]
    
#     print(f"[{state_abb}] Extracting {len(state_dcs)} datacenters from NetCDF...")
    
#     # Use context manager to ensure xarray closes cleanly and frees RAM
#     with xr.open_dataset(nldas_file) as ds:
#         lats = xr.DataArray(state_dcs['lat'].values, dims='datacenter')
#         lons = xr.DataArray(state_dcs['lon'].values, dims='datacenter')
        
#         ds_pts = ds.sel(lat=lats, lon=lons, method='nearest').compute()
#         df = ds_pts.to_dataframe().reset_index()
    
#     tz_offset = -6 if state_abb == 'TX' else -5
#     df['time'] = df['time'] + pd.Timedelta(hours=tz_offset)
    
#     df['Month'] = df['time'].dt.month
#     df['Hour'] = df['time'].dt.hour
#     df['Day_Night'] = np.where((df['Hour'] >= 7) & (df['Hour'] < 19), 'Day', 'Night')
    
#     print(f"[{state_abb}] Computing MetPy variables in parallel across {NUM_CORES} cores...")
    
#     # Split the DataFrame into chunks (4 chunks per core prevents memory spiking and balances load)
#     num_chunks = NUM_CORES * 4
#     indices = np.array_split(range(len(df)), num_chunks)
#     chunks = [df.iloc[idx] for idx in indices]
#     processed_chunks = []
    
#     # Launch Multiprocessing Pool
#     with ProcessPoolExecutor(max_workers=NUM_CORES) as executor:
#         futures = [executor.submit(compute_metpy_chunk, chunk) for chunk in chunks]
        
#         for future in as_completed(futures):
#             processed_chunks.append(future.result())
            
#     df = pd.concat(processed_chunks, ignore_index=True)
    
#     cols_to_keep = ['Month', 'Day_Night', 'Tair_C', 'Twb_C', 'RH', 'Enthalpy']
#     return df[cols_to_keep].dropna()

# # ==========================================
# # 4. MAIN EXECUTION & PLOTTING
# # ==========================================
# if __name__ == '__main__':
#     print("Loading Datacenter Metadata...")
#     dc_df = pd.read_csv(csv_path)

#     with PdfPages(out_pdf) as pdf:
#         sns.set_theme(style="whitegrid")
        
#         for state_abb, nldas_file in [('VA', va_nldas3), ('TX', tx_nldas3)]:
#             df_state = extract_and_compute_state(state_abb, nldas_file, dc_df)
            
#             # --- CRITICAL PLOTTING OPTIMIZATION ---
#             MAX_PLOT_SAMPLES = 250_000 
#             if len(df_state) > MAX_PLOT_SAMPLES:
#                 print(f"[{state_abb}] Downsampling from {len(df_state):,} to {MAX_PLOT_SAMPLES:,} rows strictly to speed up KDE drawing...")
#                 plot_df = df_state.sample(n=MAX_PLOT_SAMPLES, random_state=42)
#             else:
#                 plot_df = df_state
                
#             # --- GENERATE BOTH SPLIT AND SIDE-BY-SIDE PLOTS ---
#             for is_split in [True, False]:
#                 plot_style = "Split" if is_split else "Side-by-Side"
#                 print(f"[{state_abb}] Plotting 4x1 Violin Grid ({plot_style})...")
                
#                 fig, axes = plt.subplots(nrows=4, ncols=1, figsize=(16, 24), sharex=True)
                
#                 for idx, var_info in enumerate(PLOT_VARS):
#                     ax = axes[idx]
                    
#                     sns.violinplot(
#                         data=plot_df, 
#                         x='Month', 
#                         y=var_info['col'], 
#                         hue='Day_Night', 
#                         split=is_split,        # Toggles between split and side-by-side
#                         inner="quartile",      
#                         palette=PALETTE,
#                         ax=ax,
#                         linewidth=1.2,
#                         cut=0                  
#                     )

#                     if var_info['col'] == 'RH':
#                         ax.set_ylim(0, 100)
#                     # Force font size 16 for y-labels and ticks
#                     ax.set_ylabel(f"{var_info['name']}\n({var_info['unit']})", fontweight='bold', fontsize=16)
#                     ax.tick_params(axis='y', labelsize=16)
                    
#                     if idx == 0:
#                         # Force font size 16 for legends and title
#                         ax.legend(title='Time of Day', fontsize=16, title_fontsize=16, loc='upper right')
#                         ax.set_title(f"{state_abb} Historical Monthly Distributions: Day vs Night ({plot_style})", fontweight='bold', fontsize=16, pad=20)
#                     else:
#                         if ax.get_legend() is not None:
#                             ax.get_legend().remove()

#                 # Force font size 16 for x-labels and ticks
#                 axes[-1].set_xlabel("Month", fontweight='bold', fontsize=16)
#                 axes[-1].tick_params(axis='x', labelsize=16)
#                 axes[-1].set_xticks(range(12))
#                 axes[-1].set_xticklabels(MONTH_NAMES, fontsize=16)
                
#                 plt.tight_layout()
#                 pdf.savefig(fig)
#                 plt.close(fig)
            
#             del df_state
#             del plot_df
#             gc.collect()

#     print(f"\nDone! PDF saved to: {out_pdf}")

'''

improved parallelization

'''
import os
import gc
import numpy as np
import pandas as pd
import xarray as xr
import matplotlib.pyplot as plt
import seaborn as sns
import warnings
from matplotlib.backends.backend_pdf import PdfPages
from concurrent.futures import ProcessPoolExecutor

# Sets the default font size for EVERYTHING
plt.rcParams.update({'font.size': 16})
warnings.filterwarnings('ignore')

# ==========================================
# 1. CONFIGURATIONS & PATHS
# ==========================================
csv_path = '/discover/nobackup/cmbreen/datacenters/data/im3_open_source_data_center_atlas_v2026.02.09.csv'
tx_nldas3 = '/discover/nobackup/cmbreen/datacenters/texas_pure_hourly/tx_Pure_Hourly_Summary_FIXED.nc'
va_nldas3 = '/discover/nobackup/cmbreen/datacenters/virginia_pure_hourly/va_Pure_Hourly_Summary_FIXED.nc'
out_pdf = './Monthly_DayNight_Violin_Distributions.pdf'

PLOT_VARS = [
    {'col': 'Tair_C', 'name': 'Dry Bulb Temp', 'unit': '°C'},
    {'col': 'Twb_C', 'name': 'Wet Bulb Temp', 'unit': '°C'},
    {'col': 'RH', 'name': 'Relative Humidity', 'unit': '%'},
    {'col': 'Enthalpy', 'name': 'Enthalpy', 'unit': 'kJ/kg'}
]

MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
PALETTE = {'Day': 'tab:orange', 'Night': 'tab:blue'}

# Safely limit cores to avoid overwhelming the SLURM node
NUM_CORES = int(os.environ.get('SLURM_CPUS_PER_TASK', 16))
if NUM_CORES > 32:
    NUM_CORES = 32  # Cap at 32 to prevent memory/IPC thrashing on massive nodes

# ==========================================
# 2. PARALLEL WORKER FUNCTION (Only for Twb)
# ==========================================
def compute_twb_chunk(args):
    """
    Worker function taking pure 1D NumPy arrays to avoid Pandas pickling overhead.
    Unpacks arguments so we can track exactly which chunk and PID is running.
    """
    chunk_id, total_chunks, press_m, temp_m, rh_m = args
    pid = os.getpid()
    
    # flush=True forces the print to show up in the SLURM log immediately!
    print(f"  -> [Worker PID {pid}] Started Chunk {chunk_id}/{total_chunks} ({len(temp_m):,} rows)...", flush=True)
    
    import metpy.calc as mpcalc
    from metpy.units import units
    import warnings
    warnings.filterwarnings('ignore') 

    press_qty = press_m * units.Pa
    temp_qty = temp_m * units.degC
    rh_qty = rh_m * units.percent
    
    dewpt = mpcalc.dewpoint_from_relative_humidity(temp_qty, rh_qty)
    twb = mpcalc.wet_bulb_temperature(press_qty, temp_qty, dewpt)
    
    print(f"  -> [Worker PID {pid}] Finished Chunk {chunk_id}/{total_chunks}.", flush=True)
    return twb.m

# ==========================================
# 3. DATA PROCESSING FUNCTION
# ==========================================
def extract_and_compute_state(state_abb, nldas_file, dc_df):
    print(f"\n--- Processing {state_abb} ---", flush=True)
    state_dcs = dc_df[dc_df['state_abb'] == state_abb]
    
    print(f"[{state_abb}] Extracting {len(state_dcs)} datacenters from NetCDF...", flush=True)
    with xr.open_dataset(nldas_file) as ds:
        lats = xr.DataArray(state_dcs['lat'].values, dims='datacenter')
        lons = xr.DataArray(state_dcs['lon'].values, dims='datacenter')
        ds_pts = ds.sel(lat=lats, lon=lons, method='nearest').compute()
        df = ds_pts.to_dataframe().reset_index()
    
    tz_offset = -6 if state_abb == 'TX' else -5
    df['time'] = df['time'] + pd.Timedelta(hours=tz_offset)
    df['Month'] = df['time'].dt.month
    df['Hour'] = df['time'].dt.hour
    df['Day_Night'] = np.where((df['Hour'] >= 7) & (df['Hour'] < 19), 'Day', 'Night')
    
    print(f"[{state_abb}] Vectorizing Enthalpy and Relative Humidity (Fast)...", flush=True)
    temp_m = df['Tair_C'].values
    qair_m = df['Qair'].values
    press_m = df.get('PSurf', np.full(len(df), 101325)).values
    
    df['Enthalpy'] = 1.006 * temp_m + qair_m * (2501 + 1.86 * temp_m)
    
    import metpy.calc as mpcalc
    from metpy.units import units
    if 'RH' not in df.columns:
        rh_calc = mpcalc.relative_humidity_from_specific_humidity(
            press_m * units.Pa, temp_m * units.degC, qair_m * units('kg/kg')
        ) * 100
        df['RH'] = rh_calc.m
        
    rh_m = df['RH'].values

    # Determine chunking strategy
    num_chunks = NUM_CORES * 4
    press_chunks = np.array_split(press_m, num_chunks)
    temp_chunks = np.array_split(temp_m, num_chunks)
    rh_chunks = np.array_split(rh_m, num_chunks)
    
    # Bundle the arguments together with chunk IDs for tracking
    chunk_args = [
        (i + 1, num_chunks, press_chunks[i], temp_chunks[i], rh_chunks[i]) 
        for i in range(num_chunks)
    ]
    
    print(f"[{state_abb}] Dispatching {num_chunks} chunks to {NUM_CORES} CPU workers...", flush=True)
    
    with ProcessPoolExecutor(max_workers=NUM_CORES) as executor:
        # executor.map handles distributing the bundled args to the workers in chronological order
        twb_results = list(executor.map(compute_twb_chunk, chunk_args))
            
    print(f"[{state_abb}] Reassembling parallel results...", flush=True)
    df['Twb_C'] = np.concatenate(twb_results)
    
    cols_to_keep = ['Month', 'Day_Night', 'Tair_C', 'Twb_C', 'RH', 'Enthalpy']
    return df[cols_to_keep].dropna()

# ==========================================
# 4. MAIN EXECUTION & PLOTTING
# ==========================================
if __name__ == '__main__':
    print("Loading Datacenter Metadata...", flush=True)
    dc_df = pd.read_csv(csv_path)

    with PdfPages(out_pdf) as pdf:
        sns.set_theme(style="whitegrid")
        
        for state_abb, nldas_file in [('VA', va_nldas3), ('TX', tx_nldas3)]:
            df_state = extract_and_compute_state(state_abb, nldas_file, dc_df)
            
            # --- CRITICAL PLOTTING OPTIMIZATION ---
            MAX_PLOT_SAMPLES = 250_000 
            if len(df_state) > MAX_PLOT_SAMPLES:
                print(f"[{state_abb}] Downsampling from {len(df_state):,} to {MAX_PLOT_SAMPLES:,} rows strictly to speed up KDE drawing...", flush=True)
                plot_df = df_state.sample(n=MAX_PLOT_SAMPLES, random_state=42)
            else:
                plot_df = df_state
                
            # --- GENERATE BOTH SPLIT AND SIDE-BY-SIDE PLOTS ---
            for is_split in [True, False]:
                plot_style = "Split" if is_split else "Side-by-Side"
                print(f"[{state_abb}] Plotting 4x1 Violin Grid ({plot_style})...", flush=True)
                
                fig, axes = plt.subplots(nrows=4, ncols=1, figsize=(16, 24), sharex=True)
                
                for idx, var_info in enumerate(PLOT_VARS):
                    ax = axes[idx]
                    
                    sns.violinplot(
                        data=plot_df, 
                        x='Month', 
                        y=var_info['col'], 
                        hue='Day_Night', 
                        split=is_split,        
                        inner="quartile",      
                        palette=PALETTE,
                        ax=ax,
                        linewidth=1.2,
                        cut=0                  
                    )

                    if var_info['col'] == 'RH':
                        ax.set_ylim(0, 100)
                        
                    ax.set_ylabel(f"{var_info['name']}\n({var_info['unit']})", fontweight='bold', fontsize=16)
                    ax.tick_params(axis='y', labelsize=16)
                    
                    if idx == 0:
                        ax.legend(title='Time of Day', fontsize=16, title_fontsize=16, loc='upper right')
                        ax.set_title(f"{state_abb} Historical Monthly Distributions: Day vs Night ({plot_style})", fontweight='bold', fontsize=16, pad=20)
                    else:
                        if ax.get_legend() is not None:
                            ax.get_legend().remove()

                axes[-1].set_xlabel("Month", fontweight='bold', fontsize=16)
                axes[-1].tick_params(axis='x', labelsize=16)
                axes[-1].set_xticks(range(12))
                axes[-1].set_xticklabels(MONTH_NAMES, fontsize=16)
                
                plt.tight_layout()
                pdf.savefig(fig)
                plt.close(fig)
            
            # Memory Management
            del df_state
            del plot_df
            gc.collect()

    print(f"\nDone! PDF saved to: {out_pdf}", flush=True)