import xarray as xr
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg') # Crucial for running on NCCS Discover without a display
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.dates as mdates
from matplotlib.ticker import FuncFormatter
from matplotlib.gridspec import GridSpec
from matplotlib.backends.backend_pdf import PdfPages
import warnings
import os
warnings.filterwarnings('ignore') # Suppress nan/slice warnings for cleaner logs

# ==========================================
# 0. CACHE FOR LIGHTNING-FAST ASHRAE CHARTS
# ==========================================
SEASONAL_BG_CACHE = {}

def get_precomputed_ashrae_background(nc_path, target_date_str):
    """Calculates and caches the 2D histogram of statewide seasonal norms to avoid loop overhead."""
    target_date = pd.to_datetime(target_date_str)
    # Determine the season
    season_code = 'DJF' if target_date.month in [12, 1, 2] else 'MAM' if target_date.month in [3, 4, 5] else 'JJA' if target_date.month in [6, 7, 8] else 'SON'
    cache_key = (nc_path, season_code)

    if cache_key not in SEASONAL_BG_CACHE:
        print(f"    -> [Cache Miss] Pre-computing {season_code} ASHRAE background (Runs ONLY ONCE per state/season!)")
        
        with xr.open_dataset(nc_path) as ds:
            ds_season = ds.isel(time=(ds['time'].dt.season == season_code))
            
            # Flatten once
            day_t = ds_season['DayTime_Avg_Tair'].values.flatten()
            day_q = ds_season['DayTime_Avg_Qair'].values.flatten()
            day_p = ds_season['DayTime_Avg_PSurf'].values.flatten()
            night_t = ds_season['NightTime_Avg_Tair'].values.flatten()
            night_q = ds_season['NightTime_Avg_Qair'].values.flatten()
            night_p = ds_season['NightTime_Avg_PSurf'].values.flatten()
        
        day_rh = calc_rh(day_t, day_q, day_p)
        night_rh = calc_rh(night_t, night_q, night_p)
        
        # Filter out NaNs
        d_valid = np.isfinite(day_t) & np.isfinite(day_rh)
        n_valid = np.isfinite(night_t) & np.isfinite(night_rh)
        
        # PRE-COMPUTE THE 2D HISTOGRAMS (This is what was slowing you down)
        bins = [50, 50]
        rng = [[-15, 50], [0, 100]]
        
        day_H, xedges, yedges = np.histogram2d(day_t[d_valid], day_rh[d_valid], bins=bins, range=rng)
        night_H, _, _ = np.histogram2d(night_t[n_valid], night_rh[n_valid], bins=bins, range=rng)
        
        SEASONAL_BG_CACHE[cache_key] = {
            'day_H': day_H, 'night_H': night_H, 
            'xedges': xedges, 'yedges': yedges
        }
        
    return SEASONAL_BG_CACHE[cache_key]

# ==========================================
# 1. REFACTORED PLOTTING FUNCTIONS 
# ==========================================

def plot_datacenter_heat_map_tx(ax, dc_id, target_date, df, ds_path):
    target_dc = df[df['id'] == dc_id]
    if target_dc.empty: return
        
    target_lat, target_lon = target_dc['lat'].values[0], target_dc['lon'].values[0]
    target_operator = target_dc['operator'].values[0]
    if pd.isna(target_operator): target_operator = f"Datacenter {dc_id}"

    state_abb = target_dc['state_abb'].values[0]
    state_dcs = df[df['state_abb'] == state_abb]
    
    aws_operators = ['Amazon Web Services', 'AWS', 'Amazon']
    aws_dcs = state_dcs[state_dcs['operator'].isin(aws_operators)]
    non_aws_dcs = state_dcs[~state_dcs['operator'].isin(aws_operators)]

    ds = xr.open_dataset(ds_path)
    try:
        day_temp = ds.sel(time=target_date)['DayTime_Avg_Tair']
    except KeyError:
        ds.close()
        return

    ax.set_title(f"Infrastructure & Heat ({target_date})", fontsize=12, fontweight='bold')

    temp_plot = ax.pcolormesh(ds.lon, ds.lat, day_temp, cmap='YlOrRd', shading='auto', alpha=0.85)
    cbar = plt.colorbar(temp_plot, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label('Avg Daytime Temp (°C)', fontsize=10)

    ax.scatter(non_aws_dcs['lon'], non_aws_dcs['lat'], c='grey', s=20, alpha=0.7, edgecolor='whitesmoke', linewidth=0.5, zorder=3)
    ax.scatter(aws_dcs['lon'], aws_dcs['lat'], c='black', s=40, marker='^', edgecolor='white', linewidth=0.8, zorder=4)

    box_size = 0.08 
    highlight_box = patches.Rectangle(
        (target_lon - (box_size / 2), target_lat - (box_size / 2)), 
        box_size, box_size, linewidth=2.5, edgecolor='purple', facecolor='none', zorder=6
    )
    ax.add_patch(highlight_box)

    def format_lon(x, pos): return f"{abs(x):g}°W" if x < 0 else f"{x:g}°E"
    def format_lat(x, pos): return f"{x:g}°N" if x > 0 else f"{abs(x):g}°S"
    ax.xaxis.set_major_formatter(FuncFormatter(format_lon))
    ax.yaxis.set_major_formatter(FuncFormatter(format_lat))
    ax.tick_params(axis='both', labelsize=8)

    ax.set_xlim(ds.lon.min().values, ds.lon.max().values)
    ax.set_ylim(ds.lat.min().values, ds.lat.max().values)
    ax.grid(True, linestyle=':', color='black', alpha=0.3, zorder=1)
    ds.close()

def plot_failure_event_with_baselines(axes, ds_path, thresh_path, target_date_str, dc_id, df):
    ax1, ax2, ax3 = axes
    dc_info = df[df['id'] == dc_id]
    if dc_info.empty: return
    dc_lat, dc_lon = dc_info['lat'].values[0], dc_info['lon'].values[0]

    target_date = pd.to_datetime(target_date_str)
    start_date = target_date - pd.Timedelta(days=14)
    end_date = target_date + pd.Timedelta(days=3)
    month_str = target_date.strftime('%Y-%m')

    ds = xr.open_dataset(ds_path)
    point_ds = ds.sel(lat=dc_lat, lon=dc_lon, method='nearest')
    event_data = point_ds.sel(time=slice(start_date, end_date))
    times = event_data.time.values

    ds_thresh = xr.open_dataset(thresh_path)
    monthly_thresh = ds_thresh.sel(lat=dc_lat, lon=dc_lon, quantile=0.90, method='nearest').sel(time=month_str).mean(dim='time')
    
    day_thresh_val = monthly_thresh.DayTime_Avg_enthalpy_thresholds.values
    night_thresh_val = monthly_thresh.NightTime_Avg_enthalpy_thresholds.values

   # Temp
    ax1.plot(times, event_data.DayTime_Avg_Tair, label='Day Avg', color='darkorange', linewidth=2)
    ax1.plot(times, event_data.DayTime_Tair_max, label='Day Max', color='firebrick', linestyle='--', alpha=0.4)
    ax1.plot(times, event_data.NightTime_Avg_Tair, label='Night Avg', color='purple', linewidth=2)
    ax1.plot(times, event_data.NightTime_Tair_max, label='Night Max', color='indigo', linestyle='--', alpha=0.4)
    ax1.set_ylabel('Temp (°C)', fontsize=9)
    ax1.set_title('Daily Build-up (14 Days Prior)', fontsize=12, fontweight='bold')
    ax1.legend(loc='upper left', ncol=2, fontsize=7)
    ax1.set_ylim(10, 50)
    #ax1.set_xlim(times[0], times[-1]) # Locks X-axis tight to the data window
    ax1.grid(True, alpha=0.3)

    # Enthalpy
    ax2.axhline(day_thresh_val, color='firebrick', linestyle='-.', linewidth=1.5, label='90th Pct (Day)')
    ax2.axhline(night_thresh_val, color='indigo', linestyle='-.', linewidth=1.5, label='90th Pct (Night)')
    ax2.plot(times, event_data.DayTime_Avg_enthalpy, color='darkorange', linewidth=2)
    ax2.plot(times, event_data.NightTime_Avg_enthalpy, color='purple', linewidth=2)
    ax2.set_ylabel('Enthalpy (kJ/kg)', fontsize=9)
    ax2.legend(loc='upper left', ncol=1, fontsize=7)
    ax2.set_ylim(20, 85)
    ax2.grid(True, alpha=0.3)

    # Humidity
    ax3.plot(times, event_data.DayTime_Avg_Qair, color='darkorange', linewidth=2)
    ax3.plot(times, event_data.NightTime_Avg_Qair, color='purple', linewidth=2)
    ax3.set_ylabel('Qair (kg/kg)', fontsize=9)
    ax3.set_ylim(0.005, 0.02) # Fixed typo: assumed 0.005 instead of 0.05
    ax3.grid(True, alpha=0.3)

    for ax in axes:
        ax.axvspan(target_date, target_date + pd.Timedelta(days=1), color='red', alpha=0.15)
        
    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
    ds.close(); ds_thresh.close()

def plot_hourly_failure_event(axes, hourly_path, thresh_path, target_date_str, dc_id, df):
    ax1, ax2, ax3 = axes
    dc_info = df[df['id'] == dc_id]
    if dc_info.empty: return
    dc_lat, dc_lon = dc_info['lat'].values[0], dc_info['lon'].values[0]

    target_date = pd.to_datetime(target_date_str)
    start_date = target_date - pd.Timedelta(days=14)
    end_date = target_date + pd.Timedelta(days=3)
    month_str = target_date.strftime('%Y-%m')

    ds_hourly = xr.open_dataset(hourly_path)
    event_data = ds_hourly.sel(lat=dc_lat, lon=dc_lon, method='nearest').sel(time=slice(start_date, end_date)).load()
    times = event_data.time.values

    ds_thresh = xr.open_dataset(thresh_path)
    monthly_thresh = ds_thresh.sel(lat=dc_lat, lon=dc_lon, quantile=0.90, method='nearest').sel(time=month_str).mean(dim='time')
    
    line_color = 'teal'

    ax1.plot(times, event_data.Tair_C, color=line_color, linewidth=1.5)
    ax1.set_ylabel('Temp (°C)', fontsize=9)
    ax1.set_title('Hourly Fluctuations (14 Days Prior)', fontsize=12, fontweight='bold')
    ax1.set_ylim(10, 50)
    ax1.grid(True, alpha=0.3)

    ax2.plot(times, event_data.enthalpy, color=line_color, linewidth=1.5)
    ax2.axhline(monthly_thresh.DayTime_Avg_enthalpy_thresholds.values, color='firebrick', linestyle='-.', linewidth=1.5)
    ax2.axhline(monthly_thresh.NightTime_Avg_enthalpy_thresholds.values, color='midnightblue', linestyle='-.', linewidth=1.5)
    ax2.set_ylabel('Enthalpy', fontsize=9)
    ax2.set_ylim(20, 90)
    ax2.grid(True, alpha=0.3)

    ax3.plot(times, event_data.Qair, color=line_color, linewidth=1.5)
    ax3.set_ylabel('Qair', fontsize=9)
    ax3.set_ylim(0.005, 0.02) # Fixed typo: assumed 0.005 instead of 0.05
    ax3.grid(True, alpha=0.3)

    for ax in axes:
        ax.axvspan(target_date, target_date + pd.Timedelta(days=1), color='red', alpha=0.15)
        
    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
    ds_hourly.close(); ds_thresh.close()

# ASHRAE helpers
def calc_sat_vapor_pressure(t_celsius): return 611.2 * np.exp((17.67 * t_celsius) / (t_celsius + 243.5))
def calc_rh(t_air, q_air, p_surf):
    w = q_air / (1.0 - q_air)
    e = (w * p_surf) / (0.622 + w)
    return np.clip((e / calc_sat_vapor_pressure(t_air)) * 100.0, 0, 100)

def get_ashrae_bounds(t_min, t_max, rh_min, rh_max, dp_min, dp_max):
    t_grid = np.linspace(t_min, t_max, 200)
    vp_sat_grid = calc_sat_vapor_pressure(t_grid)
    return t_grid, np.maximum(rh_min, (calc_sat_vapor_pressure(dp_min)/vp_sat_grid)*100), np.minimum(rh_max, (calc_sat_vapor_pressure(dp_max)/vp_sat_grid)*100)

def plot_rh_seasonal_envelope(axes, nc_path, target_date_str, dc_id, df):
    ax1, ax2 = axes
    target_date = pd.to_datetime(target_date_str)
    season_code = 'DJF' if target_date.month in [12, 1, 2] else 'MAM' if target_date.month in [3, 4, 5] else 'JJA' if target_date.month in [6, 7, 8] else 'SON'
    
    dc_info = df[df['id'] == dc_id]
    if dc_info.empty: return
    
    ds = xr.open_dataset(nc_path)
    
    # ====================================================================
    # 1. THE BACKGROUND (Static): Use ALL pixels in the state for the season
    # ====================================================================
    ds_season = ds.isel(time=(ds['time'].dt.season == season_code))
    
    # Flattening combines all times AND all locations into one massive, static distribution
    day_t = ds_season['DayTime_Avg_Tair'].values.flatten()
    day_q = ds_season['DayTime_Avg_Qair'].values.flatten()
    day_p = ds_season['DayTime_Avg_PSurf'].values.flatten()
    
    night_t = ds_season['NightTime_Avg_Tair'].values.flatten()
    night_q = ds_season['NightTime_Avg_Qair'].values.flatten()
    night_p = ds_season['NightTime_Avg_PSurf'].values.flatten()

    # ====================================================================
    # 2. THE PURPLE DOT (Moving): Specific Datacenter, Specific Day
    # ====================================================================
    point_ds = ds.sel(lat=dc_info['lat'].values[0], lon=dc_info['lon'].values[0], method='nearest')
    
    try:
        tgt_ds = point_ds.sel(time=target_date_str)
        found_target, tgt_day_t = True, tgt_ds['DayTime_Avg_Tair'].item()
        tgt_day_rh = calc_rh(tgt_day_t, tgt_ds['DayTime_Avg_Qair'].item(), tgt_ds['DayTime_Avg_PSurf'].item())
        tgt_night_t = tgt_ds['NightTime_Avg_Tair'].item()
        tgt_night_rh = calc_rh(tgt_night_t, tgt_ds['NightTime_Avg_Qair'].item(), tgt_ds['NightTime_Avg_PSurf'].item())
    except: 
        found_target = False

    ashrae_classes = [
        {'name': 'A4', 't': (5, 45), 'rh': (8, 90), 'dp': (-12, 24), 'color': 'lightgreen', 'alpha': 0.05},
        {'name': 'A3', 't': (5, 40), 'rh': (8, 85), 'dp': (-12, 24), 'color': 'limegreen', 'alpha': 0.05},
        {'name': 'A2', 't': (10, 35), 'rh': (8, 80), 'dp': (-12, 21), 'color': 'forestgreen', 'alpha': 0.05},
        {'name': 'A1', 't': (15, 32), 'rh': (8, 80), 'dp': (-12, 17), 'color': 'darkgreen', 'alpha': 0.05}
    ]

# def plot_rh_seasonal_envelope(axes, nc_path, target_date_str, dc_id, df):
#     ax1, ax2 = axes
#     target_date = pd.to_datetime(target_date_str)
#     season_code = 'DJF' if target_date.month in [12, 1, 2] else 'MAM' if target_date.month in [3, 4, 5] else 'JJA' if target_date.month in [6, 7, 8] else 'SON'
    
#     dc_info = df[df['id'] == dc_id]
#     if dc_info.empty: return
    
#     ds = xr.open_dataset(nc_path)
    
#     # ====================================================================
#     # 1. THE BACKGROUND (Static): Use ALL pixels in the state for the season
#     # ====================================================================
#     ds_season = ds.isel(time=(ds['time'].dt.season == season_code))
    
#     # Flattening combines all times AND all locations into one massive, static distribution
#     day_t = ds_season['DayTime_Avg_Tair'].values.flatten()
#     day_q = ds_season['DayTime_Avg_Qair'].values.flatten()
#     day_p = ds_season['DayTime_Avg_PSurf'].values.flatten()
    
#     night_t = ds_season['NightTime_Avg_Tair'].values.flatten()
#     night_q = ds_season['NightTime_Avg_Qair'].values.flatten()
#     night_p = ds_season['NightTime_Avg_PSurf'].values.flatten()

#     # ====================================================================
#     # 2. THE PURPLE DOT (Moving): Specific Datacenter, Specific Day
#     # ====================================================================
#     point_ds = ds.sel(lat=dc_info['lat'].values[0], lon=dc_info['lon'].values[0], method='nearest')
    
#     try:
#         tgt_ds = point_ds.sel(time=target_date_str)
#         found_target, tgt_day_t = True, tgt_ds['DayTime_Avg_Tair'].item()
#         tgt_day_rh = calc_rh(tgt_day_t, tgt_ds['DayTime_Avg_Qair'].item(), tgt_ds['DayTime_Avg_PSurf'].item())
#         tgt_night_t = tgt_ds['NightTime_Avg_Tair'].item()
#         tgt_night_rh = calc_rh(tgt_night_t, tgt_ds['NightTime_Avg_Qair'].item(), tgt_ds['NightTime_Avg_PSurf'].item())
#     except: 
#         found_target = False

#     ashrae_classes = [
#         {'name': 'A4', 't': (5, 45), 'rh': (8, 90), 'dp': (-12, 24), 'color': 'lightgreen', 'alpha': 0.05},
#         {'name': 'A3', 't': (5, 40), 'rh': (8, 85), 'dp': (-12, 24), 'color': 'limegreen', 'alpha': 0.05},
#         {'name': 'A2', 't': (10, 35), 'rh': (8, 80), 'dp': (-12, 21), 'color': 'forestgreen', 'alpha': 0.05},
#         {'name': 'A1', 't': (15, 32), 'rh': (8, 80), 'dp': (-12, 17), 'color': 'darkgreen', 'alpha': 0.05}
#     ]

#     def format_panel(ax, t_data, rh_data, title):
#         valid = np.isfinite(t_data) & np.isfinite(rh_data)
#         # Using rasterized=True to keep PDF sizes manageable since we are using flattened data!
#         ax.hist2d(t_data[valid], rh_data[valid], bins=[50, 50], range=[[-15, 50], [0, 100]], cmap='inferno', cmin=1, alpha=0.9, zorder=1, rasterized=True)
        
#         for ac in ashrae_classes:
#             t_grid, b_bnd, t_bnd = get_ashrae_bounds(*ac['t'], *ac['rh'], *ac['dp'])
#             ax.fill_between(t_grid, b_bnd, t_bnd, color=ac['color'], alpha=ac['alpha'], zorder=2)
#             ax.plot(t_grid, t_bnd, color=ac['color'], linewidth=1, zorder=3)
#             ax.plot(t_grid, b_bnd, color=ac['color'], linewidth=1, zorder=3)
            
#         ax.set_title(title, fontsize=12, fontweight='bold')
#         ax.set_xlim(-15, 50)
#         ax.set_ylim(0, 100)
#         ax.grid(alpha=0.3, linestyle='--')
#         ax.text(25, 15, 'A1', color='darkgreen', fontsize=5, fontweight='bold')
#         ax.text(30, 15, 'A2', color='darkgreen', fontsize=5, fontweight='bold')
#         ax.text(35, 15, 'A3', color='darkgreen', fontsize=5, fontweight='bold')
#         ax.text(40, 15, 'A4', color='darkgreen', fontsize=5, fontweight='bold')

#     format_panel(ax1, day_t, calc_rh(day_t, day_q, day_p), "ASHRAE (Daytime - Statewide Norm)")
#     ax1.set_xlabel('Temp (°C)', fontsize=9)
#     ax1.set_ylabel('Relative Humidity (%)', fontsize=9)
#     if found_target: ax1.scatter(tgt_day_t, tgt_day_rh, color='#9f00ff', s=150, marker='*', zorder=5)

#     format_panel(ax2, night_t, calc_rh(night_t, night_q, night_p), "ASHRAE (Nighttime - Statewide Norm)")
#     ax2.set_xlabel('Temp (°C)', fontsize=9)
#     if found_target: ax2.scatter(tgt_night_t, tgt_night_rh, color='#9f00ff', s=150, marker='*', zorder=5)
    
#     ds.close()

#     format_panel(ax1, day_t, calc_rh(day_t, day_q, day_p), "ASHRAE (Daytime - Statewide Norm)")
#     ax1.set_xlabel('Temp (°C)', fontsize=9)
#     ax1.set_ylabel('Relative Humidity (%)', fontsize=9)
#     if found_target: ax1.scatter(tgt_day_t, tgt_day_rh, color='#9f00ff', s=150, marker='*', zorder=5)

#     format_panel(ax2, night_t, calc_rh(night_t, night_q, night_p), "ASHRAE (Nighttime - Statewide Norm)")
#     ax2.set_xlabel('Temp (°C)', fontsize=9)
#     if found_target: ax2.scatter(tgt_night_t, tgt_night_rh, color='#9f00ff', s=150, marker='*', zorder=5)
    
#     ds.close()

def plot_rh_seasonal_envelope(axes, nc_path, target_date_str, dc_id, df):
    ax1, ax2 = axes
    
    dc_info = df[df['id'] == dc_id]
    if dc_info.empty: return
    
    # 1. Fetch the INSTANT pre-computed 2D histograms from cache
    bg_data = get_precomputed_ashrae_background(nc_path, target_date_str)
    
    # 2. Extract ONLY the target moving purple dot (Super fast)
    with xr.open_dataset(nc_path) as ds:
        point_ds = ds.sel(lat=dc_info['lat'].values[0], lon=dc_info['lon'].values[0], method='nearest')
        try:
            tgt_ds = point_ds.sel(time=target_date_str)
            found_target, tgt_day_t = True, tgt_ds['DayTime_Avg_Tair'].item()
            tgt_day_rh = calc_rh(tgt_day_t, tgt_ds['DayTime_Avg_Qair'].item(), tgt_ds['DayTime_Avg_PSurf'].item())
            tgt_night_t = tgt_ds['NightTime_Avg_Tair'].item()
            tgt_night_rh = calc_rh(tgt_night_t, tgt_ds['NightTime_Avg_Qair'].item(), tgt_ds['NightTime_Avg_PSurf'].item())
        except: 
            found_target = False

    ashrae_classes = [
        {'name': 'A4', 't': (5, 45), 'rh': (8, 90), 'dp': (-12, 24), 'color': 'lightgreen', 'alpha': 0.05},
        {'name': 'A3', 't': (5, 40), 'rh': (8, 85), 'dp': (-12, 24), 'color': 'limegreen', 'alpha': 0.05},
        {'name': 'A2', 't': (10, 35), 'rh': (8, 80), 'dp': (-12, 21), 'color': 'forestgreen', 'alpha': 0.05},
        {'name': 'A1', 't': (15, 32), 'rh': (8, 80), 'dp': (-12, 17), 'color': 'darkgreen', 'alpha': 0.05}
    ]

    def format_panel(ax, H, xedges, yedges, title):
        # Mask 0 values so they don't plot (equivalent to cmin=1 in hist2d)
        H_masked = np.ma.masked_where(H < 1, H)
        
        # Use pcolormesh instead of hist2d (lightning fast rendering)
        ax.pcolormesh(xedges, yedges, H_masked.T, cmap='inferno', alpha=0.9, zorder=1, rasterized=True)
        
        for ac in ashrae_classes:
            t_grid, b_bnd, t_bnd = get_ashrae_bounds(*ac['t'], *ac['rh'], *ac['dp'])
            ax.fill_between(t_grid, b_bnd, t_bnd, color=ac['color'], alpha=ac['alpha'], zorder=2)
            ax.plot(t_grid, t_bnd, color=ac['color'], linewidth=1, zorder=3)
            ax.plot(t_grid, b_bnd, color=ac['color'], linewidth=1, zorder=3)

            ## vertical lines
            ax.plot([t_grid[0], t_grid[0]], [b_bnd[0], t_bnd[0]], color=ac['color'], linewidth=1.5, zorder=3)
            ax.plot([t_grid[-1], t_grid[-1]], [b_bnd[-1], t_bnd[-1]], color=ac['color'], linewidth=1.5, zorder=3)
            
            
        ax.set_title(title, fontsize=12, fontweight='bold')
        ax.set_xlim(-15, 50)
        ax.set_ylim(0, 100)
        ax.grid(alpha=0.3, linestyle='--')
        ax.text(25, 15, 'A1', color='darkgreen', fontsize=5, fontweight='bold')
        ax.text(30, 15, 'A2', color='darkgreen', fontsize=5, fontweight='bold')
        ax.text(35, 15, 'A3', color='darkgreen', fontsize=5, fontweight='bold')
        ax.text(40, 15, 'A4', color='darkgreen', fontsize=5, fontweight='bold')

    # Apply the panels and stars
    format_panel(ax1, bg_data['day_H'], bg_data['xedges'], bg_data['yedges'], "ASHRAE (Daytime)")
    ax1.set_xlabel('Temp (°C)', fontsize=9)
    ax1.set_ylabel('Relative Humidity (%)', fontsize=9)
    if found_target: ax1.scatter(tgt_day_t, tgt_day_rh, color='#9f00ff', s=150, marker='*', zorder=5)

    format_panel(ax2, bg_data['night_H'], bg_data['xedges'], bg_data['yedges'], "ASHRAE (Nighttime)")
    ax2.set_xlabel('Temp (°C)', fontsize=9)
    if found_target: ax2.scatter(tgt_night_t, tgt_night_rh, color='#9f00ff', s=150, marker='*', zorder=5)


# ==========================================
# 2. NEW: COMPUTE STATISTICS FOR THE TABLE
# ==========================================

# def compute_threshold_stats(hourly_path, thresh_path, target_date_str, dc_lat, dc_lon):
#     """Calculates crossings, total hours, and the max hourly enthalpy jump strictly prior to the event."""
#     target_date = pd.to_datetime(target_date_str)
#     start_date = target_date - pd.Timedelta(days=14)
#     # Stop calculating 1 hour before the event day begins
#     end_date_stats = target_date - pd.Timedelta(hours=1) 
    
#     ds_hourly = xr.open_dataset(hourly_path)
#     ds_thresh = xr.open_dataset(thresh_path)
    
#     hourly_data = ds_hourly.sel(lat=dc_lat, lon=dc_lon, method='nearest').sel(time=slice(start_date, end_date_stats)).load()
#     enth = hourly_data.enthalpy.values
    
#     month_str = target_date.strftime('%Y-%m')
#     monthly_thresh = ds_thresh.sel(lat=dc_lat, lon=dc_lon, quantile=0.90, method='nearest').sel(time=month_str).mean(dim='time')
    
#     day_t = float(monthly_thresh.DayTime_Avg_enthalpy_thresholds.values)
#     night_t = float(monthly_thresh.NightTime_Avg_enthalpy_thresholds.values)
    
#     stats = {'day_val': day_t, 'night_val': night_t, 'day_hours': 0, 'day_cross': 0, 'night_hours': 0, 'night_cross': 0}
    
#     if len(enth) > 0:
#         # NEW: Calculate the maximum positive hour-over-hour jump in enthalpy
#         enth_diff = np.diff(enth)
#         stats['max_hourly_jump'] = float(np.max(enth_diff)) if len(enth_diff) > 0 else 0.0

#         for thresh, prefix in [(day_t, 'day'), (night_t, 'night')]:
#             above = (enth > thresh).astype(int)
#             stats[f'{prefix}_hours'] = int(np.sum(above))
            
#             # Count times it crossed the threshold (went from 0 to 1)
#             crossings = np.sum(np.diff(above) == 1)
#             if above[0] == 1: crossings += 1 # Count if it started the 14-day window already above
#             stats[f'{prefix}_cross'] = int(crossings)
            
#     ds_hourly.close(); ds_thresh.close()
#     return stats

def compute_threshold_stats(daily_path, hourly_path, thresh_path, target_date_str, dc_lat, dc_lon):
    """Calculates crossings, total hours, and the max 1hr, 24hr, and 48hr enthalpy jumps prior to the event."""
    target_date = pd.to_datetime(target_date_str)
    start_date = target_date - pd.Timedelta(days=14)
    # Stop calculating hourly crossings 1 hour before the event day begins
    end_date_stats = target_date - pd.Timedelta(hours=1) 
    
    ds_hourly = xr.open_dataset(hourly_path)
    ds_thresh = xr.open_dataset(thresh_path)
    ds_daily = xr.open_dataset(daily_path) # NEW: load daily for the 24/48hr stats
    
    # -----------------------------------------------------
    # 1. Hourly Stats (Crossings & 1-hr surge)
    # -----------------------------------------------------
    hourly_data = ds_hourly.sel(lat=dc_lat, lon=dc_lon, method='nearest').sel(time=slice(start_date, end_date_stats)).load()
    enth = hourly_data.enthalpy.values
    
    month_str = target_date.strftime('%Y-%m')
    monthly_thresh = ds_thresh.sel(lat=dc_lat, lon=dc_lon, quantile=0.90, method='nearest').sel(time=month_str).mean(dim='time')
    
    day_t = float(monthly_thresh.DayTime_Avg_enthalpy_thresholds.values)
    night_t = float(monthly_thresh.NightTime_Avg_enthalpy_thresholds.values)
    
    stats = {'day_val': day_t, 'night_val': night_t, 'day_hours': 0, 'day_cross': 0, 'night_hours': 0, 'night_cross': 0}
    
    if len(enth) > 0:
        enth_diff = np.diff(enth)
        stats['max_hourly_jump'] = float(np.max(enth_diff)) if len(enth_diff) > 0 else 0.0

        for thresh, prefix in [(day_t, 'day'), (night_t, 'night')]:
            above = (enth > thresh).astype(int)
            stats[f'{prefix}_hours'] = int(np.sum(above))
            
            crossings = np.sum(np.diff(above) == 1)
            if above[0] == 1: crossings += 1 
            stats[f'{prefix}_cross'] = int(crossings)
            
    # -----------------------------------------------------
    # 2. Daily Stats (24-hr and 48-hr Surge)
    # -----------------------------------------------------
    daily_data = ds_daily.sel(lat=dc_lat, lon=dc_lon, method='nearest').sel(time=slice(start_date, target_date)).load()
    
    for prefix, var_name in [('day', 'DayTime_Avg_enthalpy'), ('night', 'NightTime_Avg_enthalpy')]:
        d_enth = daily_data[var_name].values
        
        # 24-hr surge (max difference over 1 day)
        if len(d_enth) > 1:
            stats[f'{prefix}_surge_24'] = float(np.max(np.diff(d_enth)))
        else:
            stats[f'{prefix}_surge_24'] = 0.0
            
        # 48-hr surge (max difference over 2 days)
        if len(d_enth) > 2:
            stats[f'{prefix}_surge_48'] = float(np.max(d_enth[2:] - d_enth[:-2]))
        else:
            stats[f'{prefix}_surge_48'] = 0.0
            
    ds_hourly.close(); ds_thresh.close(); ds_daily.close()
    return stats


# ==========================================
# 3. PDF GENERATION LOGIC 
# ==========================================

def generate_master_panel(pdf, dc_id, target_date, df, state_abb):
    """Creates a 16:9 master panel with 4 quadrants + Stats Table."""
    if state_abb == 'VA':
        daily_nc = '/discover/nobackup/cmbreen/datacenters/virginia_hourly/va_Daily_DayNight_Summary_CORRECTED.nc'
        hourly_nc = '/discover/nobackup/cmbreen/datacenters/virginia_pure_hourly/va_Pure_Hourly_Summary_FIXED.nc'
        thresh_nc = '/discover/nobackup/cmbreen/datacenters/virginia_hourly/va_daynight_threshold.nc'
    else:
        daily_nc = '/discover/nobackup/cmbreen/datacenters/texas_hourly/tx_Daily_DayNight_Summary_CORRECTED.nc'
        hourly_nc = '/discover/nobackup/cmbreen/datacenters/texas_pure_hourly/tx_Pure_Hourly_Summary_FIXED.nc'
        thresh_nc = '/discover/nobackup/cmbreen/datacenters/texas_hourly/tx_daynight_threshold.nc'

    fig = plt.figure(figsize=(16, 9), dpi=150)
    gs = GridSpec(2, 2, figure=fig, width_ratios=[1, 1.2], height_ratios=[1, 1], wspace=0.15, hspace=0.25)
    
    operator = df[df['id'] == dc_id]['operator'].values[0]
    fig.suptitle(f"Datacenter Operations Dashboard | ID: {dc_id} ({operator}) | Target Date: {target_date}", 
                 fontsize=18, fontweight='bold', y=0.96)

    # # ----------------------------------------------------
    # # Quadrant 1 (Top Left): Map & Table
    # # ----------------------------------------------------
    # # Sub-grid to stack Map on top and Table on bottom
    # gs_left = gs[0, 0].subgridspec(2, 1, height_ratios=[2.5, 1], hspace=0.4)
    # ax_map = fig.add_subplot(gs_left[0, 0])
    # ax_table = fig.add_subplot(gs_left[1, 0])
    # ax_table.axis('off')
    
    # plot_datacenter_heat_map_tx(ax_map, dc_id, target_date, df, daily_nc)

    # ----------------------------------------------------
    # Quadrant 1 (Top Left): Map & Table
    # ----------------------------------------------------
    # Sub-grid: 2 rows, 2 columns. 
    # width_ratios=[0.85, 0.15] gives the map 85% of the width, leaving 15% empty on the right.
    gs_left = gs[0, 0].subgridspec(2, 2, height_ratios=[2.5, 1], width_ratios=[0.85, 0.15], hspace=0.4)
    
    # Map goes in row 0, col 0 (leaving col 1 empty as a buffer for the colorbar)
    ax_map = fig.add_subplot(gs_left[0, 0])
    
    # Table goes in row 1, but uses ":" to span across BOTH columns so it stays centered
    ax_table = fig.add_subplot(gs_left[1, :])
    ax_table.axis('off')
    
    plot_datacenter_heat_map_tx(ax_map, dc_id, target_date, df, daily_nc)

    # # Calculate and draw Table
    # dc_lat, dc_lon = df[df['id'] == dc_id]['lat'].values[0], df[df['id'] == dc_id]['lon'].values[0]
    # stats = compute_threshold_stats(hourly_nc, thresh_nc, target_date, dc_lat, dc_lon)
    
    # # Format NaN thresholds neatly if they occur
    # d_val = f"{stats['day_val']:.1f}" if np.isfinite(stats['day_val']) else "N/A"
    # n_val = f"{stats['night_val']:.1f}" if np.isfinite(stats['night_val']) else "N/A"
    
    # # Calculate Average Hours per Event (avoiding division by zero)
    # d_avg = f"{stats['day_hours'] / stats['day_cross']:.1f}" if stats['day_cross'] > 0 else "0.0"
    # n_avg = f"{stats['night_hours'] / stats['night_cross']:.1f}" if stats['night_cross'] > 0 else "0.0"
    
    # table_data = [
    #     ['Daytime', d_val, str(stats['day_cross']), str(stats['day_hours']), d_avg],
    #     ['Nighttime', n_val, str(stats['night_cross']), str(stats['night_hours']), n_avg]
    # ]
    
    # # Updated Headers to accommodate the new metric
    # col_labels = ['Period', 'Threshold \n (kJ/kg)', 'Events \n (Crossings)', 'Total Hours \n Exceeded', 'Avg Hours / \n Event',
    #               '48-hr surge', '24-hr surge']

    # max_surge = stats.get('max_hourly_jump', 0.0)
    # ax_table.set_title(f"14-Day Pre-Event Summary (Max Hourly Surge: +{max_surge:.1f} kJ/kg)", 
    #                    fontsize=10, fontweight='bold', pad=5)
    # table = ax_table.table(cellText=table_data, colLabels=col_labels, loc='center', cellLoc='center', bbox=[0, 0, 1, 1])
    # table.auto_set_font_size(False)
    # table.set_fontsize(6)
    # table.scale(1, 1.5) # Add padding to cells

    # Calculate and draw Table
    dc_lat, dc_lon = df[df['id'] == dc_id]['lat'].values[0], df[df['id'] == dc_id]['lon'].values[0]
    
    # Pass daily_nc as the first argument
    stats = compute_threshold_stats(daily_nc, hourly_nc, thresh_nc, target_date, dc_lat, dc_lon)
    
    # Format NaN thresholds neatly if they occur
    d_val = f"{stats['day_val']:.1f}" if np.isfinite(stats['day_val']) else "N/A"
    n_val = f"{stats['night_val']:.1f}" if np.isfinite(stats['night_val']) else "N/A"
    
    # Calculate Average Hours per Event (avoiding division by zero)
    d_avg = f"{stats['day_hours'] / stats['day_cross']:.1f}" if stats['day_cross'] > 0 else "0.0"
    n_avg = f"{stats['night_hours'] / stats['night_cross']:.1f}" if stats['night_cross'] > 0 else "0.0"
    
    # Format the new surges (Adding '+' to show it's a jump)
    d_24 = f"+{max(0, stats['day_surge_24']):.1f}"
    d_48 = f"+{max(0, stats['day_surge_48']):.1f}"
    n_24 = f"+{max(0, stats['night_surge_24']):.1f}"
    n_48 = f"+{max(0, stats['night_surge_48']):.1f}"
    
    # Append the surges to match your 7 column headers (Notice 48-hr comes before 24-hr)
    table_data = [
        ['Daytime', d_val, str(stats['day_cross']), str(stats['day_hours']), d_avg, d_48, d_24],
        ['Nighttime', n_val, str(stats['night_cross']), str(stats['night_hours']), n_avg, n_48, n_24]
    ]
    
    col_labels = ['Period', 'Threshold \n (kJ/kg)', 'Events \n (Crossings)', 'Total Hours \n Exceeded', 'Avg Hours / \n Event',
                  '48-hr surge', '24-hr surge']

    max_surge = stats.get('max_hourly_jump', 0.0)
    ax_table.set_title(f"14-Day Pre-Event Summary (Max Hourly Surge: +{max_surge:.1f} kJ/kg)", 
                       fontsize=10, fontweight='bold', pad=5)
    table = ax_table.table(cellText=table_data, colLabels=col_labels, loc='center', cellLoc='center', bbox=[0, 0, 1, 1])
    table.auto_set_font_size(False)
    table.set_fontsize(6)
    table.scale(1, 1.5) # Add padding to cells
    
    for (i, j), cell in table.get_celld().items():
        if i == 0: # Header
            cell.set_text_props(weight='bold', color='white')
            cell.set_facecolor('#4c4c4c')
        else: # Rows
            cell.set_facecolor('#f2f2f2' if i % 2 == 0 else 'white')

    # ----------------------------------------------------
    # Quadrant 2 (Top Right): Daily Build-Up
    # ----------------------------------------------------
    gs_daily = gs[0, 1].subgridspec(3, 1, hspace=0.1)
    ax_d1, ax_d2, ax_d3 = fig.add_subplot(gs_daily[0, 0]), fig.add_subplot(gs_daily[1, 0]), fig.add_subplot(gs_daily[2, 0])
    plt.setp(ax_d1.get_xticklabels(), visible=False); plt.setp(ax_d2.get_xticklabels(), visible=False)
    
    plot_failure_event_with_baselines([ax_d1, ax_d2, ax_d3], daily_nc, thresh_nc, target_date, dc_id, df)

    # ----------------------------------------------------
    # Quadrant 3 (Bottom Left): ASHRAE Envelopes
    # ----------------------------------------------------
    gs_ashrae = gs[1, 0].subgridspec(1, 2, wspace=0.1)
    ax_a1, ax_a2 = fig.add_subplot(gs_ashrae[0, 0]), fig.add_subplot(gs_ashrae[0, 1])
    plt.setp(ax_a2.get_yticklabels(), visible=False)
    
    plot_rh_seasonal_envelope([ax_a1, ax_a2], daily_nc, target_date, dc_id, df)

    # ----------------------------------------------------
    # Quadrant 4 (Bottom Right): Hourly Build-Up
    # ----------------------------------------------------
    gs_hourly = gs[1, 1].subgridspec(3, 1, hspace=0.1)
    ax_h1, ax_h2, ax_h3 = fig.add_subplot(gs_hourly[0, 0]), fig.add_subplot(gs_hourly[1, 0]), fig.add_subplot(gs_hourly[2, 0])
    plt.setp(ax_h1.get_xticklabels(), visible=False); plt.setp(ax_h2.get_xticklabels(), visible=False)
    
    plot_hourly_failure_event([ax_h1, ax_h2, ax_h3], hourly_nc, thresh_nc, target_date, dc_id, df)

    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)

# ==========================================
# 4. MAIN EXECUTION 
# ==========================================

if __name__ == "__main__":
    df = pd.read_csv('~/INNOVATE/im3_open_source_data_center_atlas_v2026.02.09.csv')
    
    # ------------------------------------------------------------------
    # NEW: Filter Texas datacenters based on NetCDF spatial boundaries
    # ------------------------------------------------------------------
    tx_daily_nc = '/discover/nobackup/cmbreen/datacenters/texas_hourly/tx_Daily_DayNight_Summary_CORRECTED.nc'
    
    # Open the TX NetCDF to grab the bounding box
    with xr.open_dataset(tx_daily_nc) as ds_tx:
        tx_min_lat, tx_max_lat = ds_tx.lat.min().item(), ds_tx.lat.max().item()
        tx_min_lon, tx_max_lon = ds_tx.lon.min().item(), ds_tx.lon.max().item()
    
    # Filter the DataFrame to ONLY include TX datacenters inside these bounds
    tx_df = df[
        (df['state_abb'] == 'TX') & 
        (df['lat'] >= tx_min_lat) & (df['lat'] <= tx_max_lat) & 
        (df['lon'] >= tx_min_lon) & (df['lon'] <= tx_max_lon)
    ]
    tx_ids = tx_df['id'].tolist()
    
    print(f"Loaded {len(tx_ids)} Texas datacenters within NetCDF bounds.")

    # Virginia AWS Datacenters
    aws_ops = ['Amazon Web Services', 'AWS', 'Amazon']
    va_ids = df[(df['state_abb'] == 'VA') & (df['operator'].isin(aws_ops))]['id'].tolist()

    # REMOVED San Antonio event per your request
    target_events = [
        {"date": "2012-06-29", "state": "VA", "desc": "AWS_us-east-1"},
        # {"date": "2018-09-04", "state": "TX", "desc": "San_Antonio_NA"},
        {"date": "2023-07-31", "state": "TX", "desc": "First_Major_Peak"},
        {"date": "2023-08-10", "state": "TX", "desc": "Summer_2023_Peak"},
        {"date": "2023-08-17", "state": "TX", "desc": "Late_Aug_Heatwave_1"},
        {"date": "2023-08-24", "state": "TX", "desc": "Late_Aug_Heatwave_2"},
        {"date": "2023-09-05", "state": "TX", "desc": "Sept_Heatwave"} 
    ]

    for event in target_events:
        event_date, event_state, event_desc = event["date"], event["state"], event["desc"]
        dc_list = va_ids if event_state == 'VA' else tx_ids

        output_dir = "/discover/nobackup/cmbreen/datacenters/output_pdfs/" 
        os.makedirs(output_dir, exist_ok=True) 

        output_pdf = f"{output_dir}Datacenter_Panels_{event_state}_{event_date}_{event_desc}.pdf"
        print(f"\n{'='*50}\nCreating {output_pdf} ({len(dc_list)} pages)\n{'='*50}")
        
        with PdfPages(output_pdf) as pdf:
            for i, dc_id in enumerate(dc_list):
                print(f"  [{i+1}/{len(dc_list)}] Processing DC {dc_id} on {event_date}...")
                try:
                    generate_master_panel(pdf, dc_id, event_date, df, event_state)
                except Exception as e:
                    print(f"  -> ERROR plotting DC {dc_id}: {e}")
                    continue 
                    
        print(f"-> Successfully saved {output_pdf}")
