import logging
import sys
import os
import time

import atexit
from pexpect import fdpexpect

from client.Client import Client
from client.EventHandler import DefaultEventHandler, EventHandler
from client.TimeoutDetector import TimeoutDetector

from utils.dev import get_dev_paths
from utils.utils import get_ip

#################################################
CLIENT_NAME = "read default example"
CLIENT_IP = get_ip() # local network ip - must be accessible by control/worker servers
CLIENT_PORT = "8080"
CONTROL_SERVER = ""

if not CONTROL_SERVER:
    CONTROL_SERVER = os.environ.get("USBIPICE_CONTROL_SERVER")
#################################################

if not (CLIENT_NAME and CLIENT_IP and CLIENT_PORT and CONTROL_SERVER):
    raise Exception("Configuration error.")

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler(sys.stdout))

client = Client(CLIENT_NAME, CONTROL_SERVER, logger)
event_handlers = []
event_handlers.append(DefaultEventHandler(logger))
event_handlers.append(TimeoutDetector(client, logger))

class ReadOnExport(EventHandler):
    def handleExport(self, client: Client, serial: str, bus, worker_ip, worker_port):
        time.sleep(2)
        device_paths = get_dev_paths()

        if serial not in device_paths:
            raise Exception("Unable to find device file.")

        dev_path = device_paths[serial][0]

        tty = os.open(dev_path, os.O_RDWR)
        p = fdpexpect.fdspawn(tty, timeout=5)
        p.expect("default firmware")
        print(f"Read from device {serial}!")
        p.close()

    def handleReservationEnd(self, client, serial):
        # Reserve new device
        new_serials = client.reserve(1)
        if not new_serials:
            raise Exception("Failed to reserve new device")

        print(f"Reserved new device: {new_serials[0]}")

event_handlers.append(ReadOnExport())

client.startEventServer(event_handlers, CLIENT_IP, CLIENT_PORT)

serials = client.reserve(1)
atexit.register(client.endAll)

if not serials:
    raise Exception("Failed to reserve a device.")

print(f"Reserved first device: {serials[0]}")

# Wait for first device to print
time.sleep(5)

# End the reservation of the first device. This will cause
# handleReservationEnd to run, and a new device will be reserved.
print("Ending first device reservation.")
ended = client.end(serials)

if not ended:
    raise Exception("Failed to end reservation.")
# Wait for second device to print
time.sleep(5)

# The old device is no longer available after the reservation
# has ended. This will happen regardless of whether the client
# ends the reservation itself or the time runs out.
print(f"Current devices: {list(get_dev_paths().keys())}")

# Stops the event server - this is done BEFORE the exit procedure
# of ending device reservations. If the event server was still running,
# the handler would reserve a new device.
client.stopEventServer()
