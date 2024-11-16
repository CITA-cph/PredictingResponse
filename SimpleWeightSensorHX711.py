import os
import pickle
import csv
import time
from datetime import datetime
from hx711 import HX711  # Import HX711 library
import RPi.GPIO as GPIO

# Constants
SWAP_FILE = 'hx711_calibration.swp'
CSV_FILE = 'weight_readings.csv'
MEASUREMENT_INTERVAL = 10  # Measurement interval in seconds (default: 10)

def calibrate_sensor(hx):
    """Calibrates the HX711 sensor using a known weight."""
    print("Starting calibration...")
    try:
        # Tare the scale
        print("Taring the scale (please ensure no weight on the scale)...")
        err = hx.zero()
        if err:
            raise ValueError('Tare failed.')
        print("Tare successful.")

        # Read raw data and prompt user for a known weight
        reading = hx.get_data_mean()
        if not reading:
            raise ValueError('Invalid reading during calibration.')

        print(f"Raw reading: {reading}")
        known_weight = float(input("Place a known weight (in grams) on the scale and enter its value: "))
        ratio = reading / known_weight
        hx.set_scale_ratio(ratio)
        print(f"Calibration successful! Scale ratio set to {ratio}")

        return hx
    except ValueError as e:
        print(f"Error during calibration: {e}")
        return None

def load_or_calibrate_sensor():
    """Loads calibration data or prompts for calibration."""
    hx = HX711(dout_pin=20, pd_sck_pin=21)
    if os.path.isfile(SWAP_FILE):
        with open(SWAP_FILE, 'rb') as file:
            hx = pickle.load(file)
            print("Loaded saved calibration.")
    else:
        hx = calibrate_sensor(hx)
        if hx:
            with open(SWAP_FILE, 'wb') as file:
                pickle.dump(hx, file)
    return hx

def log_to_csv(timestamp, weight):
    """Logs a weight measurement to a CSV file."""
    try:
        file_exists = os.path.isfile(CSV_FILE)
        with open(CSV_FILE, mode='a', newline='') as file:
            writer = csv.writer(file)
            if not file_exists:
                writer.writerow(["Timestamp", "Weight (grams)"])  # Write header if file is new
            writer.writerow([timestamp, weight])
        print(f"Logged: {timestamp}, {weight} grams")
    except Exception as e:
        print(f"Error writing to CSV: {e}")

def measure_and_log_weight(hx, interval):
    """Measures weight and logs it to a CSV file at a defined interval."""
    print(f"Starting weight measurements every {interval} seconds. Press Ctrl+C to stop.")
    try:
        while True:
            weight = hx.get_weight_mean(50)  # Average of 50 readings
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f"{timestamp} - Weight: {weight:.2f} grams")
            log_to_csv(timestamp, weight)
            time.sleep(interval)  # Wait for the defined interval
    except KeyboardInterrupt:
        print("Measurement stopped.")
    finally:
        GPIO.cleanup()

def main():
    global MEASUREMENT_INTERVAL

    # Allow user to adjust measurement interval at runtime
    try:
        user_interval = input(f"Enter measurement interval in seconds (default: {MEASUREMENT_INTERVAL}): ")
        if user_interval.strip():
            MEASUREMENT_INTERVAL = int(user_interval)
    except ValueError:
        print("Invalid input. Using default interval.")

    GPIO.setmode(GPIO.BCM)
    hx = load_or_calibrate_sensor()
    if hx:
        measure_and_log_weight(hx, MEASUREMENT_INTERVAL)

if __name__ == "__main__":
    main()
