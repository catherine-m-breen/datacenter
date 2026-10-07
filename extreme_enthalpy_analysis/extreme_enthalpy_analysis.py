# import os
# import warnings
# import xarray as xr
# import pandas as pd
# import numpy as np
# from scipy.stats import linregress

# # CRITICAL FOR SLURM: Set backend before importing pyplot
# import matplotlib
# matplotlib.use('Agg') 
# import matplotlib.pyplot as plt

# # Suppress annoying slice/nan warnings for a clean SLURM .out log
# warnings.filterwarnings('ignore')

# # ==========================================
# # 1. LOAD DATA
# # ==========================================
# print("Loading datasets...")
# va_zarr = '/discover/nobackup/cmbreen/datacenters/virginia_enthalpy_stacked.zarr'
# tx_zarr = '/discover/nobackup/cmbreen/datacenters/texas_enthalpy_stacked.zarr'

# # Use absolute path to ensure SLURM finds it regardless of launch directory
# locations_csv = '~/INNOVATE/im3_open_source_data_center_atlas_v2026.02.09.csv'
# output_pdf = '/discover/nobackup/cmbreen/datacenters/output_pdfs/Extreme_Enthalpy_Trends.pdf'

# va_ts = xr.open_dataset(va_zarr, engine='zarr')
# tx_ts = xr.open_dataset(tx_zarr, engine='zarr')
# locations_df = pd.read_csv(locations_csv)

# target_quantile = 0.90
# seasons_map = {'DJF': 'Winter', 'MAM': 'Spring', 'JJA': 'Summer', 'SON': 'Fall'}
# season_keys = list(seasons_map.keys())

# # ==========================================
# # 2. EXTRACT DATACENTER LOCATIONS & VARIABLES
# # ==========================================
# def get_dc_coords(ds, df):
#     min_lon, max_lon = ds.lon.min().item(), ds.lon.max().item()
#     min_lat, max_lat = ds.lat.min().item(), ds.lat.max().item()
    
#     mask = (df['lon'] >= min_lon) & (df['lon'] <= max_lon) & \
#            (df['lat'] >= min_lat) & (df['lat'] <= max_lat)
#     state_df = df[mask]
    
#     lons = xr.DataArray(state_df['lon'].values, dims='points')
#     lats = xr.DataArray(state_df['lat'].values, dims='points')
    
#     return lons, lats, len(state_df)

# va_lons, va_lats, va_count = get_dc_coords(va_ts, locations_df)
# tx_lons, tx_lats, tx_count = get_dc_coords(tx_ts, locations_df)

# print(f"Number of Virginia data centers: {va_count}")
# print(f"Number of Texas data centers: {tx_count}")

# print("Extracting variables via nearest neighbor...")
# # Extract violations
# va_dc_hot = va_ts['crossed_seasonal_hot'].sel(lon=va_lons, lat=va_lats, method='nearest')
# tx_dc_hot = tx_ts['crossed_seasonal_hot'].sel(lon=tx_lons, lat=tx_lats, method='nearest')

# # Extract temperatures
# va_dc_temp = va_ts['Tair'].sel(lon=va_lons, lat=va_lats, method='nearest')
# tx_dc_temp = tx_ts['Tair'].sel(lon=tx_lons, lat=tx_lats, method='nearest')

# # ==========================================
# # 3. HELPER FUNCTIONS
# # ==========================================
# def get_yearly_violations_dc(dc_ts, quantile, season_str):
#     """Returns the raw count of total data center violation days per year."""
#     q_ts = dc_ts.sel(quantile=quantile)
#     season_ts = q_ts.where(q_ts['time'].dt.season == season_str, drop=True)
    
#     daily_actual = season_ts.sum(dim='points')
#     yearly_actual = daily_actual.groupby('time.year').sum().to_pandas()
    
#     return yearly_actual.loc[2002:2023]

# def get_yearly_avg_temp(dc_temp, season_str):
#     season_ts = dc_temp.where(dc_temp['time'].dt.season == season_str, drop=True)
#     yearly_temp = season_ts.mean(dim='points').groupby('time.year').mean().to_pandas()
#     return yearly_temp.loc[2002:2023]

# # ==========================================
# # 4. PLOT 2x4 GRID (Row 0: VA, Row 1: TX)
# # ==========================================
# print("Generating trend plots...")
# fig, axes = plt.subplots(2, 4, figsize=(20, 8), sharex=True)
# colors = {'Virginia': '#1f77b4', 'Texas': '#ff7f0e'}  
# temp_colors = {'Virginia': 'grey', 'Texas': 'grey'} 

# for col_idx, season_key in enumerate(season_keys):
#     season_name = seasons_map[season_key]
    
#     # ================= ROW 0: VIRGINIA =================
#     ax_va = axes[0, col_idx]
#     va_counts = get_yearly_violations_dc(va_dc_hot, target_quantile, season_key)
    
#     # Calculate percentage dynamically using va_count
#     va_pct = (va_counts.values) / (va_count * 90) * 100
    
#     ax_va.bar(va_counts.index, va_pct, alpha=0.5, color=colors['Virginia'], edgecolor='black', label=f'VA (n={va_count})')
    
#     if len(va_counts) > 1 and va_counts.sum() > 0:
#         slope, intercept, r_value, p_value, std_err = linregress(va_counts.index, va_pct)
#         sig_marker = '*' if p_value < 0.05 else ''
#         trend_label = f'Trend (p={p_value:.3f}){sig_marker}'
#         ax_va.plot(va_counts.index, intercept + slope * va_counts.index, color='#08519c', linestyle='--', linewidth=1.5, label=trend_label)
        
#     ax2_va = ax_va.twinx()
#     va_temp = get_yearly_avg_temp(va_dc_temp, season_key)
#     ax2_va.plot(va_temp.index, va_temp.values, color=temp_colors['Virginia'], marker='.', linestyle='-', linewidth=2, label='VA Avg Temp')
    
#     ax_va.set_title(f'Virginia - {season_name} (Q={target_quantile})', fontsize=14)
#     ax_va.grid(axis='y', linestyle='--', alpha=0.7)
    
#     # ================= ROW 1: TEXAS =================
#     ax_tx = axes[1, col_idx]
#     tx_counts = get_yearly_violations_dc(tx_dc_hot, target_quantile, season_key)
    
#     # Calculate percentage dynamically using tx_count
#     tx_pct = (tx_counts.values) / (tx_count * 90) * 100
    
#     ax_tx.bar(tx_counts.index, tx_pct, alpha=0.5, color=colors['Texas'], edgecolor='black', label=f'TX (n={tx_count})')
    
#     if len(tx_counts) > 1 and tx_counts.sum() > 0:
#         slope_tx, intercept_tx, r_value_tx, p_value_tx, std_err_tx = linregress(tx_counts.index, tx_pct)
#         sig_marker_tx = '*' if p_value_tx < 0.05 else ''
#         trend_label_tx = f'Trend (p={p_value_tx:.3f}){sig_marker_tx}'
#         ax_tx.plot(tx_counts.index, intercept_tx + slope_tx * tx_counts.index, color='#a63603', linestyle='--', linewidth=1.5, label=trend_label_tx)
        
#     ax2_tx = ax_tx.twinx()
#     tx_temp = get_yearly_avg_temp(tx_dc_temp, season_key)
#     ax2_tx.plot(tx_temp.index, tx_temp.values, color=temp_colors['Texas'], marker='.', linestyle='-', linewidth=2, label='TX Avg Temp')
    
#     ax_tx.set_title(f'Texas - {season_name} (Q={target_quantile})', fontsize=14)
#     ax_tx.grid(axis='y', linestyle='--', alpha=0.7)
#     ax_tx.set_xlabel(' ', fontsize=14)

#     # ================= LABELS & LEGENDS =================
#     # Primary Y-labels (Left)
#     if col_idx == 0:
#         ax_va.set_ylabel('Extreme Enthalpy Occurence (%)', fontsize=14)
#         ax_tx.set_ylabel('Extreme Enthalpy Occurence (%)', fontsize=14)        
    
#     # Secondary Y-labels (Right)
#     if col_idx == 3:
#         ax2_va.set_ylabel('Avg Temp (°C)', fontsize=14)
#         ax2_tx.set_ylabel('Avg Temp (°C)', fontsize=14)
#         ax2_va.set_ylim(-10,35)
#         ax2_tx.set_ylim(-10,35)
#     else:
#         ax2_va.set_yticklabels([])
#         ax2_tx.set_yticklabels([])
#         ax2_va.set_ylim(-10,35)
#         ax2_tx.set_ylim(-10,35)
        
#     # Legends
#     lines_1, labels_1 = ax_va.get_legend_handles_labels()
#     lines_2, labels_2 = ax2_va.get_legend_handles_labels()

#     ax_va.set_ylim(0,30) 
#     ax_va.legend(lines_1 + lines_2, labels_1 + labels_2, loc='upper left', fontsize=9)
    
#     lines_3, labels_3 = ax_tx.get_legend_handles_labels()
#     lines_4, labels_4 = ax2_tx.get_legend_handles_labels()
#     ax_tx.legend(lines_3 + lines_4, labels_3 + labels_4, loc='upper left', fontsize=9)

#     ax_tx.set_ylim(0,30) 
#     ax_tx.set_xlim(2001.5, 2023.5)
#     ax_tx.set_xticks([2002, 2007, 2012, 2017, 2022])
    
#     ax_va.tick_params(axis='both', which='major', labelsize=12, length=6, width=2)
#     ax2_va.tick_params(axis='both', which='major', labelsize=12, length=6, width=2)
#     ax_tx.tick_params(axis='both', which='major', labelsize=12, length=6, width=2)
#     ax2_tx.tick_params(axis='both', which='major', labelsize=12, length=6, width=2)

# plt.tight_layout()

# # Ensure output directory exists and save
# os.makedirs(os.path.dirname(output_pdf), exist_ok=True)
# plt.savefig(output_pdf, bbox_inches='tight', dpi=150)
# plt.close()

# print(f"Success! Plot saved to: {output_pdf}")
import os
import numpy as np
import pandas as pd
import xarray as xr
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from scipy.stats import linregress

# ==========================================
# 1. LOAD DATA
# ==========================================
print("Loading datasets...")

va_nc = '/discover/nobackup/cmbreen/datacenters/virginia_hourly/va_Daily_DayNight_Summary_CORRECTED.nc'
tx_nc = '/discover/nobackup/cmbreen/datacenters/texas_hourly/tx_Daily_DayNight_Summary_CORRECTED.nc'

# Use absolute path to ensure SLURM finds it
locations_csv = '~/INNOVATE/im3_open_source_data_center_atlas_v2026.02.09.csv'
output_pdf = '/discover/nobackup/cmbreen/datacenters/output_pdfs/Extreme_Enthalpy_Trends.pdf'

va_ts = xr.open_dataset(va_nc)
tx_ts = xr.open_dataset(tx_nc)
locations_df = pd.read_csv(locations_csv)

target_quantiles = [0.90, 0.95, 0.99]
seasons_map = {'DJF': 'Winter', 'MAM': 'Spring', 'JJA': 'Summer', 'SON': 'Fall'}
season_keys = list(seasons_map.keys())

# ==========================================
# 2. EXTRACT DATACENTER LOCATIONS
# ==========================================
def get_dc_coords(ds, df):
    min_lon, max_lon = ds.lon.min().item(), ds.lon.max().item()
    min_lat, max_lat = ds.lat.min().item(), ds.lat.max().item()
    
    mask = (df['lon'] >= min_lon) & (df['lon'] <= max_lon) & \
           (df['lat'] >= min_lat) & (df['lat'] <= max_lat)
    state_df = df[mask]
    
    lons = xr.DataArray(state_df['lon'].values, dims='points')
    lats = xr.DataArray(state_df['lat'].values, dims='points')
    
    return lons, lats, len(state_df)

va_lons, va_lats, va_count = get_dc_coords(va_ts, locations_df)
tx_lons, tx_lats, tx_count = get_dc_coords(tx_ts, locations_df)

print(f"Number of Virginia data centers: {va_count}")
print(f"Number of Texas data centers: {tx_count}")

print("Extracting variables via nearest neighbor...")
# Extract all variables for just the data center locations
va_pts = va_ts.sel(lon=va_lons, lat=va_lats, method='nearest')
tx_pts = tx_ts.sel(lon=tx_lons, lat=tx_lats, method='nearest')

# ==========================================
# 3. PLOT MULTI-PAGE PDF
# ==========================================
print("Generating trend plots into Multi-Page PDF...")

os.makedirs(os.path.dirname(output_pdf), exist_ok=True)

colors = {'Virginia': '#1f77b4', 'Texas': '#ff7f0e'}  
trend_colors = {'Virginia': '#08519c', 'Texas': '#a63603'} 

states_data = [
    ('Virginia', va_pts, va_count),
    ('Texas', tx_pts, tx_count)
]

with PdfPages(output_pdf) as pdf:
    # 1. Outer Loop: State
    for state_name, ds_pts, dc_count in states_data:
        # 2. Inner Loop: Quantile (90, 95, 99)
        for q in target_quantiles:
            
            # Create a 2x4 Grid per State-Quantile combination
            fig, axes = plt.subplots(2, 4, figsize=(20, 10), sharex=False) # Turned off sharex to handle dynamic years better
            fig.suptitle(f'{state_name} Extreme Enthalpy Trends - Quantile: {q}', fontsize=20, y=0.98, fontweight='bold')
            
            # Row 0: Daytime, Row 1: Nighttime
            for row_idx, tod_prefix in enumerate(['DayTime', 'NightTime']):
                
                # Identify variable names dynamically based on your NetCDF schema
                enthalpy_var = f"{tod_prefix}_Avg_enthalpy"
                threshold_var = f"{tod_prefix}_Avg_enthalpy_thresholds"
                temp_var = f"{tod_prefix}_Avg_Tair"
                
                # Check where Enthalpy > Threshold for the specific quantile
                thresholds_q = ds_pts[threshold_var].sel(quantile=q)
                violations = (ds_pts[enthalpy_var] > thresholds_q).astype(int)
                
                for col_idx, season_key in enumerate(season_keys):
                    ax = axes[row_idx, col_idx]
                    season_name = seasons_map[season_key]
                    
                    # Filter to current season
                    season_mask = violations['time'].dt.season == season_key
                    season_violations = violations.where(season_mask, drop=True)
                    season_temp = ds_pts[temp_var].where(season_mask, drop=True)
                    
                    # Aggregate to yearly summaries
                    daily_actual = season_violations.sum(dim='points')
                    counts = daily_actual.groupby('time.year').sum().to_pandas()
                    time_steps = season_violations['time'].groupby('time.year').count().to_pandas()
                    temp_vals = season_temp.mean(dim='points').groupby('time.year').mean().to_pandas()
                    
                    # Dynamic percentage: (Total Violations) / (Number of DCs * Available Timesteps) * 100
                    if len(time_steps) > 0:
                        pct = (counts.values / (dc_count * time_steps.values)) * 100
                    else:
                        pct = np.zeros_like(counts.values)
                    
                    # Plot primary bar chart
                    ax.bar(counts.index, pct, alpha=0.5, color=colors[state_name], edgecolor='black', label=f'{state_name} (n={dc_count})')
                    
                    # Plot trendline
                    if len(counts) > 1 and counts.sum() > 0:
                        slope, intercept, r_value, p_value, std_err = linregress(counts.index, pct)
                        sig_marker = '*' if p_value < 0.05 else ''
                        trend_label = f'Trend (p={p_value:.3f}){sig_marker}'
                        ax.plot(counts.index, intercept + slope * counts.index, color=trend_colors[state_name], linestyle='--', linewidth=1.5, label=trend_label)
                        
                    # Plot secondary Temperature line
                    ax2 = ax.twinx()
                    ax2.plot(temp_vals.index, temp_vals.values, color='grey', marker='.', linestyle='-', linewidth=2, label='Avg Temp')
                    
                    # Titles and grids
                    tod_label = 'Daytime' if row_idx == 0 else 'Nighttime'
                    ax.set_title(f'{season_name} - {tod_label}', fontsize=14)
                    ax.grid(axis='y', linestyle='--', alpha=0.7)
                    
                    # Y-Axis Scaling 
                    max_pct = pct.max() if len(pct) > 0 and not np.isnan(pct.max()) else 10
                    ax.set_ylim(0, max(max_pct * 1.3, 5)) 

                    # Y-Labels Formatting
                    if col_idx == 0:
                        ax.set_ylabel('Extreme Enthalpy Occurence (%)', fontsize=14)
                    if col_idx == 3:
                        ax2.set_ylabel('Avg Temp (°C)', fontsize=14)
                        ax2.set_ylim(-10, 35)
                    else:
                        ax2.set_yticklabels([])
                        ax2.set_ylim(-10, 35)
                        
                    # Legends
                    lines_1, labels_1 = ax.get_legend_handles_labels()
                    lines_2, labels_2 = ax2.get_legend_handles_labels()
                    ax.legend(lines_1 + lines_2, labels_1 + labels_2, loc='upper left', fontsize=9)
                    
                    # X-Axis formatting (Bottom row only)
                    if row_idx == 1:
                        min_yr, max_yr = int(counts.index.min()), int(counts.index.max())
                        ax.set_xlim(min_yr - 0.5, max_yr + 0.5)
                        # Set a tick every 5 years dynamically based on your data length
                        ax.set_xticks(range(min_yr, max_yr + 1, 5))
                        ax.set_xlabel('Year', fontsize=14)
                    else:
                        # Hide x-axis labels for the top row to make it cleaner
                        ax.set_xticklabels([])
                        
                    ax.tick_params(axis='both', which='major', labelsize=12, length=6, width=2)
                    ax2.tick_params(axis='both', which='major', labelsize=12, length=6, width=2)

            plt.tight_layout(rect=[0, 0, 1, 0.96])
            
            # Save this state-quantile grid as a single page in the PDF
            pdf.savefig(fig, bbox_inches='tight', dpi=150)
            plt.close(fig)

print(f"Success! 6-Page Multi-panel PDF saved to: {output_pdf}")