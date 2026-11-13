'''
This code does a point extraction on all the uscrn stations simulatneously for all nldas3 data and then we will do all the bias analysis etc afterwards. 
This will hopefully minimize everything so that it just runs once 


'''

# import os
# import glob
# import pandas as pd
# import xarray as xr
# import warnings

# warnings.filterwarnings('ignore')

# # ==========================================
# # CONFIGURATION
# # ==========================================
# PROCESS_ALL_YEARS = True

# NLDAS_DIR = '/discover/nobackup/projects/eis_nldas3/DATA/forcing/hourly'
# STATION_DIR = '/discover/nobackup/cmbreen/datacenters/uscrn_independent_data'
# OUTPUT_CSV = './nldas_station_reports_sequential/ALL_STATIONS_NLDAS_EXTRACTED.csv'

# NLDAS_TMP = 'Tair'      
# NLDAS_SPFH = 'Qair'    
# NLDAS_PSURF = 'PSurf'    

# os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)

# # ==========================================
# # 1. GATHER ALL STATION COORDINATES
# # ==========================================
# print("Gathering station coordinates...")
# station_files = [f for f in glob.glob(os.path.join(STATION_DIR, '*.csv')) if not os.path.basename(f).startswith('all_')]

# station_meta = []
# for stn_file in station_files:
#     stn_name = os.path.basename(stn_file).replace('.csv', '')
#     # Just read the first row to get the lat/lon
#     df_temp = pd.read_csv(stn_file, nrows=1)
#     if 'latitude' in df_temp.columns and 'longitude' in df_temp.columns:
#         station_meta.append({
#             'Station': stn_name,
#             'lat': df_temp['latitude'].iloc[0],
#             'lon': df_temp['longitude'].iloc[0]
#         })

# df_meta = pd.DataFrame(station_meta)
# print(f"Found {len(df_meta)} valid stations.")

# # Create Xarray DataArrays for vectorized extraction
# lats_da = xr.DataArray(df_meta['lat'].values, dims='Station')
# lons_da = xr.DataArray(df_meta['lon'].values, dims='Station')
# stns_da = xr.DataArray(df_meta['Station'].values, dims='Station')

# # ==========================================
# # 2. FIND NLDAS FILES
# # ==========================================
# if PROCESS_ALL_YEARS:
#     nldas_pattern = os.path.join(NLDAS_DIR, '*', '*.nc')
# else:
#     nldas_pattern = os.path.join(NLDAS_DIR, '2018*', '*.nc')
    
# nldas_files = sorted(glob.glob(nldas_pattern))
# print(f"Found {len(nldas_files)} NLDAS files to process.")

# # ==========================================
# # 3. VECTORIZED EXTRACTION LOOP
# # ==========================================
# print("Starting extraction...")

# # Initialize CSV with headers
# pd.DataFrame(columns=['Station', 'datetime', 'Tair', 'Qair', 'PSurf']).to_csv(OUTPUT_CSV, index=False)

# buffer = []
# chunk_size = 100  # Write to disk every 500 files to save RAM

# import IPython
# import tqdm
# times_list = []
# tair_list = []
# qair_list = []
# psurf_list = []

# import numpy as np
# stn_names = df_meta['Station'].values

# # ==========================================
# # 1. PRE-COMPUTE GRID INDICES (THE MASSIVE SPEEDUP)
# # ==========================================
# print("Pre-computing nearest grid indices...")
# nldas_files = sorted(glob.glob(os.path.join(NLDAS_DIR, '*', '*.nc')))

# # Open just the first file to get the grid coordinates
# with xr.open_dataset(nldas_files[0], engine='netcdf4') as ds_ref:
#     lat_var = 'lat' if 'lat' in ds_ref.coords else 'latitude'
#     lon_var = 'lon' if 'lon' in ds_ref.coords else 'longitude'
    
#     grid_lats = ds_ref[lat_var].values
#     grid_lons = ds_ref[lon_var].values

# # Find the exact integer index for each station ONCE
# lat_idxs = [np.abs(grid_lats - stn_lat).argmin() for stn_lat in df_meta['lat']]
# lon_idxs = [np.abs(grid_lons - stn_lon).argmin() for stn_lon in df_meta['lon']]

# # Convert to xarray DataArrays for fast vectorized integer indexing
# ilat_da = xr.DataArray(lat_idxs, dims='Station')
# ilon_da = xr.DataArray(lon_idxs, dims='Station')

# # ==========================================
# # 2. INITIALIZE NESTED DICTIONARY
# # ==========================================
# # Structure: { "Station_1": {}, "Station_2": {} }
# extracted_data = {stn: {} for stn in stn_names}

# '''
# Every file f is a day with 24 hours
# '''
# for i, f in tqdm.tqdm(enumerate(nldas_files)):
#     try:
#         with xr.open_dataset(f, engine='netcdf4') as ds:
#             lat_var = 'lat' if 'lat' in ds.coords else 'latitude'
#             lon_var = 'lon' if 'lon' in ds.coords else 'longitude'
#             time_var = 'time' if 'time' in ds.coords else 'valid_time' 

#             # --- THE MAGIC FORMULA ---
#             # This extracts all stations at once using nearest neighbor
#             ds_pts = ds.sel({lat_var: lats_da, lon_var: lons_da}, method='nearest')
            
#             # Attach the actual station names as a coordinate
#             ds_pts = ds_pts.assign_coords(Station=stns_da)
            
#             # Convert to pandas dataframe
#             basename = os.path.basename(f)
#             date_str = basename.split('.')[1][1:]  
#             yearmonth = date_str[:6]               
#             day = date_str   
#             import netCDF4 as nc
#             with nc.Dataset(f, 'r') as root:
#                 tair_var = root.variables[NLDAS_TMP]
#                 qair_var = root.variables[NLDAS_SPFH]
#                 psurf_var = root.variables[NLDAS_PSURF]
#                 IPython.embed()
#                 import tqdm 
#                 for stn_name, y_idx, x_idx in tqdm.tqdm(zip(stn_names, lat_idxs, lon_idxs)):
#                     stn_tair = tair_var[:, y_idx, x_idx].filled(np.nan)
#                     stn_qair = qair_var[:, y_idx, x_idx].filled(np.nan)
#                     stn_psurf = psurf_var[:, y_idx, x_idx].filled(np.nan)
                    
#                     if yearmonth not in extracted_data[stn_name]:
#                         extracted_data[stn_name][yearmonth] = {}
                        
#                     extracted_data[stn_name][yearmonth][day] = {
#                         'tair': stn_tair.tolist(),
#                         'qair': stn_qair.tolist(),
#                         'psurf': stn_psurf.tolist()
#                     }
#                     #print(stn_name)
#                 print(f)
#             # times_list.append(ds_pts[time_var].values)
#             # tair_list.append(ds_pts[NLDAS_TMP].values)
#             # qair_list.append(ds_pts[NLDAS_SPFH].values)
#             # psurf_list.append(ds_pts[NLDAS_PSURF].values)
            
#             # ## need to switch this to numpy array with lat/ long too 
#             # #df_pt = ds_pts[[NLDAS_TMP, NLDAS_SPFH, NLDAS_PSURF]].to_dataframe().reset_index()
            
#             # # Clean up columns (rename 'time' to 'datetime')
#             # time_var = 'time' if 'time' in df_pt.columns else 'valid_time'
#             # df_pt = df_pt.rename(columns={time_var: 'datetime'})
            
#             # # Keep only what we need
#             # df_pt = df_pt[['Station', 'datetime', NLDAS_TMP, NLDAS_SPFH, NLDAS_PSURF]]
            
#             buffer.append(df_pt)
#             print(f)
            
#     except Exception as e:
#         print(f"Error reading {f}: {e}")
        
#     # Write to disk in chunks to prevent memory overload
#     if (i + 1) % chunk_size == 0 or (i + 1) == len(nldas_files):
#         if buffer:
#             chunk_df = pd.concat(buffer, ignore_index=True)
#             chunk_df.to_csv(OUTPUT_CSV, mode='a', header=False, index=False)
#             buffer = [] # clear memory
#         print(f"Processed {i + 1}/{len(nldas_files)} files...")

# print(f"\nExtraction complete! Saved to {OUTPUT_CSV}")



'''
Try 2:
eliminates xarray and only uses netcdf4 libraries
this was still 1 min per day for all stations 


'''

# import os
# import glob
# import json
# import numpy as np
# import pandas as pd
# import xarray as xr
# import netCDF4 as nc
# import warnings
# from tqdm import tqdm

# warnings.filterwarnings('ignore')

# # ==========================================
# # CONFIGURATION
# # ==========================================
# NLDAS_DIR = '/discover/nobackup/projects/eis_nldas3/DATA/forcing/hourly'
# STATION_DIR = '/discover/nobackup/cmbreen/datacenters/uscrn_independent_data'
# OUTPUT_JSON = './nldas_station_reports_sequential/ALL_STATIONS_NLDAS.json'

# NLDAS_TMP = 'Tair'      
# NLDAS_SPFH = 'Qair'    
# NLDAS_PSURF = 'PSurf' # Fixed case, usually Psurf in NLDAS

# os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)

# # ==========================================
# # 1. GATHER ALL STATION COORDINATES
# # ==========================================
# print("Gathering station coordinates...")
# station_files = [f for f in glob.glob(os.path.join(STATION_DIR, '*.csv')) if not os.path.basename(f).startswith('all_')]

# station_meta = []
# for stn_file in station_files:
#     stn_name = os.path.basename(stn_file).replace('.csv', '')
#     df_temp = pd.read_csv(stn_file, nrows=1)
#     if 'latitude' in df_temp.columns and 'longitude' in df_temp.columns:
#         station_meta.append({
#             'Station': stn_name,
#             'lat': df_temp['latitude'].iloc[0],
#             'lon': df_temp['longitude'].iloc[0]
#         })

# df_meta = pd.DataFrame(station_meta)
# stn_names = df_meta['Station'].values
# print(f"Found {len(df_meta)} valid stations.")

# # ==========================================
# # 2. FIND NLDAS FILES
# # ==========================================
# nldas_files = sorted(glob.glob(os.path.join(NLDAS_DIR, '*', '*.nc')))
# print(f"Found {len(nldas_files)} NLDAS files to process.")

# # ==========================================
# # 3. PRE-COMPUTE GRID INDICES (THE MASSIVE SPEEDUP)
# # ==========================================
# print("Pre-computing nearest grid indices...")
# with xr.open_dataset(nldas_files[0], engine='netcdf4') as ds_ref:
#     lat_var = 'lat' if 'lat' in ds_ref.coords else 'latitude'
#     lon_var = 'lon' if 'lon' in ds_ref.coords else 'longitude'
    
#     grid_lats = ds_ref[lat_var].values
#     grid_lons = ds_ref[lon_var].values

# # Find the exact integer index for each station ONCE
# lat_idxs = [np.abs(grid_lats - stn_lat).argmin() for stn_lat in df_meta['lat']]
# lon_idxs = [np.abs(grid_lons - stn_lon).argmin() for stn_lon in df_meta['lon']]

# # ==========================================
# # 4. INITIALIZE NESTED DICTIONARY
# # ==========================================
# extracted_data = {stn: {} for stn in stn_names}

# # ==========================================
# # 5. PURE NETCDF4 EXTRACTION LOOP
# # ==========================================
# print("Starting lightning-fast extraction...")

# # Only ONE tqdm bar for the files (no inner tqdm)
# for f in tqdm(nldas_files, desc="Processing Files"):
#     try:
#         basename = os.path.basename(f)
#         date_str = basename.split('.')[1][1:]  
#         yearmonth = date_str[:6]               
#         day = date_str   
        
#         # Open using pure NetCDF4 (Xarray is fully banished from this loop)
#         with nc.Dataset(f, 'r') as root:
#             tair_var = root.variables[NLDAS_TMP]
#             qair_var = root.variables[NLDAS_SPFH]
#             psurf_var = root.variables[NLDAS_PSURF]
            
#             # Fast inner loop using our pre-calculated integers
#             for stn_name, y_idx, x_idx in zip(stn_names, lat_idxs, lon_idxs):
                
#                 # Instantly jump to the exact pixel on disk
#                 stn_tair = tair_var[:, y_idx, x_idx].filled(np.nan)
#                 stn_qair = qair_var[:, y_idx, x_idx].filled(np.nan)
#                 stn_psurf = psurf_var[:, y_idx, x_idx].filled(np.nan)
                
#                 # Append to dictionary
#                 if yearmonth not in extracted_data[stn_name]:
#                     extracted_data[stn_name][yearmonth] = {}
                    
#                 extracted_data[stn_name][yearmonth][day] = {
#                     'tair': stn_tair.tolist(),
#                     'qair': stn_qair.tolist(),
#                     'psurf': stn_psurf.tolist()
#                 }
                
#     except Exception as e:
#         print(f"\nError reading {f}: {e}")

# # ==========================================
# # 6. SAVE TO JSON
# # ==========================================
# print("\nSaving to JSON...")
# with open(OUTPUT_JSON, 'w') as jf:
#     json.dump(extracted_data, jf)

# print(f"Extraction complete! Saved to {OUTPUT_JSON}")




'''
Try 3
supposed to limit thrashing... but did not work
'''

# import os
# import glob
# import json
# import numpy as np
# import pandas as pd
# import xarray as xr
# import netCDF4 as nc
# import warnings
# from tqdm import tqdm

# warnings.filterwarnings('ignore')

# # ==========================================
# # CONFIGURATION
# # ==========================================
# NLDAS_DIR = '/discover/nobackup/projects/eis_nldas3/DATA/forcing/hourly'
# STATION_DIR = '/discover/nobackup/cmbreen/datacenters/uscrn_independent_data'
# OUTPUT_JSON = './nldas_station_reports_sequential/ALL_STATIONS_NLDAS.json'

# NLDAS_TMP = 'Tair'      
# NLDAS_SPFH = 'Qair'    
# NLDAS_PSURF = 'PSurf'

# os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)

# # ==========================================
# # 1. GATHER ALL STATION COORDINATES
# # ==========================================
# print("Gathering station coordinates...")
# station_files = [f for f in glob.glob(os.path.join(STATION_DIR, '*.csv')) if not os.path.basename(f).startswith('all_')]

# station_meta = []
# for stn_file in station_files:
#     stn_name = os.path.basename(stn_file).replace('.csv', '')
#     df_temp = pd.read_csv(stn_file, nrows=1)
#     if 'latitude' in df_temp.columns and 'longitude' in df_temp.columns:
#         station_meta.append({
#             'Station': stn_name,
#             'lat': df_temp['latitude'].iloc[0],
#             'lon': df_temp['longitude'].iloc[0]
#         })

# df_meta = pd.DataFrame(station_meta)
# stn_names = df_meta['Station'].values
# print(f"Found {len(df_meta)} valid stations.")

# nldas_files = sorted(glob.glob(os.path.join(NLDAS_DIR, '*', '*.nc')))
# print(f"Found {len(nldas_files)} NLDAS files to process.")

# # ==========================================
# # 2. PRE-COMPUTE GRID INDICES
# # ==========================================
# print("Pre-computing nearest grid indices...")
# with xr.open_dataset(nldas_files[0], engine='netcdf4') as ds_ref:
#     lat_var = 'lat' if 'lat' in ds_ref.coords else 'latitude'
#     lon_var = 'lon' if 'lon' in ds_ref.coords else 'longitude'
    
#     grid_lats = ds_ref[lat_var].values
#     grid_lons = ds_ref[lon_var].values

# lat_idxs = [np.abs(grid_lats - stn_lat).argmin() for stn_lat in df_meta['lat']]
# lon_idxs = [np.abs(grid_lons - stn_lon).argmin() for stn_lon in df_meta['lon']]

# # --- THE MAGIC RAM BLOCK MAPPING ---
# # Find the unique rows (Y-indices) so we can pull contiguous blocks
# unique_y_list = sorted(list(set(lat_idxs)))

# # Create a dictionary to map the "Global" Y coordinate to our new "Local" RAM subset
# y_lookup = {global_y: local_y for local_y, global_y in enumerate(unique_y_list)}

# extracted_data = {stn: {} for stn in stn_names}

# # ==========================================
# # 3. EXTRACTION LOOP (THE RAM BLOCK METHOD)
# # ==========================================
# print("Starting RAM Block extraction...")

# for f in tqdm(nldas_files, desc="Processing Files"):
#     try:
#         basename = os.path.basename(f)
#         date_str = basename.split('.')[1][1:]  
#         yearmonth = date_str[:6]               
#         day = date_str   
        
#         with nc.Dataset(f, 'r') as root:
#             # --- HUGE SPEEDUP HERE ---
#             # We index using `unique_y_list`. This tells NetCDF4 to grab all 24 hours 
#             # and all longitudes, but ONLY for the ~160 specific rows we care about. 
#             # This turns 11,500 tiny disk reads into exactly 3 fast block reads!
#             tair_block = root.variables[NLDAS_TMP][:, unique_y_list, :].filled(np.nan)
#             qair_block = root.variables[NLDAS_SPFH][:, unique_y_list, :].filled(np.nan)
#             psurf_block = root.variables[NLDAS_PSURF][:, unique_y_list, :].filled(np.nan)
            
#             # Now we loop through the stations and pull data from RAM instantly
#             for stn_name, y_idx, x_idx in zip(stn_names, lat_idxs, lon_idxs):
                
#                 # Convert the global Y to the local Y of our RAM block
#                 local_y = y_lookup[y_idx]
                
#                 # Instantly slice from the NumPy array in RAM
#                 stn_tair = tair_block[:, local_y, x_idx]
#                 stn_qair = qair_block[:, local_y, x_idx]
#                 stn_psurf = psurf_block[:, local_y, x_idx]
                
#                 if yearmonth not in extracted_data[stn_name]:
#                     extracted_data[stn_name][yearmonth] = {}
                    
#                 extracted_data[stn_name][yearmonth][day] = {
#                     'tair': stn_tair.tolist(),
#                     'qair': stn_qair.tolist(),
#                     'psurf': stn_psurf.tolist()
#                 }
                
#     except Exception as e:
#         print(f"\nError reading {f}: {e}")

# # ==========================================
# # 4. SAVE TO JSON
# # ==========================================
# print("\nSaving to JSON...")
# with open(OUTPUT_JSON, 'w') as jf:
#     json.dump(extracted_data, jf)

# print(f"Extraction complete! Saved to {OUTPUT_JSON}")

'''
try 4, like 2 but with multiprocessing
'''


# import os
# import glob
# import json
# import numpy as np
# import pandas as pd
# import xarray as xr
# import netCDF4 as nc
# import warnings
# from tqdm import tqdm
# from multiprocessing import Pool, cpu_count

# warnings.filterwarnings('ignore')

# # ==========================================
# # CONFIGURATION
# # ==========================================
# NLDAS_DIR = '/discover/nobackup/projects/eis_nldas3/DATA/forcing/hourly'
# STATION_DIR = '/discover/nobackup/cmbreen/datacenters/uscrn_independent_data'
# OUTPUT_JSON = './nldas_station_reports_sequential/ALL_STATIONS_NLDAS.json'

# NLDAS_TMP = 'Tair'      
# NLDAS_SPFH = 'Qair'    
# NLDAS_PSURF = 'PSurf' 

# os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)

# # Define how many CPU cores to use. 
# # Leaves 2 cores free so the node doesn't freeze.
# NUM_WORKERS = max(1, cpu_count() - 2)

# # ==========================================
# # 1. GATHER ALL STATION COORDINATES
# # ==========================================
# print("Gathering station coordinates...")
# station_files = [f for f in glob.glob(os.path.join(STATION_DIR, '*.csv')) if not os.path.basename(f).startswith('all_')]

# station_meta = []
# for stn_file in station_files:
#     stn_name = os.path.basename(stn_file).replace('.csv', '')
#     df_temp = pd.read_csv(stn_file, nrows=1)
#     if 'latitude' in df_temp.columns and 'longitude' in df_temp.columns:
#         station_meta.append({
#             'Station': stn_name,
#             'lat': df_temp['latitude'].iloc[0],
#             'lon': df_temp['longitude'].iloc[0]
#         })

# df_meta = pd.DataFrame(station_meta)
# # These must be globally accessible for the worker processes
# stn_names = df_meta['Station'].values
# print(f"Found {len(df_meta)} valid stations.")

# # ==========================================
# # 2. FIND NLDAS FILES
# # ==========================================
# nldas_files = sorted(glob.glob(os.path.join(NLDAS_DIR, '*', '*.nc')))
# print(f"Found {len(nldas_files)} NLDAS files to process.")

# # ==========================================
# # 3. PRE-COMPUTE GRID INDICES (THE MASSIVE SPEEDUP)
# # ==========================================
# print("Pre-computing nearest grid indices...")
# with xr.open_dataset(nldas_files[0], engine='netcdf4') as ds_ref:
#     lat_var = 'lat' if 'lat' in ds_ref.coords else 'latitude'
#     lon_var = 'lon' if 'lon' in ds_ref.coords else 'longitude'
    
#     grid_lats = ds_ref[lat_var].values
#     grid_lons = ds_ref[lon_var].values

# lat_idxs = [np.abs(grid_lats - stn_lat).argmin() for stn_lat in df_meta['lat']]
# lon_idxs = [np.abs(grid_lons - stn_lon).argmin() for stn_lon in df_meta['lon']]

# # ==========================================
# # 4. THE PARALLEL WORKER FUNCTION
# # ==========================================
# def process_single_file(f):
#     """
#     This function runs on a separate CPU core.
#     It reads ONE file and returns the data for all stations for that day.
#     """
#     try:
#         basename = os.path.basename(f)
#         date_str = basename.split('.')[1][1:]  
#         yearmonth = date_str[:6]               
#         day = date_str   
        
#         # This dictionary will hold just this file's data to send back to the main process
#         day_results = {}
        
#         with nc.Dataset(f, 'r') as root:
#             tair_var = root.variables[NLDAS_TMP]
#             qair_var = root.variables[NLDAS_SPFH]
#             psurf_var = root.variables[NLDAS_PSURF]
            
#             for stn_name, y_idx, x_idx in zip(stn_names, lat_idxs, lon_idxs):
#                 stn_tair = tair_var[:, y_idx, x_idx].filled(np.nan)
#                 stn_qair = qair_var[:, y_idx, x_idx].filled(np.nan)
#                 stn_psurf = psurf_var[:, y_idx, x_idx].filled(np.nan)
                
#                 day_results[stn_name] = {
#                     'tair': stn_tair.tolist(),
#                     'qair': stn_qair.tolist(),
#                     'psurf': stn_psurf.tolist()
#                 }
                
#         return yearmonth, day, day_results, None
        
#     except Exception as e:
#         return None, None, None, f"Error reading {f}: {e}"

# # ==========================================
# # 5. EXECUTE PARALLEL EXTRACTION
# # ==========================================
# # The __name__ == '__main__' block is REQUIRED for multiprocessing to work safely
# if __name__ == '__main__':
#     print(f"Starting lightning-fast PARALLEL extraction on {NUM_WORKERS} cores...")
    
#     extracted_data = {stn: {} for stn in stn_names}
    
#     # Launch the pool of CPU workers
#     with Pool(processes=NUM_WORKERS) as pool:
        
#         # imap_unordered streams results back as soon as ANY file finishes
#         iterator = pool.imap_unordered(process_single_file, nldas_files)
        
#         # Wrap the iterator in tqdm for a single, clean progress bar
#         for yearmonth, day, day_results, error_msg in tqdm(iterator, total=len(nldas_files), desc="Processing Files"):
            
#             if error_msg:
#                 print(f"\n{error_msg}")
#                 continue
                
#             # Merge the results from the worker core into our master dictionary
#             for stn in stn_names:
#                 if yearmonth not in extracted_data[stn]:
#                     extracted_data[stn][yearmonth] = {}
                    
#                 extracted_data[stn][yearmonth][day] = day_results[stn]

#     # ==========================================
#     # 6. SAVE TO JSON
#     # ==========================================
#     print("\nSaving to JSON...")
#     with open(OUTPUT_JSON, 'w') as jf:
#         json.dump(extracted_data, jf)

#     print(f"Extraction complete! Saved to {OUTPUT_JSON}")


'''
try 5 
putting different years on different cores

'''

import os
import glob
import json
import numpy as np
import pandas as pd
import xarray as xr
import netCDF4 as nc
import warnings
from multiprocessing import Pool, cpu_count
from collections import defaultdict

warnings.filterwarnings('ignore')

# ==========================================
# CONFIGURATION
# ==========================================
NLDAS_DIR = '/discover/nobackup/projects/eis_nldas3/DATA/forcing/hourly'
STATION_DIR = '/discover/nobackup/cmbreen/datacenters/uscrn_independent_data'
OUTPUT_JSON = './nldas_station_reports_sequential/ALL_STATIONS_NLDAS.json'

NLDAS_TMP = 'Tair'      
NLDAS_SPFH = 'Qair'    
NLDAS_PSURF = 'PSurf'

os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)

# SLURM-aware CPU Count
slurm_cpus = os.environ.get('SLURM_CPUS_PER_TASK')
if slurm_cpus:
    NUM_WORKERS = int(slurm_cpus)
else:
    NUM_WORKERS = max(1, cpu_count() - 2)

# ==========================================
# 1. GATHER ALL STATION COORDINATES
# ==========================================
print("Gathering station coordinates...")
station_files = [f for f in glob.glob(os.path.join(STATION_DIR, '*.csv')) if not os.path.basename(f).startswith('all_')]

station_meta = []
for stn_file in station_files:
    stn_name = os.path.basename(stn_file).replace('.csv', '')
    df_temp = pd.read_csv(stn_file, nrows=1)
    if 'latitude' in df_temp.columns and 'longitude' in df_temp.columns:
        station_meta.append({
            'Station': stn_name,
            'lat': df_temp['latitude'].iloc[0],
            'lon': df_temp['longitude'].iloc[0]
        })

df_meta = pd.DataFrame(station_meta)
stn_names = df_meta['Station'].values

# ==========================================
# 2. FIND & BATCH NLDAS FILES BY YEAR
# ==========================================
nldas_files = sorted(glob.glob(os.path.join(NLDAS_DIR, '*', '*.nc')))
print(f"Found {len(nldas_files)} NLDAS files.")

print("Batching files by year...")
files_by_year = defaultdict(list)
for f in nldas_files:
    # NLDAS_FOR0010_H.A20010101.030.beta.nc -> '2001'
    year = os.path.basename(f).split('.')[1][1:5]
    files_by_year[year].append(f)

print(f"Divided into {len(files_by_year)} yearly batches.")

# ==========================================
# 3. PRE-COMPUTE GRID INDICES
# ==========================================
print("Pre-computing nearest grid indices...")
with xr.open_dataset(nldas_files[0], engine='netcdf4') as ds_ref:
    lat_var = 'lat' if 'lat' in ds_ref.coords else 'latitude'
    lon_var = 'lon' if 'lon' in ds_ref.coords else 'longitude'
    grid_lats = ds_ref[lat_var].values
    grid_lons = ds_ref[lon_var].values

lat_idxs = [np.abs(grid_lats - stn_lat).argmin() for stn_lat in df_meta['lat']]
lon_idxs = [np.abs(grid_lons - stn_lon).argmin() for stn_lon in df_meta['lon']]

# ==========================================
# 4. THE YEARLY WORKER FUNCTION
# ==========================================
def process_single_year(batch_data):
    """
    Worker function: Processes a whole year of files on a single core.
    """
    year, files = batch_data
    print(f"  -> Worker started on Year {year} ({len(files)} files)...", flush=True)
    
    # Dictionary to hold ONLY this year's data
    year_results = {stn: {} for stn in stn_names}
    error_count = 0
    import tqdm
    for f in tqdm.tqdm(files):
        try:
            basename = os.path.basename(f)
            date_str = basename.split('.')[1][1:]  
            yearmonth = date_str[:6]               
            day = date_str   
            
            with nc.Dataset(f, 'r') as root:
                tair_var = root.variables[NLDAS_TMP]
                qair_var = root.variables[NLDAS_SPFH]
                psurf_var = root.variables[NLDAS_PSURF]
                
                for stn_name, y_idx, x_idx in zip(stn_names, lat_idxs, lon_idxs):
                    stn_tair = tair_var[:, y_idx, x_idx].filled(np.nan)
                    stn_qair = qair_var[:, y_idx, x_idx].filled(np.nan)
                    stn_psurf = psurf_var[:, y_idx, x_idx].filled(np.nan)
                    
                    if yearmonth not in year_results[stn_name]:
                        year_results[stn_name][yearmonth] = {}
                        
                    year_results[stn_name][yearmonth][day] = {
                        'tair': stn_tair.tolist(),
                        'qair': stn_qair.tolist(),
                        'psurf': stn_psurf.tolist()
                    }
                    print(year, f)
        except Exception as e:
            error_count += 1
            
    print(f"  <- Worker FINISHED Year {year}. (Errors: {error_count})", flush=True)
    return year, year_results

# ==========================================
# 5. EXECUTE PARALLEL BATCHES
# ==========================================
if __name__ == '__main__':
    print(f"\nStarting Batched PARALLEL extraction on {NUM_WORKERS} cores...")
    
    extracted_data = {stn: {} for stn in stn_names}
    
    # Prepare the task list: [(2001, [file1, file2...]), (2002, [file1, file2...])]
    tasks = list(files_by_year.items())
    
    with Pool(processes=NUM_WORKERS) as pool:
        # imap_unordered yields the results as soon as a year finishes
        for year, year_results in pool.imap_unordered(process_single_year, tasks):
            
            # Merge the completed year into the master dictionary
            for stn in stn_names:
                # Update our master dict with the year's worth of data for this station
                extracted_data[stn].update(year_results[stn])

    # ==========================================
    # 6. SAVE TO JSON
    # ==========================================
    print("\nSaving to JSON...")
    with open(OUTPUT_JSON, 'w') as jf:
        json.dump(extracted_data, jf)

    print(f"Extraction complete! Saved to {OUTPUT_JSON}")