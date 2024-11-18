#!/usr/bin/env python3
import RPi.GPIO as GPIO
from hx711 import HX711
import csv
import time
import os

# File paths
CALIBRATION_FILE = '/home/pi/loadcell.calib'
CSV_FILE = '/home/pi/CITA-load.csv'


def save_calibration_data(calibration_factor):
    """Saves calibration data to a file."""
    with open(CALIBRATION_FILE, 'w') as file:
        file.write(str(calibration_factor))
    print("Calibration data saved.")


def load_calibration_data():
    """Loads calibration data from a file."""
    if os.path.isfile(CALIBRATION_FILE):
        with open(CALIBRATION_FILE, 'r') as file:
            calibration_factor = float(file.read())
        print("Loaded calibration data.")
        return calibration_factor
    else:
        return None


def calibrate(hx711, known_weight):
    """Calibrates the HX711 using a known weight."""
    print("Calibrating... Please place a known weight on the scale.")
    raw_data = hx711.get_data_mean(times=10)
    average_raw_value = sum(raw_data) / len(raw_data)
    print(f"Average raw value (without weight): {average_raw_value}")
    
    calibration_factor = average_raw_value / known_weight
    print(f"Calibration factor: {calibration_factor}")
    
    return calibration_factor


def get_weight(hx711, calibration_factor):
    """Reads the weight from the scale using the calibration factor."""
    raw_data = hx711.get_data_mean(times=10)
    average_raw_value = sum(raw_data) / len(raw_data)
    weight = average_raw_value / calibration_factor
    return weight


def log_to_csv(timestamp, weight):
    """Logs the weight and timestamp to a CSV file."""
    file_exists = os.path.isfile(CSV_FILE)
    with open(CSV_FILE, mode='a', newline='') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(['Timestamp', 'Weight (grams)'])  # Write header if file is new
        writer.writerow([timestamp, weight])
    print(f"Logged: {timestamp}, {weight} grams")


def measure_and_log_weight(hx711, calibration_factor, interval_seconds):
    """Measures and logs the weight every interval_seconds."""
    print(f"Taking measurements every {interval_seconds} seconds. Press Ctrl+C to stop.")
    
    try:
        while True:
            # Get the average weight over the defined interval
            weight_readings = []
            start_time = time.time()
            while time.time() - start_time < interval_seconds:
                weight = get_weight(hx711, calibration_factor)
                weight_readings.append(weight)
                time.sleep(1)  # Sleep for 1 second before taking the next reading
            
            average_weight = sum(weight_readings) / len(weight_readings)
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
            log_to_csv(timestamp, average_weight)  # Log the weight with the timestamp

            print(f"{timestamp} - Average Weight: {average_weight:.2f} grams")

            time.sleep(interval_seconds)  # Wait for the next measurement cycle

    except KeyboardInterrupt:
        print("Measurement stopped.")


def main():
    """Main function to start the program."""
    GPIO.setmode(GPIO.BCM)

    # Create an HX711 instance
    hx711 = HX711(dout_pin=21, pd_sck_pin=20)

    # Load calibration data or calibrate if not found
    calibration_factor = load_calibration_data()

    if calibration_factor is None:
        print("Calibration data not found. Proceeding with calibration...")
        known_weight = float(input("Enter a known weight (in grams) for calibration: "))
        calibration_factor = calibrate(hx711, known_weight)
        save_calibration_data(calibration_factor)  # Save the calibration data to a file
    else:
        print(f"Using loaded calibration factor: {calibration_factor}")

    # Ask for the measurement interval in seconds
    interval_seconds = int(input("Enter the measurement interval in seconds: "))

    # Start measuring and logging weight
    measure_and_log_weight(hx711, calibration_factor, interval_seconds)

    GPIO.cleanup()  # Clean up GPIO pins


if __name__ == "__main__":
    main()
