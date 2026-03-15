from google.transit import gtfs_realtime_pb2
import requests

# The official DRT Live Feed
GTFS_RT_URL = "https://drtonline.durhamregiontransit.com/gtfsrealtime/VehiclePositions"
API_KEY = "transit_publicapi_v3_784080d35549c414b4dc6ffd170e74feb7417578f94e44cf04a8294c1457a5b2" # Paste your real key here

def scan_fleet():
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Cache-Control": "no-cache"
    }
    
    print("Fetching live Durham Region Transit fleet data...")
    try:
        response = requests.get(GTFS_RT_URL, headers=headers, timeout=5)
        response.raise_for_status()
        
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(response.content)
        
        count = 0
        print("\n--- ACTIVE BUSES RIGHT NOW ---")
        for entity in feed.entity:
            if entity.HasField('vehicle'):
                bus_id = entity.vehicle.vehicle.id
                lat = entity.vehicle.position.latitude
                lon = entity.vehicle.position.longitude
                print(f"Fleet ID: {bus_id} | Location: {lat}, {lon}")
                count += 1
                
        print(f"\nTotal active buses found: {count}")
        
    except Exception as e:
        print(f"[ERROR] Could not read GTFS feed: {e}")

if __name__ == "__main__":
    scan_fleet()