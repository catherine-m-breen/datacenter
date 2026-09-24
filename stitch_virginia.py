import xarray as xr
import glob
import os

def stitch_virginia():
    output_dir = '/discover/nobackup/cmbreen/datacenters/virginia_hourly'
    prefix = 'va'
    
    print("Finding all Virginia temp files...")
    # Grab all the temp files you just showed me
    yearly_files = sorted(glob.glob(os.path.join(output_dir, f"{prefix}_*_temp.nc")))
    
    if not yearly_files:
        print("No temp files found! Maybe they were already stitched and deleted?")
        return
        
    print(f"Stitching {len(yearly_files)} files into the final master file...")
    
    # Open all of them together
    ds_final = xr.open_mfdataset(
        yearly_files, 
        combine='nested', 
        concat_dim='time', 
        join='override', 
        parallel=False
    )
    
    # Sort and remove duplicates just in case there's overlap at the edges
    ds_final = ds_final.sortby('time')
    ds_final = ds_final.drop_duplicates(dim='time')
    
    final_out = os.path.join(output_dir, f"{prefix}_Daily_DayNight_Summary.nc")
    print(f"Saving to {final_out} (this might take a few minutes)...")
    
    # Save the final file
    ds_final.to_netcdf(final_out)
    ds_final.close()
    
    # Clean up the intermediate yearly files so your folder is clean
    print("Cleaning up temporary yearly files...")
    # for f in yearly_files:
    #     os.remove(f)
        
    print(f"Finished! Saved to {final_out}")

if __name__ == "__main__":
    stitch_virginia()