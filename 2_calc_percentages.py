'''
add in seasonal enthalpy for 90, 95, 99

winter: december, january, february 
spring: march, april, may 
summer: june, july, august
fall: sept, oct, nov 
save as four additional bands; 
so we have the annual enthalpy thresholds, and the seasonal enthalpy thresholds 


'''
import xarray as xr
import glob

import xarray as xr
import glob

def calculate_state_quantiles(state_name, input_glob, out_file):
    print(f"\n[{state_name}] Loading dataset from {input_glob}...")
    file_paths = sorted(glob.glob(input_glob))
    
    if not file_paths:
        print(f"[{state_name}] Error: No files found!")
        return

    # Use data_vars='minimal' to avoid the FutureWarnings you were getting
    ds = xr.open_mfdataset(file_paths, combine='by_coords', parallel=True, engine='h5netcdf', data_vars='minimal') 
    
    print(f"[{state_name}] Pulling enthalpy into RAM for fast calculation...")
    # By loading just enthalpy into memory, we bypass Dask's slow distributed quantile calculation entirely
    enthalpy_da = ds['enthalpy'].load()

    quantiles = [0.01, 0.05, 0.10, 0.90, 0.95, 0.99]

    # Calculate Annual percentiles
    print(f"[{state_name}] Calculating annual percentiles...")
    annual_quantiles = enthalpy_da.quantile(quantiles, dim='time')

    # Calculate Seasonal percentiles
    print(f"[{state_name}] Calculating seasonal percentiles...")
    seasonal_quantiles = enthalpy_da.groupby('time.season').quantile(quantiles, dim='time')

    # Package into a Dataset
    print(f"[{state_name}] Structuring final dataset...")
    ds_out = xr.Dataset({
        'enthalpy_annual': annual_quantiles,
        'enthalpy_winter': seasonal_quantiles.sel(season='DJF').drop_vars('season'),
        'enthalpy_spring': seasonal_quantiles.sel(season='MAM').drop_vars('season'),
        'enthalpy_summer': seasonal_quantiles.sel(season='JJA').drop_vars('season'),
        'enthalpy_fall':   seasonal_quantiles.sel(season='SON').drop_vars('season')
    })

    # Save
    print(f"[{state_name}] Saving to {out_file}...")
    ds_out.to_netcdf(out_file)
    ds.close()
    print(f"[{state_name}] Done!")

def main():
    # VIRGINIA
    calculate_state_quantiles(
        state_name="Virginia",
        input_glob='/discover/nobackup/cmbreen/datacenters/virginia/*.nc',
        out_file='/discover/nobackup/cmbreen/datacenters/virginia_enthalpy_quantiles.nc'
    )

    # TEXAS
    calculate_state_quantiles(
        state_name="Texas",
        input_glob='/discover/nobackup/cmbreen/datacenters/texas/*.nc',
        out_file='/discover/nobackup/cmbreen/datacenters/texas_enthalpy_quantiles.nc'
    )

if __name__ == "__main__":
    main()



    '''
    the below works but chatgsfc is saying the one above it is faster
    
    
    '''

# def main():
#     # 1. Load the data 
#     virginia_path = sorted(glob.glob('/discover/nobackup/cmbreen/datacenters/virginia/*.nc'))
#     print(f"Found {len(virginia_path)} files. Loading dataset...")

#     ds = xr.open_mfdataset(virginia_path, combine='by_coords', parallel=True, engine='h5netcdf') 
    
#     # Rechunk to have continuous time chunks for quantile calculation
#     ds = ds.chunk({'time': -1}) 

#     quantiles = [0.01, 0.05, 0.10, 0.90, 0.95, 0.99]

#     # 2. Calculate the Annual percentiles
#     print("Calculating annual percentiles...")
#     annual_quantiles = ds['enthalpy'].quantile(quantiles, dim='time').compute()

#     # 3. Calculate the Seasonal percentiles
#     # xarray automatically groups by 'DJF', 'MAM', 'JJA', 'SON'
#     print("Calculating seasonal percentiles...")
#     seasonal_quantiles = ds['enthalpy'].groupby('time.season').quantile(quantiles, dim='time').compute()

#     # 4. Package them all into a single Dataset (these will act as your "bands")
#     print("Structuring final dataset...")
#     ds_out = xr.Dataset({
#         'enthalpy_annual': annual_quantiles,
#         'enthalpy_winter': seasonal_quantiles.sel(season='DJF').drop_vars('season'),
#         'enthalpy_spring': seasonal_quantiles.sel(season='MAM').drop_vars('season'),
#         'enthalpy_summer': seasonal_quantiles.sel(season='JJA').drop_vars('season'),
#         'enthalpy_fall':   seasonal_quantiles.sel(season='SON').drop_vars('season')
#     })

#     # 5. Save the results to a single NetCDF file
#     out_file = '/discover/nobackup/cmbreen/datacenters/virginia_enthalpy_quantiles.nc'
#     print(f"Saving to {out_file}...")
    
#     # The output will have 5 variables (bands), each with dimensions: (quantile, lat, lon)
#     ds_out.to_netcdf(out_file)
#     print("Virginia Done!")

#     ######## Now do texas!!!! #######
#         # 1. Load the data 
#     texas_path = sorted(glob.glob('/discover/nobackup/cmbreen/datacenters/texas/*.nc'))
#     print(f"Found {len(texas_path)} files. Loading dataset...")

#     ds = xr.open_mfdataset(texas_path, combine='by_coords', parallel=True, engine='h5netcdf') 
    
#     # Rechunk to have continuous time chunks for quantile calculation
#     ds = ds.chunk({'time': -1}) 

#     quantiles = [0.01, 0.05, 0.10, 0.90, 0.95, 0.99]

#     # 2. Calculate the Annual percentiles
#     print("Calculating annual percentiles...")
#     annual_quantiles = ds['enthalpy'].quantile(quantiles, dim='time').compute()

#     # 3. Calculate the Seasonal percentiles
#     # xarray automatically groups by 'DJF', 'MAM', 'JJA', 'SON'
#     print("Calculating seasonal percentiles...")
#     seasonal_quantiles = ds['enthalpy'].groupby('time.season').quantile(quantiles, dim='time').compute()

#     # 4. Package them all into a single Dataset (these will act as your "bands")
#     print("Structuring final dataset...")
#     ds_out = xr.Dataset({
#         'enthalpy_annual': annual_quantiles,
#         'enthalpy_winter': seasonal_quantiles.sel(season='DJF').drop_vars('season'),
#         'enthalpy_spring': seasonal_quantiles.sel(season='MAM').drop_vars('season'),
#         'enthalpy_summer': seasonal_quantiles.sel(season='JJA').drop_vars('season'),
#         'enthalpy_fall':   seasonal_quantiles.sel(season='SON').drop_vars('season')
#     })

#     # 5. Save the results to a single NetCDF file
#     out_file = '/discover/nobackup/cmbreen/datacenters/texas_enthalpy_quantiles.nc'
#     print(f"Saving to {out_file}...")
    
#     # The output will have 5 variables (bands), each with dimensions: (quantile, lat, lon)
#     ds_out.to_netcdf(out_file)
#     print("Texas Done!")


# if __name__ == "__main__":
#     main()