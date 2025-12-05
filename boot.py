# boot.py – wird beim Start ausgeführt

import network
import time

WIFI_SSID = "DEIN_WIFI"
WIFI_PASSWORD = "DEIN_PASSWORT"

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if not wlan.isconnected():
        print("Verbinde mit WLAN…")
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)

        timeout = 10
        while not wlan.isconnected() and timeout > 0:
            time.sleep(1)
            timeout -= 1
    
    if wlan.isconnected():
        print("WLAN verbunden:", wlan.ifconfig())
    else:
        print("⚠️ WLAN konnte nicht verbunden werden")

# WLAN beim Boot herstellen (optional)
try:
    connect_wifi()
except:
    print("WLAN-Fehler im boot.py")
