import xarray as xr
import pandas as pd
import numpy as np
import os
import glob
import tqdm

# ==========================================
# 1. CONFIGURATION
# ==========================================
INPUT_CSV = '/discover/nobackup/cmbreen/datacenters/im3_open_source_data_center_atlas_v2026.02.09.csv'
BASE_OUTPUT_DIR = '/discover/nobackup/cmbreen/datacenters/nldas3_master_hourly'
BASE_FORCING_PATH = '/discover/nobackup/projects/eis_nldas3/DATA/forcing/hourly'

BUFFER_DEG = 0.015  # 3km bounding box
YEARS = range(2000, 2023)  # Adjust to the years you need

os.makedirs(BASE_OUTPUT_DIR, exist_ok=True)

# ==========================================
# 2. PROCESSING FUNCTION
# ==========================================
def process_single_datacenter(dc_id, lat, lon, state, utc_offset):
    state_dir = os.path.join(BASE_OUTPUT_DIR, state)
    os.makedirs(state_dir, exist_ok=True)
    
    final_out = os.path.join(state_dir, f"dc_{dc_id}_nldas3_hourly_master.nc")
    
    # SMART SKIP: Skip if we already finished this datacenter
    if os.path.exists(final_out):
        return
        
    lat_slice = slice(lat - BUFFER_DEG, lat + BUFFER_DEG)
    lon_slice = slice(lon - BUFFER_DEG, lon + BUFFER_DEG)
    
    def subset_spatial(ds_single):
        return ds_single.sel(lat=lat_slice, lon=lon_slice)
    
    yearly_datasets = []
    
    # Loop through each year, load it, process it
    for year in YEARS:
        forcing_files = sorted(glob.glob(os.path.join(BASE_FORCING_PATH, f'{year}*/*.nc')))
        if not forcing_files:
            continue
            
        try:
            # 1. Open the year using the preprocess trick to save RAM
            ds = xr.open_mfdataset(
                forcing_files, 
                combine='by_coords', 
                preprocess=subset_spatial,
                join='override',
                parallel=False,  
                engine='netcdf4'
            )
            
            # Load the tiny 3x3 box into memory
            ds_nova = ds.load()
            
            # 2. Calculate Thermodynamics
            temp = ds_nova['Tair'] - 273.15
            humidity = ds_nova['Qair']
            pressure = ds_nova['PSurf']
            
            W = humidity / (1.0 - humidity)
            enthalpy = 1.006 * temp + W * (2501.0 + 1.86 * temp)
            
            ds_derived = xr.Dataset({
                'Tair_C': temp,
                'Qair': humidity,
                'PSurf': pressure,
                'enthalpy': enthalpy
            })

            # 3. TIMEZONE ADJUSTMENT (Shift to Local Standard Time for TMY comparison)
            ds_derived['time'] = ds_derived['time'] + pd.Timedelta(hours=utc_offset)
            
            # 4. THE 12-HOUR BLOCK TRICK FOR DAY/NIGHT MIN/MAX
            # Shift time by 6 hours temporarily. 
            # 6 AM LST becomes 12 PM. 6 PM LST becomes 12 AM (00:00).
            ds_derived['shifted_time'] = ds_derived['time'] + pd.Timedelta(hours=6)
            
            # Swap dimension to shifted_time so we can resample it
            ds_derived = ds_derived.swap_dims({'time': 'shifted_time'})
            
            # Resample into exact 12-hour blocks (00:00 to 11:59 is Night, 12:00 to 23:59 is Day)
            block_max = ds_derived[['Tair_C', 'enthalpy']].resample(shifted_time='12H').max()
            block_min = ds_derived[['Tair_C', 'enthalpy']].resample(shifted_time='12H').min()
            
            # "Smear" (forward-fill) those block maximums back onto every hour within the block
            hourly_max = block_max.reindex(shifted_time=ds_derived['shifted_time'], method='ffill')
            hourly_min = block_min.reindex(shifted_time=ds_derived['shifted_time'], method='ffill')
            
            # Assign the smeared values back to the dataset
            ds_derived['Period_Tair_max'] = hourly_max['Tair_C']
            ds_derived['Period_Tair_min'] = hourly_min['Tair_C']
            ds_derived['Period_enthalpy_max'] = hourly_max['enthalpy']
            
            # Swap the dimensions back to the pure LST Time!
            ds_derived = ds_derived.swap_dims({'shifted_time': 'time'})
            ds_derived = ds_derived.drop_vars('shifted_time')
            
            # 5. Add a helper flag so you know if the "Period" is Day or Night
            ds_derived['is_daytime'] = (ds_derived['time'].dt.hour >= 6) & (ds_derived['time'].dt.hour < 18)
            
            yearly_datasets.append(ds_derived)
            ds.close()
            
        except Exception as e:
            # Catches empty spatial slices (datacenter out of bounds)
            continue
            
    # 6. STITCH ALL YEARS TOGETHER AND SAVE
    if yearly_datasets:
        ds_final = xr.concat(yearly_datasets, dim='time')
        
        # Add metadata
        ds_final['Tair_C'].attrs = {'units': 'Celsius', 'long_name': 'Hourly Dry Bulb'}
        ds_final['enthalpy'].attrs = {'units': 'kJ/kg'}
        ds_final['Period_Tair_max'].attrs = {'units': 'Celsius', 'long_name': 'Max Temp for the current Day/Night Period'}
        ds_final.attrs['utc_offset'] = utc_offset
        
        ds_final.to_netcdf(final_out)
        ds_final.close()

# ==========================================
# 3. MAIN EXECUTION
# ==========================================
if __name__ == "__main__":
    print("Loading datacenter locations...")
    df_dc = pd.read_csv(INPUT_CSV)
    
    state_col = next((col for col in df_dc.columns if 'state' in col.lower()), None)
    if not state_col:
        df_dc['state'] = 'unknown'
        state_col = 'state'
        
    print(f"Starting extraction for {len(df_dc)} datacenters...\n")
    
    for idx, row in tqdm.tqdm(df_dc.iterrows(), total=len(df_dc)):
        dc_id = str(row['id'])
        state = str(row[state_col]).strip().lower().replace(' ', '_')
        lat = float(row['lat'])
        lon = float(row['lon'])
        
        # DYNAMIC TIMEZONE CALCULATION
        # Longitude divided by 15 gives standard UTC offset (e.g. -97 / 15 = -6.46 -> -6 CST)
        utc_offset = int(round(lon / 15.0))
        
        process_single_datacenter(dc_id, lat, lon, state, utc_offset)

    print("\nFinished processing all datacenters!")