"""Data behind the weather topic: cities, the official Kalshi weather stations, and their daily markets."""

import math
from collections import namedtuple
from datetime import date, datetime, timedelta, timezone

City = namedtuple("City", "id name state lat lon")
Station = namedtuple("Station", "code name lat lon high_series low_series")

# Official settlement sites used by Kalshi weather markets. Rain markets come from the
# KXRAIN series (ticker suffix = code); temperature markets from the high/low series.
STATIONS = [
    Station("NYC", "New York City (Central Park)", 40.7789, -73.9692, "KXHIGHNY", "KXLOWTNYC"),
    Station("CHI", "Chicago (Midway)", 41.7868, -87.7522, "KXHIGHCHI", "KXLOWTCHI"),
    Station("MIA", "Miami", 25.7959, -80.2870, "KXHIGHMIA", "KXLOWTMIA"),
    Station("AUS", "Austin", 30.3208, -97.7604, "KXHIGHAUS", "KXLOWTAUS"),
    Station("DEN", "Denver", 39.8466, -104.6562, "KXHIGHDEN", "KXLOWTDEN"),
    Station("LAX", "Los Angeles", 33.9382, -118.3866, "KXHIGHLAX", "KXLOWTLAX"),
    Station("PHIL", "Philadelphia", 39.8733, -75.2268, "KXHIGHPHIL", "KXLOWTPHIL"),
    Station("ATL", "Atlanta", 33.6301, -84.4418, "KXHIGHTATL", "KXLOWTATL"),
    Station("BOS", "Boston", 42.3606, -71.0097, "KXHIGHTBOS", "KXLOWTBOS"),
    Station("DC", "Washington DC", 38.8483, -77.0342, "KXHIGHTDC", "KXLOWTDC"),
    Station("SEA", "Seattle", 47.4447, -122.3136, "KXHIGHTSEA", "KXLOWTSEA"),
    Station("SFO", "San Francisco", 37.7705, -122.4269, "KXHIGHTSFO", "KXLOWTSFO"),
    Station("HOU", "Houston", 29.6375, -95.2825, "KXHIGHTHOU", "KXLOWTHOU"),
    Station("DAL", "Dallas", 32.8998, -97.0403, "KXHIGHTDAL", "KXLOWTDAL"),
    Station("PHX", "Phoenix", 33.4278, -112.0037, "KXHIGHTPHX", "KXLOWTPHX"),
    Station("LV", "Las Vegas", 36.0719, -115.1634, "KXHIGHTLV", "KXLOWTLV"),
    Station("MIN", "Minneapolis", 44.8831, -93.2289, "KXHIGHTMIN", "KXLOWTMIN"),
    Station("NOLA", "New Orleans", 29.9934, -90.2580, "KXHIGHTNOLA", "KXLOWTNOLA"),
    Station("OKC", "Oklahoma City", 35.3889, -97.6006, "KXHIGHTOKC", "KXLOWTOKC"),
    Station("SATX", "San Antonio", 29.5443, -98.4839, "KXHIGHTSATX", "KXLOWTSATX"),
    Station("EWR", "Newark", 40.6825, -74.1694, "KXHIGHTEWR", "KXLOWTEWR"),
    Station("TTN", "Trenton", 40.2766, -74.8135, "KXHIGHTTTN", "KXLOWTTTN"),
    Station("CMH", "Columbus", 39.9914, -82.8808, None, None),
    Station("PIT", "Pittsburgh", 40.4915, -80.2329, None, None),
    Station("MKE", "Milwaukee", 42.9550, -87.9044, None, None),
    Station("LEX", "Lexington", 38.0365, -84.6060, None, None),
    Station("PVD", "Providence", 41.7225, -71.4325, None, None),
    Station("SGF", "Springfield", 37.2457, -93.3886, None, None),
    Station("CLL", "College Station", 30.5886, -96.3638, None, None),
    Station("ABQ", "Albuquerque", 35.0419, -106.6156, None, None),
]

CITIES = [
    City("ann-arbor-mi", "Ann Arbor", "MI", 42.2808, -83.7430),
    City("detroit-mi", "Detroit", "MI", 42.3314, -83.0458),
    City("grand-rapids-mi", "Grand Rapids", "MI", 42.9634, -85.6681),
    City("chicago-il", "Chicago", "IL", 41.8781, -87.6298),
    City("milwaukee-wi", "Milwaukee", "WI", 43.0389, -87.9065),
    City("madison-wi", "Madison", "WI", 43.0731, -89.4012),
    City("minneapolis-mn", "Minneapolis", "MN", 44.9778, -93.2650),
    City("columbus-oh", "Columbus", "OH", 39.9612, -82.9988),
    City("cleveland-oh", "Cleveland", "OH", 41.4993, -81.6944),
    City("cincinnati-oh", "Cincinnati", "OH", 39.1031, -84.5120),
    City("pittsburgh-pa", "Pittsburgh", "PA", 40.4406, -79.9959),
    City("philadelphia-pa", "Philadelphia", "PA", 39.9526, -75.1652),
    City("new-york-ny", "New York", "NY", 40.7128, -74.0060),
    City("brooklyn-ny", "Brooklyn", "NY", 40.6782, -73.9442),
    City("hoboken-nj", "Hoboken", "NJ", 40.7440, -74.0324),
    City("princeton-nj", "Princeton", "NJ", 40.3573, -74.6672),
    City("boston-ma", "Boston", "MA", 42.3601, -71.0589),
    City("providence-ri", "Providence", "RI", 41.8240, -71.4128),
    City("washington-dc", "Washington", "DC", 38.9072, -77.0369),
    City("baltimore-md", "Baltimore", "MD", 39.2904, -76.6122),
    City("atlanta-ga", "Atlanta", "GA", 33.7490, -84.3880),
    City("lexington-ky", "Lexington", "KY", 38.0406, -84.5037),
    City("nashville-tn", "Nashville", "TN", 36.1627, -86.7816),
    City("miami-fl", "Miami", "FL", 25.7617, -80.1918),
    City("orlando-fl", "Orlando", "FL", 28.5383, -81.3792),
    City("new-orleans-la", "New Orleans", "LA", 29.9511, -90.0715),
    City("houston-tx", "Houston", "TX", 29.7604, -95.3698),
    City("austin-tx", "Austin", "TX", 30.2672, -97.7431),
    City("san-antonio-tx", "San Antonio", "TX", 29.4241, -98.4936),
    City("dallas-tx", "Dallas", "TX", 32.7767, -96.7970),
    City("college-station-tx", "College Station", "TX", 30.6280, -96.3344),
    City("oklahoma-city-ok", "Oklahoma City", "OK", 35.4676, -97.5164),
    City("springfield-mo", "Springfield", "MO", 37.2090, -93.2923),
    City("denver-co", "Denver", "CO", 39.7392, -104.9903),
    City("boulder-co", "Boulder", "CO", 40.0150, -105.2705),
    City("albuquerque-nm", "Albuquerque", "NM", 35.0844, -106.6504),
    City("phoenix-az", "Phoenix", "AZ", 33.4484, -112.0740),
    City("las-vegas-nv", "Las Vegas", "NV", 36.1699, -115.1398),
    City("los-angeles-ca", "Los Angeles", "CA", 34.0522, -118.2437),
    City("san-diego-ca", "San Diego", "CA", 32.7157, -117.1611),
    City("san-francisco-ca", "San Francisco", "CA", 37.7749, -122.4194),
    City("oakland-ca", "Oakland", "CA", 37.8044, -122.2712),
    City("seattle-wa", "Seattle", "WA", 47.6062, -122.3321),
]

_CITY_BY_ID = {city.id: city for city in CITIES}
_STATION_BY_CODE = {station.code: station for station in STATIONS}

LOW_RISK_KM = 30
MEDIUM_RISK_KM = 150

BASIS_NOTES = {
    "low": "You're close to the official station, so its reading should match the weather you see.",
    "medium": "Weather at the station can differ from your street. Cover pays on the station's reading, not yours.",
    "high": "The closest official station is far away. Cover pays on its reading, which may not match your weather.",
}


def city(city_id):
    return _CITY_BY_ID.get(city_id)


def station(code):
    return _STATION_BY_CODE.get(code)


def distance_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def basis_risk(km):
    if km <= LOW_RISK_KM:
        return "low"
    if km <= MEDIUM_RISK_KM:
        return "medium"
    return "high"


def nearest_station(place, peril):
    """Nearest station that lists markets for this peril, with its distance in km."""
    candidates = [s for s in STATIONS if peril == "rain" or (s.high_series if peril == "heat" else s.low_series)]
    best = min(candidates, key=lambda s: distance_km(place.lat, place.lon, s.lat, s.lon))
    return best, distance_km(place.lat, place.lon, best.lat, best.lon)


RAIN_SERIES = "KXRAIN"
CATEGORY = "Climate and Weather"
CUTOFF = timedelta(minutes=10)

PERILS = {
    "rain": {"name": "Rain", "description": "Pays when measurable rain falls on a covered day."},
    "heat": {"name": "Heat", "description": "Pays when the daily high climbs past a threshold."},
    "cold": {"name": "Cold", "description": "Pays when the overnight low drops below a threshold."},
}

_MONTHS = {m: i for i, m in enumerate(["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}


def event_date(event_ticker):
    """KXHIGHNY-26OCT04 -> 2026-10-04."""
    stamp = event_ticker.rsplit("-", 1)[-1]
    return date(2000 + int(stamp[:2]), _MONTHS[stamp[2:5]], int(stamp[5:7]))


def date_stamp(day):
    return day.strftime("%y%b%d").upper()


def series_for(peril, station):
    if peril == "rain":
        return RAIN_SERIES
    return station.high_series if peril == "heat" else station.low_series


def trigger_label(peril, market):
    if peril == "rain":
        return "Any measurable rain"
    subtitle = market.get("yes_sub_title") or ""
    return f"High of {subtitle}" if peril == "heat" else f"Low of {subtitle}"


def matches(peril, station, market):
    if peril == "rain":
        return market.get("ticker", "").endswith(f"-{station.code}")
    wanted = "greater" if peril == "heat" else "less"
    return market.get("strike_type") == wanted


def triggers(market_data, peril, station, now=None):
    """Open, bookable markets for this peril at this station: [{ticker, date, label, close_time, market}]."""
    now = now or datetime.now(timezone.utc)
    series = series_for(peril, station)
    if not series:
        return []
    found = []
    for market in market_data.series_markets(series):
        if not matches(peril, station, market) or market.get("status") not in (None, "active", "open"):
            continue
        close_time = datetime.fromisoformat(market["close_time"].replace("Z", "+00:00"))
        if close_time - CUTOFF <= now:
            continue
        found.append(
            {
                "ticker": market["ticker"],
                "date": event_date(market["event_ticker"]).isoformat(),
                "label": trigger_label(peril, market),
                "close_time": close_time.isoformat(),
                "market": market,
            }
        )
    found.sort(key=lambda item: (item["date"], item["ticker"]))
    return found
