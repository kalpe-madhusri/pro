
import os
import math
from datetime import datetime

import requests
from flask import Flask, request, jsonify, render_template_string

# Optional MySQL dependency
try:
    import mysql.connector
    from mysql.connector import Error
except ImportError:
    mysql = None
    Error = Exception


# ======================================================
# 1. FLASK CONFIGURATION
# ======================================================

app = Flask(__name__)

app.secret_key = os.getenv(
    "SECRET_KEY",
    "change-this-development-key"
)

WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "")
DATABASE_MODE = os.getenv("DATABASE_MODE", "demo").lower()

DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", ""),
    "database": os.getenv("MYSQL_DATABASE", "wildalert_db")
}


# ======================================================
# 2. DEMO ALERT DATA
# ======================================================

demo_alerts = [
    {
        "id": 1,
        "hazard": "Wildfire",
        "location": "Demo Forest Village A",
        "severity": "High",
        "status": "Unverified demo",
        "latitude": 17.3850,
        "longitude": 78.4867,
        "created_at": "Demo record"
    },
    {
        "id": 2,
        "hazard": "Flood",
        "location": "Demo River Village B",
        "severity": "Medium",
        "status": "Unverified demo",
        "latitude": 17.4500,
        "longitude": 78.4000,
        "created_at": "Demo record"
    },
    {
        "id": 3,
        "hazard": "Heat",
        "location": "Demo Village C",
        "severity": "Low",
        "status": "Unverified demo",
        "latitude": 17.3200,
        "longitude": 78.5500,
        "created_at": "Demo record"
    }
]


# ======================================================
# 3. DATABASE FUNCTIONS
# ======================================================

def get_db():

    if DATABASE_MODE != "mysql":
        return None

    if mysql is None:
        raise RuntimeError(
            "Install mysql-connector-python."
        )

    return mysql.connector.connect(**DB_CONFIG)


def initialize_database():

    if DATABASE_MODE != "mysql":
        return

    connection = get_db()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (

                id INT AUTO_INCREMENT PRIMARY KEY,

                hazard VARCHAR(100) NOT NULL,

                location VARCHAR(255) NOT NULL,

                severity VARCHAR(30) NOT NULL,

                status VARCHAR(100) NOT NULL,

                latitude DOUBLE,

                longitude DOUBLE,

                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

            )
        """)

        connection.commit()

    finally:
        cursor.close()
        connection.close()


def get_alerts():

    if DATABASE_MODE != "mysql":
        return demo_alerts

    connection = get_db()
    cursor = connection.cursor(dictionary=True)

    try:

        cursor.execute("""
            SELECT
                id,
                hazard,
                location,
                severity,
                status,
                latitude,
                longitude,
                created_at

            FROM alerts

            ORDER BY id DESC

            LIMIT 100
        """)

        records = cursor.fetchall()

        for record in records:

            if record.get("created_at"):

                record["created_at"] = (
                    record["created_at"].strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                )

        return records

    finally:
        cursor.close()
        connection.close()


def save_alert(alert):

    if DATABASE_MODE != "mysql":

        alert["id"] = max(
            [item["id"] for item in demo_alerts] + [0]
        ) + 1

        alert["created_at"] = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        demo_alerts.insert(0, alert)

        return alert

    connection = get_db()
    cursor = connection.cursor()

    try:

        cursor.execute("""
            INSERT INTO alerts (

                hazard,
                location,
                severity,
                status,
                latitude,
                longitude

            )

            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            alert["hazard"],
            alert["location"],
            alert["severity"],
            alert["status"],
            alert["latitude"],
            alert["longitude"]
        ))

        connection.commit()

        alert["id"] = cursor.lastrowid

        return alert

    finally:
        cursor.close()
        connection.close()


# ======================================================
# 4. WEATHER API
# ======================================================

def get_weather(latitude, longitude):

    if not WEATHER_API_KEY:
        return demo_weather(latitude, longitude)

    url = (
        "https://api.openweathermap.org/data/2.5/weather"
    )

    response = requests.get(
        url,
        params={
            "lat": latitude,
            "lon": longitude,
            "appid": WEATHER_API_KEY,
            "units": "metric"
        },
        timeout=10
    )

    response.raise_for_status()

    data = response.json()

    return {

        "temperature": data["main"]["temp"],

        "humidity": data["main"]["humidity"],

        "wind_speed": round(
            data["wind"]["speed"] * 3.6, 2
        ),

        "rainfall": data.get(
            "rain", {}
        ).get("1h", 0),

        "condition": data["weather"][0][
            "description"
        ].title(),

        "city": data.get(
            "name", "Selected location"
        ),

        "source": "Live OpenWeatherMap API"

    }


def demo_weather(latitude, longitude):

    return {

        "temperature": 32,

        "humidity": 42,

        "wind_speed": 16,

        "rainfall": 0,

        "condition": "Demo weather - not live",

        "city": "Selected coordinates",

        "source": "Demo data - not live"

    }


# ======================================================
# 5. DISTANCE CALCULATION
# ======================================================

def distance_km(lat1, lon1, lat2, lon2):

    earth_radius = 6371

    dlat = math.radians(lat2 - lat1)

    dlon = math.radians(lon2 - lon1)

    value = (
        math.sin(dlat / 2) ** 2
        +
        math.cos(math.radians(lat1))
        *
        math.cos(math.radians(lat2))
        *
        math.sin(dlon / 2) ** 2
    )

    return earth_radius * 2 * math.atan2(
        math.sqrt(value),
        math.sqrt(max(0, 1 - value))
    )


# ======================================================
# 6. ILLUSTRATIVE DISASTER RISK CALCULATION
# ======================================================

def calculate_risk(weather, nearby_wildfires=0):

    score = 0
    factors = []

    temperature = weather["temperature"]

    humidity = weather["humidity"]

    wind_speed = weather["wind_speed"]

    rainfall = weather["rainfall"]

    if temperature >= 40:

        score += 25

        factors.append("Very high temperature")

    elif temperature >= 35:

        score += 18

        factors.append("High temperature")

    elif temperature >= 30:

        score += 10

        factors.append("Warm conditions")

    if humidity <= 20:

        score += 25

        factors.append("Very low humidity")

    elif humidity <= 35:

        score += 15

        factors.append("Low humidity")

    if wind_speed >= 40:

        score += 25

        factors.append("Strong wind")

    elif wind_speed >= 25:

        score += 15

        factors.append("Elevated wind speed")

    if rainfall == 0:

        score += 10

        factors.append("No rainfall recorded in the last hour")

    elif rainfall >= 5:

        score -= 10

        factors.append("Recent rainfall reported")

    if nearby_wildfires > 0:

        score += min(15, nearby_wildfires * 5)

        factors.append(
            "Nearby verified wildfire records exist"
        )

    score = max(0, min(100, score))

    if score >= 70:

        level = "High"

        advice = [
            "Check official disaster warnings immediately.",
            "Avoid outdoor burning.",
            "Follow evacuation instructions from local authorities."
        ]

    elif score >= 40:

        level = "Moderate"

        advice = [
            "Monitor official weather updates.",
            "Avoid unnecessary outdoor burning.",
            "Keep emergency contacts accessible."
        ]

    else:

        level = "Low"

        advice = [
            "Continue monitoring official alerts.",
            "Follow local safety guidelines.",
            "A low score does not rule out danger."
        ]

    if not factors:

        factors.append(
            "No elevated indicators in the demonstration rules"
        )

    return {

        "score": score,

        "level": level,

        "factors": factors,

        "recommendations": advice,

        "disclaimer": (
            "Illustrative screening score only. "
            "Not a validated disaster forecast."
        )

    }


# ======================================================
# 7. HTML, CSS, BOOTSTRAP, LEAFLET AND CHART.JS
# ======================================================

PAGE = r"""

<!DOCTYPE html>
<html lang="en">

<head>

<meta charset="UTF-8">

<meta name="viewport"
content="width=device-width, initial-scale=1">

<title>WildAlert | Disaster Early Warning System</title>

<!-- BOOTSTRAP -->

<link
href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css"
rel="stylesheet">

<!-- LEAFLET MAP CSS -->

<link
rel="stylesheet"
href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">

<!-- CHART.JS -->

<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

<!-- LEAFLET MAP JS -->

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>


<style>

:root {

    --bg: #0b1220;

    --panel: #131f32;

    --muted: #9caec5;

    --accent: #ff7849;

    --border: #27364c;

}

body {

    background: var(--bg);

    color: #f4f7fb;

    font-family: Arial, sans-serif;

}

.navbar {

    background: #101a2b;

    border-bottom: 1px solid var(--border);

}

.brand {

    font-weight: 800;

    color: var(--accent);

    letter-spacing: 1px;

}

.hero {

    padding: 45px 0 30px;

}

.hero h1 {

    font-weight: 800;

    font-size: clamp(2rem, 4vw, 3.3rem);

}

.accent {

    color: var(--accent);

}

.muted {

    color: var(--muted);

}

.panel {

    background: var(--panel);

    border: 1px solid var(--border);

    border-radius: 16px;

    padding: 22px;

    height: 100%;

}

.metric {

    font-size: 2rem;

    font-weight: 800;

}

.metric-label {

    color: var(--muted);

    font-size: 0.9rem;

}

.btn-alert {

    background: var(--accent);

    color: #171717;

    border: 0;

    font-weight: 700;

}

.btn-alert:hover {

    background: #ff936e;

    color: #171717;

}

.form-control,
.form-select {

    background: #0b1526;

    border-color: #35445b;

    color: white;

}

.form-control:focus,
.form-select:focus {

    background: #0b1526;

    color: white;

    border-color: var(--accent);

    box-shadow: none;

}

.form-control::placeholder {

    color: #8fa0b6;

}

.risk-circle {

    width: 120px;

    height: 120px;

    border: 7px solid var(--accent);

    border-radius: 50%;

    display: flex;

    flex-direction: column;

    align-items: center;

    justify-content: center;

    margin: 15px auto;

}

.risk-number {

    font-size: 2rem;

    font-weight: 800;

}

.section-title {

    font-weight: 750;

    margin-bottom: 20px;

}

.alert-item {

    padding: 14px 0;

    border-bottom: 1px solid var(--border);

}

.alert-item:last-child {

    border-bottom: 0;

}

canvas {

    max-height: 290px;

}

.small-note {

    font-size: 0.82rem;

    color: var(--muted);

}

footer {

    border-top: 1px solid var(--border);

    color: var(--muted);

    padding: 25px 0;

    margin-top: 40px;

}

/* DISASTER MAP */

#disasterMap {

    width: 100%;

    height: 450px;

    border-radius: 12px;

    border: 1px solid var(--border);

    z-index: 1;

}

.map-legend {

    display: flex;

    flex-wrap: wrap;

    gap: 18px;

    margin-top: 15px;

    font-size: 13px;

    color: var(--muted);

}

.legend-dot {

    display: inline-block;

    width: 12px;

    height: 12px;

    border-radius: 50%;

    margin-right: 5px;

}

.legend-red {

    background: #ff3030;

}

.legend-orange {

    background: #ff9f1c;

}

.legend-green {

    background: #25c77a;

}

.leaflet-popup-content-wrapper,
.leaflet-popup-tip {

    color: #222;

}

</style>

</head>


<body>


<!-- NAVIGATION -->

<nav class="navbar navbar-expand-lg navbar-dark">

    <div class="container">

        <a class="navbar-brand brand" href="/">

            🔥 WILDALERT

        </a>

        <span class="navbar-text small">

            Disaster Monitoring Dashboard

        </span>

    </div>

</nav>


<main class="container">


<!-- HERO SECTION -->

<section class="hero">

    <div class="row align-items-center g-4">

        <div class="col-lg-8">

            <p class="accent fw-bold text-uppercase">

                AI-inspired Environmental Risk Screening

            </p>

            <h1>

                Know the risk.

                <br>

                <span class="accent">

                    Act earlier.

                </span>

            </h1>

            <p class="muted mt-3">

                Monitor weather conditions, review disaster
                risk indicators, and visualize recorded
                incidents on an interactive map.

            </p>

            <div class="small-note">

                Educational prototype. Not an official
                emergency warning service.

            </div>

        </div>

        <div class="col-lg-4">

            <div class="panel text-center">

                <div class="metric">

                    LIVE / DEMO

                </div>

                <div class="metric-label">

                    Weather data mode

                </div>

                <p id="modeText" class="muted small mt-2">

                    Checking configuration...

                </p>

            </div>

        </div>

    </div>

</section>


<!-- DASHBOARD METRICS -->

<section class="row g-3 mb-4">

    <div class="col-md-4">

        <div class="panel">

            <div class="metric" id="alertCount">—</div>

            <div class="metric-label">

                Stored alert records

            </div>

        </div>

    </div>

    <div class="col-md-4">

        <div class="panel">

            <div class="metric" id="highCount">—</div>

            <div class="metric-label">

                High-severity records

            </div>

        </div>

    </div>

    <div class="col-md-4">

        <div class="panel">

            <div class="metric" id="databaseMode">—</div>

            <div class="metric-label">

                Database mode

            </div>

        </div>

    </div>

</section>


<!-- WEATHER AND RISK -->

<section class="row g-4 mb-4">

    <div class="col-lg-5">

        <div class="panel">

            <h2 class="section-title h4">

                📍 Check a Location

            </h2>

            <p class="muted small">

                Search by city or use your current location.

            </p>

            <label class="form-label">

                City or place

            </label>

            <div class="input-group mb-3">

                <input
                    id="cityInput"
                    class="form-control"
                    placeholder="Example: Hyderabad">

                <button
                    class="btn btn-alert"
                    onclick="searchCity()">

                    Search

                </button>

            </div>

            <button
                class="btn btn-outline-light w-100 mb-3"
                onclick="useMyLocation()">

                Use My Current Location

            </button>

            <div id="message" class="small muted" role="status">

                Choose a location.

            </div>

            <hr style="border-color:var(--border)">

            <div class="row g-3">

                <div class="col-6">

                    <div class="metric" id="temperature">—</div>

                    <div class="metric-label">

                        Temperature °C

                    </div>

                </div>

                <div class="col-6">

                    <div class="metric" id="humidity">—</div>

                    <div class="metric-label">

                        Humidity %

                    </div>

                </div>

                <div class="col-6">

                    <div class="metric" id="wind">—</div>

                    <div class="metric-label">

                        Wind km/h

                    </div>

                </div>

                <div class="col-6">

                    <div class="metric" id="rain">—</div>

                    <div class="metric-label">

                        Rain mm/hour

                    </div>

                </div>

            </div>

            <p id="condition" class="muted mt-3">

                Weather not checked.

            </p>

            <p id="weatherSource" class="small-note">

            </p>

        </div>

    </div>


    <div class="col-lg-7">

        <div class="panel text-center">

            <h2 class="section-title h4 text-start">

                Disaster Risk Screening

            </h2>

            <div class="risk-circle">

                <span class="risk-number" id="riskScore">

                    —

                </span>

                <span class="small">

                    out of 100

                </span>

            </div>

            <h3 id="riskLevel">

                Not assessed

            </h3>

            <p id="riskDisclaimer" class="small-note">

                Check a location to calculate the score.

            </p>

            <div class="text-start mt-4">

                <h3 class="h6">

                    Factors Considered

                </h3>

                <ul id="factorList" class="muted">

                    <li>Waiting for location check</li>

                </ul>

                <h3 class="h6 mt-3">

                    Suggested Precautions

                </h3>

                <ul id="adviceList" class="muted">

                    <li>Follow official safety guidance.</li>

                </ul>

            </div>

        </div>

    </div>

</section>


<!-- INTERACTIVE DISASTER MAP -->

<section class="panel mb-4">

    <div class="d-flex justify-content-between
                align-items-center flex-wrap gap-2">

        <div>

            <h2 class="section-title h4">

                🗺️ Disaster Danger Zone Map

            </h2>

            <p class="muted small">

                Interactive map showing recorded incident locations
                and illustrative danger zones.

            </p>

        </div>

        <button
            class="btn btn-alert"
            onclick="loadAlerts()">

            Refresh Map

        </button>

    </div>

    <div id="disasterMap"></div>

    <div class="map-legend">

        <span>

            <span class="legend-dot legend-red"></span>

            Verified high-severity alert

        </span>

        <span>

            <span class="legend-dot legend-orange"></span>

            Unverified alert

        </span>

        <span>

            <span class="legend-dot legend-green"></span>

            Other verified alert

        </span>

        <span>

            Red shaded circle: illustrative danger zone

        </span>

    </div>

    <p class="small-note mt-3">

        The 25 km circle is an illustrative screening radius,
        not an official danger or evacuation boundary.
        Only records with coordinates appear on the map.

    </p>

</section>


<!-- CHARTS -->

<section class="row g-4 mb-4">

    <div class="col-lg-6">

        <div class="panel">

            <h2 class="section-title h4">

                Alert Severity Overview

            </h2>

            <canvas id="severityChart"></canvas>

        </div>

    </div>

    <div class="col-lg-6">

        <div class="panel">

            <h2 class="section-title h4">

                Weather Indicators

            </h2>

            <canvas id="weatherChart"></canvas>

        </div>

    </div>

</section>


<!-- ALERT RECORDS AND FORM -->

<section class="row g-4 mb-4">

    <div class="col-lg-7">

        <div class="panel">

            <h2 class="section-title h4">

                Recorded Alerts

            </h2>

            <div id="alertList" class="muted">

                Loading records...

            </div>

            <p class="small-note mt-3">

                Demo records are not verified active incidents.

            </p>

        </div>

    </div>


    <div class="col-lg-5">

        <div class="panel">

            <h2 class="section-title h4">

                Add an Alert Record

            </h2>

            <p class="muted small">

                Record an incident for review.
                Submission does not notify emergency services.

            </p>

            <form id="alertForm">

                <label class="form-label">

                    Hazard Type

                </label>

                <select id="hazard"
                        class="form-select mb-3"
                        required>

                    <option>Wildfire</option>

                    <option>Flood</option>

                    <option>Heat</option>

                    <option>Storm</option>

                    <option>Landslide</option>

                    <option>Other</option>

                </select>


                <label class="form-label">

                    Village / Location

                </label>

                <input
                    id="alertLocation"
                    class="form-control mb-3"
                    placeholder="Enter village or locality"
                    required>


                <label class="form-label">

                    Severity

                </label>

                <select
                    id="severity"
                    class="form-select mb-3"
                    required>

                    <option>Low</option>

                    <option>Medium</option>

                    <option>High</option>

                </select>


                <label class="form-label">

                    Verification Status

                </label>

                <select
                    id="status"
                    class="form-select mb-3">

                    <option>
                        Unverified - submitted by user
                    </option>

                </select>


                <div class="row">

                    <div class="col-6">

                        <label class="form-label">

                            Latitude

                        </label>

                        <input
                            id="latitude"
                            type="number"
                            step="any"
                            class="form-control mb-3"
                            placeholder="Optional">

                    </div>

                    <div class="col-6">

                        <label class="form-label">

                            Longitude

                        </label>

                        <input
                            id="longitude"
                            type="number"
                            step="any"
                            class="form-control mb-3"
                            placeholder="Optional">

                    </div>

                </div>


                <button
                    class="btn btn-alert w-100"
                    type="submit">

                    Save Alert Record

                </button>

                <div
                    id="formMessage"
                    class="small mt-3"
                    role="status">

                </div>

            </form>

        </div>

    </div>

</section>


<!-- HOW IT WORKS -->

<section class="panel mb-4">

    <h2 class="section-title h4">

        How WildAlert Works

    </h2>

    <div class="row g-3">

        <div class="col-md-4">

            <h3 class="h6 accent">

                01 — Collect

            </h3>

            <p class="muted small">

                Retrieve weather data for a selected location.

            </p>

        </div>

        <div class="col-md-4">

            <h3 class="h6 accent">

                02 — Assess

            </h3>

            <p class="muted small">

                Apply demonstration rules to environmental indicators.

            </p>

        </div>

        <div class="col-md-4">

            <h3 class="h6 accent">

                03 — Inform

            </h3>

            <p class="muted small">

                Display precautions and recorded disaster incidents.

            </p>

        </div>

    </div>

    <p class="small-note">

        Weather conditions alone cannot establish whether
        a disaster is currently occurring. Verified incident
        feeds and official warnings are required.

    </p>

</section>


</main>


<!-- FOOTER -->

<footer>

    <div class="container">

        <div class="fw-bold">

            WILDALERT

        </div>

        <div class="small">

            AI-Powered Wildfire and Disaster Early Warning System

        </div>

        <div class="small mt-2">

            Educational prototype. Not a replacement for
            official emergency services.

        </div>

    </div>

</footer>



<!-- ==================================================
     JAVASCRIPT
================================================== -->

<script>


// ==================================================
// 8. GLOBAL VARIABLES
// ==================================================

let severityChart = null;

let weatherChart = null;

let currentCoordinates = null;

let disasterMap = null;

let alertMarkers = null;


// ==================================================
// 9. API HELPER
// ==================================================

async function api(url, options = {}) {

    const response = await fetch(url, options);

    const data = await response.json();

    if (!response.ok) {

        throw new Error(
            data.error || "Request failed"
        );

    }

    return data;

}


// ==================================================
// 10. INITIALIZE DISASTER MAP
// ==================================================

function initializeDisasterMap() {

    disasterMap = L.map("disasterMap").setView(
        [17.3850, 78.4867],
        9
    );

    L.tileLayer(
        "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        {
            attribution:
                '&copy; OpenStreetMap contributors',

            maxZoom: 19
        }
    ).addTo(disasterMap);

    alertMarkers = L.layerGroup().addTo(disasterMap);

}


// ==================================================
// 11. DISPLAY ALERTS ON MAP
// ==================================================

function renderAlertMap(alerts) {

    if (!disasterMap || !alertMarkers) {
        return;
    }

    alertMarkers.clearLayers();

    let mapLocations = [];

    alerts.forEach(alert => {

        const latitude = Number(alert.latitude);

        const longitude = Number(alert.longitude);

        if (
            alert.latitude === null ||
            alert.longitude === null ||
            alert.latitude === "" ||
            alert.longitude === "" ||
            !Number.isFinite(latitude) ||
            !Number.isFinite(longitude) ||
            latitude < -90 ||
            latitude > 90 ||
            longitude < -180 ||
            longitude > 180
        ) {

            return;

        }


        const isVerified =
            alert.status === "Verified by official source";

        const isHigh =
            alert.severity === "High";

        const isWildfire =
            alert.hazard.toLowerCase() === "wildfire";


        // Marker colours

        let markerColor = "#ff9f1c";

        if (isVerified && isHigh) {

            markerColor = "#ff3030";

        } else if (isVerified) {

            markerColor = "#25c77a";

        }


        // Create marker

        const marker = L.circleMarker(
            [latitude, longitude],
            {
                radius: 9,

                color: markerColor,

                fillColor: markerColor,

                fillOpacity: 0.9,

                weight: 2
            }
        );


        // Safe popup creation

        const popup = document.createElement("div");

        const heading = document.createElement("strong");

        heading.textContent = alert.hazard + " Alert";

        const location = document.createElement("p");

        location.textContent =
            "Village / Location: " + alert.location;

        const severity = document.createElement("p");

        severity.textContent =
            "Severity: " + alert.severity;

        const status = document.createElement("p");

        status.textContent =
            "Status: " + alert.status;

        popup.append(
            heading,
            location,
            severity,
            status
        );

        marker.bindPopup(popup);

        marker.addTo(alertMarkers);


        mapLocations.push([latitude, longitude]);


        // Verified high-severity wildfire zone

        if (isVerified && isHigh && isWildfire) {

            const dangerCircle = L.circle(
                [latitude, longitude],
                {
                    radius: 25000,

                    color: "#ff3030",

                    weight: 2,

                    opacity: 0.9,

                    fillColor: "#ff3030",

                    fillOpacity: 0.15
                }
            );

            dangerCircle.bindPopup(
                "Illustrative 25 km wildfire screening zone. " +
                "Not an official evacuation boundary."
            );

            dangerCircle.addTo(alertMarkers);

        }

    });


    // Fit map to recorded incident locations

    if (mapLocations.length > 0) {

        const bounds = L.latLngBounds(mapLocations);

        disasterMap.fitBounds(
            bounds,
            {
                padding: [40, 40],
                maxZoom: 12
            }
        );

    }

}


// ==================================================
// 12. SEARCH CITY
// ==================================================

async function searchCity() {

    const city = document
        .getElementById("cityInput")
        .value
        .trim();

    if (!city) {

        showMessage("Enter a city or village name.");

        return;

    }

    showMessage("Searching location...");

    try {

        const result = await api(
            "/api/geocode?q=" + encodeURIComponent(city)
        );

        await checkLocation(
            result.latitude,
            result.longitude
        );

    } catch (error) {

        showMessage(error.message);

    }

}


// ==================================================
// 13. CURRENT LOCATION
// ==================================================

function useMyLocation() {

    if (!navigator.geolocation) {

        showMessage(
            "Geolocation is not supported by your browser."
        );

        return;

    }

    showMessage(
        "Requesting current location permission..."
    );

    navigator.geolocation.getCurrentPosition(

        position => {

            checkLocation(
                position.coords.latitude,
                position.coords.longitude
            );

        },

        error => {

            showMessage(
                "Location unavailable or permission denied."
            );

        },

        {
            enableHighAccuracy: true,
            timeout: 12000
        }

    );

}


// ==================================================
// 14. CHECK LOCATION AND WEATHER
// ==================================================

async function checkLocation(latitude, longitude) {

    showMessage(
        "Retrieving weather and calculating risk..."
    );

    try {

        const result = await api(
            "/api/current-risk",
            {
                method: "POST",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify({

                    latitude: latitude,

                    longitude: longitude

                })
            }
        );

        currentCoordinates = {

            latitude: latitude,

            longitude: longitude

        };

        displayResult(result);

        showMessage("Location check completed.");

    } catch (error) {

        showMessage(
            "Could not complete check: " + error.message
        );

    }

}


// ==================================================
// 15. DISPLAY WEATHER AND RISK
// ==================================================

function displayResult(data) {

    const weather = data.weather;

    const risk = data.risk;


    document.getElementById("temperature").textContent =
        weather.temperature + "°";

    document.getElementById("humidity").textContent =
        weather.humidity + "%";

    document.getElementById("wind").textContent =
        weather.wind_speed;

    document.getElementById("rain").textContent =
        weather.rainfall;


    document.getElementById("condition").textContent =
        weather.condition + " · " + weather.city;

    document.getElementById("weatherSource").textContent =
        "Source: " + weather.source;


    document.getElementById("riskScore").textContent =
        risk.score;

    document.getElementById("riskLevel").textContent =
        risk.level + " screening risk";

    document.getElementById("riskDisclaimer").textContent =
        risk.disclaimer;


    // Risk factors

    const factorList =
        document.getElementById("factorList");

    factorList.replaceChildren();

    risk.factors.forEach(item => {

        const li = document.createElement("li");

        li.textContent = item;

        factorList.appendChild(li);

    });


    // Recommendations

    const adviceList =
        document.getElementById("adviceList");

    adviceList.replaceChildren();

    risk.recommendations.forEach(item => {

        const li = document.createElement("li");

        li.textContent = item;

        adviceList.appendChild(li);

    });


    // Fill alert coordinates

    if (currentCoordinates) {

        document.getElementById("latitude").value =
            currentCoordinates.latitude;

        document.getElementById("longitude").value =
            currentCoordinates.longitude;

        document.getElementById("alertLocation").value =
            weather.city;

    }


    updateWeatherChart(weather);

}


// ==================================================
// 16. WEATHER CHART
// ==================================================

function updateWeatherChart(weather) {

    if (weatherChart) {

        weatherChart.destroy();

    }

    weatherChart = new Chart(

        document.getElementById("weatherChart"),

        {

            type: "bar",

            data: {

                labels: [
                    "Temperature °C",
                    "Humidity %",
                    "Wind km/h",
                    "Rain mm/h"
                ],

                datasets: [{

                    label: "Weather Indicators",

                    data: [

                        weather.temperature,

                        weather.humidity,

                        weather.wind_speed,

                        weather.rainfall

                    ],

                    backgroundColor: [

                        "#ff7849",
                        "#42b7d8",
                        "#f4c95d",
                        "#7c83fd"

                    ]

                }]

            },

            options: {

                responsive: true,

                scales: {

                    y: {
                        beginAtZero: true
                    }

                },

                plugins: {

                    legend: {
                        display: false
                    }

                }

            }

        }

    );

}


// ==================================================
// 17. LOAD ALERT RECORDS AND UPDATE MAP
// ==================================================

async function loadAlerts() {

    try {

        const data = await api("/api/alerts");

        const alerts = data.alerts;


        // Update metrics

        document.getElementById("alertCount").textContent =
            alerts.length;

        document.getElementById("highCount").textContent =
            alerts.filter(
                a => a.severity === "High"
            ).length;

        document.getElementById("databaseMode").textContent =
            data.database_mode.toUpperCase();


        document.getElementById("modeText").textContent =

            data.weather_api_configured

            ? "Live weather API configured"

            : "Demo weather mode - not live";


        // UPDATE DISASTER MAP

        renderAlertMap(alerts);


        // Display alert list

        const list = document.getElementById("alertList");

        list.replaceChildren();


        if (alerts.length === 0) {

            list.textContent =
                "No alert records have been saved.";

        }


        alerts.forEach(alert => {

            const item = document.createElement("div");

            item.className = "alert-item";


            const title = document.createElement("div");

            title.className = "fw-bold";

            title.textContent =
                alert.hazard + " · " + alert.location;


            const detail = document.createElement("div");

            detail.className = "small muted";

            detail.textContent =
                "Severity: " + alert.severity +
                " | Status: " + alert.status +
                " | ID: " + alert.id;


            item.append(title, detail);

            list.appendChild(item);

        });


        // Severity chart

        const counts = {

            High: alerts.filter(
                a => a.severity === "High"
            ).length,

            Medium: alerts.filter(
                a => a.severity === "Medium"
            ).length,

            Low: alerts.filter(
                a => a.severity === "Low"
            ).length

        };


        if (severityChart) {

            severityChart.destroy();

        }


        severityChart = new Chart(

            document.getElementById("severityChart"),

            {

                type: "doughnut",

                data: {

                    labels: [
                        "High",
                        "Medium",
                        "Low"
                    ],

                    datasets: [{

                        data: [
                            counts.High,
                            counts.Medium,
                            counts.Low
                        ],

                        backgroundColor: [
                            "#ff5d67",
                            "#f4c95d",
                            "#35c995"
                        ]

                    }]

                },

                options: {

                    responsive: true,

                    plugins: {

                        legend: {

                            labels: {
                                color: "#f4f7fb"
                            }

                        }

                    }

                }

            }

        );

    } catch (error) {

        document.getElementById("alertList").textContent =
            "Could not load alerts: " + error.message;

    }

}


// ==================================================
// 18. ADD ALERT RECORD
// ==================================================

document.getElementById("alertForm")
.addEventListener("submit", async event => {

    event.preventDefault();


    const payload = {

        hazard: document.getElementById("hazard").value,

        location: document
            .getElementById("alertLocation")
            .value
            .trim(),

        severity: document.getElementById("severity").value,

        latitude: document.getElementById("latitude").value,

        longitude: document.getElementById("longitude").value

    };


    const message =
        document.getElementById("formMessage");

    message.textContent = "Saving alert record...";


    try {

        await api(

            "/api/alerts",

            {

                method: "POST",

                headers: {

                    "Content-Type": "application/json"

                },

                body: JSON.stringify(payload)

            }

        );


        message.textContent =
            "Alert record saved successfully.";

        event.target.reset();

        await loadAlerts();


    } catch (error) {

        message.textContent =
            "Could not save: " + error.message;

    }

});


// ==================================================
// 19. SHOW STATUS MESSAGE
// ==================================================

function showMessage(text) {

    document.getElementById("message").textContent =
        text;

}


// ==================================================
// 20. START APPLICATION
// ==================================================

initializeDisasterMap();

loadAlerts();

</script>

</body>
</html>
"""


# ======================================================
# 21. FLASK ROUTES
# ======================================================

@app.route("/")
def home():

    return render_template_string(PAGE)


# ======================================================
# 22. CITY GEOCODING API
# ======================================================

@app.route("/api/geocode")
def geocode():

    city = request.args.get("q", "").strip()

    if not city:

        return jsonify({
            "error": "Enter a city name."
        }), 400

    if not WEATHER_API_KEY:

        return jsonify({
            "error": (
                "City search requires a Weather API key. "
                "Use current location or configure WEATHER_API_KEY."
            )
        }), 400

    try:

        response = requests.get(

            "https://api.openweathermap.org/geo/1.0/direct",

            params={

                "q": city,

                "limit": 1,

                "appid": WEATHER_API_KEY

            },

            timeout=10

        )

        response.raise_for_status()

        places = response.json()

        if not places:

            return jsonify({
                "error": "City not found."
            }), 404


        return jsonify({

            "latitude": places[0]["lat"],

            "longitude": places[0]["lon"]

        })


    except requests.RequestException:

        return jsonify({
            "error": "Geocoding service is unavailable."
        }), 502


# ======================================================
# 23. CURRENT WEATHER AND RISK API
# ======================================================

@app.route("/api/current-risk", methods=["POST"])
def current_risk():

    data = request.get_json(silent=True) or {}

    try:

        latitude = float(data["latitude"])

        longitude = float(data["longitude"])

    except (KeyError, TypeError, ValueError):

        return jsonify({
            "error": "Valid latitude and longitude are required."
        }), 400


    if not (

        math.isfinite(latitude)

        and math.isfinite(longitude)

        and -90 <= latitude <= 90

        and -180 <= longitude <= 180

    ):

        return jsonify({
            "error": "Coordinates are out of range."
        }), 400


    try:

        # Get weather

        weather = get_weather(
            latitude,
            longitude
        )


        # Check nearby verified wildfire records

        alerts = get_alerts()

        nearby_wildfires = 0


        for alert in alerts:

            if (
                alert.get("latitude") is None
                or alert.get("longitude") is None
            ):

                continue


            try:

                distance = distance_km(

                    latitude,

                    longitude,

                    float(alert["latitude"]),

                    float(alert["longitude"])

                )


                is_wildfire = (

                    alert.get("hazard", "").lower()
                    == "wildfire"

                )


                is_verified = (

                    alert.get("status", "").lower()
                    == "verified by official source"

                )


                if (

                    distance <= 25

                    and is_wildfire

                    and is_verified

                ):

                    nearby_wildfires += 1


            except (TypeError, ValueError):

                continue


        # Calculate illustrative risk

        risk = calculate_risk(
            weather,
            nearby_wildfires
        )


        return jsonify({

            "weather": weather,

            "risk": risk,

            "nearby_verified_wildfire_records":
                nearby_wildfires,

            "notice": (
                "Nearby records are not a complete active-fire feed. "
                "No record does not mean no disaster."
            )

        })


    except requests.RequestException:

        return jsonify({

            "error": (
                "Live weather lookup failed. "
                "Check your API key, connection and API quota."
            )

        }), 502


    except Exception:

        app.logger.exception("Risk check failed")

        return jsonify({

            "error": "Unable to complete location check."

        }), 500


# ======================================================
# 24. GET ALL ALERTS
# ======================================================

@app.route("/api/alerts", methods=["GET"])
def list_alerts():

    try:

        return jsonify({

            "alerts": get_alerts(),

            "database_mode": DATABASE_MODE,

            "weather_api_configured":
                bool(WEATHER_API_KEY)

        })


    except Exception:

        app.logger.exception("Could not load alerts")

        return jsonify({

            "error": "Unable to load alert records."

        }), 500


# ======================================================
# 25. CREATE NEW ALERT
# ======================================================

@app.route("/api/alerts", methods=["POST"])
def create_alert():

    data = request.get_json(silent=True) or {}


    hazard = str(
        data.get("hazard", "")
    ).strip()


    location = str(
        data.get("location", "")
    ).strip()


    severity = str(
        data.get("severity", "")
    ).strip()


    if not hazard or not location:

        return jsonify({

            "error": "Hazard and location are required."

        }), 400


    if severity not in ("Low", "Medium", "High"):

        return jsonify({

            "error": "Invalid severity."

        }), 400


    if len(hazard) > 100 or len(location) > 255:

        return jsonify({

            "error": "One or more fields are too long."

        }), 400


    # Validate coordinates

    latitude = data.get("latitude")

    longitude = data.get("longitude")


    try:

        if latitude in ("", None) and longitude in ("", None):

            latitude = None

            longitude = None


        elif latitude in ("", None) or longitude in ("", None):

            return jsonify({

                "error": "Enter both coordinates or leave both empty."

            }), 400


        else:

            latitude = float(latitude)

            longitude = float(longitude)


            if not (

                math.isfinite(latitude)

                and math.isfinite(longitude)

                and -90 <= latitude <= 90

                and -180 <= longitude <= 180

            ):

                raise ValueError()


    except (TypeError, ValueError):

        return jsonify({

            "error": "Invalid coordinates."

        }), 400


    # All submitted reports remain unverified.
    # A trusted verification process must change this status.

    alert = {

        "hazard": hazard,

        "location": location,

        "severity": severity,

        "status": "Unverified - submitted by user",

        "latitude": latitude,

        "longitude": longitude

    }


    try:

        saved = save_alert(alert)

        return jsonify({

            "message": "Alert record saved.",

            "alert": saved

        }), 201


    except Exception:

        app.logger.exception("Could not save alert")

        return jsonify({

            "error": "Unable to save alert. Check database configuration."

        }), 500


# ======================================================
# 26. RUN FLASK APPLICATION
# ======================================================

if __name__ == "__main__":

    if DATABASE_MODE == "mysql":

        initialize_database()


    app.run(

        host="127.0.0.1",

        port=int(os.getenv("PORT", "5000")),

        debug=os.getenv("FLASK_DEBUG", "0") == "1"

    )
