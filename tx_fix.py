
# ==============================================================================
# SCRIPT PURPOSE & BACKGROUND:
# This script repairs time coordinate corruption caused by the initial processing 
# script. During the original run, shifting the timezone from UTC to Local Time 
# using Pandas converted the standard NetCDF time into nanoseconds and created 
# overlapping month boundaries. When xarray concatenated these overlapping files, 
# it implicitly injected an illegal `_FillValue` into the time coordinate, making 
# the final NetCDF file unreadable in standard climate tools (like Panoply). 
# This script bypasses the corrupted time decoding, manually reconstructs the 
# time arrays, and applies a strict encoding to strip the `_FillValue` and 
# restore CF-compliant time units before saving the final file.
# ==============================================================================

import xarray as xr
import pandas as pd
import glob

print("Finding Texas monthly files...")
hourly_files = sorted(glob.glob('/discover/nobackup/cmbreen/datacenters/texas_pure_hourly/tx_2*_hourly_temp.nc'))
print(f"Found {len(hourly_files)} monthly files to stitch.")

datasets = []
for f in hourly_files:
    ds_month = xr.open_dataset(f, decode_times=False)
    
    # 1. Pandas datetime fix
    units = ds_month.time.attrs['units']
    base_time_str = units.split('since ')[1]
    base_time = pd.to_datetime(base_time_str)
    
    real_times = base_time + pd.to_timedelta(ds_month.time.values, unit='h')
    ds_month['time'] = real_times
    
    ds_month.time.attrs.clear()
    datasets.append(ds_month)

print("Concatenating files... (Applying join='override' to prevent grid expansion)")
ds_final = xr.concat(datasets, dim='time', join='override')

print("Sorting and deduplicating...")
ds_final = ds_final.sortby('time')
ds_final = ds_final.drop_duplicates(dim='time')

# 2. THE MAGIC FIX: Explicitly format the NetCDF time output
ds_final.time.encoding = {
    'units': 'hours since 2000-12-31 19:00:00',
    'calendar': 'standard',
    '_FillValue': None
}

final_out = '/discover/nobackup/cmbreen/datacenters/texas_pure_hourly/tx_Pure_Hourly_Summary_FIXED.nc'
print(f"Saving fixed summary to {final_out}...")
ds_final.to_netcdf(final_out)
print("Done! Your Texas dataset is finally stitched together properly.")