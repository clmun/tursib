import datetime
import math
import logging
import requests
from bs4 import BeautifulSoup

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

_LOGGER = logging.getLogger(__name__)
DOMAIN = "tursib"


async def async_setup_entry(hass, config_entry, async_add_entities):
    station_id = config_entry.data["station_id"]
    station_name = config_entry.data["station_name"]
    coordinator = TursibCoordinator(hass, {station_id: station_name})
    await coordinator.async_config_entry_first_refresh()

    async_add_entities([TursibSensor(coordinator, station_id, station_name)])



class TursibCoordinator(DataUpdateCoordinator):
    """Coordinator to fetch and parse Tursib data."""

    def __init__(self, hass, stations):
        super().__init__(
            hass,
            _LOGGER,
            name="Tursib",
            update_interval=datetime.timedelta(minutes=1),
        )
        self.stations = stations

    async def _async_update_data(self):
        """Fetch data for all stations."""
        data = {}
        now = datetime.datetime.now()

        for station_id, name in self.stations.items():
            try:
                url = f"https://tursib.ro/s/{station_id}?arrivals=on"
                resp = requests.get(url, timeout=15)
                resp.raise_for_status()
                parsed = self.parse_html_to_json(resp.text)

                weekday = now.weekday()
                if weekday < 5:
                    program_key = "luni-vineri"
                    program_label = "Luni–Vineri"
                elif weekday == 5:
                    program_key = "sambata"
                    program_label = "Sâmbătă"
                else:
                    program_key = "duminica"
                    program_label = "Duminică"

                departures_raw = parsed.get(program_key, [])
                departures_sorted = self._sorted_departures(departures_raw, now)

                data[station_id] = {
                    "station": name,
                    "program": program_label,
                    "departures": departures_sorted,
                    "last_update": datetime.datetime.now().isoformat(),
                }
            except Exception as e:
                raise UpdateFailed(f"Error updating station {name}: {e}")

        return data

    def _minutes_and_dt(self, now_dt, hhmm):
        try:
            h, m = map(int, hhmm.split(":"))
        except Exception:
            return None, None
        dep_dt = datetime.datetime.combine(now_dt.date(), datetime.time(h, m))
        if dep_dt < now_dt:
            dep_dt += datetime.timedelta(days=1)
        delta = (dep_dt - now_dt).total_seconds()
        if delta < 0:
            return None, None
        if delta < 60:
            minutes = "Acum"
        else:
            minutes = str(math.ceil(delta / 60))
        return minutes, dep_dt

    def _sorted_departures(self, departures, now_dt):
        occ = []
        for d in departures:
            minutes, dep_dt = self._minutes_and_dt(now_dt, d.get("departure", ""))
            if minutes is None:
                continue
            item = {
                "line": d.get("line", "?"),
                "destination": d.get("destination", "?"),
                "departure": d.get("departure", ""),
                "minutes": minutes,
                "scheduled_time": d.get("departure", ""),
            }
            occ.append((dep_dt, item))
        occ.sort(key=lambda x: x[0])
        return [x[1] for x in occ]

    def parse_html_to_json(self, html):
        soup = BeautifulSoup(html, "html.parser")
        data = {"luni-vineri": [], "sambata": [], "duminica": []}
        sections = soup.find_all("div", class_="program")

        for sec in sections:
            header = sec.find("h4")
            if not header:
                continue
            title = header.text.strip().lower()
            if "luni" in title:
                key = "luni-vineri"
            elif "sâmbătă" in title or "sambata" in title:
                key = "sambata"
            elif "duminică" in title or "duminica" in title:
                key = "duminica"
            else:
                continue

            plecari = sec.find_all("div", class_="card-body")
            for p in plecari:
                line_el = p.find("a", class_="traseu-link")
                dir_el = p.find("span", class_="headsign-info")
                times = [t.text.strip() for t in p.find_all("span", class_="h") if ":" in t.text]

                if not times:
                    continue

                line = line_el.text.strip() if line_el else "?"
                direction = dir_el.text.strip() if dir_el else "?"

                for t in times:
                    if len(t) == 5 and ":" in t:
                        data[key].append({"line": line, "destination": direction, "departure": t})

        return data if any(data.values()) else None


class TursibSensor(SensorEntity):
    """Representation of a Tursib station sensor."""

    def __init__(self, coordinator, station_id, name):
        self.coordinator = coordinator
        self._station_id = station_id
        self._attr_name = f"Tursib {name}"
        self._attr_unique_id = f"tursib_{station_id}"

    @property
    def native_value(self):
        departures = self.coordinator.data.get(self._station_id, {}).get("departures", [])
        return departures[0]["departure"] if departures else "n/a"

    @property
    def extra_state_attributes(self):
        return self.coordinator.data.get(self._station_id, {})
