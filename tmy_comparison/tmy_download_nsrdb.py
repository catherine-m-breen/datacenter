import pandas as pd
import requests
import os
import time
import IPython

# ==========================================
# 1. CONFIGURATION - UPDATE THESE!
# ==========================================
API_KEY = 'WmQhDWC6TqGMTj9nhhkjtCQmTpgQRfdwtFd6q9LC'  # Replace with your actual API key
EMAIL = 'catherine.m.breen@nasa.gov'  # Replace with the email you registered with
INPUT_CSV = '/Users/cmbreen/Library/CloudStorage/OneDrive-NASA/oasis_datacenter/datasets/im3_open_source_data_center_atlas_v2026.02.09.csv'  # The name of your spreadsheet
OUTPUT_DIR = 'tmy_data'  # Folder where all 1500 files will be saved

# Create the output folder if it doesn't exist
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ==========================================
# 2. READ DATACENTER LOCATIONS
# ==========================================
try:
    df = pd.read_csv(INPUT_CSV)
    #IPython.embed()
    df = df[:10]
    print(f"Loaded {len(df)} datacenter locations.")
except FileNotFoundError:
    print(f"Error: Could not find {INPUT_CSV}. Please ensure it is in the same folder.")
    exit()

# ==========================================
# 3. DOWNLOAD LOOP
# ==========================================
# The API endpoint for the NSRDB TMY data
url = "https://developer.nrel.gov/api/nsrdb/v2/solar/psm3-tmy-download.csv"

for index, row in df.iterrows():
    site_id = row['id']
    lat = row['lat']
    lon = row['lon']
    
    print(f"Downloading data for {site_id} (Lat: {lat}, Lon: {lon})...")
    
    # Define what data we are asking the API for
    params = {
        'api_key': API_KEY,
        'email': EMAIL,
        'names': 'tmy',          # This tells the database to get Typical Meteorological Year data
        'lat': lat,
        'lon': lon,
        'attributes': 'dew_point,temperature,pressure,wind_direction,wind_speed',
        'interval': '60'         # Hourly data; alternative is 30
    }
    
    try:
        response = requests.get(url, params=params)
        
        # If the request was successful (Status Code 200)
        if response.status_code == 200:
            file_path = os.path.join(OUTPUT_DIR, f"{site_id}_tmy.csv")
            with open(file_path, 'wb') as f:
                f.write(response.content)
            print(f"  -> Success! Saved to {file_path}")
        else:
            # If something went wrong, print the error message from the server
            print(f"  -> FAILED for {site_id}. Server said: {response.text}")

    except requests.exceptions.ConnectionError:
        print(f"  -> NETWORK ERROR! Could not reach NREL. Check your VPN, proxy, or internet connection.")
        break  # Stops the loop completely since there's no internet
    
    # ==========================================
    # 4. BE POLITE TO THE SERVER (RATE LIMITING)
    # ==========================================
    time.sleep(1)

print("\nFinished processing all datacenters!")