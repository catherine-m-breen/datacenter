import xarray as xr
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg') # Crucial for Discover
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import os
import warnings
warnings.filterwarnings('ignore')

# ==========================================
# 1. ASHRAE MATH & BOUNDS LOGIC
# ==========================================
def calc_sat_vapor_pressure(t_celsius): 
    """Returns Saturation Vapor Pressure in Pascals using the Magnus formula."""
    return 611.2 * np.exp((17.67 * t_celsius) / (t_celsius + 243.5))

def check_outside_ashrae(t, q, p, class_name='A1'):
    """
    Vectorized calculation to check if (Temp, Qair, PSurf) arrays fall OUTSIDE ASHRAE envelopes.
    Returns a Boolean array (True = Outside ASHRAE, False = Inside ASHRAE).
    """
    # ASHRAE Specifications: (T_min, T_max), (RH_min, RH_max), (DP_min, DP_max)
    bounds = {
        'A1': {'t': (15, 32), 'rh': (8, 80), 'dp': (-12, 17)}, # Recommended
        'A4': {'t': (5, 45),  'rh': (8, 90), 'dp': (-12, 24)}  # Max Allowable
    }
    b = bounds[class_name]

    # Calculate actual Vapor Pressure (e) and Relative Humidity (RH)
    w = q / (1.0 - q)
    e = (w * p) / (0.622 + w) # Vapor pressure in Pascals
    vp_sat = calc_sat_vapor_pressure(t)
    rh = np.clip((e / vp_sat) * 100.0, 0, 100)

    # Convert Dewpoint bounds to absolute Vapor Pressure limits
    vp_min = calc_sat_vapor_pressure(b['dp'][0])
    vp_max = calc_sat_vapor_pressure(b['dp'][1])

    # A point is inside if T, RH, and Dewpoint (Vapor Pressure) are ALL within bounds
    is_inside = (
        (t >= b['t'][0]) & (t <= b['t'][1]) &
        (rh >= b['rh'][0]) & (rh <= b['rh'][1]) &
        (e >= vp_min) & (e <= vp_max)
    )
    
    # We want probability of being OUTSIDE
    return ~is_inside 


# ==========================================
# 2. DATA PROCESSING ENGINE
# ==========================================
def process_region_probabilities(nc_path, df, state_abb, is_aws_only=False):
    """Pulls all datacenters via Xarray advanced indexing and computes seasonal probabilities."""
    print(f"Processing Data for {state_abb}...")
    
    # 1. Open Dataset and filter bounds to avoid edge-snapping errors
    with xr.open_dataset(nc_path) as ds:
        min_lat, max_lat = ds.lat.min().item(), ds.lat.max().item()
        min_lon, max_lon = ds.lon.min().item(), ds.lon.max().item()

    # 2. Filter DataFrame
    region_df = df[(df['state_abb'] == state_abb) & 
                   (df['lat'] >= min_lat) & (df['lat'] <= max_lat) & 
                   (df['lon'] >= min_lon) & (df['lon'] <= max_lon)]
    
    if is_aws_only:
        aws_ops = ['Amazon Web Services', 'AWS', 'Amazon']
        region_df = region_df[region_df['operator'].isin(aws_ops)]
        
    print(f" -> Found {len(region_df)} datacenters within spatial domain.")

    # 3. Fast extraction using Xarray DataArrays for lat/lon lists
    lats = xr.DataArray(region_df['lat'].values, dims='datacenter')
    lons = xr.DataArray(region_df['lon'].values, dims='datacenter')

    # Pulls a massive 2D array: (time, datacenter) in one quick sweep
    with xr.open_dataset(nc_path) as ds:
        ds_dc = ds.sel(lat=lats, lon=lons, method='nearest').load()

    # 4. Calculate Boolean Exceedance Matrices (True = Outside, False = Inside)
    # Resulting shape: (time, datacenter)
    day_t, day_q, day_p = ds_dc['DayTime_Avg_Tair'].values, ds_dc['DayTime_Avg_Qair'].values, ds_dc['DayTime_Avg_PSurf'].values
    night_t, night_q, night_p = ds_dc['NightTime_Avg_Tair'].values, ds_dc['NightTime_Avg_Qair'].values, ds_dc['NightTime_Avg_PSurf'].values

    # Ignore NaNs during the checks
    valid_day = np.isfinite(day_t)
    valid_night = np.isfinite(night_t)

    # Attach results back to the xarray dataset for easy seasonal groupby
    ds_dc['day_out_A1'] = (('time', 'datacenter'), check_outside_ashrae(day_t, day_q, day_p, 'A1') & valid_day)
    ds_dc['day_out_A4'] = (('time', 'datacenter'), check_outside_ashrae(day_t, day_q, day_p, 'A4') & valid_day)
    ds_dc['night_out_A1'] = (('time', 'datacenter'), check_outside_ashrae(night_t, night_q, night_p, 'A1') & valid_night)
    ds_dc['night_out_A4'] = (('time', 'datacenter'), check_outside_ashrae(night_t, night_q, night_p, 'A4') & valid_night)

    # 5. Group by Season and calculate overall probability (Mean)
    # First mean across time (by season), then mean across all datacenters
    prob_ds = ds_dc[['day_out_A1', 'day_out_A4', 'night_out_A1', 'night_out_A4']].groupby('time.season').mean(dim='time')
    prob_overall = prob_ds.mean(dim='datacenter') * 100.0 # Convert to percentage

    # Reorder seasons to chronological order
    season_order = ['DJF', 'MAM', 'JJA', 'SON']
    return prob_overall.sel(season=season_order)


# ==========================================
# 3. PLOTTING SCRIPT
# ==========================================
def plot_ashrae_probabilities(tx_data, va_data, output_pdf):
    print("Generating Plots...")
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), dpi=150)
    fig.subplots_adjust(hspace=0.3)
    
    seasons = ['Winter (DJF)', 'Spring (MAM)', 'Summer (JJA)', 'Fall (SON)']
    x = np.arange(len(seasons))
    width = 0.2  # Width of the bars

    def format_axis(ax, data, title):
        # Extract variables
        d_a1 = data['day_out_A1'].values
        n_a1 = data['night_out_A1'].values
        d_a4 = data['day_out_A4'].values
        n_a4 = data['night_out_A4'].values

        # Plot bars
        b1 = ax.bar(x - width*1.5, d_a1, width, label='Day (Outside A1 Recommended)', color='darkorange', alpha=0.8)
        b2 = ax.bar(x - width*0.5, d_a4, width, label='Day (Outside A4 Allowable)', color='darkorange', hatch='//', edgecolor='white')
        
        b3 = ax.bar(x + width*0.5, n_a1, width, label='Night (Outside A1 Recommended)', color='indigo', alpha=0.8)
        b4 = ax.bar(x + width*1.5, n_a4, width, label='Night (Outside A4 Allowable)', color='indigo', hatch='//', edgecolor='white')

        # Formatting
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_ylabel('Probability (%)', fontsize=11, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(seasons, fontsize=11)
        ax.set_ylim(0, 100)
        ax.grid(axis='y', linestyle='--', alpha=0.6)
        ax.legend(loc='upper right', fontsize=9, ncol=2)

        # Add percentage labels on top of bars
        for bars in [b1, b2, b3, b4]:
            for bar in bars:
                height = bar.get_height()
                if height > 0.5: # Don't label 0% bars to keep it clean
                    ax.annotate(f'{height:.1f}%', 
                                xy=(bar.get_x() + bar.get_width() / 2, height),
                                xytext=(0, 3), textcoords="offset points",
                                ha='center', va='bottom', fontsize=8, rotation=90)

    # Plot Texas and Virginia
    format_axis(ax1, tx_data, "Texas Datacenters: Probability of Falling Outside ASHRAE Boundaries")
    format_axis(ax2, va_data, "Virginia AWS Datacenters: Probability of Falling Outside ASHRAE Boundaries")

    with PdfPages(output_pdf) as pdf:
        pdf.savefig(fig, bbox_inches='tight')
    plt.close()
    print(f"-> Successfully saved {output_pdf}")


if __name__ == "__main__":
    # File Paths
    csv_path = '~/INNOVATE/im3_open_source_data_center_atlas_v2026.02.09.csv'
    tx_nc = '/discover/nobackup/cmbreen/datacenters/texas_hourly/tx_Daily_DayNight_Summary.nc'
    va_nc = '/discover/nobackup/cmbreen/datacenters/virginia_hourly/va_Daily_DayNight_Summary.nc'
    output_dir = '/discover/nobackup/cmbreen/datacenters/output_pdfs/'
    
    os.makedirs(output_dir, exist_ok=True)
    out_pdf = os.path.join(output_dir, 'ASHRAE_Seasonal_Probabilities.pdf')

    # Load Database
    print("Reading Datacenter CSV...")
    df = pd.read_csv(csv_path)

    # Process Data
    tx_results = process_region_probabilities(tx_nc, df, 'TX', is_aws_only=False)
    va_results = process_region_probabilities(va_nc, df, 'VA', is_aws_only=True)

    # Generate Chart
    plot_ashrae_probabilities(tx_results, va_results, out_pdf)