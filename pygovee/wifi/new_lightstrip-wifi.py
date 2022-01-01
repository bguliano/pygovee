import requests
import ast
from typing import List, Any, Union, Tuple, Dict
from colour import Color
import random
from collections import ChainMap


class CommandNotSupportedError(Exception):
    """ Exception raised when a command is attempted that is not supported by the device """

    def __init__(self, cmd: str):
        super().__init__(f'{cmd} is not supported by the selected device')


class CommandFailure(Exception):
    """" Exception raised when executing a command returns a non-200 status code """

    def __init__(self, reason: str):
        super().__init__(f'Command failed to execute. Reason: {reason}')


class WifiDevice:
    def __init__(self, **kwargs):
        self.api_key = kwargs["api_key"]

        # device vars
        self.mac = kwargs["mac"]
        self.model = kwargs["model"]
        self.name = kwargs["name"]
        self.controllable = kwargs["controllable"]
        self.retrievable = kwargs["retrievable"]
        self.supportedCommands = kwargs["supportedCommands"]

    @property
    def online(self) -> bool:
        return self._get_state("online")

    @property
    def state(self) -> bool:
        return self.onoff == "on"

    @state.setter
    def state(self, val: bool):
        self.set_state(val)

    @property
    def onoff(self) -> str:
        return self._get_state("powerState")

    @onoff.setter
    def onoff(self, val: str):
        self.set_state(val == "on")

    @property
    def brightness(self) -> int:
        return self._get_state("brightness")

    @brightness.setter
    def brightness(self, val: int):
        self.set_brightness(val)

    @property
    def r(self) -> int:
        return self._get_state("color")["r"]

    @r.setter
    def r(self, val: int):
        rgb = self._get_state("color")
        self.set_rgb(val, rgb["g"], rgb["b"])

    @property
    def g(self) -> int:
        return self._get_state("color")["g"]

    @g.setter
    def g(self, val: int):
        rgb = self._get_state("color")
        self.set_rgb(rgb["r"], val, rgb["b"])

    @property
    def b(self) -> int:
        return self._get_state("color")["b"]

    @b.setter
    def b(self, val: int):
        rgb = self._get_state("color")
        self.set_rgb(rgb["r"], rgb["g"], val)

    @property
    def color(self) -> Tuple[int, int, int]:
        rgb = self._get_state("color")
        return rgb["r"], rgb["g"], rgb["b"]

    @color.setter
    def color(self, val: Any):
        self.set_rgb(*self.color2rgb(val))

    def _check_support(self, cmd: str):
        if cmd not in self.supportedCommands:
            raise CommandNotSupportedError(cmd)

    def _get_state(self, key: str) -> Union[bool, str, int, Dict[str, int]]:
        response = requests.get("https://developer-api.govee.com/v1/devices/state",
                                headers={"Govee-API-Key": self.api_key},
                                params={"device": self.mac, "model": self.model}
                                )
        state = response.json()["data"]["properties"]
        state_dict = dict(ChainMap(*state))
        # valid keys are: online, powerState, brightness, color
        return state_dict[key]

    def _send_request(self, cmd: dict):
        json = {"device": self.mac, "model": self.model, "cmd": cmd}
        response = requests.put("https://developer-api.govee.com/v1/devices/control",
                                headers={"Content-Type": "application/json",
                                         "Govee-API-Key": self.api_key},
                                json=json)
        if response.status_code != 200:
            dict_str = response.content.decode('utf-8')
            reason = ast.literal_eval(dict_str)["errors"]
            raise CommandFailure(reason)

    @staticmethod
    def color2rgb(color: Any) -> Tuple[int, ...]:
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

    def set_state(self, state: bool):
        if state:
            self.turn_on()
        else:
            self.turn_off()

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


def get_devices(api_key: str) -> List[WifiDevice]:
    response = requests.get("https://developer-api.govee.com/v1/devices",
                            headers={"Govee-API-Key": api_key})
    result = []
    for device in response.json()["data"]["devices"]:
        result.append(WifiDevice(
            mac=device["device"],
            model=device["model"],
            name=device["deviceName"],
            controllable=device["controllable"],
            retrievable=device["retrievable"],
            supportedCommands=device["supportCmds"],
            api_key=api_key
        ))
    return result
