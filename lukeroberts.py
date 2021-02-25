#!/usr/bin/python3

import sys
sys.path[0:0] = (".","../bleak","../txdbus","../anyio/src")

import anyio
from bleak import BleakScanner, BleakClient
from functools import partial

import logging
logging.basicConfig(level=logging.DEBUG)

async def dev_main(addr,adap,sc):
    async with BleakClient(addr, adapter=adap):
        svcs = await client.get_services()
        print("Services:")
        for service in svcs:
            print(service)
        sc.cancel()

def detection_callback(scanner, tg, device, advertisement_data):
    print(device.address, "RSSI:", device.rssi, advertisement_data)
    for u in device.details.get('UUIDs',[]):
        if u.upper() == "44092840-0567-11E6-B862-0002A5D5C51B":
            tg.spawn(dev_main,device,scanner._adapter,tg.cancel_scope)
            break

async def main():
    scanner = BleakScanner(adapter="hci0")
    async with anyio.create_task_group() as tg:
        scanner.register_detection_callback(partial(detection_callback,scanner,tg))

        async with scanner:
            #await anyio.sleep(2)
            #print(await scanner.get_discovered_devices())
            await anyio.sleep(99999)

anyio.run(main, backend="asyncio")

