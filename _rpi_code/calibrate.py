import busio
import digitalio
import board
import time
import datetime
import adafruit_mcp3xxx.mcp3008 as MCP

from adafruit_mcp3xxx.analog_in import AnalogIn


## Setup MCP3008
spi = busio.SPI(clock=board.SCK, MISO=board.MISO, MOSI=board.MOSI)
cs = digitalio.DigitalInOut(board.D22)
mcp = MCP.MCP3008(spi, cs)
input_channel = AnalogIn(mcp, MCP.P1)

## Startup Text
print(" --- Starting WoodsGate Calibration Software --- ")
print(" -----------------------------------------------")

## Variables
resistor_value = 96.75
time_steps = 1200
avg_time = int(time_steps/10)

dict = {}

def measure_amperage():
  measured_voltage = input_channel.voltage
  measured_mA = measured_voltage/resistor_value*1000
  return round(measured_mA,3)

for i in range(time_steps):

  # Look at occurence of values. Doing average does not seem to be as good due to fluctuations in the data
  mA = measure_amperage()
  if mA in dict:
    dict[mA] += 1
  else:
    dict[mA] = 1
#  print(mA)
  time.sleep(1)

  if i%avg_time == 0:
    print("Remaining time: {:.2f} minutes, current average: {}".format((time_steps-i)/60, max(dict, key=dict.get)))

print("Final Average: {}".format(max(dict, key=dict.get)))
print("Top 5 Measurments: ")
res = sorted(dict.items(), key=lambda x: x[1],reverse = True)[:5]
print(res)
