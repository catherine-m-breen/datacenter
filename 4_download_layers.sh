#!/bin/bash

# ==============================================================================
# Annual NLCD Zip Downloader & Clipper (2002-2023)
# Downloads the zip, extracts it, clips two bounding boxes, and cleans up.
# ==============================================================================

# Base URL for MRLC AWS S3 Bucket (Standard for Annual NLCD)
BASE_URL="https://s3-us-west-2.amazonaws.com/mrlc"

# Define your Bounding Boxes in Lat/Lon (WGS84 / EPSG:4326)
# Format: MinLon MinLat MaxLon MaxLat (Note: GDAL uses X_MIN Y_MIN X_MAX Y_MAX)
BBOX_1_NAME="Virginia"
BBOX_1="-78 38.5 -77.0 39.5 "

BBOX_2_NAME="Texas"
BBOX_2="-97.5, 32.3, -96.5, 33.3"

# Create output directory
mkdir -p nlcd_clipped
cd nlcd_clipped

for YEAR in {2002..2023}; do
    FILENAME="Annual_NLCD_LndCov_${YEAR}_CU_C1V2.zip"
    URL="${BASE_URL}/${FILENAME}"
    
    echo "=================================================="
    echo "Processing Year: $YEAR"
    echo "Downloading: $FILENAME"
    
    # 1. Download the zip file using curl
    # -# shows a progress bar, -O saves it with the remote filename
    curl -# -O "$URL"
    
    if [ ! -s "$FILENAME" ]; then
        echo "❌ Failed to download $FILENAME (or file is empty). Skipping..."
        rm -f "$FILENAME" # remove empty file if it was created
        continue
    fi

    # 2. Unzip only the raster file
    mkdir -p temp_extract_$YEAR
    echo "Extracting raster..."
    unzip -q -j "$FILENAME" "*.tif" "*.img" -d temp_extract_$YEAR/
    
    # Find the extracted raster file
    RASTER_FILE=$(find temp_extract_$YEAR -type f \( -name "*.tif" -o -name "*.img" \) | head -n 1)

    if [ -z "$RASTER_FILE" ]; then
        echo "❌ No .tif or .img found in $FILENAME."
    else
        echo "Clipping bounding boxes..."
        
        # 3. Clip BBOX 1
        gdalwarp -q -te $BBOX_1 -t_srs EPSG:4326 "$RASTER_FILE" "${BBOX_1_NAME}_NLCD_${YEAR}.tif"
        echo "✅ Created ${BBOX_1_NAME}_NLCD_${YEAR}.tif"

        # 4. Clip BBOX 2
        gdalwarp -q -te $BBOX_2 -t_srs EPSG:4326 "$RASTER_FILE" "${BBOX_2_NAME}_NLCD_${YEAR}.tif"
        echo "✅ Created ${BBOX_2_NAME}_NLCD_${YEAR}.tif"
    fi

    # 5. Clean up the giant zip and extracted full raster to save space
    echo "Cleaning up large files for $YEAR..."
    rm "$FILENAME"
    rm -rf temp_extract_$YEAR

done

echo "=================================================="
echo "🎉 All years processed! Clipped files are in the 'nlcd_clipped' directory."