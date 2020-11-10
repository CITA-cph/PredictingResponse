#IMPORTS
#general
from __future__ import print_function

from datetime import datetime
import pickle
import io
import shutil
import os
import json
#camera
from picamera.array import PiRGBArray
from picamera import PiCamera
import cv2
#influxdb
import requests
#import local modules
import RPi.GPIO as GPIO  # import GPIO
from hx711 import HX711  # import the class HX711

#FUNCTIONS
#data formatting to influxDB
def date_now():
    today = datetime.now().strftime("%Y-%m-%d")
    today = str(today)
    return (today)

def time_now():
    now = datetime.now().strftime("%H:%M:%S")
    now = str(now)
    print(now)
    return (now)

def get_timestamp():
    timestamp = str(int(datetime.now().timestamp() * 1000))
    return timestamp

#writing data to InfluxDB
def get_line_protocol(measurementName, tagKey1, tagValue1, tagKey2, tagvalue2, fieldKey, fieldValue, time):
    line = "{},{}={},{}={} {}={} {}"
    return line.format(measurementName, tagKey1, tagValue1, tagKey2, tagvalue2, fieldKey, fieldValue, time)

def send_line(line):
    try:
        url = "{}api/v2/write?org={}&bucket={}&precision={}".format(influx_url, organization, bucket, precision)
        headers = {"Authorization": "Token {}".format(influx_token)}
        r = requests.post(url, data=line, headers=headers)
        print(line)
    except:
        print("oops")

#INITIALIZE
#Load init.json
with open('init.json') as f:
    data = f.read()
    init_dic = json.loads(data)

# Variables related to using the REST API
influx_url = init_dic['influx_url']
influx_token = init_dic['influx_token']
organization = init_dic['organization']
bucket = init_dic['bucket']
precision = init_dic['precision']

#Tagging variables
measurementName = init_dic['measurement_name']
tagKeyA = "State"
tagValueA = init_dic['state']
tagKeyB = "Measure_type"
#camera
tagValue_m1 = init_dic['measurement1_type']
fieldKey_m1 = init_dic['measurement1_fieldKey']
#weight
tagValue_m2 = init_dic['measurement2_type']
fieldKey_m2 = init_dic['measurement2_fieldKey']
weightTare = init_dic['weightTare']
#moisture // NOT IMPLEMENTED YET
tagValue_m3 = init_dic['measurement3_type']
fieldKey_m3 = init_dic['measurement3_fieldKey']
#UPLOAD
uploadToInfluxDB = init_dic['upload']

#Define function that return the field value from every sensor
def prepWeightMeasure():
    "measures the weight of the sample"

    try:
        GPIO.setmode(GPIO.BCM)  # set GPIO pin mode to BCM numbering
        # Create an object hx which represents your real hx711 chip
        # Required input parameters are only 'dout_pin' and 'pd_sck_pin'
        hx = HX711(dout_pin=5, pd_sck_pin=6)
        # Check if we have swap file. If yes that suggest that the program was not
        # terminated proprly (power failure). We load the latest state.
        swap_file_name = 'swap_file.swp'
        if os.path.isfile(swap_file_name):
            with open(swap_file_name, 'rb') as swap_file:
                hx = pickle.load(swap_file)
                # now we loaded the state before the Pi restarted.
        else:
            # measure tare and save the value as offset for current channel
            # and gain selected. That means channel A and gain 128
            err = hx.zero()
            # check if successful
            if err:
                raise ValueError('Tare is unsuccessful.')

            reading = hx.get_raw_data_mean()
            if reading:  # always check if you get correct value or only False
                # now the value is close to 0
                print('Data subtracted by offset but still not converted to units:',
                      reading)
            else:
                print('invalid data', reading)

            # In order to calculate the conversion ratio to some units, in my case I want grams,
            # you must have known weight.
            input('Put known weight on the scale and then press Enter')
            reading = hx.get_data_mean()
            if reading:
                print('Mean value from HX711 subtracted by offset:', reading)
                known_weight_grams = input(
                    'Write how many grams it was and press Enter: ')
                try:
                    value = float(known_weight_grams)
                    print(value, 'grams')
                except ValueError:
                    print('Expected integer or float and I have got:',
                          known_weight_grams)

                # set scale ratio for particular channel and gain which is
                # used to calculate the conversion to units. Required argument is only
                # scale ratio. Without arguments 'channel' and 'gain_A' it sets
                # the ratio for current channel and gain.
                ratio = reading / value  # calculate the ratio for channel A and gain 128
                hx.set_scale_ratio(ratio)  # set ratio for current channel
                print('Ratio is set.')
            else:
                raise ValueError(
                    'Cannot calculate mean value. Try debug mode. Variable reading:',
                    reading)

            # This is how you can save the ratio and offset in order to load it later.
            # If Raspberry Pi unexpectedly powers down, load the settings.
            print('Saving the HX711 state to swap file on persistant memory')
            with open(swap_file_name, 'wb') as swap_file:
                pickle.dump(hx, swap_file)
                swap_file.flush()
                os.fsync(swap_file.fileno())
                # you have to flush, fsynch and close the file all the time.
                # This will write the file to the drive. It is slow but safe.

        # Read data several times and return mean value
        # subtracted by offset and converted by scale ratio to
        # desired units. In my case in grams.
        # print("Now, I will read data in infinite loop. To exit press 'CTRL + C'")
        # input('Press Enter to begin reading')
        # while True:
        weight = hx.get_weight_mean(50) - weightTare
        print(weight, 'g without weight mesh')

        return weight

    except (KeyboardInterrupt, SystemExit):
        print('Bye :)')

    finally:
        GPIO.cleanup()

def prepCameraShot():
    "takes a picture"
    camera = PiCamera()
    rawCapture = PiRGBArray(camera)

    camera.capture(rawCapture, format='rgb')
    image = rawCapture.array
    image = cv2.cvtColor(image,cv2.COLOR_BGR2RGB)

    return image


if uploadToInfluxDB == True:
    #upload data to influx
    weightMes = prepWeightMeasure()
    imgMes = prepCameraShot()
    timestamp = get_timestamp()

    influx_weight = get_line_protocol(measurementName, tagKeyA, tagValueA, tagKeyB, tagValue_m2, fieldKey_m2, weightMes, timestamp)
    influx_img = get_line_protocol(measurementName, tagKeyA, tagValueA, tagKeyB, tagValue_m1, fieldKey_m1, 1, timestamp)

    influx_lines = [influx_weight,influx_img]

    for line in influx_lines:
        send_line(line)
    print('Upload to Influx Done')

    pathExp = '/home/pi/mnt/gdrive/2020_Establishing_Methods_Phase/%s' % (measurementName)

    if not os.path.exists(pathExp):
        os.makedirs(pathExp)

    #upload image to google drive
    now = datetime.now().strftime("%Y-%m-%d_%H-%M")
    print(now)
    imName = "{}_{}.jpg".format(measurementName, now)
    imLoc = '{}/{}'.format(pathExp, imName)
    print(imLoc)
    cv2.imwrite(imLoc, imgMes)
    print("image uploaded to gdrive")






