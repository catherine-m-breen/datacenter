'''
This took wayyy too long 

'''

# import xarray as xr
# import pandas as pd
# import numpy as np
# import os
# import glob
# import tqdm

# # ==========================================
# # 1. CONFIGURATION
# # ==========================================
# #INPUT_CSV = '/discover/nobackup/cmbreen/datacenters/im3_open_source_data_center_atlas_v2026.02.09.csv'
# INPUT_CSV = '~/INNOVATE/im3_open_source_data_center_atlas_v2026.02.09.csv'
# BASE_OUTPUT_DIR = '/discover/nobackup/cmbreen/datacenters/nldas3_master_hourly'
# BASE_FORCING_PATH = '/discover/nobackup/projects/eis_nldas3/DATA/forcing/hourly'
# BUFFER_DEG = 0.15  # Approx. 5-mile buffer, creating a 10x10 mile bounding box
# YEARS = range(2000, 2023)  # Adjust to the years you need

# os.makedirs(BASE_OUTPUT_DIR, exist_ok=True)


# '''

# ==================================================
# ALL VARIABLES FOUND:
# ==================================================
# Name: Tair            | Units: K          | Desc: 2-meter above ground Temperature
# Name: Qair            | Units: kg kg-1    | Desc: 2-meter above ground Specific humidity
# Name: PSurf           | Units: Pa         | Desc: Surface pressure
# Name: LWdown          | Units: W m-2      | Desc: Longwave radiation flux downwards (surface)
# Name: SWdown          | Units: W m-2      | Desc: Shortwave radiation flux downwards (surface)
# Name: Wind_N          | Units: m s-1      | Desc: 10-meter above ground Meridional wind speed
# Name: Wind_E          | Units: m s-1      | Desc: 10-meter above ground Zonal wind speed
# Name: Rainf           | Units: kg m-2     | Desc: Total precipitation
# >>> 

# '''
# # ==========================================
# # 2. PROCESSING FUNCTION
# # ==========================================
# def process_single_datacenter(dc_id, lat, lon, state, utc_offset):
#     state_dir = os.path.join(BASE_OUTPUT_DIR, state)
#     os.makedirs(state_dir, exist_ok=True)
    
#     final_out = os.path.join(state_dir, f"dc_{dc_id}_nldas3_hourly_master.nc")
    
#     # SMART SKIP: Skip if we already finished this datacenter
#     if os.path.exists(final_out):
#         return
        
#     lat_slice = slice(lat - BUFFER_DEG, lat + BUFFER_DEG)
#     lon_slice = slice(lon - BUFFER_DEG, lon + BUFFER_DEG)
    
#     def subset_spatial(ds_single):
#         return ds_single.sel(lat=lat_slice, lon=lon_slice)
    
#     yearly_datasets = []
    
#     # Loop through each year, load it, process it
#     for year in YEARS:
#         forcing_files = sorted(glob.glob(os.path.join(BASE_FORCING_PATH, f'{year}*/*.nc')))
#         if not forcing_files:
#             continue
            
#         try:
#             # 1. Open the year using the preprocess trick to save RAM
#             ds = xr.open_mfdataset(
#                 forcing_files, 
#                 combine='by_coords', 
#                 preprocess=subset_spatial,
#                 join='override',
#                 parallel=False,  
#                 engine='netcdf4'
#             )
            
#             # Load the tiny 3x3 box into memory
#             ds_nova = ds.load()
            
#             # 2. Calculate Thermodynamics
#             temp = ds_nova['Tair'] - 273.15
#             humidity = ds_nova['Qair']
#             pressure = ds_nova['PSurf']
#             wind_N = ds_nova['Wind_N']
#             wind_E = ds_nova['Wind_E']
#             Rainf = ds_nova['Rainf']

#             W = humidity / (1.0 - humidity)
#             enthalpy = 1.006 * temp + W * (2501.0 + 1.86 * temp)
            
#             ds_derived = xr.Dataset({
#                 'Tair_C': temp,
#                 'Qair': humidity,
#                 'PSurf': pressure,
#                 'enthalpy': enthalpy, 
#                 'wind_N': wind_N, 
#                 'wind_E': wind_E, 
#                 'Rainf': Rainf, 

#             })

#             # 3. TIMEZONE ADJUSTMENT (Shift to Local Standard Time for TMY comparison)
#             ds_derived['time'] = ds_derived['time'] + pd.Timedelta(hours=utc_offset)
            
#             # 4. THE 12-HOUR BLOCK TRICK FOR DAY/NIGHT MIN/MAX
#             # Shift time by 6 hours temporarily. 
#             # 6 AM LST becomes 12 PM. 6 PM LST becomes 12 AM (00:00).
#             ds_derived['shifted_time'] = ds_derived['time'] + pd.Timedelta(hours=6)
            
#             # Swap dimension to shifted_time so we can resample it
#             ds_derived = ds_derived.swap_dims({'time': 'shifted_time'})
            
#             # Resample into exact 12-hour blocks (00:00 to 11:59 is Night, 12:00 to 23:59 is Day)
#             block_max = ds_derived[['Tair_C', 'enthalpy']].resample(shifted_time='12H').max()
#             block_min = ds_derived[['Tair_C', 'enthalpy']].resample(shifted_time='12H').min()
            
#             # "Smear" (forward-fill) those block maximums back onto every hour within the block
#             hourly_max = block_max.reindex(shifted_time=ds_derived['shifted_time'], method='ffill')
#             hourly_min = block_min.reindex(shifted_time=ds_derived['shifted_time'], method='ffill')
            
#             # Assign the smeared values back to the dataset
#             ds_derived['Period_Tair_max'] = hourly_max['Tair_C']
#             ds_derived['Period_Tair_min'] = hourly_min['Tair_C']
#             ds_derived['Period_enthalpy_max'] = hourly_max['enthalpy']
            
#             # Swap the dimensions back to the pure LST Time!
#             ds_derived = ds_derived.swap_dims({'shifted_time': 'time'})
#             ds_derived = ds_derived.drop_vars('shifted_time')
            
#             # 5. Add a helper flag so you know if the "Period" is Day or Night
#             ds_derived['is_daytime'] = (ds_derived['time'].dt.hour >= 6) & (ds_derived['time'].dt.hour < 18)
            
#             yearly_datasets.append(ds_derived)
#             ds.close()
            
#         except Exception as e:
#             # Catches empty spatial slices (datacenter out of bounds)
#             continue
            
#     # 6. STITCH ALL YEARS TOGETHER AND SAVE
#     if yearly_datasets:
#         ds_final = xr.concat(yearly_datasets, dim='time')
        
#         # Add metadata
#         ds_final['Tair_C'].attrs = {'units': 'Celsius', 'long_name': 'Hourly Dry Bulb'}
#         ds_final['enthalpy'].attrs = {'units': 'kJ/kg'}
#         ds_final['Period_Tair_max'].attrs = {'units': 'Celsius', 'long_name': 'Max Temp for the current Day/Night Period'}
#         ds_final.attrs['utc_offset'] = utc_offset
        
#         ds_final.to_netcdf(final_out)
#         ds_final.close()

# # ==========================================
# # 3. MAIN EXECUTION
# # ==========================================
# if __name__ == "__main__":
#     print("Loading datacenter locations...")
#     df_dc = pd.read_csv(INPUT_CSV)
    
#     state_col = next((col for col in df_dc.columns if 'state' in col.lower()), None)
#     if not state_col:
#         df_dc['state'] = 'unknown'
#         state_col = 'state'
        
#     print(f"Starting extraction for {len(df_dc)} datacenters...\n")
    
#     for idx, row in tqdm.tqdm(df_dc.iterrows(), total=len(df_dc)):
#         dc_id = str(row['id'])
#         state = str(row[state_col]).strip().lower().replace(' ', '_')
#         lat = float(row['lat'])
#         lon = float(row['lon'])
        
#         # DYNAMIC TIMEZONE CALCULATION
#         # Longitude divided by 15 gives standard UTC offset (e.g. -97 / 15 = -6.46 -> -6 CST)
#         utc_offset = int(round(lon / 15.0))
        
#         process_single_datacenter(dc_id, lat, lon, state, utc_offset)

#     print("\nFinished processing all datacenters!")

'''
take 2 

we will try to parallelize this across nodes and cpus 


'''

import os
import glob
import numpy as np
import pandas as pd
import xarray as xr
import netCDF4 as nc
import warnings
from multiprocessing import Pool, cpu_count
from collections import defaultdict
import metpy.calc as mpcalc
from metpy.units import units

warnings.filterwarnings('ignore')

# ==========================================
# CONFIGURATION
# ==========================================
NLDAS_DIR = '/discover/nobackup/projects/eis_nldas3/DATA/forcing/hourly'
TMY_BASE_DIR = '/discover/nobackup/cmbreen/datacenters/noaa_tmy_downloads_datacenterslocs/zip'
OUTPUT_DIR = '/discover/nobackup/cmbreen/datacenters/nldas_datacenter_subsets'

TARGET_STATES = ['TX', 'IL', 'OH', 'VA', 'IA', 'NC', 'NM', 'NE']
os.makedirs(OUTPUT_DIR, exist_ok=True)

# NLDAS Variable names 
VARS_TO_EXTRACT = {
    'Tair': 'Tair',    # K
    'Qair': 'Qair',    # kg/kg
    'PSurf': 'PSurf',  # Pa
    'Rainf': 'Rainf',  # kg m-2 s-1 (mm/s)
    'Wind': 'Wind'     # m/s
}

slurm_cpus = os.environ.get('SLURM_CPUS_PER_TASK')
NUM_WORKERS = int(slurm_cpus) if slurm_cpus else max(1, cpu_count() - 2)

# ==========================================
# 1. GATHER DATACENTER COORDINATES
# ==========================================
print("Gathering datacenter coordinates from target states...")
station_meta = []
for meta_file in glob.glob(f'{TMY_BASE_DIR}/*/*-metadata.csv'):
    df_temp = pd.read_csv(meta_file)
    state = df_temp['State'].iloc[0]
    
    if state in TARGET_STATES:
        station_meta.append({
            'Station': df_temp['USAF'].iloc[0], # Using USAF ID as station name
            'State': state,
            'lat': df_temp['Latitude'].iloc[0],
            'lon': df_temp['Longitude'].iloc[0]
        })

df_meta = pd.DataFrame(station_meta)
stn_names = df_meta['Station'].values
# print(f"Found {len(df_meta)} datacenters in prioritized states.")

import sys # add this to your imports

# ==========================================
# 1. GATHER DATACENTER COORDINATES
# ==========================================
# ... [Keep your existing code that builds df_meta] ...
print(f"Total datacenters found: {len(df_meta)}")

# --- NEW: SLURM JOB ARRAY CHUNKING ---
CHUNK_SIZE = 100  # Number of datacenters per node

# Default to 0 if running interactively without an array
task_id = int(os.environ.get('SLURM_ARRAY_TASK_ID', 0))

start_idx = task_id * CHUNK_SIZE
end_idx = min(start_idx + CHUNK_SIZE, len(df_meta))

# Slice the dataframe to only keep this node's datacenters
df_meta = df_meta.iloc[start_idx:end_idx]

if df_meta.empty:
    print(f"Task ID {task_id}: No datacenters in this chunk. Exiting.")
    sys.exit(0)

stn_names = df_meta['Station'].values
print(f"Node (Task {task_id}) processing datacenters {start_idx} to {end_idx-1} ({len(df_meta)} total).")


# ==========================================
# 2. FIND & BATCH NLDAS FILES BY YEAR
# ==========================================
nldas_files = sorted(glob.glob(os.path.join(NLDAS_DIR, '*', '*.nc')))
print(f"Found {len(nldas_files)} NLDAS files.")

files_by_year = defaultdict(list)
for f in nldas_files:
    year = os.path.basename(f).split('.')[1][1:5]
    files_by_year[year].append(f)

# ==========================================
# 3. PRE-COMPUTE 15x15 KM BOUNDING BOX INDICES
# ==========================================
print("Pre-computing bounding box grid indices (~15x15 km)...")
with xr.open_dataset(nldas_files[0], engine='netcdf4') as ds_ref:
    lat_var = 'lat' if 'lat' in ds_ref.coords else 'latitude'
    lon_var = 'lon' if 'lon' in ds_ref.coords else 'longitude'
    grid_lats = ds_ref[lat_var].values
    grid_lons = ds_ref[lon_var].values

# 1 degree is ~111 km. 7.5 km in all directions gives a 15x15 box.
DEG_BUFFER = 7.5 / 111.0 
stn_boxes = {}

for _, row in df_meta.iterrows():
    stn = row['Station']
    stn_lat, stn_lon = row['lat'], row['lon']
    
    # Boolean masks for lat/lon within buffer
    y_mask = (grid_lats >= stn_lat - DEG_BUFFER) & (grid_lats <= stn_lat + DEG_BUFFER)
    x_mask = (grid_lons >= stn_lon - DEG_BUFFER) & (grid_lons <= stn_lon + DEG_BUFFER)
    
    # If the point falls directly in the center of a pixel and misses the buffer, force minimum 1 nearest pixel
    if not y_mask.any():
        y_mask[np.abs(grid_lats - stn_lat).argmin()] = True
    if not x_mask.any():
        x_mask[np.abs(grid_lons - stn_lon).argmin()] = True
        
    y_indices = np.where(y_mask)[0]
    x_indices = np.where(x_mask)[0]
    
    stn_boxes[stn] = {
        'y_slice': slice(y_indices[0], y_indices[-1] + 1),
        'x_slice': slice(x_indices[0], x_indices[-1] + 1),
        'lats': grid_lats[y_indices[0]:y_indices[-1] + 1],
        'lons': grid_lons[x_indices[0]:x_indices[-1] + 1]
    }

# ==========================================
# 4. YEARLY WORKER FUNCTION
# ==========================================
def process_single_year(batch_data):
    year, files = batch_data
    
    # Initialize dict to hold time-series arrays for this year
    year_results = {stn: {'times': []} for stn in stn_names}
    for stn in stn_names:
        for v in VARS_TO_EXTRACT.keys():
            year_results[stn][v] = []

    for f in files:
        try:
            basename = os.path.basename(f)
            # Example: NLDAS_FOR0010_H.A20010101.030.beta.nc
            date_str = basename.split('.')[1][1:] # '20010101'
            hour_str = basename.split('.')[2][:2] # '03'
            dt = pd.to_datetime(f"{date_str}{hour_str}", format="%Y%m%d%H")
            
            with nc.Dataset(f, 'r') as root:
                for stn in stn_names:
                    box = stn_boxes[stn]
                    year_results[stn]['times'].append(dt)
                    
                    for var_name, nc_var in VARS_TO_EXTRACT.items():
                        # Extract the slice: [time, lat_slice, lon_slice]
                        data_slice = root.variables[nc_var][:, box['y_slice'], box['x_slice']].filled(np.nan)
                        year_results[stn][var_name].append(data_slice)
        except Exception as e:
            continue
            
    # Concatenate the lists along the time axis
    for stn in stn_names:
        if year_results[stn]['times']:
            for v in VARS_TO_EXTRACT.keys():
                year_results[stn][v] = np.concatenate(year_results[stn][v], axis=0)
                
    return year, year_results

# ==========================================
# 5. EXECUTE BATCHES & ASSEMBLE NetCDF
# ==========================================
if __name__ == '__main__':
    print(f"\nStarting extraction on {NUM_WORKERS} cores...")
    
    # Prepare master storage dict
    master_data = {stn: {'times': []} for stn in stn_names}
    for stn in stn_names:
        for v in VARS_TO_EXTRACT.keys():
            master_data[stn][v] = []

    tasks = list(files_by_year.items())
    
    with Pool(processes=NUM_WORKERS) as pool:
        for year, year_results in pool.imap_unordered(process_single_year, tasks):
            print(f"Finished extracting year: {year}")
            for stn in stn_names:
                if year_results[stn]['times']:
                    master_data[stn]['times'].extend(year_results[stn]['times'])
                    master_data[stn][v].append(year_results[stn][v])

    print("\nExtraction complete! Calculating Thermodynamics and saving NetCDFs...")
    
    for stn in stn_names:
        times = master_data[stn]['times']
        if not times:
            continue
            
        # Sort by time just in case unordered multiprocessing mixed them up
        sort_idx = np.argsort(times)
        times = np.array(times)[sort_idx]
        
        # Build Xarray Dataset
        ds_vars = {}
        box = stn_boxes[stn]
        
        for v in VARS_TO_EXTRACT.keys():
            # Stack the yearly blocks together and sort by time
            arr = np.concatenate(master_data[stn][v], axis=0)[sort_idx]
            
            # Precip fix: convert kg m-2 s-1 to mm/hour (multiply by 3600)
            if v == 'Rainf':
                arr = arr * 3600
                
            ds_vars[v] = (['time', 'lat', 'lon'], arr)
            
        ds = xr.Dataset(
            data_vars=ds_vars,
            coords={
                'time': times,
                'lat': box['lats'],
                'lon': box['lons']
            },
            attrs={'Datacenter_USAF': stn, 'Description': '15x15km NLDAS-3 Subset'}
        )

        # --- CALCULATE THERMODYNAMICS ---
        print(f"Calculating Wet Bulb and Enthalpy for {stn}...")
        
        # Flatten spatial dimensions for MetPy calculations
        tair_c = (ds['Tair'].values - 273.15) * units.degC
        psurf_pa = ds['PSurf'].values * units.Pa
        qair = ds['Qair'].values # dimensionless (kg/kg)
        
        # Calculate Relative Humidity from Specific Humidity
        rh = mpcalc.relative_humidity_from_specific_humidity(psurf_pa, tair_c, qair)
        
        # Calculate Dew Point
        dewpoint = mpcalc.dewpoint_from_relative_humidity(tair_c, rh)
        
        # Wet Bulb Temperature
        wet_bulb = mpcalc.wet_bulb_temperature(psurf_pa, tair_c, dewpoint).m
        ds['Wet_Bulb_C'] = (['time', 'lat', 'lon'], wet_bulb)
        
        # Moist Enthalpy (approximate moist static energy in kJ/kg)
        enthalpy = mpcalc.moist_static_energy(psurf_pa, tair_c, dewpoint).m / 1000
        ds['Enthalpy_kJ_kg'] = (['time', 'lat', 'lon'], enthalpy)

        # --- SAVE NetCDF ---
        out_file = os.path.join(OUTPUT_DIR, f"{stn}_NLDAS_Subset.nc")
        ds.to_netcdf(out_file)
        print(f"Saved {out_file}")

    print("All tasks complete!")