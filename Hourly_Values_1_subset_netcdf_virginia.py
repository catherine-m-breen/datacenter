import xarray as xr
import pandas as pd
import os
import glob
import numpy as np

def process_state_forcing_hourly(forcing_files, output_dir, lat_slice, lon_slice, prefix, tz_name, utc_offset, yyyymm):
    print(f"  -> Processing {yyyymm} ({len(forcing_files)} files)...")
    
    def subset_spatial(ds_single):
        return ds_single.sel(lat=lat_slice, lon=lon_slice)
    
    # 1. Open this month's files
    ds = xr.open_mfdataset(
        forcing_files, 
        combine='by_coords', 
        preprocess=subset_spatial,
        join='override',
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
    
    # Create output dataset keeping the native hourly frequency
    out_ds = xr.Dataset({
        'Tair_C': temp,
        'Qair': humidity,
        'PSurf': pressure,
        'enthalpy': enthalpy
    })

    # --- TIMEZONE ADJUSTMENT ---
    # Convert from UTC to Local Time so extreme heat hours match local afternoon
    out_ds['time'] = out_ds['time'] + pd.Timedelta(hours=utc_offset)
    
    # --- ADD METADATA ---
    out_ds['Tair_C'].attrs = {'units': 'Celsius'}
    out_ds['Qair'].attrs = {'units': 'kg/kg'}
    out_ds['PSurf'].attrs = {'units': 'Pa'}
    out_ds['enthalpy'].attrs = {'units': 'kJ/kg'}

    # Save intermediate file
    out_filename = os.path.join(output_dir, f"{prefix}_{yyyymm}_hourly_temp.nc")
    out_ds.to_netcdf(out_filename)

    ds.close()
    out_ds.close()
    return out_filename


def process_state_full(base_path, output_dir, lat_slice, lon_slice, prefix, tz_name, utc_offset):
    os.makedirs(output_dir, exist_ok=True)
    print(f"\n--- Starting HOURLY processing for {prefix.upper()} ({tz_name}) ---")
    
    # Find all year/month directories (e.g., /.../hourly/200001, 200002, etc.)
    ym_dirs = sorted(glob.glob(os.path.join(base_path, '2*')))
    
    hourly_files = []
    
    for ym_dir in ym_dirs:
        yyyymm = os.path.basename(ym_dir)
        out_filename = os.path.join(output_dir, f"{prefix}_{yyyymm}_hourly_temp.nc")
        
        # --- RESUME LOGIC ---
        if os.path.exists(out_filename):
            print(f"  -> Skipping {yyyymm}, already processed.")
            hourly_files.append(out_filename)
            continue
            
        # Find all files for this specific month
        forcing_files = sorted(glob.glob(os.path.join(ym_dir, '*.nc')))
        
        if len(forcing_files) > 0:
            temp_file = process_state_forcing_hourly(
                forcing_files, output_dir, lat_slice, lon_slice, 
                prefix, tz_name, utc_offset, yyyymm
            )
            hourly_files.append(temp_file)
            
    print(f"Stitching {len(hourly_files)} files into final master hourly file...")
    
    # Open the intermediate files
    ds_final = xr.open_mfdataset(hourly_files, combine='nested', concat_dim='time', join='override', parallel=False)
    
    # Sort and drop duplicates caused by timezone shifts at month boundaries
    ds_final = ds_final.sortby('time')
    ds_final = ds_final.drop_duplicates(dim='time')
    
    final_out = os.path.join(output_dir, f"{prefix}_Pure_Hourly_Summary.nc")
    ds_final.to_netcdf(final_out)
    ds_final.close()
    
    # Clean up the intermediate yearly files
    print("Cleaning up temporary monthly files...")
    for f in hourly_files:
        os.remove(f)
        
    print(f"Finished {prefix.upper()}! Saved to {final_out}")


if __name__ == "__main__":
    base_forcing_path = '/discover/nobackup/projects/eis_nldas3/DATA/forcing/hourly'
    
    # VIRGINIA
    process_state_full(
        base_path=base_forcing_path,
        output_dir='/discover/nobackup/cmbreen/datacenters/virginia_pure_hourly',
        lat_slice=slice(38.5, 39.5),
        lon_slice=slice(-78, -77),
        prefix='va',
        tz_name='Eastern Standard Time',
        utc_offset=-5
    )
    
