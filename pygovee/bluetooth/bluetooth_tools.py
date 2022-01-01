import bleak
import asyncio
from typing import List, Optional

def get_devices() -> List[bleak.backends.device.BLEDevice]:
    async def _get_devices():
        return await bleak.BleakScanner.discover()
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(_get_devices())

def get_mac_from_name(device_name: str) -> Optional[str]:
    for dev in get_devices():
        if dev.name == device_name:
            return dev.address
