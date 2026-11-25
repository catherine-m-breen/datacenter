"""
Datacenter Thermal Exposure Mapping
Generates 99.6th percentile exposure maps for Wet Bulb, Dry Bulb, and Enthalpy.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import xarray as xr
import metpy.calc as mpcalc
from metpy.units import units
import warnings
import os

warnings.filterwarnings('ignore')

# ==========================================
# 0. CONFIGURATION & PATHS (EDIT HERE)
# ==========================================
# Datacenter Atlas CSV
CSV_PATH = '/discover/nobackup/cmbreen/datacenters/data/im3_open_source_data_center_atlas_v2026.02.09.csv'

# NLDAS NetCDF Files (Update these to point to your real historical NLDAS data)
# You can use glob patterns (e.g., 'path/to/nldas/*.nc') if using xr.open_mfdataset
VA_NLDAS_PATH = '/discover/nobackup/cmbreen/datacenters/data/nldas_va_placeholder.nc'
TX_NLDAS_PATH = '/discover/nobackup/cmbreen/datacenters/data/nldas_tx_placeholder.nc'

# Bounding Boxes
VA_BOUNDS = {'lat_min': 38.70, 'lat_max': 39.15, 'lon_min': -77.70, 'lon_max': -77.25}
TX_BOUNDS = {'lat_min': 32.3, 'lat_max': 33.3, 'lon_min': -97.5, 'lon_max': -96.5}


# ==========================================
# 1. EXPOSURE CALCULATION (ALL 3 METRICS)
# ==========================================
def get_historical_exposures(nldas_path, dc_df):
    """
    Extracts time series for each datacenter, calculates Wet Bulb, Dry Bulb, 
    and Enthalpy, and returns the 99.6th percentile for each facility.
    """
    print(f"Loading NLDAS data from {nldas_path}...")
    
    # Use open_mfdataset if dealing with multiple files, else open_dataset
    if '*' in nldas_path or '?' in nldas_path:
        ds = xr.open_mfdataset(nldas_path, chunks='auto')[['Tair_C', 'Qair', 'PSurf']]
    else:
        ds = xr.open_dataset(nldas_path)[['Tair_C', 'Qair', 'PSurf']]
    
    print(f"Finding nearest neighbors for {len(dc_df)} facilities...")
    lat_idxs = [np.abs(ds.lat.values - lat).argmin() for lat in dc_df['lat'].values]
    lon_idxs = [np.abs(ds.lon.values - lon).argmin() for lon in dc_df['lon'].values]
    
    # Extract point time series and compute (brings subset into memory for fast Pandas math)
    ds_pts = ds.isel(
        lat=xr.DataArray(lat_idxs, dims='datacenter'), 
        lon=xr.DataArray(lon_idxs, dims='datacenter')
    ).compute()
    
    df = ds_pts.to_dataframe().reset_index()
    ds.close()
    
    print("Calculating Thermodynamics (Dry Bulb, Wet Bulb, Enthalpy)...")
    # 1. Dry Bulb Temp (Already in dataset as Tair_C)
    df['DryBulb_C'] = df['Tair_C']
    
    # 2. Wet Bulb Temp (Via MetPy)
    temp = df['Tair_C'].values * units.degC
    press = df['PSurf'].values * units.Pa
    qair = df['Qair'].values * units('kg/kg')
    
    rh = mpcalc.relative_humidity_from_specific_humidity(press, temp, qair) * 100 * units.percent
    dewpt = mpcalc.dewpoint_from_relative_humidity(temp, rh)
    df['WetBulb_C'] = mpcalc.wet_bulb_temperature(press, temp, dewpt).m
    
    # 3. Enthalpy (Standard ASHRAE Moist Air Formula: kJ/kg)
    # H = 1.006 * T + W * (2501 + 1.86 * T)  where W is specific humidity in kg/kg
    df['Enthalpy_kJ_kg'] = 1.006 * df['Tair_C'] + df['Qair'] * (2501 + 1.86 * df['Tair_C'])
    
    print("Extracting 99.6th Percentiles...")
    # Group by facility and get extreme metrics
    dc_df['Exposure_DryBulb'] = df.groupby('datacenter')['DryBulb_C'].quantile(0.996).values
    dc_df['Exposure_WetBulb'] = df.groupby('datacenter')['WetBulb_C'].quantile(0.996).values
    dc_df['Exposure_Enthalpy'] = df.groupby('datacenter')['Enthalpy_kJ_kg'].quantile(0.996).values
    
    return dc_df


# ==========================================
# 2. SCALE BAR HELPER FUNCTION
# ==========================================
def add_scalebar(ax, lon0, lat0, length_km):
    d_lon = length_km / (111.32 * np.cos(np.radians(lat0)))
    
    ax.plot([lon0, lon0 + d_lon], [lat0, lat0], color='black', linewidth=5, transform=ccrs.PlateCarree(), zorder=10)
    tick = 0.015  
    ax.plot([lon0, lon0], [lat0 - tick/2, lat0 + tick/2], color='black', linewidth=2, transform=ccrs.PlateCarree(), zorder=10)
    ax.plot([lon0 + d_lon, lon0 + d_lon], [lat0 - tick/2, lat0 + tick/2], color='black', linewidth=2, transform=ccrs.PlateCarree(), zorder=10)
    
    bbox = dict(facecolor='white', alpha=0.8, edgecolor='none', pad=0.3)
    ax.text(lon0 + d_lon/2, lat0 + 0.018, f'{length_km} km', ha='center', va='bottom', fontsize=20, fontweight='bold', transform=ccrs.PlateCarree(), zorder=10, bbox=bbox)


# ==========================================
# 3. CORE PLOTTING FUNCTION
# ==========================================
def plot_exposure_map(va_df, tx_df, metric_col, cbar_label, out_pdf):
    print(f"\nPlotting Map for {metric_col}...")
    proj = ccrs.PlateCarree()
    fig, axes = plt.subplots(1, 2, figsize=(22, 9), subplot_kw={'projection': proj})

    plt.rcParams.update({'font.size': 20})

    # Force shared color scale across both maps based on the chosen metric
    vmin = min(va_df[metric_col].min(), tx_df[metric_col].min())
    vmax = max(va_df[metric_col].max(), tx_df[metric_col].max())

    # --- HIGH-RES CARTOPY FEATURES ---
    states_10m = cfeature.NaturalEarthFeature('cultural', 'admin_1_states_provinces_lines', '10m', facecolor='none')
    counties_10m = cfeature.NaturalEarthFeature('cultural', 'admin_2_counties', '10m', facecolor='none')
    lakes_10m = cfeature.NaturalEarthFeature('physical', 'lakes', '10m', facecolor='lightblue', edgecolor='dodgerblue')
    rivers_10m = cfeature.NaturalEarthFeature('physical', 'rivers_lake_centerlines', '10m', facecolor='none')

    # --- CUSTOM LEGEND ELEMENTS ---
    legend_elements = [
        Line2D([0], [0], color='black', lw=2.5, label='State Line'),
        Line2D([0], [0], color='gray', lw=1.5, linestyle=':', label='County Line')
    ]

    # --- PLOT VIRGINIA ---
    axes[0].add_feature(counties_10m, edgecolor='gray', linewidth=0.8, linestyle=':', zorder=0) 
    axes[0].add_feature(lakes_10m, alpha=0.6, zorder=1)
    axes[0].add_feature(rivers_10m, edgecolor='dodgerblue', linewidth=1.2, zorder=1)
    axes[0].add_feature(states_10m, edgecolor='black', linewidth=2.5, zorder=2) 

    sc1 = axes[0].scatter(
        va_df['lon'], va_df['lat'], c=va_df[metric_col], cmap='YlOrRd',           
        s=250, edgecolor='black', linewidth=0.8, vmin=vmin, vmax=vmax, alpha=0.9, transform=proj, zorder=3
    )

    # Cities in VA
    axes[0].plot(-77.3411, 38.9687, marker='*', color='black', markersize=20, transform=proj, zorder=4)
    axes[0].text(-77.3411, 38.9687 + 0.015, 'Reston', fontsize=20, fontweight='bold', transform=proj, zorder=5, ha='center', va='bottom')

    # Map Embellishments
    add_scalebar(axes[0], lon0=-77.66, lat0=38.72, length_km=10)
    axes[0].legend(handles=legend_elements, loc='lower right', fontsize=20, framealpha=0.9)

    axes[0].set_title(f"Northern Virginia ({len(va_df)} Datacenters)", fontweight='bold', fontsize=20, pad=15)
    axes[0].set_extent([VA_BOUNDS['lon_min'], VA_BOUNDS['lon_max'], VA_BOUNDS['lat_min'], VA_BOUNDS['lat_max']], crs=proj)

    gl1 = axes[0].gridlines(draw_labels=True, linestyle='--', alpha=0.6, zorder=0)
    gl1.top_labels = False; gl1.right_labels = False
    gl1.xlabel_style = {'size': 20, 'rotation': 0}; gl1.ylabel_style = {'size': 20, 'rotation': 90}  

    # --- PLOT TEXAS ---
    axes[1].add_feature(counties_10m, edgecolor='gray', linewidth=0.8, linestyle=':', zorder=0) 
    axes[1].add_feature(lakes_10m, alpha=0.6, zorder=1)
    axes[1].add_feature(rivers_10m, edgecolor='dodgerblue', linewidth=1.2, zorder=1)
    axes[1].add_feature(states_10m, edgecolor='black', linewidth=2.5, zorder=2) 

    sc2 = axes[1].scatter(
        tx_df['lon'], tx_df['lat'], c=tx_df[metric_col], cmap='YlOrRd', 
        s=250, edgecolor='black', linewidth=0.8, vmin=vmin, vmax=vmax, alpha=0.9, transform=proj, zorder=3
    )

    # Cities in TX
    axes[1].plot(-97.3308, 32.7555, marker='*', color='black', markersize=20, transform=proj, zorder=4)
    axes[1].text(-97.3308 + 0.02, 32.7555, 'Fort Worth', fontsize=20, fontweight='bold', transform=proj, zorder=5, va='center')

    axes[1].plot(-96.7970, 32.7767, marker='*', color='black', markersize=20, transform=proj, zorder=4)
    axes[1].text(-96.7970, 32.7767 - 0.025, 'Dallas', fontsize=20, fontweight='bold', transform=proj, zorder=5, ha='center', va='top')

    # Map Embellishments
    add_scalebar(axes[1], lon0=-97.43, lat0=32.36, length_km=20)
    axes[1].legend(handles=legend_elements, loc='lower right', fontsize=20, framealpha=0.9)

    axes[1].set_title(f"Texas ({len(tx_df)} Datacenters)", fontweight='bold', fontsize=20, pad=15)
    axes[1].set_extent([TX_BOUNDS['lon_min'], TX_BOUNDS['lon_max'], TX_BOUNDS['lat_min'], TX_BOUNDS['lat_max']], crs=proj)

    gl2 = axes[1].gridlines(draw_labels=True, linestyle='--', alpha=0.6, zorder=0)
    gl2.top_labels = False; gl2.right_labels = False
    gl2.xlabel_style = {'size': 20, 'rotation': 0}; gl2.ylabel_style = {'size': 20, 'rotation': 90}

    # --- SHARED COLORBAR ---
    cbar = fig.colorbar(sc1, ax=axes.ravel().tolist(), fraction=0.03, pad=0.04)
    cbar.set_label(cbar_label, fontweight='bold', fontsize=20, labelpad=20)
    cbar.ax.tick_params(labelsize=20)

    plt.suptitle("Facility Thermal Exposure Map: Datacenters Colored by Historical Heat Stress", fontweight='bold', fontsize=20, y=1.02)

    plt.savefig(out_pdf, bbox_inches='tight')
    plt.close() # Close figure to free memory for the next loop

    print(f"Map successfully saved to {out_pdf}!")


# ==========================================
# 4. MAIN EXECUTION SCRIPT
# ==========================================
if __name__ == '__main__':
    print(f"Loading real datacenter data from: {CSV_PATH}")
    dc_df = pd.read_csv(CSV_PATH)

    # Standardize column names
    cols_lower = {c: c.lower() for c in dc_df.columns}
    dc_df.rename(columns=cols_lower, inplace=True)
    if 'latitude' in dc_df.columns:
        dc_df.rename(columns={'latitude': 'lat', 'longitude': 'lon'}, inplace=True)

    # Filter to specific boxes
    va_data = dc_df[
        (dc_df['lat'] >= VA_BOUNDS['lat_min']) & (dc_df['lat'] <= VA_BOUNDS['lat_max']) & 
        (dc_df['lon'] >= VA_BOUNDS['lon_min']) & (dc_df['lon'] <= VA_BOUNDS['lon_max'])
    ].copy()

    tx_data = dc_df[
        (dc_df['lat'] >= TX_BOUNDS['lat_min']) & (dc_df['lat'] <= TX_BOUNDS['lat_max']) & 
        (dc_df['lon'] >= TX_BOUNDS['lon_min']) & (dc_df['lon'] <= TX_BOUNDS['lon_max'])
    ].copy()

    print(f"Found {len(va_data)} datacenters in Northern Virginia.")
    print(f"Found {len(tx_data)} datacenters in Texas.")

    # Process Historical Exposures for all 3 metrics
    print("\n--- Processing Virginia Historical Data ---")
    va_data = get_historical_exposures(VA_NLDAS_PATH, va_data)
    
    print("\n--- Processing Texas Historical Data ---")
    tx_data = get_historical_exposures(TX_NLDAS_PATH, tx_data)

    # Define the 3 maps we want to make
    metrics_to_plot = [
        {
            'col': 'Exposure_WetBulb',
            'label': "Historical Thermal Exposure\n(99.6th Percentile Wet-Bulb Temp °C)",
            'out': 'Facility_Thermal_Exposure_WetBulb.pdf'
        },
        {
            'col': 'Exposure_DryBulb',
            'label': "Historical Thermal Exposure\n(99.6th Percentile Dry-Bulb Temp °C)",
            'out': 'Facility_Thermal_Exposure_DryBulb.pdf'
        },
        {
            'col': 'Exposure_Enthalpy',
            'label': "Historical Thermal Exposure\n(99.6th Percentile Enthalpy kJ/kg)",
            'out': 'Facility_Thermal_Exposure_Enthalpy.pdf'
        }
    ]

    # Generate all 3 Maps
    for m in metrics_to_plot:
        plot_exposure_map(
            va_df=va_data, 
            tx_df=tx_data, 
            metric_col=m['col'], 
            cbar_label=m['label'], 
            out_pdf=m['out']
        )
    
    print("\nAll processing and plotting completed successfully!")