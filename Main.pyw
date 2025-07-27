import subprocess
import os
import socket
import ipaddress
import yaml
from pathlib import Path

import argparse

# Create the parser
parser = argparse.ArgumentParser(description="Raspberry Pi data transfer tool")

# Add arguments
parser.add_argument("--db_name", type=str, help="Name of stored db on local PC")
parser.add_argument(
    "--local_ip", type=str, help="Local IP-address of RPI on home-network"
)
parser.add_argument(
    "--external_ip", type=str, help="External IP-address of RPI via Tailscale"
)
parser.add_argument("--local_port", type=int, help="Local Port of RPI on home-network")
parser.add_argument("--rpi_user", type=str, help="Username on RPI")
parser.add_argument(
    "--config", type=str, default="config.yml", help="Name of utilized config file"
)

# Parse arguments
args = parser.parse_args()

# Generate config-file
default_config = {
    "rpi_user": "your_rpi_username_here",
    "local_ip": "192.168.x.x",
    "external_ip": "xxx.xxx.xxx.xxx",
    "local_port": 22,
    "db_name": "data.db",
}


def create_blank_config(path="config.yml"):
    if Path(path).exists():
        return

    with open(path, "w") as f:
        yaml.dump(default_config, f, sort_keys=False)
        print(f"Template config created at '{path}'")


use_config = False
for key, value in vars(args).items():
    if value is None and key != "config":
        use_config = True
        print(f"❗ Argument '{key}' is missing")

config_path = args.config
if use_config:
    if not config_path:
        print(
            "No config path specified and no data entered as arguments. Quitting early!"
        )
        exit(1)
    else:
        print(
            f"Some arguments were not specified, attempting to use values stored in config file: {config_path}"
        )

if os.path.exists(config_path):
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
else:
    print(
        f"{config_path} not found, a new blank file is being generated. Please fill it out!"
    )
    create_blank_config(args.config)
    exit(1)


def fetch_value(name):
    val = getattr(args, name) or config.get(name, None)
    if val is None:
        print(f"Found no valid value for {name}, exiting program...")
        exit(1)
    print(f"-{name}: {val}")
    return val


db_name = fetch_value("db_name")
local_ip = fetch_value("local_ip")
local_port = fetch_value("local_port")
external_ip = fetch_value("external_ip")
rpi_user = fetch_value("rpi_user")


def get_local_ip():
    """Get the local IP of the current machine."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't actually connect, just forces IP selection
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
    finally:
        s.close()
    return local_ip


def is_same_network(my_ip, rpi_local_ip):
    """Check if both IPs are on the same /24 subnet."""
    my_net = ipaddress.ip_network(my_ip + "/24", strict=False)
    return ipaddress.ip_address(rpi_local_ip) in my_net


# Detect and choose target IP
my_ip = get_local_ip()
if is_same_network(my_ip, local_ip):
    print("User is on same network as RPI, using Local IP.")
    ip = local_ip
else:
    print("User is not on same network as RPI, using Tailscale IP.")
    ip = external_ip


if not Path.home().joinpath(".ssh", "id_ed25519").exists():
    print(
        "SSH key not found. Please generate one with `ssh-keygen` and add it to your RPi, see readme for more info"
    )
    exit(1)

cmd = f"scp -P {str(local_port)} -o StrictHostKeyChecking=no {rpi_user}@{ip}:/home/admin/Documents/5400_data.db {db_name}"
output_lines = []

print("Starting download.... This may take a few minutes depending on connection!")
with subprocess.Popen(
    cmd,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1,
    universal_newlines=True,
) as p:
    for line in p.stdout:
        print(line, end="")
        output_lines.append(line)

    p.wait()

output = "".join(output_lines)
return_code = p.returncode

if return_code != 0:
    print("Command failed!")
    print(output)
else:
    print("Success!")
