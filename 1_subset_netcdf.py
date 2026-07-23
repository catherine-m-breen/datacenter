import xarray as xr
import matplotlib.pyplot as plt
import tqdm
import os
## Forcing file for all years and days ##
import glob


import xarray as xr
import tqdm
import os
import glob

def process_state_forcing(forcing_files, output_dir, lat_slice, lon_slice, prefix):
    os.makedirs(output_dir, exist_ok=True)
    print(f"\nProcessing {len(forcing_files)} files for {prefix}...")
    
    for file in tqdm.tqdm(forcing_files):
        ds = xr.open_dataset(file)
        
        # Subset spatially
        ds_nova = ds.sel(lat=lat_slice, lon=lon_slice)
        
        # Calculate variables while PRESERVING the time dimension
        temp = ds_nova['Tair'] - 273.15
        temp_max = ds_nova['Tair_max'] - 273.15 # Fixed mapping
        temp_min = ds_nova['Tair_min'] - 273.15 # Fixed mapping
        
        humidity = ds_nova['Qair']
        pressure = ds_nova['PSurf']

        # convert Qair to humidity ratio (using the right variable)
        W = humidity / (1.0 - humidity)

        # Calculate enthalpy
        enthalpy = 1.006 * temp + W * (2501.0 + 1.86 * temp)

        # Create output dataset
        out_ds = xr.Dataset(
            data_vars={
                'Tair': temp,
                'Tair_min': temp_min,
                'Tair_max': temp_max,
                'Qair': humidity,
                'PSurf': pressure,
                'enthalpy': enthalpy
            },
            coords={
                'time': ds_nova['time'],
                'lat': ds_nova['lat'],
                'lon': ds_nova['lon']
            }
        )

        # Add metadata
        out_ds['Tair'].attrs['units'] = 'Celsius'
        out_ds['Tair'].attrs['long_name'] = '2-m Air Temperature (Dry Bulb)'
        out_ds['Tair_max'].attrs['long_name'] = '2-m Air Temperature MAX (Dry Bulb)'
        out_ds['Tair_max'].attrs['units'] = 'Celsius'
        out_ds['Tair_min'].attrs['long_name'] = '2-m Air Temperature MIN (Dry Bulb)'
        out_ds['Tair_min'].attrs['units'] = 'Celsius'
        out_ds['enthalpy'].attrs['units'] = 'kJ/kg'
        out_ds['enthalpy'].attrs['long_name'] = 'Air Enthalpy'
        out_ds['enthalpy'].attrs['description'] = 'Calculated from Tair and Qair'

        out_ds.attrs = ds.attrs
        out_ds.attrs['processing_note'] = 'Subsetted; Enthalpy calculated; Temp converted to C'

        # Save to NetCDF
        base_name = os.path.basename(file)
        out_filename = os.path.join(output_dir, f"{prefix}_{base_name}")
        out_ds.to_netcdf(out_filename)

        ds.close()
        out_ds.close()


if __name__ == "__main__":
    forcing_files = sorted(glob.glob('/discover/nobackup/projects/eis_nldas3/DATA/forcing/daily/2*/*.nc'))
    
    print(f"First file: {forcing_files[0]}")
    print(f"Last file: {forcing_files[-1]}")
    
    # VIRGINIA
    process_state_forcing(
        forcing_files=forcing_files,
        output_dir='/discover/nobackup/cmbreen/datacenters/virginia',
        lat_slice=slice(38.5, 39.5),
        lon_slice=slice(-78, -77),
        prefix='va'
    )
    
    # TEXAS
    process_state_forcing(
        forcing_files=forcing_files,
        output_dir='/discover/nobackup/cmbreen/datacenters/texas',
        lat_slice=slice(32.3, 33.3),
        lon_slice=slice(-97.5, -96.5),
        prefix='tx'
    )



# ##################################
# ############ VIRGINIA ################
# ##################################

# forcing_files = sorted(glob.glob('/discover/nobackup/projects/eis_nldas3/DATA/forcing/daily/2*/*.nc'))

# output_dir = '/discover/nobackup/cmbreen/datacenters/virginia'
# os.makedirs(output_dir, exist_ok=True)


# print(forcing_files[0])
# print(forcing_files[-1])
# print(f' it is {len(forcing_files)} files') ##
# ## it goes from 2001 to 2023

# ## Subsetting information
# lat_slice = slice(38.5, 39.5)
# lon_slice = slice(-78, -77)

# ## check that there aren't other better variables. There aren't any better ones (LWdown, SWdown Wind_E Rainf Qair
# forcing_vars = ['Tair', 'Tair_max', 'Tair_min', 'Qair', 'PSurf']


# max_enthalpy_rasters = []
# for file in tqdm.tqdm(forcing_files):
#     ds = xr.open_dataset(file)
#     ds_nova = ds.sel(lat=lat_slice, lon=lon_slice)
#     temp = ds_nova['Tair'].isel(time=0) - 273.15 # convert Kelvin to Celsius
#     temp_max = ds_nova['Tair_max'].isel(time=0) - 273.15 # convert Kelvin to Celsius
#     temp_min = ds_nova['Tair_min'].isel(time=0) - 273.15 # convert Kelvin to Celsius
#         ## this is temp not dry_bulb? double check
#     humidity = ds_nova['Qair'].isel(time=0)
#     pressure = ds_nova['PSurf'].isel(time=0)

#     # convert Qair to humidity ratio
#     W = ds_nova['Qair'] / (1.0 - ds_nova['Qair'])

#     #enthalpy = 1.006 * T_db + W * (2501.0 + 1.86 * T_db) ## measured in kJ/kg
#     enthalpy = 1.006 * temp + W * (2501.0 + 1.86 * temp)
#     #max_enthalpy_rasters.append(enthalpy)

#     # 4. Create the final output dataset with ALL requested variables
#     out_ds = xr.Dataset(
#         data_vars={
#             'Tair': temp,
#             'Tair_min': temp_min,
#             'Tair_max': temp_max,
#             'Qair': humidity,
#             'PSurf': pressure,
#             'enthalpy': enthalpy
#         },
#         coords={
#             'time': ds_nova['time'],
#             'lat': ds_nova['lat'],
#             'lon': ds_nova['lon']
#         }
#     )

#     # 5. Add metadata
#     out_ds['Tair'].attrs['units'] = 'Celsius'
#     out_ds['Tair'].attrs['long_name'] = '2-m Air Temperature (Dry Bulb)'
#     out_ds['Tair_max'].attrs['long_name'] = '2-m Air Temperature MAX (Dry Bulb)'
#     out_ds['Tair_max'].attrs['units'] = 'Celsius'
#     out_ds['Tair_min'].attrs['long_name'] = '2-m Air Temperature MIN (Dry Bulb)'
#     out_ds['Tair_min'].attrs['units'] = 'Celsius'
#     out_ds['enthalpy'].attrs['units'] = 'kJ/kg'
#     out_ds['enthalpy'].attrs['long_name'] = 'Air Enthalpy'
#     out_ds['enthalpy'].attrs['description'] = 'Calculated from Tair and Qair'

#     # Preserve global attributes from the original file
#     out_ds.attrs = ds.attrs
#     out_ds.attrs['processing_note'] = 'Subsetted; Enthalpy calculated; Temp converted to C'

#     # 6. Save to a new NetCDF file
#     base_name = os.path.basename(file)
#     out_filename = os.path.join(output_dir, f"va_{base_name}")

#     out_ds.to_netcdf(out_filename)

#     # 7. Explicitly close datasets to free up memory
#     ds.close()
#     out_ds.close()




# ##################################
# ############ TEXAS ################
# ##################################

# forcing_files = sorted(glob.glob('/discover/nobackup/projects/eis_nldas3/DATA/forcing/daily/2*/*.nc'))

# output_dir = '/discover/nobackup/cmbreen/datacenters/texas'
# os.makedirs(output_dir, exist_ok=True)


# print(forcing_files[0])
# print(forcing_files[-1])
# print(f' it is {len(forcing_files)} files') ##
# ## it goes from 2001 to 2023


# ## Subsetting information
# lat_slice = slice(32.3, 33.3)
# lon_slice = slice(-97.5, -96.5)

# ## check that there aren't other better variables. There aren't any better ones (LWdown, SWdown Wind_E Rainf Qair
# forcing_vars = ['Tair', 'Tair_max', 'Tair_min','Qair', 'PSurf']


# max_enthalpy_rasters = []
# for file in tqdm.tqdm(forcing_files):
#     ds = xr.open_dataset(file)
#     ds_nova = ds.sel(lat=lat_slice, lon=lon_slice)
#     temp = ds_nova['Tair'].isel(time=0) - 273.15 # convert Kelvin to Celsius
#     temp_max = ds_nova['Tair_max'].isel(time=0) - 273.15 # convert Kelvin to Celsius
#     temp_min = ds_nova['Tair_min'].isel(time=0) - 273.15 # convert Kelvin to Celsius
#         ## this is temp not dry_bulb? double check
#     humidity = ds_nova['Qair'].isel(time=0)
#     pressure = ds_nova['PSurf'].isel(time=0)

#     # convert Qair to humidity ratio
#     W = ds_nova['Qair'] / (1.0 - ds_nova['Qair'])

#     #enthalpy = 1.006 * T_db + W * (2501.0 + 1.86 * T_db) ## measured in kJ/kg
#     enthalpy = 1.006 * temp + W * (2501.0 + 1.86 * temp)
#     #max_enthalpy_rasters.append(enthalpy)

#     # 4. Create the final output dataset with ALL requested variables
#     out_ds = xr.Dataset(
#         data_vars={
#             'Tair': temp,
#             'Tair_min': temp_min,
#             'Tair_max': temp_max,
#             'Qair': humidity,
#             'PSurf': pressure,
#             'enthalpy': enthalpy
#         },
#         coords={
#             'time': ds_nova['time'],
#             'lat': ds_nova['lat'],
#             'lon': ds_nova['lon']
#         }
#     )

#     # 5. Add metadata
#     out_ds['Tair'].attrs['units'] = 'Celsius'
#     out_ds['Tair'].attrs['long_name'] = '2-m Air Temperature (Dry Bulb)'
#     out_ds['Tair_max'].attrs['long_name'] = '2-m Air Temperature MAX (Dry Bulb)'
#     out_ds['Tair_max'].attrs['units'] = 'Celsius'
#     out_ds['Tair_min'].attrs['long_name'] = '2-m Air Temperature MIN (Dry Bulb)'
#     out_ds['Tair_min'].attrs['units'] = 'Celsius'
#     out_ds['enthalpy'].attrs['units'] = 'kJ/kg'
#     out_ds['enthalpy'].attrs['long_name'] = 'Air Enthalpy'
#     out_ds['enthalpy'].attrs['description'] = 'Calculated from Tair and Qair'

#     # Preserve global attributes from the original file
#     out_ds.attrs = ds.attrs
#     out_ds.attrs['processing_note'] = 'Subsetted; Enthalpy calculated; Temp converted to C'

#     # 6. Save to a new NetCDF file
#     base_name = os.path.basename(file)
#     out_filename = os.path.join(output_dir, f"tx_{base_name}")

#     out_ds.to_netcdf(out_filename)

#     # 7. Explicitly close datasets to free up memory
#     ds.close()
#     out_ds.close()

