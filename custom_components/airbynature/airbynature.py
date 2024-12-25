import datetime
import logging
import requests

# logo - see https://airbynature.com/wp-content/uploads/2023/03/brochure-test-nye-produkt-tekster.pdf

from homeassistant import config_entries, exceptions


class InvalidLogin(Exception):
    """Error to indicate there is an invalid username/password."""


class HttpTimeout(Exception):
    """Error communication timeout."""


_LOGGER = logging.getLogger(__name__)


class AirByNature:
    host = "https://admin.airbynature.com"
    user = ""
    token = ""
    profile_id = -1
    group_id = -1
    device_id = []

    def __init__(self):
        _LOGGER.info("Starting")

    def login(self, user, password):
        login_ext = "/oauth/token"
        header = {
            "Content-type": "application/x-www-form-urlencoded",
            "Accept": "application/json, text/plain, */*",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }
        data = {
            "username": user,
            "password": password,
            "grant_type": "password",
            "scope": "*",
            "client_id": "1",
            "client_secret": "angular-app",
        }

        url = self.host + login_ext
        try:
            response = requests.post(url=url, headers=header, data=data, timeout=10)
        except requests.exceptions.Timeout as err:
            raise HttpTimeout("Login timeout") from err

        if response.status_code != 200:
            _LOGGER.error("Login failed: %d", response.status_code)
            raise InvalidLogin("login failed")

        rjson = response.json()
        self.token = rjson["access_token"]
        return True

    def get_profile_id(self):
        # optional
        profile_ext = "/api/profile"

        header = {
            "Content-type": "application/json",
            "Authorization": "Bearer " + self.token,
        }

        url = self.host + profile_ext
        try:
            response = requests.get(url=url, headers=header, timeout=10)
        except requests.exceptions.Timeout as err:
            raise HttpTimeout("Get profile timoue") from err

        if response.status_code != 200:
            _LOGGER.error("Get Profile failed: %d", response.status_code)
            raise InvalidLogin("Get profile error")
        rjson = response.json()
        # _LOGGER.info(rjson)
        self.profile_id = rjson["data"]["id"]

        group_ext = "/api/user-app/devicegroups"
        url = self.host + group_ext
        try:
            response = requests.get(url=url, headers=header, timeout=10)
        except requests.exceptions.Timeout as err:
            raise HttpTimeout("Get device group timeout") from err

        if response.status_code != 200:
            _LOGGER.error("Get device group failed: %d", response.status_code)
            raise InvalidLogin("Get device group failed")
        rjson = response.json()
        # _LOGGER.info(rjson)
        self.group_id = rjson["data"][0]["id"]

    def get_devices(self):
        devices_ext = f"/api/user-app/devicegroups/{self.group_id}"

        header = {
            "Content-type": "application/json",
            "Authorization": "Bearer " + self.token,
        }
        url = self.host + devices_ext
        try:
            response = requests.get(url=url, headers=header, timeout=10)
        except requests.exceptions.Timeout as err:
            raise HttpTimeout("Get devices timeoiut") from err

        if response.status_code != 200:
            _LOGGER.error("Get Devices failed: %d", response.status_code)
            raise InvalidLogin("Get devices failed")

        rjson = response.json()
        # _LOGGER.info(rjson)
        self.decode_data(rjson)
        return rjson

    def decode_device_data(self, data):
        name = data["name"]
        out_speed_factor = data["outlet_speed_factor"]  #: "65.00",
        in_speed_factor = data["inlet_speed_factor"]  #: "55.00",
        comfort_level = data["comfort_level"]  #: 3,           fan speed
        is_online = data["is_online"]  #: true,
        rssi = data["wifi_signal"]  #: 28,

        more_data = data["latest_history"]

        temperature_in = more_data["inlet_temp"]  #: 23.82,
        hum_in = more_data["inlet_humid"]  #: 60.72,
        in_fan = more_data["inlet_fan"]  #: 0,
        in_fan1_rpm = more_data["inlet_fan1_rpm"]  #: 0,
        in_fan2_rpm = more_data["inlet_fan2_rpm"]  #: 0,
        temperature_out = more_data["outlet_temp"]  #: 25.9,
        hum_out = more_data["outlet_humid"]  #: 55.45,
        co2_out = more_data["outlet_co2"]  #: 440.72,
        out_fan = more_data["outlet_fan"]  #: 74,
        tvoc_out = more_data["outlet_tvoc"]  #: 46.9,
        out_fan1_rpm = more_data["outlet_fan1_rpm"]  #: 3616,
        out_fan2_rpm = more_data["outlet_fan2_rpm"]  #: 0,
        temperature_outside = more_data["external_temp"]  #: 23.27,

        _LOGGER.info("%s - speed: %d", name, comfort_level)
        _LOGGER.info(
            "Temperature: outside: %f in: %f - out: %f",
            temperature_outside,
            temperature_in,
            temperature_out,
        )
        _LOGGER.info("Humidity: in: {hum_in} out: {hum_out}")
        _LOGGER.info("Env: CO2 out: %f TVOC: %f", co2_out, tvoc_out)
        _LOGGER.info("RPM: in: %f out: %f ", in_fan1_rpm, out_fan1_rpm)

    def decode_data(self, data):
        main_data = data["data"]

        target_temperature = main_data["target_temperature"]
        current_rule = main_data["current_running_rule"]
        mode = main_data["mode"]
        avg_temp = main_data["avg_temp"]
        is_drying = main_data["is_drying"]
        status = main_data["status"]

        _LOGGER.info("Target temperature: %f", target_temperature)

        for device in main_data["devices"]:
            self.device_id.append(device["id"])
            self.decode_device_data(device)

        # _LOGGER.info(self.device_id)

    def set_level(self, new_level):
        data = {"comfort_level": new_level}
        header = {
            "Content-type": "application/json",
            "Authorization": "Bearer " + self.token,
        }

        for device in self.device_id:
            set_level_ext = (
                f"/api/user-app/devicegroups/{self.group_id}/devices/{device}"
            )
            url = self.host + set_level_ext
            _LOGGER.info(url)
            _LOGGER.info(data)

            try:
                response = requests.patch(
                    url=url, headers=header, json=data, timeout=10
                )
            except requests.exceptions.Timeout:
                raise HttpTimeout

            if response.status_code != 200:
                _LOGGER.error(
                    "Set comfort level %d failed: %d", new_level, response.status_code
                )
                raise InvalidLogin
            # _LOGGER.info(response.json())
            # validate maybe?

    def set_target_temperature(self, new_temperature):
        devices_ext = f"/api/user-app/devicegroups/{self.group_id}"

        header = {
            "Content-type": "application/json",
            "Authorization": "Bearer " + self.token,
        }
        data = {"target_temperature": new_temperature}

        url = self.host + devices_ext
        try:
            response = requests.put(url=url, headers=header, json=data, timeout=10)
        except requests.exceptions.Timeout:
            raise HttpTimeout

        if response.status_code != 200:
            _LOGGER.error("Set temperature failed: %d", response.status_code)
            raise InvalidLogin

    def set_pause_for_hours(self, hours_to_pause):
        devices_ext = f"/api/user-app/devicegroups/{self.group_id}"

        header = {
            "Content-type": "application/json",
            "Authorization": "Bearer " + self.token,
        }
        if hours_to_pause == 0:
            data = {"pause_inlets_until": None}
        else:
            utc_now = datetime.datetime.now(datetime.UTC) + datetime.timedelta(
                hours=hours_to_pause
            )
            utc_now_plus_hours = utc_now.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            data = {"pause_inlets_until": utc_now_plus_hours}

        url = self.host + devices_ext
        try:
            response = requests.put(url=url, headers=header, json=data, timeout=10)
        except requests.exceptions.Timeout:
            raise HttpTimeout

        if response.status_code != 200:
            _LOGGER.error(
                "Set pause for %d failed: %d", hours_to_pause, response.status_code
            )
            raise InvalidLogin

        # _LOGGER.info(response.json())

    def set_stopPause(self):
        self.set_pause_for_hours(0)


if __name__ == "__main__":
    _LOGGER.info("testing")
    abn = AirByNature()
    abn.login("karsten@tonnet.dk", "hoshah60")

    abn.get_profile_id()
    abn.get_devices()
    abn.set_level(3)

    abn.set_target_temperature(23)

    abn.set_pause_for_hours(0)
