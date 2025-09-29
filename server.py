import flask
import logging
import sys
from werkzeug.utils import secure_filename

from DeviceManager import DeviceManager

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler(sys.stdout))

manager = DeviceManager(logger, export_usbip=True)


app = flask.Flask(__name__)

@app.get("/devices/all")
def devices_all():
    return manager.getDevices()

@app.get("/devices/available")
def devices_available():
    return manager.getDevicesAvailable()

@app.get("/devices/buses/<device>")
def devices_bus(device):
    devices = manager.getDeviceExportedBuses(device)

    if devices:
        return flask.jsonify(devices), 200
    
    return "", 403

@app.get("/devices/reserve/<device>")
def devices_reserve_put(device):
    res = manager.reserve(device)

    return "", 200 if res else 403

@app.get("/devices/unreserve/<device>")
def devices_reserve_delete(device):
    res = manager.unreserve(device)

    return "", 200 if res else 403

from DeviceManager import Firmware

@app.post("/devices/flash/<device>")
def devices_flash(device):
    if "firmware" not in flask.request.files:
        return "No firmware", 403

    file = flask.request.files["firmware"]

    name = flask.request.form.get("name")
    if not name:
        return "No name", 403
    
    fname = "firmware/" + secure_filename(device) + ".uf2"
    file.save(fname)

    res = manager.uploadFirmware(device, Firmware(name, fname))

    return "", 200 if res else 403

app.run()

