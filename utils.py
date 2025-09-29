def format_dev_file(udevinfo):
    id_serial = udevinfo.get("ID_SERIAL")
    usb_num = udevinfo.get("ID_USB_INTERFACE_NUM")
    dev_name = udevinfo.get("DEVNAME")
    return f"[{id_serial} : {usb_num} : {dev_name}]"

import re

# some devices like disks will show up as multiple devices since there are
# also partitions, but these will have the same busid. If one of these are 
# exported using usbip, a future exports will cause an error
def get_busid(udevinfo):
    dev_path = udevinfo.get("DEVPATH")

    if not dev_path:
        return None
    
    capture = re.search("/usb1/(.*?)/", dev_path).group(1)
    busid = re.search("(.*?)-", capture).group(1)
    busid = int(float(busid))

    devid = re.search("-(.*?)$", capture).group(1)
    devid = int(float(devid))

    return f"{busid}-{devid}"