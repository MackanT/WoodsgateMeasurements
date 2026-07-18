import sqlite3
import os
from datetime import datetime, timedelta
import time
import statistics
import smbus2
import struct


database_name = '/shared_data/data.db'


####################
### Device Setup ###
####################
# ADS1115 configuration
ADS1115_ADDRESS = 0x48  # Default I2C address
ADS1115_REG_CONFIG = 0x01
ADS1115_REG_CONVERT = 0x00

# Configuration for continuous conversion, ±4.096V range, 128 SPS
ADS1115_CONFIG = 0x8483  # Single-shot, A0, ±4.096V, 128SPS

# Persistent I2C bus handle, reused across reads instead of being opened every
# call. Previously a new smbus2.SMBus(1) was opened on every read and never
# closed, leaking a file descriptor for /dev/i2c-1 each second until the
# process hit its open-file limit ("Too many open files"), after which every
# read failed silently (caught below) and no further data was ever written.
_bus: smbus2.SMBus | None = None


def _get_bus() -> smbus2.SMBus:
    global _bus
    if _bus is None:
        _bus = smbus2.SMBus(1)
    return _bus


def read_adc_voltage():
    """Read voltage from ADS1115 A0 pin"""
    global _bus
    try:
        bus = _get_bus()
        # Write config to start conversion
        bus.write_i2c_block_data(ADS1115_ADDRESS, ADS1115_REG_CONFIG,
                                [ADS1115_CONFIG >> 8, ADS1115_CONFIG & 0xFF])

        # Wait for conversion (8ms for 128 SPS)
        time.sleep(0.01)

        # Read conversion result
        data = bus.read_i2c_block_data(ADS1115_ADDRESS, ADS1115_REG_CONVERT, 2)

        # Convert to voltage (16-bit signed, ±4.096V range)
        raw_adc = struct.unpack('>h', bytes(data))[0]
        voltage = raw_adc * 4.096 / 32767.0

        return voltage
    except Exception as e:
        print(f"Error reading ADC: {e}")
        # The bus/connection may be in a bad state (e.g. I2C bus error) -
        # close and drop it so the next read reopens a fresh handle instead
        # of retrying forever on a broken one.
        if _bus is not None:
            try:
                _bus.close()
            except Exception:
                pass
            _bus = None
        return None

##################
### User Input ###
##################

save_time = 120 # [s - Approximate time between saves]
v_min = 0 # Measured voltage at 4mA current
v_max = 4.089 # Measured voltage at 20mA current
tank_height = 3.11 # [m - Tank height - nozzle height - offset]

###################
### Actual Code ###
###################
print("\n --- Starting Woodsgate 5400 Measurements --- \n Time Between Saves: \t {} s \n Tank Height: \t\t {} m \n Minimum Measured voltage at 4mA: \t {} V \n Maximum Measured voltage at 20mA: \t {} V".format(save_time, tank_height, v_min, v_max))
print(" --------------------------------------------")


def open_database(file_name:str) -> sqlite3.Connection:

  # Ensure directory exists
  os.makedirs(os.path.dirname(file_name), exist_ok=True)

  db_existed = os.path.exists(file_name)
  print(f"Opening file {file_name}" if db_existed else f"Cannot find database, initializing file: {file_name}")

  conn = sqlite3.connect(file_name)
  conn.execute("""
  create table if not exists data (
     data_id integer primary key autoincrement
    ,time datetime
    ,level float
    ,volume float
  )
  """)
  conn.commit()

  return conn

def insert_row(conn, level, volume):

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
      # Back-date the "end" of the previous level to one full sampling
      # window (save_time seconds) ago - the same window used to compute
      # the median above - instead of an unrelated, hardcoded offset.
      pre_now = now - timedelta(seconds=save_time)
      pre_date_time = pre_now.strftime('%Y-%m-%d %H:%M:%S')

      # "End" previous constant-meas
      conn.execute("insert into data (time, level, volume) values (?, ?, ?)",
                    (pre_date_time, lvl, vol))

      # "Add" new measurement
      conn.execute("insert into data (time, level, volume) values (?, ?, ?)",
                    (date_time, level, volume))
      conn.commit()

      print(f"New measurement detected. Time: {date_time}, Level: {level}")

def main():
    conn = open_database(database_name)

    data = []
    while True:
      try:
        voltage = read_adc_voltage()
        # Only add valid readings (filter out obvious errors)
        if voltage is not None and voltage > 0:
          data.append(voltage)

        if len(data) == save_time:
          
          median = statistics.median(data)
          print(f"Median voltage: {median}V")

          data = []
          
          lvl = (median - v_min) / ( (v_max - v_min) / tank_height)
          rounded_lvl = round(lvl, 3)

          volume = 3.41 + lvl * 3.855 * 5.06 # Estimated constants for tank shape
          rounded_volume = round(volume, 3)

          insert_row(conn, rounded_lvl, rounded_volume)

      except Exception as e:
        print(f"Error reading sensor: {e}")
        # Wait longer on error to avoid flooding logs
        time.sleep(5)
        continue
      
      time.sleep(1)

if __name__ == "__main__":
    main()
