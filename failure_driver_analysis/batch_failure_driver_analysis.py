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
warnings.filterwarnings('ignore') # Suppress nan/slice warnings for cleaner logs

# ==========================================
# 1. REFACTORED PLOTTING FUNCTIONS 
# (Modified to accept specific `axes` instead of making their own figures)
# ==========================================

def plot_datacenter_heat_map_tx(ax, dc_id, target_date, df, ds_path):
    target_dc = df[df['id'] == dc_id]
    if target_dc.empty: return
        
    target_lat, target_lon = target_dc['lat'].values[0], target_dc['lon'].values[0]
    target_operator = target_dc['operator'].values[0]
    if pd.isna(target_operator): target_operator = f"Datacenter {dc_id}"

    # Get all datacenters for the state to plot in the background
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

    ax.scatter(non_aws_dcs['lon'], non_aws_dcs['lat'], c='grey', s=20, alpha=0.7, 
               edgecolor='whitesmoke', linewidth=0.5, label='Other DCs', zorder=3)
    ax.scatter(aws_dcs['lon'], aws_dcs['lat'], c='black', s=40, marker='^', 
               edgecolor='white', linewidth=0.8, label='AWS DCs', zorder=4)

    box_size = 0.08 
    highlight_box = patches.Rectangle(
        (target_lon - (box_size / 2), target_lat - (box_size / 2)), 
        box_size, box_size, linewidth=2.5, edgecolor='purple', 
        facecolor='none', zorder=6, label=f'Target: {target_operator}'
    )
    ax.add_patch(highlight_box)
    ax.legend(loc='upper left', framealpha=0.9, fontsize=8)

    def format_lon(x, pos): return f"{abs(x):g}°W" if x < 0 else f"{x:g}°E"
    def format_lat(x, pos): return f"{x:g}°N" if x > 0 else f"{abs(x):g}°S"
    ax.xaxis.set_major_formatter(FuncFormatter(format_lon))
    ax.yaxis.set_major_formatter(FuncFormatter(format_lat))
    ax.tick_params(axis='both', labelsize=8)

    ax.set_xlim(ds.lon.min().values, ds.lon.max().values)
    ax.set_ylim(ds.lat.min().values, ds.lat.max().values)
    ax.grid(True, linestyle=':', color='black', alpha=0.3, zorder=1)
    ds.close()

def plot_failure_event_with_baselines(axes, ds_path, target_date_str, dc_id, df):
    ax1, ax2, ax3 = axes
    dc_info = df[df['id'] == dc_id]
    if dc_info.empty: return
    dc_lat, dc_lon = dc_info['lat'].values[0], dc_info['lon'].values[0]

    target_date = pd.to_datetime(target_date_str)
    start_date = target_date - pd.Timedelta(days=14)
    end_date = target_date + pd.Timedelta(days=1)
    month_str = target_date.strftime('%Y-%m')

    ds = xr.open_dataset(ds_path)
    point_ds = ds.sel(lat=dc_lat, lon=dc_lon, method='nearest')
    event_data = point_ds.sel(time=slice(start_date, end_date))
    times = event_data.time.values

    thresh_path = ds_path.replace('Daily_DayNight_Summary.nc', 'daynight_threshold.nc')
    ds_thresh = xr.open_dataset(thresh_path)
    point_thresh = ds_thresh.sel(lat=dc_lat, lon=dc_lon, quantile=0.90, method='nearest')
    monthly_thresh = point_thresh.sel(time=month_str).mean(dim='time')
    
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
    ax1.grid(True, alpha=0.3)

    # Enthalpy
    ax2.axhline(day_thresh_val, color='firebrick', linestyle='-.', linewidth=1.5, label='90th Pct (Day)')
    ax2.axhline(night_thresh_val, color='indigo', linestyle='-.', linewidth=1.5, label='90th Pct (Night)')
    ax2.plot(times, event_data.DayTime_Avg_enthalpy, label='Day Avg Enthalpy', color='darkorange', linewidth=2)
    ax2.plot(times, event_data.NightTime_Avg_enthalpy, label='Night Avg Enthalpy', color='purple', linewidth=2)
    ax2.set_ylabel('Enthalpy (kJ/kg)', fontsize=9)
    ax2.legend(loc='upper left', ncol=2, fontsize=7)
    ax2.grid(True, alpha=0.3)

    # Humidity
    ax3.plot(times, event_data.DayTime_Avg_Qair, color='darkorange', linewidth=2)
    ax3.plot(times, event_data.NightTime_Avg_Qair, color='purple', linewidth=2)
    ax3.set_ylabel('Qair (kg/kg)', fontsize=9)
    ax3.grid(True, alpha=0.3)

    for ax in axes:
        ax.axvspan(target_date, target_date + pd.Timedelta(days=1), color='red', alpha=0.15)
        
    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
    ds.close(); ds_thresh.close()

def plot_hourly_failure_event(axes, hourly_path, target_date_str, dc_id, df):
    ax1, ax2, ax3 = axes
    dc_info = df[df['id'] == dc_id]
    if dc_info.empty: return
    dc_lat, dc_lon = dc_info['lat'].values[0], dc_info['lon'].values[0]

    target_date = pd.to_datetime(target_date_str)
    start_date = target_date - pd.Timedelta(days=14)
    end_date = target_date + pd.Timedelta(days=1)
    month_str = target_date.strftime('%Y-%m')

    thresh_path = hourly_path.replace('hourly_data.nc', 'daynight_threshold.nc')

    ds_hourly = xr.open_dataset(hourly_path)
    event_data = ds_hourly.sel(lat=dc_lat, lon=dc_lon, method='nearest').sel(time=slice(start_date, end_date)).load()
    times = event_data.time.values

    ds_thresh = xr.open_dataset(thresh_path)
    monthly_thresh = ds_thresh.sel(lat=dc_lat, lon=dc_lon, quantile=0.90, method='nearest').sel(time=month_str).mean(dim='time')
    
    line_color = 'teal'

    ax1.plot(times, event_data.Tair_C, color=line_color, linewidth=1.5)
    ax1.set_ylabel('Temp (°C)', fontsize=9)
    ax1.set_title('Hourly Fluctuations (14 Days Prior)', fontsize=12, fontweight='bold')
    ax1.grid(True, alpha=0.3)

    ax2.plot(times, event_data.enthalpy, color=line_color, linewidth=1.5)
    ax2.axhline(monthly_thresh.DayTime_Avg_enthalpy_thresholds.values, color='firebrick', linestyle='-.', linewidth=1.5)
    ax2.axhline(monthly_thresh.NightTime_Avg_enthalpy_thresholds.values, color='midnightblue', linestyle='-.', linewidth=1.5)
    ax2.set_ylabel('Enthalpy', fontsize=9)
    ax2.grid(True, alpha=0.3)

    ax3.plot(times, event_data.Qair, color=line_color, linewidth=1.5)
    ax3.set_ylabel('Qair', fontsize=9)
    ax3.grid(True, alpha=0.3)

    for ax in axes:
        ax.axvspan(target_date, target_date + pd.Timedelta(days=1), color='red', alpha=0.15)
        
    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
    ds_hourly.close(); ds_thresh.close()

# Helpers for ASHRAE
def calc_sat_vapor_pressure(t_celsius): return 611.2 * np.exp((17.67 * t_celsius) / (t_celsius + 243.5))
def calc_rh(t_air, q_air, p_surf):
    w = q_air / (1.0 - q_air)
    e = (w * p_surf) / (0.622 + w)
    return np.clip((e / calc_sat_vapor_pressure(t_air)) * 100.0, 0, 100)

def get_ashrae_bounds(t_min, t_max, rh_min, rh_max, dp_min, dp_max):
    t_grid = np.linspace(t_min, t_max, 200)
    vp_sat_grid = calc_sat_vapor_pressure(t_grid)
    top_bound = np.minimum(rh_max, (calc_sat_vapor_pressure(dp_max) / vp_sat_grid) * 100)
    bottom_bound = np.maximum(rh_min, (calc_sat_vapor_pressure(dp_min) / vp_sat_grid) * 100)
    return t_grid, bottom_bound, top_bound

def plot_rh_seasonal_envelope(axes, nc_path, target_date_str, dc_id, df):
    ax1, ax2 = axes
    target_date = pd.to_datetime(target_date_str)
    month = target_date.month
    season_code = 'DJF' if month in [12, 1, 2] else 'MAM' if month in [3, 4, 5] else 'JJA' if month in [6, 7, 8] else 'SON'
    
    dc_info = df[df['id'] == dc_id]
    if dc_info.empty: return
    dc_lat, dc_lon = dc_info['lat'].values[0], dc_info['lon'].values[0]

    ds = xr.open_dataset(nc_path)
    point_ds = ds.sel(lat=dc_lat, lon=dc_lon, method='nearest')
    ds_season = point_ds.isel(time=(point_ds['time'].dt.season == season_code))
    
    day_t = ds_season['DayTime_Avg_Tair'].values
    day_rh = calc_rh(day_t, ds_season['DayTime_Avg_Qair'].values, ds_season['DayTime_Avg_PSurf'].values)
    night_t = ds_season['NightTime_Avg_Tair'].values
    night_rh = calc_rh(night_t, ds_season['NightTime_Avg_Qair'].values, ds_season['NightTime_Avg_PSurf'].values)

    try:
        tgt_ds = point_ds.sel(time=target_date_str)
        tgt_day_t = tgt_ds['DayTime_Avg_Tair'].item()
        tgt_day_rh = calc_rh(tgt_day_t, tgt_ds['DayTime_Avg_Qair'].item(), tgt_ds['DayTime_Avg_PSurf'].item())
        tgt_night_t = tgt_ds['NightTime_Avg_Tair'].item()
        tgt_night_rh = calc_rh(tgt_night_t, tgt_ds['NightTime_Avg_Qair'].item(), tgt_ds['NightTime_Avg_PSurf'].item())
        found_target = True
    except KeyError:
        found_target = False

    ashrae_classes = [
        {'name': 'A4', 't': (5, 45), 'rh': (8, 90), 'dp': (-12, 24), 'color': 'lightgreen', 'alpha': 0.05},
        {'name': 'A3', 't': (5, 40), 'rh': (8, 85), 'dp': (-12, 24), 'color': 'limegreen', 'alpha': 0.05},
        {'name': 'A2', 't': (10, 35), 'rh': (8, 80), 'dp': (-12, 21), 'color': 'forestgreen', 'alpha': 0.05},
        {'name': 'A1', 't': (15, 32), 'rh': (8, 80), 'dp': (-12, 17), 'color': 'darkgreen', 'alpha': 0.05}
    ]

    def format_panel(ax, t_data, rh_data, title):
        valid = np.isfinite(t_data) & np.isfinite(rh_data)
        ax.hist2d(t_data[valid], rh_data[valid], bins=[50, 50], range=[[-15, 50], [0, 100]], cmap='inferno', cmin=1, alpha=0.9, zorder=1)
        
        for ac in ashrae_classes:
            t_grid, b_bnd, t_bnd = get_ashrae_bounds(*ac['t'], *ac['rh'], *ac['dp'])
            ax.fill_between(t_grid, b_bnd, t_bnd, color=ac['color'], alpha=ac['alpha'], zorder=2)
            ax.plot(t_grid, t_bnd, color=ac['color'], linewidth=1, zorder=3)
            ax.plot(t_grid, b_bnd, color=ac['color'], linewidth=1, zorder=3)

        ax.set_title(title, fontsize=12, fontweight='bold')
        ax.set_xlim(-15, 50)
        ax.set_ylim(0, 100)
        ax.grid(alpha=0.3, linestyle='--')
        ax.text(30, 15, 'A1', color='darkgreen', fontsize=7, fontweight='bold')
        ax.text(34, 15, 'A2', color='forestgreen', fontsize=7, fontweight='bold')

    format_panel(ax1, day_t, day_rh, "ASHRAE (Daytime)")
    ax1.set_xlabel('Temp (°C)', fontsize=9)
    ax1.set_ylabel('Relative Humidity (%)', fontsize=9)
    if found_target: ax1.scatter(tgt_day_t, tgt_day_rh, color='#9f00ff', s=150, marker='*', zorder=5)

    format_panel(ax2, night_t, night_rh, "ASHRAE (Nighttime)")
    ax2.set_xlabel('Temp (°C)', fontsize=9)
    if found_target: ax2.scatter(tgt_night_t, tgt_night_rh, color='#9f00ff', s=150, marker='*', zorder=5)
    
    ds.close()

# ==========================================
# 2. PDF GENERATION LOGIC 
# ==========================================

def generate_master_panel(pdf, dc_id, target_date, df, state_abb):
    """Creates a 16:9 master panel with 4 quadrants for a single DC/Date."""
    
    # Paths (adjust these based on how you have them structured on Discover)
    if state_abb == 'VA':
        daily_nc = '/discover/nobackup/cmbreen/datacenters/virginia_hourly/va_Daily_DayNight_Summary.nc'
        hourly_nc = '/discover/nobackup/cmbreen/datacenters/virginia_hourly/va_hourly_data.nc'
    else:
        daily_nc = '/discover/nobackup/cmbreen/datacenters/texas_hourly/tx_Daily_DayNight_Summary.nc'
        hourly_nc = '/discover/nobackup/cmbreen/datacenters/texas_hourly/tx_hourly_data.nc'

    # Setup 16:9 Figure
    fig = plt.figure(figsize=(16, 9), dpi=150)
    gs = GridSpec(2, 2, figure=fig, width_ratios=[1, 1.2], height_ratios=[1, 1], wspace=0.15, hspace=0.25)
    
    operator = df[df['id'] == dc_id]['operator'].values[0]
    fig.suptitle(f"Datacenter Operations Dashboard | ID: {dc_id} ({operator}) | Target Date: {target_date}", 
                 fontsize=18, fontweight='bold', y=0.96)

    # ----------------------------------------------------
    # Quadrant 1 (Top Left): Map
    # ----------------------------------------------------
    ax_map = fig.add_subplot(gs[0, 0])
    print(f"Plotting Map for DC {dc_id}...")
    plot_datacenter_heat_map_tx(ax_map, dc_id, target_date, df, daily_nc)

    # ----------------------------------------------------
    # Quadrant 2 (Top Right): Daily Build-Up
    # ----------------------------------------------------
    gs_daily = gs[0, 1].subgridspec(3, 1, hspace=0.1)
    ax_d1 = fig.add_subplot(gs_daily[0, 0])
    ax_d2 = fig.add_subplot(gs_daily[1, 0], sharex=ax_d1)
    ax_d3 = fig.add_subplot(gs_daily[2, 0], sharex=ax_d1)
    plt.setp(ax_d1.get_xticklabels(), visible=False)
    plt.setp(ax_d2.get_xticklabels(), visible=False)
    
    print(f"Plotting Daily Data for DC {dc_id}...")
    plot_failure_event_with_baselines([ax_d1, ax_d2, ax_d3], daily_nc, target_date, dc_id, df)

    # ----------------------------------------------------
    # Quadrant 3 (Bottom Left): ASHRAE Envelopes
    # ----------------------------------------------------
    gs_ashrae = gs[1, 0].subgridspec(1, 2, wspace=0.1)
    ax_a1 = fig.add_subplot(gs_ashrae[0, 0])
    ax_a2 = fig.add_subplot(gs_ashrae[0, 1], sharey=ax_a1)
    plt.setp(ax_a2.get_yticklabels(), visible=False)
    
    print(f"Plotting ASHRAE Envelopes for DC {dc_id}...")
    plot_rh_seasonal_envelope([ax_a1, ax_a2], daily_nc, target_date, dc_id, df)

    # ----------------------------------------------------
    # Quadrant 4 (Bottom Right): Hourly Build-Up
    # ----------------------------------------------------
    gs_hourly = gs[1, 1].subgridspec(3, 1, hspace=0.1)
    ax_h1 = fig.add_subplot(gs_hourly[0, 0])
    ax_h2 = fig.add_subplot(gs_hourly[1, 0], sharex=ax_h1)
    ax_h3 = fig.add_subplot(gs_hourly[2, 0], sharex=ax_h1)
    plt.setp(ax_h1.get_xticklabels(), visible=False)
    plt.setp(ax_h2.get_xticklabels(), visible=False)
    
    print(f"Plotting Hourly Data for DC {dc_id}...")
    plot_hourly_failure_event([ax_h1, ax_h2, ax_h3], hourly_nc, target_date, dc_id, df)

    # Save page to PDF
    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)

# ==========================================
# 3. MAIN EXECUTION (Subset Data & Create PDF)
# ==========================================

# ==========================================
# 3. MAIN EXECUTION (Separate PDF per Date)
# ==========================================

if __name__ == "__main__":
    # NOTE: Assume `df` is already loaded in your environment from your CSV
    df = pd.read_csv('~/INNOVATE/im3_open_source_data_center_atlas_v2026.02.09.csv')
    
    # 1. Identify Virginia AWS Datacenters
    aws_ops = ['Amazon Web Services', 'AWS', 'Amazon']
    va_ids = df[(df['state_abb'] == 'VA') & (df['operator'].isin(aws_ops))]['id'].tolist()
    
    # 2. Identify ALL Texas Datacenters
    tx_ids = df[df['state_abb'] == 'TX']['id'].tolist()

    # 3. Define the specific target dates and map them to their state and a file label.
    # For date ranges (e.g. Aug 17-20), we use the start date as the failure/event target.
    target_events = [
        {"date": "2012-06-29", "state": "VA", "desc": "AWS_us-east-1"},
        {"date": "2018-09-04", "state": "TX", "desc": "San_Antonio_NA"},
        {"date": "2023-07-31", "state": "TX", "desc": "First_Major_Peak"},
        {"date": "2023-08-10", "state": "TX", "desc": "Summer_2023_Peak"},
        {"date": "2023-08-17", "state": "TX", "desc": "Late_Aug_Heatwave_1"}, # Start of 17-20
        {"date": "2023-08-24", "state": "TX", "desc": "Late_Aug_Heatwave_2"}, # Start of 24-26
        {"date": "2023-09-05", "state": "TX", "desc": "Sept_Heatwave"}        # Start of 5-6
    ]

    # 4. Loop through each event and create a dedicated PDF
    for event in target_events:
        event_date = event["date"]
        event_state = event["state"]
        event_desc = event["desc"]
        
        # Assign the correct list of datacenters based on the state
        dc_list = va_ids if event_state == 'VA' else tx_ids
        
        # Name the PDF for this specific date
        output_pdf = f"Datacenter_Panels_{event_state}_{event_date}_{event_desc}.pdf"
        print(f"\n{'='*50}")
        print(f"Creating {output_pdf} ({len(dc_list)} pages)")
        print(f"{'='*50}")
        
        # Open a new PDF for this date
        with PdfPages(output_pdf) as pdf:
            for i, dc_id in enumerate(dc_list):
                print(f"  [{i+1}/{len(dc_list)}] Processing DC {dc_id} on {event_date}...")
                
                try:
                    # Use the master panel generator from the previous script
                    generate_master_panel(pdf, dc_id, event_date, df, event_state)
                except Exception as e:
                    print(f"  -> ERROR plotting DC {dc_id}: {e}")
                    # If one DC fails (e.g., data missing), keep going to the next one
                    continue 
                    
        print(f"-> Successfully saved {output_pdf}")
        
    print("\nAll PDFs have been successfully generated!")