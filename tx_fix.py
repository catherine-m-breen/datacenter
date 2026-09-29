import xarray as xr
import glob

print("Finding Texas monthly files...")
hourly_files = sorted(glob.glob('/discover/nobackup/cmbreen/datacenters/texas_pure_hourly/tx_2*_hourly_temp.nc'))
print(f"Found {len(hourly_files)} monthly files to stitch.")

datasets = []
for f in hourly_files:
    # 1. Open the file WITHOUT decoding the time to bypass the error
    ds_month = xr.open_dataset(f, decode_times=False)
    
    # 2. Fix the broken 'T' in the units string
    ds_month.time.attrs['units'] = ds_month.time.attrs['units'].replace('T', ' ')
    
    # 3. NOW tell Xarray to decode it. This turns [0, 1, 2...] into real datetimes!
    ds_month = xr.decode_cf(ds_month)
    
    datasets.append(ds_month)

print("Concatenating files... (Because they are real datetimes now, they won't overlap!)")
ds_final = xr.concat(datasets, dim='time')
ds_final = ds_final.sortby('time')
ds_final = ds_final.drop_duplicates(dim='time')

# 4. Clear the old corrupted metadata so it writes a clean, standard NetCDF time format
ds_final.time.encoding.clear()

final_out = '/discover/nobackup/cmbreen/datacenters/texas_pure_hourly/tx_Pure_Hourly_Summary_FIXED.nc'
print(f"Saving fixed summary to {final_out}...")
ds_final.to_netcdf(final_out)
print("Done! Your Texas dataset is finally stitched together properly.")