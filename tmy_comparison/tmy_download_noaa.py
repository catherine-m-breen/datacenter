# import pandas as pd
# import numpy as np
# import math
# import io

# # ==========================================
# # 1. CONFIGURATION
# # ==========================================
# INPUT_CSV = '/Users/cmbreen/Library/CloudStorage/OneDrive-NASA/oasis_datacenter/datasets/im3_open_source_data_center_atlas_v2026.02.09.csv'
# OUTPUT_CSV = 'datacenters_mapped_to_noaa.csv'

# # ==========================================
# # 2. LOAD OFFICIAL NOAA STATIONS
# # ==========================================
# # I embedded a sample of the stations from the manual you pasted. 
# # (To do all 1,972 stations, you would save Table S6 to a CSV and load it here!)
# noaa_stations_data = """Station_ID,Latitude,Longitude,Station_Name
# USW00014734,40.6828,-74.1692,NEWARK LIBERTY INTL AP
# USW00003812,35.4317,-82.5378,ASHEVILLE AP
# USW00014922,44.8853,-93.2314,MINNEAPOLIS-ST PAUL INTL AP
# USW00013874,33.6297,-84.4422,ATLANTA HARTSFIELD-JACKSON INT
# USW00023234,37.6197,-122.3656,SAN FRANCISCO INTL AP
# USW00012839,25.7881,-80.3169,MIAMI INTL AP
# USW00023062,39.8467,-104.6561,DENVER INTL AP
# USW00013968,36.1986,-95.8783,TULSA INTL AP
# USW00014739,42.3606,-71.0097,BOSTON
# """
# df_stations = pd.read_csv(io.StringIO(noaa_stations_data))

# # ==========================================
# # 3. HAVERSINE DISTANCE FUNCTION (in Miles)
# # ==========================================
# def calculate_distance(lat1, lon1, lat2, lon2):
#     R = 3958.8  # Radius of Earth in miles
#     dlat = math.radians(lat2 - lat1)
#     dlon = math.radians(lon2 - lon1)
#     a = (math.sin(dlat / 2) * math.sin(dlat / 2) +
#          math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
#          math.sin(dlon / 2) * math.sin(dlon / 2))
#     c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
#     return R * c

# # ==========================================
# # 4. LOAD DATACENTERS & FIND NEAREST STATION
# # ==========================================
# try:
#     df_dc = pd.read_csv(INPUT_CSV)
#     df_dc = df_dc[:10]  # Testing the first 10
#     print(f"Loaded {len(df_dc)} datacenters. Mapping to nearest NOAA stations...")
# except FileNotFoundError:
#     print(f"Error: Could not find {INPUT_CSV}.")
#     exit()

# # Lists to hold our results
# nearest_ids = []
# nearest_names = []
# nearest_distances = []
# noaa_filenames = []

# for index, dc in df_dc.iterrows():
#     dc_lat = dc['lat']
#     dc_lon = dc['lon']
    
#     min_dist = float('inf')
#     best_station = None
    
#     # Check distance to every NOAA station
#     for _, station in df_stations.iterrows():
#         dist = calculate_distance(dc_lat, dc_lon, station['Latitude'], station['Longitude'])
#         if dist < min_dist:
#             min_dist = dist
#             best_station = station
            
#     # Record the best match
#     nearest_ids.append(best_station['Station_ID'])
#     nearest_names.append(best_station['Station_Name'])
#     nearest_distances.append(round(min_dist, 2))
    
#     # Generate the exact filename specified in Section 5.2.1 of your manual!
#     filename = f"tmy-station_id-{best_station['Station_ID'].lower()}-time_period-199801-202212-weights-equal.csv"
#     noaa_filenames.append(filename)

# # Add the results back to your datacenter dataframe
# df_dc['NOAA_Station_ID'] = nearest_ids
# df_dc['NOAA_Station_Name'] = nearest_names
# df_dc['Distance_Miles'] = nearest_distances
# df_dc['NOAA_Filename'] = noaa_filenames

# # ==========================================
# # 5. SAVE AND PRINT RESULTS
# # ==========================================
# df_dc.to_csv(OUTPUT_CSV, index=False)
# print(f"\nSuccess! Mapping saved to {OUTPUT_CSV}\n")

# # Print a preview
# print(df_dc[['id', 'NOAA_Station_Name', 'Distance_Miles', 'NOAA_Filename']].head().to_string())

import os
import time
import logging
import pandas as pd
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configure Logging to track success/failure across 1,500 rows
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# --- CONFIGURATION ---
CSV_INPUT_PATH = '/Users/cmbreen/Library/CloudStorage/OneDrive-NASA/oasis_datacenter/datasets/im3_open_source_data_center_atlas_v2026.02.09.csv'
CSV_OUTPUT_PATH = "tmy_results.csv"       # Combined output target
NOAA_API_TOKEN = "WmQhDWC6TqGMTj9nhhkjtCQmTpgQRfdwtFd6q9LC"    # Get free token from NCEI if required
BASE_URL = "https://noaa.gov"

# NCEI limits change based on the endpoint. 
# Adjust MAX_WORKERS to prevent 429 (Too Many Requests) errors.
MAX_WORKERS = 3  
DELAY_BETWEEN_REQUESTS = 0.2  # Seconds to sleep between calls per thread

headers = {"token": NOAA_API_TOKEN}

def fetch_tmy_data(location_id, lat=None, lon=None):
    """
    Fetches weather data for a specific location. 
    Accepts NCEI Station IDs (e.g., 'GHCND:USW00014732') or coordinates.
    """
    # Build query params based on what your CSV provides
    params = {
        "datasetid": "GSOY",  # Global Summary of the Year (or change to your target TMY dataset ID)
        "startdate": "2025-01-01", 
        "enddate": "2025-12-31",
        "limit": 1000,
        "units": "standard"
    }
    
    if location_id:
        params["stationid"] = location_id
    elif lat and lon:
        # If searching by bounding box or coordinates instead of direct ID
        params["extent"] = f"{lat-0.1},{lon-0.1},{lat+0.1},{lon+0.1}"

    try:
        time.sleep(DELAY_BETWEEN_REQUESTS)  # Defensive throttling
        response = requests.get(BASE_URL, headers=headers, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            # Return list of data dictionaries if present
            return data.get("results", [])
        elif response.status_code == 429:
            logging.warning(f"Rate limit hit for {location_id}. Sleeping...")
            time.sleep(5)  # Backoff
            return []
        else:
            logging.error(f"Failed {location_id}: HTTP {response.status_code}")
            return []
            
    except Exception as e:
        logging.error(f"Exception fetching {location_id}: {str(e)}")
        return []

def main():
    # 1. Load your 1,500 locations
    if not os.path.exists(CSV_INPUT_PATH):
        logging.error(f"Input file {CSV_INPUT_PATH} not found.")
        return
        
    df_locations = pd.read_csv(CSV_INPUT_PATH)
    
    # Ensure columns exist (adapt these strings to match your CSV headers)
    # Assumes columns: 'station_id', 'latitude', 'longitude'
    all_results = []
    
    logging.info(f"Starting batch download for {len(df_locations)} rows...")

    # 2. Use a ThreadPool to process requests concurrently within safe limits
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit tasks
        future_to_loc = {
            executor.submit(
                fetch_tmy_data, 
                row.get("station_id", None), 
                row.get("latitude", None), 
                row.get("longitude", None)
            ): row for _, row in df_locations.iterrows()
        }
        
        # Process as they complete
        completed_count = 0
        for future in as_completed(future_to_loc):
            row_info = future_to_loc[future]
            completed_count += 1
            
            try:
                records = future.result()
                if records:
                    for record in records:
                        # Append original CSV metadata to the API result for tracking
                        record["input_station_id"] = row_info.get("station_id")
                        all_results.append(record)
                
                if completed_count % 50 == 0:
                    logging.info(f"Progress: {completed_count}/{len(df_locations)} locations processed.")
                    
            except Exception as exc:
                logging.error(f"Row generated an exception: {exc}")

    # 3. Export to aggregated CSV
    if all_results:
        df_output = pd.DataFrame(all_results)
        df_output.to_csv(CSV_OUTPUT_PATH, index=False)
        logging.info(f"Successfully saved {len(df_output)} climate rows to {CSV_OUTPUT_PATH}")
    else:
        logging.warning("No data retrieved.")

if __name__ == "__main__":
    main()
