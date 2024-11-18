#!/usr/bin/env python3
import RPi.GPIO as GPIO
from hx711 import HX711
import csv
import time
import os

# CSV file path
CSV_FILE = 'cita-load.csv'

def log_to_csv(timestamp, weight):
    """Logs the weight and timestamp to a CSV file."""
    file_exists = os.path.isfile(CSV_FILE)
    with open(CSV_FILE, mode='a', newline='') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(['Timestamp', 'Weight (grams)'])  # Write header if file is new
        writer.writerow([timestamp, weight])
    print(f"Logged: {timestamp}, {weight} grams")


def get_average_weight(hx, interval_seconds):
    """Takes the average of the measurements in the last 'interval_seconds' seconds."""
    weight_readings = []
    start_time = time.time()
    while time.time() - start_time < interval_seconds:
        weight = hx.get_weight_mean(10)  # Take a reading (mean of 10 samples)
        weight_readings.append(weight)
        time.sleep(1)  # Wait 1 second before the next reading
    
    average_weight = sum(weight_readings) / len(weight_readings)
    return average_weight


def main():
    GPIO.setmode(GPIO.BCM)

    # Create an HX711 instance
    hx = HX711(dout_pin=21, pd_sck_pin=20)

    # Measure tare and save the value as offset for current channel and gain selected
    err = hx.zero()
    if err:
        raise ValueError('Tare is unsuccessful.')

    # Print initial reading after tare
    reading = hx.get_raw_data_mean()
    if reading:
        print('Data subtracted by offset but still not converted to units:', reading)
    else:
        print('Invalid data', reading)

    # Calibration process with known weight (optional step)
    input('Put known weight on the scale and then press Enter')
    reading = hx.get_data_mean()
    if reading:
        print('Mean value from HX711 subtracted by offset:', reading)
        known_weight_grams = input('Write how many grams it was and press Enter: ')
        try:
            value = float(known_weight_grams)
            print(value, 'grams')
        except ValueError:
            print('Expected integer or float and I have got:', known_weight_grams)

        ratio = reading / value  # Calculate the ratio for channel A and gain 128
        hx.set_scale_ratio(ratio)  # Set the ratio for current channel
        print('Ratio is set.')
    else:
        raise ValueError('Cannot calculate mean value. Try debug mode. Variable reading:', reading)

    # Start continuous measurement every 10 seconds
    print("Starting continuous measurements. Press 'CTRL + C' to exit.")
    try:
        while True:
            # Get the average weight reading over the last 10 seconds
            average_weight = get_average_weight(hx, 10)
            
            # Get current timestamp
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
            
            # Log the timestamp and average weight into the CSV file
            log_to_csv(timestamp, average_weight)

            print(f"{timestamp} - Average Weight: {average_weight:.2f} grams")

            # Wait for the next cycle
            time.sleep(10)  # Wait 10 seconds before next measurement cycle

    except KeyboardInterrupt:
        print("Measurement stopped.")

    finally:
        GPIO.cleanup()


if __name__ == "__main__":
    main()
