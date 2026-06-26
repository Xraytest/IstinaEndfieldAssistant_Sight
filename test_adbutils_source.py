#!/usr/bin/env python3
import adbutils
import inspect
print('adbutils location:', inspect.getsourcefile(adbutils))

from adbutils import AdbDevice
print('AdbDevice.create_connection source:')
print(inspect.getsource(AdbDevice.create_connection))
