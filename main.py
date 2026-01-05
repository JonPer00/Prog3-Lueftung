# Importiert die Pin- und I2C-Klassen aus dem machine-Modul
# Pin: Zugriff auf GPIOs
# I2C: Kommunikation über den I2C-Bus
from machine import Pin, I2C

# time: Zeitfunktionen (sleep, ticks_ms)
# struct: Wandelt Bytefolgen in Datentypen (z. B. float) um
import time, struct

# Treiber für SSD1306 OLED-Displays
import ssd1306

# Bluetooth Low Energy (BLE) Modul von MicroPython
import bluetooth

# const(): definiert Konstanten (spart RAM, schneller)
from micropython import const


# ============================================================
# I2C INITIALISIERUNG
# ============================================================

# Initialisiert I2C-Bus 0
# scl = Clock-Leitung
# sda = Daten-Leitung
# OPEN_DRAIN ist für I2C zwingend erforderlich
# freq = 100 kHz (stabil für SCD30 + OLED)
i2c = I2C(
    0,
    scl=Pin(5, Pin.OPEN_DRAIN),
    sda=Pin(4, Pin.OPEN_DRAIN),
    freq=100000
)


# ============================================================
# OLED INITIALISIERUNG
# ============================================================

# Erstellt ein OLED-Objekt mit 128x64 Pixeln
# addr=0x3C ist die Standard-I2C-Adresse vieler SSD1306
oled = ssd1306.SSD1306_I2C(128, 64, i2c, addr=0x3C)

# Hilfsfunktion zur Anzeige von bis zu vier Textzeilen
def oled_show(l1="", l2="", l3="", l4=""):
    oled.fill(0)          # Löscht den Display-Puffer
    oled.text(l1, 0, 0)   # Zeile 1
    oled.text(l2, 0, 16)  # Zeile 2
    oled.text(l3, 0, 32)  # Zeile 3
    oled.text(l4, 0, 48)  # Zeile 4
    oled.show()           # Überträgt den Puffer auf das Display

# Startmeldung nach dem Boot
oled_show("CO2 Monitor", "Booting...")
time.sleep(1)             # Kurze Pause für Lesbarkeit


# ============================================================
# RGB-LED INITIALISIERUNG
# ============================================================

# RGB-LED mit gemeinsamer Kathode
# HIGH = LED an
led_r = Pin(15, Pin.OUT)  # Rot
led_g = Pin(23, Pin.OUT)  # Grün
led_b = Pin(22, Pin.OUT)  # Blau

# Schaltet alle LEDs aus
def led_off():
    led_r.off()
    led_g.off()
    led_b.off()

# Grün = gute Luftqualität
def led_green():
    led_r.off()
    led_g.on()
    led_b.off()

# Gelb = erhöhte CO2-Werte
def led_yellow():
    led_r.on()
    led_g.on()
    led_b.off()

# Rot = schlechte Luftqualität
def led_red():
    led_r.on()
    led_g.off()
    led_b.off()


# ============================================================
# BUZZER + BUTTON
# ============================================================

# Aktiver Buzzer (HIGH = Ton)
buzzer = Pin(21, Pin.OUT)
buzzer.off()               # Sicherheit: aus beim Start

# Button gegen GND, interner Pull-Up
# Gedrückt = LOW
button = Pin(18, Pin.IN, Pin.PULL_UP)

# Alarmstatus:
# alarm_active  -> Buzzer läuft gerade
# alarm_latched -> Alarm wurde bereits ausgelöst (Sperre)
alarm_active = False
alarm_latched = False
alarm_start = 0            # Startzeitpunkt des Buzzers

# Startet den Alarmton genau einmal
def start_beep():
    global alarm_active, alarm_start, alarm_latched
    if not alarm_active and not alarm_latched:
        buzzer.on()
        alarm_start = time.ticks_ms()
        alarm_active = True
        alarm_latched = True

# Stoppt den Alarm nach 3 Sekunden
def update_beep():
    global alarm_active
    if alarm_active and time.ticks_diff(time.ticks_ms(), alarm_start) > 3000:
        buzzer.off()
        alarm_active = False


# ============================================================
# SCD30 SENSOR
# ============================================================

# I2C-Adresse des SCD30
SCD30_ADDR = 0x61

# Temperatur-Offset in Grad Celsius
TEMP_OFFSET_C = 4.0

# CRC8-Berechnung laut Sensirion-Datenblatt
#"0x31" sind alles vordefinierte Befehle welche für comands verwendet werden 

def crc8(data):
    crc = 0xFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = ((crc << 1) ^ 0x31) if (crc & 0x80) else (crc << 1)
            crc &= 0xFF
    return crc

# Schreibt ein Kommando an den SCD30
def scd30_write(cmd, args=None):
    buf = [(cmd >> 8) & 0xFF, cmd & 0xFF]
    if args:
        for a in args:
            msb = (a >> 8) & 0xFF
            lsb = a & 0xFF
            buf += [msb, lsb, crc8([msb, lsb])]
    i2c.writeto(SCD30_ADDR, bytes(buf))

# Liest Daten vom SCD30
def scd30_read(cmd, words):
    i2c.writeto(SCD30_ADDR, bytes([(cmd >> 8) & 0xFF, cmd & 0xFF]))
    time.sleep_ms(5)
    raw = i2c.readfrom(SCD30_ADDR, words * 3)
    data = bytearray()
    for i in range(0, len(raw), 3):
        data += raw[i:i+2]
    return data

# Prüft, ob neue Messdaten verfügbar sind
def scd30_ready():
    return scd30_read(0x0202, 1)[1] == 1


# ============================================================
# BLUETOOTH LOW ENERGY (BLE)
# ============================================================

# BLE-Ereigniscodes
_IRQ_CENTRAL_CONNECT = const(1)
_IRQ_CENTRAL_DISCONNECT = const(2)

# Initialisiert BLE (bewusst spät!)
def ble_init():
    global ble, conn_handle, data_handle

    # BLE-Objekt erzeugen
    ble = bluetooth.BLE()
    ble.active(True)   # Bluetooth einschalten

    # Eigene Service-UUID (eindeutig)
    SERVICE_UUID = bluetooth.UUID("6E400001-B5A3-F393-E0A9-E50E24DCCA9E")

    # Characteristic-UUID für Messdaten
    DATA_UUID    = bluetooth.UUID("6E400002-B5A3-F393-E0A9-E50E24DCCA9E")

    # Service + Characteristic registrieren
    ((data_handle,),) = ble.gatts_register_services((
        (SERVICE_UUID, (
            (DATA_UUID, const(0x0002) | const(0x0010)),  # READ + NOTIFY
        )),
    ))

    # BLE-Event-Handler
    def irq(event, data):
        global conn_handle
        if event == _IRQ_CENTRAL_CONNECT:
            conn_handle, _, _ = data
        elif event == _IRQ_CENTRAL_DISCONNECT:
            conn_handle = None
            ble.gap_advertise(100000, adv)

    ble.irq(irq)

    # Advertising-Paket:
    # 0x02 0x01 0x06  -> BLE Flags
    # 0x09           -> Complete Local Name
    adv = b'\x02\x01\x06' + bytes((len("CO2Monitor") + 1, 0x09)) + b"CO2Monitor"

    # Initialwert der Characteristic
    ble.gatts_write(data_handle, b"0,0.0,0.0")

    # Startet BLE-Werbung
    ble.gap_advertise(100000, adv)


# ============================================================
# STARTUP
# ============================================================

# Sichtbare Aufwärmphase des Sensors
oled_show("Init SCD30", "Warming up...")
start = time.ticks_ms()
while time.ticks_diff(time.ticks_ms(), start) < 10000:
    oled_show("Init SCD30", "Warming up...", f"{(time.ticks_ms()-start)//1000}s")
    time.sleep(0.5)

# Startet die Messung
scd30_write(0x0010, [0])
time.sleep(1)

# Deaktiviert automatische Selbstkalibrierung
scd30_write(0x5306, [0])
time.sleep_ms(100)

# Setzt Temperatur-Offset
scd30_write(0x5403, [int(TEMP_OFFSET_C * 100)])

# BLE erst jetzt initialisieren (wichtig!)
ble = None
conn_handle = None
ble_init()


# ============================================================
# HAUPTSCHLEIFE
# ============================================================

last_notify = 0          # Zeitstempel letzte BLE-Übertragung
last_co2 = 0.0           # letzte CO2-Messung
last_temp = 0.0          # letzte Temperatur
last_rh = 0.0            # letzte Luftfeuchte

while True:
    update_beep()        # Prüft, ob Buzzer abgeschaltet werden muss

    # Button quittiert Alarm dauerhaft
    if not button.value():
        buzzer.off()
        alarm_active = False
        alarm_latched = True

    # Neue Sensordaten?
    if scd30_ready():
        raw = scd30_read(0x0300, 6)
        last_co2, last_temp, last_rh = struct.unpack(">fff", raw)

        if last_co2 < 1000:
            led_green()
            alarm_latched = False

        elif last_co2 < 2000:
            led_yellow()
            alarm_latched = False

        elif last_co2 < 2500:
            led_red()
            alarm_latched = False

        else:
            led_red()
            start_beep()

    # OLED immer aktualisieren
    oled_show(
        f"CO2: {last_co2:4.0f} ppm",
        f"T: {last_temp:.1f} C",
        f"RH: {last_rh:.1f} %",
        "BLE ACTIVE"
    )

    # BLE-Daten senden (Notify)
    if conn_handle is not None and time.ticks_diff(time.ticks_ms(), last_notify) > 500:
        last_notify = time.ticks_ms()
        payload = f"{last_co2:.0f},{last_temp:.1f},{last_rh:.1f}".encode()
        try:
            ble.gatts_notify(conn_handle, data_handle, payload)
        except:
            pass

    time.sleep(0.05)     # Kurze Pause für stabile Ausführung
