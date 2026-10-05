import xarray as xr
import pandas as pd
import numpy as np
import warnings
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score

warnings.filterwarnings('ignore') # Suppress nan/slice warnings

# ==========================================
# 1. FEATURE EXTRACTION FUNCTIONS
# ==========================================

def compute_14d_stats(hourly_ds, thresh_ds, target_date_str, dc_lat, dc_lon):
    """Calculates 14-day chronic stress features (hours over 90th pct & crossings)."""
    target_date = pd.to_datetime(target_date_str)
    start_date = target_date - pd.Timedelta(days=14)
    end_date_stats = target_date - pd.Timedelta(hours=1)
    
    try:
        hourly_data = hourly_ds.sel(lat=dc_lat, lon=dc_lon, method='nearest').sel(time=slice(start_date, end_date_stats)).load()
        enth = hourly_data.enthalpy.values
        
        month_str = target_date.strftime('%Y-%m')
        monthly_thresh = thresh_ds.sel(lat=dc_lat, lon=dc_lon, quantile=0.90, method='nearest').sel(time=month_str).mean(dim='time')
        
        day_t = float(monthly_thresh.DayTime_Avg_enthalpy_thresholds.values)
        night_t = float(monthly_thresh.NightTime_Avg_enthalpy_thresholds.values)
        
        day_hours, day_cross = 0, 0
        if len(enth) > 0 and np.isfinite(day_t):
            above = (enth > day_t).astype(int)
            day_hours = int(np.sum(above))
            crossings = np.sum(np.diff(above) == 1)
            if above[0] == 1: crossings += 1
            day_cross = int(crossings)
            
        return day_hours, day_cross
    except Exception as e:
        return np.nan, np.nan


def build_dataset(df, target_events, non_events):
    """Loops through datacenters and dates to build the ML dataframe."""
    
    # Define paths
    paths = {
        'VA': {
            'daily': '/discover/nobackup/cmbreen/datacenters/virginia_hourly/va_Daily_DayNight_Summary.nc',
            'hourly': '/discover/nobackup/cmbreen/datacenters/virginia_hourly/va_hourly_data.nc',
            'thresh': '/discover/nobackup/cmbreen/datacenters/virginia_hourly/va_daynight_threshold.nc'
        },
        'TX': {
            'daily': '/discover/nobackup/cmbreen/datacenters/texas_hourly/tx_Daily_DayNight_Summary.nc',
            'hourly': '/discover/nobackup/cmbreen/datacenters/texas_hourly/tx_hourly_data.nc',
            'thresh': '/discover/nobackup/cmbreen/datacenters/texas_hourly/tx_daynight_threshold.nc'
        }
    }
    
    dataset_rows = []
    all_events = target_events + non_events
    
    # Open datasets once per state to save massive amounts of I/O time
    ds_cache = {}
    for state in ['VA', 'TX']:
        print(f"Loading {state} NetCDF files into memory...")
        ds_cache[state] = {
            'daily': xr.open_dataset(paths[state]['daily']),
            'hourly': xr.open_dataset(paths[state]['hourly']),
            'thresh': xr.open_dataset(paths[state]['thresh'])
        }

    print("Extracting features for all dates...")
    for event in all_events:
        date_str, state, label, is_failure = event['date'], event['state'], event['desc'], event['is_fail']
        
        # Get appropriate datacenters
        if state == 'VA':
            aws_ops = ['Amazon Web Services', 'AWS', 'Amazon']
            dc_subset = df[(df['state_abb'] == 'VA') & (df['operator'].isin(aws_ops))]
        else:
            dc_subset = df[df['state_abb'] == 'TX']
            
        daily_ds = ds_cache[state]['daily']
        hourly_ds = ds_cache[state]['hourly']
        thresh_ds = ds_cache[state]['thresh']
        
        for _, dc in dc_subset.iterrows():
            dc_id, lat, lon = dc['id'], dc['lat'], dc['lon']
            
            try:
                # 1. Acute Features (Day of the event)
                point_daily = daily_ds.sel(lat=lat, lon=lon, method='nearest').sel(time=date_str)
                max_temp = float(point_daily['DayTime_Tair_max'].values)
                avg_enthalpy = float(point_daily['DayTime_Avg_enthalpy'].values)
                avg_qair = float(point_daily['DayTime_Avg_Qair'].values)
                
                # 2. Chronic Features (14 days prior)
                day_hours, day_cross = compute_14d_stats(hourly_ds, thresh_ds, date_str, lat, lon)
                
                dataset_rows.append({
                    'dc_id': dc_id,
                    'date': date_str,
                    'state': state,
                    'is_failure': is_failure,
                    'acute_max_temp_c': max_temp,
                    'acute_avg_enthalpy': avg_enthalpy,
                    'acute_avg_qair': avg_qair,
                    'chronic_14d_hours_above_90pct': day_hours,
                    'chronic_14d_threshold_crossings': day_cross
                })
            except Exception as e:
                # Skip if data is missing for this day/pixel
                continue
                
    # Close datasets
    for state in ds_cache:
        for ds in ds_cache[state].values(): ds.close()
        
    return pd.DataFrame(dataset_rows)


# ==========================================
# 2. MACHINE LEARNING & DRIVER ANALYSIS
# ==========================================

def run_driver_analysis(df_ml):
    print("\n" + "="*50)
    print(" DATACENTER FAILURE LIKELIHOOD MODEL RESULTS")
    print("="*50)
    
    # Drop rows with missing data
    df_ml = df_ml.dropna()
    print(f"Total valid Datacenter-Days modeled: {len(df_ml)}")
    print(f"  -> Failures (Y=1): {df_ml['is_failure'].sum()}")
    print(f"  -> Normal Days (Y=0): {len(df_ml) - df_ml['is_failure'].sum()}\n")
    
    # Define Features (X) and Target (Y)
    feature_cols = [
        'acute_max_temp_c', 
        'acute_avg_enthalpy', 
        'acute_avg_qair', 
        'chronic_14d_hours_above_90pct', 
        'chronic_14d_threshold_crossings'
    ]
    X = df_ml[feature_cols]
    y = df_ml['is_failure']
    
    # Scale the features (Crucial for Logistic Regression!)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    X_scaled_df = pd.DataFrame(X_scaled, columns=feature_cols)

    # --- MODEL 1: RANDOM FOREST ---
    rf = RandomForestClassifier(n_estimators=200, max_depth=5, random_state=42, class_weight='balanced')
    rf.fit(X, y)
    
    rf_importances = pd.Series(rf.feature_importances_, index=feature_cols).sort_values(ascending=False)
    
    print("--- 1. RANDOM FOREST: FEATURE IMPORTANCE ---")
    print("What matters most? (Sums to 100%)")
    for feat, imp in rf_importances.items():
        print(f"  {feat.ljust(35)} {imp*100:.1f}%")
    
    # --- MODEL 2: LOGISTIC REGRESSION ---
    lr = LogisticRegression(class_weight='balanced', random_state=42)
    lr.fit(X_scaled_df, y)
    
    # Calculate Odds Ratios (e^coef)
    odds_ratios = np.exp(lr.coef_[0])
    lr_results = pd.Series(odds_ratios, index=feature_cols).sort_values(ascending=False)
    
    print("\n--- 2. LOGISTIC REGRESSION: ODDS RATIOS ---")
    print("How much does a 1 Standard Deviation increase multiply the risk of failure?")
    for feat, odds in lr_results.items():
        # Interpretation text
        if odds > 1.5: impact = "STRONG Driver"
        elif odds > 1.1: impact = "Moderate Driver"
        elif odds < 0.9: impact = "Protective (Reduces Risk)"
        else: impact = "Negligible Impact"
        
        print(f"  {feat.ljust(35)} {odds:.2f}x ({impact})")
        
    print("\n(Note: An Odds Ratio of 2.0 means a 1 SD increase doubles the likelihood of failure.)")
    print("="*50 + "\n")


# ==========================================
# 3. MAIN EXECUTION
# ==========================================

if __name__ == "__main__":
    # Assume df is loaded
    # df = pd.read_csv('/path/to/your/datacenters.csv')
    
    # 1. Define Failures (Y = 1)
    target_events = [
        {"date": "2012-06-29", "state": "VA", "desc": "AWS_us-east-1", "is_fail": 1},
        {"date": "2018-09-04", "state": "TX", "desc": "San_Antonio_NA", "is_fail": 1},
        {"date": "2023-07-31", "state": "TX", "desc": "First_Major_Peak", "is_fail": 1},
        {"date": "2023-08-10", "state": "TX", "desc": "Summer_2023_Peak", "is_fail": 1},
        {"date": "2023-08-17", "state": "TX", "desc": "Late_Aug_Heatwave_1", "is_fail": 1},
        {"date": "2023-08-24", "state": "TX", "desc": "Late_Aug_Heatwave_2", "is_fail": 1},
        {"date": "2023-09-05", "state": "TX", "desc": "Sept_Heatwave", "is_fail": 1}
    ]
    
    # 2. Define Normal / Safe Baseline Days (Y = 0)
    # Note: I picked random dates from Spring/early Summer before heatwaves typically start
    non_events = [
        {"date": "2012-05-15", "state": "VA", "desc": "Spring_Baseline_1", "is_fail": 0},
        {"date": "2012-06-01", "state": "VA", "desc": "Spring_Baseline_2", "is_fail": 0},
        {"date": "2022-05-20", "state": "TX", "desc": "Spring_Baseline_3", "is_fail": 0},
        {"date": "2023-05-15", "state": "TX", "desc": "Spring_Baseline_4", "is_fail": 0},
        {"date": "2023-06-05", "state": "TX", "desc": "Spring_Baseline_5", "is_fail": 0},
        # Adding a few non-failure summer days to test model resilience
        {"date": "2022-08-01", "state": "TX", "desc": "Summer_Safe_1", "is_fail": 0}, 
        {"date": "2023-07-15", "state": "TX", "desc": "Summer_Safe_2", "is_fail": 0}
    ]
    
    print("Starting Datacenter Driver Analysis...")
    
    # Step A: Build Dataset (this will take a minute as it crunches the NetCDF arrays)
    df_ml = build_dataset(df, target_events, non_events)
    
    # Optional: Save it so you don't have to re-extract it later!
    df_ml.to_csv("datacenter_ml_features.csv", index=False)
    print("Saved extracted features to 'datacenter_ml_features.csv'")
    
    # Step B: Train Models & Output Insights
    run_driver_analysis(df_ml)