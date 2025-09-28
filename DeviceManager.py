import logging
import pyudev
import re
import sys
import subprocess
from threading import Lock
import os

from utils import *

class Firmware:
    def __init__(self, name, file):
        self.name = name
        self.file = file
    
class Device:
    def __init__(self, serial, logger, dev_files={}):
        self.serial = serial
        self.logger = logger
        self.dev_files = dev_files
        self.exported_devices = {}

        self.available = True
        self.next_firmware = None
        self.lock = Lock()
        self.export_usbip = True
    
    def uploadFirmware(self, firmware):
        self.logger.info(f"updating firmware of {self.serial} to {firmware.name}")
        self.next_firmware = firmware
        self.cleanup()

    def handleAddDevice(self, udevinfo):
        if self.next_firmware:
            self.handleBootloaderMode(udevinfo)

        identifier = udevinfo.get("DEVNAME")

        if not identifier:
            self.logger.error(f"{format_dev_file(udevinfo)} addDevice: no devname in udevinfo, ignoring")
            return
        
        if identifier in self.dev_files.keys():
            self.logger.error(f"device {format_dev_file({udevinfo})} added but already exists, overwriting")
        
        self.dev_files[identifier] = udevinfo
        
        self.logger.info(f"added dev file {format_dev_file(udevinfo)}")

        if self.export_usbip:
            busid = get_busid(udevinfo)
            #TODO verify this works
            subprocess.run(["sudo", "usbip", "bind", "-b", busid])
        
            if busid not in self.exported_devices.keys():
                self.exported_devices[busid] = {}
            
            self.exported_devices[busid] = udevinfo

    def handleBootloaderMode(self, udevinfo):
        if udevinfo.get("SUBSYSTEM") == "tty":
            # TODO run on a separate thread with longer timeout
            subprocess.run(["picocom", "--baud", "1200", udevinfo["DEVNAME"]], timeout=2)
            logging.info(f"sending bootloader signal to {udevinfo["DEVNAME"]}")

        elif udevinfo.get("DEVTYPE") == "partition":
            logging.info(f"found bootloader candidate {udevinfo["DEVNAME"]} for {self.serial}")
            path = f"media/{self.serial}"
            if not os.path.isdir(path):
                os.mkdir(path)
            
            # TODO handle errors
            subprocess.run(["sudo", "mount", udevinfo["DEVNAME"], f"media/{self.serial}"])

            if os.listdir(path) != ["INDEX.HTM", "INFO_UF2.TXT"]:
                logging.warning(f"bootloader candidate {udevinfo["DEVNAME"]} for {self.serial} mounted but had unexpected files")
                subprocess.run(["sudo", "umount", path])
                return
            
            # TODO more error handling!
            subprocess.run(["sudo", "cp", "rp2_ice_blinky.uf2", path])
            subprocess.run(["sudo", "umount", path])
            logging.info(f"updated firmware for {self.serial}")
            self.next_firmware = None

    def cleanup(self):
        self.export_usbip = False

        for bus in set(self.exported_devices.keys()):
            subprocess.run(["sudo", "usbip", "unbind", "-b", bus], timeout=2)
            self.logger.debug(f"unbinding bus {bus}")
    
    def handleRemoveDevice(self, udevinfo):
        identifier = udevinfo.get("DEVNAME")

        if not identifier:
            self.logger.error(f"{format_dev_file(udevinfo)} removeDevice: no devname in udevinfo, ignoring")
            return
        
        if identifier not in self.dev_files.keys():
            self.logger.error(f"{format_dev_file(udevinfo)} removeDevice: dev file under major/minor does not exist, ignoring")
            return
        
        del self.dev_files[identifier]

        busid = get_busid(udevinfo)

        if busid not in self.exported_devices.keys():
            return
        
        if identifier not in self.exported_devices[busid]:
            return
        
        del self.exported_devices[busid][identifier]

        self.logger.info(f"removed device {format_dev_file(udevinfo)}")
    
    def reserve(self):
        with self.lock:
            if not self.available:
                return False
            
            self.available = False
            return True
    
    def unreserve(self):
        with self.lock:
            if self.available:
                return False
            
            self.available = True
            return True

class DeviceManager:
    def __init__(self, logger):
        self.logger = logger
        self.devs = {}

        if not os.path.isdir("media"):
            os.mkdir("media")

        def handle_dev_events(dev):
            attributes = dict(dev.properties)

            devname = attributes.get("DEVNAME")

            if not devname:
                return

            if not re.match("/dev/", devname) or re.match("/dev/bus/", devname):
                return

            id_model = attributes.get("ID_MODEL")

            if id_model != "RP2350" and id_model != 'pico-ice' and id_model != 'Pico':
                return 
            
            serial = attributes.get("ID_SERIAL_SHORT")

            if not serial:
                return

            if dev.action == "add":
                self.handleAddDevice(serial, attributes)
            elif dev.action == "remove":
                self.handleRemoveDevice(serial, attributes)
            else:
                logger.warning(f"Unhandled action type {dev.action} for {format_dev_file(attributes)}")

        context = pyudev.Context()
        monitor = pyudev.Monitor.from_netlink(context)
        observer = pyudev.MonitorObserver(monitor, callback=handle_dev_events, name='monitor-observer')
        observer.start()


    def handleAddDevice(self, serial, udevinfo):
        if serial not in self.devs:
            self.logger.info(f"Creating device with serial {serial}")
            self.devs[serial] = Device(serial, self.logger)
        
        self.devs[serial].handleAddDevice(udevinfo)

    def handleRemoveDevice(self, serial, udevinfo):
        if serial not in self.devs:
            self.logger.warning(f"tried to remove dev file {format_dev_file(udevinfo)} but does not exist")
            return
        
        self.devs[serial].handleRemoveDevice(udevinfo)
    
    def getDevices(self):
        values = []

        for d in self.devs:
            values.append(d.serial)
        
        return values
    
    def getDevicesAvailable(self):
        values = []

        for d in self.devs.values():
            if d.available:
                values.append(d.serial)
        
        return values
