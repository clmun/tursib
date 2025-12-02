# 📍 Tursib Bus Departures – Home Assistant Integration

This custom integration adds **Tursib bus departure sensors** to Home Assistant.  
It scrapes live timetables from [tursib.ro](https://tursib.ro) and exposes them as sensors with attributes for upcoming departures, line, destination, and minutes until arrival.

---

## ✨ Features
- Sensors for each configured bus station
- Attributes include:
  - **Line** (bus route number)
  - **Destination**
  - **Scheduled departure time**
  - **Minutes until departure** (or `"Acum"` if < 60s)
  - **Program type** (Weekday, Saturday, Sunday)
  - **Last update timestamp**
- Automatic refresh every minute
- Works natively inside Home Assistant (no AppDaemon required)

---

## 📦 Installation

### Via HACS (recommended)
1. Open HACS in Home Assistant.
2. Go to **Integrations → Custom repositories**.
3. Add your repo URL and select category **Integration**.
4. Search for **Tursib Bus Departures** and install.
5. Restart Home Assistant.

### Manual
1. Copy the `custom_components/tursib/` folder into your Home Assistant `config/custom_components/` directory.
2. Restart Home Assistant.

---

## ⚙️ Configuration

### UI (Config Flow)
1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **Tursib**.
3. Enter your station IDs and names (e.g. `123: Gara`, `456: Centru`).
4. Sensors will be created automatically.

### Example Sensor
```yaml
sensor.tursib_gara
