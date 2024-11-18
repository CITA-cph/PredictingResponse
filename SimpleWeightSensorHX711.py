#!/usr/bin/python3
import time
import csv
from hx711 import HX711
import RPi.GPIO as GPIO

# Calibration function
def calibrate(hx711, known_weight):
    print("Calibrating... Please place a known weight on the scale.")
    
    # Read multiple samples to calculate average raw value
    raw_data = hx711.get_data_mean(times=10)
    average_raw_value = sum(raw_data) / len(raw_data)  # Get the average raw value
    print(f"Average raw value (without weight): {average_raw_value}")
    
    # The calibration factor is derived as:
    calibration_factor = average_raw_value / known_weight
    print(f"Calibration factor: {calibration_factor}")
    
    return calibration_factor

# Function to get weight in grams
def get_weight(hx711, calibration_factor):
    raw_data = hx711.get_data_mean(times=10)
    average_raw_value = sum(raw_data) / len(raw_data)  # Average of multiple readings
    weight = average_raw_value / calibration_factor  # Apply calibration factor
    return weight

# Initialize HX711
hx711 = HX711(
    dout_pin=17,
    pd_sck_pin=21,
    channel='A',
    gain=64
)

# Calibration setup (example)
known_weight = 100  # Known weight in grams for calibration

# Set up GPIO cleanup at the end
try:
    hx711.reset()  # Before we start, reset the HX711 (optional)

    # Tare the scale (reset it)
    hx711.tare()  # Use tare() instead of zero()

    # Calibrate with known weight
    calibration_factor = calibrate(hx711, known_weight)
    
    # Set up CSV file to write measurements
    csv_file = '/home/pi/force_gauge_measurements.csv'
    with open(csv_file, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['Timestamp', 'Weight (grams)'])  # Write headers
        
        # Take measurements at defined intervals
        interval_seconds = 5  # Time interval between measurements (in seconds)
        duration_minutes = 10  # Total duration of the measurement session (in minutes)
        
        start_time = time.time()
        
        while time.time() - start_time < duration_minutes * 60:
            # Get the weight reading
            weight = get_weight(hx711, calibration_factor)
            
            # Get the current timestamp
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
            
            # Write to CSV file
            writer.writerow([timestamp, weight])
            
            # Print the result (optional)
            print(f"{timestamp} - Weight: {weight:.2f} grams")
            
            # Wait for the next interval
            time.sleep(interval_seconds)
    
finally:
    GPIO.cleanup()  # Always clean up GPIO to avoid issues

print("Measurement session completed.")
