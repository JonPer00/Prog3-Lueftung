# Importiert die Pin- und I2C-Klassen aus dem machine-Modul.
# Pin: steuert GPIOs
# I2C: stellt den I2C-Bus bereit
from machine import Pin, I2C

# time: Zeitfunktionen (sleep, ticks_ms)
# struct: Umwandlung von Bytefolgen in Float-Werte
import time, struct

# OLED-Treiber für SSD1306-Displays
import ssd1306

# Bluetooth-Modul von MicroPython (BLE)
import bluetooth

# const(): erzeugt konstante Werte (spart RAM)
from micropython import const


# ================= I2C =================
# Initialisiert den I2C-Bus 0
# scl: Taktleitung
# sda: Datenleitung
# OPEN_DRAIN: Pflicht für I2C (Pull-Ups erforderlich)
# freq: 100 kHz ist stabil für SCD30 + OLED
i2c = I2C(
    0,
    scl=Pin(5, Pin.OPEN_DRAIN),
    sda=Pin(4, Pin.OPEN_DRAIN),
    freq=100000
)


# ================= OLED =================
# Erstellt ein SSD1306-OLED-Objekt mit 128x64 Pixeln
# addr=0x3C ist die übliche I2C-Adresse
oled = ssd1306.SSD1306_I2C(128, 64, i2c, addr=0x3C)

# Hilfsfunktion zur Anzeige von bis zu 4 Textzeilen
# Das Display wird jedes Mal komplett neu gezeichnet
def oled_show(l1="", l2="", l3="", l4=""):
    oled.fill(0)          # löscht den Bildspeicher
    oled.text(l1, 0, 0)   # Zeile 1 (y=0)
    oled.text(l2, 0, 16)  # Zeile 2
    oled.text(l3, 0, 32)  # Zeile 3
    oled.text(l4, 0, 48)  # Zeile 4
    oled.show()           # überträgt den Puffer aufs Display

# Startmeldung direkt nach dem Boot
oled_show("CO2 Monitor", "Booting...")
time.sleep(1)             # kurze Pause, damit Text sichtbar bleibt


# ================= LEDs =================
# RGB-LED mit gemeinsamer Kathode
# HIGH = LED an
led_r = Pin(15, Pin.OUT)  # rote LED
led_g = Pin(23, Pin.OUT)  # grüne LED
led_b = Pin(22, Pin.OUT)  # blaue LED

# Schaltet alle LEDs aus
def led_off():
    led_r.off()
    led_g.off()
    led_b.off()

# Grün: gute Luftqualität
def led_green():
    led_r.off()
    led_g.on()
    led_b.off()

# Gelb: erhöhte CO2-Konzentration
def led_yellow():
    led_r.on()
    led_g.on()
    led_b.off()

# Rot: schlechte Luftqualität
def led_red():
    led_r.on()
    led_g.off()
    led_b.off()


# ================= BUZZER =================
# Aktiver Buzzer, HIGH = Ton
buzzer = Pin(21, Pin.OUT)
buzzer.off()               # Sicherheit: aus beim Start

# Statusvariable: Alarm aktiv oder nicht
alarm_active = False

# Zeitpunkt, wann der Alarm gestartet wurde
alarm_start = 0

# Startet einen Alarmton für maximal 3 Sekunden
def start_beep():
    global alarm_active, alarm_start
    if not alarm_active:           # verhindert mehrfaches Starten
        buzzer.on()                # Buzzer einschalten
        alarm_start = time.ticks_ms()
        alarm_active = True

# Prüft, ob der Alarm nach 3 Sekunden beendet werden muss
def update_beep():
    global alarm_active
    if alarm_active and time.ticks_diff(time.ticks_ms(), alarm_start) > 3000:
        buzzer.off()
        alarm_active = False


# ================= SCD30 =================
# I2C-Adresse des SCD30 CO2-Sensors
SCD30_ADDR = 0x61

# Temperatur-Offset in °C (wird an den Sensor übertragen)
TEMP_OFFSET_C = 4.0

# CRC8-Berechnung nach Sensirion-Datenblatt
# Der SCD30 verlangt für jedes 16-Bit-Wort eine CRC
def crc8(data):
    crc = 0xFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = ((crc << 1) ^ 0x31) if (crc & 0x80) else (crc << 1)
            crc &= 0xFF
    return crc

# Schreibt ein Kommando (und optionale Argumente) an den SCD30
def scd30_write(cmd, args=None):
    buf = [(cmd >> 8) & 0xFF, cmd & 0xFF]  # Kommando in zwei Bytes
    if args:
        for a in args:
            msb = (a >> 8) & 0xFF
            lsb = a & 0xFF
            buf += [msb, lsb, crc8([msb, lsb])]
    i2c.writeto(SCD30_ADDR, bytes(buf))

# Liest Daten vom SCD30
# words = Anzahl der 16-Bit-Worte
def scd30_read(cmd, words):
    i2c.writeto(SCD30_ADDR, bytes([(cmd >> 8) & 0xFF, cmd & 0xFF]))
    time.sleep_ms(5)                         # Sensor braucht kurze Pause
    raw = i2c.readfrom(SCD30_ADDR, words * 3)
    data = bytearray()
    for i in range(0, len(raw), 3):
        data += raw[i:i+2]                   # CRC-Bytes werden verworfen
    return data

# Prüft, ob neue Messdaten verfügbar sind
def scd30_ready():
    return scd30_read(0x0202, 1)[1] == 1


# ================= BLE =================
# BLE-Ereigniscodes
_IRQ_CENTRAL_CONNECT = const(1)
_IRQ_CENTRAL_DISCONNECT = const(2)

# Initialisiert Bluetooth LE
def ble_init():
    global ble, conn_handle, data_handle

    ble = bluetooth.BLE()        # BLE-Objekt erzeugen
    ble.active(True)             # Bluetooth einschalten

    # Service-UUID (beliebig gewählt, eindeutig)
    SERVICE_UUID = bluetooth.UUID("6E400001-B5A3-F393-E0A9-E50E24DCCA9E")

    # Characteristic-UUID für Messdaten
    DATA_UUID    = bluetooth.UUID("6E400002-B5A3-F393-E0A9-E50E24DCCA9E")

    # Registriert Service + Characteristic beim BLE-Stack
    ((data_handle,),) = ble.gatts_register_services((
        (SERVICE_UUID, (
            (DATA_UUID, const(0x0002) | const(0x0010)),  # READ + NOTIFY
        )),
    ))

    # Interrupt-Handler für BLE-Verbindungen
    def irq(event, data):
        global conn_handle
        if event == _IRQ_CENTRAL_CONNECT:
            conn_handle, _, _ = data
        elif event == _IRQ_CENTRAL_DISCONNECT:
            conn_handle = None
            ble.gap_advertise(100000, adv)

    ble.irq(irq)

    # Advertising-Paket (nur Name + Flags, stabil auf ESP32-C6)
    adv = b'\x02\x01\x06' + bytes((len("CO2Monitor") + 1, 0x09)) + b"CO2Monitor"

    # Initialwert für Characteristic
    ble.gatts_write(data_handle, b"0,0.0,0.0")

    # Startet BLE-Werbung
    ble.gap_advertise(100000, adv)


# ================= STARTUP =================
# Sichtbare Aufwärmphase des SCD30 (10 Sekunden)
oled_show("Init SCD30", "Warming up...")
start = time.ticks_ms()
while time.ticks_diff(time.ticks_ms(), start) < 10000:
    oled_show("Init SCD30", "Warming up...", f"{(time.ticks_ms()-start)//1000}s")
    time.sleep(0.5)

# Startet die kontinuierliche Messung
scd30_write(0x0010, [0])
time.sleep(1)

# Deaktiviert automatische Selbstkalibrierung
scd30_write(0x5306, [0])
time.sleep_ms(100)

# Setzt den Temperatur-Offset im Sensor
scd30_write(0x5403, [int(TEMP_OFFSET_C * 100)])

# BLE-Statusvariablen
ble = None
conn_handle = None

# Initialisiert BLE erst nach dem Warm-up
ble_init()


# ================= MAIN LOOP =================
# Zeitstempel für letzte BLE-Benachrichtigung
last_notify = 0

# Letzte gültige Messwerte
last_co2 = last_temp = last_rh = 0.0

while True:
    update_beep()   # prüft, ob der Buzzer abgeschaltet werden muss

    # Nur wenn neue Sensordaten verfügbar sind
    if scd30_ready():
        raw = scd30_read(0x0300, 6)
        last_co2, last_temp, last_rh = struct.unpack(">fff", raw)

        # LED-Logik abhängig vom CO2-Wert
        if last_co2 < 1000:
            led_green()
        elif last_co2 < 2000:
            led_yellow()
        elif last_co2 < 2500:
            led_red()
        else:
            led_red()
            start_beep()

    # OLED wird immer aktualisiert
    oled_show(
        f"CO2: {last_co2:4.0f} ppm",
        f"T: {last_temp:.1f} C",
        f"RH: {last_rh:.1f} %",
        "BLE ACTIVE"
    )

    # Sendet Messwerte per BLE (Notify), wenn verbunden
    if conn_handle is not None and time.ticks_diff(time.ticks_ms(), last_notify) > 500:
        last_notify = time.ticks_ms()
        payload = f"{last_co2:.0f},{last_temp:.1f},{last_rh:.1f}".encode()
        try:
            ble.gatts_notify(conn_handle, data_handle, payload)
        except:
            pass

    time.sleep(0.05)   # kurze Pause für stabiles Multitasking
