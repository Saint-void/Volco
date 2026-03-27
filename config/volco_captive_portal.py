from flask import Flask, request, render_template_string
import subprocess
import time

app = Flask(__name__)

# The sleek UI that pops up on your phone
HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Volco Setup</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; text-align: center; margin-top: 10vh; background-color: #0a0a0a; color: #ffffff;}
        .container { background: #1a1a1a; padding: 30px; border-radius: 12px; width: 80%; max-width: 350px; margin: auto; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }
        h2 { margin-bottom: 5px; color: #00d2ff; }
        p { color: #aaaaaa; font-size: 14px; margin-bottom: 20px; }
        input { width: 90%; padding: 12px; margin: 10px 0; border-radius: 6px; border: 1px solid #333; background: #222; color: white; outline: none; }
        button { width: 98%; padding: 14px; margin-top: 15px; border-radius: 6px; border: none; background: #00d2ff; color: #000; font-weight: bold; font-size: 16px; cursor: pointer; }
        .footer { font-size: 10px; color: #444; margin-top: 30px; letter-spacing: 1px; }
    </style>
</head>
<body>
    <div class="container">
        <h2>Volco OS</h2>
        <p>Connect to a Wi-Fi network</p>
        <form method="POST" action="/connect">
            <input type="text" name="ssid" placeholder="Network Name (SSID)" required><br>
            <input type="password" name="password" placeholder="Password"><br>
            <button type="submit">Link Device</button>
        </form>
    </div>
    <div class="footer">POWERED BY VOID ENTERPRISES</div>
</body>
</html>
"""

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def portal(path):
    """Catch-all route. iOS/Android will ping random URLs to test internet. We always return the portal."""
    return render_template_string(HTML_PAGE)

@app.route("/connect", methods=["POST"])
def connect():
    ssid = request.form.get("ssid")
    password = request.form.get("password")
    
    print(f"🔄 Received credentials for {ssid}. Attempting connection...")
    
    # Send a response to the phone before the Pi kills its own hotspot
    response = f"<h3>Connecting to {ssid}...</h3><p>Volco will reboot in 5 seconds. You can close this window.</p>"
    
    # We trigger the actual network switch in the background so the HTTP response can finish sending
    subprocess.Popen(["python3", "apply_wifi.py", ssid, password])
    
    return response

if __name__ == "__main__":
    # Run on port 80 so the phone finds it immediately
    app.run(host="0.0.0.0", port=80)