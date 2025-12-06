import subprocess
import os

# this is probably be the worst
# thing i've written

# swarm doesn't allow privileged mode
# eventually this needs to be moved to kubernetes
# for now this is easier

SSH_HOSTS = []

IMAGE_REPO = os.environ.get("DOCKER_IMAGE_REPO")
USBIPICE_DATABASE = os.environ.get("USBIPICE_DATABASE")
if not IMAGE_REPO or not USBIPICE_DATABASE:
    raise Exception("Configuration error")

hoststr = ",".join(SSH_HOSTS)

# verify we can connect
subprocess.run(["pdsh", "-w", hoststr, "echo", "test"], check=True)

subprocess.run(["pdsh", "-w", hoststr, "eval", "docker stop $(docker ps -a -q)"])
subprocess.run(["pdsh", "-w", hoststr, "eval", "docker rm $(docker ps -a -q)"])

# subprocess.run(["pdsh", "-w", hoststr, "docker", "pull", IMAGE_REPO])

for host in SSH_HOSTS:
    subprocess.run(["pdsh", "-w", host, "docker", "run",
                    "--privileged",
                    "-v", "/dev:/dev",
                    "-v", "/lib/modules:/lib/modules",
                    "-v", "/tmp:/tmp",
                    "-v", "/run/udev:/run/udev:ro",
                    "--network=host",

                    "-d",

                    "-e",
                    f"USBIPICE_DATABASE='{USBIPICE_DATABASE}'",
                    "-e",
                    f"USBIPICE_WORKER_NAME='{host}'",

                    IMAGE_REPO,
                    ".venv/bin/worker",
                    "-c",
                    "src/usbipice/worker/example_config.ini"])
