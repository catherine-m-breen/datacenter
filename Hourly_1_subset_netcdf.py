import xarray as xr
import pandas as pd
import os
import glob

def process_state_forcing_yearly(forcing_files, output_dir, lat_slice, lon_slice, prefix, tz_name, utc_offset, year):
    print(f"  -> Processing {year} ({len(forcing_files)} files)...")
    
    def subset_spatial(ds_single):
        return ds_single.sel(lat=lat_slice, lon=lon_slice)
    
    # 1. Open ONLY this year's files
    # CRITICAL: parallel=False prevents HDF5 Segmentation Faults
    ds = xr.open_mfdataset(
        forcing_files, 
        combine='by_coords', 
        preprocess=subset_spatial,
        join='override',
       # compat='override',
        parallel=False,  
        engine='netcdf4'
    )
    
    # 2. Subset spatially and load into memory
    ds_nova = ds.load()
    
    # Calculate derived variables
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

    # --- 1. TIMEZONE ADJUSTMENT ---
    ds_derived['time'] = ds_derived['time'] + pd.Timedelta(hours=utc_offset)
    
    # --- 2. ALIGN CONTINUOUS NIGHTTIME CROSSING MIDNIGHT ---
    ds_derived['time'] = ds_derived['time'] + pd.Timedelta(hours=6)
    
    # --- 3. SEPARATE DAY AND NIGHT ---
    is_day = ds_derived.time.dt.hour >= 12
    ds_day = ds_derived.where(is_day)
    ds_night = ds_derived.where(~is_day)
    
    # --- 4. SUMMARIZE TO DAILY ---
    day_mean = ds_day.resample(time='1D').mean()
    day_min  = ds_day.resample(time='1D').min()
    day_max  = ds_day.resample(time='1D').max()
    
    night_mean = ds_night.resample(time='1D').mean()
    night_min  = ds_night.resample(time='1D').min()
    night_max  = ds_night.resample(time='1D').max()

    # Create output dataset
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

    # --- ADD METADATA ---
    out_ds['DayTime_Avg_Tair'].attrs = {'units': 'Celsius'}
    out_ds['NightTime_Avg_Tair'].attrs = {'units': 'Celsius'}

    # Save intermediate yearly file
    out_filename = os.path.join(output_dir, f"{prefix}_{year}_temp.nc")
    out_ds.to_netcdf(out_filename)

    ds.close()
    out_ds.close()
    return out_filename


def process_state_full(base_path, output_dir, lat_slice, lon_slice, prefix, tz_name, utc_offset):
    os.makedirs(output_dir, exist_ok=True)
    print(f"\n--- Starting processing for {prefix.upper()} ({tz_name}) ---")
    
    # Find all year directories (e.g., /.../hourly/2000, 2001, etc.)
    year_dirs = sorted(glob.glob(os.path.join(base_path, '2*')))
    
    yearly_files = []
    
    for y_dir in year_dirs:
        year = os.path.basename(y_dir)
        # Find all files for this specific year
        forcing_files = sorted(glob.glob(os.path.join(y_dir, '*.nc')))
        
        if len(forcing_files) > 0:
            temp_file = process_state_forcing_yearly(
                forcing_files, output_dir, lat_slice, lon_slice, 
                prefix, tz_name, utc_offset, year
            )
            yearly_files.append(temp_file)
            
    print(f"Stitching {len(yearly_files)} yearly files into final master file...")
    # Open the ~20 intermediate files (perfectly safe and fast!)
    ds_final = xr.open_mfdataset(yearly_files, combine='by_coords', parallel=False)
    
    final_out = os.path.join(output_dir, f"{prefix}_Daily_DayNight_Summary.nc")
    ds_final.to_netcdf(final_out)
    ds_final.close()
    
    # Clean up the intermediate yearly files
    print("Cleaning up temporary yearly files...")
    for f in yearly_files:
        os.remove(f)
        
    print(f"Finished {prefix.upper()}! Saved to {final_out}")


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
    
    # TEXAS
    process_state_full(
        base_path=base_forcing_path,
        output_dir='/discover/nobackup/cmbreen/datacenters/texas_hourly',
        lat_slice=slice(32.3, 33.3),
        lon_slice=slice(-97.5, -96.5),
        prefix='tx',
        tz_name='Central Standard Time',
        utc_offset=-6
    )