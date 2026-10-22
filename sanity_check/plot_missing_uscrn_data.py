import os
import glob
import numpy as np
import pandas as pd
#import matplotlib.subplots
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.lines as mlines
from matplotlib.backends.backend_pdf import PdfPages
import warnings

warnings.filterwarnings('ignore')

# ==========================================
# CONFIGURATION
# ==========================================
PROCESS_ALL_STATIONS = False

STATION_DIR = '/discover/nobackup/cmbreen/datacenters/uscrn_independent_data'
QAQC_DIR = './station_qaqc_reports' 
OUTPUT_PDF = 'missing_data_comprehensive_report.pdf'

# The universal suffix for your single missing data file
QAQC_SUFFIX = '_missing_timestamps.csv'

HEATMAP_START_YEAR = 2002
HEATMAP_END_YEAR = 2026
HEATMAP_YEARS = list(range(HEATMAP_START_YEAR, HEATMAP_END_YEAR + 1))
MAX_PER_PAGE = 10  # Maximum stations per PDF page

# Map our plot titles to the exact column names in your CSV
VARS = {
    'Temp': {'title': 'Temperature', 'col': 'temperature'},
    'RH': {'title': 'Relative Humidity', 'col': 'relative_humidity'}
}

VIEWS = [
    ('main', None, 'Timeline (2002 - 2026)'),
    ('08', 2008, 'Timeline - 2008'),
    ('09', 2009, 'Timeline - 2009'),
    ('10', 2010, 'Timeline - 2010')
]

# ==========================================
# GATHER FILES & PRE-PROCESS DATA
# ==========================================
if PROCESS_ALL_STATIONS:
    station_files = sorted([f for f in glob.glob(os.path.join(STATION_DIR, '*.csv')) 
                            if not os.path.basename(f).startswith('all_')])
else:
    station_files = sorted(glob.glob(os.path.join(STATION_DIR, 'VA_*.csv')) + \
                           glob.glob(os.path.join(STATION_DIR, 'TX_*.csv')))

print(f"Found {len(station_files)} total stations. Processing data...")

all_data = []

for stn_file in station_files:
    stn_name = os.path.basename(stn_file).replace('.csv', '')
    
    # 1. Get operational lifespan
    df_orig = pd.read_csv(stn_file, usecols=['datetime'])
    df_orig['datetime'] = pd.to_datetime(df_orig['datetime'], errors='coerce', utc=True).dt.tz_localize(None)
    start_date = df_orig['datetime'].min()
    end_date = df_orig['datetime'].max()
    total_expected_hours = (end_date - start_date).total_seconds() / 3600.0
    
    stn_record = {
        'name': stn_name,
        'start': start_date,
        'end': end_date,
        'Temp_miss': pd.DataFrame(),
        'RH_miss': pd.DataFrame(),
        'Temp_heat': {'Station': stn_name},
        'RH_heat': {'Station': stn_name}
    }
    
    # 2. Extract Missing Data from the single file
    missing_file = os.path.join(QAQC_DIR, f"{stn_name}{QAQC_SUFFIX}")
    
    if os.path.exists(missing_file):
        # Read the file
        df_miss = pd.read_csv(missing_file)
        if not df_miss.empty:
            df_miss['datetime'] = pd.to_datetime(df_miss['datetime'], errors='coerce', utc=True).dt.tz_localize(None)
            
            for vk, vinfo in VARS.items():
                col_name = vinfo['col']
                if col_name in df_miss.columns:
                    # Keep ONLY the rows where this specific variable is NaN (missing)
                    df_var_miss = df_miss[df_miss[col_name].isna()][['datetime']]
                    stn_record[f'{vk}_miss'] = df_var_miss
                else:
                    print(f" -> [WARNING] Column '{col_name}' not found in {stn_name}{QAQC_SUFFIX}")
    else:
        print(f" -> [WARNING] No QAQC file found for {stn_name}. Missing data will not be plotted.")
            
    # 3. Calculate Global Heatmap Statistics (2002 - 2026)
    for vk in VARS.keys():
        for yr in HEATMAP_YEARS:
            yr_start = pd.Timestamp(f'{yr}-01-01')
            yr_end = pd.Timestamp(f'{yr}-12-31 23:59:59')
            op_start = max(start_date, yr_start)
            op_end = min(end_date, yr_end)
            
            if op_start < op_end and total_expected_hours > 0:
                if not stn_record[f'{vk}_miss'].empty:
                    df_m = stn_record[f'{vk}_miss']
                    miss_yr = df_m[(df_m['datetime'] >= yr_start) & (df_m['datetime'] <= yr_end)]
                    miss_count = len(miss_yr['datetime'].drop_duplicates())
                else:
                    miss_count = 0
                pct_missing = (miss_count / total_expected_hours) * 100.0
            else:
                pct_missing = np.nan
                
            stn_record[f'{vk}_heat'][str(yr)] = pct_missing
            
    all_data.append(stn_record)

# ==========================================
# PLOTTING FUNCTIONS
# ==========================================
def plot_timeline_chunk(chunk, var_key, title, year=None):
    fig, ax = plt.subplots(figsize=(16, 8))
    y_ticks, stn_names = [], []
    
    for idx, stn in enumerate(chunk):
        y_ticks.append(idx)
        stn_names.append(stn['name'])
        
        # Grey Lifespan Line
        ax.plot([stn['start'], stn['end']], [idx, idx], color='lightgrey', linewidth=4, zorder=1)
        
        # Red Missing Data Ticks
        df_miss = stn[f'{var_key}_miss']
        if not df_miss.empty:
            if year:
                df_miss = df_miss[df_miss['datetime'].dt.year == year]
            
            if not df_miss.empty:
                ax.plot(df_miss['datetime'], [idx] * len(df_miss), 
                        marker='|', color='red', markersize=14, linestyle='None', zorder=2)

    ax.set_yticks(y_ticks)
    ax.set_yticklabels(stn_names, fontsize=10)
    ax.invert_yaxis() # Put Station 1 at the top of the page
    
    ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
    ax.set_xlabel("Time", fontsize=12, fontweight='bold')
    
    if year:
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
    ax.legend(handles=[grey_line, red_tick], loc='upper right', bbox_to_anchor=(1.0, 1.05))
    ax.grid(axis='x', linestyle='--', alpha=0.6)
    ax.set_axisbelow(True)
    
    fig.tight_layout()
    return fig

def plot_heatmap_chunk(chunk, var_key, var_title):
    fig, ax = plt.subplots(figsize=(18, 8))
    df_heat = pd.DataFrame([stn[f'{var_key}_heat'] for stn in chunk]).set_index('Station')
    
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
    ax.set_title(f"Missing {var_title} Percentage ({HEATMAP_START_YEAR}-{HEATMAP_END_YEAR})", 
                 fontsize=16, fontweight='bold', pad=20)
    
    for i in range(len(df_heat.index)):
        for j in range(len(df_heat.columns)):
            val = data[i, j]
            if not np.isnan(val) and val > 0:
                text = f"{val:.3f}%"
                color = "white" if val > (np.nanmax(data) / 2) else "black"
                ax.text(j, i, text, ha="center", va="center", color=color, fontsize=8)
                
    fig.tight_layout()
    return fig

# ==========================================
# GENERATE MULTIPAGE PDF
# ==========================================
print("Saving pages to PDF...")
with PdfPages(OUTPUT_PDF) as pdf:
    chunks = [all_data[i:i + MAX_PER_PAGE] for i in range(0, len(all_data), MAX_PER_PAGE)]
    
    for vk, vinfo in VARS.items():
        # Timelines
        for view_key, year, title_suffix in VIEWS:
            for page_num, chunk in enumerate(chunks, 1):
                title = f"Missing {vinfo['title']} {title_suffix} (Page {page_num}/{len(chunks)})"
                fig = plot_timeline_chunk(chunk, vk, title, year)
                pdf.savefig(fig)
                plt.close(fig)
                
        # Heatmaps
        for page_num, chunk in enumerate(chunks, 1):
            title = f"{vinfo['title']} Heatmap (Page {page_num}/{len(chunks)})"
            fig = plot_heatmap_chunk(chunk, vk, title)
            pdf.savefig(fig)
            plt.close(fig)

print(f"Done! Report saved to {OUTPUT_PDF}.")