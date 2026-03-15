from scapy.all import sniff, Dot11ProbeReq, RadioTap, Dot11Elt
import hashlib
import time
import csv
import os

# Configuration
INTERFACE = "wlan1"
RSSI_THRESHOLD = -85
NODE_LOCATION = "Front" 
CSV_FILE = f"drt_telemetry_{NODE_LOCATION}.csv"

# Initialize CSV File and Headers
file_exists = os.path.isfile(CSV_FILE)
with open(CSV_FILE, mode='a', newline='') as file:
    writer = csv.writer(file)
    if not file_exists:
        writer.writerow(["Timestamp", "Node", "Pseudo_MAC", "RSSI"])

def get_rssi(packet):
    """Extracts the RSSI value from the RadioTap layer."""
    try:
        return packet[RadioTap].dBm_AntSignal
    except Exception:
        return None

def generate_pseudo_mac(packet):
    """
    Loops through the Information Elements (Dot11Elt) to create a unique, 
    persistent hardware signature bypassing MAC randomization.
    """
    ie_raw_bytes = b""
    elt = packet.getlayer(Dot11Elt)
    
    while elt:
        if elt.ID != 0:
            ie_raw_bytes += bytes(elt.info)
        elt = elt.payload.getlayer(Dot11Elt)
        
    if not ie_raw_bytes:
        return None
        
    return hashlib.sha256(ie_raw_bytes).hexdigest()[:16]

def process_packet(packet):
    """Callback triggered for every captured packet."""
    if packet.haslayer(Dot11ProbeReq):
        
        rssi = get_rssi(packet)
        
        if rssi is None or rssi < RSSI_THRESHOLD:
            return
            
        pseudo_mac = generate_pseudo_mac(packet)
        
        if pseudo_mac:
            timestamp = int(time.time())
            
            print(f"[{NODE_LOCATION}] Time: {timestamp} | Signature: {pseudo_mac} | RSSI: {rssi} dBm")
            
            # Safely append to the CSV file
            with open(CSV_FILE, mode='a', newline='') as file:
                writer = csv.writer(file)
                writer.writerow([timestamp, NODE_LOCATION, pseudo_mac, rssi])

print(f"Starting DRT Sentinel Edge Node: {NODE_LOCATION} on {INTERFACE}...")
print(f"Filtering RSSI strictly above {RSSI_THRESHOLD} dBm. Press Ctrl+C to stop.")

# The sniffer is now active
sniff(iface=INTERFACE, prn=process_packet, store=0)
