"""Approximate country centroids and a rough spread, in degrees.

Used for two things: placing synthetic fixture events, and letting the web app
fly the map to a country. Precision is deliberately low; these are eyeball
centroids, not survey data, and nothing quantitative depends on them.
"""

CENTROIDS = {
    "Saudi Arabia": (45.0, 24.0, 4.5),
    "Iran": (53.0, 32.5, 5.0),
    "Iraq": (43.7, 33.2, 2.5),
    "United Arab Emirates": (54.0, 24.0, 1.2),
    "Kuwait": (47.6, 29.3, 0.6),
    "Qatar": (51.2, 25.3, 0.5),
    "Oman": (56.5, 21.0, 2.5),
    "Bahrain": (50.55, 26.05, 0.2),
    "Libya": (17.5, 27.0, 5.0),
    "Algeria": (2.6, 28.0, 6.0),
    "Egypt": (30.0, 26.8, 3.5),
    "Tunisia": (9.5, 34.0, 1.8),
    "Morocco": (-6.0, 31.8, 3.0),
    "Nigeria": (8.1, 9.6, 3.5),
    "Venezuela": (-66.5, 7.1, 3.5),
    "Kazakhstan": (68.0, 48.0, 7.0),
    "Angola": (17.9, -11.2, 4.5),
    "Israel": (35.0, 31.5, 0.9),
    "Palestine": (35.1, 31.9, 0.5),
    "Lebanon": (35.9, 33.9, 0.5),
    "Syria": (38.5, 35.0, 2.0),
    "Jordan": (36.5, 31.3, 1.5),
    "Turkey": (35.0, 39.0, 4.5),
    "Ukraine": (31.2, 48.4, 3.5),
    "Russia": (60.0, 58.0, 15.0),
    "Belarus": (28.0, 53.7, 2.0),
    "Moldova": (28.5, 47.2, 0.8),
    "Pakistan": (69.3, 30.4, 4.0),
    "Afghanistan": (66.0, 33.9, 3.0),
    "India": (79.0, 22.0, 7.0),
    "Azerbaijan": (47.6, 40.4, 1.3),
    "Armenia": (45.0, 40.2, 0.8),
    "China": (104.0, 35.0, 12.0),
    "Taiwan": (121.0, 23.7, 0.8),
    "North Korea": (127.0, 40.0, 1.5),
    "South Korea": (127.8, 36.4, 1.3),
    "Philippines": (122.0, 12.5, 3.5),
    "Indonesia": (118.0, -2.5, 10.0),
    "Sudan": (30.0, 15.5, 4.5),
    "Ethiopia": (39.6, 8.6, 3.5),
    "Somalia": (46.2, 5.2, 3.5),
    "Mali": (-3.5, 17.5, 4.5),
    "Niger": (9.5, 17.6, 4.5),
    "Burkina Faso": (-1.6, 12.3, 2.0),
    "Chad": (18.7, 15.5, 4.5),
    "Democratic Republic of Congo": (23.6, -2.9, 5.5),
    "Mozambique": (35.5, -18.0, 4.5),
    "Mexico": (-102.5, 23.6, 5.5),
    "Colombia": (-74.3, 4.6, 3.5),
    "Brazil": (-51.9, -14.2, 8.0),
    "Myanmar": (96.0, 21.0, 3.5),
    "Yemen": (47.5, 15.5, 2.5),
}


def centroid(country):
    return CENTROIDS.get(country)
