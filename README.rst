BLE stuff
=========

This repository contains a couple of Python scripts for doing things with
BLE.

In particular, I managed to read the stored data from a Beurer BM85 blood
pressure cuff.

Dependencies
++++++++++++

`bleak <https://github.com/hbldh/bleak>`_ with my asyncdbus add-on,
available `here <github.com/M-o-a-T/bleak>`_.

`dbus-next <https://github.com/altdesktop/python-dbus-next>`_, or rather my
`asyncdbus <https://github.com/M-o-a-T/asyncdbus>`_ branch.

`anyio <https://github.com/agronholm/anyio/>`_. You need the ``start_task``
branch.

