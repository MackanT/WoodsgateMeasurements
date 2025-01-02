import sqlite3
import os
from datetime import datetime, timedelta
import time

import busio
import digitalio
import board
import adafruit_mcp3xxx.mcp3008 as MCP
from adafruit_mcp3xxx.analog_in import AnalogIn


database_name = '5400_data.db'


## Setup MCP3008
spi = busio.SPI(clock=board.SCK, MISO=board.MISO, MOSI=board.MOSI)
cs = digitalio.DigitalInOut(board.D22)
mcp = MCP.MCP3008(spi, cs)
input_channel = AnalogIn(mcp, MCP.P1)

## User Inputs
save_time = 120	# [s - Approximate time between saves]

resistor_value = 96.75	# [Ohm - Resistance value of resistor on MCP-board] Measured to 106.75, but calibrated to 116.6
tank_height = 3.11	# [m - Tank height - nozzle height - offset]
mA_min = 4.0 	# [mA - Simulate Device at 0m, average over 1-2min] # Old: 3.980
mA_max = 20.0	# [mA - Simulate Device at full tank, average over 1-2 min] # Old: 19.928

## Startup Text
print("\n --- Starting Woodsgate 5300 Measurements --- \n Time Between Saves: \t {} s \n Resitor Value: \t {} Ohm \n Tank Height: \t\t {} m \n Minimum Measured mA: \t {} mA \n Maximum Measured: mA \t {} mA".format(save_time, resistor_value, tank_height, mA_min, mA_max))
print(" --------------------------------------------")


def open_database(file_name:str) -> sqlite3.Connection:

  if os.path.exists(file_name):
    print(f"Opening file {file_name}")
    conn = sqlite3.connect(file_name)
  else:
    print(f"Cannot find databse, initializing file: {file_name}")
    conn = sqlite3.connect(file_name)

    ## Data
    conn.execute("""
    create table if not exists data (
       data_id integer primary key autoincrement
      ,time datetime
      ,level float
      ,volume float
    )
    """)
    print("Created table 'data' successfully!")
    conn.commit()

  return conn

def insert_row(level, volume):

  now = datetime.now()
  date_time = now.strftime('%Y-%m-%d %H:%M:%S')

  cursor = conn.execute("""
        select level, volume
        from data
        order by data_id desc
        limit 1
    """)
  data = cursor.fetchall()

  # First measurement reading!
  if len(data) == 0:
      conn.execute("insert into data (time, level, volume) values (?, ?, ?)",
                    (date_time, level, volume))
      conn.commit()
      print(f"First measurement detected. Time: {date_time}, Level: {level}")

  else:
    data = data[0]
    lvl, vol = data

    if level != lvl:
      pre_now = now - timedelta(minutes=int((save_time/120)))
      pre_date_time = pre_now.strftime('%Y-%m-%d %H:%M:%S')

      # "End" previous constant-meas
      conn.execute("insert into data (time, level, volume) values (?, ?, ?)",
                    (pre_date_time, lvl, vol))

      # "Add" new measurement
      conn.execute("insert into data (time, level, volume) values (?, ?, ?)",
                    (date_time, level, volume))
      conn.commit()

      print(f"New measurement detected. Time: {date_time}, Level: {level}")



def measure_mA():
  measured_voltage = input_channel.voltage
  measured_mA = measured_voltage/resistor_value*1000
  return round(measured_mA,3)

conn = open_database(database_name)

data = []
while True:

  mA = measure_mA()
  data.append(mA)

  if len(data) == save_time:

    data_count= 0
    for i in range(save_time):
      if data[i] != 0:
        data_count += 1
    avg = sum(data) / data_count

    data = []
    measured_lvl = (avg-mA_min)/((mA_max-mA_min)/tank_height)
    current_level = round(measured_lvl, 3)

    # Calculate Volume - 3.41 from uneven base = 0.35*3.855*5.06 / 2 - 3.866x5.06 is tank size
    current_volume = round(3.41 + (measured_lvl)*3.855*5.06, 3)
    insert_row(current_level, current_volume)

  time.sleep(1)
