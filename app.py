
import os
from datetime import datetime, timezone

from flask import Flask, request, render_template_string
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)

# Render verwendet einen Reverse Proxy.
# Eine Proxy-Ebene wird berücksichtigt.
app.wsgi_app = ProxyFix(
    app.wsgi_app,
    x_for=1,
    x_proto=1
)

# ==================================================
# NETWORK INFORMATION
# ==================================================

def get_public_ip():
    ip = request.remote_addr

    if not ip:
        return "Nicht verfügbar"

    return ip


def get_browser_info():
    return request.headers.get(
        "User-Agent",
        "Unbekannt"
    )


def get_local_ip():
    return "Nicht direkt im Browser verfügbar"


def get_mac_address():
    return "Aus Datenschutzgründen nicht verfügbar"


def get_wifi_name():
    return "Aus Datenschutzgründen nicht verfügbar"


# ==================================================
# HTML
# ==================================================

HTML = """
<!DOCTYPE html>
<html lang="de">

<head>

<meta charset="UTF-8">

<meta name="viewport"
      content="width=device-width, initial-scale=1">

<title>RED // NETWORK</title>

<style>

* {
    box-sizing: border-box;
}

:root {
    --red: #ff2020;
    --red-dark: #7a0808;
    --background: #050505;
    --card: #0d0d0d;
}

body {
    margin: 0;

    background: var(--background);
    color: var(--red);

    font-family: Consolas, monospace;

    min-height: 100vh;
}

/* Hintergrund */

body::before {
    content: "";

    position: fixed;
    inset: 0;

    background:
        linear-gradient(
            rgba(255, 0, 0, 0.035) 1px,
            transparent 1px
        ),
        linear-gradient(
            90deg,
            rgba(255, 0, 0, 0.035) 1px,
            transparent 1px
        );

    background-size: 35px 35px;

    pointer-events: none;
}

/* Header */

header {
    text-align: center;

    padding: 40px 15px;

    border-bottom: 1px solid #ff292933;
}

h1 {
    font-size: clamp(28px, 6vw, 55px);

    letter-spacing: 8px;

    text-shadow: 0 0 20px red;
}

.subtitle {
    color: #8b1717;

    letter-spacing: 4px;

    font-size: 12px;
}

/* Layout */

.container {
    max-width: 1050px;

    margin: 40px auto;

    padding: 20px;
}

/* Status */

.status {
    border: 1px solid var(--red);

    padding: 15px;

    margin-bottom: 25px;

    box-shadow: 0 0 15px #ff000022;
}

.online {
    animation: blink 2s infinite;
}

/* Cards */

.grid {
    display: grid;

    grid-template-columns:
        repeat(auto-fit, minmax(250px, 1fr));

    gap: 20px;
}

.card {
    background: var(--card);

    border: 1px solid #5c1111;

    padding: 25px;

    transition: 0.2s;

    min-width: 0;
}

.card:hover {
    border-color: var(--red);

    box-shadow: 0 0 20px #ff000033;

    transform: translateY(-3px);
}

.label {
    font-size: 12px;

    color: #a52a2a;

    letter-spacing: 2px;

    margin-bottom: 15px;
}

.value {
    font-size: 18px;

    color: #ff4545;

    overflow-wrap: anywhere;

    text-shadow: 0 0 10px #ff000044;
}

/* Clock */

.clock {
    text-align: center;

    margin: 30px;

    font-size: 22px;

    text-shadow: 0 0 12px red;
}

/* Button */

button {
    background: #160000;

    color: var(--red);

    border: 1px solid var(--red);

    padding: 12px 20px;

    cursor: pointer;

    font-family: inherit;
}

button:hover {
    background: var(--red);

    color: black;
}

/* Footer */

footer {
    text-align: center;

    color: #5b1717;

    padding: 30px;

    font-size: 12px;
}

.warning {
    color: #a52a2a;

    font-size: 12px;

    line-height: 1.7;

    margin-top: 25px;
}

/* Animation */

@keyframes blink {
    50% {
        opacity: 0.4;
    }
}

</style>

</head>

<body>

<header>

    <h1>RED // NETWORK</h1>

    <div class="subtitle">
        PERSONAL NETWORK TERMINAL
    </div>

</header>

<div class="container">

    <div class="status">

        <span class="online">● SYSTEM ONLINE</span>

        &nbsp; | &nbsp;

        CONNECTION ESTABLISHED

    </div>

    <div class="clock" id="clock">
        00:00:00
    </div>

    <div class="grid">

        <div class="card">

            <div class="label">
                YOUR PUBLIC IP
            </div>

            <div class="value">
                {{ data.public_ip }}
            </div>

        </div>

        <div class="card">

            <div class="label">
                LOCAL IP ADDRESS
            </div>

            <div class="value">
                {{ data.local_ip }}
            </div>

        </div>

        <div class="card">

            <div class="label">
                MAC ADDRESS
            </div>

            <div class="value">
                {{ data.mac }}
            </div>

        </div>

        <div class="card">

            <div class="label">
                WIFI / SSID
            </div>

            <div class="value">
                {{ data.wifi }}
            </div>

        </div>

        <div class="card">

            <div class="label">
                BROWSER
            </div>

            <div class="value" id="browser">
                Wird erkannt ...
            </div>

        </div>

        <div class="card">

            <div class="label">
                OPERATING SYSTEM
            </div>

            <div class="value" id="os">
                Wird erkannt ...
            </div>

        </div>

    </div>

    <p class="warning">
        Hinweis: MAC-Adresse, WLAN-Name und lokale IP-Adresse
        sind für normale Websites nicht zugänglich.
        Deine öffentliche IP wird durch den Server ermittelt.
    </p>

    <br>

    <button onclick="location.reload()">
        [ REFRESH DATA ]
    </button>

</div>

<footer>
    RED NETWORK // CONNECTION TERMINAL
</footer>

<script>

function updateClock() {

    document.getElementById("clock").textContent =
        new Date().toLocaleTimeString("de-DE");

}

function detectDevice() {

    const ua = navigator.userAgent;

    let browser = "Unbekannter Browser";

    if (ua.includes("Firefox")) {
        browser = "Mozilla Firefox";
    } else if (ua.includes("Edg")) {
        browser = "Microsoft Edge";
    } else if (ua.includes("Chrome")) {
        browser = "Google Chrome";
    } else if (ua.includes("Safari")) {
        browser = "Safari";
    }

    document.getElementById("browser").textContent =
        browser;

    let os = "Unbekannt";

    if (ua.includes("Windows")) {
        os = "Windows";
    } else if (ua.includes("Android")) {
        os = "Android";
    } else if (ua.includes("iPhone")) {
        os = "iOS";
    } else if (ua.includes("Mac")) {
        os = "macOS";
    } else if (ua.includes("Linux")) {
        os = "Linux";
    }

    document.getElementById("os").textContent = os;

}

updateClock();

setInterval(updateClock, 1000);

detectDevice();

</script>

</body>
</html>
"""


# ==================================================
# ROUTES
# ==================================================

@app.route("/")
def index():

    data = {
        "public_ip": get_public_ip(),
        "local_ip": get_local_ip(),
        "mac": get_mac_address(),
        "wifi": get_wifi_name()
    }

    return render_template_string(
        HTML,
        data=data
    )


# ==================================================
# START
# ==================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        debug=False
    )
