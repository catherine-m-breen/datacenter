import pandas as pd
import xarray as xr
import numpy as np
import matplotlib.pyplot as plt
import metpy.calc as mpcalc
from metpy.units import units
import warnings

warnings.filterwarnings('ignore')

# ==========================================
# 1. PATHS
# ==========================================
csv_path = '/discover/nobackup/cmbreen/datacenters/data/im3_open_source_data_center_atlas_v2026.02.09.csv'
tx_nldas3 = '/discover/nobackup/cmbreen/datacenters/texas_pure_hourly/tx_Pure_Hourly_Summary_FIXED.nc'
va_nldas3 = '/discover/nobackup/cmbreen/datacenters/virginia_pure_hourly/va_Pure_Hourly_Summary_FIXED.nc'
out_map_pdf = './Facility_Thermal_Exposure_Map.pdf'

# ==========================================
# 2. FAST EXPOSURE CALCULATION
# ==========================================
def get_thermal_exposure(state_abb, nldas_file, dc_df):
    print(f"Calculating Thermal Exposure for {state_abb}...")
    state_dcs = dc_df[dc_df['state_abb'] == state_abb].copy()
    
    ds = xr.open_dataset(nldas_file)[['Tair_C', 'Qair', 'PSurf']]
    
    # Fast nearest-neighbor lookup
    lat_idxs = [np.abs(ds.lat.values - lat).argmin() for lat in state_dcs['lat'].values]
    lon_idxs = [np.abs(ds.lon.values - lon).argmin() for lon in state_dcs['lon'].values]
    
    ds_pts = ds.isel(
        lat=xr.DataArray(lat_idxs, dims='datacenter'), 
        lon=xr.DataArray(lon_idxs, dims='datacenter')
    ).compute()
    
    df = ds_pts.to_dataframe().reset_index()
    ds.close()
    
    # Calculate Wet Bulb
    temp = df['Tair_C'].values * units.degC
    press = df['PSurf'].values * units.Pa
    qair = df['Qair'].values * units('kg/kg')
    
    rh = mpcalc.relative_humidity_from_specific_humidity(press, temp, qair) * 100 * units.percent
    dewpt = mpcalc.dewpoint_from_relative_humidity(temp, rh)
    df['Twb_C'] = mpcalc.wet_bulb_temperature(press, temp, dewpt).m
    
    # Extract the 99th percentile Wet-Bulb Temp for each facility
    exposure_vals = df.groupby('datacenter')['Twb_C'].quantile(0.99).values
    state_dcs['Thermal_Exposure'] = exposure_vals
    
    return state_dcs

# ==========================================
# 3. EXECUTE & PLOT
# ==========================================
dc_df = pd.read_csv(csv_path)

va_data = get_thermal_exposure('VA', va_nldas3, dc_df)
tx_data = get_thermal_exposure('TX', tx_nldas3, dc_df)

print("Plotting the Maps...")
# 1 Row, 2 Columns (Separate Lat/Lon grids!)
fig, axes = plt.subplots(1, 2, figsize=(22, 9))
plt.rcParams.update({'font.size': 14})

# CRITICAL STEP: Global Min/Max to force both maps to share the exact same color scale
vmin = min(va_data['Thermal_Exposure'].min(), tx_data['Thermal_Exposure'].min())
vmax = max(va_data['Thermal_Exposure'].max(), tx_data['Thermal_Exposure'].max())

# --- PLOT VIRGINIA ---
sc1 = axes[0].scatter(
    va_data['lon'], va_data['lat'], 
    c=va_data['Thermal_Exposure'], 
    cmap='YlOrRd',           # Yellow to Orange to Red heatmap
    s=250,                   # Dot size (larger for visibility)
    edgecolor='black',       # Give dots a border so they pop
    linewidth=0.8,
    vmin=vmin, vmax=vmax,    # Force uniform scale
    alpha=0.9
)
axes[0].set_title("Northern Virginia (309 Datacenters)", fontweight='bold', fontsize=20, pad=15)
axes[0].set_xlabel("Longitude", fontweight='bold', fontsize=16)
axes[0].set_ylabel("Latitude", fontweight='bold', fontsize=16)
axes[0].grid(True, linestyle='--', alpha=0.6)
# Correct the aspect ratio so the state doesn't look stretched
axes[0].set_aspect(1.0 / np.cos(np.radians(va_data['lat'].mean())))

# --- PLOT TEXAS ---
sc2 = axes[1].scatter(
    tx_data['lon'], tx_data['lat'], 
    c=tx_data['Thermal_Exposure'], 
    cmap='YlOrRd', 
    s=250, 
    edgecolor='black',
    linewidth=0.8,
    vmin=vmin, vmax=vmax,    # Force uniform scale
    alpha=0.9
)
axes[1].set_title("Texas (69 Datacenters)", fontweight='bold', fontsize=20, pad=15)
axes[1].set_xlabel("Longitude", fontweight='bold', fontsize=16)
axes[1].set_ylabel("Latitude", fontweight='bold', fontsize=16)
axes[1].grid(True, linestyle='--', alpha=0.6)
# Correct the aspect ratio for Texas's latitude
axes[1].set_aspect(1.0 / np.cos(np.radians(tx_data['lat'].mean())))

# --- SHARED COLORBAR ---
# We attach one massive colorbar to both plots
cbar = fig.colorbar(sc1, ax=axes.ravel().tolist(), fraction=0.03, pad=0.04)
cbar.set_label("Historical Thermal Exposure\n(99th Percentile Wet-Bulb Temp °C)", fontweight='bold', fontsize=18, labelpad=20)
cbar.ax.tick_params(labelsize=14)

plt.suptitle("Facility Thermal Exposure Map: Datacenters Colored by Historical Heat Stress", fontweight='bold', fontsize=26, y=1.02)

plt.savefig(out_map_pdf, bbox_inches='tight')
plt.show()

print(f"Map successfully saved to {out_map_pdf}!")