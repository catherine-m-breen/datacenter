###
import xarray as xr
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

### prior analysis was with avg temp, this is now avg daytime temperatures 

## day night information for Virginia and Texas

va_netcdf_path = '/discover/nobackup/cmbreen/datacenters/virginia_hourly/va_Daily_DayNight_Summary.nc'
tx_netcdf_path = '/discover/nobackup/cmbreen/datacenters/texas_hourly/tx_Daily_DayNight_Summary.nc'
locations_csv = 'im3_open_source_data_center_atlas_v2026.02.09.csv'

va_ds = xr.open_dataset(va_netcdf_path)
tx_ds = xr.open_dataset(tx_netcdf_path)
tx_ds

def enthalpy_threshold_values(path, output_path):
    target_quantiles = [0.01, 0.05, 0.1, 0.90, 0.95, 0.99]

    ds = xr.open_dataset(path)
    enth_vars = ['DayTime_Avg_enthalpy', 'NightTime_Avg_enthalpy']
    ds_thresholds = ds[enth_vars].groupby('time.season').quantile(target_quantiles, dim='time')

    ds_thresholds_daily = ds_thresholds.sel(season=ds['time.season'])
    ds_thresholds_daily = ds_thresholds_daily.drop_vars('season')

    ds_thresholds_daily = ds_thresholds_daily.rename({
        'DayTime_Avg_enthalpy': 'DayTime_Avg_enthalpy_thresholds',
        'NightTime_Avg_enthalpy': 'NightTime_Avg_enthalpy_thresholds'
    })
    # merge it with original dataset
    ds_merged = xr.merge([ds, ds_thresholds_daily])
    
    ds_merged.to_netcdf(output_path)
    ds.close()
    print('done')
    return 

output_path = '/discover/nobackup/datacenters/virginia_hourly/va_daynight_threshold.nc'
va_ds = enthalpy_threshold_values(va_netcdf_path, output_path)

output_path = '/discover/nobackup/datacenters/texas_hourly/tx_daynight_threshold.nc'
tx_ts = enthalpy_threshold_values(tx_netcdf_path)
