import xarray as xr
import pandas as pd
import numpy as np
import os
import glob
from tqdm import tqdm

# ==========================================
# 1. CONFIGURATION
# ==========================================
INPUT_CSV = '~/INNOVATE/im3_open_source_data_center_atlas_v2026.02.09.csv'
BASE_OUTPUT_DIR = '/discover/nobackup/cmbreen/datacenters/nldas3_master_csv'
BASE_FORCING_PATH = '/discover/nobackup/projects/eis_nldas3/DATA/forcing/hourly'
YEARS = range(2000, 2023)

os.makedirs(BASE_OUTPUT_DIR, exist_ok=True)

# ==========================================
# 2. LOAD ALL DATACENTERS
# ==========================================
print("Loading datacenter locations...")
df_dc = pd.read_csv(INPUT_CSV)

# Calculate UTC offset for each datacenter right now
df_dc['utc_offset'] = (df_dc['lon'] / 15.0).round().astype(int)

# ⚠️ THE XARRAY TRICK: 
# We turn the pandas columns into xarray DataArrays. 
# This lets xarray extract all points simultaneously!
target_lats = xr.DataArray(df_dc['lat'].values, dims='datacenter')
target_lons = xr.DataArray(df_dc['lon'].values, dims='datacenter')
target_ids = df_dc['id'].values
target_offsets = df_dc['utc_offset'].values

# ==========================================
# 3. YEARLY PROCESSING LOOP
# ==========================================
for year in YEARS:
    out_csv = os.path.join(BASE_OUTPUT_DIR, f"datacenters_nldas3_{year}.csv")
    
    if os.path.exists(out_csv):
        print(f"Skipping {year}, already processed.")
        continue
        
    forcing_files = sorted(glob.glob(os.path.join(BASE_FORCING_PATH, f'{year}*/*.nc')))
    if not forcing_files:
        print(f"No files found for {year}")
        continue
        
    print(f"\n--- Processing {year} ({len(forcing_files)} files) ---")
    
    # 1. Open the whole year lazily
    ds = xr.open_mfdataset(
        forcing_files, 
        combine='by_coords', 
        join='override',
        parallel=False,  
        engine='netcdf4'
    )
    
    # 2. THE MAGIC: Extract all 500 datacenters instantly!
    # method='nearest' snaps to the closest NLDAS-3 grid cell
    print("Extracting all spatial points...")
    ds_points = ds.sel(lat=target_lats, lon=target_lons, method='nearest')
    
    # 3. Load into RAM (This is safe now! It's only extracting the exact pixels we need)
    ds_points = ds_points.load()
    ds.close() # Free up the file handles immediately
    
    # 4. Convert directly to a massive Pandas DataFrame
    print("Converting to Pandas and calculating thermodynamics...")
    df_year = ds_points.to_dataframe().reset_index()
    
    # Clean up the dataframe
    # 'datacenter' is the index (0 to 499). Let's map the real IDs and offsets back to it.
    df_year['dc_id'] = df_year['datacenter'].map(lambda x: target_ids[x])
    df_year['utc_offset'] = df_year['datacenter'].map(lambda x: target_offsets[x])
    
    # Drop the xarray index column and lat/lon since we just need the dc_id
    df_year = df_year.drop(columns=['datacenter', 'lat', 'lon'])
    
    # ==========================================
    # 5. PANDAS MATH (Blazingly Fast)
    # ==========================================
    # Thermodynamics
    df_year['Tair_C'] = df_year['Tair'] - 273.15
    df_year['W'] = df_year['Qair'] / (1.0 - df_year['Qair'])
    df_year['enthalpy'] = 1.006 * df_year['Tair_C'] + df_year['W'] * (2501.0 + 1.86 * df_year['Tair_C'])
    
    # Apply UTC Offset dynamically per row
    # Convert 'time' to datetime if it isn't already, then apply the offset
    df_year['time'] = pd.to_datetime(df_year['time'])
    df_year['local_time'] = df_year['time'] + pd.to_timedelta(df_year['utc_offset'], unit='h')
    
    # Sort so the data is grouped nicely by datacenter, then by time
    df_year = df_year.sort_values(['dc_id', 'local_time'])
    
    # Drop intermediate columns to save file space
    df_year = df_year.drop(columns=['Tair', 'W'])
    
    # # 6. Save the massive yearly file
    # print(f"Saving {year} CSV...")
    # df_year.to_csv(out_csv, index=False)
    
    #NOTE: If the CSV is too big (>2 GB), change the above line to:
    df_year.to_parquet(out_csv.replace('.csv', '.parquet'), index=False)
    #Parquet is 10x smaller and 100x faster to load in Pandas later!
    
print("\nFINISHED! All data extracted.")