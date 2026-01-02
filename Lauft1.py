# ===== Standard-Imports =====
# Pin: GPIO Steuerung
# I2C: I2C-Bus
from machine import Pin, I2C

# time: Zeitfunktionen (sleep, ticks_ms)
# struct: Umwandlung von Bytes → float
import time, struct

# OLED-Treiber
import ssd1306


# ============================================================
# I2C INITIALISIERUNG
# ============================================================
# Wir benutzen I2C-Controller 0
# OPEN_DRAIN ist bei I2C Pflicht (Pull-Ups!)
# 100 kHz ist stabil für SCD30 + ESP32-C6
i2c = I2C(
    0,
    scl=Pin(5, Pin.OPEN_DRAIN),   # SCL-Leitung
    sda=Pin(4, Pin.OPEN_DRAIN),   # SDA-Leitung
    freq=100000                   # I2C-Geschwindigkeit
)


# ============================================================
# OLED INITIALISIERUNG
# ============================================================
# SSD1306 OLED mit 128x64 Pixeln, Adresse 0x3C
oled = ssd1306.SSD1306_I2C(128, 64, i2c, addr=0x3C)

# Hilfsfunktion, um 4 Textzeilen sauber darzustellen
def oled_show(l1="", l2="", l3="", l4=""):
    oled.fill(0)                  # Display löschen
    oled.text(l1, 0, 0)            # Zeile 1
    oled.text(l2, 0, 16)           # Zeile 2
    oled.text(l3, 0, 32)           # Zeile 3
    oled.text(l4, 0, 48)           # Zeile 4
    oled.show()                    # Anzeige aktualisieren

# Startmeldung
oled_show("CO2 Monitor", "Booting...")


# ============================================================
# RGB-LED (gemeinsame Kathode)
# ============================================================
# Jede Farbe liegt an einem GPIO
# HIGH = LED an, LOW = LED aus
led_r = Pin(15, Pin.OUT)   # Rot
led_g = Pin(23, Pin.OUT)   # Grün
led_b = Pin(22, Pin.OUT)   # Blau

def led_off():
    led_r.off()
    led_g.off()
    led_b.off()

def led_green():
    led_r.off()
    led_g.on()
    led_b.off()

def led_yellow():
    led_r.on()
    led_g.on()
    led_b.off()

def led_red():
    led_r.on()
    led_g.off()
    led_b.off()


# ============================================================
# BUZZER + BUTTON
# ============================================================
# Aktiver Buzzer → HIGH = Ton
buzzer = Pin(21, Pin.OUT)
buzzer.off()               # Sicherheit: aus beim Start

# Button gegen GND, interner Pull-Up
# Gedrückt = LOW
button = Pin(18, Pin.IN, Pin.PULL_UP)

# Alarm-Statusvariablen
alarm_active = False   # Alarm wurde bereits ausgelöst
alarm_muted  = False   # Alarm wurde per Button quittiert


# ============================================================
# SCD30 KONSTANTEN
# ============================================================
SCD30_ADDR = 0x61       # I2C-Adresse des SCD30
TEMP_OFFSET_C = 4.0     # Temperatur-Offset in °C


# ============================================================
# CRC8-BERECHNUNG (vom Datenblatt gefordert)
# ============================================================
# Der SCD30 verlangt für jedes 16-Bit-Wort eine CRC-Prüfsumme
def crc8(data):
    crc = 0xFF           # Startwert laut Datenblatt
    for b in data:       # Für jedes Byte
        crc ^= b         # XOR mit CRC
        for _ in range(8):   # 8 Bit verarbeiten
            if crc & 0x80:   # Prüfen ob höchstes Bit gesetzt
                crc = (crc << 1) ^ 0x31
            else:
                crc = crc << 1
            crc &= 0xFF      # Auf 8 Bit begrenzen
    return crc


# ============================================================
# SCD30 WRITE-FUNKTION
# ============================================================
def scd30_write(cmd, args=None):
    # cmd ist 16-Bit → aufteilen in High- & Low-Byte
    buf = [
        (cmd >> 8) & 0xFF,   # High-Byte
        cmd & 0xFF           # Low-Byte
    ]

    # Falls zusätzliche Argumente gesendet werden sollen
    if args:
        for a in args:
            msb = (a >> 8) & 0xFF   # High-Byte des Wertes
            lsb = a & 0xFF          # Low-Byte des Wertes
            crc = crc8([msb, lsb])  # CRC für dieses Wort
            buf += [msb, lsb, crc]

    # Bytes über I2C senden
    i2c.writeto(SCD30_ADDR, bytes(buf))


# ============================================================
# SCD30 READ-FUNKTION
# ============================================================
def scd30_read(cmd, words):
    # Zuerst das Kommando senden
    i2c.writeto(SCD30_ADDR, bytes([
        (cmd >> 8) & 0xFF,
        cmd & 0xFF
    ]))

    time.sleep_ms(5)  # kurze Wartezeit

    # Jedes Wort = 2 Datenbytes + 1 CRC-Byte
    raw = i2c.readfrom(SCD30_ADDR, words * 3)

    # bytearray ist veränderbar und effizient
    data = bytearray()

    # CRC-Bytes werden ignoriert
    for i in range(0, len(raw), 3):
        data += raw[i:i+2]   # nur die 2 Nutzbytes

    return data


# ============================================================
# PRÜFEN OB NEUE MESSDATEN VORLIEGEN
# ============================================================
def scd30_ready():
    # Kommando 0x0202 liefert Statuswort
    # Byte[1] == 1 → neue Daten verfügbar
    return scd30_read(0x0202, 1)[1] == 1


# ============================================================
# SCD30 WARM-UP (sichtbar, nicht blockierend)
# ============================================================
oled_show("Init SCD30", "Warming up...")
start = time.ticks_ms()

while time.ticks_diff(time.ticks_ms(), start) < 10000:
    oled_show(
        "Init SCD30",
        "Warming up...",
        f"{(time.ticks_ms() - start)//1000} s"
    )
    time.sleep(0.5)


# ============================================================
# SCD30 START & KONFIGURATION
# ============================================================
scd30_write(0x0010, [0])                     # Messung starten
time.sleep(1)
scd30_write(0x5306, [0])                     # ASC deaktivieren
time.sleep_ms(100)
scd30_write(0x5403, [int(TEMP_OFFSET_C * 100)])  # Temp-Offset


# ============================================================
# MAIN LOOP
# ============================================================
blink = False
last_blink = time.ticks_ms()
BLINK_INTERVAL = 500   # 1 Hz Blinken (an/aus je 0.5 s)

while True:

    if scd30_ready():
        # 6 Worte = CO2, Temp, RH (je 32-Bit float)
        raw = scd30_read(0x0300, 6)
        co2, temp, rh = struct.unpack(">fff", raw)

        # Button unterbricht den Buzzer sofort
        if not button.value():
            alarm_muted = True
            buzzer.off()

        # LED-Logik
        if co2 < 1000:
            led_green()
            alarm_active = False
            alarm_muted = False

        elif co2 < 2000:
            led_yellow()
            alarm_active = False
            alarm_muted = False

        elif co2 < 2500:
            led_red()
            alarm_active = False
            alarm_muted = False

        else:
            # Alarmbereich
            if not alarm_active and not alarm_muted:
                buzzer.on()
                start_beep = time.ticks_ms()

                # Maximal 3 Sekunden piepen
                while time.ticks_diff(time.ticks_ms(), start_beep) < 3000:
                    if not button.value():
                        alarm_muted = True
                        break
                    time.sleep(0.05)

                buzzer.off()
                alarm_active = True

            # Schnelles rotes Blinken
            if time.ticks_diff(time.ticks_ms(), last_blink) > BLINK_INTERVAL:
                blink = not blink
                last_blink = time.ticks_ms()

            led_red() if blink else led_off()

        # OLED-Anzeige
        oled_show(
            f"CO2: {co2:4.0f} ppm",
            f"T: {temp:.1f} C",
            f"RH: {rh:.1f} %",
            ""
        )

    time.sleep(0.05)   # schnelle Loop-Rate für sauberes Blinken
