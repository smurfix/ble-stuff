#!/usr/bin/python3

import sys
sys.path[0:0] = (".","../bleak","../asyncdbus","../anyio/src")

import anyio
from bleak import BleakScanner, BleakClient
from functools import partial

import logging
logging.basicConfig(level=logging.DEBUG)

async def dev_main(addr,adap):
    async with BleakClient(addr, adapter=adap):
        svcs = await client.get_services()
        print("Services:")
        for service in svcs:
            print(service)

def detection_callback(scanner, tg, device, advertisement_data):
    print(device.address, "RSSI:", device.rssi, advertisement_data)
    if device.details['Name'].startswith("Beurer "):
        tg.spawn(dev_main,device.address,scanner._adapter)

async def main():
    scanner = BleakScanner(adapter="hci0")
    async with anyio.create_task_group() as tg:
        scanner.register_detection_callback(partial(detection_callback,scanner,tg))

        async with scanner:
            #await anyio.sleep(2)
            #print(await scanner.get_discovered_devices())
            await anyio.sleep(99999)

anyio.run(main, backend="trio")

