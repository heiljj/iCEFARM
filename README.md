# iCE FPGA Array Resource Manager
Device manager for reserving and interfacing with pico2-ice development boards.

## Architecture Overview
- Control
    - Hosts a database. This keeps track of all of the pico devices, and on-going reservation sessions.
    - Provides an API for reserving devices.
    - Heartbeats workers
- Worker
    - Physically connected to the pico devices.
    - Updates database with devices.
    - Provides APIs for interacting with devices.
- Client
    - Reserve devices using the control API
    - Interface with devices using the worker APIs

### Worker
Each pico maintains a certain state object, which defines the behavior of the device. When clients request for a certain device behavior, such as a pulse-count evaluator, they are indicating which state the pico should switch to. The [reservable](./src/usbipice/worker/device/state/reservable/) module contains the states that the client can request. These states are event based and include hooks for add/remove device events. In addition, a state can make a method available to be called by clients through a web API. This is done in a similar way to how most Python web frameworks declare url paths with decorators and has support for files. States can also send events back to clients.

### Client
The core of the client is the event server. This event server is in change of listening for events sent by device states, and routing them to event handlers.

A separate client interface is made for each device state, and a single device state may have multiple different clients for different situations. The client lib contains a base for each device state, which includes an event handler stub. An example of this is the [pulse count state](./src/usbipice/client/lib/pulsecount.py), which contains an event hook for once the bitstreams have been evaluated. In addition, an API for interacting with methods that the state has made available for web interfacing is included. Continuing with the pulse count example, the client can first use *reserve* to obtain a device, then call *evaluate* to queue a bitstream for evaluation. Once the device state has finished measuring the amount of pulses, it sends a request to the event server of the client. The event server then routes the request into the *results* method on the event handler.

## Local Development Setup
### Database Setup
iCEFARM uses postgres. Install postgres:
```
sudo apt install postgresql
```
Start postgres:
```
service postgresql@{version}-main start
```
Create a database and user. Note that this can be configured using the [command generator](./command_generators.py):
```
sudo -u postgres psql
postgres=# CREATE ROLE {username} LOGIN PASSWORD '{password}';
postgres=# CREATE DATABASE {database} WITH OWNER = {username};
postgres=# GRANT ALL ON SCHEMA public TO {username}; #needed for flyway
```
In order to connect to the database with the new user, authentication must first be configured. This can by done by modifying ```/etc/postgresql/{version}/main/pg_hba.conf```. For local use, the following entry can be added:
```
local {database name} {username} md5
```
Note that docker containers do not use local connections. To add an entry for another device:
```
host {database name} {username} {ip}/0 md5
```
For non-local use, postgres needs to be configured to listen for other addresses. This can be done by changing ```listen_addresses``` in ```/etc/postgresql/{version}/main/postgresql.conf```.
Confirm that the login works:
```
psql -U {username} {database name}
```
Now, the database connection string needs to be configured. This is a [libpg connection string](https://www.postgresql.org/docs/current/libpq-connect.html#LIBPQ-CONNSTRING). This needs to be configured on all machines running the control or worker process:
```
export USBIPICE_DATABASE='host={ip} port=5432 dbname={database name} user={username} password={password}
```
Confirm that the connection string works:
```
psql -d "$USBIPICE_DATABASE"
```
Note that you have to be careful when passing the connection string around, as it may contain spaces.

Flyway is used in order to apply migrations. Start by installing [Flyway](https://documentation.red-gate.com/fd/command-line-277579359.html). Try running flyway:
```
flyway
```
Flyway ships with its own java runtime, which may be compiled for the wrong architecture. If you encounter an exec format error, ensure you have a separate java runtime installed and delete the ```flyway-{version}/jre/bin/java``` file. Now, Flyway needs to be configured. The configuration file is located at ```flyway-{version}/conf/flyway.toml```. An example is provided by Flyway at ```flyway-{version}/conf/flyway.toml```. In addition, here is a configuration that works with the project:
```
[flyway]
locations = ["filesystem:migrations"]
cleanDisabled = false # optional
[environments.default]
url = "jdbc:postgresql://localhost:5432/{database}"
user = ""
password = ""
```
The ```flyway.cleanDisabled``` setting is optional and enables the use of the ```flyway clean``` command. This essentially drops all of the objects in the database and is useful during development. In order to run the migrations:
```
cd src/usbipice/control/flyway && flyway migrate
```
This can also be done with the ```database-rebuild``` vscode task. Note that in addition to running the migrations, it also runs clean beforehand.


### Building Firmware
Note that this is **not required to run or build images. If you are going to only use Docker, you may skip this step.**. If not already installed, install the [pico-sdk](https://github.com/raspberrypi/pico-sdk) and [pico-ice-sdk](https://github.com/tinyvision-ai-inc/pico-ice-sdk). Make sure to run ```git submodule update --init``` in the pico-ice-sdk repo. Commands:

```
git clone https://github.com/tinyvision-ai-inc/pico-ice-sdk.git
cd pico-ice-sdk
git submodule update --init --recursive
```

```
git clone https://github.com/raspberrypi/pico-sdk.git
cd pico-sdk
git submodule update --init --recursive
```

Create symlinks for the sdks in the firmware directory:
```
ln -s [full_path]/pico-sdk pico-sdk
ls -s [full_path]/pico-ice-sdk pico-ice-sdk
```

Run build.sh in this directory, or use the ```build-firmware``` task:
```
cd src/usbipice/worker/firmware
chmod +x build.sh
./build.sh
```

### Configuration
For the control server:
| Environment Variable | Description | Default |
|----------------------|-------------|---------|
|USBIPICE_DATABASE|[psycopg connection string](https://www.postgresql.org/docs/current/libpq-connect.html#LIBPQ-CONNSTRING)| required |
|USBIPICE_CONTROL_PORT| Port to run on | 8080|

Configuration for the worker can be done using environment variables or a toml file. Environment variables take precedence over the configuration file. Note that USBIPICE_DATABASE is not able to be provided through the configuration file. An example is [provided](./src/usbipice/worker/example_config.ini). The worker has to run with sudo in order to upload firmware to devices. This means that the environment variables need to be passed along:
```
sudo USBIPICE_DATABASE="$USBIPICE_DATABASE USBIPICE_WORKER_CONFIG=$USBIPICE_WORKER_CONFIG [command]
```
This may also be done with the -E flag, but this is not supported on all systems.
| Environment Variable | Description | Default |
|----------------------|-------------|---------|
| USBIPICE_WORKER_CONFIG | Path to config file | None|
|USBIPICE_DATABASE|[psycopg connection string](https://www.postgresql.org/docs/current/libpq-connect.html#LIBPQ-CONNSTRING)| required |
|USBIPICE_WORKER_NAME| Name of the worker for identification purposes. Must be unique.| required|
|USBIPICE_CONTROL_SERVER | Url to control server | required |
|USBIPICE_DEFAULT| Path for Ready state firmware | required |
|USBIPICE_PULSE_COUNT | Path for PulseCount state firmware | required |
|USBIPICE_WORKER_LOGS | Log location | None - required if running with uvicorn|
|USBIPICE_SERVER_PORT| Port to host server on | 8081|
|USBIPICE_VIRTUAL_IP| Ip for clients to reach worker with | First result from hostname -I |
|USBIPICE_VIRTUAL_PORT| Port for clients to reach worker with | 8081 |

### Preparing Devices
The picos need to be plugged into the worker and running firmware that has tinyusb loaded. The [rp2_hello_world](https://github.com/tinyvision-ai-inc/pico-ice-sdk/tree/main/examples/rp2_hello_world) example from the pico-ice-sdk works for this purpose.

### Running Control/Worker
*Only choose one option. Docker is quickest, debugging locally recommended is for testing/development. See end of section for verification information*

#### Docker
Note that the images can be built using the provided vscode tasks. Images are also available on [DockerHub](https://hub.docker.com/r/usbipiceproject/usbipice-worker/tags). Before building an image, ensure that firmware builds are up to date.

If it is not yet installed, install [Docker Engine](https://docs.docker.com/engine/install/). Follow the [post installation steps](https://docs.docker.com/engine/install/linux-postinstall/) so that you do not need to use sudo. Included below:
 ```
 sudo usermod -aG docker {linux-username}
 #new shell or log out and then login
 newgrp docker
 ```

Build the image. You may skip this step and the image will automatically download from DockerHub. If you are on an arm device, change the tag to arm.
```
docker build -f deploy/Dockerfile -t usbipiceproject/usbipice-worker:amd.
```
A compose file is included for running both the worker and control. This can also be done through the provided vscode tasks. If you are on an arm device, you will need to change the image tag in the compose file to arm.
```
docker compose -f deploy/compose.yml up
```

#### Debug Locally
Install iCEFARM module:
```
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```
Debug configurations are available in the [launch.json](./.vscode/launch.json). The control can be run with ```control```. The worker requires sudo in order to upload firmware to the devices. Note that sudo changes the environment variables, so it is recommended to use a configuration file. The command can also be generated using the [command generators](./command_generators.py):
```
sudo USBIPICE_DATABASE="$USBIPICE_DATABASE" USBIPICE_WORKER_CONFIG="$USBIPICE_WORKER_CONFIG" .venv/bin/worker
```

#### Uvicorn Locally
Not recommended to use this, but here for the sake of completeness. The docker compose stack runs with uvicorn, so it is usually better to use that.
Install iCEFARM module:
```
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```
Uvicorn does not access environment variables. Variables can be passed with a [.env](https://github.com/theskumar/python-dotenv) file. The provided ```.uvicorn_env_bridge``` file passes iCEFARM related environment variables to uvicorn.
Control:
```
uvicorn usbipice.control.app:run_uvicorn --env-file .uvicorn_env_bridge --factory --host 0.0.0.0 --port 8080
```
Worker:
```
sudo USBIPICE_DATABASE="$USBIPICE_DATABASE" USBIPICE_WORKER_CONFIG=$USBIPICE_WORKER_CONFIG .venv/bin/uvicorn usbipice.worker.app:run_uvicorn --env-file .uvicorn_env_bridge --factory --host 0.0.0.0 --port 8081
```

### Verification
If there is unexpected behavior, check the [troubleshooting](#troubleshooting) section.
Approximate output from Worker:
```
[DeviceManager] Scanning for devices
[DeviceManager] [{SERIAL}] [FlashState] state is now FlashState
[DeviceManager] [{SERIAL}] [FlashState] sending bootloader signal to /dev/ttyACM0
[DeviceManager] [{SERIAL}] [TestState] state is now TestState
[DeviceManager] [{SERIAL}] [ReadyState] state is now ReadyState
[DeviceManager] Finished scan
```
Note that the order and dev files will vary. In some situations there may be multiple bootloader signals sent. Confirm that the device has been added to the database:
```
psql -d "$USBIPICE_DATABASE" -c 'select * from device;'
```
Expected output:
```
| serialid |    worker     | devicestatus |
|----------|---------------|--------------|
| {serial} | {worker name} |   available  |
```

The control does not have any immediate output. It will send periodic heartbeats to workers:
```
[Control] [Heartbeat] heartbeat success for debug-worker
```
In addition, it will receive logs from the workers. Note that log entries that happened before the control was started will not be displayed:
```
[debug-worker@1] [DeviceManager] Scanning for devices
[debug-worker@1] [DeviceManager] [{serial}] [FlashState] state is now FlashState
[debug-worker@1] [DeviceManager] [{serial}] [FlashState] sending bootloader signal to /dev/ttyACM0
```

## Running Client
The client for pulse count experiments is provided in [usbipice.client.drivers.pulse_count](./src/usbipice/client/drivers/pulse_count/PulseCountClient.py). An [example usage](./examples/pulse_count_driver/main.py) is provided. All other examples use usbip. The client library can be installed separately using pip without having to clone the repo:
```
pip install git+https://github.com/heiljj/usbip-ice.git
```
Note that this does not include examples.


## Workflow
Vscode debug configurations are available for both the worker and control. There is also an assortment of vscode tasks. Notably, ```docker-build-all``` builds both firmware and the docker image. The ```compose-rebuild``` task builds the firmware and image, clears the database, and deploys/redeploys the compose stack. The task ```database-clear``` removes workers from the database and is useful to fix invalid worker/device states. This can also be done with ```psql -d "$USBIPICE_DATABASE" -c 'delete from worker;```.

## Troubleshooting
*Generally, most things can be fixed by clearing the database*
### Worker fails to run, unable to add to database because it already exists
Clear the database, start the worker again.
### Device goes to BrokenState
This can happen occasionally even if everything is set up correctly. Clear the database, unplug and plug the device back in, then restart the worker. If it happens again, it's probably a configuration error. Ensure that you are running with sudo, as this is needed in order to upload the firmware. Ensure that the firmware has been properly built and that the configuration points to the correct path. If this has been done correctly, try manually flashing to the device.
```
sudo picocom --baud 1200 /dev/ttyACM0
sudo mount /dev/sda1 [mount_location]
sudo cp [firmware_location] [mount_location]
sudo umount [mount_location]
```
Note that you will have to wait between commands for the device to respond, and that the exact device path may be different.

### Client fails to reserve device
Ensure that the control server is actually accessible. Check whether the device is listed as 'available' under the database Device table. If the device is stuck at reserved, clear the database and start the worker again.

## Usbip Information
Usbip allows devices to be remotely controlled as through they were physically connected. This can be useful, but it is significantly slower than defining specific device behavior. It also requires significantly more setup. Usbip does not provide any means of authentication; any machine that can access the port is able to connect to the remove devices. The workers and client need to have usbip installed and enabled. This is through a kernel specific package.
```
sudo apt install "linux-tools-$(uname -r)"
sudo modprobe usbip_core
sudo modprobe usbip_host
sudo modprobe vhci_hcd
```
Note that the modules will have to be reloaded after the device reboots. In addition, a usbip server needs to be started on the workers.
```
sudo usbipd -D
```

When running through a container, the image must be relatively similar to that of the host device. For example, the image ubuntu:noble-20240432 works with ubuntu noble 24.04. The kernel version must also match. The usbip linux-tools package mentioned earlier must be installed on both the host and the container, while the modules and usbip server must be started on the host. In order to run usbip from the container, the container needs to run with the volume mount ```/lib/modules:/lib/modules```. It does not appear that running usbip in an unprivileged container is possible, as the container also accesses files in ```/sys```.

A iCEFARM client for reserving devices with the UsbipState is available in the [client library](./src/usbipice/client/drivers/usbip/UsbipClient.py).
