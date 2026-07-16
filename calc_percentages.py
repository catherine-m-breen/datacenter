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



def main():
    # 1. Load the data 
    virginia_path = sorted(glob.glob('/discover/nobackup/cmbreen/datacenters/virginia/*.nc'))
    print(f"Found {len(virginia_path)} files. Loading dataset...")

    ds = xr.open_mfdataset(virginia_path, combine='by_coords', parallel=True, engine='h5netcdf') 
    
    # Rechunk to have continuous time chunks for quantile calculation
    ds = ds.chunk({'time': -1}) 

    quantiles = [0.01, 0.05, 0.10, 0.90, 0.95, 0.99]

    # 2. Calculate the Annual percentiles
    print("Calculating annual percentiles...")
    annual_quantiles = ds['enthalpy'].quantile(quantiles, dim='time').compute()

    # 3. Calculate the Seasonal percentiles
    # xarray automatically groups by 'DJF', 'MAM', 'JJA', 'SON'
    print("Calculating seasonal percentiles...")
    seasonal_quantiles = ds['enthalpy'].groupby('time.season').quantile(quantiles, dim='time').compute()

    # 4. Package them all into a single Dataset (these will act as your "bands")
    print("Structuring final dataset...")
    ds_out = xr.Dataset({
        'enthalpy_annual': annual_quantiles,
        'enthalpy_winter': seasonal_quantiles.sel(season='DJF'),
        'enthalpy_spring': seasonal_quantiles.sel(season='MAM'),
        'enthalpy_summer': seasonal_quantiles.sel(season='JJA'),
        'enthalpy_fall':   seasonal_quantiles.sel(season='SON')
    })

    # 5. Save the results to a single NetCDF file
    out_file = '/discover/nobackup/cmbreen/datacenters/virginia_enthalpy_quantiles.nc'
    print(f"Saving to {out_file}...")
    
    # The output will have 5 variables (bands), each with dimensions: (quantile, lat, lon)
    ds_out.to_netcdf(out_file)
    print("Virginia Done!")

    ######## Now do texas!!!! #######
        # 1. Load the data 
    texas_path = sorted(glob.glob('/discover/nobackup/cmbreen/datacenters/texas/*.nc'))
    print(f"Found {len(virginia_path)} files. Loading dataset...")

    ds = xr.open_mfdataset(texas_path, combine='by_coords', parallel=True, engine='h5netcdf') 
    
    # Rechunk to have continuous time chunks for quantile calculation
    ds = ds.chunk({'time': -1}) 

    quantiles = [0.01, 0.05, 0.10, 0.90, 0.95, 0.99]

    # 2. Calculate the Annual percentiles
    print("Calculating annual percentiles...")
    annual_quantiles = ds['enthalpy'].quantile(quantiles, dim='time').compute()

    # 3. Calculate the Seasonal percentiles
    # xarray automatically groups by 'DJF', 'MAM', 'JJA', 'SON'
    print("Calculating seasonal percentiles...")
    seasonal_quantiles = ds['enthalpy'].groupby('time.season').quantile(quantiles, dim='time').compute()

    # 4. Package them all into a single Dataset (these will act as your "bands")
    print("Structuring final dataset...")
    ds_out = xr.Dataset({
        'enthalpy_annual': annual_quantiles,
        'enthalpy_winter': seasonal_quantiles.sel(season='DJF'),
        'enthalpy_spring': seasonal_quantiles.sel(season='MAM'),
        'enthalpy_summer': seasonal_quantiles.sel(season='JJA'),
        'enthalpy_fall':   seasonal_quantiles.sel(season='SON')
    })

    # 5. Save the results to a single NetCDF file
    out_file = '/discover/nobackup/cmbreen/datacenters/texas_enthalpy_quantiles.nc'
    print(f"Saving to {out_file}...")
    
    # The output will have 5 variables (bands), each with dimensions: (quantile, lat, lon)
    ds_out.to_netcdf(out_file)
    print("Texas Done!")


if __name__ == "__main__":
    main()