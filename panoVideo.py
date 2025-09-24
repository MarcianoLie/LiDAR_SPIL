import cv2
import numpy as np
import time
from collections import deque
from tkinter import Tk, filedialog # <-- Diubah: Menambah filedialog

# --- PENGATURAN DAN KALIBRASI ---
PIXELS_PER_METER = 500
SPEED_THRESHOLD_KMH = 0.15
CAPTURE_DISTANCE_PIXELS = 1.0
TRACKING_CONFIDENCE_THRESHOLD = 0.8 

# --- TAMPILAN INSTRUKSI ---
print("Program Pemindai Adaptif Cerdas (v4.3 - Simpan Hasil Kustom)")
print("-------------------------------------")
print("Tekan 's' untuk AKTIFKAN/NONAKTIFKAN mode pemindaian.")
print("Tekan 'c' untuk MENGHAPUS hasil pindaian.")
print("Tekan 'q' untuk KELUAR dan memilih lokasi penyimpanan gambar.")
print("-------------------------------------")

# --- Membuka File Explorer untuk memilih video ---
Tk().withdraw() 
video_path = filedialog.askopenfilename(title="Pilih file video Anda", 
                                       filetypes=[("Video Files", "*.mp4 *.avi *.mkv *.mov"), 
                                                  ("All files", ".")])

if not video_path:
    print("Tidak ada file yang dipilih. Program berhenti.")
    exit()

# --- INISIALISASI ---
cap = cv2.VideoCapture(video_path) 
if not cap.isOpened():
    print(f"Error: Tidak bisa membuka file video '{video_path}'")
    exit()

frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
print(f"Resolusi Video: {frame_width}x{frame_height}")

# --- MEMBUAT PLACEHOLDER ---
placeholder = np.zeros((frame_height, 500, 3), dtype=np.uint8)
cv2.putText(placeholder, "Hasil akan muncul di sini...", (50, frame_height // 2), 
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

# --- VARIABEL STATUS ---
is_scanning_mode_active = False
hasil_scan = placeholder.copy()
is_first_capture = True
posisi_slit = frame_width // 2
accumulated_pixel_shift = 0.0
is_tracking = False
last_known_position = None
last_frame_time = time.time()
template = None
speed_buffer = deque()
display_speed_kmh = 0.0
last_speed_update_time = time.time()
last_tracking_reset_time = time.time()

# --- PENGATURAN KOTAK ---
box_size = 100
w, h = box_size, box_size
x_box_init = (frame_width - w) // 2
y_box_init = (frame_height - h) // 2

# --- LOOP UTAMA ---
cv2.imshow('Hasil Pindaian', hasil_scan)
while True:
    ret, frame = cap.read()
    if not ret: 
        print("Video selesai diproses.")
        break

    frame = cv2.flip(frame, 1) 
    
    display_frame = frame.copy()
    current_time = time.time()
    delta_time = current_time - last_frame_time
    last_frame_time = current_time

    # --- BLOK LOGIKA RESET PELACAKAN ---
    if is_scanning_mode_active and (current_time - last_tracking_reset_time >= 1.0):
        is_tracking = False
        template = None
        last_known_position = None
        last_tracking_reset_time = current_time
        print("INFO: Posisi pelacakan di-reset ke tengah.")
    
    instant_speed_mps = 0.0

    # --- LOGIKA UTAMA ---
    if is_scanning_mode_active:
        if not is_tracking:
            template = frame[y_box_init : y_box_init + h, x_box_init : x_box_init + w]
            gray_template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
            if cv2.Laplacian(gray_template, cv2.CV_64F).var() > 20:
                is_tracking = True
                last_known_position = (x_box_init, y_box_init)
                print("Objek terdeteksi, memulai pelacakan...")
        
        else:
            search_area = frame[y_box_init - 20 : y_box_init + h + 20, :]
            res = cv2.matchTemplate(search_area, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)

            if max_val >= TRACKING_CONFIDENCE_THRESHOLD:
                current_pos = (max_loc[0], max_loc[1] + y_box_init - 20)
                pixel_distance = abs(current_pos[0] - last_known_position[0])
                
                if delta_time > 0:
                    instant_speed_mps = (pixel_distance / PIXELS_PER_METER) / delta_time

                if (instant_speed_mps * 3.6) > SPEED_THRESHOLD_KMH:
                    accumulated_pixel_shift += pixel_distance
                    while accumulated_pixel_shift >= CAPTURE_DISTANCE_PIXELS:
                        irisan = frame[:, posisi_slit:posisi_slit+1]
                        if is_first_capture:
                            hasil_scan = irisan
                            is_first_capture = False
                        else:
                            hasil_scan = np.concatenate((hasil_scan, irisan), axis=1)
                        accumulated_pixel_shift -= CAPTURE_DISTANCE_PIXELS
                
                last_known_position = current_pos
                template = frame[current_pos[1]:current_pos[1]+h, current_pos[0]:current_pos[0]+w]
                cv2.rectangle(display_frame, current_pos, (current_pos[0] + w, current_pos[1] + h), (0, 255, 0), 2)
            
            else:
                is_tracking = False
                print("Pelacakan gagal, mencari objek baru...")

    # --- BLOK PERHITUNGAN KECEPATAN ---
    speed_buffer.append((current_time, instant_speed_mps))
    while speed_buffer and current_time - speed_buffer[0][0] > 1.0:
        speed_buffer.popleft()

    if current_time - last_speed_update_time >= 1.0:
        if speed_buffer and is_tracking:
            avg_speed_mps = sum(item[1] for item in speed_buffer) / len(speed_buffer)
            display_speed_kmh = avg_speed_mps * 3.6
        else:
            display_speed_kmh = 0.0
        last_speed_update_time = current_time

    # --- VISUALISASI ---
    cv2.line(display_frame, (posisi_slit, 0), (posisi_slit, frame_height), (0, 255, 0), 1)
    scan_status_text = f"SCAN MODE: {'ACTIVE' if is_scanning_mode_active else 'OFF'}"
    tracking_status_text = "TRACKING" if is_tracking else "WAITING FOR OBJECT"
    speed_text = f"Kecepatan: {display_speed_kmh:.2f} km/jam" 
    
    cv2.putText(display_frame, scan_status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    if is_scanning_mode_active:
        cv2.putText(display_frame, tracking_status_text, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
        cv2.putText(display_frame, speed_text, (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
    
    if not is_tracking and is_scanning_mode_active:
        cv2.rectangle(display_frame, (x_box_init, y_box_init), (x_box_init + w, y_box_init + h), (255, 255, 0), 2)

    cv2.imshow('Pemindai Adaptif Cerdas', display_frame)
    cv2.imshow('Hasil Pindaian', hasil_scan)

    # --- KONTROL KEYBOARD ---
    key = cv2.waitKey(1) & 0xFF
    if key == ord('s'):
        is_scanning_mode_active = not is_scanning_mode_active
        if not is_scanning_mode_active:
            is_tracking = False; display_speed_kmh = 0.0; template = None
            print("Mode pemindaian NONAKTIF.")
        else:
            print("Mode pemindaian AKTIF. Arahkan objek ke tengah untuk memulai.")
            
    elif key == ord('c'):
        hasil_scan = placeholder.copy()
        is_first_capture = True
        print("Hasil pindaian dihapus.")
        
    elif key == ord('q'):
        print("Keluar dari program.")
        break

# --- PERUBAHAN: PEMBERSIHAN DAN PENYIMPANAN ---
# Hanya coba menyimpan jika ada sesuatu yang sudah dipindai
if not is_first_capture and hasil_scan.shape[1] > 1:
    # Membuka dialog 'Save As' untuk memilih lokasi dan nama file
    save_path = filedialog.asksaveasfilename(
        title="Simpan hasil pindaian sebagai...",
        defaultextension=".png", # Ekstensi file default
        filetypes=[("PNG Image", "*.png"), 
                   ("JPEG Image", "*.jpg"), 
                   ("All Files", ".")]
    )

    # Jika pengguna memilih lokasi (tidak menekan cancel)
    if save_path:
        cv2.imwrite(save_path, hasil_scan)
        print(f"Gambar berhasil disimpan di: {save_path}")
    else:
        print("Penyimpanan dibatalkan oleh pengguna.")

# --- AKHIR PERUBAHAN ---

cap.release()
cv2.destroyAllWindows()