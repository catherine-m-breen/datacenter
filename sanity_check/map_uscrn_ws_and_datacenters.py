import os
import glob
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.backends.backend_pdf import PdfPages
import warnings

warnings.filterwarnings('ignore')

# ==========================================
# CONFIGURATION
# ==========================================
STATION_DIR = '/discover/nobackup/cmbreen/datacenters/uscrn_independent_data'
DATACENTER_CSV = 'im3_open_source_data_center_atlas_v2026.02.09.csv'
OUTPUT_PDF = './master_station_datacenter_map.pdf'

# ==========================================
# 1. LOAD WEATHER STATIONS
# ==========================================
print("Gathering USCRN Weather Station locations...")
station_files = [f for f in glob.glob(os.path.join(STATION_DIR, '*.csv')) if not os.path.basename(f).startswith('all_')]

stn_lats, stn_lons = [], []
for stn_file in station_files:
    try:
        # Read just the first row to get lat/lon quickly
        df_sample = pd.read_csv(stn_file, nrows=1)
        if 'latitude' in df_sample.columns and 'longitude' in df_sample.columns:
            stn_lats.append(df_sample['latitude'].iloc[0])
            stn_lons.append(df_sample['longitude'].iloc[0])
    except:
        pass

print(f" -> Loaded {len(stn_lats)} weather stations.")

# ==========================================
# 2. LOAD DATACENTER ATLAS
# ==========================================
print(f"Gathering Data Centers from {DATACENTER_CSV}...")
if not os.path.exists(DATACENTER_CSV):
    raise FileNotFoundError(f"Could not find {DATACENTER_CSV}. Please ensure it is in the same directory.")

df_dc = pd.read_csv(DATACENTER_CSV)
df_dc = df_dc.dropna(subset=['lat', 'lon'])  # Remove any rows missing coordinates
print(f" -> Loaded {len(df_dc)} data center locations.")

# To prevent thousands of overlapping 1x1 boxes from turning solid black,
# we round the coordinates to the nearest whole degree to group nearby data centers 
# into unique 1x1 degree regional grid boxes.
df_dc['grid_lat'] = df_dc['lat'].round(0)
df_dc['grid_lon'] = df_dc['lon'].round(0)
unique_dc_regions = df_dc[['grid_lat', 'grid_lon']].drop_duplicates()

# ==========================================
# 3. GENERATE MAP PDF
# ==========================================
print(f"Generating Map PDF: {OUTPUT_PDF}")

with PdfPages(OUTPUT_PDF) as pdf:
    fig = plt.figure(figsize=(16, 10))
    fig.suptitle("USCRN Weather Stations vs. US Data Center Atlas\nWith 1°x1° Regional Datacenter Extraction Grids", fontsize=18, fontweight='bold', y=0.96)

    # Setup Custom Map Layout [left, bottom, width, height]
    ax_main = fig.add_axes([0.1, 0.2, 0.8, 0.75])    # CONUS
    ax_ak = fig.add_axes([0.1, 0.05, 0.25, 0.25])    # Alaska (Bottom Left)
    ax_hi = fig.add_axes([0.42, 0.05, 0.2, 0.2])     # Hawaii (Bottom Middle)

    axes_dict = {
        'CONUS': (ax_main, [-130, -65], [24, 50]),
        'Alaska': (ax_ak, [-180, -130], [50, 75]),
        'Hawaii': (ax_hi, [-162, -154], [18, 23])
    }

    # Attempt to load Geopandas for offline state outlines
    has_geopandas = False
    try:
        import geopandas as gpd
        world = gpd.read_file(gpd.datasets.get_path('naturalearth_lowres'))
        usa = world[world.name == "United States of America"]
        has_geopandas = True
    except:
        print("Note: Geopandas not found. Falling back to clean Cartesian grids.")

    # --- PLOTTING LOOP ---
    for region, (ax, x_bounds, y_bounds) in axes_dict.items():
        
        # 1. State/Coastline Outlines
        if has_geopandas:
            usa.boundary.plot(ax=ax, color='black', linewidth=0.8, alpha=0.5)
            
        # 2. Draw 1°x1° Data Center Regions (Light Grey Boxes)
        for _, row in unique_dc_regions.iterrows():
            center_lat = row['grid_lat']
            center_lon = row['grid_lon']
            
            # 1 degree box centered on the coordinate
            lon_min, lon_max = center_lon - 0.5, center_lon + 0.5
            lat_min, lat_max = center_lat - 0.5, center_lat + 0.5
            
            # Check if this box is inside the current subplot bounds
            if (x_bounds[0] <= center_lon <= x_bounds[1]) and (y_bounds[0] <= center_lat <= y_bounds[1]):
                rect = Rectangle((lon_min, lat_min), lon_max - lon_min, lat_max - lat_min, 
                                 linewidth=1, edgecolor='dimgrey', facecolor='lightgrey', alpha=0.3, 
                                 label='1°x1° Extraction Region' if (region == 'CONUS' and '1°x1° Extraction Region' not in ax.get_legend_handles_labels()[1]) else "")
                ax.add_patch(rect)

        # 3. Plot EXACT Data Center Locations (Dark Grey Dots)
        # Using zorder=2 ensures they plot on top of the grey boxes
        ax.scatter(df_dc['lon'], df_dc['lat'], c='black', s=10, alpha=0.6, marker='o', zorder=2,
                   label='Data Center (IM3 Atlas)' if region == 'CONUS' else "")

        # 4. Plot USCRN Weather Stations (Purple Stars)
        # Using zorder=3 ensures the stations stand out on top of everything
        ax.scatter(stn_lons, stn_lats, c='#9b59b6', s=90, marker='o', edgecolor='black', linewidth=0.5, zorder=3,
                   label='USCRN Station' if region == 'CONUS' else "")
        
        # 5. Map Formatting
        ax.set_xlim(x_bounds)
        ax.set_ylim(y_bounds)
        ax.set_title(region, fontsize=12, fontweight='bold')
        ax.set_facecolor('#f4f9f9')  # Very light blue for oceans
        ax.grid(True, linestyle=':', alpha=0.6)
        
        if region != 'CONUS':
            ax.set_xticks([])
            ax.set_yticks([])
        else:
            ax.set_xlabel("Longitude")
            ax.set_ylabel("Latitude")

    # Final Legend Generation
    handles, labels = ax_main.get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    ax_main.legend(by_label.values(), by_label.keys(), loc='lower right', framealpha=0.9, fontsize=11, markerscale=1.5)

    pdf.savefig(fig, bbox_inches='tight')
    plt.close()

print(f"\nDone! Map created successfully and saved as {OUTPUT_PDF}.")