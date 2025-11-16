import os
import re
import subprocess
import pyudev

def get_serial(dev):
    """Obtains the serial from a dev file dict. Returns false if the dev file 
    is not related to pico2-ice."""
    devname = dev.get("DEVNAME")

    if not devname:
        return False

    if not re.match("/dev/", devname) or re.match("/dev/bus/", devname):
        return False

    id_model = dev.get("ID_MODEL")

    if id_model != "RP2350" and id_model != 'pico-ice' and id_model != 'Pico':
        return False

    serial = dev.get("ID_SERIAL_SHORT")

    if serial:
        return serial

    return False

def format_dev_file(udevinfo):
    id_serial = udevinfo.get("ID_SERIAL")
    usb_num = udevinfo.get("ID_USB_INTERFACE_NUM")
    dev_name = udevinfo.get("DEVNAME")
    dev_path = udevinfo.get("DEVPATH")
    return f"[{id_serial} : {usb_num} : {dev_name} : {dev_path}]"

def get_busid(udevinfo):
    dev_path = udevinfo.get("DEVPATH")

    if not dev_path:
        return None

    # TODO really need to find a better way to do this
    capture = re.search("/usb1/.*?/(.*?)([:/]|$)", dev_path)
    if capture:
        return capture.group(1)
    return None

def mount(drive, loc, timeout=10):
    try:
        p = subprocess.run(["sudo", "mount", drive, loc], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout)
        if p.returncode != 0:
            raise Exception
    except:
        return False

    return True

def umount(loc):
    try:
        p = subprocess.run(["sudo", "umount", loc], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if p.returncode != 0:
            raise Exception
    except:
        return False

    return True

def send_bootloader(path, timeout=10):
    try:
        p = subprocess.run(["sudo", "picocom", "--baud", "1200", path], timeout=timeout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        return False

    return True

def get_devs():
    """Returns a dict mapping device serials to list of dev info dicts. This operation 
    looks through all available dev files and is intended to be only used once after reserving devices.
    If you are dealing with frequent dev file changes, you should use a pyudev MonitorObserver instead."""
    out = {}

    context = pyudev.Context().list_devices()
    for dev in context:
        values = dict(dev)
        serial = get_serial(values)

        if not serial:
            continue

        devname = values.get("DEVNAME")

        if not devname:
            continue

        if serial not in out:
            out[serial] = []
        
        out[serial].append(dev)
    
    return out

def get_dev_paths():
    """Returns a dict mapping device serials to list of dev paths. This operation 
    looks through all available dev files and is intended to be only used once after reserving devices.
    If you are dealing with frequent dev file changes, you should use a pyudev MonitorObserver instead."""
    out = get_devs()
    for key in out:
        items = map(lambda x : x.get("DEVNAME"), out[key])
        filtered = filter(lambda x : x, items)
        out[key] = list(filtered)
    
    return out

class FirmwareUploadFail(Exception):
    def __init__(self, *args):
        super().__init__(*args)

def upload_firmware(partition_path, mount_location, firmware_bytes, mount_timeout=10):
    mounted = mount(partition_path, mount_location, timeout=mount_timeout)

    if not mounted:
        return False

    if os.listdir(mount_location) != ["INDEX.HTM", "INFO_UF2.TXT"]:
        umount(mount_location)
        return False

    try:
        with open(os.path.join(mount_location, "firmware.uf2"), "wb") as f:
            f.write(firmware_bytes)
    except Exception:
        umount(partition_path)
        raise FirmwareUploadFail()

    umount(partition_path)

    return True


