import os
import logging
import sys
import time

from usbipice.client.drivers.pulse_count import PulseCountClient
from usbipice.utils import get_ip

#################################################
BITSTREAM_PATHS = []

CLIENT_NAME = "read default example"
CLIENT_IP = get_ip() # local network ip - must be accessible by control/worker servers
CLIENT_PORT = "8080"
CONTROL_SERVER = ""

if not CONTROL_SERVER:
    CONTROL_SERVER = os.environ.get("USBIPICE_CONTROL_SERVER")
#################################################

if not CONTROL_SERVER:
    raise Exception("Configuration error")

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler(sys.stdout))

client = PulseCountClient(CONTROL_SERVER, CLIENT_NAME, logger)
client.start(CLIENT_IP, CLIENT_PORT)
if not client.reserve(1):
    raise Exception("failed to reserve")
# wait device to flash
time.sleep(15)

logger.info(client.evaluate(BITSTREAM_PATHS))

client.stop()
