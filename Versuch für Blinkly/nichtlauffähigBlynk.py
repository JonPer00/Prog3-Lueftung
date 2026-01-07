#Dieser code ist nicht lauffähig
#Ledigliche Versuche für Verbindung via WLAN zur Speicherung / Darstellung der Werte 

from machine import Pin, I2C
import time, struct, network
import ssd1306
import BlynkLib

WIFI_SSID = "lua"
WIFI_PASS = ""
BLYNK_AUTH = "rY3teBBEHj-FndrEfXX-uuiZmSM7Jejl"

MEASURE_INTERVAL = 2000

i2c = I2C(
    0,
    scl=Pin(5, Pin.OPEN_DRAIN),
    sda=Pin(4, Pin.OPEN_DRAIN),
    freq=100000
)

oled = ssd1306.SSD1306_I2C(128, 64, i2c, addr=0x3C)

def oled_show(l1="", l2="", l3="", l4=""):
    oled.fill(0)
    oled.text(l1, 0, 0)
    oled.text(l2, 0, 16)
    oled.text(l3, 0, 32)
    oled.text(l4, 0, 48)
    oled.show()

oled_show("CO2 Monitor", "Booting...")
time.sleep(1)

led_r = Pin(15, Pin.OUT)
led_g = Pin(23, Pin.OUT)
led_b = Pin(22, Pin.OUT)

def led_green():
    led_r.off(); led_g.on(); led_b.off()

def led_yellow():
    led_r.on(); led_g.on(); led_b.off()

def led_red():
    led_r.on(); led_g.off(); led_b.off()

buzzer = Pin(21, Pin.OUT)
buzzer.off()

alarm_running = False
alarm_start = 0

def start_alarm():
    global alarm_running, alarm_start
    if not alarm_running:
        buzzer.on()
        alarm_start = time.ticks_ms()
        alarm_running = True

def update_alarm():
    global alarm_running
    if alarm_running and time.ticks_diff(time.ticks_ms(), alarm_start) > 3000:
        buzzer.off()
        alarm_running = False

SCD30_ADDR = 0x61
TEMP_OFFSET_C = 4.0

def crc8(data):
    crc = 0xFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = ((crc << 1) ^ 0x31) if (crc & 0x80) else (crc << 1)
            crc &= 0xFF
    return crc

def scd30_write(cmd, args=None):
    buf = [(cmd >> 8) & 0xFF, cmd & 0xFF]
    if args:
        for a in args:
            msb = (a >> 8) & 0xFF
            lsb = a & 0xFF
            buf += [msb, lsb, crc8([msb, lsb])]
    i2c.writeto(SCD30_ADDR, bytes(buf))

def scd30_read(cmd, words):
    i2c.writeto(SCD30_ADDR, bytes([(cmd >> 8) & 0xFF, cmd & 0xFF]))
    time.sleep_ms(5)
    raw = i2c.readfrom(SCD30_ADDR, words * 3)
    data = bytearray()
    for i in range(0, len(raw), 3):
        data += raw[i:i+2]
    return data

def scd30_ready():
    return scd30_read(0x0202, 1)[1] == 1

oled_show("Init SCD30", "Warming up...")
start = time.ticks_ms()
while time.ticks_diff(time.ticks_ms(), start) < 10000:
    oled_show("Init SCD30", "Warming up...", f"{(time.ticks_ms()-start)//1000}s")
    time.sleep(0.5)

scd30_write(0x0010, [0])
time.sleep(1)
scd30_write(0x4600, [2])
time.sleep_ms(100)
scd30_write(0x5306, [0])
time.sleep_ms(100)
scd30_write(0x5403, [int(TEMP_OFFSET_C * 100)])

oled_show("WiFi", "Connecting...")
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(WIFI_SSID, WIFI_PASS)
while not wlan.isconnected():
    time.sleep(0.2)

oled_show("WiFi", "Connected")

blynk = BlynkLib.Blynk(BLYNK_AUTH)

last_measure = 0

while True:
    blynk.run()
    update_alarm()

    if time.ticks_diff(time.ticks_ms(), last_measure) > MEASURE_INTERVAL:
        last_measure = time.ticks_ms()

        if scd30_ready():
            raw = scd30_read(0x0300, 6)
            co2, temp, rh = struct.unpack(">fff", raw)

            if co2 < 1000:
                led_green()
            elif co2 < 2000:
                led_yellow()
            elif co2 < 2500:
                led_red()
            else:
                led_red()
                start_alarm()

            oled_show(
                f"CO2: {co2:.0f} ppm",
                f"T: {temp:.1f} C",
                f"RH: {rh:.1f} %",
                "Blynk Online"
            )

            blynk.virtual_write(0, int(co2))
            blynk.virtual_write(1, round(temp, 1))
            blynk.virtual_write(2, round(rh, 1))
            blynk.virtual_write(3, 1 if alarm_running else 0)

    time.sleep(0.05)
