# Lüftungs-Reminder – ESP32 mit CO₂-, Temperatur- & Feuchtigkeitssensor + 2.9" Display

Dieses Projekt implementiert ein smartes Lüftungs-Reminder-System auf Basis eines **ESP32**.  
Es misst **CO₂**, **Temperatur** und **Luftfeuchtigkeit** und stellt die Werte auf einem **2.9"-I²C-Display** dar.  
Ab definierten Grenzwerten erinnert das System automatisch daran, den Raum zu lüften.

---

## 🚀 Projektziele

- Regelmäßige CO₂-/Klimaüberwachung  
- Visuelle Darstellung auf einem 2.9" Display  
- Einfach verständliche Lüftungsindikatoren  
- Klare Trennung zwischen Backend (ESP32) und Frontend (Streamlit)

---

## 👥 Verantwortlichkeiten

### Meine Aufgaben (Software / ESP32)
- Sensor-Ansteuerung via **I²C**
- Datenerfassung (CO₂, Temperatur, Feuchte)
- Display-Rendering auf dem **2.9" I²C-Display**
- Logik für Lüftungs-Reminder
- Bereitstellung von Messdaten für Streamlit (optional)

### Andere Teammitglieder
- Streamlit Dashboard / Datenvisualisierung  
- UI/Design  
- Präsentation im Frontend

---

## 🛠️ Hardware

- **ESP32 Dev Board**
- **CO₂-/Temp-/Feuchte-Sensor**  
  *(z. B. SCD41, SCD30 oder vergleichbar)*
- **2.9" I²C Display**
- USB-Stromversorgung

---

## 📦 Softwarefunktionen

- Initialisierung aller I²C-Geräte  
- Periodische Sensormessung  
- Fehlererkennung („Sensor nicht gefunden“)  
- Dynamische Anzeige (CO₂, Temperatur, Feuchtigkeit, Status)  
- Logik zur Lüftungsempfehlung  
- Möglichkeit zur späteren Web-Schnittstelle (Streamlit)

---

## 📊 Lüftungslogik (Beispiel)

| CO₂-Wert (ppm) | Status           | Anzeige                  |
|----------------|------------------|--------------------------|
| < 800          | Gut              | Grün / „Alles OK“        |
| 800–1200       | Mittel           | Gelb / „Bald Lüften“     |
| > 1200         | Schlecht         | Rot / „Bitte Lüften“     |

---

## 🖥️ Anzeige auf dem 2.9"-Display

Typisches Displaylayout:

- CO₂-Wert (ppm)  
- Temperatur (°C)  
- Luftfeuchtigkeit (%)  
- Lüftungsstatus (Text + Symbol)

---

## ⚙️ Benötigte Libraries

Je nach Sensor und Display:

- `Wire.h`  
- `Adafruit_GFX`  
- Display-Treiber (z. B. `Adafruit_ST7789`, Waveshare E-Paper etc.)  
- CO₂-Sensor-Library (z. B. `Sensirion I2C SCD4x`)

---

## ▶️ Setup / Installation in VS Code (PlatformIO)

1. Git-Repository klonen  
2. VS Code mit PlatformIO öffnen  
3. Board auswählen: **ESP32 Dev Module**  
4. Libraries über PlatformIO Library Manager installieren  
5. Gerät via USB verbinden  
6. Flashen  
7. Messwerte & Display prüfen

---

## 🔧 Zukünftige Erweiterungen

- Webinterface (Streamlit)  
- Logging / Speicherung (CSV, MQTT, HTTP)  
- LED/Buzzer als zusätzlicher Alarm  
- Energiesparmodi / Batteriebetrieb


