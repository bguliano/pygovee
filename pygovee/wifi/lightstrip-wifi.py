import requests
import ast
from typing import List, Optional, Any, Dict
from dataclasses import dataclass
from colour import Color
import random


class CommandNotSupportedError(Exception):
    """ Exception raised when a command is attempted that is not supported by the device """

    def __init__(self, cmd: str):
        super().__init__(f'{cmd} is not supported by the selected device')


class NoDeviceSelected(Exception):
    """ Exception raised when a command is attempted but the controller is not connected to a device """

    def __init__(self):
        super().__init__('No device has been selected yet. Use select_device() to do so.')


class CommandFailure(Exception):
    """" Exception raised when executing a command returns a non-200 status code """

    def __init__(self, reason: str):
        super().__init__(f'Command failed to execute. Reason: {reason}')


@dataclass(frozen=True)
class WifiDeviceState:
    """ A dataclass that stores information about the current state of a device """
    online: bool
    state: bool
    onoff: str
    brightness: int
    color: Dict[str, int]
    r: int
    g: int
    b: int


@dataclass(frozen=True)
class WifiDevice:
    """ A dataclass that stores information about a wifi-enabled Govee device """
    mac: str
    model: str
    name: str
    controllable: bool
    retrievable: bool
    supportedCommands: List[str]
    _api_key: str

    @property
    def state(self) -> WifiDeviceState:
        response = requests.get("https://developer-api.govee.com/v1/devices/state",
                                headers={"Govee-API-Key": self._api_key},
                                params={"device": self.mac, "model": self.model}
                                )
        state = response.json()["data"]["properties"]
        state_dict = {}
        for prop in state:
            state_dict[list(prop.keys())[0]] = list(prop.values())[0]
        return WifiDeviceState(
            online=state_dict["online"],
            state=state_dict["powerState"] == "on",
            onoff=state_dict["powerState"],
            brightness=state_dict["brightness"],
            color=state_dict["color"],
            r=state_dict["color"]["r"],
            g=state_dict["color"]["g"],
            b=state_dict["color"]["b"]
        )


class WifiController:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.device: Optional[WifiDevice] = None

    def _check_support(self, cmd: str):
        if self.device is None:
            raise NoDeviceSelected
        if cmd not in self.device.supportedCommands:
            raise CommandNotSupportedError(cmd)

    def _send_request(self, cmd: dict):
        json = {"device": self.device.mac, "model": self.device.model, "cmd": cmd}
        response = requests.put("https://developer-api.govee.com/v1/devices/control",
                                headers={"Content-Type": "application/json",
                                         "Govee-API-Key": self.api_key},
                                json=json)
        if response.status_code != 200:
            dict_str = response.content.decode('utf-8')
            reason = ast.literal_eval(dict_str)["errors"]
            raise CommandFailure(reason)

    def get_devices(self) -> List[WifiDevice]:
        response = requests.get("https://developer-api.govee.com/v1/devices",
                                headers={"Govee-API-Key": self.api_key})
        result = []
        for device in response.json()["data"]["devices"]:
            result.append(WifiDevice(
                mac=device["device"],
                model=device["model"],
                name=device["deviceName"],
                controllable=device["controllable"],
                retrievable=device["retrievable"],
                supportedCommands=device["supportCmds"],
                _api_key=self.api_key
            ))
        return result

    def select_device(self, device: WifiDevice):
        if not isinstance(device, WifiDevice):
            raise ValueError("device parameter must be of type WifiDevice")
        self.device = device

    @staticmethod
    def color2rgb(color: Any):
        """ Converts a color-convertible into 3-tuple of 0-255 valued ints. """

        col = Color(color)
        rgb = col.red, col.green, col.blue
        rgb = [round(x * 255) for x in rgb]
        return tuple(rgb)

    def turn_on(self):
        self._check_support("turn")
        cmd = {
            "name": "turn",
            "value": "on"
        }
        self._send_request(cmd)

    def turn_off(self):
        self._check_support("turn")
        cmd = {
            "name": "turn",
            "value": "off"
        }
        self._send_request(cmd)

    def set_brightness(self, value: int):
        self._check_support("brightness")
        value = min(100, max(0, value))
        cmd = {
            "name": "brightness",
            "value": value
        }
        self._send_request(cmd)

    def set_rgb(self, r: int, g: int, b: int):
        self._check_support("color")
        r, g, b = [min(255, max(0, val)) for val in (r, g, b)]
        cmd = {
            "name": "color",
            "value": {
                "r": r,
                "g": g,
                "b": b
            }
        }
        self._send_request(cmd)

    def set_color(self, color: Any):
        self.set_rgb(*self.color2rgb(color))

    def set_random_color(self):
        self.set_rgb(*random.sample(range(255), 3))

    def set_temperature(self, temperature: int):
        self._check_support("colorTem")
        temperature = min(9000, max(2000, temperature))
        cmd = {
            "name": "colorTem",
            "value": temperature
        }
        self._send_request(cmd)
