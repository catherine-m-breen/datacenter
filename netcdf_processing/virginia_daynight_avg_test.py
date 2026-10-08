import xarray as xr
import pandas as pd
import os
import glob

def process_hourly_chunk(forcing_files, output_dir, lat_slice, lon_slice, prefix, chunk_name):
    # Pass 1: Extract, calculate variables, and save HOURLY data
    out_filename = os.path.join(output_dir, f"{prefix}_{chunk_name}_hourly_derived.nc")
    
    if os.path.exists(out_filename):
        print(f"  -> Skipping {chunk_name}, intermediate hourly file exists.")
        return out_filename

    writing_filename = out_filename + ".writing"
    print(f"  -> Extracting chunk {chunk_name} ({len(forcing_files)} files)...")
    
    def subset_spatial(ds_single):
        return ds_single.sel(lat=lat_slice, lon=lon_slice)
    
    ds = xr.open_mfdataset(
        forcing_files, 
        combine='by_coords', 
        preprocess=subset_spatial,
        join='override',
        parallel=False,  
        engine='netcdf4'
    )
    
    ds_nova = ds.load()
    
    temp = ds_nova['Tair'] - 273.15
    humidity = ds_nova['Qair']
    pressure = ds_nova['PSurf']
    
    W = humidity / (1.0 - humidity)
    enthalpy = 1.006 * temp + W * (2501.0 + 1.86 * temp)
    
    # Save the HOURLY data (No time shifting or resampling yet!)
    out_ds = xr.Dataset({
        'Tair_C': temp,
        'Qair': humidity,
        'PSurf': pressure,
        'enthalpy': enthalpy
    })

    out_ds.to_netcdf(writing_filename)
    os.rename(writing_filename, out_filename)

    ds.close()
    out_ds.close()
    return out_filename


def process_state_full(base_path, output_dir, lat_slice, lon_slice, prefix, tz_name, utc_offset):
    os.makedirs(output_dir, exist_ok=True)
    # Changed output name for the test run
    final_out = os.path.join(output_dir, f"{prefix}_Daily_DayNight_Summary_6MONTH_TEST.nc")

    if os.path.exists(final_out):
        print(f"Final file {final_out} already exists! Skipping {prefix.upper()}.")
        return

    # SLICED TO JUST THE FIRST 6 CHUNKS FOR THE SAMPLE RUN
    chunk_dirs = sorted(glob.glob(os.path.join(base_path, '2*')))[:6]
    hourly_files = []

    print(f"\n--- PHASE 1: Generating Continuous Hourly Time Series for {prefix.upper()} ({tz_name}) ---")
    for c_dir in chunk_dirs:
        chunk_name = os.path.basename(c_dir)
        forcing_files = sorted(glob.glob(os.path.join(c_dir, '*.nc')))
        
        # Clean up any partial `.writing` files left over from a killed job
        if os.path.exists(os.path.join(output_dir, f"{prefix}_{chunk_name}_hourly_derived.nc.writing")):
            os.remove(os.path.join(output_dir, f"{prefix}_{chunk_name}_hourly_derived.nc.writing"))
            
        if len(forcing_files) > 0:
            temp_file = process_hourly_chunk(
                forcing_files, output_dir, lat_slice, lon_slice, prefix, chunk_name
            )
            hourly_files.append(temp_file)

    print(f"\n--- PHASE 2: Time Shifting & Resampling on Full Continuous Dataset ---")
    
    ds_full = xr.open_mfdataset(
        hourly_files, 
        combine='nested',       
        concat_dim='time',      
        join='override',        
        parallel=False
    )
    
    print("Loading full hourly dataset into memory...")
    ds_full = ds_full.load()
    
    # --- 1. TIMEZONE SHIFT ---
    print("Applying timezone shift across continuous boundaries...")
    total_shift = pd.Timedelta(hours=utc_offset + 6)
    ds_full = ds_full.assign_coords(time=ds_full.time + total_shift)
    
    # --- 2. SEPARATE DAY AND NIGHT ---
    print("Masking Day/Night...")
    is_day = ds_full.time.dt.hour >= 12
    ds_day = ds_full.where(is_day)
    ds_night = ds_full.where(~is_day)
    
    # --- 3. SUMMARIZE TO DAILY ---
    print("Resampling to Daily...")
    day_mean = ds_day.resample(time='1D').mean()
    day_min  = ds_day.resample(time='1D').min()
    day_max  = ds_day.resample(time='1D').max()
    
    night_mean = ds_night.resample(time='1D').mean()
    night_min  = ds_night.resample(time='1D').min()
    night_max  = ds_night.resample(time='1D').max()

    # --- 4. ASSEMBLE FINAL DATASET ---
    out_ds = xr.Dataset(
        data_vars={
            'DayTime_Avg_Tair': day_mean['Tair_C'],
            'DayTime_Tair_min': day_min['Tair_C'],
            'DayTime_Tair_max': day_max['Tair_C'],
            'DayTime_Avg_Qair': day_mean['Qair'],
            'DayTime_Avg_PSurf': day_mean['PSurf'],
            'DayTime_Avg_enthalpy': day_mean['enthalpy'],

            'NightTime_Avg_Tair': night_mean['Tair_C'],
            'NightTime_Tair_min': night_min['Tair_C'],
            'NightTime_Tair_max': night_max['Tair_C'],
            'NightTime_Avg_Qair': night_mean['Qair'],
            'NightTime_Avg_PSurf': night_mean['PSurf'],
            'NightTime_Avg_enthalpy': night_mean['enthalpy'],
        }
    )

    out_ds['DayTime_Avg_Tair'].attrs = {'units': 'Celsius'}
    out_ds['NightTime_Avg_Tair'].attrs = {'units': 'Celsius'}

    # We drop any genuinely incomplete days
    out_ds = out_ds.dropna(dim='time', subset=['DayTime_Avg_Tair', 'NightTime_Avg_Tair'], how='any')

    print(f"Saving final dataset to {final_out}...")
    writing_filename = final_out + ".writing"
    out_ds.to_netcdf(writing_filename)
    os.rename(writing_filename, final_out)
    
    # --- 5. PRINT SAMPLE OUTPUT FOR VALIDATION ---
    print("\n=======================================================")
    print("--- VALIDATION: CHECKING THE 1ST OF EVERY MONTH ---")
    
    # Extract just the first latitude/longitude point to a pandas Series for easy printing
    sample_lat = out_ds.lat.values[0]
    sample_lon = out_ds.lon.values[0]
    sample_ts = out_ds['DayTime_Avg_Tair'].sel(lat=sample_lat, lon=sample_lon).to_series()
    
    # Loop over the unique months in our 6-month dataset
    for month_val in sample_ts.index.month.unique():
        # Get just the data for this specific month
        month_data = sample_ts[sample_ts.index.month == month_val]
        
        # Print the first 3 days of the month
        print(f"\nValues for Month {month_val}:")
        print(month_data.head(3))
        
    print("=======================================================\n")

    ds_full.close()
    out_ds.close()
    print(f"Finished {prefix.upper()}!")


if __name__ == "__main__":
    base_forcing_path = '/discover/nobackup/projects/eis_nldas3/DATA/forcing/hourly'

    # VIRGINIA
    process_state_full(
        base_path=base_forcing_path,
        output_dir='/discover/nobackup/cmbreen/datacenters/virginia_hourly',
        lat_slice=slice(38.5, 39.5),
        lon_slice=slice(-78, -77),
        prefix='va',
        tz_name='Eastern Standard Time',
        utc_offset=-5
    )