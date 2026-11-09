import os
import time
import pandas as pd
import pvlib
import tqdm

# ==========================================
# 1. CONFIGURATION - UPDATE THESE!
# ==========================================
API_KEY = 'WmQhDWC6TqGMTj9nhhkjtCQmTpgQRfdwtFd6q9LC' 
EMAIL = 'catherine.m.breen@nasa.gov'  
INPUT_CSV = '/Users/cmbreen/Library/CloudStorage/OneDrive-NASA/oasis_datacenter/datasets/im3_open_source_data_center_atlas_v2026.02.09.csv'
OUTPUT_DIR = 'tmy_data'  

# Create the output folder if it doesn't exist
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ==========================================
# 2. READ DATACENTER LOCATIONS
# ==========================================
try:
    df_locations = pd.read_csv(INPUT_CSV)
    print(f"Loaded {len(df_locations)} datacenter locations.")
except FileNotFoundError:
    print(f"Error: Could not find {INPUT_CSV}. Please check the file path.")
    exit()

# ==========================================
# 3. SORT TO PRIORITIZE TX, IL, OH, VA
# ==========================================
# Find the column that contains the state information (case-insensitive search)
state_col = None
for col in df_locations.columns:
    if 'state' in col.lower():
        state_col = col
        break

if state_col:
    # Handle both abbreviations and full names just in case
    priority_targets = ['TX', 'TEXAS', 'IL', 'ILLINOIS', 'OH', 'OHIO', 'VA', 'VIRGINIA']
    
    # Assign priority 0 to target states, priority 1 to everything else
    df_locations['sort_priority'] = df_locations[state_col].apply(
        lambda x: 0 if str(x).strip().upper() in priority_targets else 1
    )
    
    # Sort the dataframe so 0s are at the top, then reset the index
    df_locations = df_locations.sort_values(by='sort_priority').reset_index(drop=True)
    
    # Clean up the temporary column
    df_locations.drop(columns=['sort_priority'], inplace=True)
    
    print(f"Sorted datacenters to prioritize TX, IL, OH, and VA based on column '{state_col}'.")
else:
    print("WARNING: Could not find a 'state' column to prioritize by. Proceeding in default order.")

# ==========================================
# 4. DOWNLOAD LOOP USING PVLIB
# ==========================================
# Wrapping df_locations.iterrows() in tqdm gives us a beautiful progress bar!
for index, row in tqdm.tqdm(df_locations.iterrows(), total=len(df_locations)):
    site_id = row['id']
    lat = row['lat']
    lon = row['lon']
    
    file_path = os.path.join(OUTPUT_DIR, f"{site_id}_tmy.csv")
    
    # SMART SKIP: If we already downloaded this file, skip it! 
    # This saves your API limits and lets you resume if the script crashes.
    if os.path.exists(file_path):
        continue
    
    # Use tqdm.write instead of print so it doesn't break the progress bar visually
   # tqdm.tqdm.write(f"Fetching TMY data via pvlib for {site_id} (Lat: {lat}, Lon: {lon})...")
    
    try:
        tmy_df, metadata = pvlib.iotools.get_nsrdb_psm4_tmy(
            latitude=lat,
            longitude=lon,
            api_key=API_KEY,
            email=EMAIL,
            year='tmy',          
            time_step=60,        
            map_variables=True   
        )
        
        tmy_df.to_csv(file_path)
       # tqdm.tqdm.write(f"  -> Success! Saved to {file_path}")
        
    except Exception as e:
        tqdm.tqdm.write(f"  -> FAILED for {site_id}. Error details: {e}")
    
    # ==========================================
    # 5. RATE LIMIT PAUSE
    # ==========================================
    time.sleep(1)

print("\nFinished processing datacenters!")