#!/usr/bin/python3

import sys
sys.path[0:0] = (".","../bleak","../asyncdbus","../anyio/src")

import anyio
from bleak import BleakScanner, BleakClient
from bleak.exc import BleakDisconnectError
from functools import partial
from datetime import datetime
from dataclasses import dataclass

import logging
logging.basicConfig(level=logging.INFO)

@dataclass(init=False)
class Measurement:
    pulse:float = None
    systole:float = None
    diastole:float = None
    arterial:float = None
    time:datetime = None
    unit:str = None

    @classmethod
    def decode(cls, b: bytearray, broken:bool = False):
        m = cls()
        flags = b[0]
        off = 1
        m.valid = bool(flags & 0x10)
        if not m.valid:
            raise NotImplementedError("Cannot decode invalid: %r",b)
        m.systole = m.decode_sfloat(b[off:off+2]) or None
        m.diastole = m.decode_sfloat(b[off+2:off+4]) or None
        m.arterial = m.decode_sfloat(b[off+4:off+6]) or None
        off += 6
        if flags & 0x8:
            raise NotImplementedError("Cannot decode user: %r",b)
        if flags & 0x02:
            yy = int.from_bytes(b[off:off+2],"little")
            mm = b[off+2]
            dd = b[off+3]
            HH = b[off+4]
            MM = b[off+5]
            SS = b[off+7]
            m.time = datetime(yy,mm,dd,HH,MM,SS)
            off += 7
        if flags & 0x04:
            m.pulse = m.decode_sfloat(b[off:off+2], broken) or None
            off += 2
        m.unit = "kPa" if flags & 1 else "mmHg"
        return m

    @staticmethod
    def decode_sfloat(b: bytearray, broken:bool = False):
        v = int.from_bytes(b,"big" if broken else "little")
        sign = -1 if v & 0x0800 else 1
        exp = v >> 12
        if exp > 7:
            exp -= 16
        val = v & 0x7FF
        return val * (10**exp) * sign



async def dev_main(addr,adap, sc):
    try:
        async with BleakClient(addr, adapter=adap) as client:
            svcs = await client.get_services()
            bp = svcs["00001810-0000-1000-8000-00805f9b34fb"]
            char = bp.get_characteristic("00002a35-0000-1000-8000-00805f9b34fb")

            print("READ")
            with anyio.move_on_after(5):
                async with client.notification(char) as q:
                    #d = await client.read_gatt_char(char)
                    #print("GOT",d)
                    async for d in q:
                        m = Measurement.decode(d, True)  # Beurer BM85 codes the pulse with wrong byte order
                        print(m)

            # done
    except BleakDisconnectError:
        pass
    print("DONE")
    sc.cancel()

def detection_callback(scanner, tg, device, advertisement_data):
    print(device.address, "RSSI:", device.rssi, advertisement_data)
    if device.name.startswith("Beurer "):
        tg.spawn(dev_main,device, scanner._adapter, tg.cancel_scope)

async def main():
    scanner = BleakScanner(adapter="hci1")
    async with anyio.create_task_group() as tg:
        scanner.register_detection_callback(partial(detection_callback,scanner,tg))

        async with scanner:
            #await anyio.sleep(2)
            #print(await scanner.get_discovered_devices())
            await anyio.sleep(99999)

anyio.run(main, backend="trio")

