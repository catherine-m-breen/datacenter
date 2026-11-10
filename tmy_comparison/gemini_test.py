import os
import requests

def download_nrel_tmy(lat, lon, api_key, email, output_filename="tmy_data.csv"):
    """
    Downloads TMY data from the NREL NSRDB API for a specific latitude and longitude.
    """
    # NREL NSRDB PSM v3 TMY endpoint
    url = "https://nrel.gov"
    
    # Required parameters for the NREL TMY endpoint
    payload = {
        'api_key': api_key,
        'full_name': 'Developer',
        'email': email,
        'affiliation': 'None',
        'mailing_list': 'false',
        'reason': 'Academic/Research',
        'wkt': f'POINT({lon} {lat})', # Well-Known Text format for coordinates
        'names': 'tmy',               # Specifies Typical Meteorological Year data
        'attributes': 'dhi,dni,ghi,dew_point,air_temperature,wind_speed,relative_humidity',
        'leap_day': 'false',
        'utc': 'false'
    }
    
    print(f"Requesting TMY data for Coordinates: {lat}, {lon}...")
    
    try:
        response = requests.post(url, data=payload, timeout=30)
        
        # Check if the request was successful
        if response.status_code == 200:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(output_filename) if os.path.dirname(output_filename) else '.', exist_ok=True)
            
            with open(output_filename, 'w', encoding='utf-8') as f:
                f.write(response.text)
            print(f"Success! TMY data successfully saved to: {output_filename}")
        else:
            print(f"Failed to retrieve data. Status Code: {response.status_code}")
            print(f"Response: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"An error occurred during the API request: {e}")

if __name__ == "__main__":
    # --- CONFIGURATION ---
    # Sign up for a free key at https://nrel.gov
    NREL_API_KEY = "WmQhDWC6TqGMTj9nhhkjtCQmTpgQRfdwtFd6q9LC"  # Replace with your actual NREL API key
    USER_EMAIL = "catherine.m.breen@nasa.gov"  # Replace with your registered email
    
    # Geographic coordinates (Example: Goddard/Greenbelt, MD area)
    LATITUDE = 39.00
    LONGITUDE = -76.88
    
    OUTPUT_FILE = "tmy_greenbelt_md.csv"
    # ---------------------
    
    download_nrel_tmy(
        lat=LATITUDE, 
        lon=LONGITUDE, 
        api_key=NREL_API_KEY, 
        email=USER_EMAIL, 
        output_filename=OUTPUT_FILE
    )
