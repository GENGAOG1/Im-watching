
import os
import socket
import uuid
import platform
import subprocess
import secrets
import requests

from flask import Flask, request, session, redirect, render_template_string

app = Flask(__name__)

# Zufälliger Session-Schlüssel
app.secret_key = secrets.token_hex(32)

# Passwort über Umgebungsvariable setzen
PASSWORD = os.environ.get("DASHBOARD_PASSWORD")

if not PASSWORD:
    PASSWORD = secrets.token_urlsafe(16)
    print("\nDashboard-Passwort:", PASSWORD)

# Nur lokal erreichbar
HOST = "127.0.0.1"
PORT = 5000


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("192.0.2.1", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "Nicht verfügbar"


def get_mac_address():
    try:
        mac = uuid.getnode()
        return ":".join(
            f"{(mac >> shift) & 0xff:02X}"
            for shift in range(40, -1, -8)
        )
    except Exception:
        return "Nicht verfügbar"


def get_wifi_name():
    system = platform.system()

    try:
        if system == "Windows":
            result = subprocess.run(
                ["netsh", "wlan", "show", "interfaces"],
                capture_output=True,
                text=True,
                timeout=5
            )

            for line in result.stdout.splitlines():
                if "SSID" in line and "BSSID" not in line:
                    return line.split(":", 1)[1].strip()

        elif system == "Linux":
            result = subprocess.run(
                ["nmcli", "-t", "-f", "ACTIVE,SSID", "dev", "wifi"],
                capture_output=True,
                text=True,
                timeout=5
            )

            for line in result.stdout.splitlines():
                if line.startswith("yes:"):
                    return line[4:] or "Unbekannt"

        elif system == "Darwin":
            result = subprocess.run(
                ["/usr/sbin/networksetup", "-getairportnetwork", "en0"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if "Current Wi-Fi Network:" in result.stdout:
                return result.stdout.split(":", 1)[1].strip()

    except Exception:
        pass

    return "Nicht verfügbar"


def get_public_ip():
    try:
        response = requests.get(
            "https://api.ipify.org",
            timeout=4
        )
        response.raise_for_status()
        return response.text.strip()
    except Exception:
        return "Nicht verfügbar"


HTML = """
<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<title>RED // NETWORK</title>

<style>
* {
    box-sizing: border-box;
}

body {
    margin: 0;
    background: #070707;
    color: #ff2929;
    font-family: Consolas, monospace;
    min-height: 100vh;
    overflow-x: hidden;
}

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

header {
    text-align: center;
    padding: 35px 15px;
    border-bottom: 1px solid #ff292933;
}

h1 {
    font-size: clamp(30px, 6vw, 55px);
    letter-spacing: 8px;
    text-shadow: 0 0 20px #ff0000;
}

.subtitle {
    color: #8b1717;
    letter-spacing: 4px;
}

.container {
    max-width: 1000px;
    margin: 40px auto;
    padding: 20px;
}

.status {
    border: 1px solid #ff2929;
    padding: 15px;
    margin-bottom: 25px;
    box-shadow: 0 0 15px #ff000022;
}

.grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 20px;
}

.card {
    background: #0d0d0d;
    border: 1px solid #5c1111;
    padding: 25px;
    transition: 0.2s;
    position: relative;
    overflow: hidden;
}

.card:hover {
    border-color: #ff2929;
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
    font-size: 20px;
    color: #ff4545;
    overflow-wrap: anywhere;
    text-shadow: 0 0 10px #ff000044;
}

footer {
    text-align: center;
    color: #5b1717;
    padding: 30px;
    font-size: 12px;
}

button {
    background: #160000;
    color: #ff2929;
    border: 1px solid #ff2929;
    padding: 12px 20px;
    cursor: pointer;
    font-family: inherit;
}

button:hover {
    background: #ff2929;
    color: black;
}

.clock {
    text-align: center;
    margin: 30px;
    font-size: 20px;
    text-shadow: 0 0 12px red;
}

.scan {
    animation: blink 1.5s infinite;
}

@keyframes blink {
    50% { opacity: 0.4; }
}
</style>
</head>

<body>

<header>
    <h1>RED // NETWORK</h1>
    <div class="subtitle">PERSONAL NETWORK TERMINAL</div>
</header>

<div class="container">

    <div class="status">
        <span class="scan">● SYSTEM ONLINE</span>
        &nbsp; | &nbsp; LOCAL ACCESS ONLY
    </div>

    <div class="clock" id="clock">00:00:00</div>

    <div class="grid">

        <div class="card">
            <div class="label">PUBLIC IP ADDRESS</div>
            <div class="value">{{ data.public_ip }}</div>
        </div>

        <div class="card">
            <div class="label">LOCAL IPv4 ADDRESS</div>
            <div class="value">{{ data.local_ip }}</div>
        </div>

        <div class="card">
            <div class="label">MAC ADDRESS</div>
            <div class="value">{{ data.mac }}</div>
        </div>

        <div class="card">
            <div class="label">WIFI NETWORK / SSID</div>
            <div class="value">{{ data.wifi }}</div>
        </div>

        <div class="card">
            <div class="label">OPERATING SYSTEM</div>
            <div class="value">{{ data.os }}</div>
        </div>

        <div class="card">
            <div class="label">DEVICE NAME</div>
            <div class="value">{{ data.hostname }}</div>
        </div>

    </div>

    <br>

    <button onclick="location.reload()">
        [ REFRESH DATA ]
    </button>

    <form action="/logout" method="post" style="display:inline">
        <button type="submit">[ LOGOUT ]</button>
    </form>

</div>

<footer>
    RED NETWORK TERMINAL // PRIVATE SESSION
</footer>

<script>
function updateClock() {
    document.getElementById("clock").textContent =
        new Date().toLocaleTimeString("de-DE");
}

updateClock();
setInterval(updateClock, 1000);
</script>

</body>
</html>
"""


LOGIN_HTML = """
<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">

<title>RED // LOGIN</title>

<style>
body {
    background: #070707;
    color: #ff2929;
    font-family: Consolas, monospace;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
}

.login {
    border: 1px solid red;
    padding: 35px;
    width: 90%;
    max-width: 400px;
    box-shadow: 0 0 25px #ff000022;
}

input {
    background: black;
    border: 1px solid #ff2929;
    padding: 12px;
    color: red;
    width: 100%;
    margin: 15px 0;
}

button {
    background: #180000;
    border: 1px solid red;
    color: red;
    padding: 12px;
    width: 100%;
    cursor: pointer;
}

button:hover {
    background: red;
    color: black;
}
</style>
</head>

<body>

<div class="login">
    <h2>RED // ACCESS</h2>
    <p>AUTHENTICATION REQUIRED</p>

    {% if error %}
        <p style="color:white">ACCESS DENIED</p>
    {% endif %}

    <form method="post">
        <input type="password" name="password"
               placeholder="Enter access password" required>
        <button type="submit">AUTHENTICATE</button>
    </form>
</div>

</body>
</html>
"""


@app.route("/", methods=["GET", "POST"])
def index():
    if not session.get("authenticated"):
        error = False

        if request.method == "POST":
            if secrets.compare_digest(
                request.form.get("password", ""),
                PASSWORD
            ):
                session["authenticated"] = True
                return redirect("/")
            error = True

        return render_template_string(
            LOGIN_HTML,
            error=error
        )

    data = {
        "public_ip": get_public_ip(),
        "local_ip": get_local_ip(),
        "mac": get_mac_address(),
        "wifi": get_wifi_name(),
        "os": platform.system() + " " + platform.release(),
        "hostname": socket.gethostname()
    }

    return render_template_string(HTML, data=data)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect("/")


if __name__ == "__main__":
    print("\nRED NETWORK TERMINAL")
    print("Local URL: http://127.0.0.1:5000")
    print("Nur auf diesem PC erreichbar.\n")

    app.run(
        host=HOST,
        port=PORT,
        debug=False
    )
