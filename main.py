from machine import Pin, I2C
import time, struct
import ssd1306
import bluetooth
from micropython import const


# ================= I2C =================
i2c = I2C(
    0,
    scl=Pin(5, Pin.OPEN_DRAIN),
    sda=Pin(4, Pin.OPEN_DRAIN),
    freq=100000
)


# ================= OLED =================
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


# ================= LEDs =================
led_r = Pin(15, Pin.OUT)
led_g = Pin(23, Pin.OUT)
led_b = Pin(22, Pin.OUT)

def led_off():
    led_r.off(); led_g.off(); led_b.off()

def led_green():
    led_r.off(); led_g.on(); led_b.off()

def led_yellow():
    led_r.on(); led_g.on(); led_b.off()

def led_red():
    led_r.on(); led_g.off(); led_b.off()


# ================= BUZZER =================
buzzer = Pin(21, Pin.OUT)
buzzer.off()

alarm_active = False
alarm_start = 0

def start_beep():
    global alarm_active, alarm_start
    if not alarm_active:
        buzzer.on()
        alarm_start = time.ticks_ms()
        alarm_active = True

def update_beep():
    global alarm_active
    if alarm_active and time.ticks_diff(time.ticks_ms(), alarm_start) > 3000:
        buzzer.off()
        alarm_active = False


# ================= SCD30 =================
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


# ================= BLE (spät initialisiert!) =================
_IRQ_CENTRAL_CONNECT = const(1)
_IRQ_CENTRAL_DISCONNECT = const(2)

def advertising_payload(name, uuid):
    payload = bytearray()
    payload += b'\x02\x01\x06'
    payload += bytes((len(name) + 1, 0x09)) + name.encode()
    payload += bytes((17, 0x07)) + bytes(uuid)
    return payload

def ble_init():
    global ble, conn_handle, data_handle

    ble = bluetooth.BLE()
    ble.active(True)

    SERVICE_UUID = bluetooth.UUID("6E400001-B5A3-F393-E0A9-E50E24DCCA9E")
    DATA_UUID    = bluetooth.UUID("6E400002-B5A3-F393-E0A9-E50E24DCCA9E")

    ((data_handle,),) = ble.gatts_register_services((
        (SERVICE_UUID, (
            (DATA_UUID, const(0x0002) | const(0x0010)),
        )),
    ))

    def irq(event, data):
        global conn_handle
        if event == 1:
            conn_handle, _, _ = data
        elif event == 2:
            conn_handle = None
            ble.gap_advertise(100000, adv)

    ble.irq(irq)

    adv = b'\x02\x01\x06' + bytes((len("CO2Monitor") + 1, 0x09)) + b"CO2Monitor"
    ble.gatts_write(data_handle, b"0,0.0,0.0")
    ble.gap_advertise(100000, adv)



# ================= STARTUP =================
oled_show("Init SCD30", "Warming up...")
start = time.ticks_ms()
while time.ticks_diff(time.ticks_ms(), start) < 10000:
    oled_show("Init SCD30", "Warming up...", f"{(time.ticks_ms()-start)//1000}s")
    time.sleep(0.5)

scd30_write(0x0010, [0])
time.sleep(1)
scd30_write(0x5306, [0])
time.sleep_ms(100)
scd30_write(0x5403, [int(TEMP_OFFSET_C * 100)])

ble = None
conn_handle = None
ble_init()


# ================= MAIN LOOP =================
last_notify = 0
last_co2 = last_temp = last_rh = 0.0

while True:
    update_beep()

    if scd30_ready():
        raw = scd30_read(0x0300, 6)
        last_co2, last_temp, last_rh = struct.unpack(">fff", raw)

        if last_co2 < 1000:
            led_green()
        elif last_co2 < 2000:
            led_yellow()
        elif last_co2 < 2500:
            led_red()
        else:
            led_red()
            start_beep()

    oled_show(
        f"CO2: {last_co2:4.0f} ppm",
        f"T: {last_temp:.1f} C",
        f"RH: {last_rh:.1f} %",
        "BLE ACTIVE"
    )

    if conn_handle is not None and time.ticks_diff(time.ticks_ms(), last_notify) > 500:
        last_notify = time.ticks_ms()
        payload = f"{last_co2:.0f},{last_temp:.1f},{last_rh:.1f}".encode()
        try:
            ble.gatts_notify(conn_handle, data_handle, payload)
        except:
            pass

    time.sleep(0.05)
