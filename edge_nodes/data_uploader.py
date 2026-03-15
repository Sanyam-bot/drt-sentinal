import os
import csv
import time
import requests

# --- CONFIGURATION ---
# Replace this with your Windows laptop's IP address on the local hotspot
WINDOWS_HOST_IP = "10.32.194.25" 
API_ENDPOINT = f"http://{WINDOWS_HOST_IP}:8000/api/ingest"

# The files your sniffers are currently generating
TARGET_FILES = [
    "drt_telemetry_Front.csv",
    "drt_telemetry_BLE_Front.csv"
]

UPLOAD_INTERVAL = 10  # Send data every 10 seconds

def process_and_upload():
    for live_file in TARGET_FILES:
        if not os.path.exists(live_file):
            continue

        # 1. Atomic Rename: Safely move the live file to a processing state
        processing_file = f"{live_file}.processing"
        try:
            os.rename(live_file, processing_file)
        except Exception as e:
            print(f"[ERROR] Could not rename {live_file}: {e}")
            continue

        payload_batch = []

        # 2. Read the locked processing file
        with open(processing_file, mode='r') as file:
            reader = csv.reader(file)
            headers = next(reader, None) # Skip the header row

            for row in reader:
                if not row:
                    continue
                
                # Handle the difference between the Wi-Fi CSV (4 cols) and BLE CSV (5 cols)
                if len(row) == 4:
                    ts, node, mac, rssi = row
                    protocol = "Wi-Fi"
                elif len(row) == 5:
                    ts, node, protocol, mac, rssi = row
                else:
                    continue

                # Build the exact JSON structure the FastAPI Pydantic model expects
                payload_batch.append({
                    "timestamp": int(ts),
                    "node_location": node,
                    "protocol": protocol,
                    "pseudo_mac": mac,
                    "rssi": int(rssi)
                })

        # 3. HTTP POST the batch to the Windows backend
        if payload_batch:
            try:
                print(f"Uploading {len(payload_batch)} records from {live_file}...")
                response = requests.post(API_ENDPOINT, json=payload_batch, timeout=5)
                
                if response.status_code == 200:
                    print("[SUCCESS] Batch accepted by server.")
                    # 4. Clean up the processing file only if the upload succeeded
                    os.remove(processing_file)
                else:
                    print(f"[FAILED] Server returned {response.status_code}. Keeping data for next try.")
                    os.rename(processing_file, live_file) # Revert the rename to try again later
            
            except requests.exceptions.RequestException as e:
                print(f"[NETWORK ERROR] Cannot reach {API_ENDPOINT}. Is the FastAPI server running?")
                os.rename(processing_file, live_file) # Revert and retry next loop
        else:
            # File was empty (just headers), safe to delete
            os.remove(processing_file)

if __name__ == "__main__":
    print(f"Starting DRT Telemetry Uploader. Pointing to {API_ENDPOINT}...")
    while True:
        process_and_upload()
        time.sleep(UPLOAD_INTERVAL)

