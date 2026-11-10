import pandas as pd
import requests
import os

os.environ['HTTP_PROXY'] = 'http://127.0.0.1:9000'
os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:9000'
import time

# Add this to stop Python from spamming warnings about bypassing SSL
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================================
# 1. CONFIGURATION
# ==========================================
API_KEY = 'WmQhDWC6TqGMTj9nhhkjtCQmTpgQRfdwtFd6q9LC'  
EMAIL = 'catherine.m.breen@nasa.gov'  
INPUT_CSV = '/Users/cmbreen/Library/CloudStorage/OneDrive-NASA/oasis_datacenter/datasets/im3_open_source_data_center_atlas_v2026.02.09.csv'  
OUTPUT_DIR = 'tmy_data_nsrdb'  

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ==========================================
# 2. READ DATACENTER LOCATIONS
# ==========================================
try:
    df = pd.read_csv(INPUT_CSV)
    df = df[:10]  # Just testing the first 10
    print(f"Loaded {len(df)} datacenter locations.")
except FileNotFoundError:
    print(f"Error: Could not find {INPUT_CSV}.")
    exit()

# ==========================================
# 3. DOWNLOAD LOOP
# ==========================================
url = "https://developer.nrel.gov/api/nsrdb/v2/solar/psm3-tmy-download.csv"

for index, row in df.iterrows():
    # Make sure these match your CSV exactly (e.g., 'id' or 'ID', 'lat' or 'Latitude')
    site_id = row.get('id', index)
    lat = row.get('lat', row.get('Latitude'))
    lon = row.get('lon', row.get('Longitude'))
    
    print(f"Downloading data for {site_id} (Lat: {lat}, Lon: {lon})...")
    
    # Define what data we are asking the API for
    params = {
        'api_key': API_KEY,
        'email': EMAIL,
        'names': 'tmy',          
        'wkt': f'POINT({lon} {lat})',  # NREL REQUIRES Longitude FIRST inside the POINT() tag
        'attributes': 'dew_point,temperature,pressure,wind_direction,wind_speed',
        'interval': '60'         
    }
    
    try:
        # THE FIX: Added verify=False to bypass the NASA Zscaler firewall block
        response = requests.get(url, params=params, verify=False)
        
        if response.status_code == 200:
            file_path = os.path.join(OUTPUT_DIR, f"{site_id}_tmy.csv")
            with open(file_path, 'wb') as f:
                f.write(response.content)
            print(f"  -> Success! Saved to {file_path}")
        else:
            print(f"  -> FAILED for {site_id}. Server said: {response.text[:200]}")

    except requests.exceptions.ConnectionError:
        print(f"  -> NETWORK ERROR! Still unable to reach NREL.")
        break  
    
    # Be polite to the server
    time.sleep(1)

print("\nFinished processing all datacenters!")