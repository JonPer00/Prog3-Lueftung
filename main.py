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


#Standart Imports:
from machine import Pin, I2C #GPIO Pins und I2C Bus
import time, struct #Time für Zeit, Struct für Bytes in Float 
import ssd1306 #Treiber für Dispaly
import bluetooth #für Verbindung nach via Bluetooth
from micropython import const #Speicheroptimiert in Flash statt RAM

#I2C Init für SCD30 und Display
#SCL = clock line an Pin 5
#SDA = data Line an Pin 4
#Open Drain --> Leitung Dauerhaft HIGH. Wenn SDA schicken will --> Leitung von SCL auf LOW gezogen --> Daten Lesen oder senden möglich 
#Wenn nicht Open Drain, dann Buskollision 
#SCL gibt nur Tackt vor wann geschrieben oder gelesen werden kann. Zieht die Leitung auf LOW
i2c = I2C(
    0,
    scl=Pin(5, Pin.OPEN_DRAIN),
    sda=Pin(4, Pin.OPEN_DRAIN), 
    freq=100000 #Standart bei I2C
)

#OLED 128x64 - Dispaly Init 
#Laut Datenblatt 0x3C 
#Alternative 0x3D wenn Pin auf HIGH liegen würde (nicht bei uns)
oled = ssd1306.SSD1306_I2C(128, 64, i2c, addr=0x3C)

#l definiert die 4 Zeilen auf dem Display
#Jeweilige Definition(Zeile, X-Wert, Y-Wert) --> Erhöhrung Y-wert pro höhere Zeile
#Befehl oled.fill(0) --> Löschen was aktuell drauf ist

def oled_show(l1="", l2="", l3="", l4=""):
    oled.fill(0)          
    oled.text(l1, 0, 0)   
    oled.text(l2, 0, 16)  
    oled.text(l3, 0, 32)  
    oled.text(l4, 0, 48)  
    oled.show()           


#RGB ansteuern ohne PWM 
led_r = Pin(15, Pin.OUT)  #rot
led_g = Pin(23, Pin.OUT)  #grün
led_b = Pin(22, Pin.OUT)  #blau

#Funktionien für einfachere Eingebung der State Machine
#alle leds aus
def led_off():
    led_r.off()
    led_g.off()
    led_b.off()

#Grün --> <1000ppm
def led_green():
    led_r.off()
    led_g.on()
    led_b.off()

#Gelb --> 1000 - 2000ppm 
def led_yellow():
    led_r.on()
    led_g.on()
    led_b.off()

#Rot --> >2000ppm
def led_red():
    led_r.on()
    led_g.off()
    led_b.off()

#Buzzer Init mit HIGH = Ton
buzzer = Pin(21, Pin.OUT)
buzzer.off() 

#Button Init mit Pull UP --> Gedrückt = LOW
button = Pin(18, Pin.IN, Pin.PULL_UP)

#2. State Machine mit Alarm:
alarm_active = False #aktuell kein Alarm
alarm_start = 0 #Startzeit für time.ticks.diff() weil time.sleep CPU Blockierend ist
alarm_done = False #Wenn 1x Alarm fertig, dann kein 2.x

#startet 1x Piep bei STATE = > 2500ppm
def start_beep():
    global alarm_active, alarm_start, alarm_done
    if alarm_active == False and alarm_done == False:
        buzzer.on()
        alarm_start = time.ticks_ms() #aktuell Zeit Merken, dass sie nach 3 Sekunden automatisch wieder ausgeht
        alarm_active = True
        alarm_done = True

#Stoppt alarm
def update_beep():
    global alarm_active
    if alarm_active and time.ticks_diff(time.ticks_ms(), alarm_start) > 3000: #Nach 3 sekunden
        buzzer.off()
        alarm_active = False


#SCD30 Init --- Schlüsselstelle 
#Fix vorgegebene Adresse vom Datenblatt |Kann zu problemen führen, wenn 2 SCD30 auf einem ESP laufen 
SCD30_ADDR = 0x61

#Temperatur Korrektur durch messung mit anderen Temperatur Sensoren nach 60min | also 4 grad ABZIEHEN 
TEMP_OFFSET_C = 4.0
#Offset beschreibt einen Fehler, desshalb kein -
 

#was ist das crc? 
#crc ist eine Prüfsumme welche nach einem Algorithmus immer 8Bit (1Byte) mitsendet | das passiert alle 16Bits 
#Prüft ob die Werte welcher der ESP bekommt auch 1:1 die selben sind welche der SCD30 sendet 
#Die 8 einfach als Sicherheit 2Hoch8 = 256 verschiedene mögliche Prüfsummen --> Sehr sicher
#Klar vorgegeben als crc8:
def crc8(data):
    crc = 0xFF
    for b in data:
        crc = crc ^ b
        for _ in range(8):
            crc = ((crc << 1) ^ 0x31) if (crc & 0x80) else (crc << 1)
            crc = crc & 0xFF
    return crc

#Wiederholung Bit Operator:
#<< Leftshift 
#>> Rightshift 
#^ ODER (XOR)
#& AND

#Hier werden Befehle in die Sprache des Sensores übersetzt
#MSB und LSB schiebt die Bits nur nach vorne oder Hinten, sodass keine Vertauschung der Argumente passiert 
# --> alle Argumente an richtiger stelle (zwingend crc als 3. Byte)

def scd30_write(cmd, args=None): #cmd = comand | args... manche Sensoren brauchen Meereshöhe, dieser nicht
    buf = [(cmd >> 8) & 0xFF, cmd & 0xFF] #I2C Bus schickt immer nur 8 Bit, deshalb aufteilung der zu sendenen 16 Bit in 2 mal 8
    if args:
        for a in args:
            msb = (a >> 8) & 0xFF #1. Byte vom Argument
            lsb = a & 0xFF #2. Byte vom Argument
            buf += [msb, lsb, crc8([msb, lsb])] #3. Byte vom Argument zwingend crc!!!
    i2c.writeto(SCD30_ADDR, bytes(buf)) #an die Adresse mittels SDA und SCL geschickt 


#Dasselbe mit Lesen der Daten - Abholstation
#"words" ins Sensorenwelt = 2Byte
#3 Werte lesen wir aus: CO2, Temp und Luftfeuchtigkeit und "*3" da die crc dazu! 
def scd30_read(cmd, words):
    i2c.writeto(SCD30_ADDR, bytes([(cmd >> 8) & 0xFF, cmd & 0xFF])) #Anfrage: schick temp, LF und CO2
    time.sleep_ms(5) #Denkpause für SCD30 WICHTIG
    raw = i2c.readfrom(SCD30_ADDR, words * 3) #Auslesen Rohdateien 
    data = bytearray() #liste für speicherung

    #Jetzt brauchen wir die crc nichtmehr, deshlab überspringen wir jedes 3. Byte --> crc in den Müll
    for i in range(0, len(raw), 3): 
        data += raw[i:i+2]
    return data
    
"""
    Aktuell funktioniert noch nicht, aber hier wird die crc geprüft:

    for i in range (0, len(raw), 3):
        word = raw[i:i+2]      #Differenzierung zwischen 1. zwei Bytes und der crc
        received_crc = raw[i+2] #crc als 3. bite als recived_crc definieren
        
        #Rechnung: Stimmt die CRC? 
        if crc8(word) == received_crc:
            data += word       #Ja? --> Zur liste hinzufügen 
        else:
            #Nein --> Fehlermeldung? 
            print("Falsche Werte! CRC passt nicht")
            return None #Nichts --> weiter
            
    return data
"""
#Hat der Sensor schon neue Daten? - Polling 
#0x0202 = Get Data Ready Status 
#1 = 1 Word --> 2 Byte + crc Byte
#Hier wollen wir nur den 2. Byte wissen, weil da die Info drinn steht ob neuer wert da ist oder nicht
#[1] = Index in Byte Array zur kontrolle. Nimmt wert 0 oder 1 an
#[] - wert 0 = False --> Nichts
#[] - Wert 1 = True --> Start scd30_read
def scd30_ready():
    return scd30_read(0x0202, 1)[1] == 1


#Bluetooth 
#const als speichersparer. Somit bei Connect nurnoch Wert 1 | Disconnet Wert 2
_IRQ_CENTRAL_CONNECT = const(1) #Gerät Verbunden als Interrupt
_IRQ_CENTRAL_DISCONNECT = const(2) #Gerät nichtmehr verbunden als Interrupt


#Bluetooth Init 
def ble_init():
    global ble, conn_handle, data_handle #Variablen für alle verfügbar 

    #Bluetooth einschalten 
    ble = bluetooth.BLE()
    ble.active(True)   

    #UUID für Bluetooth 
    SERVICE_UUID = bluetooth.UUID("6E400001-B5A3-F393-E0A9-E50E24DCCA9E")

    #UUID für die Messdaten
    DATA_UUID    = bluetooth.UUID("6E400002-B5A3-F393-E0A9-E50E24DCCA9E")

    #Beide Eigenschaften laufen lassen: ServiceUUID und die DataUUID
    #0x0002 = Handy darf lesen (Read)
    #0x0010 = Bekommt Benachrichtigung wenn neue werte da (Notify)
    #Registrierung beim GATT Service 
    ((data_handle,),) = ble.gatts_register_services((
        (SERVICE_UUID, (
            (DATA_UUID, const(0x0002) | const(0x0010)),  
        )),
    ))


    #Wird aufgerufen sobalt sich der Bluetooth Status sich ändert| 1 oder 2 
    #Verbindungsnummer wichtig für Mehrere Verbindungen | Wem soll er welche Infos geben 
    def irq(event, data):
        global conn_handle
        if event == _IRQ_CENTRAL_CONNECT:
            #Verbindungsnummer, Adresstyp und Adresse --> Nur Verbindungsnummer Interessiert uns als conn_handle
            conn_handle, _, _ = data 
        #Wenn keine Verbindung mehr, dann keine Verbingungsnummer + wieder verfügbar für connection 
        elif event == _IRQ_CENTRAL_DISCONNECT:
            conn_handle = None
            ble.gap_advertise(100000, adv) #10000 = Jede 0,1 Sekunde signal für verfügbarkeit senden #Fixwert 

    ble.irq(irq) #ESP soll immer bescheid sagen ob Verbunden oder nicht 

    #Start vom Advertisen.
    #bytes((len("CO"MONITOR") +1, 0x09)) = länge des Namens | 0x09 = Code für Vollständiger lokaler Name
    #b"CO2Monitor" = tatsächlich angezeigter Name am Handy
    adv = b'\x02\x01\x06' + bytes((len("CO2Monitor") + 1, 0x09)) + b"CO2Monitor"

    #Gegen Fehlermeldungen in APP, füllen von GATT mit 0 Werten | 0 CO2, 0,0 Temperatur und 0.0 Feuchtigkeit
    ble.gatts_write(data_handle, b"0,0.0,0.0")

    #Start des Advertise 
    ble.gap_advertise(100000, adv) #10000 = Jede 0,1 Sekunde signal für verfügbarkeit senden #Fixwert 



#Startup, wichtig für richige Werte:
start = time.ticks_ms()
duration = 10000  #Warmup 10 Skeunden 

while time.ticks_diff(time.ticks_ms(), start) < duration:
    remaining = (duration - time.ticks_diff(time.ticks_ms(), start)) // 1000 #Umrechung in Sekunden
    
    #, trennt die Zeilen auf dem Display
    oled_show("Init SCD30", "Warming up...", f"{remaining}s")
    time.sleep(0.5) #Entprellung

#Starte die Messung mit Trigger continuous measurement = 0x0010
#[0] = Umgebungsdruck | Da 0 nimmt er seine eigenen Werte 
scd30_write(0x0010, [0])
time.sleep(1) #Entprellung zum hochfrahren 

#Selbstkalibrierung deaktivieren
#Sensor will 1x pro woche 400ppm --> bei nie / kaum lüftung kalibriert er sich sonst selber Falsch 
#Deactivate Automatic Self-Calibration = 0x5306 | [0] = aus | [1] = ein 
scd30_write(0x5306, [0]) 
time.sleep_ms(100) #entprellung

#0x5403 = Temperatur Offset 
#Rechnet ohne Kommmerzahlen (z.B. bei Offset von 2,5 = 250), deshalb * 100
#Ganzer Befehl notwendig, weil Luftfeuchtigkeit relativ zu Temperatur gemossen wird somit korrektur für Feuchtigkeit dabei
scd30_write(0x5403, [int(TEMP_OFFSET_C * 100)])

#Bluetooth erst nach der Initialisierung vom Sensor Starten!
#+ keine werte von ble oder conn_handle sonst feheler
ble = None
conn_handle = None
ble_init()

######Hautpschleifee######

last_notify = 0 #Letztes Bluetooth Signal (dass keine Überlastung stattfindet)

#Speicherzellen für die aktuellen werte
last_co2 = 0.0 
last_temp = 0.0 
last_rh = 0.0 

while True:
    update_beep() #Alarm Stopp erstmal    

    #Alarm sofort aus wenn button gedrückt wird
    if not button.value():
        buzzer.off()
        alarm_active = False
        alarm_done = True

    #Wenn neue Sensor daten kommen
    #0x0300 = Auslesen der Daten
    #6 Words = 18 byte (jedes 3. Byte crc)
    if scd30_ready():
        raw = scd30_read(0x0300, 6)
        #Diese Rohdateien kommen als 0 und 1
        #struct.unpack(">fff") = Sturkturiertes Entpacken in 3x Float
        #> = Big Endian - dient der auslesung 
        last_co2, last_temp, last_rh = struct.unpack(">fff", raw)

        #immer wieder alarm_done = False | wenn Wert wieder < 2500ppm erneutes scharfstellen stattfindet 
        if last_co2 < 1000:
            led_green()
            alarm_done = False

        elif last_co2 < 2000:
            led_yellow()
            alarm_done = False

        elif last_co2 < 2500:
            led_red()
            alarm_done = False

        else:
            led_red()
            start_beep()

    #aktuelisierung der Werte, wenn neue da sind
    oled_show(
        f"CO2: {last_co2:4.0f} ppm",  #4.0 = Mindestbreite des Textfeldes (es Reserviert 4 Stellen)
        f"T: {last_temp:.1f} C",
        f"RH: {last_rh:.1f} %",
        "BLE ACTIVE"
    )

    #Notify Funktion
    #Ist eine Verbindung da und die Zeit > als 0,5 Sekunden, dann schicke die Neusten werte via Bluetooth an mein handy
    if conn_handle is not None and time.ticks_diff(time.ticks_ms(), last_notify) > 500:  #Damit keine überlastung da ist
        last_notify = time.ticks_ms()
        #Payload = Datenpacket "Schnüren"
        #TextSring durch , getrennt
        payload = f"{last_co2:.0f},{last_temp:.1f},{last_rh:.1f}".encode() #.encode = verwandlung in Bytes für BLE
        try:
            #Dem Handy sagen das neue Daten da sind
            ble.gatts_notify(conn_handle, data_handle, payload) 
        except:
            pass #weitermachen 

        """
        conn_handle = sende an dieses Handy
        data_handle = Diesen Messwert 
        payload = diesen Befehl
        """

    time.sleep(0.05) #Entprellung für CPU und Stromsparend 





