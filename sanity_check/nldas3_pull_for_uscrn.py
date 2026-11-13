'''
This code does a point extraction on all the uscrn stations simulatneously for all nldas3 data and then we will do all the bias analysis etc afterwards. 
This will hopefully minimize everything so that it just runs once 


'''

import os
import glob
import pandas as pd
import xarray as xr
import warnings

warnings.filterwarnings('ignore')

# ==========================================
# CONFIGURATION
# ==========================================
PROCESS_ALL_YEARS = True

NLDAS_DIR = '/discover/nobackup/projects/eis_nldas3/DATA/forcing/hourly'
STATION_DIR = '/discover/nobackup/cmbreen/datacenters/uscrn_independent_data'
OUTPUT_CSV = './nldas_station_reports_sequential/ALL_STATIONS_NLDAS_EXTRACTED.csv'

NLDAS_TMP = 'Tair'      
NLDAS_SPFH = 'Qair'    
NLDAS_PSURF = 'Psurf'    

os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)

# ==========================================
# 1. GATHER ALL STATION COORDINATES
# ==========================================
print("Gathering station coordinates...")
station_files = [f for f in glob.glob(os.path.join(STATION_DIR, '*.csv')) if not os.path.basename(f).startswith('all_')]

station_meta = []
for stn_file in station_files:
    stn_name = os.path.basename(stn_file).replace('.csv', '')
    # Just read the first row to get the lat/lon
    df_temp = pd.read_csv(stn_file, nrows=1)
    if 'latitude' in df_temp.columns and 'longitude' in df_temp.columns:
        station_meta.append({
            'Station': stn_name,
            'lat': df_temp['latitude'].iloc[0],
            'lon': df_temp['longitude'].iloc[0]
        })

df_meta = pd.DataFrame(station_meta)
print(f"Found {len(df_meta)} valid stations.")

# Create Xarray DataArrays for vectorized extraction
lats_da = xr.DataArray(df_meta['lat'].values, dims='Station')
lons_da = xr.DataArray(df_meta['lon'].values, dims='Station')
stns_da = xr.DataArray(df_meta['Station'].values, dims='Station')

# ==========================================
# 2. FIND NLDAS FILES
# ==========================================
if PROCESS_ALL_YEARS:
    nldas_pattern = os.path.join(NLDAS_DIR, '*', '*.nc')
else:
    nldas_pattern = os.path.join(NLDAS_DIR, '2018*', '*.nc')
    
nldas_files = sorted(glob.glob(nldas_pattern))
print(f"Found {len(nldas_files)} NLDAS files to process.")

# ==========================================
# 3. VECTORIZED EXTRACTION LOOP
# ==========================================
print("Starting extraction...")

# Initialize CSV with headers
pd.DataFrame(columns=['Station', 'datetime', 'Tair', 'Qair', 'Psurf']).to_csv(OUTPUT_CSV, index=False)

buffer = []
chunk_size = 100  # Write to disk every 500 files to save RAM

for i, f in enumerate(nldas_files):
    try:
        with xr.open_dataset(f, engine='netcdf4') as ds:
            lat_var = 'lat' if 'lat' in ds.coords else 'latitude'
            lon_var = 'lon' if 'lon' in ds.coords else 'longitude'
            
            # --- THE MAGIC FORMULA ---
            # This extracts all stations at once using nearest neighbor
            ds_pts = ds.sel({lat_var: lats_da, lon_var: lons_da}, method='nearest')
            
            # Attach the actual station names as a coordinate
            ds_pts = ds_pts.assign_coords(Station=stns_da)
            
            # Convert to pandas dataframe
            df_pt = ds_pts[[NLDAS_TMP, NLDAS_SPFH, NLDAS_PSURF]].to_dataframe().reset_index()
            
            # Clean up columns (rename 'time' to 'datetime')
            time_var = 'time' if 'time' in df_pt.columns else 'valid_time'
            df_pt = df_pt.rename(columns={time_var: 'datetime'})
            
            # Keep only what we need
            df_pt = df_pt[['Station', 'datetime', NLDAS_TMP, NLDAS_SPFH, NLDAS_PSURF]]
            
            buffer.append(df_pt)
            print(f)
            
    except Exception as e:
        print(f"Error reading {f}: {e}")
        
    # Write to disk in chunks to prevent memory overload
    if (i + 1) % chunk_size == 0 or (i + 1) == len(nldas_files):
        if buffer:
            chunk_df = pd.concat(buffer, ignore_index=True)
            chunk_df.to_csv(OUTPUT_CSV, mode='a', header=False, index=False)
            buffer = [] # clear memory
        print(f"Processed {i + 1}/{len(nldas_files)} files...")

print(f"\nExtraction complete! Saved to {OUTPUT_CSV}")