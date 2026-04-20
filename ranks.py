ranks = [
    {"name": "Ylijumala",      "odds": 100000, "color": 0xffffff, "score": 26},
    {"name": "Jumala",         "odds": 50000,  "color": 0xffe066, "score": 25},
    {"name": "Aurinkokeisari", "odds": 10000,  "color": 0xffd700, "score": 24},
    {"name": "Suurruhtinas",   "odds": 6000,   "color": 0xffb3ff, "score": 23},
    {"name": "Paavi",          "odds": 4500,   "color": 0xfff0b3, "score": 22},
    {"name": "Arkkipiispa",    "odds": 3000,   "color": 0xffcc66, "score": 20},
    {"name": "Keisari",        "odds": 2000,   "color": 0xff4d4d, "score": 19},
    {"name": "Kuningas",       "odds": 1800,   "color": 0xffcc00, "score": 18},
    {"name": "Prinssi",        "odds": 1650,   "color": 0xffd1dc, "score": 17},
    {"name": "Suurherttua",    "odds": 1400,   "color": 0x9b5de5, "score": 16},
    {"name": "Suurvisiiri",    "odds": 1200,   "color": 0xc77dff, "score": 15},
    {"name": "Herttua",        "odds": 1000,   "color": 0x4d96ff, "score": 14},
    {"name": "Emiiri",         "odds": 850,    "color": 0x00bbf9, "score": 13},
    {"name": "Markiisi",       "odds": 700,    "color": 0x00f5d4, "score": 12},
    {"name": "Jaarli",         "odds": 600,    "color": 0x2ec4b6, "score": 11},
    {"name": "Kreivi",         "odds": 500,    "color": 0x38b000, "score": 10},
    {"name": "Paroni",         "odds": 400,    "color": 0x70e000, "score": 9},
    {"name": "Vapaaherra",     "odds": 300,    "color": 0x80ed99, "score": 8},
    {"name": "Lordi",          "odds": 200,    "color": 0x577590, "score": 7},
    {"name": "Baronetti",      "odds": 150,    "color": 0x4d4dff, "score": 6},
    {"name": "Ritari",         "odds": 100,    "color": 0xa0c4ff, "score": 5},
    {"name": "Aseenkantaja",   "odds": 50,     "color": 0xbdbdbd, "score": 4},
    {"name": "Säätyläinen",    "odds": 30,     "color": 0x8d99ae, "score": 3},
    {"name": "Talonpoika",     "odds": 10,     "color": 0x6c757d, "score": 2},
    {"name": "Orja",           "odds": 2,      "color": 0x1a1a1a, "score": 1},
]

# O(1) name lookup — built once at import time
RANK_BY_NAME: dict = {r["name"]: r for r in ranks}

# Precomputed weights for random.choices() — O(1) rolling
_RANK_NAMES:   list = [r["name"] for r in ranks]
_RANK_WEIGHTS: list = [1 / r["odds"] for r in ranks]
