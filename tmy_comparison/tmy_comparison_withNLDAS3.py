import pandas as pd
import numpy as np
import psychrolib

# Set psychrolib to use SI units (Celsius, Pascals, kg/kg)
psychrolib.SetUnitSystem(psychrolib.SI)

def calculate_psychrometrics(df):
    """
    Calculates Wet Bulb and Enthalpy from NLDAS-3 standard variables.
    Assumes df has columns: 'Temp_C', 'Pressure_Pa', 'Specific_Humidity_kg_kg'
    """
    print("Calculating thermodynamic variables...")
    
    # Pre-allocate lists for speed
    wet_bulbs = []
    enthalpies = []
    
    # Iterate through rows. Note: For 1480 datacenters x 25 years, 
    # you may want to parallelize this step using Dask or multiprocessing later.
    for _, row in df.iterrows():
        tdb = row['Temp_C']
        pressure = row['Pressure_Pa']
        q = row['Specific_Humidity_kg_kg']
        
        # Convert specific humidity (q) to humidity ratio (W)
        # W = q / (1 - q)
        w = q / (1 - q)
        
        try:
            # Calculate Wet Bulb (Celsius) and Enthalpy (Joules per kg)
            twb = psychrolib.GetTWetBulbFromHumRatio(tdb, w, pressure)
            # Convert Enthalpy from J/kg to kJ/kg for easier reading
            enth = psychrolib.GetMoistAirEnthalpy(tdb, w) / 1000.0 
        except:
            twb, enth = np.nan, np.nan # Handle impossible atmospheric states
            
        wet_bulbs.append(twb)
        enthalpies.append(enth)
        
    df['WetBulb_C'] = wet_bulbs
    df['Enthalpy_kJ_kg'] = enthalpies
    
    return df

def get_nldas_percentiles(nldas_df):
    """
    Groups 25 years of NLDAS data by Month and Hour, 
    and extracts the 90th, 95th, and 99th percentiles.
    Assumes the DataFrame index is a datetime object.
    """
    print("Calculating Month-Hour percentiles for NLDAS-3...")
    
    # Extract Month and Hour from the datetime index
    nldas_df['Month'] = nldas_df.index.month
    nldas_df['Hour'] = nldas_df.index.hour
    
    # Group by Month and Hour and calculate quantiles
    quantiles = nldas_df.groupby(['Month', 'Hour'])[['Temp_C', 'WetBulb_C', 'Enthalpy_kJ_kg']].quantile([0.90, 0.95, 0.99])
    
    # Unstack the quantiles so they become columns (e.g., 'Temp_C_0.90')
    quantiles = quantiles.unstack(level=-1)
    
    # Clean up column names for readability
    quantiles.columns = [f"{var}_{int(pct*100)}th" for var, pct in quantiles.columns]
    
    return quantiles.reset_index()

def process_tmy_data(tmy_df):
    """
    Processes TMY data for the same Month-Hour comparison.
    Assumes TMY data is for 1 year (8760 hours) and index is datetime.
    """
    print("Processing TMY data...")
    tmy_df['Month'] = tmy_df.index.month
    tmy_df['Hour'] = tmy_df.index.hour
    
    # TMY is already a "typical" representation, so we just group by month/hour 
    # to get the typical values for that specific block. We take the mean in case 
    # of slight variations, though usually there is only one value per month-hour in TMY.
    tmy_grouped = tmy_df.groupby(['Month', 'Hour'])[['Temp_C', 'WetBulb_C', 'Enthalpy_kJ_kg']].mean()
    
    # Rename for clarity
    tmy_grouped.columns = [f"{col}_TMY" for col in tmy_grouped.columns]
    
    return tmy_grouped.reset_index()

def compare_datasets(nldas_df, tmy_df):
    """
    Master function to run the pipeline for a single datacenter.
    """
    # 1. Add psychrometrics to NLDAS-3 (assuming TMY already has it or you run it on TMY too)
    nldas_processed = calculate_psychrometrics(nldas_df)
    
    # 2. Get NLDAS percentiles
    nldas_stats = get_nldas_percentiles(nldas_processed)
    
    # 3. Process TMY
    tmy_stats = process_tmy_data(tmy_df)
    
    # 4. Merge them together on Month and Hour
    comparison_df = pd.merge(tmy_stats, nldas_stats, on=['Month', 'Hour'])
    
    # 5. Calculate the Volatility Gaps (Difference between NLDAS 99th and TMY)
    comparison_df['DryBulb_Gap_99th'] = comparison_df['Temp_C_99th'] - comparison_df['Temp_C_TMY']
    comparison_df['WetBulb_Gap_99th'] = comparison_df['WetBulb_C_99th'] - comparison_df['WetBulb_C_TMY']
    comparison_df['Enthalpy_Gap_99th'] = comparison_df['Enthalpy_kJ_kg_99th'] - comparison_df['Enthalpy_kJ_kg_TMY']
    
    return comparison_df

# =========================================================
# EXAMPLE USAGE:
# =========================================================
if __name__ == "__main__":
    # Simulate a few hours of NLDAS-3 data for demonstration
    dates = pd.date_range("2000-01-01", "2025-12-31 23:00", freq="H")
    # Make a dummy dataframe of size ~227,904 rows
    # (In reality, load your NLDAS-3 CSV/NetCDF here)
    nldas_mock = pd.DataFrame({
        'Temp_C': np.random.normal(20, 10, len(dates)),
        'Pressure_Pa': np.random.normal(101325, 500, len(dates)),
        'Specific_Humidity_kg_kg': np.random.uniform(0.005, 0.015, len(dates))
    }, index=dates)

    # Note: Because applying psychrolib row-by-row on 25 years of data takes a minute, 
    # we'll slice just a small piece for this quick mock test
    nldas_mock = nldas_mock.iloc[:1000] 

    # Simulate 1 year of TMY data (8760 hours)
    tmy_dates = pd.date_range("2024-01-01", "2024-12-31 23:00", freq="H")
    tmy_mock = pd.DataFrame({
        'Temp_C': np.random.normal(18, 8, len(tmy_dates)),
        'WetBulb_C': np.random.normal(15, 5, len(tmy_dates)),
        'Enthalpy_kJ_kg': np.random.normal(45, 10, len(tmy_dates))
    }, index=tmy_dates)

    # Run the comparison
    final_comparison = compare_datasets(nldas_mock, tmy_mock)
    
    print("\nComparison complete! Here is a sample of Month-Hour gaps:")
    # Look specifically at summer afternoon (July, Hour 15 / 3:00 PM)
    print(final_comparison[(final_comparison['Month'] == 7) & (final_comparison['Hour'] == 15)].head())