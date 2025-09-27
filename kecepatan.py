import cv2
import numpy as np
import time
from math import sqrt
import sys
import os

# --- Constants ---
# Define the filesystem path for the named pipe (FIFO).
# This pipe is used for Inter-Process Communication (IPC) to send data to another process.
FIFO_PATH = "/tmp/speed_pipe"

# PIXELS_PER_METER defines the scaling factor for converting pixel distance to meters.
# This value needs to be calibrated based on the camera setup (lens, distance to object, etc.).
# For this example, we assume 500 pixels in the camera view correspond to 1 meter in reality.
PIXELS_PER_METER = 500

def main():
    # --- IPC Setup ---
    # Check if the named pipe already exists.
    if not os.path.exists(FIFO_PATH):
        try:
            # Create the named pipe (FIFO). This is a special file that allows
            # one process to write to it and another to read from it.
            os.mkfifo(FIFO_PATH)
            print(f"Named pipe created at: {FIFO_PATH}")
        except OSError as e:
            # Exit if the pipe cannot be created.
            print(f"Failed to create FIFO: {e}", file=sys.stderr)
            sys.exit(1)

    # --- Pipe Connection ---
    # Open the named pipe in write mode ("w").
    # This is a BLOCKING call. The script will pause here until another process
    # (the "reader") opens the same pipe for reading.
    print("Waiting for a reader to connect to the pipe...")
    try:
        fifo = open(FIFO_PATH, "w")
        print("Reader connected. Starting speed detection.")
    except Exception as e:
        print(f"Failed to open FIFO for writing: {e}", file=sys.stderr)
        sys.exit(1)

    # --- Camera Initialization ---
    # Initialize video capture from the default camera (index 0).
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Cannot open camera.", file=sys.stderr)
        fifo.close() # Clean up the pipe if camera fails
        return

    # --- Variable Initialization ---
    template = None             # To store the image of the object we are tracking.
    last_capture_time = time.time() # To keep track of time for speed calculation.
    speed_kmh = 0.0             # The calculated speed in km/h.

    # Get camera frame dimensions.
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # Define the dimensions of the initial template capture box.
    box_size = 100
    w, h = box_size, box_size
    # Position the box in the center of the frame.
    x_box = int((frame_width - w) / 2)
    y_box = int((frame_height - h) / 2)

    try:
        # --- Main Processing Loop ---
        while True:
            # Read a new frame from the camera.
            ret, frame = cap.read()
            if not ret:
                print("Error: Failed to grab frame. Exiting.", file=sys.stderr)
                break

            # Flip the frame horizontally for a more intuitive, mirror-like view.
            frame = cv2.flip(frame, 1)
            
            current_time = time.time()
            delta_time = current_time - last_capture_time

            # --- Template Re-capture Logic ---
            # Every 1 second, capture a new template from the central box.
            # This allows tracking of a moving object as it passes through the center.
            if delta_time >= 1:
                template = frame[y_box : y_box + h, x_box : x_box + w]
                last_capture_time = current_time
                speed_kmh = 0.0 # Reset speed at the moment of new capture.
            
            # --- Search Area Definition ---
            # To optimize tracking, we don't search the entire frame.
            # We define a horizontal search area around the vertical center of the frame.
            search_area_height = 110
            center_y = frame_height // 2
            center_x = frame_width // 2
            y1_search = max(0, center_y - (search_area_height // 2))
            y2_search = min(frame_height, center_y + (search_area_height // 2))
            x1_search = max(0, center_x - (search_area_height // 2))
            
            # --- Object Tracking and Speed Calculation ---
            if template is not None:
                # Define the region of the frame where we will search for the template.
                search_area = frame[y1_search:y2_search, x1_search:]
                
                # Use template matching to find the location of the template in the search area.
                # TM_CCOEFF_NORMED is a robust matching method.
                res = cv2.matchTemplate(search_area, template, cv2.TM_CCOEFF_NORMED)
                _, _, _, max_loc = cv2.minMaxLoc(res) # We only need the location of the best match.
                
                # Convert the match location from search_area coordinates to full frame coordinates.
                top_left_global = (max_loc[0] + x1_search, max_loc[1] + y1_search)
                
                # Calculate the center of the found object.
                found_center_x = top_left_global[0] + w // 2
                original_center_x = frame_width // 2

                # --- Speed Calculation ---
                # 1. Calculate the horizontal distance the object has moved in pixels.
                pixel_distance = abs(found_center_x - original_center_x)
                
                if delta_time > 0:
                    # 2. Convert pixel distance to meters using the calibration factor.
                    meter_distance = pixel_distance / PIXELS_PER_METER
                    # 3. Calculate speed in meters per second (speed = distance / time).
                    speed_mps = meter_distance / delta_time
                    # 4. Convert speed from m/s to km/h.
                    speed_kmh = speed_mps * 3.6

            # --- IPC Write ---
            try:
                # Format the speed as a string with a newline character.
                # The newline acts as a message delimiter for the reader process.
                speed_message = f"{speed_kmh:.2f}\n"
                fifo.write(speed_message)
                # Flush the buffer to ensure the data is sent immediately without waiting.
                fifo.flush()
            except BrokenPipeError:
                # This error occurs if the reader process closes its end of the pipe.
                print("Reader has disconnected. Exiting.", file=sys.stderr)
                break 
            
            # Pause briefly to prevent the loop from consuming 100% CPU.
            # A 10ms sleep caps the loop at a theoretical maximum of 100 iterations per second.
            time.sleep(0.01)

    except KeyboardInterrupt:
        # Allow the user to stop the script gracefully with Ctrl+C.
        print("\nShutting down due to user request...", file=sys.stderr)
    finally:
        # --- Cleanup ---
        # This block runs whether the script exits normally or via an error.
        print("Cleaning up resources...", file=sys.stderr)
        # Close the named pipe.
        if 'fifo' in locals() and not fifo.closed:
            fifo.close()
        
        # Release the camera resource.
        cap.release()

# --- Script Entry Point ---
if __name__ == "__main__":
    main()
