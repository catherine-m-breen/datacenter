import xarray as xr
import pandas as pd
import glob

print("Finding Virginia monthly files...")
hourly_files = sorted(glob.glob('/discover/nobackup/cmbreen/datacenters/virginia_pure_hourly/va_2*_hourly_temp.nc'))
print(f"Found {len(hourly_files)} monthly files to stitch.")

datasets = []
for f in hourly_files:
    # 1. Open without decoding
    ds_month = xr.open_dataset(f, decode_times=False)
    
    # 2. MANUALLY BUILD THE DATES WITH PANDAS
    # Grab the string (e.g., 'hours since 2000-12-31T19:00:00')
    units = ds_month.time.attrs['units']
    
    # Extract just the date part ('2000-12-31T19:00:00')
    base_time_str = units.split('since ')[1]
    base_time = pd.to_datetime(base_time_str)
    
    # Add the hours (0, 1, 2...) to the base date to get actual timestamps
    real_times = base_time + pd.to_timedelta(ds_month.time.values, unit='h')
    
    # Overwrite the time coordinate with the real datetimes!
    ds_month['time'] = real_times
    
    # Clear the old attributes so Xarray doesn't get confused
    ds_month.time.attrs.clear()
    
    datasets.append(ds_month)

print("Concatenating files... (Applying join='override' to prevent grid expansion)")
# REMOVED compat='override' - just join='override' is all you need!
ds_final = xr.concat(datasets, dim='time', join='override')

print("Sorting and deduplicating...")
ds_final = ds_final.sortby('time')
ds_final = ds_final.drop_duplicates(dim='time')

# 3. VERIFICATION STEP 
print("\n--- SANITY CHECK BEFORE SAVING ---")
print(f"Total hours in dataset: {ds_final.time.size}")
print(f"First 5 dates: {ds_final.time.values[:5]}")
print("----------------------------------\n")

# Clear the encoding to ensure a clean save
ds_final.time.encoding.clear()

final_out = '/discover/nobackup/cmbreen/datacenters/virginia_pure_hourly/va_Pure_Hourly_Summary_FIXED.nc'
print(f"Saving fixed summary to {final_out}...")
ds_final.to_netcdf(final_out)
print("Done! Your Virginia dataset is finally stitched together properly.")