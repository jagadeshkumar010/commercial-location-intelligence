WATER_KEYWORDS = [
    "sea", "ocean", "lake", "river", "reservoir", "dam", "backwater",
    "lagoon", "bay", "gulf", "strait", "canal", "pond", "wetland",
    "arabian sea", "bay of bengal", "stream", "creek"
]
UNINHABITED_KEYWORDS = [
    "forest", "reserve forest", "reserved forest", "rf", "national park",
    "wildlife sanctuary", "sanctuary", "tiger reserve", "biosphere",
    "glacier", "desert", "barren", "uninhabited", "restricted area",
    "ghat", "hills", "range", "jungle", "woodland"
]

def check_osm_site_context(lat, lon, radius=300):
    """
    Queries OSM Overpass around (lat, lon) to detect forest/water/protected zones
    and check whether any buildings, roads, or amenities exist nearby.
    Returns dict or None if network/Overpass is unreachable.
    """
    query = f"""
    [out:json][timeout:6];
    (
      way["landuse"~"forest|reservoir|basin"](around:{radius},{lat},{lon});
      relation["landuse"~"forest|reservoir|basin"](around:{radius},{lat},{lon});
      way["natural"~"wood|water|wetland|scrub|bare_rock"](around:{radius},{lat},{lon});
      way["boundary"~"national_park|protected_area"](around:{radius},{lat},{lon});
      relation["boundary"~"national_park|protected_area"](around:{radius},{lat},{lon});
      node["place"~"isolated_dwelling|hamlet|village|town|city|suburb"](around:{radius},{lat},{lon});
      way["building"](around:{radius},{lat},{lon});
      way["highway"~"residential|tertiary|secondary|primary|trunk|living_street|unclassified|service"](around:{radius},{lat},{lon});
    );
    out tags center;
    """
    try:
        resp = requests.post("https://overpass-api.de/api/interpreter", data={"data": query}, timeout=7)
        if resp.status_code != 200:
            return None
        elements = resp.json().get("elements", [])

        has_forest_or_protected = False
        has_water = False
        has_settlement_or_structure = False

        for el in elements:
            tags = el.get("tags", {})
            landuse = str(tags.get("landuse", "")).lower()
            natural = str(tags.get("natural", "")).lower()
            boundary = str(tags.get("boundary", "")).lower()

            if "forest" in landuse or natural in {"wood", "scrub", "bare_rock"} or boundary in {"national_park", "protected_area"}:
                has_forest_or_protected = True
            if landuse in {"reservoir", "basin"} or natural in {"water", "wetland"}:
                has_water = True
            if "building" in tags or "highway" in tags or "place" in tags:
                has_settlement_or_structure = True

        return {
            "has_forest_or_protected": has_forest_or_protected,
            "has_water": has_water,
            "has_settlement_or_structure": has_settlement_or_structure,
        }
    except Exception:
        return None

def check_site_habitability(lat, lon, address_text, force_mode="Auto-Detect"):
    """
    Checks whether a location is a forest/uninhabited area, water body, or isolated place.
    Returns (is_possible: bool, status_label: str, reason_detail: str)
    """
    if force_mode == "Force: Water Body":
        return False, "NOT POSSIBLE (Water Body)", "Site falls within or on a water body; establishing a shop is not possible."
    if force_mode == "Force: Uninhabited Area":
        return False, "NOT POSSIBLE (Uninhabited / Forest Area)", "Site is in an uninhabited/forest/protected zone; establishing a shop is not possible."
    if force_mode == "Force: Isolated / No Population":
        return False, "NOT POSSIBLE (Isolated Place)", "Site is isolated with no viable population catchment; establishing a shop is not possible."

    combined_texts = [(address_text or "").lower()]

    # Always inspect reverse-geocoded address for forest/terrain/water indicators
    try:
        rev = geolocator.reverse((lat, lon), timeout=6)
        if rev and rev.address:
            combined_texts.append(rev.address.lower())
    except Exception:
        pass

    full_text = " | ".join(combined_texts)

    for kw in WATER_KEYWORDS:
        if kw in full_text:
            return False, "NOT POSSIBLE (Water Body)", f"Detected water-body feature ('{kw}') near ({lat:.5f}, {lon:.5f}); it is not possible to establish a shop."

    for kw in UNINHABITED_KEYWORDS:
        if kw in full_text:
            return False, "NOT POSSIBLE (Uninhabited / Forest Area)", f"Detected forest/uninhabited terrain indicator ('{kw}') near ({lat:.5f}, {lon:.5f}); it is not possible to establish a shop."

    osm_ctx = check_osm_site_context(lat, lon, radius=300)
    if osm_ctx is not None:
        if osm_ctx["has_water"] and not osm_ctx["has_settlement_or_structure"]:
            return False, "NOT POSSIBLE (Water Body)", f"OSM spatial layer shows a water body with no built/inhabited structures within 300m of ({lat:.5f}, {lon:.5f}); shop establishment is not possible."
        if osm_ctx["has_forest_or_protected"] and not osm_ctx["has_settlement_or_structure"]:
            return False, "NOT POSSIBLE (Uninhabited / Forest Area)", f"OSM spatial layer identifies forest/protected land with no settlement/built structures within 300m of ({lat:.5f}, {lon:.5f}); it is not possible to establish a shop."
        if not osm_ctx["has_settlement_or_structure"]:
            return False, "NOT POSSIBLE (Isolated Place)", f"No inhabited buildings, settlements, or road/amenity structures found within 300m of ({lat:.5f}, {lon:.5f}); location appears isolated and unviable for a shop."

    return True, "FEASIBLE (Populated / Accessible)", "Location shows habitable/accessible context for commercial retail evaluation."
