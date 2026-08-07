import csv
import random
import uuid
import math
import os
from datetime import datetime, timedelta

# Configuration
NUM_REPORTS = 500   # increased to better use larger dictionary

# Robust path handling
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "incident_reports_dummy.csv")

# Pune geographic constraints
CENTER_LAT = 18.5204
CENTER_LON = 73.8567
RADIUS_KM = 2.5


# Expanded incident description dictionary
DESCRIPTIONS = {
    "Harassment": [
        "A group of people were catcalling pedestrians.",
        "Someone yelled obscenities at me while passing by.",
        "Aggressive panhandling at the intersection.",
        "A group of men making inappropriate comments to women walking past.",
        "Someone whistled loudly and shouted remarks as I walked by.",
        "People sitting on bikes repeatedly shouting at passersby.",
        "A stranger approached and kept making uncomfortable remarks.",
        "Someone mocked and insulted pedestrians walking alone.",
        "A group of teenagers throwing verbal insults at people crossing the street.",
        "Someone kept shouting vulgar words from across the road.",
        "Men standing near the corner were making offensive gestures.",
        "Someone followed pedestrians briefly while shouting insults.",
        "People near the bus stop were loudly harassing commuters.",
        "A man kept trying to start unwanted conversations with people walking alone.",
        "Someone deliberately blocked my path while making rude remarks.",
        "A person kept clapping loudly and calling out to passing women.",
        "A group repeatedly laughed and shouted at people walking by.",
        "Someone made threatening comments toward pedestrians.",
        "Individuals were yelling aggressive remarks toward people passing by.",
        "Someone was recording people walking past while making mocking comments."
    ],

    "Poor lighting": [
        "Streetlights are completely out on this block.",
        "Very dark alleyway, visibility is almost zero.",
        "Flickering lights make it hard to see the footpath.",
        "Most of the streetlights along this road are not working.",
        "The area near the bus stop is poorly lit after sunset.",
        "Broken streetlight leaves the entire corner in darkness.",
        "Only one dim light is working along this stretch of road.",
        "The pathway behind the buildings has no lighting at all.",
        "The park entrance is completely dark at night.",
        "Streetlights are covered by tree branches, making the area very dim.",
        "The lights near the underpass are not functioning.",
        "Parking lot lighting is extremely weak and uneven.",
        "Frequent power outages leave the street in darkness.",
        "Dim yellow bulbs make it difficult to see obstacles.",
        "The walkway lighting is inconsistent and patchy.",
        "Several lamp posts are present but none are working.",
        "The pedestrian bridge has no lighting at night.",
        "Lights along the alley flicker constantly.",
        "Street corners are shadowy due to missing lights.",
        "The lane between buildings is completely dark after sunset."
    ],

    "Suspicious Activity": [
        "Group of individuals loitering around parked cars.",
        "Someone looking into ground-floor windows.",
        "Unattended bag left near the bus stand.",
        "Two people standing near the ATM watching everyone closely.",
        "Someone repeatedly walking back and forth while observing houses.",
        "A person trying car door handles along the street.",
        "Unknown individuals sitting in a parked car for a long time.",
        "Someone attempting to peek through shop shutters.",
        "A person walking around the same block multiple times.",
        "Someone hiding behind parked vehicles and watching pedestrians.",
        "An individual lingering near building entrances without explanation.",
        "A group quietly observing people entering the apartment complex.",
        "Someone inspecting parked bikes closely.",
        "A person crouching near a vehicle as if tampering with it.",
        "Someone scanning apartment balconies from the street.",
        "Two people whispering while watching the nearby houses.",
        "Someone repeatedly checking their phone while pacing around suspiciously.",
        "Unknown person trying to access locked gates.",
        "A person standing still in the shadows watching people pass.",
        "Someone examining delivery packages left outside homes."
    ],

    "Stalking": [
        "A person followed me for three consecutive blocks.",
        "Noticed the same two-wheeler circling the area slowly.",
        "Someone was taking photos of people walking by without consent.",
        "A person followed me for three consecutive blocks.",
        "The same person kept appearing behind me along different streets.",
        "Someone on a scooter slowly followed me along the road.",
        "A stranger kept maintaining distance but followed my path.",
        "A person walked behind me and matched my pace repeatedly.",
        "Someone stopped whenever I stopped walking.",
        "The same car passed me multiple times within a few minutes.",
        "Someone stood across the street watching me for several minutes.",
        "A person followed me from the bus stop to the market.",
        "Someone kept turning into the same streets I did.",
        "A stranger walked behind me while pretending to be on a call.",
        "A bike rider slowed down and kept watching pedestrians.",
        "Someone waited outside a building and followed me when I left.",
        "A person kept circling the area on a bicycle watching people.",
        "Someone trailed me while pretending to check their phone.",
        "A stranger walked very closely behind me for a long distance.",
        "Someone followed me across multiple crossings without explanation."
    ],

    "Unsafe infrastructure": [
        "Deep open manhole right in the middle of the sidewalk.",
        "Broken pavement forcing pedestrians to walk on the busy street.",
        "Construction debris blocking the entire walking path.",
        "Loose paving stones making the sidewalk dangerous.",
        "Large pothole filled with water on the pedestrian walkway.",
        "Broken stairs leading to the pedestrian bridge.",
        "Collapsed section of pavement near the corner.",
        "Exposed electrical wires hanging near the footpath.",
        "Temporary construction fencing blocking the walkway.",
        "Uneven road surface causing people to trip.",
        "Open drainage canal without protective covering.",
        "Damaged guardrails near the road crossing.",
        "Missing manhole cover on the side of the street.",
        "Sharp metal rods sticking out from construction materials.",
        "Cracked concrete slabs creating tripping hazards.",
        "Debris and rubble scattered across the footpath.",
        "Broken street signs lying across the walkway.",
        "Flooded sidewalk making it unsafe to walk.",
        "Narrow walkway with no barrier from heavy traffic.",
        "Exposed pipes sticking out of the pavement."
    ]
}
# Automatically derive incident types
INCIDENT_TYPES = list(DESCRIPTIONS.keys())


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

    return round(new_lat, 6), round(new_lon, 6)


def generate_random_timestamp(days_back=30):
    """Generates a random timestamp within the last X days."""
    now = datetime.now()
    random_days = random.uniform(0, days_back)
    random_date = now - timedelta(days=random_days)
    return random_date.strftime("%Y-%m-%d %H:%M:%S")


def generate_csv():

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    headers = ["id", "latitude", "longitude", "incident_type", "description", "created_at"]

    with open(OUTPUT_FILE, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(headers)

        for _ in range(NUM_REPORTS):

            record_id = str(uuid.uuid4())

            lat, lon = generate_random_point(CENTER_LAT, CENTER_LON, RADIUS_KM)

            # Randomly select incident type from dictionary keys
            incident_type = random.choice(INCIDENT_TYPES)

            # Safely select description
            description_list = DESCRIPTIONS.get(incident_type, ["General safety concern reported"])
            description = random.choice(description_list)

            created_at = generate_random_timestamp()

            writer.writerow([record_id, lat, lon, incident_type, description, created_at])

    print(f"Successfully generated {NUM_REPORTS} records at {OUTPUT_FILE}")


if __name__ == "__main__":
    generate_csv()