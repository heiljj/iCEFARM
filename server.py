import flask
import logging
import sys

from DeviceManager import DeviceManager

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler(sys.stdout))

manager = DeviceManager(logger)


app = flask.Flask(__name__)

@app.get("/devices/all")
def devices_all():
    return manager.getDevices()

@app.get("/devices/available")
def devices_available():
    return manager.getDevicesAvailable()

@app.get("/devices/buses/<device>")
def devices_bus(device):
    if device not in manager.devs:
        return "", 400
    
    return manager.devs[device].exported_devices, 200

@app.put("/devices/reserve/<device>")
def devices_reserve_put(device):
    if device not in manager.devs:
        return "", 403
    
    res = manager.devs[device].reserve()
    return "", 200 if res else 403

@app.delete("/devices/reserve/<device>")
def f(device):
    if device not in manager.devs:
        return "", 403
    
    res = manager.devs[device].unreserve()
    return "", 200 if res else 403

from DeviceManager import Firmware

@app.put("/devices/flash/<device>")
def devices_flash(device):
    if device not in manager.devs:
        return "", 403
    
    # TODO
    manager.devs[device].uploadFirmware(Firmware("n", "f"))
    return "", 200

app.run()

