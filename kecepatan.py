# speed_writer.py (Template Matching + Shared Memory)

import cv2
import numpy as np
import time
from math import sqrt
import sys
import struct

# --- PENGATURAN IPC ---
# Pastikan library pywin32 sudah terinstal: pip install pywin32
from multiprocessing import shared_memory
import win32event
import win32security

SHM_NAME = "speed_shm"
SEM_NAME = "speed_sem"
DATA_SIZE = 8 # 8 bytes untuk tipe data double

# --- PENGATURAN DAN KALIBRASI ---
PIXELS_PER_METER = 500  # Sesuaikan dengan kalibrasi Anda

def main():
    # --- INISIALISASI ---
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Tidak bisa membuka kamera.")
        return

    template = None
    last_capture_time = time.time()
    speed_kmh = 0.0

    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    box_size = 100
    w, h = box_size, box_size
    x_box = int((frame_width - w) / 2)
    y_box = int((frame_height - h) / 2)

    # --- SETUP SHARED MEMORY & SEMAPHORE ---
    try:
        shm = shared_memory.SharedMemory(name=SHM_NAME, create=True, size=DATA_SIZE)
        print(f"Blok Shared Memory '{SHM_NAME}' dibuat.")
    except FileExistsError:
        shm = shared_memory.SharedMemory(name=SHM_NAME, create=False, size=DATA_SIZE)
        print(f"Blok Shared Memory '{SHM_NAME}' sudah ada.")

    sa = win32security.SECURITY_ATTRIBUTES()
    sa.bInheritHandle = False
    sem = win32event.CreateSemaphore(sa, 1, 1, SEM_NAME)
    print(f"Semaphore '{SEM_NAME}' dibuat.")

    try:
        # --- LOOP UTAMA PROGRAM ---
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame = cv2.flip(frame, 1)
            display_frame = frame.copy()
            current_time = time.time()
            delta_time = current_time - last_capture_time

            # Ambil template baru setiap 1 detik
            if delta_time >= 1:
                template = frame[y_box : y_box + h, x_box : x_box + w]
                last_capture_time = current_time
                speed_kmh = 0.0
            
            # Definisikan koordinat search area
            search_area_height = 110
            center_y = frame_height // 2
            center_x = frame_width // 2
            y1_search = max(0, center_y - (search_area_height // 2))
            y2_search = min(frame_height, center_y + (search_area_height // 2))
            x1_search = max(0, center_x - (search_area_height // 2))
            
            if template is not None:
                # Lakukan template matching dan hitung kecepatan
                search_area = frame[y1_search:y2_search, x1_search:]
                res = cv2.matchTemplate(search_area, template, cv2.TM_CCOEFF_NORMED)
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
                
                top_left_global = (max_loc[0] + x1_search, max_loc[1] + y1_search)
                
                found_center_x = top_left_global[0] + w // 2
                original_center_x = frame_width // 2

                pixel_distance = abs(found_center_x - original_center_x)
                
                if delta_time > 0:
                    meter_distance = pixel_distance / PIXELS_PER_METER
                    speed_mps = meter_distance / delta_time
                    speed_kmh = speed_mps * 3.6

                # Gambar kotak hijau di lokasi yang cocok
                bottom_right_global = (top_left_global[0] + w, top_left_global[1] + h)
                cv2.rectangle(display_frame, top_left_global, bottom_right_global, (0, 255, 0), 2)
                cv2.putText(display_frame, f"Match: {max_val:.2f}", (top_left_global[0], top_left_global[1]-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

            # --- PUBLISH DATA KE SHARED MEMORY ---
            win32event.WaitForSingleObject(sem, win32event.INFINITE)
            packed_data = struct.pack("d", speed_kmh)
            shm.buf[:DATA_SIZE] = packed_data
            win32event.ReleaseSemaphore(sem, 1)

            # --- VISUALISASI ---
            # Kotak kuning untuk area capture template
            cv2.rectangle(display_frame, (x_box, y_box), (x_box + w, y_box + h), (0, 255, 255), 2)
            
            # Kotak putih tipis untuk search area
            cv2.rectangle(display_frame, (x1_search, y1_search), (frame_width, y2_search), (255, 255, 255), 1)

            # Tampilkan teks kecepatan dan preview template
            speed_text = f"Kecepatan: {speed_kmh:.2f} km/jam"
            cv2.putText(display_frame, speed_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2, cv2.LINE_AA)
            
            if template is not None:
                roi_h, roi_w, _ = template.shape
                start_y = frame_height - roi_h - 10
                start_x = frame_width - roi_w - 10
                display_frame[start_y : start_y + roi_h, start_x : start_x + roi_w] = template
                cv2.rectangle(display_frame, (start_x, start_y), (start_x + roi_w, start_y + roi_h), (255, 0, 0), 1)
                cv2.putText(display_frame, "Template", (start_x - 10, start_y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)

            cv2.imshow("Deteksi Kecepatan - Python Writer", display_frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    except KeyboardInterrupt:
        print("\nMenutup program...")
    finally:
        # --- CLEANUP SEMUA RESOURCE ---
        print("Membersihkan resources...")
        shm.close()
        shm.unlink()
        if sem: sem.Close()
        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()