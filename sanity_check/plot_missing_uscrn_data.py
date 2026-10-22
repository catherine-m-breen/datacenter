import os
import glob
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.lines as mlines
from matplotlib.backends.backend_pdf import PdfPages
import warnings

warnings.filterwarnings('ignore')

# ==========================================
# CONFIGURATION
# ==========================================
PROCESS_ALL_STATIONS = True  # Set to False to only plot VA & TX stations

STATION_DIR = '/discover/nobackup/cmbreen/datacenters/uscrn_independent_data'
QAQC_DIR = './station_qaqc_reports'
OUTPUT_PDF = 'missing_data_comprehensive_report.pdf'

# Configure how the script finds your separated QAQC files
TEMP_QAQC_SUFFIX = '_missing_temp.csv'
RH_QAQC_SUFFIX = '_missing_rh.csv'

# NLDAS-3 Temporal Range for the Heatmap
NLDAS_START_YEAR = 2002
NLDAS_END_YEAR = 2026
NLDAS_YEARS = list(range(NLDAS_START_YEAR, NLDAS_END_YEAR + 1))

# Define variables to loop over
VARS = {
    'Temp': {'title': 'Temperature', 'suffix': TEMP_QAQC_SUFFIX},
    'RH': {'title': 'Relative Humidity', 'suffix': RH_QAQC_SUFFIX}
}

# ==========================================
# GATHER FILES & SETUP
# ==========================================
if PROCESS_ALL_STATIONS:
    station_files = sorted([f for f in glob.glob(os.path.join(STATION_DIR, '*.csv')) 
                            if not os.path.basename(f).startswith('all_')])
else:
    station_files = sorted(glob.glob(os.path.join(STATION_DIR, 'VA_*.csv')) + \
                           glob.glob(os.path.join(STATION_DIR, 'TX_*.csv')))

print(f"Found {len(station_files)} total stations to plot.")
print(f"Generating comprehensive plots: {OUTPUT_PDF}")

fig_height = max(6, len(station_files) * 0.4)

# Dictionary to hold all figures, axes, and heatmap data for Temp and RH
plots = {}
for vk in VARS.keys():
    plots[vk] = {
        'main': plt.subplots(figsize=(16, fig_height)),
        '08': plt.subplots(figsize=(16, fig_height)),
        '09': plt.subplots(figsize=(16, fig_height)),
        '10': plt.subplots(figsize=(16, fig_height)),
        'heat_data': []
    }

station_names = []
y_ticks = []

# ==========================================
# PROCESS DATA
# ==========================================
for idx, stn_file in enumerate(station_files):
    stn_name = os.path.basename(stn_file).replace('.csv', '')
    station_names.append(stn_name)
    y_ticks.append(idx)
    
    # 1. Get total operational lifespan from the original file
    df_orig = pd.read_csv(stn_file, usecols=['datetime'])
    df_orig['datetime'] = pd.to_datetime(df_orig['datetime'], errors='coerce', utc=True).dt.tz_localize(None)
    start_date = df_orig['datetime'].min()
    end_date = df_orig['datetime'].max()
    
    # Calculate TOTAL expected operating hours across all years
    total_expected_hours = (end_date - start_date).total_seconds() / 3600.0
    
    for vk, vinfo in VARS.items():
        # Plot grey background lines on all timelines for this variable
        for view in ['main', '08', '09', '10']:
            ax = plots[vk][view][1]
            ax.plot([start_date, end_date], [idx, idx], color='lightgrey', linewidth=4, zorder=1)
        
        # 2. Look for the separated missing timestamps file
        missing_file = os.path.join(QAQC_DIR, f"{stn_name}{vinfo['suffix']}")
        df_miss = pd.DataFrame()
        
        if os.path.exists(missing_file):
            df_miss = pd.read_csv(missing_file, usecols=['datetime'])
            if not df_miss.empty:
                df_miss['datetime'] = pd.to_datetime(df_miss['datetime'], errors='coerce', utc=True).dt.tz_localize(None)
                
                # Plot main red ticks
                plots[vk]['main'][1].plot(df_miss['datetime'], [idx] * len(df_miss), 
                                          marker='|', color='red', markersize=12, linestyle='None', zorder=2)
                
                # Plot zoom red ticks
                for yr, view in zip([2008, 2009, 2010], ['08', '09', '10']):
                    df_miss_yr = df_miss[df_miss['datetime'].dt.year == yr]
                    if not df_miss_yr.empty:
                        plots[vk][view][1].plot(df_miss_yr['datetime'], [idx] * len(df_miss_yr), 
                                                marker='|', color='red', markersize=12, linestyle='None', zorder=2)
        else:
            print(f" -> [WARNING] No {vk} QAQC file found for {stn_name}. Missing data will not be plotted.")
        
        # 3. Calculate Global NLDAS Heatmap Statistics
        heat_record = {'Station': stn_name}
        for yr in NLDAS_YEARS:
            yr_start = pd.Timestamp(f'{yr}-01-01')
            yr_end = pd.Timestamp(f'{yr}-12-31 23:59:59')
            
            # Was the station operating during this year?
            op_start = max(start_date, yr_start)
            op_end = min(end_date, yr_end)
            
            if op_start < op_end and total_expected_hours > 0:
                if not df_miss.empty:
                    # Count missing hours in THIS year
                    miss_yr = df_miss[(df_miss['datetime'] >= yr_start) & (df_miss['datetime'] <= yr_end)]
                    miss_count = len(miss_yr['datetime'].drop_duplicates())
                else:
                    miss_count = 0
                
                # DIVIDE BY THE TOTAL EXPECTED HOURS ACROSS ALL YEARS
                pct_missing = (miss_count / total_expected_hours) * 100.0
            else:
                # Station not built yet, or decommissioned (will appear grey)
                pct_missing = np.nan
                
            heat_record[str(yr)] = pct_missing
            
        plots[vk]['heat_data'].append(heat_record)

# ==========================================
# FORMATTING TIMELINE PLOTS
# ==========================================
def format_axis(ax, title, is_zoom=False, year=None):
    ax.set_yticks(y_ticks)
    ax.set_yticklabels(station_names, fontsize=10)
    ax.set_title(title, fontsize=18, fontweight='bold', pad=20)
    ax.set_xlabel("Time", fontsize=12, fontweight='bold')
    
    if is_zoom and year:
        ax.set_xlim(pd.Timestamp(f'{year}-01-01'), pd.Timestamp(f'{year}-12-31'))
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b'))
    else:
        ax.set_xlim(pd.Timestamp('2002-01-01'), pd.Timestamp('2026-12-31'))
        ax.xaxis.set_major_locator(mdates.YearLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    
    plt.setp(ax.get_xticklabels(), rotation=45, ha='right')
    
    grey_line = mlines.Line2D([], [], color='lightgrey', linewidth=4, label='Station Operating')
    red_tick = mlines.Line2D([], [], color='red', marker='|', linestyle='None', markersize=12, label='Missing Hourly Data')
    ax.legend(handles=[grey_line, red_tick], loc='upper right', bbox_to_anchor=(1.0, 1.05), framealpha=1.0)
    
    ax.grid(axis='x', linestyle='--', alpha=0.6)
    ax.set_axisbelow(True)

for vk, vinfo in VARS.items():
    format_axis(plots[vk]['main'][1], f"Missing {vinfo['title']} Timeline (2002 - 2026)")
    format_axis(plots[vk]['08'][1], f"Missing {vinfo['title']} Timeline - 2008", is_zoom=True, year=2008)
    format_axis(plots[vk]['09'][1], f"Missing {vinfo['title']} Timeline - 2009", is_zoom=True, year=2009)
    format_axis(plots[vk]['10'][1], f"Missing {vinfo['title']} Timeline - 2010", is_zoom=True, year=2010)

# ==========================================
# FORMATTING GLOBAL HEATMAPS
# ==========================================
def generate_heatmap(heatmap_data, var_title):
    df_heat = pd.DataFrame(heatmap_data).set_index('Station')
    # Use a wider figure because we are plotting ~48 years
    fig, ax = plt.subplots(figsize=(24, fig_height))
    
    data = df_heat.values
    data_masked = np.ma.masked_invalid(data)
    
    cmap = plt.cm.Reds
    cmap.set_bad(color='lightgrey')
    
    cax = ax.imshow(data_masked, cmap=cmap, aspect='auto')
    cbar = fig.colorbar(cax, ax=ax)
    cbar.set_label('% Missing (vs TOTAL Station Lifespan)', rotation=270, labelpad=15)
    
    ax.set_yticks(range(len(df_heat.index)))
    ax.set_yticklabels(df_heat.index, fontsize=10)
    ax.set_xticks(range(len(df_heat.columns)))
    ax.set_xticklabels(df_heat.columns, fontsize=10, rotation=90)
    ax.set_title(f"Missing {var_title} Percentage (NLDAS-3: {NLDAS_START_YEAR}-{NLDAS_END_YEAR})", 
                 fontsize=18, fontweight='bold', pad=20)
    
    # Annotate with percentages
    for i in range(len(df_heat.index)):
        for j in range(len(df_heat.columns)):
            val = data[i, j]
            if not np.isnan(val) and val > 0:
                text = f"{val:.3f}%"
                color = "white" if val > (np.nanmax(data) / 2) else "black"
                # Font is small (6) to fit inside the narrow 48-year grid
                ax.text(j, i, text, ha="center", va="center", color=color, fontsize=6)
                
    fig.tight_layout()
    return fig

heat_fig_temp = generate_heatmap(plots['Temp']['heat_data'], "Temperature")
heat_fig_rh = generate_heatmap(plots['RH']['heat_data'], "Relative Humidity")

# ==========================================
# SAVE TO MULTIPAGE PDF
# ==========================================
print("Saving pages to PDF...")
with PdfPages(OUTPUT_PDF) as pdf:
    for vk in VARS.keys():
        for view in ['main', '08', '09', '10']:
            plots[vk][view][0].tight_layout()
            pdf.savefig(plots[vk][view][0])
            
    pdf.savefig(heat_fig_temp)
    pdf.savefig(heat_fig_rh)

plt.close('all')
print(f"Done! Saved 10-page report to {OUTPUT_PDF}.")