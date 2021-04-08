#!/usr/bin/python
#encoding:utf-8

import time
import board
import busio
import adafruit_ads1x15.ads1015 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
import configparser
from os import path

# This is the path to the configuration file
MOISTURE01_CONFIG_FILE = "/home/pi/moisture_calibration0.ini"

# Create the I2C bus
i2c = busio.I2C(board.SCL, board.SDA)

# Create the ADC object using the I2C bus
ads = ADS.ADS1015(i2c)
ads.gain = 1

# Create single-ended input on channel 0
moistureSensor = AnalogIn(ads, ADS.P0)

# Our starting readings (defaults)
maxVal = 20000
minVal = 10000
 
# get thresholds from config file
rpgConfig = configparser.ConfigParser()  # Create ConfigParser
if path.exists(MOISTURE01_CONFIG_FILE):    # if ini file exists...
    rpgConfig.read(MOISTURE01_CONFIG_FILE) # Load data from the file
    # Note: if ini file doesn't exist, this does not throw an error
 
if 'moisture_sensor_0' in rpgConfig:
    # Create a section object to hold part of the ini file
    moistureSection = rpgConfig['moisture_sensor_0']
 
    # Set variables from the configparser.
    # Note that all ini file values are treated as strings, so they 
    # need to be converted when reading or saving
    maxVal = int(moistureSection['dryVal'])
    minVal = int(moistureSection['wetVal'])
else:
    # add the moisture_sensor_1 section if it doesn't exist
    # and save the ini file
    rpgConfig.add_section("moisture_sensor_0")
    moistureSection = rpgConfig['moisture_sensor_0']
    moistureSection["dryVal"] = str(maxVal)
    moistureSection["wetVal"] = str(minVal)
    with open(MOISTURE01_CONFIG_FILE, 'w') as configfile:
        rpgConfig.write(configfile)
 
# Loop, checking to see if the value read is outside of 
# the existing thresholds
try:
    while True:
        foundNewVal = False
        val = moistureSensor.value
 
        if (val > maxVal):
            foundNewVal = True
            maxVal = val
            moistureSection['dryVal'] = str(maxVal)
            print('***** New Maximum Value: ', maxVal)
 
        if (val < minVal):
            foundNewVal = True
            minVal = val
            moistureSection['wetVal'] = str(minVal)
            print('***** New Minimum Value: ', minVal)
 
        if (foundNewVal):  # Update the ini file
            with open(MOISTURE01_CONFIG_FILE, 'w') as configfile:
                rpgConfig.write(configfile)
 
        print("Reading:", val, " Sensor Range:", minVal, "-", maxVal)
        time.sleep(1)
 
except KeyboardInterrupt:    
    pass  # Don't do anything special if user typed Ctrl-C
 
except Exception as ex:
    # Handle other exceptions
    print(type(ex))
    print(ex.args)
    print(ex)
 
finally:
    print("\nFinal Range: ", minVal, " - ", maxVal)