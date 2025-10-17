# usbip-ice
Device manager for exporting pico2-ice boards over usbip

# Security Considerations
Usbip does not use any form of authentication. This should not be used on insecure networks.

### Enable usbip
On both client and server devices
```
sudo modprobe usbip_core
sudo modprobe usbip_host
sudo modprobe vhci_hcd
```
On server device
```
sudo usbipd -D
```
### Install dependencies 
```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Configuration
- Set server port in server.py
- Set DEFAULT_MANAGER_SERVER in usbipicecl.py to the server address
- Set DEFAULT_DEVICE_IP in usbipicecl.py to the server ip
- Set client port in client.py
- If you are manually running the client server, set CLIENT_SERVER to its address in usbipicecl.py


### Usage
Run server.py on the device with the picos. This tracks devices, exports them over usbip, and provides an interface to interact with them. Devices are detected using the ID_MODEL they report, so firmware that modifies this field may not be detected. 

Optionally run client.py on the client. This is only needed if you are connecting to multiple devices. The client server subscribes to notifications when a usbip disconnect is detected and automatically reconnects it.  

usbipicecl.py is for actually connecting to the devices. You can run it to get available commands. Most importantly, the connect command will automatically connect to an available device over usbip. If a client server is provided, it will use it to reconnect to devices. Otherwise, it will start one - If you don't provide a client server and try to connect to multiple devices, you will get conflicting ports. The flash command is also useful. Note that this will only work on devices that respond to connecting with a baud of 1200. 