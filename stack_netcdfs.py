'''
After we have pulled the bounding box for Tair, Psurf, Q & enthalpy for all of NLDAS3 (see /discover/nobackup/cmbreen/subset_netcdf.py)
and also pulled the 90, 95, 99 thresholds for the full year (/discover/nobackup/cmbreen/datacenters/datacenter/calc_percentiles.py)
and also pulled the 90, 95, 99 thresholds for each season year (/discover/nobackup/cmbreen/datacenters/datacenter/calc_percentiles.py)

Stack the netcdf (so it's not 8400 files)
add whether it crossed the annual 90, 95, 99 Annual threshold 
add whether it crossed it's respective seasonal 90, 95, 99 threshold 

## this needs to run after 
(datacenter) cmbreen@discover31:/discover/nobackup/cmbreen/datacenters> cat datacenter_perc.o57167567
finishes running 

## this is now running here: 
cmbreen@discover32:/discover/nobackup/cmbreen/datacenters> sbatch sbatch_percentiles
Submitted batch job 57253580

'''
import dask.array as da
import xarray as xr
import glob
import xarray as xr
import matplotlib.pyplot as plt
import tqdm
import os
import numpy as np

# virginia = '/discover/nobackup/cmbreen/datacenters/virginia/*.nc' ## 8400 files 
# texas = '/discover/nobackup/cmbreen/datacenters/texas/*.nc' ## 8400 
# virginia_enthalpy_thresholds = '/discover/nobackup/cmbreen/datacenters/virginia_enthalpy_quantiles.nc'
# texas_enthalpy_thresholds = '/discover/nobackup/cmbreen/datacenters/texas_enthalpy_quantiles.nc'

# # ## stack the virginia netcdfs along time dimension so there are 7 bands: 
# # tair
# # psurf 
# # q 
# # annual enthalpy quantile thresholds [0.01, 0.05, 0.1, 0.90, 0.95, 0.99] (6 values)
# # did it cross annual enthalpy threshold 1(yes) 0 (no) (6 long for each threshold)
# # seasonal enthalpy threshold [0.01, 0.05, 0.1, 0.90, 0.95, 0.99] (6 values) --> use month from time dimension to determine which is the season 
# # season band --> use month from time dimension to determine which is the season; store season for easy slicing 
# # did it cross seasonal enthalpy threshold (use month to determine which threshold to use); 1(yes) 0 (no) (6 long for each threshold)

# ## save it as this file
# virignia_enthalpy_stacked = '/discover/nobackup/cmbreen/datacenters/virginia_enthalpy_stacked.nc'

# ### then do the same for texas 

# ## save it as this file
# texas_enthalpy_stacked = '/discover/nobackup/cmbreen/datacenters/texas_enthalpy_stacked.nc'

# def process_region(raw_files_glob, thresh_file, out_file, region_name):
#     print(f"[{region_name}] Loading raw files and thresholds...")
    
#     # 1. Load raw data (chunked by time so we don't run out of memory)
#     files = sorted(glob.glob(raw_files_glob))
#     ds = xr.open_mfdataset(files, combine='by_coords', parallel=True, engine='h5netcdf', chunks={'time': 100})
    
#     # 2. Load thresholds
#     ds_thresh = xr.open_dataset(thresh_file)
    
#     # 3. Add season band (as a string/categorical)
#     print(f"[{region_name}] Mapping seasons...")
#     # xarray 'time.season' outputs 'DJF', 'MAM', 'JJA', 'SON'
#     ds['season'] = ds['time.season']
#     # shape = (len(ds_thresh.quantile), len(ds.time), len(ds.lat), len(ds.lon))
#     print(f"[{region_name}] Building seasonal thresholds...")
    
#     # DEFINING SHAPE HERE using bracket notation to avoid method conflicts
#     shape = (len(ds_thresh['quantile']), len(ds['time']), len(ds['lat']), len(ds['lon']))
    
#     # Use dask to create an empty array of the right shape and chunks
#     empty_data = da.full(
#         shape, 
#         np.nan, 
#         chunks=(len(ds_thresh['quantile']), 100, len(ds['lat']), len(ds['lon']))
#     )
    
#     seasonal_thresholds = xr.DataArray(
#         empty_data, 
#         coords={
#             'quantile': ds_thresh['quantile'], 
#             'time': ds['time'], 
#             'lat': ds['lat'], 
#             'lon': ds['lon']
#         }, 
#         dims=['quantile', 'time', 'lat', 'lon']
#     )
    
#     season_map = {
#         'DJF': 'enthalpy_winter',
#         'MAM': 'enthalpy_spring',
#         'JJA': 'enthalpy_summer',
#         'SON': 'enthalpy_fall'
#     }
    
#     for season_str, var_name in season_map.items():
#         # Find where time matches this season, and fill with the corresponding threshold
#         is_season = (ds['season'] == season_str)
#         seasonal_thresholds = xr.where(is_season, ds_thresh[var_name], seasonal_thresholds)
    
#     ds['seasonal_enthalpy_thresholds'] = seasonal_thresholds
    
#     # 5. Calculate Annual Crossings
#     print(f"[{region_name}] Calculating threshold crossings...")
#     # Cold extremes (1st, 5th, 10th) - True if Enthalpy < Threshold
#     cold_quants = [0.01, 0.05, 0.10]
#     ds['crossed_annual_cold'] = ds['enthalpy'] < ds_thresh['enthalpy_annual'].sel(quantile=cold_quants)
    
#     # Hot extremes (90th, 95th, 99th) - True if Enthalpy > Threshold
#     hot_quants = [0.90, 0.95, 0.99]
#     ds['crossed_annual_hot'] = ds['enthalpy'] > ds_thresh['enthalpy_annual'].sel(quantile=hot_quants)
    
#     # 6. Calculate Seasonal Crossings
#     ds['crossed_seasonal_cold'] = ds['enthalpy'] < ds['seasonal_enthalpy_thresholds'].sel(quantile=cold_quants)
#     ds['crossed_seasonal_hot'] = ds['enthalpy'] > ds['seasonal_enthalpy_thresholds'].sel(quantile=hot_quants)
    
#     # 7. Convert boolean crossings to 1 (yes) and 0 (no) as requested
#     ds['crossed_annual_cold'] = ds['crossed_annual_cold'].astype(int)
#     ds['crossed_annual_hot'] = ds['crossed_annual_hot'].astype(int)
#     ds['crossed_seasonal_cold'] = ds['crossed_seasonal_cold'].astype(int)
#     ds['crossed_seasonal_hot'] = ds['crossed_seasonal_hot'].astype(int)
    
#     # 8. Save the stacked dataset
#     print(f"[{region_name}] Saving to {out_file}...")
#     # Rechunking to standard sizes before saving helps file I/O speed
#     ds.to_netcdf(out_file, compute=True)
#     print(f"[{region_name}] Done!\n")

# def main():
#     # VIRGINIA
#     process_region(
#         raw_files_glob='/discover/nobackup/cmbreen/datacenters/virginia/*.nc',
#         thresh_file='/discover/nobackup/cmbreen/datacenters/virginia_enthalpy_quantiles.nc',
#         out_file='/discover/nobackup/cmbreen/datacenters/virginia_enthalpy_stacked.nc',
#         region_name='Virginia'
#     )
    
#     # TEXAS
#     process_region(
#         raw_files_glob='/discover/nobackup/cmbreen/datacenters/texas/*.nc',
#         thresh_file='/discover/nobackup/cmbreen/datacenters/texas_enthalpy_quantiles.nc',
#         out_file='/discover/nobackup/cmbreen/datacenters/texas_enthalpy_stacked.nc',
#         region_name='Texas'
#     )

# if __name__ == "__main__":
#     main()

import dask.array as da
import xarray as xr
import glob
import os
import numpy as np

def process_region(raw_files_glob, thresh_file, out_dir, region_name):
    print(f"[{region_name}] Loading raw files and thresholds...")
    
    files = sorted(glob.glob(raw_files_glob))[:100]
    
    # Fix for the FutureWarning: explicitly set data_vars or use default
    ds = xr.open_mfdataset(
        files, 
        combine='by_coords', 
        parallel=True, 
        engine='h5netcdf', 
        chunks={'time': 100},
        data_vars='minimal' # Prevents merging non-dimension variables unnecessarily
    )
    
    ds_thresh = xr.open_dataset(thresh_file)
    
    # 3. Add season string
    ds['season'] = ds['time.season']
    
    print(f"[{region_name}] Mapping seasons...")
    # Combine the 4 seasonal variables into a single DataArray with a 'season' dimension
    # This completely eliminates the need for xr.where() and empty dask arrays!
    seasonal_da = xr.concat(
        [ds_thresh['enthalpy_winter'], ds_thresh['enthalpy_spring'], 
         ds_thresh['enthalpy_summer'], ds_thresh['enthalpy_fall']],
        dim=xr.DataArray(['DJF', 'MAM', 'JJA', 'SON'], dims='season_name', name='season_name')
    )
    
    # Xarray can now automatically align the data using groupby
    # This is highly optimized in Dask compared to xr.where loops
    ds['seasonal_enthalpy_thresholds'] = seasonal_da.sel(season_name=ds['season']).drop_vars('season_name')

    print(f"[{region_name}] Calculating threshold crossings...")
    cold_quants = [0.01, 0.05, 0.10]
    hot_quants = [0.90, 0.95, 0.99]
    
    # Annual
    ds['crossed_annual_cold'] = ds['enthalpy'] < ds_thresh['enthalpy_annual'].sel(quantile=cold_quants)
    ds['crossed_annual_hot'] = ds['enthalpy'] > ds_thresh['enthalpy_annual'].sel(quantile=hot_quants)
    
    # Seasonal
    ds['crossed_seasonal_cold'] = ds['enthalpy'] < ds['seasonal_enthalpy_thresholds'].sel(quantile=cold_quants)
    ds['crossed_seasonal_hot'] = ds['enthalpy'] > ds['seasonal_enthalpy_thresholds'].sel(quantile=hot_quants)
    
    # NOTE: .astype(int) can sometimes throw warnings if there are NaNs. 
    # If enthalpy has NaNs (like over oceans), these booleans might evaluate weirdly. 
    # using .fillna(0).astype('int8') is often safer and uses less memory.
    for var in ['crossed_annual_cold', 'crossed_annual_hot', 'crossed_seasonal_cold', 'crossed_seasonal_hot']:
        ds[var] = ds[var].astype('int8')

    print(f"[{region_name}] Saving to Zarr format (Highly recommended for parallel writes)...")
    
    # Save as Zarr directory instead of NetCDF
    # E.g., out_dir = '/discover/nobackup/cmbreen/datacenters/virginia_enthalpy_stacked.zarr'
    ds.to_zarr(out_dir, mode='w', consolidated=True)
    
    print(f"[{region_name}] Done!\n")

def main():
    process_region(
        raw_files_glob='/discover/nobackup/cmbreen/datacenters/virginia/*.nc',
        thresh_file='/discover/nobackup/cmbreen/datacenters/virginia_enthalpy_quantiles.nc',
        out_dir='/discover/nobackup/cmbreen/datacenters/virginia_enthalpy_stacked.zarr',
        region_name='Virginia'
    )
    
    # Same for Texas... (change out_dir to .zarr)
        # TEXAS
    process_region(
        raw_files_glob='/discover/nobackup/cmbreen/datacenters/texas/*.nc',
        thresh_file='/discover/nobackup/cmbreen/datacenters/texas_enthalpy_quantiles.nc',
        out_file='/discover/nobackup/cmbreen/datacenters/texas_enthalpy_stacked.zarr',
        region_name='Texas'
    )


if __name__ == "__main__":
    main()