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

'''
import xarray as xr
import glob
import xarray as xr
import matplotlib.pyplot as plt
import tqdm
import os


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

def process_region(raw_files_glob, thresh_file, out_file, region_name):
    print(f"[{region_name}] Loading raw files and thresholds...")
    
    # 1. Load raw data (chunked by time so we don't run out of memory)
    files = sorted(glob.glob(raw_files_glob))
    ds = xr.open_mfdataset(files, combine='by_coords', parallel=True, engine='h5netcdf', chunks={'time': 100})
    
    # 2. Load thresholds
    ds_thresh = xr.open_dataset(thresh_file)
    
    # 3. Add season band (as a string/categorical)
    print(f"[{region_name}] Mapping seasons...")
    # xarray 'time.season' outputs 'DJF', 'MAM', 'JJA', 'SON'
    ds['season'] = ds['time.season']
    
    # 4. Build a continuous time-series of the correct seasonal thresholds
    # We create an empty array shaped like our data, then fill it season by season
    seasonal_thresholds = xr.DataArray(
        np.nan, 
        coords=[ds_thresh.quantile, ds.time, ds.lat, ds.lon], 
        dims=['quantile', 'time', 'lat', 'lon']
    ).chunk({'time': 100})
    
    season_map = {
        'DJF': 'enthalpy_winter',
        'MAM': 'enthalpy_spring',
        'JJA': 'enthalpy_summer',
        'SON': 'enthalpy_fall'
    }
    
    for season_str, var_name in season_map.items():
        # Find where time matches this season, and fill with the corresponding threshold
        is_season = (ds['season'] == season_str)
        seasonal_thresholds = xr.where(is_season, ds_thresh[var_name], seasonal_thresholds)
    
    ds['seasonal_enthalpy_thresholds'] = seasonal_thresholds
    
    # 5. Calculate Annual Crossings
    print(f"[{region_name}] Calculating threshold crossings...")
    # Cold extremes (1st, 5th, 10th) - True if Enthalpy < Threshold
    cold_quants = [0.01, 0.05, 0.10]
    ds['crossed_annual_cold'] = ds['enthalpy'] < ds_thresh['enthalpy_annual'].sel(quantile=cold_quants)
    
    # Hot extremes (90th, 95th, 99th) - True if Enthalpy > Threshold
    hot_quants = [0.90, 0.95, 0.99]
    ds['crossed_annual_hot'] = ds['enthalpy'] > ds_thresh['enthalpy_annual'].sel(quantile=hot_quants)
    
    # 6. Calculate Seasonal Crossings
    ds['crossed_seasonal_cold'] = ds['enthalpy'] < ds['seasonal_enthalpy_thresholds'].sel(quantile=cold_quants)
    ds['crossed_seasonal_hot'] = ds['enthalpy'] > ds['seasonal_enthalpy_thresholds'].sel(quantile=hot_quants)
    
    # 7. Convert boolean crossings to 1 (yes) and 0 (no) as requested
    ds['crossed_annual_cold'] = ds['crossed_annual_cold'].astype(int)
    ds['crossed_annual_hot'] = ds['crossed_annual_hot'].astype(int)
    ds['crossed_seasonal_cold'] = ds['crossed_seasonal_cold'].astype(int)
    ds['crossed_seasonal_hot'] = ds['crossed_seasonal_hot'].astype(int)
    
    # 8. Save the stacked dataset
    print(f"[{region_name}] Saving to {out_file}...")
    # Rechunking to standard sizes before saving helps file I/O speed
    ds.to_netcdf(out_file, compute=True)
    print(f"[{region_name}] Done!\n")

def main():
    # VIRGINIA
    process_region(
        raw_files_glob='/discover/nobackup/cmbreen/datacenters/virginia/*.nc',
        thresh_file='/discover/nobackup/cmbreen/datacenters/virginia_enthalpy_quantiles.nc',
        out_file='/discover/nobackup/cmbreen/datacenters/virginia_enthalpy_stacked.nc',
        region_name='Virginia'
    )
    
    # TEXAS
    process_region(
        raw_files_glob='/discover/nobackup/cmbreen/datacenters/texas/*.nc',
        thresh_file='/discover/nobackup/cmbreen/datacenters/texas_enthalpy_quantiles.nc',
        out_file='/discover/nobackup/cmbreen/datacenters/texas_enthalpy_stacked.nc',
        region_name='Texas'
    )

if __name__ == "__main__":
    main()