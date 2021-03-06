"""Support for Naver Weather Sensors."""
import logging
import requests
from bs4 import BeautifulSoup
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from datetime import timedelta
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_NAME, CONF_SCAN_INTERVAL, CONF_MONITORED_CONDITIONS)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle


REQUIREMENTS = ["beautifulsoup4==4.9.0"]

_LOGGER = logging.getLogger(__name__)

CONF_AREA = 'area'

BSE_URL = 'https://search.naver.com/search.naver?query={}'

DEFAULT_NAME = 'naver_weather'
DEFAULT_AREA = '날씨'

SCAN_INTERVAL = timedelta(seconds=900)

_INFO = {
    'LocationInfo':   ['위치',         '',      'mdi:map-marker-radius'],
    'WeatherCast':    ['현재날씨',     '',      'mdi:weather-cloudy'],
    'NowTemp':        ['현재온도',     '°C',    'mdi:thermometer'],
    'Humidity':       ['현재습도',     '%',     'mdi:water-percent'],
    'TodayFeelTemp':  ['체감온도',     '°C',    'mdi:thermometer'],
    'TodayMinTemp':   ['최저온도',     '°C',    'mdi:thermometer-chevron-down'],
    'TodayMaxTemp':   ['최고온도',     '°C',    'mdi:thermometer-chevron-up'],
    'Ozon':           ['오존',         'ppm',   'mdi:alpha-o-circle'],
    'TodayUV':        ['자외선지수',   '',      'mdi:weather-sunny-alert'],
    'UltraFineDust':  ['초미세먼지',   '㎍/㎥', 'mdi:blur-linear'],
    'FineDust':       ['미세먼지',     '㎍/㎥', 'mdi:blur'],
    'tomorrowAState': ['내일오전날씨', '',      'mdi:weather-cloudy'],
    'tomorrowATemp':  ['내일최고온도', '°C',    'mdi:thermometer-chevron-up'],
    'tomorrowMState': ['내일오후날씨', '',      'mdi:weather-cloudy'],
    'tomorrowMTemp':  ['내일최저온도', '°C',    'mdi:thermometer-chevron-down']
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_AREA, default=DEFAULT_AREA): cv.string,
    vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL): cv.time_period,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up a Naver Weather Sensors."""
    name = config.get(CONF_NAME)
    area = config.get(CONF_AREA)

    informs = config.get(CONF_MONITORED_CONDITIONS)

    SCAN_INTERVAL = config.get(CONF_SCAN_INTERVAL)

    sensors = []
    child   = []

    api = NWeatherAPI(area)

    api.update()

    for key, value in api.result.items():
        sensor = childSensor(name, key, value)
        child   += [sensor]
        sensors += [sensor]

    sensors += [NWeatherSensor(name, api, child)]

    add_entities(sensors, True)


class NWeatherAPI:
    """NWeather API."""

    def __init__(self, area):
        """Initialize the NWeather API.."""
        self.area   = area
        self.result = {}

    def update(self):
        """Update function for updating api information."""
        try:
            url = BSE_URL.format(self.area)
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            NowTemp = ""
            CheckDust = []

            LocationInfo = soup.find('span', {'class':'btn_select'}).text

            # 현재 온도
            NowTemp = soup.find('span', {'class': 'todaytemp'}).text + soup.find('span', {'class' : 'tempmark'}).text[2:-1]

            # 날씨 캐스트
            WeatherCast = soup.find('p', {'class' : 'cast_txt'}).text

            # 오늘 오전온도, 오후온도, 체감온도
            TodayMinTemp = soup.find('span', {'class' : 'min'}).text[:-1]
            TodayMaxTemp = soup.find('span', {'class' : 'max'}).text[:-1]
            TodayFeelTemp = soup.find('span', {'class' : 'sensible'}).text[5:-1]

            # 자외선 지수
            TodayUV = soup.find('span', {'class' : 'indicator'}).text[4:].replace("\ub0ae\uc74c","").replace("\ubcf4\ud1b5","").replace("\ub192\uc74c","").replace("\ub9e4\uc6b0","").replace("\uc704\ud5d8","")

            # 미세먼지, 초미세먼지, 오존 지수
            CheckDust1 = soup.find('div', {'class': 'sub_info'})
            CheckDust2 = CheckDust1.find('div', {'class': 'detail_box'})

            for i in CheckDust2.select('dd'):
                CheckDust.append(i.text)

            FineDust = CheckDust[0][:-5]
            UltraFineDust = CheckDust[1][:-5]
            Ozon = CheckDust[2][:-5]

            # 현재 습도
            Humidity1 = soup.find('div', {'class': 'info_list humidity _tabContent'})
            Humidity2 = Humidity1.find('li', {'class': 'on now'})
            Humidity3 = Humidity2.find('dd', {'class': 'weather_item _dotWrapper'})
            Humidity = Humidity3.find('span').text.strip()


            # 내일 오전, 오후 온도 및 상태 체크
            tomorrowArea = soup.find('div', {'class': 'tomorrow_area'})
            tomorrowCheck = tomorrowArea.find_all('div', {'class': 'main_info morning_box'})

            # 내일 오전온도
            tomorrowMTemp = tomorrowCheck[0].find('span', {'class': 'todaytemp'}).text

            # 내일 오전상태
            tomorrowMState1 = tomorrowCheck[0].find('div', {'class' : 'info_data'})
            tomorrowMState2 = tomorrowMState1.find('ul', {'class' : 'info_list'})
            tomorrowMState = tomorrowMState2.find('p', {'class' : 'cast_txt'}).text

            # 내일 오후온도
            tomorrowATemp1 = tomorrowCheck[1].find('p', {'class' : 'info_temperature'})
            tomorrowATemp = tomorrowATemp1.find('span', {'class' : 'todaytemp'}).text

            # 내일 오후상태
            tomorrowAState1 = tomorrowCheck[1].find('div', {'class' : 'info_data'})
            tomorrowAState2 = tomorrowAState1.find('ul', {'class' : 'info_list'})
            tomorrowAState = tomorrowAState2.find('p', {'class' : 'cast_txt'}).text

            #json 파일로 저장
            weather = dict()
            weather["LocationInfo"]   = LocationInfo
            weather["NowTemp"]        = NowTemp
            weather["Humidity"]       = Humidity
            weather["TodayFeelTemp"]  = TodayFeelTemp
            weather["TodayMinTemp"]   = TodayMinTemp
            weather["TodayMaxTemp"]   = TodayMaxTemp
            weather["WeatherCast"]    = WeatherCast
            weather["TodayUV"]        = TodayUV
            weather["FineDust"]       = FineDust
            weather["UltraFineDust"]  = UltraFineDust
            weather["Ozon"]           = Ozon
            weather["tomorrowMTemp"]  = tomorrowMTemp
            weather["tomorrowMState"] = tomorrowMState
            weather["tomorrowATemp"]  = tomorrowATemp
            weather["tomorrowAState"] = tomorrowAState

            self.result = weather
        except Exception as ex:
            _LOGGER.error('Failed to update NWeather API status Error: %s', ex)
            raise


class NWeatherSensor(Entity):
    """Representation of a KWeather Sensor."""

    def __init__(self, name, api, child):
        """Initialize the NWeather sensor."""
        self._name = name
        self._api   = api
        self._child = child
        self._icon = 'mdi:weather-partly-cloudy'

    @property
    def entity_id(self):
        """Return the entity ID."""
        return 'sensor.naver_weather'

    @property
    def name(self):
        """Return the name of the sensor, if any."""
        return '네이버 날씨'

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._api.result["WeatherCast"]

    @Throttle(SCAN_INTERVAL)
    def update(self):
        """Get the latest state of the sensor."""
        if self._api is None:
            return

        self._api.update()

        for sensor in self._child:
            sensor.setValue( self._api.result[sensor._key] )

    @property
    def device_state_attributes(self):
        """Attributes."""

        data = {}

        for key, value in self._api.result.items():
            data[_INFO[key][0]] = '{}{}'.format(value, _INFO[key][1])

        return data

class childSensor(Entity):
    """Representation of a KWeather Sensor."""
    _STATE = None

    def __init__(self, name, key, value):
        """Initialize the NWeather sensor."""
        self._name  = name
        self._key   = key
        self._value = value
        self._STATE = value

    @property
    def entity_id(self):
        """Return the entity ID."""
        return 'sensor.nw_{}'.format(self._key.lower())

    @property
    def name(self):
        """Return the name of the sensor, if any."""
        return _INFO[self._key][0]

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return _INFO[self._key][2]

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._value

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return _INFO[self._key][1]


    def update(self):
        """Get the latest state of the sensor."""
        self._value = self._STATE

    def setValue(self, value):
        self._STATE = value

        self.update()

    @property
    def device_state_attributes(self):
        """Attributes."""
        data = {}

        data[self._key] = self._value

        return data

