"""
Seed script for populating Firestore with reference data.

Loads hazmat entries and medical protocols from JSON files in the
data/ directory, or uses built-in defaults if files are not found.

Usage:
    python -m app.seed_data
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


async def load_hazmat_from_file() -> list[dict]:
    """
    Load hazmat entries from data/hazmat_erg.json.
    Falls back to built-in defaults if file not found.
    """
    path = os.path.join(DATA_DIR, "hazmat_erg.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            logger.info("Loaded %d hazmat entries from %s", len(data), path)
            return data

    logger.warning("hazmat_erg.json not found at %s, using built-in defaults", path)
    return _default_hazmat_entries()


async def load_protocols_from_file() -> list[dict]:
    """
    Load medical protocols from data/medical_protocols.json.
    Falls back to built-in defaults if file not found.
    """
    path = os.path.join(DATA_DIR, "medical_protocols.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            logger.info("Loaded %d protocols from %s", len(data), path)
            return data

    logger.warning("medical_protocols.json not found at %s, using built-in defaults", path)
    return _default_medical_protocols()


def _default_hazmat_entries() -> list[dict]:
    """Built-in hazmat reference data based on USDOT ERG."""
    return [
        {
            "un_number": "UN1203",
            "chemical_name": "Gasoline",
            "hazard_class": "Flammable Liquid",
            "guide_number": 128,
            "safe_distance_ft": 300,
            "ppe_required": [
                "Self-Contained Breathing Apparatus (SCBA)",
                "Chemical-resistant suit",
                "Nitrile gloves"
            ],
            "immediate_actions": [
                "Eliminate all ignition sources within 300 feet",
                "Evacuate downwind personnel immediately",
                "Do not attempt to extinguish unless trained",
                "Contain spill with absorbent material if safe to do so"
            ],
            "first_aid": [
                "Move victim to fresh air immediately",
                "If not breathing, begin CPR",
                "Remove contaminated clothing",
                "Flush skin with water for at least 20 minutes"
            ],
            "fire_response": "Use dry chemical, CO2, or alcohol-resistant foam. Water may be ineffective.",
            "spill_response": "Eliminate ignition sources. Absorb with earth or sand. Prevent entry into sewers."
        },
        {
            "un_number": "UN1017",
            "chemical_name": "Chlorine",
            "hazard_class": "Toxic Gas",
            "guide_number": 124,
            "safe_distance_ft": 1500,
            "ppe_required": [
                "Level A Hazmat Suit",
                "Self-Contained Breathing Apparatus (SCBA)",
                "Chemical-resistant boots"
            ],
            "immediate_actions": [
                "Evacuate area -- minimum 1500 feet in all directions",
                "Move upwind immediately",
                "Do NOT apply water directly to leak",
                "Isolate spill area and restrict access"
            ],
            "first_aid": [
                "Move victim to fresh air immediately",
                "If breathing difficulty, administer oxygen",
                "Remove contaminated clothing",
                "If eyes exposed, flush with water for 15 minutes"
            ],
            "fire_response": "Chlorine is not flammable but supports combustion. Use water spray to reduce vapors.",
            "spill_response": "Do not direct water at source. Use fine water spray to knock down vapors."
        },
        {
            "un_number": "UN1005",
            "chemical_name": "Ammonia (Anhydrous)",
            "hazard_class": "Toxic Gas, Corrosive",
            "guide_number": 125,
            "safe_distance_ft": 1000,
            "ppe_required": [
                "Level A or B Hazmat Suit",
                "Self-Contained Breathing Apparatus (SCBA)",
                "Chemical-resistant gloves"
            ],
            "immediate_actions": [
                "Evacuate area -- minimum 1000 feet",
                "Stay upwind",
                "Ammonia is lighter than air and rises",
                "Isolate the area and deny entry"
            ],
            "first_aid": [
                "Move victim to fresh air",
                "If not breathing, begin artificial respiration",
                "Flush contaminated skin with large amounts of water",
                "If eyes exposed, irrigate with water for 15 minutes minimum"
            ],
            "fire_response": "Ammonia containers may rocket if heated. Cool containers with water from maximum distance.",
            "spill_response": "Use fine water spray to absorb vapors. Do not direct water into liquid ammonia."
        },
        {
            "un_number": "UN1075",
            "chemical_name": "Propane",
            "hazard_class": "Flammable Gas",
            "guide_number": 115,
            "safe_distance_ft": 500,
            "ppe_required": [
                "Self-Contained Breathing Apparatus (SCBA)",
                "Structural firefighting gear",
                "Thermal protection"
            ],
            "immediate_actions": [
                "Eliminate all ignition sources within 500 feet",
                "Propane vapor is heavier than air -- collects in low areas",
                "Evacuate downhill and downwind",
                "Close cylinder valve if safe to do so"
            ],
            "first_aid": [
                "Move victim to fresh air",
                "Administer oxygen if breathing difficulty",
                "Treat frostbite if exposure to liquid propane",
                "Begin CPR if not breathing"
            ],
            "fire_response": "Do not extinguish unless leak can be stopped. Cool containers with water from distance.",
            "spill_response": "Stop leak if possible without risk. Ventilate area. Keep out of low areas."
        },
        {
            "un_number": "UN2794",
            "chemical_name": "Battery Acid (Sulfuric Acid)",
            "hazard_class": "Corrosive",
            "guide_number": 137,
            "safe_distance_ft": 150,
            "ppe_required": [
                "Acid-resistant suit",
                "Face shield and safety goggles",
                "Acid-resistant gloves",
                "Respiratory protection"
            ],
            "immediate_actions": [
                "Isolate spill area",
                "Do not touch spilled material",
                "Neutralize small spills with baking soda or lime",
                "Prevent runoff from entering drains or waterways"
            ],
            "first_aid": [
                "Flush skin with water for at least 30 minutes",
                "Remove contaminated clothing while flushing",
                "If swallowed, do NOT induce vomiting",
                "Flush eyes with water for at least 30 minutes"
            ],
            "fire_response": "Acid is not flammable. Water spray may produce toxic fumes. Use dry chemical.",
            "spill_response": "Absorb with dry earth or sand. Neutralize with soda ash. Do not use sawdust."
        },
        {
            "un_number": "UN1090",
            "chemical_name": "Acetone",
            "hazard_class": "Flammable Liquid",
            "guide_number": 127,
            "safe_distance_ft": 200,
            "ppe_required": [
                "Chemical splash goggles",
                "Organic vapor respirator",
                "Nitrile gloves",
                "Fire-resistant clothing"
            ],
            "immediate_actions": [
                "Eliminate ignition sources within 200 feet",
                "Ventilate the area",
                "Acetone vapors are heavier than air",
                "Prevent entry into confined spaces"
            ],
            "first_aid": [
                "Move to fresh air if inhaled",
                "Flush eyes with water for 15 minutes",
                "Wash skin with soap and water",
                "If ingested, do not induce vomiting -- seek medical attention"
            ],
            "fire_response": "Use alcohol-resistant foam, dry chemical, or CO2. Water spray may be ineffective.",
            "spill_response": "Absorb with inert material. Ventilate area. Prevent entry into sewers."
        },
    ]


def _default_medical_protocols() -> list[dict]:
    """Built-in medical protocol reference data based on AHA/Red Cross."""
    return [
        {
            "protocol_id": "hemorrhage_severe",
            "injury_type": "hemorrhage",
            "severity_level": "severe",
            "title": "Severe Hemorrhage -- Direct Pressure and Tourniquet Protocol",
            "source": "American Red Cross First Aid Guidelines 2024",
            "steps": [
                "Ensure scene safety before approaching the victim.",
                "Put on medical gloves if available.",
                "Expose the wound by removing or cutting away clothing.",
                "Apply direct pressure with a clean cloth or gauze pad.",
                "Maintain firm, continuous pressure for at least 10 minutes.",
                "If bleeding soaks through, add more material on top -- do NOT remove original dressing.",
                "If direct pressure fails and bleeding is from a limb, apply a tourniquet 2-3 inches above the wound.",
                "Tighten tourniquet until bleeding stops.",
                "Note the time of tourniquet application.",
                "Do NOT remove the tourniquet once applied.",
                "Keep the victim warm with a blanket.",
                "Monitor for signs of shock: pale skin, rapid breathing, confusion.",
                "Elevate legs if no spinal injury suspected."
            ],
            "warnings": [
                "Do NOT apply a tourniquet to the neck, head, or torso.",
                "Do NOT remove embedded objects from the wound.",
                "This is protocol-based guidance. A medical professional should evaluate as soon as possible."
            ]
        },
        {
            "protocol_id": "hemorrhage_moderate",
            "injury_type": "hemorrhage",
            "severity_level": "moderate",
            "title": "Moderate Hemorrhage -- Direct Pressure Protocol",
            "source": "American Red Cross First Aid Guidelines 2024",
            "steps": [
                "Put on medical gloves if available.",
                "Apply direct pressure with a sterile gauze pad.",
                "Maintain pressure for at least 10 minutes without checking.",
                "Once bleeding slows, apply a pressure bandage.",
                "Elevate the injured area above heart level if possible.",
                "Monitor for increased bleeding."
            ],
            "warnings": [
                "Seek professional medical evaluation.",
                "This is protocol-based guidance. A medical professional should evaluate as soon as possible."
            ]
        },
        {
            "protocol_id": "fracture_severe",
            "injury_type": "fracture",
            "severity_level": "severe",
            "title": "Severe Fracture -- Immobilization Protocol",
            "source": "AHA First Aid Science Advisory 2024",
            "steps": [
                "Do NOT attempt to realign the bone.",
                "Immobilize the injury in the position found.",
                "Apply a splint above and below the fracture site.",
                "Use rigid material (board, rolled magazine) or SAM splint.",
                "Pad the splint for comfort.",
                "Secure with bandages -- firm but not so tight as to cut off circulation.",
                "Check pulse, sensation, and movement below the injury.",
                "Apply cold pack wrapped in cloth to reduce swelling.",
                "Treat for shock if open fracture -- lie flat, elevate legs, keep warm."
            ],
            "warnings": [
                "Do NOT move the victim if spinal injury is suspected.",
                "Do NOT straighten a deformed limb.",
                "This is protocol-based guidance. A medical professional should evaluate as soon as possible."
            ]
        },
        {
            "protocol_id": "burn_severe",
            "injury_type": "burn",
            "severity_level": "severe",
            "title": "Severe Burn -- Emergency Cooling and Protection Protocol",
            "source": "American Burn Association Guidelines",
            "steps": [
                "Remove the victim from the heat source.",
                "Stop the burning process -- remove smoldering clothing unless stuck to skin.",
                "Cool the burn with cool (not cold) running water for 20 minutes.",
                "Do NOT use ice, butter, or ointments on severe burns.",
                "Cover the burn loosely with a sterile, non-stick dressing.",
                "Do NOT break any blisters.",
                "Elevate the burned area above heart level if possible.",
                "Remove rings, watches, and tight clothing before swelling starts.",
                "Keep the victim warm -- cover unburned areas with a blanket.",
                "Monitor airway if facial burns are present.",
                "Provide small sips of water if victim is conscious and alert."
            ],
            "warnings": [
                "Do NOT apply ice directly to burns.",
                "Do NOT use adhesive bandages on burns.",
                "Burns to face, hands, feet, genitals, or major joints require immediate hospital care.",
                "This is protocol-based guidance. A medical professional should evaluate as soon as possible."
            ]
        },
        {
            "protocol_id": "cardiac_arrest_life_threatening",
            "injury_type": "cardiac_arrest",
            "severity_level": "life_threatening",
            "title": "Cardiac Arrest -- CPR Protocol",
            "source": "AHA Guidelines for CPR and Emergency Cardiovascular Care 2024",
            "steps": [
                "Confirm unresponsiveness -- tap shoulders and shout.",
                "Call for help and request an AED immediately.",
                "Check for breathing -- look for chest rise for no more than 10 seconds.",
                "If not breathing or only gasping, begin CPR immediately.",
                "Place the heel of one hand on the center of the chest.",
                "Place the other hand on top, fingers interlaced.",
                "Compress at least 2 inches deep at a rate of 100-120 per minute.",
                "Allow full chest recoil between compressions.",
                "After 30 compressions, give 2 rescue breaths (if trained).",
                "Continue 30:2 cycle until AED arrives or EMS takes over.",
                "If AED available: turn on, follow voice prompts, apply pads.",
                "Resume CPR immediately after AED shock -- do NOT check pulse."
            ],
            "warnings": [
                "Do NOT stop CPR unless the victim starts breathing or EMS arrives.",
                "Compression quality matters more than rescue breaths.",
                "Hands-only CPR (no breaths) is acceptable for untrained rescuers.",
                "This is protocol-based guidance. A medical professional should evaluate as soon as possible."
            ]
        },
        {
            "protocol_id": "concussion_moderate",
            "injury_type": "concussion",
            "severity_level": "moderate",
            "title": "Concussion -- Assessment and Monitoring Protocol",
            "source": "CDC HEADS UP Concussion Guidelines",
            "steps": [
                "Do NOT move the victim if spinal injury is possible.",
                "Keep the victim still and calm.",
                "Monitor for worsening symptoms: increasing confusion, repeated vomiting, seizures.",
                "Check pupil response -- unequal pupils indicate serious injury.",
                "Do NOT let the victim fall asleep for the first hour.",
                "Apply a cold pack to any visible head swelling.",
                "Ask orientation questions: name, date, location.",
                "Keep the victim in a comfortable position with head slightly elevated."
            ],
            "warnings": [
                "Seek immediate hospital evaluation for any loss of consciousness.",
                "Do NOT administer aspirin or blood-thinning medications.",
                "This is protocol-based guidance. A medical professional should evaluate as soon as possible."
            ]
        },
        {
            "protocol_id": "choking_life_threatening",
            "injury_type": "choking",
            "severity_level": "life_threatening",
            "title": "Complete Airway Obstruction -- Heimlich Maneuver Protocol",
            "source": "AHA Choking Relief Guidelines 2024",
            "steps": [
                "Confirm choking -- ask 'Are you choking?' Look for inability to speak, cough, or breathe.",
                "If victim can cough forcefully, encourage them to continue coughing.",
                "If victim cannot cough, speak, or breathe -- act immediately.",
                "Stand behind the victim and wrap your arms around their waist.",
                "Make a fist with one hand and place it above the navel, below the ribcage.",
                "Grasp your fist with your other hand.",
                "Deliver quick, upward abdominal thrusts.",
                "Repeat until the object is expelled or victim becomes unconscious.",
                "If victim becomes unconscious, lower them to the ground.",
                "Begin CPR -- check mouth for visible object before rescue breaths."
            ],
            "warnings": [
                "For pregnant or obese victims, use chest thrusts instead of abdominal thrusts.",
                "For infants: use back blows and chest thrusts -- NOT abdominal thrusts.",
                "This is protocol-based guidance. A medical professional should evaluate as soon as possible."
            ]
        },
        {
            "protocol_id": "hypothermia_severe",
            "injury_type": "hypothermia",
            "severity_level": "severe",
            "title": "Severe Hypothermia -- Rewarming Protocol",
            "source": "Wilderness Medical Society Clinical Practice Guidelines",
            "steps": [
                "Move the victim to a warm, dry environment.",
                "Handle the victim GENTLY -- rough movement can trigger cardiac arrest.",
                "Remove wet clothing carefully.",
                "Wrap the victim in dry blankets or sleeping bags.",
                "Apply warm compresses to core areas: neck, armpits, groin.",
                "Do NOT warm extremities first -- this can cause cardiac arrest.",
                "Do NOT rub or massage the skin.",
                "If conscious and able to swallow, provide warm (not hot) sweet drinks.",
                "Monitor breathing continuously.",
                "Be prepared to perform CPR -- severe hypothermia can mimic death."
            ],
            "warnings": [
                "Do NOT use direct heat (hot water, heating pads) on skin.",
                "Do NOT give alcohol.",
                "A hypothermic victim is not dead until they are warm and dead -- continue resuscitation.",
                "This is protocol-based guidance. A medical professional should evaluate as soon as possible."
            ]
        },
    ]


async def seed_firestore() -> None:
    """
    Load all reference data into Firestore.
    """
    from app.database import get_database

    db = get_database()

    # Load hazmat data
    hazmat_entries = await load_hazmat_from_file()
    for entry in hazmat_entries:
        un_number = entry.get("un_number", "")
        doc_id = un_number.replace("UN", "").strip() if un_number else entry.get("chemical_name", "unknown")
        try:
            collection = db.settings.firestore_hazmat_collection
            db.client.collection(collection).document(doc_id).set(entry)
            logger.info("Seeded hazmat: %s -- %s", un_number, entry.get("chemical_name"))
        except Exception:
            logger.exception("Failed to seed hazmat entry: %s", un_number)

    # Load medical protocols
    protocol_entries = await load_protocols_from_file()
    for entry in protocol_entries:
        doc_id = entry.get("protocol_id", "unknown")
        try:
            collection = db.settings.firestore_protocols_collection
            db.client.collection(collection).document(doc_id).set(entry)
            logger.info("Seeded protocol: %s", doc_id)
        except Exception:
            logger.exception("Failed to seed protocol: %s", doc_id)

    logger.info(
        "Seeding complete: %d hazmat entries, %d medical protocols",
        len(hazmat_entries),
        len(protocol_entries),
    )


if __name__ == "__main__":
    asyncio.run(seed_firestore())
