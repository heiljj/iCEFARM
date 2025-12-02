## Worker setup

### Enable usbip 
```
sudo modprobe usbip_host
sudo modprobe usbip_core
sudo modprobe vhci_hcd
sudo usbipd -D
```

### Pythons deps 
```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

### Building device firmware
Follow steps in [firmware](./firmware/)

### Environment Configuration
- Create a configuration - see [example_config](./example_config.ini)

### Run
```
sudo USBIPICE_DATABASE=[libpg connection string] .venv/bin/worker -c [config]
```