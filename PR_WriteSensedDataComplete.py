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
#moisture
import time
import board
import busio
import adafruit_ads1x15.ads1015 as ADS
import configparser
from adafruit_ads1x15.analog_in import AnalogIn
from os import path
#thermal camera: flir lepton py library from https://github.com/groupgets/pylepton
import sys
import numpy as np
import cv2
from pylepton.Lepton3 import Lepton3
from PIL import Image
#influxdb
import requests
#import local modules
import RPi.GPIO as GPIO  # import GPIO
from hx711 import HX711  # import the class HX711 for weight reading

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
with open('/home/pi/PR_workflow/init.json') as f:
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
#moisture01
tagValue_m3 = init_dic['measurement3_type']
fieldKey_m3 = init_dic['measurement3_fieldKey']
#moisture02
tagValue_m4 = init_dic['measurement4_type']
fieldKey_m4 = init_dic['measurement4_fieldKey']
#thermal camera
tagValue_m5 = init_dic['measurement5_type']
fieldKey_m5 = init_dic['measurement5_fieldKey']
#thermal camera - min
tagValue_m6 = init_dic['measurement6_type']
fieldKey_m6 = init_dic['measurement6_fieldKey']
#thermal camera - max
tagValue_m7 = init_dic['measurement7_type']
fieldKey_m7 = init_dic['measurement7_fieldKey']
#UPLOAD
uploadToInfluxDB = init_dic['upload']

    
#Define function that return the field value from every sensor
def prepWeightMeasure():
    "measures the weight of the sample"

    try:
        GPIO.setmode(GPIO.BCM)  # set GPIO pin mode to BCM numbering
        # Create an object hx which represents your real hx711 chip
        # Required input parameters are only 'dout_pin' and 'pd_sck_pin'
        hx = HX711(dout_pin=20, pd_sck_pin=21)
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

    camera.capture(rawCapture, format='bgr')
    image = rawCapture.array
    image = cv2.cvtColor(image,cv2.COLOR_BGR2RGB)

    return image

#first calibrate moisture sensors using moisture_sensor_calibration.py
def prepMoisture01():
    MOISTURE01_CONFIG_FILE = "/home/pi/moisture_calibration0.ini"

    # Create the I2C bus
    i2c = busio.I2C(board.SCL, board.SDA)

    # Create the ADC object using the I2C bus
    ads = ADS.ADS1015(i2c)
    ads.gain = 1

    # Create single-ended input on channel 0
    chan00 = AnalogIn(ads, ADS.P0)

    #print("{:>5}\t{:>5}".format('raw', 'v'))

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
        minVal = int(moistureSection['wetVal'])
        maxVal = int(moistureSection['dryVal'])

    if True:
        rangeSize = 100.0
        factor = rangeSize / float(maxVal - minVal)
        moisture01 = float(chan00.value - minVal) * factor
        moisture01 = round(moisture01, 2)
        print("{:>5}\t{:>5.0f}\t{:>5.5f}".format(chan00.value, moisture01, chan00.voltage))
        #m1 = "{:>5.0f}".format(moisture01)
        #print(newValue)
        #time.sleep(1)
    
    return moisture01
    
     
        
def prepMoisture02():
    MOISTURE01_CONFIG_FILE = "/home/pi/moisture_calibration1.ini"

    # Create the I2C bus
    i2c = busio.I2C(board.SCL, board.SDA)

    # Create the ADC object using the I2C bus
    ads = ADS.ADS1015(i2c)
    ads.gain = 1

    # Create single-ended input on channel 0
    chan01 = AnalogIn(ads, ADS.P1)

    #print("{:>5}\t{:>5}".format('raw', 'v'))

    rpgConfig = configparser.ConfigParser()  # Create ConfigParser
    if path.exists(MOISTURE01_CONFIG_FILE):    # if ini file exists...
        rpgConfig.read(MOISTURE01_CONFIG_FILE) # Load data from the file
        # Note: if ini file doesn't exist, this does not throw an error
 
    if 'moisture_sensor_1' in rpgConfig:
        # Create a section object to hold part of the ini file
        moistureSection = rpgConfig['moisture_sensor_1']
 
        # Set variables from the configparser.
        # Note that all ini file values are treated as strings, so they 
        # need to be converted when reading or saving
        minVal = int(moistureSection['wetVal'])
        maxVal = int(moistureSection['dryVal'])

    if True:
        rangeSize = 100.0
        factor = rangeSize / float(maxVal - minVal)
        moisture02 = float(chan01.value - minVal) * factor
        moisture02 = round(moisture02)
        print("{:>5}\t{:>5.0f}\t{:>5.5f}".format(chan01.value, moisture02, chan01.voltage))
        #m2 = "{:>5.0f}".format(moisture02)
        
    return moisture02

#thermal camera

def ctok(val):
    return (val * 100.0) + 27315

min_c = ctok(10)
max_c = ctok(20)


def captureT(flip_v = False, device = "/dev/spidev0.0"):
      #prep for thermal capture
  with Lepton3(device) as l:
    a,_ = l.capture()
  if flip_v:
      cv2.flip(a,0,a)
  minVal, maxVal, minLoc, maxLoc = cv2.minMaxLoc(a)
  a[0][0] = min_c
  a[-1][-1] = max_c 
  cv2.normalize(a, a, 0, 65535, cv2.NORM_MINMAX)
  np.right_shift(a, 8, a)
  image_gray = np.uint8(a)
  img = cv2.applyColorMap(image_gray, cv2.COLORMAP_JET)
  return img


def prepThermalCameraShot():
    #take thermal image
    from optparse import OptionParser

    usage = "usage: %prog [options] output_file[.format]"
    parser = OptionParser(usage=usage)

    parser.add_option("-f", "--flip-vertical",
                    action="store_true", dest="flip_v", default=False,
                    help="flip the output image vertically")

    parser.add_option("-d", "--device",
                    dest="device", default="/dev/spidev0.0",
                    help="specify the spi device node (might be /dev/spidev0.1 on a newer device)")

    (options, args) = parser.parse_args()

    LeptonImage = captureT(flip_v = options.flip_v, device = options.device)
    return LeptonImage


def CombineImages(PiImage, LeptonImage):
    #CREATES MASKED FALSECOL IMG
  
    #overlay - since the two images from pi and thermocam have 2 different resolutions
         # the overlay is performed with a transformation called homography, which aligns corresponding points from one image to another
         # more info here: https://learnopencv.com/homography-examples-using-opencv-python-c/


    # Four corners of the sample in source image (thermal camera output)
    #- these are manually found in photoshop and placed here
    pts_src = np.array([[22, 69], [149, 79], [17, 95],[145, 100]])

    # Four corners of the sample in destination image (pi camera output)
    #- these are manually found in photoshop and placed here
    pts_dst = np.array([[288, 727],[1615, 805],[220, 996],[1582, 1030]])

    # Calculate Homography
    h, status = cv2.findHomography(pts_src, pts_dst)

    # Warp source image to destination based on homography
    im_out = cv2.warpPerspective(LeptonImage, h, (PiImage.shape[1],PiImage.shape[0]))
    alpha = 0.5
    beta = (1.0 - alpha)
    FalsecolorOverlay = cv2.addWeighted(PiImage, alpha, im_out, beta, 0.0)
    FalsecolorOverlay = Image.fromarray(FalsecolorOverlay, 'RGB')

    # creating a black mask for the background

    im_gray = cv2.cvtColor(PiImage, cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(im_gray, thresh=100, maxval=255, type=cv2.THRESH_BINARY)
    invert_mask = cv2.bitwise_not(mask)
    kernel = np.ones((6,6),np.uint8)
    maskFinal = cv2.dilate(invert_mask,kernel,iterations=2)
    maskFinal = Image.fromarray(maskFinal)

    #place the mask on top of the overlay image

    maskedOverlay = maskFinal.convert('RGB') 
    maskedOverlay.paste(FalsecolorOverlay, (0,0), maskFinal)

    #crop - find the right pixel to start the cropping from and size (manually performed in photoshop)

    upCornerX = 200
    upCornerY = 610
    dim1 = 1620
    dim2 = 1200
    thermalImage = maskedOverlay.crop((upCornerX,upCornerY,dim1,dim2))
    thermalImage = np.array(thermalImage)

    #save photo

    #cv2.imwrite('finaloutputSB1.png',thermalImage)

    return thermalImage

def prepThermalCameraValues(flip_v = False, device = "/dev/spidev0.0"):
    #gives min and max temperature from array
      with Lepton3(device) as l:
        a,_ = l.capture()
        min_t = ((a.min()-27315)/100.0)
        max_t = ((a.max()-27315)/100.00)
        return min_t, max_t
    

if uploadToInfluxDB == True:
    #upload measurements to influx
    timestamp = get_timestamp()
    weightMes = prepWeightMeasure()
    moisture01Mes = prepMoisture01()
    moisture02Mes = prepMoisture02()
    thermImgMin, thermImgMax = prepThermalCameraValues()

    influx_weight = get_line_protocol(measurementName, tagKeyA, tagValueA, tagKeyB, tagValue_m2, fieldKey_m2, weightMes, timestamp)
    influx_img = get_line_protocol(measurementName, tagKeyA, tagValueA, tagKeyB, tagValue_m1, fieldKey_m1, 1, timestamp)
    influx_moisture01 = get_line_protocol(measurementName, tagKeyA, tagValueA, tagKeyB, tagValue_m3, fieldKey_m3, moisture01Mes, timestamp)
    influx_moisture02 = get_line_protocol(measurementName, tagKeyA, tagValueA, tagKeyB, tagValue_m4, fieldKey_m4, moisture02Mes, timestamp)
    influx_thermImg = get_line_protocol(measurementName, tagKeyA, tagValueA, tagKeyB, tagValue_m5, fieldKey_m5, 2, timestamp)
    influx_thermImgMin = get_line_protocol(measurementName, tagKeyA, tagValueA, tagKeyB, tagValue_m6, fieldKey_m6, thermImgMin, timestamp)
    influx_thermImgMax = get_line_protocol(measurementName, tagKeyA, tagValueA, tagKeyB, tagValue_m7, fieldKey_m7, thermImgMax, timestamp)

    influx_lines = [influx_weight,influx_img,influx_moisture01,influx_moisture02, influx_thermImg, influx_thermImgMin, influx_thermImgMax]

    for line in influx_lines:
        send_line(line)
    print('Upload to Influx Done')
    
    realImage = prepCameraShot()
    thermImage = prepThermalCameraShot()
    combiImage = CombineImages(realImage, thermImage)

    pathExpImg = '/home/pi/mnt/gdrive/2020_Establishing_Methods_Phase/{}_{}'.format(measurementName, fieldKey_m1)

    if not os.path.exists(pathExpImg):
        os.makedirs(pathExpImg)

    #upload image to google drive
    now = datetime.now().strftime("%Y-%m-%d_%H-%M")
    print(now)
    imName = "{}_{}.jpg".format(measurementName, now)
    imLoc = '{}/{}'.format(pathExpImg, imName)
    print(imLoc)
    cv2.imwrite(imLoc, realImage)
    print("image uploaded to gdrive")
    
    pathExpThermImg = '/home/pi/mnt/gdrive/2020_Establishing_Methods_Phase/{}_{}'.format(measurementName, fieldKey_m5)

    if not os.path.exists(pathExpThermImg):
        os.makedirs(pathExpThermImg)

    #upload image to google drive
    now = datetime.now().strftime("%Y-%m-%d_%H-%M")
    print(now)
    imName = "{}_{}.jpg".format(measurementName, now)
    imLoc = '{}/{}'.format(pathExpThermImg, imName)
    print(imLoc)
    cv2.imwrite(imLoc, combiImage)
    print("thermal image uploaded to gdrive")





