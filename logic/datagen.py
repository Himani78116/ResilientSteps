# ============================================================
# DEV ONLY - never import this file from any service or API
# This file exists only for local development seeding
# ============================================================

import json
import random
import math
import os

INPUT_FILE = os.path.join("logic", "output", "pune_safety_segments.geojson")
OUTPUT_FILE = os.path.join("logic", "output", "pune_dummy_safety_data.geojson")

# Pune center coordinates and radius
CENTER_LAT = 18.5204
CENTER_LON = 73.8567
RADIUS_KM = 2.5

# 4-Hour Interval Time Penalties (Lower penalty = safer)
TIME_PENALTIES = {
    "0000-0400": 20,
    "0400-0800": 5,
    "0800-1200": 0,
    "1200-1600": 5,
    "1600-2000": 10,
    "2000-2400": 15
}

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculates distance between two lat/lon points in meters."""
    R = 6371000  # Radius of Earth in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    
    a = math.sin(dphi / 2)**2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def generate_random_point(center_lat, center_lon, radius_km):
    """Generates a random coordinate within a given radius."""
    radius_in_degrees = radius_km / 111.0
    u = random.random()
    v = random.random()
    w = radius_in_degrees * math.sqrt(u)
    t = 2 * math.pi * v
    x = w * math.cos(t)
    y = w * math.sin(t)
    # Adjust for longitude distortion
    new_lon = x / math.cos(math.radians(center_lat)) + center_lon
    new_lat = y + center_lat
    return (new_lat, new_lon)

def generate_dataset():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found. Please ensure OSMnx has generated the base map.")
        return

    with open(INPUT_FILE, 'r') as f:
        data = json.load(f)

    # Seed random risk zones (300m diameter = 150m radius)
    num_high_risk_zones = 25
    num_moderate_risk_zones = 45
    
    high_risk_centers = [generate_random_point(CENTER_LAT, CENTER_LON, RADIUS_KM) for _ in range(num_high_risk_zones)]
    moderate_risk_centers = [generate_random_point(CENTER_LAT, CENTER_LON, RADIUS_KM) for _ in range(num_moderate_risk_zones)]

    for feature in data.get('features', []):
        coords = feature['geometry']['coordinates']
        if not coords:
            continue
        
        # Approximate segment center
        mid_lon = (coords[0][0] + coords[-1][0]) / 2
        mid_lat = (coords[0][1] + coords[-1][1]) / 2
        
        # Determine safety level based on proximity to risk centers
        safety_level = "Safe"
        base_score = random.randint(85, 100)
        
        # Check Moderate Risk zones (150m radius)
        for center in moderate_risk_centers:
            if haversine_distance(mid_lat, mid_lon, center[0], center[1]) <= 150:
                safety_level = "Moderate"
                base_score = random.randint(50, 84)
                break
                
        # Check High Risk zones (150m radius) - Overrides Moderate
        for center in high_risk_centers:
            if haversine_distance(mid_lat, mid_lon, center[0], center[1]) <= 150:
                safety_level = "High Risk"
                base_score = random.randint(10, 49)
                break

        # Assign pseudorandom variables based on safety level
        props = feature.setdefault('properties', {})
        props['safety_level'] = safety_level
        props['base_safety_score'] = base_score
        
        if safety_level == "Safe":
            props['incident_density'] = random.randint(0, 2)
            props['lighting_heuristic'] = random.randint(80, 100)
            props['crowd_density'] = random.randint(40, 80)
        elif safety_level == "Moderate":
            props['incident_density'] = random.randint(3, 7)
            props['lighting_heuristic'] = random.randint(40, 79)
            props['crowd_density'] = random.randint(20, 60)
        else:
            props['incident_density'] = random.randint(8, 20)
            props['lighting_heuristic'] = random.randint(0, 39)
            props['crowd_density'] = random.randint(0, 30)

    # Embed the global time penalties into the GeoJSON root
    data['time_penalties'] = TIME_PENALTIES

    with open(OUTPUT_FILE, 'w') as f:
        json.dump(data, f, indent=4)

    print(f"Success! Generated zonal safety data with time parameters at {OUTPUT_FILE}")

if __name__ == "__main__":
    generate_dataset()
