#Display von Bernhard
#OLED 128x64 Moncron über I2C
#Treiber: SSD1306


#CO2 Sensor Anschlüsse:
#GRD --> Ground
#VCC --> 3,3V (nicht 5V, da es sonst zu schädigungen im Pin geben kann)
#SDA --> GPIO 6
#SCL --> GPIO 7


#Befehle:
#REPL öffnen: python -m mpremote connect COM5 repl
#Verlassen: Ctrl + x
#soft Reset: Ctrl + D
#Einzelne Dateien Kopieren: python -m mpremote connect COM5 cp main.py :
#Mehrere Dateien Kopieren: python -m mpremote connect COM5 cp *.py :
#Nach kopierne immer reset: python -m mpremote connect COM5 reset
#Dannach wieder ins REPL: python -m mpremote connect COM5 repl

#Alle Dateien auf dem ESP anzeigen lassen: python -m mpremote connect COM5 ls
#Dateien löschen: python -m mpremote connect COM5 rm main.py
#Test im REPL: import main
#Inhalt anzeigen: import os | os.listdir()

# main.py – Hauptprogramm


#define BLYNK_TEMPLATE_NAME "CO2 Monitor"
#define BLYNK_AUTH_TOKEN "rY3teBBEHj-FndrEfXX-uuiZmSM7Jejl"

#WIFI_SSID = "80622ae1"
#WIFI_PASS = "lev10islev10is"
#BLYNK_AUTH = "rY3teBBEHj-FndrEfXX-uuiZmSM7Jejl"

#WIFI_SSID = "lua"
#WIFI_PASS = "E9ED6FC7F9AE4BFD9B0A953129"
#BLYNK_AUTH = "rY3teBBEHj-FndrEfXX-uuiZmSM7Jejl"


from machine import I2C, Pin
import time
import struct

# ---------- I2C Setup ----------
I2C_SDA = 6
I2C_SCL = 7
SCD30_ADDR = 0x61

i2c = I2C(0, sda=Pin(I2C_SDA), scl=Pin(I2C_SCL), freq=100000)

# ---------- Helper ----------
def crc8(data):
    crc = 0xFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ 0x31) if (crc & 0x80) else (crc << 1)
            crc &= 0xFF
    return crc

def write_cmd(cmd, args=None):
    buf = [cmd >> 8, cmd & 0xFF]
    if args:
        for a in args:
            msb = (a >> 8) & 0xFF
            lsb = a & 0xFF
            buf += [msb, lsb, crc8([msb, lsb])]
    i2c.writeto(SCD30_ADDR, bytes(buf))

def read_data(cmd, words):
    i2c.writeto(SCD30_ADDR, bytes([cmd >> 8, cmd & 0xFF]))
    time.sleep_ms(5)
    raw = i2c.readfrom(SCD30_ADDR, words * 3)

    data = bytearray()
    for i in range(0, len(raw), 3):
        data += raw[i:i+2]
    return data

# ---------- SCD30 Init ----------
print("SCD30 Initialisierung...")

# Start continuous measurement (ambient pressure = 0)
write_cmd(0x0010, [0])

time.sleep(2)

print("Messung gestartet")
print("CO2 [ppm] | Temp [°C] | RH [%]")
print("--------------------------------")

# ---------- Main Loop ----------
while True:
    try:
        data = read_data(0x0300, 6)
        co2, temp, rh = struct.unpack(">fff", data)

        print(f"{co2:8.1f} | {temp:7.2f} | {rh:6.2f}")
    except Exception as e:
        print("Fehler:", e)

    time.sleep(2)
