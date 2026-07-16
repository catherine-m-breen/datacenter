'''
After we have pulled the bounding box for Tair, Psurf, Q & enthalpy for all of NLDAS3 (see /discover/nobackup/cmbreen/subset_netcdf.py)
and also pulled the 90, 95, 99 thresholds for the full year (/discover/nobackup/cmbreen/datacenters/datacenter/calc_percentiles.py)
and also pulled the 90, 95, 99 thresholds for each season year (/discover/nobackup/cmbreen/datacenters/datacenter/calc_percentiles.py)

Stack the netcdf (so it's not 8400 files)
add whether it crossed the annual 90, 95, 99 Annual threshold 
add whether it crossed it's respective seasonal 90, 95, 99 threshold 

'''
import xarray as xr
import glob
import xarray as xr
import matplotlib.pyplot as plt
import tqdm
import os


virginia = '/discover/nobackup/cmbreen/datacenters/virginia/*.nc' ## 8400 files 
texas = '/discover/nobackup/cmbreen/datacenters/texas/*.nc' ## 8400 
virginia_enthalpy_thresholds = '/discover/nobackup/cmbreen/datacenters/texas_enthalpy_quantiles.nc'
texas_enthalpy_thresholds = '/discover/nobackup/cmbreen/datacenters/texas_enthalpy_quantiles.nc'

## stack the virginia netcdfs along time dimension so there are 7 bands: 
# tair
# psurf 
# q 
# annual enthalpy quantile thresholds [0.01, 0.05, 0.1, 0.90, 0.95, 0.99] (6 values)
# did it cross annual enthalpy threshold 1(yes) 0 (no) (6 long for each threshold)
# seasonal enthalpy threshold [0.01, 0.05, 0.1, 0.90, 0.95, 0.99] (6 values) --> use month from time dimension to determine which is the season 
# season band --> use month from time dimension to determine which is the season; store season for easy slicing 
# did it cross seasonal enthalpy threshold (use month to determine which threshold to use); 1(yes) 0 (no) (6 long for each threshold)