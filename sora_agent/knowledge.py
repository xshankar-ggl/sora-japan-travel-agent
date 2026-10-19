"""Curated Japan-specific domain knowledge base for Sora.

Includes:
- Post-October 2023 National JR Pass & Regional Pass pricing and coverage
- Shinkansen & Limited Express fare, duration, and Nozomi/Mizuho supplement tables
- Regional rail vs. domestic air door-to-door comparisons
- IC card rules (Suica, PASMO, ICOCA, Apple Wallet, Welcome Suica)
- Month-by-month seasonal travel calendar (Sakura, Koyo, Matsuri, crowd alerts)
- Cultural etiquette and logistics reference (Ryokan/Onsen, Konbini, Shrines/Temples, Takkyubin)
- Geographic neighborhood clusters for day-by-day itinerary generation
"""

from __future__ import annotations
from typing import Any

# National JR Pass prices (in JPY) after the October 2023 price revision
NATIONAL_JR_PASS_PRICES: dict[str, dict[int, int]] = {
    "ordinary": {
        7: 50000,
        14: 80000,
        21: 100000,
    },
    "green": {
        7: 70000,
        14: 110000,
        21: 140000,
    },
}

# Regional JR Passes that frequently beat the National JR Pass
REGIONAL_JR_PASSES: dict[str, dict[str, Any]] = {
    "kansai_hiroshima": {
        "name": "JR West Kansai-Hiroshima Area Pass",
        "duration_days": 5,
        "price_jpy": 17000,
        "covered_cities": ["osaka", "kyoto", "nara", "kobe", "himeji", "okayama", "hiroshima", "miyajima", "kinosaki"],
        "notes": (
            "Covers Sanyo Shinkansen (including Nozomi/Mizuho!) between Shin-Osaka and Hiroshima, "
            "plus JR Miyajima Ferry. Note: Does NOT cover the Kyoto to Shin-Osaka Shinkansen segment "
            "(use JR Special Rapid Service between Kyoto and Shin-Osaka instead, 28 mins)."
        ),
    },
    "hokuriku_arch": {
        "name": "Hokuriku Arch Pass",
        "duration_days": 7,
        "price_jpy": 30000,
        "covered_cities": ["tokyo", "kanazawa", "toyama", "fukui", "tsuruga", "kyoto", "osaka", "nara"],
        "notes": (
            "Covers Tokyo to Kanazawa/Tsuruga via Hokuriku Shinkansen (Kagayaki/Hakutaka) and "
            "Thunderbird Limited Express from Tsuruga to Kyoto/Osaka. Ideal for the Tokyo-Kanazawa-Kyoto-Osaka route."
        ),
    },
    "jr_east_tohoku": {
        "name": "JR East Pass (Tohoku Area)",
        "duration_days": 5,
        "price_jpy": 30000,
        "covered_cities": ["tokyo", "nikko", "sendai", "morioka", "aomori", "yamagata", "akita"],
        "notes": "Covers Tohoku, Yamagata, and Akita Shinkansen lines (including Hayabusa). Pays off with a single Tokyo-Aomori round trip.",
    },
    "jr_kyushu_north": {
        "name": "JR Kyushu Rail Pass (Northern Kyushu)",
        "duration_days": 5,
        "price_jpy": 15000,
        "covered_cities": ["fukuoka", "hakata", "kumamoto", "beppu", "yufuin", "nagasaki", "arita"],
        "notes": "Covers Kyushu Shinkansen (Hakata-Kumamoto), Nishi-Kyushu Shinkansen, and scenic trains like Yufuin no Mori.",
    },
    "jr_tokyo_wide": {
        "name": "JR Tokyo Wide Pass",
        "duration_days": 3,
        "price_jpy": 15000,
        "covered_cities": ["tokyo", "kawaguchiko", "nikko", "karuizawa", "gala_yuzawa", "izu"],
        "notes": "Great for 3 consecutive days of side trips from Tokyo (Fuji Excursion to Kawaguchiko, Shinkansen to Karuizawa/Gala Yuzawa, Nikko).",
    },
}

# Standard one-way reserved-seat rail fares (in JPY) and travel times (in minutes)
RAIL_ROUTES: dict[tuple[str, str], dict[str, Any]] = {
    ("tokyo", "kyoto"): {
        "fare_jpy": 14170,
        "green_fare_jpy": 19040,
        "nozomi_supplement_jpy": 4960,
        "duration_mins": 135,
        "train_name": "Tokaido Shinkansen (Nozomi / Hikari)",
        "scenic_tip": "Book Seat E (2-seat side in Ordinary) for views of Mt. Fuji around Shin-Fuji Station (~40-45 mins from Tokyo).",
    },
    ("tokyo", "osaka"): {
        "fare_jpy": 14720,
        "green_fare_jpy": 19590,
        "nozomi_supplement_jpy": 4960,
        "duration_mins": 150,
        "train_name": "Tokaido Shinkansen (Nozomi / Hikari)",
        "scenic_tip": "Book Seat E for Mt. Fuji views; arrive at Shin-Osaka Station and transfer to JR or Midosuji Metro for Umeda/Namba.",
    },
    ("tokyo", "hiroshima"): {
        "fare_jpy": 19760,
        "green_fare_jpy": 27000,
        "nozomi_supplement_jpy": 6500,
        "duration_mins": 235,
        "train_name": "Tokaido-Sanyo Shinkansen (Nozomi / Hikari+Sakura)",
        "scenic_tip": "Direct via Nozomi (approx. 3h 55m), or transfer at Shin-Osaka/Himeji from Hikari to Sakura if using a JR Pass without Nozomi supplement.",
    },
    ("tokyo", "kanazawa"): {
        "fare_jpy": 14380,
        "green_fare_jpy": 20070,
        "nozomi_supplement_jpy": 0,
        "duration_mins": 150,
        "train_name": "Hokuriku Shinkansen (Kagayaki / Hakutaka)",
        "scenic_tip": "Kagayaki is all-reserved; covered 100% by JR Pass and Hokuriku Arch Pass with no extra supplement.",
    },
    ("kanazawa", "kyoto"): {
        "fare_jpy": 7000,
        "green_fare_jpy": 10500,
        "nozomi_supplement_jpy": 0,
        "duration_mins": 130,
        "train_name": "Hokuriku Shinkansen (Kanazawa-Tsuruga) + Limited Express Thunderbird (Tsuruga-Kyoto)",
        "scenic_tip": "Since March 2024, transfer at Tsuruga Station (seamless 8-minute cross-platform/concours transfer).",
    },
    ("kyoto", "osaka"): {
        "fare_jpy": 580,
        "green_fare_jpy": 580,
        "nozomi_supplement_jpy": 0,
        "duration_mins": 29,
        "train_name": "JR Kyoto Line Special Rapid (Shinkaisoku) or Hankyu/Keihan Line",
        "scenic_tip": "Do not take the Shinkansen between Kyoto and Osaka—JR Special Rapid takes you station-to-station (Kyoto to Osaka/Umeda) in 29 mins for ¥580.",
    },
    ("kyoto", "nara"): {
        "fare_jpy": 1280,
        "green_fare_jpy": 1280,
        "nozomi_supplement_jpy": 0,
        "duration_mins": 35,
        "train_name": "Kintetsu Limited Express or JR Nara Line (Miyakoji Rapid)",
        "scenic_tip": "Kintetsu Nara Station is 10-15 minutes closer on foot to Nara Park & Todai-ji than JR Nara Station.",
    },
    ("osaka", "hiroshima"): {
        "fare_jpy": 10950,
        "green_fare_jpy": 14680,
        "nozomi_supplement_jpy": 4180,
        "duration_mins": 85,
        "train_name": "Sanyo Shinkansen (Nozomi / Mizuho / Sakura)",
        "scenic_tip": "Covered INCLUDING Nozomi/Mizuho by the 5-day JR West Kansai-Hiroshima Area Pass (¥17,000).",
    },
    ("kyoto", "hiroshima"): {
        "fare_jpy": 11940,
        "green_fare_jpy": 15890,
        "nozomi_supplement_jpy": 4180,
        "duration_mins": 100,
        "train_name": "JR Special Rapid to Shin-Osaka + Sanyo Shinkansen to Hiroshima",
        "scenic_tip": "Pair with a stopover at Himeji Castle (coin lockers & luggage storage available at Himeji Station).",
    },
    ("hiroshima", "fukuoka"): {
        "fare_jpy": 9100,
        "green_fare_jpy": 12830,
        "nozomi_supplement_jpy": 3200,
        "duration_mins": 65,
        "train_name": "Sanyo Shinkansen to Hakata Station",
        "scenic_tip": "Arrives right at Hakata Station in central Fukuoka.",
    },
    ("tokyo", "fukuoka"): {
        "fare_jpy": 23810,
        "green_fare_jpy": 32050,
        "nozomi_supplement_jpy": 8140,
        "duration_mins": 300,
        "train_name": "Tokaido-Sanyo Shinkansen (Nozomi)",
        "scenic_tip": "5 hours on the train; compare with Haneda -> Fukuoka (FUK) flights where FUK airport is only 5 mins by subway from Hakata Station!",
    },
    ("tokyo", "sendai"): {
        "fare_jpy": 11410,
        "green_fare_jpy": 15080,
        "nozomi_supplement_jpy": 0,
        "duration_mins": 90,
        "train_name": "Tohoku Shinkansen (Hayabusa)",
        "scenic_tip": "Hayabusa is all-reserved; fully covered by JR Pass and JR East Tohoku Pass.",
    },
    ("tokyo", "hakodate"): {
        "fare_jpy": 23430,
        "green_fare_jpy": 30990,
        "nozomi_supplement_jpy": 0,
        "duration_mins": 240,
        "train_name": "Tohoku-Hokkaido Shinkansen (Hayabusa via Seikan Tunnel)",
        "scenic_tip": "Arrives at Shin-Hakodate-Hokuto; take the Hakodate Liner (15 mins) to Hakodate Station.",
    },
    ("tokyo", "sapporo"): {
        "fare_jpy": 29110,
        "green_fare_jpy": 38800,
        "nozomi_supplement_jpy": 0,
        "duration_mins": 470,
        "train_name": "Hokkaido Shinkansen to Shin-Hakodate-Hokuto + Limited Express Hokuto to Sapporo",
        "scenic_tip": "Nearly 8 hours by rail! Domestic air (Haneda to New Chitose CTS) is strongly preferred unless stopping in Tohoku/Hakodate.",
    },
    ("tokyo", "hakone"): {
        "fare_jpy": 2470,
        "green_fare_jpy": 2470,
        "nozomi_supplement_jpy": 0,
        "duration_mins": 75,
        "train_name": "Odakyu Romancecar (Shinjuku to Hakone-Yumoto) or Tokaido Shinkansen to Odawara",
        "scenic_tip": "Pair with the Hakone Freepass for cable car, ropeway, Lake Ashi pirate ship, and Tozan buses.",
    },
    ("hakone", "kyoto"): {
        "fare_jpy": 12320,
        "green_fare_jpy": 16890,
        "nozomi_supplement_jpy": 0,
        "duration_mins": 125,
        "train_name": "Tokaido Shinkansen Hikari (board at Odawara Station direct to Kyoto)",
        "scenic_tip": "Take the Hakone Tozan train/bus down to Odawara Station and catch a direct Hikari Shinkansen to Kyoto (no need to backtrack to Tokyo!).",
    },
    ("tokyo", "nikko"): {
        "fare_jpy": 3300,
        "green_fare_jpy": 3300,
        "nozomi_supplement_jpy": 0,
        "duration_mins": 110,
        "train_name": "Tobu Spacia X (Asakusa to Tobu-Nikko) or Tohoku Shinkansen + JR Nikko Line",
        "scenic_tip": "Tobu Nikko Pass + Spacia X from Asakusa is the most direct and scenic option.",
    },
    ("tokyo", "takayama"): {
        "fare_jpy": 16500,
        "green_fare_jpy": 22000,
        "nozomi_supplement_jpy": 0,
        "duration_mins": 265,
        "train_name": "Tokaido Shinkansen to Nagoya + JR Hida Wide View Limited Express to Takayama",
        "scenic_tip": "The JR Hida Hybrid Limited Express through the Hida River gorge is one of Japan's most scenic train rides.",
    },
}

# Rail vs. Domestic Air comparison database
RAIL_VS_AIR_CORRIDORS: dict[tuple[str, str], dict[str, Any]] = {
    ("tokyo", "kyoto"): {
        "winner": "rail",
        "headline": "Shinkansen wins decisively (Kyoto has no commercial airport).",
        "rail": {
            "mode": "Tokaido Shinkansen (Nozomi)",
            "station_to_station_mins": 135,
            "door_to_door_mins": 165,
            "cost_jpy_range": "¥13,320 - ¥14,170 (SmartEX fare)",
            "frequency": "Every 5-10 minutes",
            "pros": [
                "City center (Tokyo/Shinagawa) directly to central Kyoto Station",
                "Zero airport security wait; arrive 15 mins before departure",
                "Iconic Mt. Fuji view from Seat E",
                "Generous legroom & ekiben (train bento) experience",
            ],
        },
        "air": {
            "mode": "Flight to Osaka Itami (ITM) or Kansai (KIX) + Limousine Bus/Haruka Express to Kyoto",
            "airport_to_airport_mins": 65,
            "door_to_door_mins": 240,
            "cost_jpy_range": "¥12,000 - ¥25,000 (incl. airport transfers)",
            "pros": ["Useful only if connecting directly from an international flight at Haneda/Narita"],
        },
    },
    ("tokyo", "osaka"): {
        "winner": "rail",
        "headline": "Shinkansen wins for convenience, frequency, and door-to-door time.",
        "rail": {
            "mode": "Tokaido Shinkansen (Nozomi)",
            "station_to_station_mins": 150,
            "door_to_door_mins": 180,
            "cost_jpy_range": "¥13,870 - ¥14,720",
            "frequency": "Every 5-10 minutes",
            "pros": ["Depart from Tokyo or Shinagawa every few minutes", "No baggage drop cutoff or liquid restrictions"],
        },
        "air": {
            "mode": "Haneda (HND) to Osaka Itami (ITM)",
            "airport_to_airport_mins": 65,
            "door_to_door_mins": 195,
            "cost_jpy_range": "¥10,000 - ¥22,000",
            "pros": ["Itami Airport is only 25-30 mins from Umeda", "JAL/ANA Explorer fares can occasionally be cheaper than rail"],
        },
    },
    ("tokyo", "hiroshima"): {
        "winner": "rail_slight_edge",
        "headline": "Shinkansen wins on door-to-door convenience because Hiroshima Airport (HIJ) is 50 minutes outside the city.",
        "rail": {
            "mode": "Tokaido-Sanyo Shinkansen (Nozomi)",
            "station_to_station_mins": 235,
            "door_to_door_mins": 265,
            "cost_jpy_range": "¥19,000 - ¥19,760",
            "frequency": "3-4 direct Nozomi trains per hour",
            "pros": [
                "Drops you directly at Hiroshima Station in the city center",
                "Allows easy en-route stopover at Himeji Castle or Kurashiki",
                "Comparable door-to-door time (~4h 20m) without airport bus transfers",
            ],
        },
        "air": {
            "mode": "Haneda (HND) to Hiroshima Airport (HIJ) + 50-min Limousine Bus",
            "airport_to_airport_mins": 85,
            "door_to_door_mins": 240,
            "cost_jpy_range": "¥12,000 - ¥24,000 (+ ¥1,450 airport bus)",
            "pros": ["Slightly less sitting time on a single vehicle", "Good option if flying open-jaw or using JAL Japan Explorer Pass"],
        },
    },
    ("tokyo", "fukuoka"): {
        "winner": "air",
        "headline": "Domestic Air wins decisively—Fukuoka Airport (FUK) is uniquely 5 minutes by subway from Hakata Station!",
        "rail": {
            "mode": "Tokaido-Sanyo Shinkansen (Nozomi)",
            "station_to_station_mins": 300,
            "door_to_door_mins": 330,
            "cost_jpy_range": "¥23,000 - ¥23,810",
            "frequency": "2-3 direct trains per hour",
            "pros": ["Great only if breaking up the trip in Kyoto, Osaka, or Hiroshima along the way"],
        },
        "air": {
            "mode": "Haneda (HND) to Fukuoka Airport (FUK)",
            "airport_to_airport_mins": 115,
            "door_to_door_mins": 195,
            "cost_jpy_range": "¥11,000 - ¥22,000",
            "pros": [
                "Fukuoka Airport (FUK) is inside the city: 5 mins to Hakata Station, 11 mins to Tenjin by subway!",
                "Saves over 2 hours door-to-door and is usually ¥5,000–¥10,000 cheaper than the Shinkansen",
            ],
        },
    },
    ("tokyo", "sapporo"): {
        "winner": "air",
        "headline": "Domestic Air wins overwhelmingly (1.5h flight vs. nearly 8 hours by train).",
        "rail": {
            "mode": "Hokkaido Shinkansen to Shin-Hakodate-Hokuto + Hokuto Limited Express to Sapporo",
            "station_to_station_mins": 470,
            "door_to_door_mins": 500,
            "cost_jpy_range": "¥29,110",
            "frequency": "Every 1-2 hours",
            "pros": ["Recommended ONLY if doing a multi-day Tohoku + Hakodate overland itinerary"],
        },
        "air": {
            "mode": "Haneda (HND) or Narita (NRT) to New Chitose (CTS) + 37-min JR Rapid Airport train",
            "airport_to_airport_mins": 95,
            "door_to_door_mins": 215,
            "cost_jpy_range": "¥9,000 - ¥20,000",
            "pros": [
                "One of the world's busiest air corridors with flights every 15-30 minutes",
                "Saves 4.5+ hours and costs less than half the rail fare",
            ],
        },
    },
    ("tokyo", "okinawa"): {
        "winner": "air",
        "headline": "Domestic Air is the only viable option (Okinawa is a subtropical island chain).",
        "rail": {
            "mode": "Not applicable (no rail link to Okinawa; Naha has only the Yui Rail monorail)",
            "station_to_station_mins": 0,
            "door_to_door_mins": 0,
            "cost_jpy_range": "N/A",
            "frequency": "N/A",
            "pros": [],
        },
        "air": {
            "mode": "Haneda (HND) or Narita (NRT) to Naha (OKA)",
            "airport_to_airport_mins": 170,
            "door_to_door_mins": 250,
            "cost_jpy_range": "¥10,000 - ¥25,000",
            "pros": ["Direct connection to Naha Airport, which links directly to the Yui Rail monorail (Suica/ICOCA accepted!)"],
        },
    },
    ("tokyo", "kanazawa"): {
        "winner": "rail",
        "headline": "Hokuriku Shinkansen wins easily (2.5 hours direct to central Kanazawa Station).",
        "rail": {
            "mode": "Hokuriku Shinkansen (Kagayaki)",
            "station_to_station_mins": 150,
            "door_to_door_mins": 180,
            "cost_jpy_range": "¥14,380",
            "frequency": "Hourly",
            "pros": ["Direct to Kanazawa's iconic Tsuzumi-mon Gate station", "Scenic views of the Japanese Alps and Toyama Bay"],
        },
        "air": {
            "mode": "Haneda (HND) to Komatsu Airport (KMQ) + 40-min airport bus",
            "airport_to_airport_mins": 65,
            "door_to_door_mins": 210,
            "cost_jpy_range": "¥13,000 - ¥22,000",
            "pros": ["Only useful when connecting directly at Haneda from an international arrival"],
        },
    },
}

# Month-by-month seasonal guide for Japan
SEASONAL_GUIDE: dict[int, dict[str, Any]] = {
    1: {
        "season": "Mid-Winter (Fuyu)",
        "weather_summary": "Crisp, sunny, and dry on the Pacific side (Tokyo/Kyoto: 2°C–10°C); heavy powder snow ('Japow') in Hokkaido, Tohoku, and the Sea of Japan coast.",
        "crowd_alerts": "Jan 1–3 is Shogatsu (New Year)—Japan's most important holiday. Many museums, small shops, and restaurants close Jan 1–3, while major shrines (Meiji Jingu, Fushimi Inari) have millions of Hatsumode visitors.",
        "highlights": [
            "World-class powder skiing in Niseko, Furano, Hakuba, and Nozawa Onsen",
            "Snow monkeys (Japanese macaques) soaking in hot springs at Jigokudani (Nagano)",
            "Shirakawa-go winter snow illuminations (advance lottery/booking required)",
            "Outdoor rotenburo onsen baths surrounded by snow (Yukimi-buro)",
        ],
        "seasonal_foods": ["Snow crab (Matsuba-gani / Echizen-gani)", "Oden & Nabe hot pots", "Fugu (blowfish)", "Yuzu citrus"],
        "packing_tips": ["Thermal base layers (Uniqlo Heattech)", "Waterproof non-slip boots for snow country", "Slip-on shoes for temple interiors"],
    },
    2: {
        "season": "Late Winter & Early Plum Blossoms",
        "weather_summary": "Coldest month in northern Japan; crisp and clear views of Mt. Fuji from Tokyo/Hakone/Kawaguchiko. Subtropical warmth begins in Okinawa.",
        "crowd_alerts": "Sapporo Snow Festival (early Feb) and Lunar New Year bring high hotel demand in Hokkaido—book 6+ months ahead.",
        "highlights": [
            "Sapporo Snow Festival, Otaru Snow Light Path, and Asahikawa Winter Festival",
            "Kawazu-zakura (early-blooming cherry blossoms) on the Izu Peninsula (mid-Feb to early March)",
            "Ume (plum blossom) festivals at Kitano Tenmangu (Kyoto) and Kairakuen (Mito)",
            "Highest statistical visibility for crystal-clear Mt. Fuji views",
        ],
        "seasonal_foods": ["Hokkaido miso ramen & soup curry", "Hiroshima oysters at peak plumpness", "Fresh strawberries (Amaou)"],
        "packing_tips": ["Windproof coat", "Pocket hand warmers (Kairo—sold at every konbini)", "Lip balm & moisturizer for dry air"],
    },
    3: {
        "season": "Early Spring & Sakura Kickoff (Haru)",
        "weather_summary": "Transition from chilly mornings to mild afternoons (6°C–16°C in Tokyo/Kyoto). Light rain showers ahead of warmer days.",
        "crowd_alerts": "Late March marks the start of peak Sakura season AND Japanese school spring break. Shinkansen and hotels require early booking.",
        "highlights": [
            "Late-March cherry blossom opening (Kaika) in Tokyo, Kyoto, Hiroshima, and Fukuoka",
            "Omizutori fire & water festival at Todai-ji Temple in Nara (March 1–14)",
            "Spring Sumo Grand Tournament (Haru Basho) in Osaka",
        ],
        "seasonal_foods": ["Sakura mochi", "Takenoko (fresh bamboo shoots)", "Tai (sea bream)", "Matcha spring parfaits"],
        "packing_tips": ["Layered clothing (light down vest + trench/jacket)", "Compact umbrella"],
    },
    4: {
        "season": "Peak Sakura & High Spring",
        "weather_summary": "Pleasant, mild temperatures (10°C–21°C) across Honshu. Cherry blossoms sweep northward into Kanazawa, Takayama, and Tohoku.",
        "crowd_alerts": "Early April is peak tourist season in Tokyo/Kyoto. April 29 begins **Golden Week** (April 29 – May 5), when domestic travel surges nationwide.",
        "highlights": [
            "Full bloom (Mankai) hanami picnics in Tokyo (Chidorigafuchi, Shinjuku Gyoen) and Kyoto (Philosopher's Path, Maruyama Park)",
            "Mid-to-late April sakura in Kanazawa (Kenroku-en), Hirosaki Castle, and Kakunodate",
            "Tateyama Kurobe Alpine Route snow walls (Yuki-no-Otani) opening mid-April",
            "Takayama Spring Festival (April 14–15)",
        ],
        "seasonal_foods": ["Hanami bento boxes", "Hotaru Ika (firefly squid from Toyama Bay)", "Spring cabbage & sansai (mountain vegetables)"],
        "packing_tips": ["Comfortable walking shoes (15,000–25,000 steps/day)", "Light cardigan for cool evenings"],
    },
    5: {
        "season": "Lush Green Spring (Shinryoku)",
        "weather_summary": "Arguably Japan's best weather after May 6: warm, sunny, low humidity (15°C–25°C) before the June rainy season.",
        "crowd_alerts": "**May 1–5 is Golden Week**—Tokaido/Sanyo/Hokuriku Nozomi trains become 100% reserved-seat only! After May 6, crowds drop sharply while weather is idyllic.",
        "highlights": [
            "Wisteria (Fuji) tunnels at Ashikaga Flower Park and Kawachi Fuji Garden",
            "Sanja Matsuri in Asakusa (Tokyo, 3rd weekend of May) and Aoi Matsuri in Kyoto (May 15)",
            "Late cherry blossoms in Hokkaido (Hakodate Goryokaku & Sapporo)",
            "Lush emerald moss gardens and maple foliage (Ao-momiji) in Kyoto",
        ],
        "seasonal_foods": ["Shincha (first-harvest green tea in Uji & Shizuoka)", "Katsuo no Tataki (seared bonito)"],
        "packing_tips": ["Breathable layers", "Sunglasses & sunscreen"],
    },
    6: {
        "season": "Early Summer & Tsuyu (Plum Rain Season)",
        "weather_summary": "Warm (20°C–28°C) with periodic rain showers during *Tsuyu* (early June to mid-July in Honshu). Note: **Hokkaido has no rainy season** and enjoys crisp, dry June weather!",
        "crowd_alerts": "Low international crowd levels and great hotel rates between Golden Week and July school holidays.",
        "highlights": [
            "Hydrangea (Ajisai) blooms at Kamakura (Meigetsuin, Hasedera) and Mimuroto-ji (Uji)",
            "Atmospheric, mist-shrouded moss temples in Kyoto (Saihō-ji / Kokedera, Sanzen-in)",
            "Hokkaido early flower fields in Furano & Biei with zero rainy-season humidity",
        ],
        "seasonal_foods": ["Unagi (grilled freshwater eel for stamina)", "Hamo (pike conger in Kyoto)", "Umeshu (plum wine)"],
        "packing_tips": ["Breathable rain shell", "Water-resistant sneakers", "Clear vinyl umbrella from any konbini"],
    },
    7: {
        "season": "High Summer, Matsuri & Alpine Hiking",
        "weather_summary": "Rainy season ends mid-July, followed by hot, humid summer (26°C–35°C in cities). Cool mountain air in the Japanese Alps and Hokkaido.",
        "crowd_alerts": "Kyoto hotels fill up around July 14–17 for Gion Matsuri. Mt. Fuji climbing season officially opens early July.",
        "highlights": [
            "Kyoto Gion Matsuri (whole month of July; grand Yamaboko Junko float procession on July 17 & 24)",
            "Osaka Tenjin Matsuri (July 24–25) & Sumidagawa Fireworks in Tokyo",
            "Peak lavender bloom in Furano, Hokkaido",
            "Climbing Mt. Fuji and hiking Kamikochi in the Northern Alps",
        ],
        "seasonal_foods": ["Kakigori (fluffy shaved ice)", "Zaru Soba & Somen (chilled noodles)", "Hokkaido Yubari melon", "Edamame & draft beer"],
        "packing_tips": ["UV sun umbrella (Higasa)", "Cooling body wipes (Gatsby/Biore from konbini)", "Handheld fan", "Moisture-wicking fabrics"],
    },
    8: {
        "season": "Peak Summer Festivals &花火 (Hanabi)",
        "weather_summary": "Hot and humid in central/southern Japan (28°C–36°C); occasional typhoons late in the month. Pleasant in Hokkaido and high elevations.",
        "crowd_alerts": "**Obon Holiday (approx. Aug 13–16)** is one of Japan's three peak domestic travel periods—Nozomi Shinkansen switches to all-reserved seating.",
        "highlights": [
            "Tohoku's Great Summer Festivals: Aomori Nebuta (Aug 2–7), Akita Kanto (Aug 3–6), Sendai Tanabata (Aug 6–8)",
            "Awa Odori dance festival in Tokushima & Daimonji Gozan Okuribi bonfires in Kyoto (Aug 16)",
            "Alpine retreats in Karuizawa, Kamikochi, and Nikko Chuzenji",
        ],
        "seasonal_foods": ["Hiyashi Chuka (chilled ramen)", "Grilled ayu (sweetfish) on skewers", "Watermelon & white peaches (Okayama)"],
        "packing_tips": ["Lightweight linen/technical clothing", "Electrolyte drinks (Pocari Sweat / Aquarius from vending machines)"],
    },
    9: {
        "season": "Late Summer to Early Autumn Transition",
        "weather_summary": "Warm early in the month (23°C–30°C), cooling pleasantly by late September. Peak typhoon watch window—keep 1 flexible buffer day in itineraries.",
        "crowd_alerts": "Silver Week (mid-to-late September three-day weekends) sees moderate domestic travel.",
        "highlights": [
            "First autumn foliage (Koyo) in Japan at Daisetsuzan National Park in Hokkaido (mid-Sept)",
            "Kishiwada Danjiri Matsuri (Osaka) & Tokyo Autumn Sumo Tournament",
            "Tsukimi (Autumn Moon Viewing) gardens and seasonal sweets",
        ],
        "seasonal_foods": ["Sanma (Pacific saury grilled over charcoal)", "Matsutake mushrooms", "Shine Muscat & Kyoho grapes"],
        "packing_tips": ["Light rain jacket", "Flexible Shinkansen booking apps (SmartEX) in case of weather schedule adjustments"],
    },
    10: {
        "season": "Crisp Autumn & Alpine Foliage (Aki)",
        "weather_summary": "Sunny, dry, and comfortable (12°C–22°C)—ideal walking weather across Japan.",
        "crowd_alerts": "Very popular month for both domestic and international travelers, especially in Nikko, Takayama, and Kyoto.",
        "highlights": [
            "Peak autumn foliage in Hokkaido, Tohoku, Nikko (mid-to-late Oct), Kamikochi, and Tateyama",
            "Takayama Autumn Festival (Oct 9–10) & Kurama Fire Festival in Kyoto (Oct 22)",
            "Kochia red broom grass hills at Hitachi Seaside Park",
        ],
        "seasonal_foods": ["Kuri (chestnut) rice & Mont Blanc desserts", "Yaki-imo (roasted sweet potatoes)", "Autumn salmon & ikura"],
        "packing_tips": ["Light jacket or fleece for mountain/evening excursions", "Good walking shoes"],
    },
    11: {
        "season": "Peak Autumn Foliage (Koyo) in Honshu & Kyushu",
        "weather_summary": "Crisp, clear days and chilly evenings (8°C–17°C). Fiery red maple leaves (*momiji*) and golden ginkgo avenues across Tokyo, Kyoto, and Kanazawa.",
        "crowd_alerts": "**Mid-to-late November is Kyoto's #1 peak season** (rivaling Sakura). Book Kyoto hotels and temple night illuminations early; visit top sites at 7:00 AM.",
        "highlights": [
            "Spectacular maple foliage in Kyoto (Tofuku-ji, Eikan-do, Kiyomizu-dera, Arashiyama) from mid-to-late November",
            "Golden ginkgo avenues in Tokyo (Meiji Jingu Gaien, Rikugien, Showa Kinen Park)",
            "Shichi-Go-San (7-5-3 festival) at shrines in mid-November & Kyushu Grand Sumo Tournament in Fukuoka",
        ],
        "seasonal_foods": ["Momiji tempura", "Persimmons (Kaki)", "Shin-soba (freshly harvested buckwheat noodles)", "Hotpot & early crab season"],
        "packing_tips": ["Warm mid-layer + coat for evening temple illuminations", "Scarf & gloves for late November"],
    },
    12: {
        "season": "Early Winter, Illuminations & Onsen Season",
        "weather_summary": "Crisp and dry in Tokyo/Kyoto/Osaka (4°C–12°C); early snowfalls in Hokkaido and the Japanese Alps.",
        "crowd_alerts": "Early-to-mid December is relatively uncrowded with great value! **Dec 28 – Jan 4 is New Year (Nenmatsu-Nenshi)** when domestic travel spikes and many attractions close.",
        "highlights": [
            "Late autumn foliage lingering into the first week of December in Tokyo and Osaka",
            "Spectacular winter illuminations (Roppongi Hills, Marunouchi, Nabana no Sato, Kobe Luminarie)",
            "Chichibu Night Festival (Dec 2–3) and Joya no Kane (108 New Year's Eve temple bell strikes on Dec 31)",
        ],
        "seasonal_foods": ["Toshikoshi Soba (New Year's Eve buckwheat noodles)", "Winter yellowtail (Kan-buri)", "KFC Christmas dinner (a quirky Japanese tradition!)"],
        "packing_tips": ["Winter coat", "Thermal base layers", "Slip-on shoes with warm socks for cold wooden temple floors"],
    },
}

# Cultural Etiquette & Japan Logistics Database
CULTURAL_TOPICS: dict[str, dict[str, Any]] = {
    "ryokan_onsen": {
        "title": "Ryokan (Traditional Inn) & Onsen (Hot Spring) Etiquette",
        "golden_rules": [
            "Check-in strictly on time (usually 15:00–17:00): Kaiseki multi-course dinners are prepared at a set hour (18:00 or 18:30). Arriving after 18:00 without notice can mean forfeiting dinner.",
            "Shoes off at the Genkan (entryway): Step up onto the raised floor in socks, then use provided slippers for hallways—and remove slippers BEFORE stepping onto tatami mats!",
            "Toilet slippers: Use the dedicated slippers inside the restroom and remember to swap back when exiting.",
            "Yukata rule: Always wrap the **LEFT side over the RIGHT side** (forming a 'Y' at the collar). Right-over-left is reserved strictly for dressing the deceased at funerals.",
            "Onsen washing ritual: Enter the bath area completely naked (no swimsuits). Sit on the low plastic stool and thoroughly wash & rinse your entire body BEFORE stepping into the hot spring water.",
            "Towel etiquette: Keep the small modesty towel out of the bathwater (place it on your head or on the side of the tub). Never wring it out into the bath.",
            "Tattoo policies: Many traditional public onsen restrict tattoos. Solutions: (1) Book a ryokan with a private bath (*Kashikiri-buro* or in-room open-air bath *Rotenburo*), (2) Visit 100% tattoo-friendly onsen towns like **Kinosaki Onsen** (all 7 public bathhouses allow tattoos!) or **Beppu**, or (3) Use waterproof flesh-colored cover stickers (*Tattoo Seal*) for small tattoos.",
        ],
    },
    "konbini": {
        "title": "Konbini (Convenience Store) Culture & Traveler Hacks",
        "golden_rules": [
            "The Big Three: **7-Eleven**, **FamilyMart**, and **Lawson** (+ Hokkaido favorite **Seicomart**). Open 24/7 with pristine, Michelin-worthy grab-and-go food.",
            "Must-try items: 7-Eleven Tamago Sando (egg salad sandwich), fresh-blended fruit smoothies, and Gold Label ramen; FamilyMart 'Famichiki' boneless fried chicken and butter-soy onigiri; Lawson 'Karaage-kun' nuggets and Uchi Café Premium Roll Cake.",
            "Onigiri wrapper trick: Pull tab '1' straight down around the bottom and out the back, then pull corners '2' and '3' horizontally so the crispy nori seaweed wraps around the rice right before eating.",
            "Hot vs. Cold drinks: In konbini and vending machines, **blue labels = cold** and **red/orange labels = hot** (hot canned coffee, corn potage, and royal milk tea in winter!).",
            "ATMs & Cash: **7-Eleven (7-Bank ATMs)** and Lawson ATMs reliably accept foreign Visa/Mastercard/Amex debit cards with low fees and English menus (always choose to be billed in **JPY**, not your home currency).",
            "Trash & Eating Etiquette: Do not walk while eating (*aruki-tabi* is frowned upon). Eat inside at the konbini's designated eat-in counter (note: 10% consumption tax vs. 8% takeaway) or just outside before disposing of wrappers in the store's sorted bins.",
            "Extra services: Forward luggage via Yamato Takkyubin, print documents/tickets at multi-copy machines, and buy Ghibli Museum / Disney / event tickets via Loppi (Lawson) or FamiPort.",
        ],
    },
    "shrines_temples_dining": {
        "title": "Shrines vs. Temples, Goshuincho & Dining Etiquette",
        "golden_rules": [
            "Shinto Shrine (Jinja / Jingu - marked by a Torii gate): Purify hands and mouth at the *Chozuya* water pavilion (left hand, right hand, water in cupped left hand to rinse mouth, tip ladle vertically to rinse handle). At the altar: toss a ¥5 coin (go-en = good fortune), ring the bell if present, **bow twice, clap twice, make your wish, and bow once deeply (2-2-1 rule)**.",
            "Buddhist Temple (Tera / Ji - marked by a Sanmon gate & incense burner): Purify at the water pavilion, waft incense smoke toward yourself for health/wisdom, toss a coin, and **bow quietly with hands pressed together in prayer (DO NOT CLAP at a Buddhist temple)**.",
            "Goshuincho (Temple/Shrine Stamp Book): Buy a dedicated accordion-fold book (*Goshuincho*, ¥1,500–¥2,500) and collect hand-brushed calligraphy seals (*Goshuin*, ¥300–¥500 each in cash). Never ask them to stamp a regular notebook.",
            "Zero Tipping Culture: **Never leave a tip** at restaurants, taxis, hotels, or bars—staff will literally chase you down the street to return your 'forgotten' change. At high-end ryokan, if you wish to thank a dedicated room attendant (*nakai-san*), place crisp bills inside a small decorative envelope (*pochibukuro*) at the start of the stay.",
            "Otoshi (Table Charge): Many izakayas serve a small appetizer (*otoshi*, ¥300–¥600 per person) automatically as a seating cover charge—this is standard practice, not a tourist scam.",
            "Tabelog Ratings: Unlike Western review sites, **3.5+ out of 5.0 on Tabelog means an elite top-3% restaurant** in Japan; anything 3.2–3.4 is genuinely great!",
        ],
    },
    "luggage_connectivity": {
        "title": "Luggage Forwarding (Takkyubin), Oversized Baggage & Connectivity",
        "golden_rules": [
            "Takkyubin (Luggage Delivery): Japan's secret weapon for stress-free travel. Use **Yamato Transport (Kuroneko / Black Cat logo)** from your hotel front desk or airport counter to ship large suitcases directly to your next hotel for ~¥2,200–¥3,000 per bag (next-day delivery). Travel to intermediate stops (like Hakone, Takayama, or Miyajima) with just a small backpack!",
            "Shinkansen 160cm Oversized Baggage Rule: On the **Tokaido, Sanyo, and Kyushu Shinkansen**, if your suitcase's total dimensions (Length + Width + Height) are between **160 cm and 250 cm**, you **MUST book a 'Seat with an Oversized Baggage Area' or 'Oversized Baggage Compartment'** in advance (free with a reserved seat, ¥1,000 penalty without reservation). Bags under 160 cm fit comfortably in the overhead rack!",
            "Coin Lockers & Ecbo Cloak: Major stations have IC-card-operated coin lockers (¥400–¥1,000). If full, use the **Ecbo Cloak** app to store bags at nearby cafes, tourist counters, and shops.",
            "Connectivity & Apps: Get an eSIM (Ubigi, Airalo, or Sakuramobile) or Airport Pocket Wi-Fi. Essential apps: **Google Maps** (shows exact platform numbers & best train car for exits), **Navitime / Japan Travel by Navitime** (filters by JR Pass eligibility), **SmartEX** (Shinkansen tickets), **GO / Uber** (taxis), and **Google Translate** (camera lens for vertical menus).",
            "Cash vs. Card: While IC cards and credit cards work at 85%+ of urban places, always carry **¥10,000–¥20,000 in cash (including ¥100 and ¥1,000 denominations)** for ramen ticket machines, temple admission, goshuin, and rural buses.",
        ],
    },
}

# City Neighborhood Clusters for Day-by-Day Itinerary Scaffolding
CITY_CLUSTERS: dict[str, list[dict[str, Any]]] = {
    "tokyo": [
        {
            "cluster_name": "Historic East Tokyo: Asakusa, Ueno & Yanaka",
            "morning": "Senso-ji Temple & Nakamise-dori in Asakusa (arrive by 8:30 AM before crowds), stroll Kappabashi Kitchen Town.",
            "afternoon": "Ueno Park museums or Ameyoko Market street food, followed by old-Tokyo nostalgic alleys of Yanaka Ginza.",
            "evening": "Tokyo Skytree sunset views or Sumida River izakaya hop; dinner of Monjayaki or Tempura in Asakusa.",
            "transit_tip": "Use Tokyo Metro Ginza Line (Japan's oldest subway) with Suica/PASMO.",
        },
        {
            "cluster_name": "West Side Icons: Meiji Jingu, Harajuku & Shibuya",
            "morning": "Forested torii path of Meiji Jingu Shrine & Yoyogi Park, then architectural stroll down Omotesando & Cat Street.",
            "afternoon": "Explore Shimokitazawa vintage shops & indie cafes (Keio Inokashira Line, 7 mins) or Shibuya Parco.",
            "evening": "Shibuya Sky sunset observation deck (book 4 weeks ahead!), Shibuya Crossing, and Nonbei Yokocho / Miyashita Park dinner.",
            "transit_tip": "Walkable downhill corridor from Harajuku/Meiji-Jingumae to Shibuya.",
        },
        {
            "cluster_name": "Central Imperial, Ginza & Shinjuku Neon",
            "morning": "Tsukiji Outer Market seafood breakfast (tamagoyaki, uni bowls) and Imperial Palace East Gardens.",
            "afternoon": "Ginza flagship depachika (basement food halls at Mitsukoshi/Ginza Six) and Itoya stationery.",
            "evening": "Tokyo Metropolitan Government Building light projection, Omoide Yokocho yakitori alley, and Golden Gai in Shinjuku.",
            "transit_tip": "Take Marunouchi Line directly from Ginza to Shinjuku.",
        },
        {
            "cluster_name": "Modern Art & Bay or Classic Day Trip (Kamakura / Nikko)",
            "morning": "teamLab Planets (Toyosu) or teamLab Borderless (Azabudai Hills) + Roppongi Hills Mori Art Museum.",
            "afternoon": "Daikanyama T-Site & Nakameguro canal cafes (or half-day excursion to Kamakura's Great Buddha & Hasedera).",
            "evening": "Ebisu Yokocho or Kichijoji Harmonica Yokocho for local neighborhood izakaya vibes.",
            "transit_tip": "Yurikamome Line for Toyosu/Odaiba or JR Shonan-Shinjuku Line (55 mins) for Kamakura.",
        },
    ],
    "kyoto": [
        {
            "cluster_name": "Southern & Eastern Classics: Fushimi Inari, Kiyomizu-dera & Gion",
            "morning": "Fushimi Inari Taisha by 7:00 AM to hike through the vermilion Senbon Torii gates in peace.",
            "afternoon": "Keihan Line to Kiyomizu-dera, walking downhill through preserved Sannenzaka & Ninenzaka lanes to Kodai-ji and Yasaka Shrine.",
            "evening": "Twilight stroll through Gion (Hanamikoji & Shirakawa Canal) and Pontocho Alley along the Kamogawa River.",
            "transit_tip": "Take JR Nara Line to Inari (5 mins from Kyoto Station), then Keihan Line from Fushimi-Inari to Kiyomizu-Gojo.",
        },
        {
            "cluster_name": "Western Bamboo & Northern Gold: Arashiyama & Kinkaku-ji",
            "morning": "Arashiyama Bamboo Grove by 7:30 AM, Tenryu-ji Zen garden, and scenic Okochi Sanso Villa with matcha.",
            "afternoon": "Randen tram + bus to Kinkaku-ji (Golden Pavilion) and the tranquil rock garden of Ryoan-ji.",
            "evening": "Nishiki Market late-afternoon grazing + Kyoto Pontocho or Kiyamachi kaiseki/obanzai dinner.",
            "transit_tip": "Use JR Sagano Line from Kyoto Station to Saga-Arashiyama (16 mins) instead of slow city buses.",
        },
        {
            "cluster_name": "Eastern Zen & Day Trip to Nara & Uji",
            "morning": "Nara Park deer, Todai-ji Great Buddha Hall, and lantern-lined Kasuga Taisha Shrine.",
            "afternoon": "Stop in Uji on the return to Kyoto for Byodo-in Phoenix Hall (featured on the ¥10 coin) and freshly whisked ceremonial matcha.",
            "evening": "Nanzen-ji monumental aqueduct or Kyoto Station Skyway & Ramen Koji.",
            "transit_tip": "JR Nara Line covers Kyoto -> Uji -> Nara cleanly on IC card or JR Pass.",
        },
    ],
    "osaka": [
        {
            "cluster_name": "Kitchen of Japan: Osaka Castle, Kuromon, Shinsekai & Dotonbori",
            "morning": "Osaka Castle Park & Museum, followed by Tenma or Kuromon Ichiba Market seafood snacks.",
            "afternoon": "Retro Showa-era vibes in Shinsekai (Tsutenkaku Tower & Kushikatsu Daruma—remember: no double-dipping in the communal sauce!) and Doguyasuji kitchenware arcade.",
            "evening": "Neon lights along Dotonbori Canal (Glico Running Man), Hozenji Yokocho moss-covered Fudo Myo-o statue, and takoyaki + okonomiyaki feast.",
            "transit_tip": "Osaka Metro Midosuji Line is the main north-south spine (Shin-Osaka -> Umeda -> Shinsaibashi -> Namba -> Tennoji).",
        },
        {
            "cluster_name": "Umeda Skyline, Nakazakicho Indie Cafes & Himeji/Kobe Option",
            "morning": "Half-day Shinkansen hop to Himeji Castle (Japan's finest original hilltop castle) and Koko-en Garden.",
            "afternoon": "Return via Kobe Sannomiya for authentic Kobe beef teppanyaki lunch, or explore Osaka's hipster Nakazakicho neighborhood.",
            "evening": "Umeda Sky Building Floating Garden Observatory and Fukushima-ku local izakaya crawl.",
            "transit_tip": "5-day JR West Kansai-Hiroshima Area Pass covers Shin-Osaka -> Himeji -> Kobe -> Hiroshima!",
        },
    ],
    "hiroshima": [
        {
            "cluster_name": "Peace Memorial Park & Sacred Miyajima Island",
            "morning": "Hiroshima Peace Memorial Park, Atomic Bomb Dome, and Peace Memorial Museum, followed by Shukkeien Garden.",
            "afternoon": "JR Sanyo Line + 10-min JR Ferry to Miyajima Island: Itsukushima Floating Torii Gate, Daisho-in Temple, and Mt. Misen ropeway.",
            "evening": "Stay overnight at a Miyajima ryokan to see the illuminated Torii at low/high tide, or dine on layered Hiroshima-style okonomiyaki at Okonomimura.",
            "transit_tip": "Forward large bags from Kyoto/Osaka directly to your next big city and bring an overnight pack for Hiroshima/Miyajima.",
        },
    ],
    "kanazawa": [
        {
            "cluster_name": "Samurai, Geisha & Edo-Era Gardens",
            "morning": "Kenroku-en (one of Japan's Three Great Gardens) at opening, adjacent Kanazawa Castle, and Omicho Market kaisendon (seafood bowl).",
            "afternoon": "Nagamachi Samurai District (Nomura-ke Samurai Residence) and 21st Century Museum of Contemporary Art.",
            "evening": "Higashi Chaya Geisha District for gold-leaf soft serve and atmospheric wooden teahouses at dusk.",
            "transit_tip": "Kanazawa's top sights are within a compact 2 km radius—walkable or covered by the Kanazawa Loop Bus (IC cards accepted).",
        },
    ],
    "hakone": [
        {
            "cluster_name": "Hakone Loop, Lake Ashi & Ryokan Onsen Retreat",
            "morning": "Odakyu Romancecar from Shinjuku to Hakone-Yumoto; Hakone Tozan Switchback Train to Gora and Open-Air Museum.",
            "afternoon": "Hakone Ropeway over Owakudani volcanic valley (eat a black sulfur egg to add 7 years to your life!) down to Lake Ashi boat cruise & Hakone Shrine.",
            "evening": "Check in by 16:30 at your Hakone ryokan: soak in the outdoor rotenburo onsen and enjoy a multi-course seasonal Kaiseki dinner in your yukata.",
            "transit_tip": "Ship your heavy suitcases from Tokyo directly to Kyoto via Yamato Takkyubin so you can do the Hakone Loop hands-free!",
        },
    ],
    "takayama": [
        {
            "cluster_name": "Hida Alps, Morning Markets & Shirakawa-go Gassho-zukuri",
            "morning": "Miyagawa Morning Market, Takayama Jinya, and Sanmachi Suji historic sake-brewery streets (sake tasting Flights + Hida beef sushi).",
            "afternoon": "50-minute Nohi Bus excursion to UNESCO-listed Shirakawa-go to explore thatched-roof Gassho-zukuri farmhouses and the Shiroyama viewpoint.",
            "evening": "Hida beef Hoba Miso dinner (grilled over a magnolia leaf on a clay brazier) and alpine onsen soak.",
            "transit_tip": "Reserve Nohi Bus tickets between Takayama, Shirakawa-go, and Kanazawa in advance during spring and autumn.",
        },
    ],
    "fukuoka": [
        {
            "cluster_name": "Hakata Ramen, Canal City & Nakasu Yatai Food Stalls",
            "morning": "Kushida Shrine, Tocho-ji Giant Wooden Buddha, and Ohori Park lakeside stroll.",
            "afternoon": "Dazaifu Tenmangu Shrine excursion (plum-blossom shrine & Kengo Kuma's timber Starbucks) + warm Umegae Mochi.",
            "evening": "Open-air **Yatai** food stalls along Nakasu Island and Tenjin for Hakata Tonkotsu ramen, mentaiko, and yakitori.",
            "transit_tip": "Fukuoka Airport to Hakata Station is just 2 stops (5 mins) on the Fukuoka City Subway!",
        },
    ],
    "sapporo": [
        {
            "cluster_name": "Hokkaido Capital & Otaru Canal Excursion",
            "morning": "Nijo Market crab/uni breakfast, Odori Park, and Hokkaido Jingu Shrine inside Maruyama Park.",
            "afternoon": "35-min scenic coastal JR train to **Otaru**: stroll the historic canal warehouses, Sakaimachi glassworks, and LeTAO cheesecake.",
            "evening": "Sapporo Beer Museum or Susukino district for Genghis Khan (grilled lamb), Soup Curry, and Ganso Ramen Yokocho.",
            "transit_tip": "Reserve a right-hand window seat on the JR Rapid Airport/Hakodate Line from Sapporo to Otaru for Sea of Japan cliffside views.",
        },
    ],
}
