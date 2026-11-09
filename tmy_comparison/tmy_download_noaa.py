import pandas as pd
import numpy as np
import math
import io

# ==========================================
# 1. CONFIGURATION
# ==========================================
INPUT_CSV = '/Users/cmbreen/Library/CloudStorage/OneDrive-NASA/oasis_datacenter/datasets/im3_open_source_data_center_atlas_v2026.02.09.csv'
OUTPUT_CSV = 'datacenters_mapped_to_noaa.csv'

# ==========================================
# 2. LOAD OFFICIAL NOAA STATIONS
# ==========================================
# I embedded a sample of the stations from the manual you pasted. 
# (To do all 1,972 stations, you would save Table S6 to a CSV and load it here!)
noaa_stations_data = """Station_ID,Latitude,Longitude,Station_Name
USW00014734,40.6828,-74.1692,NEWARK LIBERTY INTL AP
USW00003812,35.4317,-82.5378,ASHEVILLE AP
USW00014922,44.8853,-93.2314,MINNEAPOLIS-ST PAUL INTL AP
USW00013874,33.6297,-84.4422,ATLANTA HARTSFIELD-JACKSON INT
USW00023234,37.6197,-122.3656,SAN FRANCISCO INTL AP
USW00012839,25.7881,-80.3169,MIAMI INTL AP
USW00023062,39.8467,-104.6561,DENVER INTL AP
USW00013968,36.1986,-95.8783,TULSA INTL AP
USW00014739,42.3606,-71.0097,BOSTON
"""
df_stations = pd.read_csv(io.StringIO(noaa_stations_data))

# ==========================================
# 3. HAVERSINE DISTANCE FUNCTION (in Miles)
# ==========================================
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 3958.8  # Radius of Earth in miles
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) * math.sin(dlat / 2) +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) * math.sin(dlon / 2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# ==========================================
# 4. LOAD DATACENTERS & FIND NEAREST STATION
# ==========================================
try:
    df_dc = pd.read_csv(INPUT_CSV)
    df_dc = df_dc[:10]  # Testing the first 10
    print(f"Loaded {len(df_dc)} datacenters. Mapping to nearest NOAA stations...")
except FileNotFoundError:
    print(f"Error: Could not find {INPUT_CSV}.")
    exit()

# Lists to hold our results
nearest_ids = []
nearest_names = []
nearest_distances = []
noaa_filenames = []

for index, dc in df_dc.iterrows():
    dc_lat = dc['lat']
    dc_lon = dc['lon']
    
    min_dist = float('inf')
    best_station = None
    
    # Check distance to every NOAA station
    for _, station in df_stations.iterrows():
        dist = calculate_distance(dc_lat, dc_lon, station['Latitude'], station['Longitude'])
        if dist < min_dist:
            min_dist = dist
            best_station = station
            
    # Record the best match
    nearest_ids.append(best_station['Station_ID'])
    nearest_names.append(best_station['Station_Name'])
    nearest_distances.append(round(min_dist, 2))
    
    # Generate the exact filename specified in Section 5.2.1 of your manual!
    filename = f"tmy-station_id-{best_station['Station_ID'].lower()}-time_period-199801-202212-weights-equal.csv"
    noaa_filenames.append(filename)

# Add the results back to your datacenter dataframe
df_dc['NOAA_Station_ID'] = nearest_ids
df_dc['NOAA_Station_Name'] = nearest_names
df_dc['Distance_Miles'] = nearest_distances
df_dc['NOAA_Filename'] = noaa_filenames

# ==========================================
# 5. SAVE AND PRINT RESULTS
# ==========================================
df_dc.to_csv(OUTPUT_CSV, index=False)
print(f"\nSuccess! Mapping saved to {OUTPUT_CSV}\n")

# Print a preview
print(df_dc[['id', 'NOAA_Station_Name', 'Distance_Miles', 'NOAA_Filename']].head().to_string())