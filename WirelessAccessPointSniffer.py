import serial
import re
import time

#This is made to run an ESP32 Wrover module. Upload it via Arduino IDE. In the console, it rpints the strength, name, and MAC address of nearby WAPs.

SERIAL_PORT = 'COM6' 
BAUD_RATE = 115200
TIMEOUT_SECONDS = 10  
devices = {}

try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE)
    print("Started. Scanning for devices...")
    
    while True:

        if ser.in_waiting > 0:
            ser. reset_input_buffer()
        line = ser.readline().decode('utf-8', errors='ignore').strip()
        
       
        match = re.search(r"RSSI: (-\d+) \| From MAC: ([\w:]+)", line)
        
        if match:
            rssi = int(match.group(1))
            mac = match.group(2)
           
            devices[mac] = [rssi, time.time()]
            
           
            current_time = time.time()
            devices = {m: data for m, data in devices.items() if (current_time - data[1]) < TIMEOUT_SECONDS}
            
          
            print("\033[H", end="")
            
            print(f"{'MAC ADDRESS':<20} | {'SIGNAL':<10} | {'PROXIMITY (Top 23)'}")
            print("-" * 65)
            
            
            sorted_devices = sorted(devices.items(), key=lambda item: item[1][0], reverse=True)[:23]
            
            for m, data in sorted_devices:
                r = data[0]
                bar_length = int((100 + r) / 2)
                
                bar_string = ("█" * max(0, bar_length)).ljust(50)
                print(f"{m:<20} | {r:<10} | {bar_string}")

except KeyboardInterrupt:
    print("\nRadar stopped.")
except Exception as e:
    print(f"\nError: {e}")
finally:
    if 'ser' in locals():
        ser.close()
