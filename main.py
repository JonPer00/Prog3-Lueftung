# main.py – Hauptprogramm
import time

# später echte Module importieren
# from sensor import read_sensor
# from display import show_values

def fake_sensor():
    # Simulation von Daten
    return {
        "co2": 750,
        "temperature": 22.5,
        "humidity": 40
    }

def decide_status(co2):
    if co2 < 800:
        return "OK"
    elif co2 < 1200:
        return "Bald Lüften"
    else:
        return "Bitte Lüften!"

while True:
    # --- Sensorwerte holen ---
    data = fake_sensor()  # später: read_sensor()
    co2 = data["co2"]
    temp = data["temperature"]
    hum = data["humidity"]

    status = decide_status(co2)

    # --- Anzeige ---
    print("CO2:", co2, "ppm")
    print("Temp:", temp, "°C")
    print("Humidity:", hum, "%")
    print("Status:", status)
    print("------")

    # später:
    # show_values(co2, temp, hum, status)

    time.sleep(2)
