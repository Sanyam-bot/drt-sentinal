import asyncio
import hashlib
import time
import csv
import os
from bleak import BleakScanner

# Configuration
RSSI_THRESHOLD = -85
NODE_LOCATION = "Front" 
CSV_FILE = f"drt_telemetry_BLE_{NODE_LOCATION}.csv"
APPLE_COMPANY_ID = 76 # 0x004C in decimal

# Initialize CSV File and Headers safely
file_exists = os.path.isfile(CSV_FILE)
with open(CSV_FILE, mode='a', newline='') as file:
    writer = csv.writer(file)
    if not file_exists:
        writer.writerow(["Timestamp", "Node", "Protocol", "Pseudo_MAC", "RSSI"])

def process_ble_packet(device, advertisement_data):
    """
    Callback triggered asynchronously every time a BLE packet is detected.
    """
    # 1. Filter out weak signals using the packet's RSSI, not the device's
    if advertisement_data.rssi < RSSI_THRESHOLD:
        return

    # 2. Check if the packet contains Manufacturer Specific Data
    if not advertisement_data.manufacturer_data:
        return

    # 3. Extract the raw bytes. We specifically look for Apple (76) 
    # but we will hash any manufacturer data to track Androids/wearables too.
    payload_bytes = b""
    for company_id, data_bytes in advertisement_data.manufacturer_data.items():
        payload_bytes += company_id.to_bytes(2, byteorder='little') + data_bytes

    if not payload_bytes:
        return

    # 4. Hash the payload to create a stable identifier
    pseudo_mac = hashlib.sha256(payload_bytes).hexdigest()[:16]
    timestamp = int(time.time())

    print(f"[BLE - {NODE_LOCATION}] Time: {timestamp} | Signature: {pseudo_mac} | RSSI: {advertisement_data.rssi} dBm")

    # 5. Safely append to the CSV file
    with open(CSV_FILE, mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([timestamp, NODE_LOCATION, "BLE", pseudo_mac, advertisement_data.rssi])

async def main():
    """Main async loop to keep the scanner running."""
    print(f"Starting DRT Sentinel BLE Edge Node: {NODE_LOCATION}...")
    print(f"Filtering RSSI strictly above {RSSI_THRESHOLD} dBm. Press Ctrl+C to stop.")
    
    # Initialize the scanner with our callback function
    scanner = BleakScanner(detection_callback=process_ble_packet)
    
    while True:
        await scanner.start()
        # Let it scan for 5 seconds, then yield control back to the event loop
        await asyncio.sleep(5.0)
        await scanner.stop()

if __name__ == "__main__":
    # Run the asynchronous event loop
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBLE Sniffer stopped by user.")
