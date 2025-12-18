import datetime
import logging
import aiohttp
from bs4 import BeautifulSoup

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
    CoordinatorEntity,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up sensor entities for a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    station_id = config_entry.data["station_id"]
    station_name = config_entry.data["station_name"]

    async_add_entities([TursibSensor(coordinator, station_id, station_name)])


class TursibCoordinator(DataUpdateCoordinator):
    """Coordinator to fetch and parse Tursib data for one station."""

    def __init__(self, hass, station_id, station_name):
        super().__init__(
            hass,
            _LOGGER,
            name=f"Tursib {station_name}",
            update_interval=datetime.timedelta(minutes=1),
        )
        self.station_id = station_id
        self.station_name = station_name

    async def _async_update_data(self):
        """Fetch data for the configured station asynchronously."""
        now = datetime.datetime.now()
        try:
            url = f"https://tursib.ro/s/{self.station_id}?arrivals=on"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=15) as resp:
                    if resp.status != 200:
                        raise UpdateFailed(f"HTTP error {resp.status}")
                    text = await resp.text()

            parsed = self.parse_html_to_json(text)
            if not parsed:
                _LOGGER.warning("No timetable data found for station %s", self.station_id)
                return {
                    "station": self.station_name,
                    "program": "Necunoscut",
                    "departures": [],
                    "last_update": datetime.datetime.now().isoformat(),
                }

            weekday = now.weekday()
            if weekday < 5:
                program_key, program_label = "luni-vineri", "Luni–Vineri"
            elif weekday == 5:
                program_key, program_label = "sambata", "Sâmbătă"
            else:
                program_key, program_label = "duminica", "Duminică"

            departures_raw = parsed.get(program_key, [])
            departures_sorted = self._sorted_departures(departures_raw, now)

            return {
                "station": self.station_name,
                "program": program_label,
                "departures": departures_sorted,
                "last_update": datetime.datetime.now().isoformat(),
            }
        except Exception as e:
            raise UpdateFailed(f"Error updating station {self.station_name}: {e}")

    def _minutes_and_dt(self, now_dt, hhmm, allow_next_day=False):
        try:
            h, m = map(int, hhmm.split(":"))
        except:
            return None, None

        dep_dt = datetime.datetime.combine(now_dt.date(), datetime.time(h, m))
        if dep_dt <= now_dt:
            if allow_next_day:
                dep_dt += datetime.timedelta(days=1)
            else:
                return None, None

        delta = (dep_dt - now_dt).total_seconds()
        minutes = "Acum" if delta < 60 else str(int(delta // 60))
        return minutes, dep_dt

    def _sorted_departures(self, departures, now_dt):
        occ = []
        # Plecări azi și mâine (pentru continuitate noaptea)
        for allow_next in [False, True]:
            for d in departures:
                dep_str = d.get("departure", "")
                minutes, dep_dt = self._minutes_and_dt(now_dt, dep_str, allow_next_day=allow_next)
                if minutes is None:
                    continue

                item = {
                    "line": d.get("line", "?"),
                    "destination": d.get("destination", "?"),
                    "departure": dep_str,
                    "minutes": minutes,
                    "scheduled_time": dep_str,
                }
                # Evităm duplicatele dacă adăugăm și pentru ziua următoare
                if not any(
                        x[1]['departure'] == item['departure'] and x[1]['line'] == item['line'] and x[0] == dep_dt for x
                        in occ):
                    occ.append((dep_dt, item))

        occ.sort(key=lambda x: x[0])
        return [x[1] for x in occ][:10]

    def parse_html_to_json(self, html):
        soup = BeautifulSoup(html, "html.parser")
        data = {"luni-vineri": [], "sambata": [], "duminica": []}
        sections = soup.find_all("div", class_="program")

        for sec in sections:
            header = sec.find("h4")
            if not header: continue

            title = header.text.strip().lower()
            if "luni" in title:
                key = "luni-vineri"
            elif "sâmbătă" in title or "sambata" in title:
                key = "sambata"
            elif "duminică" in title or "duminica" in title:
                key = "duminica"
            else:
                continue

            # Fiecare 'card-body' reprezintă o direcție a unei linii (ex: 11 dus, 11 întors)
            rows = sec.find_all("div", class_="card-body")
            for r in rows:
                line_el = r.find("a", class_="traseu-link")
                dir_el = r.find("span", class_="headsign-info")

                if not line_el: continue
                line = line_el.get_text(strip=True)

                # Extragem textul complet de destinație (ex: "Spre stația A, B, C")
                raw_dest_text = dir_el.get_text(strip=True) if dir_el else ""

                # Curățăm prefixul și separăm destinațiile după virgulă
                clean_dest = raw_dest_text.replace("Spre stația", "").strip()
                dest_list = [d.strip() for d in clean_dest.split(",") if d.strip()]

                # Luăm toate orele de plecare (span-urile cu clasa 'h')
                time_spans = r.find_all("span", class_="h")
                for ts in time_spans:
                    t_text = ts.get_text(strip=True)
                    # Eliminăm textele care nu sunt ore (ex: leading "00:00")
                    if ":" not in t_text or len(t_text) > 5:
                        continue

                    # Destinația implicită este prima din listă
                    final_destination = dest_list[0] if dest_list else raw_dest_text

                    # Verificăm clasa de culoare: p0, p1, p2...
                    classes = ts.get("class", [])
                    for cls in classes:
                        if cls.startswith("p") and len(cls) > 1:
                            try:
                                # Extragem cifra de după 'p' (ex: din 'p1' luăm 1)
                                idx = int(cls[1:])
                                if idx < len(dest_list):
                                    final_destination = dest_list[idx]
                            except (ValueError, IndexError):
                                pass
                            break  # Am găsit clasa pX, nu mai căutăm în restul claselor span-ului

                    data[key].append({
                        "line": line,
                        "destination": final_destination,
                        "departure": t_text
                    })

        return data if any(data.values()) else None


class TursibSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Tursib station sensor."""

    def __init__(self, coordinator, station_id, station_name):
        super().__init__(coordinator)
        self._station_id = station_id
        self._attr_name = f"Tursib {station_name}"
        self._attr_unique_id = f"tursib_{station_id}"

    @property
    def native_value(self):
        data = self.coordinator.data or {}
        departures = data.get("departures", [])
        return departures[0]["departure"] if departures else "n/a"

    @property
    def extra_state_attributes(self):
        return self.coordinator.data or {}