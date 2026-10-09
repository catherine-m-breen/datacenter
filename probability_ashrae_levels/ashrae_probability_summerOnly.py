import os
import warnings
import numpy as np
import pandas as pd
import xarray as xr

# CRITICAL FOR SLURM: Set backend before importing pyplot
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

warnings.filterwarnings('ignore')

# ==========================================
# 1. ASHRAE DEFINITIONS & MATH
# ==========================================
ASHRAE_CLASSES = [
    {'name': 'A4', 't': (5, 45), 'rh': (8, 90), 'dp': (-12, 24), 'color': 'lightgreen', 'alpha': 0.15},
    {'name': 'A3', 't': (5, 40), 'rh': (8, 85), 'dp': (-12, 24), 'color': 'limegreen', 'alpha': 0.25},
    {'name': 'A2', 't': (10, 35), 'rh': (8, 80), 'dp': (-12, 21), 'color': 'forestgreen', 'alpha': 0.35},
    {'name': 'A1', 't': (15, 32), 'rh': (8, 80), 'dp': (-12, 17), 'color': 'darkgreen', 'alpha': 0.5}
]

def calc_sat_vapor_pressure(t_celsius):
    return 611.2 * np.exp((17.67 * t_celsius) / (t_celsius + 243.5))

def get_ashrae_bounds(t_min, t_max, rh_min, rh_max, dp_min, dp_max):
    t_grid = np.linspace(t_min, t_max, 200)
    vp_sat_grid = calc_sat_vapor_pressure(t_grid)
    
    rh_dp_min = (calc_sat_vapor_pressure(dp_min) / vp_sat_grid) * 100
    rh_dp_max = (calc_sat_vapor_pressure(dp_max) / vp_sat_grid) * 100
    
    b_bnd = np.maximum(rh_min, rh_dp_min)
    t_bnd = np.minimum(rh_max, rh_dp_max)
    return t_grid, b_bnd, t_bnd

def check_outside(t, q, p, ac):
    w = q / (1.0 - q)
    e = (w * p) / (0.622 + w)
    vp_sat = calc_sat_vapor_pressure(t)
    rh = np.clip((e / vp_sat) * 100.0, 0, 100)
    
    vp_min = calc_sat_vapor_pressure(ac['dp'][0])
    vp_max = calc_sat_vapor_pressure(ac['dp'][1])
    
    inside = (
        (t >= ac['t'][0]) & (t <= ac['t'][1]) &
        (rh >= ac['rh'][0]) & (rh <= ac['rh'][1]) &
        (e >= vp_min) & (e <= vp_max)
    )
    return ~inside

def get_rh(t, q, p):
    w = q / (1.0 - q)
    e = (w * p) / (0.622 + w)
    vp_sat = calc_sat_vapor_pressure(t)
    return np.clip((e / vp_sat) * 100.0, 0, 100)

# ==========================================
# 2. DATA PROCESSING
# ==========================================
def extract_state_data(nc_path, df, state_abb, is_aws_only=False):
    print(f"Loading {state_abb} data...")
    with xr.open_dataset(nc_path) as ds:
        min_lat, max_lat = ds.lat.min().item(), ds.lat.max().item()
        min_lon, max_lon = ds.lon.min().item(), ds.lon.max().item()

    region_df = df[(df['state_abb'] == state_abb) & 
                   (df['lat'] >= min_lat) & (df['lat'] <= max_lat) & 
                   (df['lon'] >= min_lon) & (df['lon'] <= max_lon)]
    
    if is_aws_only:
        aws_ops = ['Amazon Web Services', 'AWS', 'Amazon']
        region_df = region_df[region_df['operator'].isin(aws_ops)]

    lats = xr.DataArray(region_df['lat'].values, dims='datacenter')
    lons = xr.DataArray(region_df['lon'].values, dims='datacenter')

    with xr.open_dataset(nc_path) as ds:
        ds_dc = ds.sel(lat=lats, lon=lons, method='nearest')
        ds_dc = ds_dc.drop_duplicates(dim='time')
        ds_dc = ds_dc.interpolate_na(dim='time', method='linear').load()
        
    return ds_dc

def get_summer_daytime(ds):
    """Helper to extract JJA Daytime arrays."""
    ds_summer = ds.where(ds['time'].dt.season == 'JJA', drop=True)
    t_raw = ds_summer['DayTime_Avg_Tair'].values.flatten()
    q_raw = ds_summer['DayTime_Avg_Qair'].values.flatten()
    p_raw = ds_summer['DayTime_Avg_PSurf'].values.flatten()
    
    valid = np.isfinite(t_raw) & np.isfinite(q_raw) & np.isfinite(p_raw)
    t, q, p_s = t_raw[valid], q_raw[valid], p_raw[valid]
    rh = get_rh(t, q, p_s)
    
    return t, q, p_s, rh

# ==========================================
# 3. PLOTTING ENGINE
# ==========================================
def create_comparison_plot(ds_tx, ds_va, out_filepath):
    print("Generating comparison plot for Texas vs Virginia (Daytime Summer)...")
    
    fig, axes = plt.subplots(1, 2, figsize=(20, 8), dpi=150)
    fig.suptitle("Datacenters: Daytime Summer (JJA) Psychrometric Comparison", 
                 fontsize=22, fontweight='bold', y=0.98)

    states_data = [
        ("Texas", ds_tx, axes[0]),
        ("Virginia", ds_va, axes[1])
    ]

    for state_name, ds, ax in states_data:
        t, q, p_s, rh = get_summer_daytime(ds)
        
        # Plot Heatmap - using individual scale per state
        counts, xedges, yedges, im = ax.hist2d(
            t, rh, bins=[80, 80], range=[[-15, 50], [0, 100]], 
            cmap='inferno', cmin=1, alpha=0.9
        )
        
        # Draw all 4 ASHRAE Envelopes stacked
        for ac in ASHRAE_CLASSES:
            t_grid, b_bnd, t_bnd = get_ashrae_bounds(*ac['t'], *ac['rh'], *ac['dp'])
            ax.fill_between(t_grid, b_bnd, t_bnd, color=ac['color'], alpha=ac['alpha'], zorder=2)
            
            # Solid lines with vertical caps
            ax.plot(t_grid, t_bnd, color=ac['color'], linewidth=1.5, zorder=3)
            ax.plot(t_grid, b_bnd, color=ac['color'], linewidth=1.5, zorder=3)
            ax.plot([t_grid[0], t_grid[0]], [b_bnd[0], t_bnd[0]], color=ac['color'], linewidth=1.5, zorder=3)
            ax.plot([t_grid[-1], t_grid[-1]], [b_bnd[-1], t_bnd[-1]], color=ac['color'], linewidth=1.5, zorder=3)
        
        # Add a colorbar specific to this subplot
        cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cbar.set_label('Frequency of Occurrence', fontsize=12, fontweight='bold')
        
        # Formatting
        ax.set_title(f"{state_name}", fontsize=18, fontweight='bold')
        ax.set_xlim(-15, 50)
        ax.set_ylim(0, 100)
        ax.grid(alpha=0.3, linestyle='--')
        ax.set_xlabel('Temperature (°C)', fontsize=14)
        ax.set_ylabel('Relative Humidity (%)', fontsize=14)

        # Calculate Probabilities for Top Right Box
        stats_text = "Outside Distribution:\n"
        for ac in ASHRAE_CLASSES[::-1]: # Calculate from A1 down to A4
            out_bool = check_outside(t, q, p_s, ac)
            pct = (np.sum(out_bool) / len(t)) * 100 if len(t) > 0 else 0
            stats_text += f"{ac['name']}: {pct:.2f}%\n"
            
        # Add textbox in top right
        props = dict(boxstyle='round,pad=0.5', facecolor='white', alpha=0.85, edgecolor='gray')
        ax.text(0.96, 0.96, stats_text.strip(), transform=ax.transAxes, fontsize=12,
                verticalalignment='top', horizontalalignment='right', bbox=props, zorder=5, family='monospace')

    plt.tight_layout()
    # Adjust top to accommodate main suptitle
    plt.subplots_adjust(top=0.88)
    
    fig.savefig(out_filepath, bbox_inches='tight')
    plt.close(fig)

# ==========================================
# 4. MAIN EXECUTION
# ==========================================
if __name__ == "__main__":
    csv_path = '~/INNOVATE/im3_open_source_data_center_atlas_v2026.02.09.csv'
    va_nc = '/discover/nobackup/cmbreen/datacenters/virginia_hourly/va_Daily_DayNight_Summary_CORRECTED.nc'
    tx_nc = '/discover/nobackup/cmbreen/datacenters/texas_hourly/tx_Daily_DayNight_Summary_CORRECTED.nc'
    
    output_dir = '/discover/nobackup/cmbreen/datacenters/output_pdfs/'
    os.makedirs(output_dir, exist_ok=True)
    out_img = os.path.join(output_dir, 'ASHRAE_DaytimeSummer_Comparison.pdf')

    print("Loading locations database...")
    df = pd.read_csv(csv_path)

    # Run for both states
    ds_va = extract_state_data(va_nc, df, 'VA', is_aws_only=False)
    ds_tx = extract_state_data(tx_nc, df, 'TX', is_aws_only=False)

    # Generate single page plot
    create_comparison_plot(ds_tx, ds_va, out_img)
        
    ds_va.close()
    ds_tx.close()
    
    print(f"Success! Plot saved to: {out_img}")