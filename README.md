# Lüftungs-Reminder – ESP32-C6 mit SCD30, OLED & Bluetooth LE

Dieses Projekt implementiert ein **lokales Lüftungs-Reminder-System** auf Basis eines  
**ESP32-C6 mit MicroPython**.

Der ESP32 misst **CO₂**, **Temperatur** und **Luftfeuchtigkeit** über einen  
**Sensirion SCD30** (I²C) und zeigt die Werte auf einem **SSD1306 OLED (128×64, I²C)** an.

Ab definierten CO₂-Grenzwerten wird der Nutzer durch **RGB-LEDs** und einen  
**akustischen Alarm (Buzzer)** auf schlechte Luftqualität hingewiesen.  
Zusätzlich werden die Messwerte lokal per **Bluetooth Low Energy (BLE)** an ein Smartphone übertragen  
(z. B. mit der App **nRF Connect oder LightBlue**).

---

## 🚀 Projektziele

- Regelmäßige Überwachung von CO₂, Temperatur und Luftfeuchtigkeit  
- Lokale Anzeige der Messwerte auf einem OLED-Display  
- Verständliche Lüftungsindikatoren (LED-Farben + Text)  
- Akustischer Alarm bei kritischen CO₂-Werten  
- Lokale, kabellose Datenübertragung per Bluetooth 

---

## 👥 Verantwortlichkeiten

### Meine Aufgaben - Jonathan (Firmware)

- Initialisierung und Ansteuerung aller I²C-Geräte  
- Kommunikation mit dem SCD30 inkl. CRC-Prüfung gemäß Datenblatt  
- Auslesen und Umwandlung der Messdaten (IEEE-754 Float)  
- Anzeige der Messwerte und Statusinformationen auf dem OLED  
- Implementierung der Lüftungs-Logik  
- Steuerung von RGB-LED und Buzzer  
- Alarm-Logik mit einmaligem 3-Sekunden-Signal pro Alarmphase  
- Quittierung des Alarms über einen Button  
- Implementierung eines BLE-GATT-Servers zur Datenübertragung

### Weitere mögliche Aufgaben (Team)

- Dokumentation / Präsentation  
- Gehäuse-Design  
- Mobile App (statt nRF Connect)

---

## 🛠️ Hardware

- **ESP32-C6** (MicroPython: `ESP32-C6`)
- **Sensirion SCD30**  
  - CO₂ / Temperatur / Luftfeuchtigkeit  
  - I²C-Adresse: `0x61`
- **SSD1306 OLED Display**  
  - 128×64 Pixel  
  - I²C-Adresse: meist `0x3C`
- **RGB-LED** 
- **Aktiver Buzzer**
- **Taster (Button)** zur Alarm-Quittierung
- USB-Stromversorgung

---

## 🔌 Pinbelegung (Firmware-Stand)

### I²C
- SDA: GPIO **4**
- SCL: GPIO **5**

### RGB-LED
- Rot: GPIO **15**
- Grün: GPIO **23**
- Blau: GPIO **22**

### Buzzer
- GPIO **21**

### Button (Quittierung)
- GPIO **18**  
  - Intern Pull-Up aktiviert  
  - Gedrückt = LOW

---

## 📦 Softwarefunktionen

### Sensor (SCD30)

- Start der kontinuierlichen Messung (`0x0010`)
- Deaktivierung der automatischen Selbstkalibrierung (ASC) (`0x5306`)
- Setzen eines Temperatur-Offsets in 0.01 °C Schritten (`0x5403`)
- Abfrage des Datenbereit-Status (`0x0202`)
- Messwerte als 32-Bit IEEE-754 Float (CO₂, Temperatur, Luftfeuchte)
- CRC8-Prüfung pro 16-Bit-Wort gemäß Sensirion-Datenblatt

---

### Anzeige (OLED)

- CO₂-Wert in ppm  
- Temperatur in °C  
- Luftfeuchtigkeit in %  
- Systemstatus (z. B. „BLE ACTIVE“)

---

### Lüftungslogik

| CO₂-Wert (ppm) | Status        | LED-Farbe | Verhalten |
|----------------|---------------|-----------|-----------|
| < 1000         | Gut           | Grün      | Kein Alarm |
| 1000–1999      | Erhöht        | Gelb      | Hinweis |
| 2000–2499      | Schlecht      | Rot       | Kein Ton |
| ≥ 2500         | Kritisch      | Rot       | 3s Buzzer (einmalig) |

**Wichtig:**  
Der Alarm wird **nur einmal ausgelöst**, solange der CO₂-Wert im kritischen Bereich bleibt  
(Alarm-Latch). Erst wenn der CO₂-Wert wieder unter 2500 ppm fällt, kann ein neuer Alarm ausgelöst werden.

---

### Buzzer & Button

- Aktiver Buzzer, HIGH = Ton  
- Alarmdauer: **3 Sekunden**
- Button quittiert den Alarm dauerhaft  
- Kein erneutes Piepen bei weiterhin hohem CO₂-Wert

---

### Bluetooth Low Energy (BLE)

- Lokaler BLE-GATT-Server auf dem ESP32-C6
- Eigener Service mit einer Notify-Characteristic
- Übertragung der Messwerte als Text:
