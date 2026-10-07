import os
import warnings
import numpy as np
import pandas as pd
import xarray as xr

# CRITICAL FOR SLURM: Set backend before importing pyplot
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.gridspec import GridSpec

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
        # Defensively drop any duplicate time indices before interpolating
        ds_dc = ds_dc.drop_duplicates(dim='time')
        # Interpolate and load into memory
        ds_dc = ds_dc.interpolate_na(dim='time', method='linear').load()
        
    return ds_dc

# ==========================================
# 3. PLOTTING ENGINE
# ==========================================
def create_state_page(pdf, ds_dc, state_name):
    print(f"Generating PDF page for {state_name}...")
    fig = plt.figure(figsize=(24, 16), dpi=150)
    
    # Leave slightly more space on the right (wspace) for the colorbar
    gs = GridSpec(3, 4, figure=fig, height_ratios=[1, 1, 0.4], hspace=0.3, wspace=0.15)
    
    fig.suptitle(f"{state_name} Datacenters: Seasonal Psychrometric Analysis", fontsize=24, fontweight='bold', y=0.95)

    seasons = ['DJF', 'MAM', 'JJA', 'SON']
    season_names = ['Winter (DJF)', 'Spring (MAM)', 'Summer (JJA)', 'Fall (SON)']
    periods = [('Daytime', 'DayTime_Avg'), ('Nighttime', 'NightTime_Avg')]
    
    # Step 3a: Pre-calculate the data and find the MAXIMUM frequency across ALL panels.
    # This ensures our single colorbar perfectly maps across every season uniformly.
    panel_data = {}
    global_vmax = 1
    
    for row_idx, (p_name, p_prefix) in enumerate(periods):
        for col_idx, season in enumerate(seasons):
            ds_season = ds_dc.where(ds_dc['time'].dt.season == season, drop=True)
            t_raw = ds_season[f'{p_prefix}_Tair'].values.flatten()
            q_raw = ds_season[f'{p_prefix}_Qair'].values.flatten()
            p_raw = ds_season[f'{p_prefix}_PSurf'].values.flatten()
            
            valid = np.isfinite(t_raw) & np.isfinite(q_raw) & np.isfinite(p_raw)
            t, q, p_s = t_raw[valid], q_raw[valid], p_raw[valid]
            rh = get_rh(t, q, p_s)
            
            panel_data[(row_idx, col_idx)] = (t, q, p_s, rh)
            
            # Find the max density block for this panel
            counts, _, _ = np.histogram2d(t, rh, bins=[80, 80], range=[[-15, 50], [0, 100]])
            if counts.max() > global_vmax:
                global_vmax = counts.max()

    # Step 3b: Plot the heatmaps and ASHRAE envelopes
    table_data = []
    heatmap_axes = []
    
    for row_idx, (p_name, p_prefix) in enumerate(periods):
        for col_idx, season in enumerate(seasons):
            ax = fig.add_subplot(gs[row_idx, col_idx])
            heatmap_axes.append(ax)
            
            t, q, p_s, rh = panel_data[(row_idx, col_idx)]
            
            # Plot Heatmap USING our calculated global_vmax so all scales match
            counts, xedges, yedges, im = ax.hist2d(
                t, rh, bins=[80, 80], range=[[-15, 50], [0, 100]], 
                cmap='inferno', cmin=1, vmax=global_vmax, alpha=0.9
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
            
            # Labels and Limits
            ax.set_title(f"{p_name} | {season_names[col_idx]}", fontsize=14, fontweight='bold')
            ax.set_xlim(-15, 50)
            ax.set_ylim(0, 100)
            ax.grid(alpha=0.3, linestyle='--')
            
            if row_idx == 1: ax.set_xlabel('Temperature (°C)', fontsize=12)
            if col_idx == 0: ax.set_ylabel('Relative Humidity (%)', fontsize=12)

            # Calculate Probabilities for the Table
            probs = []
            for ac in ASHRAE_CLASSES[::-1]: # A1, A2, A3, A4
                out_bool = check_outside(t, q, p_s, ac)
                pct = (np.sum(out_bool) / len(t)) * 100 if len(t) > 0 else 0
                probs.append(f"{pct:.2f}%")
                
            table_data.append([p_name, season_names[col_idx]] + probs)

    # Add shared Colorbar spanning the height of the heatmaps
    cbar = fig.colorbar(im, ax=heatmap_axes, shrink=0.8, aspect=30, pad=0.02)
    cbar.set_label('Frequency of Occurrence', fontsize=14, fontweight='bold')
    cbar.ax.tick_params(labelsize=12)

    # Step 3c: Generate Probability Table
    ax_table = fig.add_subplot(gs[2, :])
    ax_table.axis('off')
    
    col_labels = ['Period', 'Season', 'Outside A1', 'Outside A2', 'Outside A3', 'Outside A4']
    table = ax_table.table(cellText=table_data, colLabels=col_labels, loc='center', cellLoc='center', bbox=[0.1, 0, 0.8, 1])
    
    table.auto_set_font_size(False)
    table.set_fontsize(12)
    
    for (i, j), cell in table.get_celld().items():
        if i == 0:
            cell.set_text_props(weight='bold', color='white')
            cell.set_facecolor('#4c4c4c')
        else:
            cell.set_facecolor('#f2f2f2' if i % 2 == 0 else 'white')

    pdf.savefig(fig, bbox_inches='tight')
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
    out_pdf = os.path.join(output_dir, 'ASHRAE_Seasonal_Matrix.pdf')

    print("Loading locations database...")
    df = pd.read_csv(csv_path)

    # Run for both states
    ds_va = extract_state_data(va_nc, df, 'VA', is_aws_only=False)
    ds_tx = extract_state_data(tx_nc, df, 'TX', is_aws_only=False)

    with PdfPages(out_pdf) as pdf:
        create_state_page(pdf, ds_va, "Virginia")
        create_state_page(pdf, ds_tx, "Texas")
        
    ds_va.close()
    ds_tx.close()
    
    print(f"Success! Matrix saved to: {out_pdf}")