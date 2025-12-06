import datetime
import math
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
                # return empty structure instead of raising, so the entity stays alive
                _LOGGER.warning("No timetable data found for station %s", self.station_id)
                return {
                    "station": self.station_name,
                    "program": "Necunoscut",
                    "departures": [],
                    "last_update": datetime.datetime.now().isoformat(),
                }

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

            return {
                "station": self.station_name,
                "program": program_label,
                "departures": departures_sorted,
                "last_update": datetime.datetime.now().isoformat(),
            }
        except Exception as e:
            # keep coordinator running but surface the error
            raise UpdateFailed(f"Error updating station {self.station_name}: {e}")

    def _minutes_and_dt(self, now_dt, hhmm, allow_next_day=False):
        """Compute minutes and departure datetime; skip past times unless fallback."""
        try:
            h, m = map(int, hhmm.split(":"))
        except Exception:
            return None, None

        dep_dt = datetime.datetime.combine(now_dt.date(), datetime.time(h, m))

        # In timpul zilei, eliminam plecarile trecute.
        if dep_dt <= now_dt:
            if allow_next_day:
                dep_dt += datetime.timedelta(days=1)
            else:
                return None, None

        delta = (dep_dt - now_dt).total_seconds()
        if delta < 60:
            minutes = "Acum"
        else:
            minutes = str(math.ceil(delta / 60))
        return minutes, dep_dt

    def _sorted_departures(self, departures, now_dt):
        """Return only future departures for today; fallback to next day if none."""
        occ = []
        for d in departures:
            dep_str = d.get("departure", "")
            minutes, dep_dt = self._minutes_and_dt(now_dt, dep_str, allow_next_day=False)
            if minutes is None:
                continue
            item = {
                "line": d.get("line", "?"),
                "destination": d.get("destination", "?"),
                "departure": dep_str,
                "minutes": minutes,
                "scheduled_time": dep_str,
            }
            occ.append((dep_dt, item))

        # Fallback pentru ziua urmatoare doar daca nu mai avem plecari azi.
        if not occ:
            for d in departures:
                dep_str = d.get("departure", "")
                minutes, dep_dt = self._minutes_and_dt(now_dt, dep_str, allow_next_day=True)
                if minutes is None:
                    continue
                item = {
                    "line": d.get("line", "?"),
                    "destination": d.get("destination", "?"),
                    "departure": dep_str,
                    "minutes": minutes,
                    "scheduled_time": dep_str,
                }
                occ.append((dep_dt, item))

        occ.sort(key=lambda x: x[0])
        # Optional: limiteaza la primele N
        return [x[1] for x in occ][:10]

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


class TursibSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Tursib station sensor."""

    def __init__(self, coordinator, station_id, station_name):
        super().__init__(coordinator)  # ✅ conectează entitatea la coordinator
        self._station_id = station_id
        self._attr_name = f"Tursib {station_name}"
        self._attr_unique_id = f"tursib_{station_id}"

    @property
    def native_value(self):
        """Return ora următoarei plecări (ca în AppDaemon)."""
        data = self.coordinator.data or {}
        departures = data.get("departures", [])
        return departures[0]["departure"] if departures else "n/a"

    @property
    def extra_state_attributes(self):
        """Return full data including sorted upcoming departures."""
        return self.coordinator.data or {}
