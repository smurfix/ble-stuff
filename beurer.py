#!/usr/bin/python3

import sys
sys.path[0:0] = (".","../bleak","../asyncdbus","../anyio/src")

import anyio
from bleak import BleakScanner, BleakClient
from bleak.exc import BleakDisconnectError
from functools import partial
from datetime import datetime
from dataclasses import dataclass
from trio_mysql import connect as mysql_connect
import asyncclick as click

import logging
logging.basicConfig(level=logging.INFO)

#
# Database support
SQL = """
CREATE TABLE `user` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(80) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `u_name` (`name`)
);

CREATE TABLE `blood_pressure` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user` int(11) NOT NULL,
  `time` datetime NOT NULL,
  `systole` float DEFAULT NULL,
  `diastole` float DEFAULT NULL,
  `arterial` float DEFAULT NULL,
  `bpm` float DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `user_time` (`user`,`time`),
  CONSTRAINT `blood_pressure_user` FOREIGN KEY (`user`) REFERENCES `user` (`id`) ON DELETE CASCADE
);
"""

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

lock = False

async def dev_main(addr,adap, tg, user, once, params):

    async def locker():
        global lock
        lock = True
        with anyio.open_cancel_scope(shield=True):
            await anyio.sleep(30)
            lock = False
    #await tg.spawn(locker)

    try:
        async with mysql_connect(**params) as conn:
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
                            async with conn.transaction(), conn.cursor() as curs:
                                await curs.execute("select id from blood_pressure where user=%s and `time`=%s", (user,m.time))
                                r = await curs.fetchone()
                                print("Q",user,m.time,r)
                                if r is not None:
                                    continue
                                await curs.execute("insert into blood_pressure set user=%s, time=%s, systole=%s,diastole=%s,arterial=%s,bpm=%s", [user,m.time, m.systole,m.diastole,m.arterial,m.pulse])

                                print("W",curs.lastrowid)
                            print(m)

            # done
    except BleakDisconnectError:
        pass
    print("DONE")
    if once:
        tg.cancel_scope.cancel()

def detection_callback(scanner, tg, user, once, params, device, advertisement_data):
    print(device.address, "RSSI:", device.rssi, advertisement_data)
    if lock:
        return
    for uuid in device.details['props'].get('UUIDs',()):
        if uuid.lower() == "00001810-0000-1000-8000-00805f9b34fb":
            tg.spawn(dev_main, device, scanner._adapter, tg, user, once, params)
            break

@click.async_backend("trio")
@click.command()
@click.option("-i","--interface","intf", type=str, help="Bluetooth interface to listen to", default="hci0")
@click.option("-h","--host", type=str, help="Database host to connect to", default="localhost")
@click.option("-P","--port", type=int, help="Database port to connect to", default=3306)
@click.option("-u","--user", type=str, help="Database user", default="test")
@click.option("-p","--pass", "password", type=str, prompt=True, hide_input=True, help="Database password")
@click.option("-d","--database", type=str, help="Database to use", default="health")
@click.option("-o","--one-shot", "once", is_flags=True, help="stop after successful transmission")
@click.argument("name", type=str, nargs=1)
async def main(name, intf, once, **params):
    async with mysql_connect(**params) as conn, conn.transaction():
        async with conn.cursor() as curs:
            await curs.execute("select id from user where name=%s", (name,))
            res = await curs.fetchone()
            if res is None:
                await curs.execute("insert into user set name=%s", (name,))
                user = curs.lastrowid
            else:
                user = res[0]

    scanner = BleakScanner(adapter=intf)
    async with anyio.create_task_group() as tg:
        scanner.register_detection_callback(partial(detection_callback,scanner,tg,user, once, params))

        async with scanner:
            #await anyio.sleep(2)
            #print(await scanner.get_discovered_devices())
            await anyio.sleep(99999)

main()

