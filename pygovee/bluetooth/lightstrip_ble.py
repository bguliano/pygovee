""" Module for controlling a bluetooth-enabled Govee light or light strip """

import asyncio
from threading import Thread
from queue import Queue, Empty
from time import time, sleep
from typing import Union, Any, List

from colour import Color
import bleak


UUID_CONTROL_CHARACTERISTIC = '00010203-0405-0607-0809-0a0b0c0d2b11'


class _BLEThread(Thread):
    """ Thread to send bluetooth commands to the device in the background """

    def __init__(self, mac: str, queue: Queue):
        Thread.__init__(self)
        self.client = bleak.BleakClient(mac)
        self.queue = queue
        self.loop = asyncio.get_event_loop()
        self.stop = False
        self.ready = False

    async def work(self):
        """ Process commands from the queue and manage sending commands to the device """

        prev_time = time()
        # connect to client using context manager
        async with self.client as client:
            self.ready = True
            while not self.stop:
                try:
                    frame = self.queue.get_nowait()
                    prev_time = time()
                except Empty:  # no items in the queue
                    # every 3 seconds, send a 'keep alive' packet
                    if time() > prev_time + 3:
                        frame = bytes([0xAA, 0x01])
                        frame += bytes([0] * (19 - len(frame)))
                        checksum = 0
                        for b in frame:
                            checksum ^= b
                        frame += bytes([checksum & 0xFF])
                        await client.write_gatt_char(UUID_CONTROL_CHARACTERISTIC, frame)
                        prev_time = time()
                else:  # there is an item in the queue
                    await client.write_gatt_char(UUID_CONTROL_CHARACTERISTIC, frame)
                    self.queue.task_done()

    def run(self):
        self.loop.run_until_complete(self.work())

    def stop_work(self):
        """ Stop processing and sending commands and disconnect from the device """
        self.stop = True


class BLEController:
    """ Control a bluetooth-enabled Govee light or light strip """

    def __init__(self, mac: str, block: bool = True, verbose: bool = True):
        # instance vars (not designed to be interacted with by user)
        self._queue = Queue()

        # create thread and start the connection process
        self._worker = _BLEThread(mac, self._queue)
        self._worker.daemon = True
        self._worker.start()

        # wait for a connection if block is true
        if block:
            while not self._worker.ready:
                pass
            if verbose:
                print("Successfully connected to the light strip")

        # user-editable vars
        self.blocking = True

    def _cleanup(self):
        """ Tell thread to stop processing queue items and disconnect from device """
        self._worker.stop_work()

    def __del__(self):
        self._cleanup()

    def _send(self, cmd: int, payload: Union[bytes, List[int]]):
        """ Sends a command and handles payload padding. """

        # make sure input params are the correct type
        if not isinstance(cmd, int):
            raise ValueError('Invalid command')
        if not isinstance(payload, bytes) and not (
            isinstance(payload, list) and all(isinstance(x, int) for x in payload)):
            raise ValueError('Invalid payload')
        if len(payload) > 17:
            raise ValueError('Payload too long')

        cmd = cmd & 0xFF
        frame = bytes([0x33, cmd]) + bytes(payload)

        # pad frame data to 19 bytes (plus checksum)
        frame += bytes([0] * (19 - len(frame)))

        # The checksum is calculated by XORing all data bytes
        checksum = 0
        for b in frame:
            checksum ^= b

        frame += bytes([checksum & 0xFF])

        # add data to the queue for sending to the device
        self._queue.put(frame)

        # wait for the command to be sent if blocking is true
        if self.blocking:
            self._queue.join()

    @staticmethod
    def color2rgb(color: Any):
        """ Converts a color-convertible into 3-tuple of 0-255 valued ints. """

        col = Color(color)
        rgb = col.red, col.green, col.blue
        rgb = [round(x * 255) for x in rgb]
        return tuple(rgb)

    def disconnect(self, turn_off: bool = False):
        """ Disconnect from the device """

        if turn_off:
            self.blocking = True
            self.set_brightness(100)
            self.turn_off()
        self._cleanup()

    def turn_off(self):
        """ Turn the device off """
        self._send(0x01, [0x0])

    def turn_on(self):
        """ Turn the device on """
        self._send(0x01, [0x1])

    def set_brightness(self, value: int):
        """ Sets the LED's brightness.

        `value` must be a value between 0 and 100
        """

        if not 0 <= value <= 100:
            raise ValueError("value must be between 0 and 100")
        value = round((value / 100) * 0xFF)
        self._send(0x04, [value])

    def set_rgb(self, r: int, g: int, b: int):
        """ Sets the device's color using rgb values """
        self._send(0x05, [0x02, r, g, b])

    def set_color(self, color: Any):
        """ Sets the LED's color.

        `color` must be a color-convertible (see the `colour` library),
        e.g. 'red', '#ff0000', etc.
        """
        self.set_rgb(*self.color2rgb(color))

    def blink(self, iterations: int = 3, delay: Union[int, float] = 1, color: Any = None):
        """ Blink the light """

        if color is not None:
            self.set_brightness(0)
            self.set_color(color)
        for _ in range(iterations):
            self.set_brightness(100)
            sleep(delay)
            self.set_brightness(0)
            sleep(delay)

    def fade(self,
             fade_in: bool = True,
             fade_out: bool = True,
             fade_amt: int = 100,
             fade_speed: int = 1,
             color: Any = None):
        """ Fade a color in or out """

        if color is not None:
            self.set_brightness(0)
            self.set_color(color)
        if fade_in:
            for i in range(0, fade_amt + 1, fade_speed):
                self.set_brightness(i)
        if fade_out:
            for i in range(fade_amt, -1, -fade_speed):
                self.set_brightness(i)


if __name__ == '__main__':
    import bluetooth_tools
    address = bluetooth_tools.get_mac_from_name("ihoment_H6110_DBA2")
    controller = BLEController(address)
