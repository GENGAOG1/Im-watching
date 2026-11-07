
import os
import secrets
import socket
import platform
import requests

from flask import (
    Flask,
    request,
    session,
    redirect,
    render_template_string,
    url_for
)

# ==================================================
# CONFIGURATION
# ==================================================

app = Flask(__name__)

app.secret_key = os.environ.get("SECRET_KEY")

PASSWORD = os.environ.get("DASHBOARD_PASSWORD")

if not app.secret_key or not PASSWORD:
    raise RuntimeError(
        "SECRET_KEY und DASHBOARD_PASSWORD müssen "
        "in Render Environment Variables gesetzt sein."
    )

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=1800
)


# ==================================================
# NETWORK INFORMATION
# ==================================================

def get_public_ip():
    try:
        response = requests.get(
            "https://api.ipify.org",
            timeout=5
        )
        response.raise_for_status()

        return response.text.strip()

    except requests.RequestException:
        return "Nicht verfügbar"


def get_local_ip():
    try:
        connection = socket.socket(
            socket.AF_INET,
            socket.SOCK_DGRAM
        )

        connection.connect(("192.0.2.1", 80))

        ip_address = connection.getsockname()[0]

        connection.close()

        return ip_address

    except OSError:
        return "Nicht verfügbar"


def get_mac_address():
    # Render besitzt eine eigene Netzwerkhardware.
    # Deine persönliche MAC-Adresse ist nicht erreichbar.
    return "Nicht verfügbar (Render-Server)"


def get_wifi_name():
    # Render läuft nicht in deinem persönlichen WLAN.
    return "Nicht verfügbar (Render-Server)"


def get_hostname():
    return socket.gethostname()


# ==================================================
# HTML DESIGN
# ==================================================

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">

<title>RED // ACCESS</title>

<style>
* {
    box-sizing: border-box;
}

body {
    background: #050505;
    color: #ff2020;
    font-family: Consolas, monospace;

    min-height: 100vh;
    display: flex;
    justify-content: center;
    align-items: center;

    margin: 0;
}

.login {
    width: 90%;
    max-width: 420px;

    padding: 35px;

    background: #0b0b0b;

    border: 1px solid #ff2020;

    box-shadow:
        0 0 25px #ff000022,
        inset 0 0 20px #ff000008;
}

h1 {
    text-align: center;
    letter-spacing: 5px;
    text-shadow: 0 0 15px red;
}

.subtitle {
    text-align: center;
    color: #8b2020;
    font-size: 12px;
    letter-spacing: 2px;
}

input {
    width: 100%;
    padding: 14px;

    background: #050505;
    color: #ff3030;

    border: 1px solid #6b1717;

    margin-top: 25px;
    margin-bottom: 15px;

    font-family: inherit;
}

button {
    width: 100%;
    padding: 14px;

    background: #180000;
    color: #ff2020;

    border: 1px solid #ff2020;

    font-family: inherit;
    cursor: pointer;
}

button:hover {
    background: #ff2020;
    color: black;
}

.error {
    color: #ff5555;
    text-align: center;
}
</style>
</head>

<body>

<div class="login">

    <h1>RED // ACCESS</h1>

    <p class="subtitle">
        PERSONAL NETWORK TERMINAL
    </p>

    {% if error %}
        <p class="error">ACCESS DENIED</p>
    {% endif %}

    <form method="POST">

        <input
            type="password"
            name="password"
            placeholder="Enter access password"
            autocomplete="current-password"
            required
        >

        <button type="submit">
            AUTHENTICATE
        </button>

    </form>

</div>

</body>
</html>
"""


DASHBOARD_HTML = """
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

body {
    margin: 0;

    background: #050505;

    color: #ff2929;

    font-family: Consolas, monospace;

    min-height: 100vh;
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

    text-shadow: 0 0 20px red;
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

    grid-template-columns:
        repeat(auto-fit, minmax(250px, 1fr));

    gap: 20px;
}

.card {
    background: #0d0d0d;

    border: 1px solid #5c1111;

    padding: 25px;

    transition: 0.2s;
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

footer {
    text-align: center;

    color: #5b1717;

    padding: 30px;

    font-size: 12px;
}

.warning {
    color: #aa5555;

    font-size: 12px;

    margin-top: 20px;
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

        <span>● SYSTEM ONLINE</span>

        &nbsp; | &nbsp;

        PRIVATE SESSION

    </div>

    <div class="clock" id="clock">
        00:00:00
    </div>

    <div class="grid">

        <div class="card">

            <div class="label">
                SERVER PUBLIC IP
            </div>

            <div class="value">
                {{ data.public_ip }}
            </div>

        </div>

        <div class="card">

            <div class="label">
                SERVER LOCAL IP
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
                OPERATING SYSTEM
            </div>

            <div class="value">
                {{ data.os }}
            </div>

        </div>

        <div class="card">

            <div class="label">
                HOSTNAME
            </div>

            <div class="value">
                {{ data.hostname }}
            </div>

        </div>

    </div>

    <p class="warning">
        Diese Informationen beziehen sich auf den Render-Server,
        nicht auf dein persönliches Gerät.
    </p>

    <br>

    <button onclick="location.reload()">
        [ REFRESH ]
    </button>

    <form action="/logout" method="POST"
          style="display:inline">

        <button type="submit">
            [ LOGOUT ]
        </button>

    </form>

</div>

<footer>
    RED NETWORK // PRIVATE TERMINAL
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


# ==================================================
# ROUTES
# ==================================================

@app.route("/", methods=["GET", "POST"])
def index():

    if not session.get("authenticated"):

        error = False

        if request.method == "POST":

            entered_password = request.form.get(
                "password", ""
            )

            if secrets.compare_digest(
                entered_password,
                PASSWORD
            ):

                session.clear()

                session["authenticated"] = True

                session.permanent = True

                return redirect(url_for("index"))

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

        "hostname": get_hostname()

    }

    return render_template_string(
        DASHBOARD_HTML,
        data=data
    )


@app.route("/logout", methods=["POST"])
def logout():

    session.clear()

    return redirect(url_for("index"))


# ==================================================
# LOCAL DEVELOPMENT
# ==================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        debug=False
    )
