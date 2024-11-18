#!/usr/bin/env python3
import RPi.GPIO as GPIO
from hx711 import HX711
import csv
import time
import os

# CSV file path
CSV_FILE = 'cita-load.csv'

def log_to_csv(sample_name, timestamp, weight):
    """Logs the sample name, timestamp, and weight to a CSV file."""
    file_exists = os.path.isfile(CSV_FILE)
    with open(CSV_FILE, mode='a', newline='') as file:
        writer = csv.writer(file)
        if not file_exists:
            # Write the header row, including the sample name
            writer.writerow(['Sample', 'Timestamp', 'Weight (grams)'])
        writer.writerow([sample_name, timestamp, weight])
    print(f"Logged: {sample_name} - {timestamp}, {weight} grams")


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

    # Ask the user for the interval in seconds
    interval_seconds = input('Enter the time interval for average measurement (in seconds): ')
    try:
        interval_seconds = int(interval_seconds)
        if interval_seconds <= 0:
            raise ValueError('Interval must be a positive integer.')
    except ValueError as e:
        print(f"Invalid interval value: {e}. Defaulting to 10 seconds.")
        interval_seconds = 10  # Default to 10 seconds if invalid input

    # Ask the user to define the sample (a string to be logged)
    sample_name = input('Enter a description or name for this sample: ')
    print(f"Sample name set to: {sample_name}")

    # Inform user about stopping the measurement with 'CTRL + C'
    print(f"Starting continuous measurements with an interval of {interval_seconds} seconds. Press 'CTRL + C' to stop the measurement.")

    # Start continuous measurement
    try:
        while True:
            # Get the average weight reading over the user-defined interval
            average_weight = get_average_weight(hx, interval_seconds)
            
            # Get current timestamp
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
            
            # Log the sample name, timestamp, and average weight into the CSV file
            log_to_csv(sample_name, timestamp, average_weight)

            print(f"{timestamp} - {sample_name} - Average Weight: {average_weight:.2f} grams")

            # Wait for the next cycle
            time.sleep(interval_seconds)  # Wait for the user-defined interval before next measurement

    except KeyboardInterrupt:
        print("Measurement stopped by user.")

    finally:
        GPIO.cleanup()


if __name__ == "__main__":
    main()
