## conda activate geospatial2

import pandas as pd
import numpy as np

### for product operations 
      ### we have to stay above -12dC or 8% RH, and below 80% RH, but cap completely if it is 17. 
A1 = {'dry_bulb_lower_degCelsius' : 15, 
      'dry_bulb_upper_degCelsius' : 32,
      'humdity_range_noncondensing'  : '-12d CP & 8% RH to 17 dC DP and 80% RH',
      'relative_humdity_lower_%'  : 8, 
      'relative_humdity_upper_%'  :80,
      'max_dew_point_celsius'  :17, 
      'maximum_elevation_m'  : 3050, 
      'maximum_temperature_change_in_an_hour_degrees'  : '5/20'
      }

A2 = {'dry_bulb_lower_degCelsius'  : 10, 
      'dry_bulb_upper_degCelsius'  : 35,
      'humdity_range_noncondensing'  :  '-12d CP & 8% RH to 21 dC DP and 80% RH',
      'relative_humdity_lower_%'  : 8, 
      'relative_humdity_upper_%'  : 80,
      'max_dew_point_celsius'  : 21, 
      'maximum_elevation'  : 3050, 
      'maximum_temperature_change_in_an_hour_degrees'  :'5/20'
      }

A3 = {'dry_bulb_lower_degCelsius'  : 5, 
      'dry_bulb_upper_degCelsius'  : 40,
      'humdity_range_noncondensing'  :  '-12d CP & 8% RH to 24 dC DP and 85% RH',
      'relative_humdity_lower_%'  : 8, 
      'relative_humdity_upper_%'  : 85,
      'max_dew_point_celsius'  : 24, 
      'maximum_elevation_m'  : 3050, 
      'maximum_temperature_change_in_an_hour_degrees'  : '5/20'
      }

A4 = {'dry_bulb_lower_degCelsius'  :5, 
      'dry_bulb_upper_degCelsius'  : 45,
      'humdity_range_noncondensing'  : '-12d CP & 8% RH to 24 dC DP and 90% RH',
        'relative_humdity_lower_%'  : 8, 
      'relative_humdity_upper_%'  : 90,
      'max_dew_point_celsius'  : 24, 
      'maximum_elevation_m'  : 3050, 
      'maximum_temperature_change_in_an_hour_degrees'  :'5/20'
      }



def check_ashrae_violations(tair, q, psurf, config):
    """
    Evaluates NLDAS-3 arrays for ASHRAE compliance using a sequential system of expressions.
    
    Parameters:
    tair (array): Near-surface air temperature in KELVIN from NLDAS-3
    q (array): Near-surface specific humidity in KG/KG from NLDAS-3
    psurf (array): Surface pressure in PASCALS from NLDAS-3
    config (dict): One of your exact dictionary configurations (a1, A2, A3, A4)
    
    Returns:
    dict: A dictionary containing individual binary masks for each type of violation, 
          plus a global 'any_violation' mask. (True = Violated / Non-compliant)
    """
    # --- Step 1: Standardize Pixel Inputs to Metric ---
    T = tair - 273.15   # Convert Kelvin to Celsius
    P_kpa = psurf / 1000.0  # Convert Pascals to kPa
    
    # --- Step 2: Calculate Vapor Pressures (CalcEngineer Formulas) ---
    # Saturation Vapor Pressure (p_ws) at the current pixel temperature
    p_ws = 0.61094 * np.exp(17.625 * T / (T + 243.04))
    
    # Actual Vapor Pressure (p_w) derived directly from NLDAS-3 Specific Humidity
    p_w_actual = (q * P_kpa) / (0.62198 + 0.37802 * q)
    
    # --- Step 3: Run the System of Checks ---
    
    # Check 1: Dry Bulb Temperature Bounds
    too_cold = T < config['dry_bulb_lower_degCelsius']
    too_hot = T > config['dry_bulb_upper_degCelsius']
    temp_violation = too_cold | too_hot
    
    # Check 2: Moisture Floor Bounds (ASHRAE Lower Limit)
    # Vapor pressure at the hard -12°C Dew Point floor
    p_w_dp_min = 0.61094 * np.exp(17.625 * -12.0 / (-12.0 + 243.04))
    # Shifting 8% Relative Humidity floor pressure
    p_w_rh_min = (config['relative_humdity_lower_%'] / 100.0) * p_ws
    # Strictest limit is the maximum pressure of the two rules
    # (Using np.maximum to ensure element-wise array evaluation)
    p_w_lower_limit = np.maximum(p_w_dp_min, p_w_rh_min)
    floor_violation = p_w_actual < p_w_lower_limit
    
    # Check 3: Moisture Ceiling Bounds (ASHRAE Upper Limit)
    # Vapor pressure at your config's specific max dew point ceiling
    p_w_dp_max = 0.61094 * np.exp(17.625 * config['max_dew_point_celsius'] / (config['max_dew_point_celsius'] + 243.04))
    # Shifting upper Relative Humidity ceiling pressure (e.g., 80%, 85%, 90%)
    p_w_rh_max = (config['relative_humdity_upper_%'] / 100.0) * p_ws
    # Strictest limit is the minimum pressure of the two rules ("cap completely")
    p_w_upper_limit = np.minimum(p_w_dp_max, p_w_rh_max)
    ceiling_violation = p_w_actual > p_w_upper_limit
    
    # --- Step 4: Final Evaluation Aggregation ---
    # Global flag is True if ANY individual rule fails
    any_violation = temp_violation | floor_violation | ceiling_violation
    
    return {
        'temperature_violation': temp_violation,
        'moisture_floor_violation': floor_violation,
        'moisture_ceiling_violation': ceiling_violation,
        'any_violation': any_violation
    }

# --- Quick Test Execution ---
# Mocking a pixel array representing hot, highly humid weather over a grid
mock_tair = np.array([308.15])   # 35°C in Kelvin
mock_q = np.array([0.025])       # High humidity
mock_psurf = np.array([101325.0]) # Sea level pressure

# Let's test it against Class a1 rules
results = check_ashrae_violations(mock_tair, mock_q, mock_psurf, config=A2)

print("Check results for this grid point (True means a violation occurred):")
print(f"-> Temperature Violated? {results['temperature_violation'][0]}")
print(f"-> Moisture Floor Violated? {results['moisture_floor_violation'][0]}")
print(f"-> Moisture Ceiling Violated? {results['moisture_ceiling_violation'][0]}")
print(f"-> Fails ASHRAE Envelope entirely? {results['any_violation'][0]}")
