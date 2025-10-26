# WoodsgateMeasurements

Complete tank level monitoring system for Raspberry Pi with data collection and web interface.

Originally designed for a Rosemount 5300 probe, now upgraded to use ADS1115 ADC with Docker containerization.

## Hardware Setup

### Original Setup
Measurement sw for a Rosemount 5300 probe in a water tank using a RPI with MCP3008 ADC measuring mA over GPIO

Actual Measurement Setup
![IMG_20230714_162212](https://github.com/user-attachments/assets/19feca03-0a48-449b-9eea-175432623040)

Indoor Wiring (Cables running underground from pump to building) 
-ADC converter
![IMG_20230714_084652](https://github.com/user-attachments/assets/bd53519a-2ea2-48a6-95b9-3e02ef64b8d2)
-RPI connection
![IMG_20230714_084659](https://github.com/user-attachments/assets/3243b284-c612-42c8-829f-b3a5cebb1e7f)

### Current Setup
- **ADC**: ADS1115 (I2C) - Higher resolution than MCP3008
- **Sensor**: Rosemount 5300 probe (4-20mA output)  
- **Platform**: Docker containers on Raspberry Pi
- **Database**: SQLite with shared access
- **Interface**: Web GUI for monitoring

## Project Structure
```
WoodsgateMeasurements/
├── manage.sh                    # Master management script  
├── docker-compose.yaml          # Orchestrates both services
├── data.db                      # Shared SQLite database
├── webgui/                      # Web interface service
│   ├── src/webgui/             # Web app source code
│   ├── Dockerfile              # Web app container
│   ├── pyproject.toml          # Web app dependencies
│   └── woodsgate_collector/    # Data collection service
│       ├── data_collector.py   # Main collector script
│       ├── Dockerfile          # Collector container  
│       └── pyproject.toml      # Collector dependencies
└── _rpi_code/                  # Legacy scripts
```

## Quick Start

### Prerequisites
- Raspberry Pi with I2C enabled (`sudo raspi-config`)
- Docker and Docker Compose installed
- ADS1115 connected to I2C pins (SDA, SCL, 3.3V, GND)

### Usage
```bash
# Navigate to project root
cd /home/admin/repos/WoodsgateMeasurements/

# Build and start both services
./manage.sh build
./manage.sh start

# View logs
./manage.sh logs

# Access web interface at: http://your-pi-ip:8080

# Stop everything
./manage.sh stop
```

## Services

### 1. Data Collector (`woodsgate-collector`)
- Reads sensor data via I2C (ADS1115)
- Stores measurements in SQLite database
- Auto-restarts on crashes

### 2. Web GUI (`webgui`)  
- Web interface on port 8080
- Real-time data visualization
- Read-only database access

## Management Commands
- `./manage.sh start` - Start both services
- `./manage.sh logs` - View all logs
- `./manage.sh collector logs` - Collector logs only
- `./manage.sh webgui logs` - Web GUI logs only
- `./manage.sh status` - Show service status


### Setup Keyless-SSH
- Generate a ssh-pair on your local pc: ´ssh-keygen -t ed25519 -C "your_email@example.com"´
- To connect to the tailscale network, contact me (must be done before next step if connecting from different IP)
- Copy over keygen to rpi: ´cat ~/.ssh/id_ed25519.pub | ssh -p 22 {rpi-user}@{rpi local_ip or tailscale_ip} "mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"´ **NOTE**: different IP's are used depending on if your pc is on the same local network as the RPI or not.
- Upon running above command you will be promtped one last time to enter the password to the RPI, afterwards you can access the rpi without password
