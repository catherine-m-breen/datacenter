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
warnings.filterwarnings('ignore')

# ==========================================
# 0. CACHE & HELPERS
# ==========================================
SEASONAL_BG_CACHE = {}

def get_precomputed_ashrae_background(nc_path, target_date_str):
    target_date = pd.to_datetime(target_date_str)
    season_code = 'DJF' if target_date.month in [12, 1, 2] else 'MAM' if target_date.month in [3, 4, 5] else 'JJA' if target_date.month in [6, 7, 8] else 'SON'
    cache_key = (nc_path, season_code)

    if cache_key not in SEASONAL_BG_CACHE:
        print(f"    -> [Cache Miss] Pre-computing {season_code} ASHRAE background (Runs ONLY ONCE per state/season!)")
        with xr.open_dataset(nc_path) as ds:
            ds_season = ds.isel(time=(ds['time'].dt.season == season_code))
            day_t = ds_season['DayTime_Avg_Tair'].values.flatten()
            day_q = ds_season['DayTime_Avg_Qair'].values.flatten()
            day_p = ds_season['DayTime_Avg_PSurf'].values.flatten()
            night_t = ds_season['NightTime_Avg_Tair'].values.flatten()
            night_q = ds_season['NightTime_Avg_Qair'].values.flatten()
            night_p = ds_season['NightTime_Avg_PSurf'].values.flatten()
        
        day_rh = calc_rh(day_t, day_q, day_p)
        night_rh = calc_rh(night_t, night_q, night_p)
        
        d_valid = np.isfinite(day_t) & np.isfinite(day_rh)
        n_valid = np.isfinite(night_t) & np.isfinite(night_rh)
        
        bins, rng = [50, 50], [[-15, 50], [0, 100]]
        day_H, xedges, yedges = np.histogram2d(day_t[d_valid], day_rh[d_valid], bins=bins, range=rng)
        night_H, _, _ = np.histogram2d(night_t[n_valid], night_rh[n_valid], bins=bins, range=rng)
        
        SEASONAL_BG_CACHE[cache_key] = {'day_H': day_H, 'night_H': night_H, 'xedges': xedges, 'yedges': yedges}
        
    return SEASONAL_BG_CACHE[cache_key]

def calc_sat_vapor_pressure(t_celsius): return 611.2 * np.exp((17.67 * t_celsius) / (t_celsius + 243.5))
def calc_rh(t_air, q_air, p_surf):
    w = q_air / (1.0 - q_air)
    e = (w * p_surf) / (0.622 + w)
    return np.clip((e / calc_sat_vapor_pressure(t_air)) * 100.0, 0, 100)

def get_ashrae_bounds(t_min, t_max, rh_min, rh_max, dp_min, dp_max):
    t_grid = np.linspace(t_min, t_max, 200)
    vp_sat_grid = calc_sat_vapor_pressure(t_grid)
    return t_grid, np.maximum(rh_min, (calc_sat_vapor_pressure(dp_min)/vp_sat_grid)*100), np.minimum(rh_max, (calc_sat_vapor_pressure(dp_max)/vp_sat_grid)*100)

def get_max_enthalpy(t_max, dp_max):
    vp = calc_sat_vapor_pressure(dp_max)
    w = 0.622 * vp / (101325 - vp)
    return 1.006 * t_max + w * (2501 + 1.86 * t_max)

ASHRAE_CLASSES = [
    {'name': 'A4', 't': (5, 45), 'rh': (8, 90), 'dp': (-12, 24), 'color': 'lightgreen', 'alpha': 0.05},
    {'name': 'A3', 't': (5, 40), 'rh': (8, 85), 'dp': (-12, 24), 'color': 'limegreen', 'alpha': 0.05},
    {'name': 'A2', 't': (10, 35), 'rh': (8, 80), 'dp': (-12, 21), 'color': 'forestgreen', 'alpha': 0.05},
    {'name': 'A1', 't': (15, 32), 'rh': (8, 80), 'dp': (-12, 17), 'color': 'darkgreen', 'alpha': 0.05}
]

# ==========================================
# 1. STATS COMPUTATION
# ==========================================
def compute_threshold_stats(daily_path, hourly_path, thresh_path, target_date_str, dc_lat, dc_lon):
    target_date = pd.to_datetime(target_date_str)
    start_date = target_date - pd.Timedelta(days=14)
    
    # We need hourly data through the END of the target date to get "Day Of" stats
    end_date_full = target_date + pd.Timedelta(hours=23) 
    
    ds_hourly = xr.open_dataset(hourly_path)
    ds_thresh = xr.open_dataset(thresh_path)
    
    # Load all hourly data needed
    hourly_data = ds_hourly.sel(lat=dc_lat, lon=dc_lon, method='nearest').sel(time=slice(start_date, end_date_full)).load()
    
    # Get 14-day history prior to target day for the crossing stats
    history_data = hourly_data.sel(time=slice(start_date, target_date - pd.Timedelta(hours=1)))
    enth_history = history_data.enthalpy.values
    
    month_str = target_date.strftime('%Y-%m')
    monthly_thresh = ds_thresh.sel(lat=dc_lat, lon=dc_lon, quantile=0.90, method='nearest').sel(time=month_str).mean(dim='time')
    
    day_t = float(monthly_thresh.DayTime_Avg_enthalpy_thresholds.values)
    night_t = float(monthly_thresh.NightTime_Avg_enthalpy_thresholds.values)
    
    stats = {'day_val': day_t, 'night_val': night_t, 'day_hours': 0, 'day_cross': 0, 'night_hours': 0, 'night_cross': 0}
    
    # 1. Calculate 14-Day Event Crossings
    if len(enth_history) > 0:
        enth_diff = np.diff(enth_history)
        stats['max_hourly_jump'] = float(np.max(enth_diff)) if len(enth_diff) > 0 else 0.0
        for thresh, prefix in [(day_t, 'day'), (night_t, 'night')]:
            above = (enth_history > thresh).astype(int)
            stats[f'{prefix}_hours'] = int(np.sum(above))
            crossings = np.sum(np.diff(above) == 1)
            if above[0] == 1: crossings += 1 
            stats[f'{prefix}_cross'] = int(crossings)

    # 2. Hourly Surges (Max - Min Enthalpy)
    # -----------------------------------------------------
    # Day Before: target_date minus 1 day (e.g., 00:00 to 23:00 yesterday)
    day_before_start = target_date - pd.Timedelta(days=1)
    day_before_end = target_date - pd.Timedelta(hours=1)
    enth_day_before = hourly_data.sel(time=slice(day_before_start, day_before_end)).enthalpy.values
    
    if len(enth_day_before) > 0:
        stats['surge_day_before'] = float(np.max(enth_day_before) - np.min(enth_day_before))
    else:
        stats['surge_day_before'] = 0.0
        
    # Day Of: target_date 00:00 to 23:00 today
    day_of_end = target_date + pd.Timedelta(hours=23)
    enth_day_of = hourly_data.sel(time=slice(target_date, day_of_end)).enthalpy.values
    
    if len(enth_day_of) > 0:
        stats['surge_day_of'] = float(np.max(enth_day_of) - np.min(enth_day_of))
    else:
        stats['surge_day_of'] = 0.0
            
    ds_hourly.close(); ds_thresh.close()
    return stats

# ==========================================
# 2. PLOTTING FUNCTIONS (INDIVIDUAL & SUMMARY)
# ==========================================
def plot_datacenter_heat_map_tx(ax, target_date, df, ds_path, dc_id=None, is_summary=False, dc_list=None):
    target_dc = df[df['id'] == dc_id] if not is_summary else df[df['id'] == dc_list[0]]
    if target_dc.empty: return
        
    state_abb = target_dc['state_abb'].values[0]
    state_dcs = df[df['state_abb'] == state_abb]
    aws_operators = ['Amazon Web Services', 'AWS', 'Amazon']
    aws_dcs = state_dcs[state_dcs['operator'].isin(aws_operators)]
    non_aws_dcs = state_dcs[~state_dcs['operator'].isin(aws_operators)]

    ds = xr.open_dataset(ds_path)
    try: day_temp = ds.sel(time=target_date)['DayTime_Avg_Tair']
    except KeyError: ds.close(); return

    title = f"Infrastructure & Heat ({target_date})" if not is_summary else f"Regional Heat Map - ALL DCs ({target_date})"
    ax.set_title(title, fontsize=12, fontweight='bold')

    temp_plot = ax.pcolormesh(ds.lon, ds.lat, day_temp, cmap='YlOrRd', shading='auto', alpha=0.85)
    cbar = plt.colorbar(temp_plot, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label('Avg Daytime Temp (°C)', fontsize=10)

    ax.scatter(non_aws_dcs['lon'], non_aws_dcs['lat'], c='grey', s=20, alpha=0.7, edgecolor='whitesmoke', linewidth=0.5, zorder=3)
    ax.scatter(aws_dcs['lon'], aws_dcs['lat'], c='black', s=40, marker='^', edgecolor='white', linewidth=0.8, zorder=4)

    # if not is_summary and dc_id:
    #     t_lat, t_lon = target_dc['lat'].values[0], target_dc['lon'].values[0]
    #     ax.add_patch(patches.Rectangle((t_lon - 0.04), t_lat - 0.04, 0.08, 0.08, linewidth=2.5, edgecolor='purple', facecolor='none', zorder=6))

    if not is_summary and dc_id:
        t_lat, t_lon = target_dc['lat'].values[0], target_dc['lon'].values[0]
        # Fixed parentheses: (t_lon - 0.04, t_lat - 0.04) are now grouped together as a tuple
        ax.add_patch(patches.Rectangle((t_lon - 0.04, t_lat - 0.04), 0.08, 0.08, linewidth=2.5, edgecolor='purple', facecolor='none', zorder=6))

    def format_lon(x, pos): return f"{abs(x):g}°W" if x < 0 else f"{x:g}°E"
    def format_lat(x, pos): return f"{x:g}°N" if x > 0 else f"{abs(x):g}°S"
    ax.xaxis.set_major_formatter(FuncFormatter(format_lon))
    ax.yaxis.set_major_formatter(FuncFormatter(format_lat))
    ax.tick_params(axis='both', labelsize=8)
    ax.set_xlim(ds.lon.min().values, ds.lon.max().values)
    ax.set_ylim(ds.lat.min().values, ds.lat.max().values)
    ax.grid(True, linestyle=':', color='black', alpha=0.3, zorder=1)
    ds.close()

def plot_failure_event_with_baselines(axes, ds_path, thresh_path, target_date_str, df, dc_id=None, is_summary=False, dc_list=None):
    ax1, ax2, ax3 = axes
    target_date = pd.to_datetime(target_date_str)
    start_date = target_date - pd.Timedelta(days=14)
    end_date = target_date + pd.Timedelta(days=3)
    month_str = target_date.strftime('%Y-%m')

    ds = xr.open_dataset(ds_path)
    ds_thresh = xr.open_dataset(thresh_path)

    if is_summary:
        dc_infos = df[df['id'].isin(dc_list)]
        lats, lons = xr.DataArray(dc_infos['lat'].values, dims='points'), xr.DataArray(dc_infos['lon'].values, dims='points')
        event_data = ds.sel(lat=lats, lon=lons, method='nearest').sel(time=slice(start_date, end_date))
        m_data = event_data.mean(dim='points')
        s_data = event_data.std(dim='points')
        times = m_data.time.values
    else:
        dc_lat, dc_lon = df[df['id'] == dc_id]['lat'].values[0], df[df['id'] == dc_id]['lon'].values[0]
        event_data = ds.sel(lat=dc_lat, lon=dc_lon, method='nearest').sel(time=slice(start_date, end_date))
        m_data = event_data # For single point, mean is just the data
        times = event_data.time.values
        monthly_thresh = ds_thresh.sel(lat=dc_lat, lon=dc_lon, quantile=0.90, method='nearest').sel(time=month_str).mean(dim='time')

    # CREATE DAYTIME SHIFT (Shift daytime values forward by 12 hours so they plot at 12 PM)
    day_times = times + pd.Timedelta(hours=12)

    # Plotting Lines and Ribbons
    # 1. Temp
    ax1.plot(day_times, m_data.DayTime_Avg_Tair, label='Day Avg', color='darkorange', linewidth=2)
    ax1.plot(times, m_data.NightTime_Avg_Tair, label='Night Avg', color='purple', linewidth=2)
    
    if is_summary:
        ax1.fill_between(day_times, m_data.DayTime_Avg_Tair - s_data.DayTime_Avg_Tair, m_data.DayTime_Avg_Tair + s_data.DayTime_Avg_Tair, color='darkorange', alpha=0.2)
        ax1.fill_between(times, m_data.NightTime_Avg_Tair - s_data.NightTime_Avg_Tair, m_data.NightTime_Avg_Tair + s_data.NightTime_Avg_Tair, color='purple', alpha=0.2)
    else:
        ax1.plot(day_times, event_data.DayTime_Tair_max, label='Day Max', color='firebrick', linestyle='--', alpha=0.4)
        ax1.plot(times, event_data.NightTime_Tair_max, label='Night Max', color='indigo', linestyle='--', alpha=0.4)
    
    ax1.set_ylabel('Temp (°C)', fontsize=9)
    ax1.set_title('Daily Build-up (14 Days Prior)' if not is_summary else 'Statewide Daily Build-up (Mean ± 1 SD)', fontsize=12, fontweight='bold')
    ax1.legend(loc='upper left', ncol=2 if not is_summary else 1, fontsize=7)
    ax1.set_ylim(10, 50); ax1.grid(True, alpha=0.3)

    # 2. Enthalpy
    ax2.plot(day_times, m_data.DayTime_Avg_enthalpy, color='darkorange', linewidth=2, label='Day Enthalpy')
    ax2.plot(times, m_data.NightTime_Avg_enthalpy, color='purple', linewidth=2, label='Night Enthalpy')
    
    if is_summary:
        ax2.fill_between(day_times, m_data.DayTime_Avg_enthalpy - s_data.DayTime_Avg_enthalpy, m_data.DayTime_Avg_enthalpy + s_data.DayTime_Avg_enthalpy, color='darkorange', alpha=0.2)
        ax2.fill_between(times, m_data.NightTime_Avg_enthalpy - s_data.NightTime_Avg_enthalpy, m_data.NightTime_Avg_enthalpy + s_data.NightTime_Avg_enthalpy, color='purple', alpha=0.2)
        
        # Add Thresholds (0.90, 0.95, 0.99)
        monthly_t_all = ds_thresh.sel(lat=lats, lon=lons, method='nearest').sel(time=month_str).mean(dim='time')
        d_c, n_c = {0.90: 'darkorange', 0.95: 'orangered', 0.99: 'red'}, {0.90: 'mediumpurple', 0.95: 'blueviolet', 0.99: 'indigo'}
        for q in [0.90, 0.95, 0.99]:
            try:
                q_d = monthly_t_all.sel(quantile=q)
                d_m, d_s = q_d.DayTime_Avg_enthalpy_thresholds.mean(dim='points').values, q_d.DayTime_Avg_enthalpy_thresholds.std(dim='points').values
                n_m, n_s = q_d.NightTime_Avg_enthalpy_thresholds.mean(dim='points').values, q_d.NightTime_Avg_enthalpy_thresholds.std(dim='points').values
                ax2.axhline(d_m, color=d_c[q], linestyle='-.', alpha=0.7)
                ax2.axhspan(d_m - d_s, d_m + d_s, color=d_c[q], alpha=0.1)
                ax2.axhline(n_m, color=n_c[q], linestyle='-.', alpha=0.7)
                ax2.axhspan(n_m - n_s, n_m + n_s, color=n_c[q], alpha=0.1)
            except: pass
        
        # Add ASHRAE Lines
        for ac in ASHRAE_CLASSES:
            h_max = get_max_enthalpy(ac['t'][1], ac['dp'][1])
            ax2.axhline(h_max, color=ac['color'], linestyle=':', linewidth=1.5)
            ax2.text(times[1], h_max + 0.5, f"A{ac['name'][1]} Max", color=ac['color'], fontsize=6, fontweight='bold')
    else:
        ax2.axhline(monthly_thresh.DayTime_Avg_enthalpy_thresholds.values, color='firebrick', linestyle='-.', linewidth=1.5, label='90th Pct (Day)')
        ax2.axhline(monthly_thresh.NightTime_Avg_enthalpy_thresholds.values, color='indigo', linestyle='-.', linewidth=1.5, label='90th Pct (Night)')
        
    ax2.set_ylabel('Enthalpy (kJ/kg)', fontsize=9)
    ax2.legend(loc='upper left', ncol=2, fontsize=7)
    ax2.set_ylim(20, 95); ax2.grid(True, alpha=0.3)

    # 3. Humidity
    ax3.plot(day_times, m_data.DayTime_Avg_Qair, color='darkorange', linewidth=2)
    ax3.plot(times, m_data.NightTime_Avg_Qair, color='purple', linewidth=2)
    
    if is_summary:
        ax3.fill_between(day_times, m_data.DayTime_Avg_Qair - s_data.DayTime_Avg_Qair, m_data.DayTime_Avg_Qair + s_data.DayTime_Avg_Qair, color='darkorange', alpha=0.2)
        ax3.fill_between(times, m_data.NightTime_Avg_Qair - s_data.NightTime_Avg_Qair, m_data.NightTime_Avg_Qair + s_data.NightTime_Avg_Qair, color='purple', alpha=0.2)
        
    ax3.set_ylabel('Qair (kg/kg)', fontsize=9)
    ax3.set_ylim(0.005, 0.02) 
    ax3.grid(True, alpha=0.3)

    for ax in axes: 
        ax.axvspan(target_date, target_date + pd.Timedelta(days=1), color='red', alpha=0.15)
        
    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
    ds.close(); ds_thresh.close()

def plot_hourly_failure_event(axes, hourly_path, thresh_path, target_date_str, df, dc_id=None, is_summary=False, dc_list=None):
    ax1, ax2, ax3 = axes
    target_date = pd.to_datetime(target_date_str)
    start_date = target_date - pd.Timedelta(days=14)
    end_date = target_date + pd.Timedelta(days=3)
    month_str = target_date.strftime('%Y-%m')

    ds_hourly, ds_thresh = xr.open_dataset(hourly_path), xr.open_dataset(thresh_path)

    if is_summary:
        dc_infos = df[df['id'].isin(dc_list)]
        lats, lons = xr.DataArray(dc_infos['lat'].values, dims='points'), xr.DataArray(dc_infos['lon'].values, dims='points')
        event_data = ds_hourly.sel(lat=lats, lon=lons, method='nearest').sel(time=slice(start_date, end_date)).load()
        m_data, s_data = event_data.mean(dim='points'), event_data.std(dim='points')
        times = m_data.time.values
    else:
        dc_lat, dc_lon = df[df['id'] == dc_id]['lat'].values[0], df[df['id'] == dc_id]['lon'].values[0]
        event_data = ds_hourly.sel(lat=dc_lat, lon=dc_lon, method='nearest').sel(time=slice(start_date, end_date)).load()
        m_data = event_data
        times = event_data.time.values
        monthly_thresh = ds_thresh.sel(lat=dc_lat, lon=dc_lon, quantile=0.90, method='nearest').sel(time=month_str).mean(dim='time')

    lc = 'teal'
    ax1.plot(times, m_data.Tair_C, color=lc, linewidth=1.5)
    if is_summary: ax1.fill_between(times, m_data.Tair_C - s_data.Tair_C, m_data.Tair_C + s_data.Tair_C, color=lc, alpha=0.2)
    ax1.set_ylabel('Temp (°C)', fontsize=9)
    ax1.set_title('Hourly Fluctuations (14 Days Prior)' if not is_summary else 'Statewide Hourly Build-up (Mean ± 1 SD)', fontsize=12, fontweight='bold')
    ax1.set_ylim(10, 50); ax1.grid(True, alpha=0.3)

    ax2.plot(times, m_data.enthalpy, color=lc, linewidth=1.5)
    if is_summary:
        ax2.fill_between(times, m_data.enthalpy - s_data.enthalpy, m_data.enthalpy + s_data.enthalpy, color=lc, alpha=0.2)
        monthly_t_all = ds_thresh.sel(lat=lats, lon=lons, method='nearest').sel(time=month_str).mean(dim='time')
        d_c, n_c = {0.90: 'darkorange', 0.95: 'orangered', 0.99: 'red'}, {0.90: 'mediumpurple', 0.95: 'blueviolet', 0.99: 'indigo'}
        for q in [0.90, 0.95, 0.99]:
            try:
                q_d = monthly_t_all.sel(quantile=q)
                d_m, d_s = q_d.DayTime_Avg_enthalpy_thresholds.mean(dim='points').values, q_d.DayTime_Avg_enthalpy_thresholds.std(dim='points').values
                n_m, n_s = q_d.NightTime_Avg_enthalpy_thresholds.mean(dim='points').values, q_d.NightTime_Avg_enthalpy_thresholds.std(dim='points').values
                ax2.axhspan(d_m - d_s, d_m + d_s, color=d_c[q], alpha=0.1)
                ax2.axhline(d_m, color=d_c[q], linestyle='-.', alpha=0.7)
                ax2.axhspan(n_m - n_s, n_m + n_s, color=n_c[q], alpha=0.1)
                ax2.axhline(n_m, color=n_c[q], linestyle='-.', alpha=0.7)
            except: pass
        for ac in ASHRAE_CLASSES:
            h_max = get_max_enthalpy(ac['t'][1], ac['dp'][1])
            ax2.axhline(h_max, color=ac['color'], linestyle=':', linewidth=1.5)
    else:
        ax2.axhline(monthly_thresh.DayTime_Avg_enthalpy_thresholds.values, color='firebrick', linestyle='-.', linewidth=1.5)
        ax2.axhline(monthly_thresh.NightTime_Avg_enthalpy_thresholds.values, color='midnightblue', linestyle='-.', linewidth=1.5)
        
    ax2.set_ylabel('Enthalpy', fontsize=9); ax2.set_ylim(20, 95); ax2.grid(True, alpha=0.3)

    ax3.plot(times, m_data.Qair, color=lc, linewidth=1.5)
    if is_summary: ax3.fill_between(times, m_data.Qair - s_data.Qair, m_data.Qair + s_data.Qair, color=lc, alpha=0.2)
    ax3.set_ylabel('Qair', fontsize=9); ax3.set_ylim(0.005, 0.02); ax3.grid(True, alpha=0.3)

    for ax in axes: ax.axvspan(target_date, target_date + pd.Timedelta(days=1), color='red', alpha=0.15)
    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
    ds_hourly.close(); ds_thresh.close()

def plot_rh_seasonal_envelope(axes, nc_path, target_date_str, df, dc_id=None, is_summary=False, dc_list=None):
    ax1, ax2 = axes
    bg_data = get_precomputed_ashrae_background(nc_path, target_date_str)
    
    with xr.open_dataset(nc_path) as ds:
        if is_summary:
            dc_infos = df[df['id'].isin(dc_list)]
            lats, lons = xr.DataArray(dc_infos['lat'].values, dims='points'), xr.DataArray(dc_infos['lon'].values, dims='points')
            tgt_ds = ds.sel(lat=lats, lon=lons, method='nearest').sel(time=target_date_str)
            
            tgt_day_t = tgt_ds['DayTime_Avg_Tair'].values
            tgt_day_rh = calc_rh(tgt_day_t, tgt_ds['DayTime_Avg_Qair'].values, tgt_ds['DayTime_Avg_PSurf'].values)
            dt_m, dt_s, dr_m, dr_s = np.nanmean(tgt_day_t), np.nanstd(tgt_day_t), np.nanmean(tgt_day_rh), np.nanstd(tgt_day_rh)

            tgt_nt_t = tgt_ds['NightTime_Avg_Tair'].values
            tgt_nt_rh = calc_rh(tgt_nt_t, tgt_ds['NightTime_Avg_Qair'].values, tgt_ds['NightTime_Avg_PSurf'].values)
            nt_m, nt_s, nr_m, nr_s = np.nanmean(tgt_nt_t), np.nanstd(tgt_nt_t), np.nanmean(tgt_nt_rh), np.nanstd(tgt_nt_rh)
            found_target = True
        else:
            dc_info = df[df['id'] == dc_id]
            if dc_info.empty: return
            try:
                tgt_ds = ds.sel(lat=dc_info['lat'].values[0], lon=dc_info['lon'].values[0], method='nearest').sel(time=target_date_str)
                found_target, tgt_day_t = True, tgt_ds['DayTime_Avg_Tair'].item()
                tgt_day_rh = calc_rh(tgt_day_t, tgt_ds['DayTime_Avg_Qair'].item(), tgt_ds['DayTime_Avg_PSurf'].item())
                tgt_night_t = tgt_ds['NightTime_Avg_Tair'].item()
                tgt_night_rh = calc_rh(tgt_night_t, tgt_ds['NightTime_Avg_Qair'].item(), tgt_ds['NightTime_Avg_PSurf'].item())
            except: found_target = False

    def format_panel(ax, H, xedges, yedges, title):
        H_masked = np.ma.masked_where(H < 1, H)
        ax.pcolormesh(xedges, yedges, H_masked.T, cmap='inferno', alpha=0.9, zorder=1, rasterized=True)
        for ac in ASHRAE_CLASSES:
            t_grid, b_bnd, t_bnd = get_ashrae_bounds(*ac['t'], *ac['rh'], *ac['dp'])
            ax.fill_between(t_grid, b_bnd, t_bnd, color=ac['color'], alpha=ac['alpha'], zorder=2)
            ax.plot(t_grid, t_bnd, color=ac['color'], linewidth=1, zorder=3)
            ax.plot(t_grid, b_bnd, color=ac['color'], linewidth=1, zorder=3)
            ax.plot([t_grid[0], t_grid[0]], [b_bnd[0], t_bnd[0]], color=ac['color'], linewidth=1.5, zorder=3)
            ax.plot([t_grid[-1], t_grid[-1]], [b_bnd[-1], t_bnd[-1]], color=ac['color'], linewidth=1.5, zorder=3)
        ax.set_title(title, fontsize=12, fontweight='bold')
        ax.set_xlim(-15, 50); ax.set_ylim(0, 100); ax.grid(alpha=0.3, linestyle='--')
        for i, t in enumerate([25, 30, 35, 40]): ax.text(t, 15, f'A{i+1}', color='darkgreen', fontsize=5, fontweight='bold')

    format_panel(ax1, bg_data['day_H'], bg_data['xedges'], bg_data['yedges'], "ASHRAE (Daytime)")
    ax1.set_xlabel('Temp (°C)', fontsize=9); ax1.set_ylabel('Relative Humidity (%)', fontsize=9)
    if found_target: 
        if is_summary: ax1.errorbar(dt_m, dr_m, xerr=dt_s, yerr=dr_s, fmt='*', color='#9f00ff', markersize=15, capsize=3, zorder=5)
        else: ax1.scatter(tgt_day_t, tgt_day_rh, color='#9f00ff', s=150, marker='*', zorder=5)

    format_panel(ax2, bg_data['night_H'], bg_data['xedges'], bg_data['yedges'], "ASHRAE (Nighttime)")
    ax2.set_xlabel('Temp (°C)', fontsize=9)
    if found_target: 
        if is_summary: ax2.errorbar(nt_m, nr_m, xerr=nt_s, yerr=nr_s, fmt='*', color='#9f00ff', markersize=15, capsize=3, zorder=5)
        else: ax2.scatter(tgt_night_t, tgt_night_rh, color='#9f00ff', s=150, marker='*', zorder=5)


# ==========================================
# 3. PDF GENERATION LOGIC 
# ==========================================
def draw_table(ax_table, stats, title):
    d_val = f"{stats['day_val']:.1f}" if np.isfinite(stats['day_val']) else "N/A"
    n_val = f"{stats['night_val']:.1f}" if np.isfinite(stats['night_val']) else "N/A"
    d_avg = f"{stats['day_hours'] / stats['day_cross']:.1f}" if stats['day_cross'] > 0 else "0.0"
    n_avg = f"{stats['night_hours'] / stats['night_cross']:.1f}" if stats['night_cross'] > 0 else "0.0"
    
    # Grab the new hourly max-min surge metrics
    s_before = f"+{stats['surge_day_before']:.1f}"
    s_of = f"+{stats['surge_day_of']:.1f}"
    
    table_data = [
        ['Daytime', d_val, f"{stats['day_cross']:.0f}", f"{stats['day_hours']:.0f}", d_avg, s_before, s_of],
        ['Nighttime', n_val, f"{stats['night_cross']:.0f}", f"{stats['night_hours']:.0f}", n_avg, s_before, s_of]
    ]
    
    # Updated column labels
    col_labels = ['Period', 'Threshold \n (kJ/kg)', 'Events \n (Crossings)', 'Total Hours \n Exceeded', 'Avg Hours / \n Event', 'Day Before \n Range (Max-Min)', 'Day Of \n Range (Max-Min)']

    ax_table.set_title(title, fontsize=10, fontweight='bold', pad=5)
    table = ax_table.table(cellText=table_data, colLabels=col_labels, loc='center', cellLoc='center', bbox=[0, 0, 1, 1])
    table.auto_set_font_size(False); table.set_fontsize(6); table.scale(1, 1.5) 
    
    for (i, j), cell in table.get_celld().items():
        if i == 0: cell.set_text_props(weight='bold', color='white'); cell.set_facecolor('#4c4c4c')
        else: cell.set_facecolor('#f2f2f2' if i % 2 == 0 else 'white')

        
def get_file_paths(state_abb):
    if state_abb == 'VA':
        return ('/discover/nobackup/cmbreen/datacenters/virginia_hourly/va_Daily_DayNight_Summary_CORRECTED.nc',
                '/discover/nobackup/cmbreen/datacenters/virginia_pure_hourly/va_Pure_Hourly_Summary_FIXED.nc',
                '/discover/nobackup/cmbreen/datacenters/virginia_hourly/va_daynight_threshold.nc')
    return ('/discover/nobackup/cmbreen/datacenters/texas_hourly/tx_Daily_DayNight_Summary_CORRECTED.nc',
            '/discover/nobackup/cmbreen/datacenters/texas_pure_hourly/tx_Pure_Hourly_Summary_FIXED.nc',
            '/discover/nobackup/cmbreen/datacenters/texas_hourly/tx_daynight_threshold.nc')

def generate_master_panel(pdf, target_date, df, state_abb, dc_id=None, is_summary=False, dc_list=None, all_stats=None):
    daily_nc, hourly_nc, thresh_nc = get_file_paths(state_abb)
    fig = plt.figure(figsize=(16, 9), dpi=150)
    gs = GridSpec(2, 2, figure=fig, width_ratios=[1, 1.2], height_ratios=[1, 1], wspace=0.15, hspace=0.25)
    
    if is_summary:
        fig.suptitle(f"STATEWIDE SUMMARY DASHBOARD | State: {state_abb} | Target Date: {target_date}", fontsize=18, fontweight='bold', y=0.96)
    else:
        operator = df[df['id'] == dc_id]['operator'].values[0]
        fig.suptitle(f"Datacenter Operations Dashboard | ID: {dc_id} ({operator}) | Target Date: {target_date}", fontsize=18, fontweight='bold', y=0.96)

    # 1. Top Left (Map & Table)
    gs_left = gs[0, 0].subgridspec(2, 2, height_ratios=[2.5, 1], width_ratios=[0.85, 0.15], hspace=0.4)
    ax_map = fig.add_subplot(gs_left[0, 0]); ax_table = fig.add_subplot(gs_left[1, :]); ax_table.axis('off')
    
    plot_datacenter_heat_map_tx(ax_map, target_date, df, daily_nc, dc_id=dc_id, is_summary=is_summary, dc_list=dc_list)

    if is_summary:
        avg_stats = {k: np.nanmean([s[k] for s in all_stats]) for k in all_stats[0].keys()}
        max_surge = avg_stats.get('max_hourly_jump', 0.0)
        draw_table(ax_table, avg_stats, f"Statewide Average - 14-Day Pre-Event Summary (Avg Max Surge: +{max_surge:.1f} kJ/kg)")
    else:
        dc_lat, dc_lon = df[df['id'] == dc_id]['lat'].values[0], df[df['id'] == dc_id]['lon'].values[0]
        stats = compute_threshold_stats(daily_nc, hourly_nc, thresh_nc, target_date, dc_lat, dc_lon)
        max_surge = stats.get('max_hourly_jump', 0.0)
        draw_table(ax_table, stats, f"14-Day Pre-Event Summary (Max Hourly Surge: +{max_surge:.1f} kJ/kg)")

    # 2. Top Right (Daily)
    gs_daily = gs[0, 1].subgridspec(3, 1, hspace=0.1)
    ax_d1, ax_d2, ax_d3 = fig.add_subplot(gs_daily[0, 0]), fig.add_subplot(gs_daily[1, 0]), fig.add_subplot(gs_daily[2, 0])
    plt.setp(ax_d1.get_xticklabels(), visible=False); plt.setp(ax_d2.get_xticklabels(), visible=False)
    plot_failure_event_with_baselines([ax_d1, ax_d2, ax_d3], daily_nc, thresh_nc, target_date, df, dc_id, is_summary, dc_list)

    # 3. Bottom Left (ASHRAE)
    gs_ashrae = gs[1, 0].subgridspec(1, 2, wspace=0.1)
    ax_a1, ax_a2 = fig.add_subplot(gs_ashrae[0, 0]), fig.add_subplot(gs_ashrae[0, 1])
    plt.setp(ax_a2.get_yticklabels(), visible=False)
    plot_rh_seasonal_envelope([ax_a1, ax_a2], daily_nc, target_date, df, dc_id, is_summary, dc_list)

    # 4. Bottom Right (Hourly)
    gs_hourly = gs[1, 1].subgridspec(3, 1, hspace=0.1)
    ax_h1, ax_h2, ax_h3 = fig.add_subplot(gs_hourly[0, 0]), fig.add_subplot(gs_hourly[1, 0]), fig.add_subplot(gs_hourly[2, 0])
    plt.setp(ax_h1.get_xticklabels(), visible=False); plt.setp(ax_h2.get_xticklabels(), visible=False)
    plot_hourly_failure_event([ax_h1, ax_h2, ax_h3], hourly_nc, thresh_nc, target_date, df, dc_id, is_summary, dc_list)

    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)
    return stats if not is_summary else None

# ==========================================
# 4. MAIN EXECUTION 
# ==========================================
if __name__ == "__main__":
    df = pd.read_csv('~/INNOVATE/im3_open_source_data_center_atlas_v2026.02.09.csv')
    
    tx_daily_nc = '/discover/nobackup/cmbreen/datacenters/texas_hourly/tx_Daily_DayNight_Summary_CORRECTED.nc'
    with xr.open_dataset(tx_daily_nc) as ds_tx:
        tx_min_lat, tx_max_lat = ds_tx.lat.min().item(), ds_tx.lat.max().item()
        tx_min_lon, tx_max_lon = ds_tx.lon.min().item(), ds_tx.lon.max().item()
    
    tx_df = df[(df['state_abb'] == 'TX') & (df['lat'] >= tx_min_lat) & (df['lat'] <= tx_max_lat) & (df['lon'] >= tx_min_lon) & (df['lon'] <= tx_max_lon)]
    tx_ids = tx_df['id'].tolist()
    
    aws_ops = ['Amazon Web Services', 'AWS', 'Amazon']
    va_ids = df[(df['state_abb'] == 'VA') & (df['operator'].isin(aws_ops))]['id'].tolist()

    target_events = [
        {"date": "2012-06-29", "state": "VA", "desc": "AWS_us-east-1"},
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
        print(f"\n{'='*50}\nCreating {output_pdf} ({len(dc_list)} individual pages + 1 Summary)\n{'='*50}")
        
        event_stats_list = []
        with PdfPages(output_pdf) as pdf:
            # 1. Generate Individual Panels
            for i, dc_id in enumerate(dc_list):
                print(f"  [{i+1}/{len(dc_list)}] Processing DC {dc_id} on {event_date}...")
                try:
                    stats = generate_master_panel(pdf, event_date, df, event_state, dc_id=dc_id, is_summary=False)
                    if stats: event_stats_list.append(stats)
                except Exception as e:
                    print(f"  -> ERROR plotting DC {dc_id}: {e}")
                    
            # 2. Generate Final Statewide Summary Panel
            if event_stats_list:
                print(f"  [+] Generating Statewide Summary Panel...")
                generate_master_panel(pdf, event_date, df, event_state, is_summary=True, dc_list=dc_list, all_stats=event_stats_list)

        print(f"-> Successfully saved {output_pdf}")