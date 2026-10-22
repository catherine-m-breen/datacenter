import os
import glob
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.ticker import FuncFormatter  # <-- NEW IMPORT
import warnings

warnings.filterwarnings('ignore')

# ==========================================
# CONFIGURATION
# ==========================================
STATION_DIR = '/discover/nobackup/cmbreen/datacenters/uscrn_independent_data'
DATACENTER_CSV = '/discover/nobackup/cmbreen/datacenters/data/im3_open_source_data_center_atlas_v2026.02.09.csv'
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

# --- DEFINE CURRENT FOCUS AREAS ---
focus_areas = [
    {'lat_min': 38.5, 'lat_max': 39.5, 'lon_min': -78.0, 'lon_max': -77.0},
    {'lat_min': 32.3, 'lat_max': 33.3, 'lon_min': -97.5, 'lon_max': -96.5}
]

# ==========================================
# 3. GENERATE MAP PDF
# ==========================================
print(f"Generating Map PDF: {OUTPUT_PDF}")

with PdfPages(OUTPUT_PDF) as pdf:
    fig = plt.figure(figsize=(16, 10))
    fig.suptitle("", fontsize=18, fontweight='bold', y=0.96)

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
            
        # 2. Draw Current Focus Areas (Light Grey Boxes)
        for area in focus_areas:
            lon_min, lon_max = area['lon_min'], area['lon_max']
            lat_min, lat_max = area['lat_min'], area['lat_max']
            center_lat = (lat_min + lat_max) / 2
            center_lon = (lon_min + lon_max) / 2
            
            # Check if this box is inside the current subplot bounds
            if (x_bounds[0] <= center_lon <= x_bounds[1]) and (y_bounds[0] <= center_lat <= y_bounds[1]):
                rect = Rectangle((lon_min, lat_min), lon_max - lon_min, lat_max - lat_min, 
                                 linewidth=1.5, edgecolor='dimgrey', facecolor='lightgrey', alpha=0.5, 
                                 label='Current Focus Area' if (region == 'CONUS' and 'Current Focus Area' not in ax.get_legend_handles_labels()[1]) else "")
                ax.add_patch(rect)

        # 3. Plot EXACT Data Center Locations (Dark Grey Dots)
        ax.scatter(df_dc['lon'], df_dc['lat'], c='black', s=10, alpha=0.6, marker='o', zorder=2,
                   label='Data Center (IM3 Atlas)' if region == 'CONUS' else "")

        # 4. Plot USCRN Weather Stations (Purple Stars)
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
            # --- NEW: Format Lat/Lon Tick Labels ---
            def format_lon(val, pos):
                if val < 0:   return f"{abs(int(val))}°W"
                elif val > 0: return f"{int(val)}°E"
                else:         return "0°"
                
            def format_lat(val, pos):
                if val > 0:   return f"{int(val)}°N"
                elif val < 0: return f"{abs(int(val))}°S"
                else:         return "0°"

            ax.xaxis.set_major_formatter(FuncFormatter(format_lon))
            ax.yaxis.set_major_formatter(FuncFormatter(format_lat))
            
            # Since the labels now clearly indicate directions, you might not even 
            # need these text labels, but I left them just in case.
            ax.set_xlabel("Longitude")
            ax.set_ylabel("Latitude")

    # Final Legend Generation
    handles, labels = ax_main.get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    ax_main.legend(by_label.values(), by_label.keys(), loc='lower right', framealpha=0.9, fontsize=11, markerscale=1.5)

    pdf.savefig(fig, bbox_inches='tight')
    plt.close()

print(f"\nDone! Map created successfully and saved as {OUTPUT_PDF}.")