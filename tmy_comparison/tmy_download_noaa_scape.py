# import pandas as pd
# import requests
# import os
# import time

# # ==========================================
# # 1. CONFIGURATION
# # ==========================================
# INPUT_CSV = '/Users/cmbreen/Library/CloudStorage/OneDrive-NASA/oasis_datacenter/datasets/im3_open_source_data_center_atlas_v2026.02.09.csv'
# OUTPUT_DIR = './tmy_datacenter_data'

# os.makedirs(OUTPUT_DIR, exist_ok=True)

# API_URL = "https://www.ncei.noaa.gov/maps/typical-meteorological-year/api/data"

# # ==========================================
# # 2. LOAD DATA
# # ==========================================
# df = pd.read_csv(INPUT_CSV)

# # ⚠️ TESTING: We are only testing the first 3 rows so we don't spam NOAA if it's broken
# df = df.head(3) 
# print(f"Testing NOAA TMY pull for {len(df)} data centers...")

# # ==========================================
# # 3. AUTOMATED PULL
# # ==========================================
# for index, row in df.iterrows():
#     lat = row.get('Latitude', row.get('lat', None))
#     lon = row.get('Longitude', row.get('lon', None))
#     site_id = row.get('id', row.get('ID', f"site_{index}"))

#     if pd.isna(lat) or pd.isna(lon):
#         continue

#     print(f"Requesting NOAA TMY data for {site_id} at ({lat}, {lon})...")

#     # The exact payload your browser sent
#     payload = {
#         "lon": lon,
#         "lat": lat,
#         "nearest_stations": [],  # We have to hope NOAA calculates this for us!
#         "time_period": "1998-2022",
#         "temperature_mean": 10,
#         "temperature_max": 10,
#         "temperature_min": 10,
#         "dew_point_temperature_mean": 10,
#         "dew_point_temperature_max": 10,
#         "dew_point_temperature_min": 10,
#         "wind_speed_mean": 10,
#         "wind_speed_max": 10,
#         "GHI_mean": 10,
#         "DNI_mean": 10,
#         "weight": "Equal",
#         "additional_vars": [
#             "DHI", "snow_depth", "precipitation", 
#             "station_level_pressure", "relative_humidity", 
#             "wind_direction", "total_sky_cover", "wind_gust"
#         ],
#         "units": "metric"
#     }

#     headers = {
#         "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko)",
#         "Accept": "application/json, text/plain, */*",
#         "Content-Type": "application/json",
#         "Origin": "https://www.ncei.noaa.gov",
#         "Referer": "https://www.ncei.noaa.gov/access/typical-meteorological-year/"
#     }

#     try:
#         response = requests.post(API_URL, json=payload, headers=headers)

#         if response.status_code == 200:
#             # Determine if NOAA sent a ZIP or a CSV back
#             content_type = response.headers.get('Content-Type', '')
#             ext = "zip" if "zip" in content_type else "csv"
            
#             output_file = os.path.join(OUTPUT_DIR, f"TMY_{site_id}.{ext}")
            
#             with open(output_file, 'wb') as f:
#                 f.write(response.content)
#             print(f"  -> Success: Saved {output_file}")
            
#         else:
#             print(f"  -> Failed: HTTP {response.status_code}")
#             print(f"  -> Error: {response.text[:300]}")

#         # Pause to avoid getting blocked
#         time.sleep(3)

#     except Exception as e:
#         print(f"  -> Request error for {site_id}: {e}")

# print("Test complete.")

import pandas as pd
import os
import time
from playwright.sync_api import sync_playwright

# ==========================================
# 1. CONFIGURATION
# ==========================================
INPUT_CSV = '/Users/cmbreen/Library/CloudStorage/OneDrive-NASA/oasis_datacenter/datasets/im3_open_source_data_center_atlas_v2026.02.09.csv'
OUTPUT_DIR = 'tmy_data_noaa_scraper'

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ==========================================
# 2. RUN THE SCRAPER (HEADLESS)
# ==========================================
def run_scraper():
    # Read the CSV (Testing first 3 rows - remove .head(3) when ready to do all of them!)
    df = pd.read_csv(INPUT_CSV).head(3)
    print(f"Starting Background Scraper for {len(df)} locations...")

    with sync_playwright() as p:
        # THE FIX: headless=True makes it run invisibly in the background!
        browser = p.chromium.launch(headless=True, channel="chrome")
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        
        for index, row in df.iterrows():
            site_id = row.get('id', row.get('ID', f"site_{index}"))
            lat = row.get('lat', row.get('Latitude'))
            lon = row.get('lon', row.get('Longitude'))
            
            print(f"Scraping NOAA for {site_id} at ({lat}, {lon})...")
            
            try:
                # 1. Go to the NOAA Website
                page.goto("https://www.ncei.noaa.gov/access/typical-meteorological-year/")
                page.wait_for_load_state("networkidle")
                
                # 2. Enter Location (Coordinates)
                search_box = page.locator("#search-widget-container-input")
                search_box.fill(f"{lat}, {lon}")
                # Click the first search suggestion
                page.locator("#search-widget-container-suggestion-item-0").click()
                
                # Wait 3 seconds for NOAA's map to calculate the nearest stations
                time.sleep(3)
                
                # 3. Weights: Standard
                page.get_by_label("Standard").check()
                
                # 4. Check all Additional Variables you requested
                extra_vars = [
                    "Diffuse Horizontal Irradiance",
                    "Snow Depth",
                    "Precipitation",
                    "Station Level Pressure",
                    "Relative Humidity",
                    "Wind Direction",
                    "Sky Cover",
                    "Wind Gust"
                ]
                for var in extra_vars:
                    page.get_by_label(var).check()
                
                # 5. Units: International System of Units (SI)
                page.get_by_label("International System of Units (SI)").check()
                
                # 6. Click the Required Agreement box
                page.locator("text=I agree to download").click()
                
                # 7. Click the Download Button and catch the ZIP file
                print("  -> Downloading...")
                with page.expect_download(timeout=60000) as download_info:
                    page.locator("#download-button").click()
                    
                download = download_info.value
                
                # Save the downloaded file to your folder
                file_path = os.path.join(OUTPUT_DIR, f"{site_id}_tmy.zip")
                download.save_as(file_path)
                print(f"  -> SUCCESS! Saved {file_path}")
                
            except Exception as e:
                print(f"  -> FAILED for {site_id}. Error: {e}")
                
            # Give the background browser a second to breathe
            time.sleep(2)
            
        # Close the browser when done
        browser.close()

if __name__ == "__main__":
    run_scraper()