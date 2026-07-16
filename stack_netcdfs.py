'''
After we have pulled the bounding box for Tair, Psurf, Q & enthalpy for all of NLDAS3 (see /discover/nobackup/cmbreen/subset_netcdf.py)
and also pulled the 90, 95, 99 thresholds for the full year (/discover/nobackup/cmbreen/calc_percentiles.py)
and also pulled the 90, 95, 99 thresholds for each season year (/discover/nobackup/cmbreen/calc_percentiles.py)

Stack the netcdf (so it's not 8400 files)
add whether it crossed the annual 90, 95, 99 Annual threshold 
add whether it crossed it's respective seasonal 90, 95, 99 threshold 

'''

virginia = '/discover/nobackup/cmbreen/datacenters/virginia/*.nc'
texas = ''