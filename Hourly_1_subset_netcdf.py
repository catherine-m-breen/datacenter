import xarray as xr
import pandas as pd
import os
import glob

def process_state_forcing(forcing_files, output_dir, lat_slice, lon_slice, prefix, tz_name, utc_offset):
    os.makedirs(output_dir, exist_ok=True)
    print(f"\nStitching together files for {prefix} ({tz_name})...")
    
    # NEW: Create a preprocess function to subset EACH file before stitching them together.
    # This massively reduces memory usage and Dask graph complexity.
    def subset_spatial(ds_single):
        return ds_single.sel(lat=lat_slice, lon=lon_slice)
    
    # 1. Open all daily files at once, preprocessing them on the fly
    ds = xr.open_mfdataset(
        forcing_files, 
        combine='by_coords', 
        preprocess=subset_spatial, # Subsets each file individually
        join='override',           # Ignores slight lat/lon floating point mismatches
        compat='override',         # Forces variable compatibility across all files
        parallel=True              # Can speed up file reading if dask is available
    )
    
    # 2. Load the pre-subsetted continuous timeline into memory
    print(f"Loading spatial subset into memory for {prefix}...")
    ds_nova = ds.load() 
    # ds_nova = ds_nova.load()
    
    print(f"Calculating Day/Night averages for {prefix}...")
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
    # Shift from UTC to strictly Standard Time (EST = -5, CST = -6)
    ds_derived['time'] = ds_derived['time'] + pd.Timedelta(hours=utc_offset)
    
    # --- 2. ALIGN CONTINUOUS NIGHTTIME CROSSING MIDNIGHT ---
    # Shift timeline +6 hours so 6PM-6AM maps perfectly to hours 0-11 of the target date,
    # and 6AM-6PM maps perfectly to hours 12-23 of the target date.
    ds_derived['time'] = ds_derived['time'] + pd.Timedelta(hours=6)
    
    # --- 3. SEPARATE DAY AND NIGHT ---
    # Based on our shifted timeline, the Day starts at hour 12
    is_day = ds_derived.time.dt.hour >= 12
    ds_day = ds_derived.where(is_day)
    ds_night = ds_derived.where(~is_day)
    
    # --- 4. SUMMARIZE TO DAILY ---
    # Resample now flawlessly captures the rolling night under the current calendar day
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
    out_ds['DayTime_Avg_Tair'].attrs = {'units': 'Celsius', 'long_name': 'Daytime Average 2-m Air Temp'}
    out_ds['DayTime_Tair_min'].attrs = {'units': 'Celsius', 'long_name': 'Daytime Minimum 2-m Air Temp'}
    out_ds['DayTime_Tair_max'].attrs = {'units': 'Celsius', 'long_name': 'Daytime Maximum 2-m Air Temp'}
    out_ds['DayTime_Avg_enthalpy'].attrs = {'units': 'kJ/kg', 'long_name': 'Daytime Average Enthalpy'}
    
    out_ds['NightTime_Avg_Tair'].attrs = {'units': 'Celsius', 'long_name': 'Nighttime Average 2-m Air Temp'}
    out_ds['NightTime_Tair_min'].attrs = {'units': 'Celsius', 'long_name': 'Nighttime Minimum 2-m Air Temp'}
    out_ds['NightTime_Tair_max'].attrs = {'units': 'Celsius', 'long_name': 'Nighttime Maximum 2-m Air Temp'}
    out_ds['NightTime_Avg_enthalpy'].attrs = {'units': 'kJ/kg', 'long_name': 'Nighttime Average Enthalpy'}

    out_ds.attrs = ds.attrs
    out_ds.attrs['timezone_used'] = f'{tz_name} (UTC{utc_offset})'
    out_ds.attrs['processing_note'] = f'Subsetted; Day=6AM-6PM, Night=6PM-6AM; Resampled to local {tz_name} daily summary.'

    # Save ONE combined file per state
    out_filename = os.path.join(output_dir, f"{prefix}_Daily_DayNight_Summary.nc")
    print(f"Saving to {out_filename}...")
    out_ds.to_netcdf(out_filename)

    ds.close()
    out_ds.close()
    print("Done!")

if __name__ == "__main__":
    forcing_files = sorted(glob.glob('/discover/nobackup/projects/eis_nldas3/DATA/forcing/hourly/2*/*.nc'))
    
    print(f"Total files found: {len(forcing_files)}")
    
    # VIRGINIA
    process_state_forcing(
        forcing_files=forcing_files,
        output_dir='/discover/nobackup/cmbreen/datacenters/virginia_hourly',
        lat_slice=slice(38.5, 39.5),
        lon_slice=slice(-78, -77),
        prefix='va',
        tz_name='Eastern Standard Time',
        utc_offset=-5
    )
    
    # TEXAS
    process_state_forcing(
        forcing_files=forcing_files,
        output_dir='/discover/nobackup/cmbreen/datacenters/texas_hourly',
        lat_slice=slice(32.3, 33.3),
        lon_slice=slice(-97.5, -96.5),
        prefix='tx',
        tz_name='Central Standard Time',
        utc_offset=-6
    )