// main_reader.cpp (SUDAH DIPERBAIKI)
#include <iostream>
#include <string>
#include <chrono>
#include <thread>

#ifdef _WIN32
    #include <windows.h>
#else
    #include <fcntl.h>
    #include <sys/mman.h>
    #include <sys/stat.h>
    #include <unistd.h>
    #include <semaphore.h>
#endif

// DIUBAH: Menjadi WCHAR untuk kompatibilitas Unicode Windows
#ifdef _WIN32
    const WCHAR* SHM_NAME = L"speed_shm";
    const WCHAR* SEM_NAME = L"speed_sem";
#else
    const char* SHM_NAME = "speed_shm";
    const char* SEM_NAME = "speed_sem";
#endif

const int DATA_SIZE = 8; // 8 bytes for a double

int main() {
#ifdef _WIN32
    // --- Implementasi Windows ---
    // Kode di bawah ini tidak berubah, karena variabel di atas sudah benar tipenya
    HANDLE hSem = OpenSemaphore(SEMAPHORE_ALL_ACCESS, FALSE, SEM_NAME);
    if (hSem == NULL) {
        std::cerr << "Error: Gagal membuka Semaphore. Pastikan publisher (Python) sudah berjalan." << std::endl;
        return 1;
    }

    HANDLE hShm = OpenFileMapping(FILE_MAP_ALL_ACCESS, FALSE, SHM_NAME);
    if (hShm == NULL) {
        std::cerr << "Error: Gagal membuka Shared Memory. Pastikan publisher (Python) sudah berjalan." << std::endl;
        CloseHandle(hSem);
        return 1;
    }

    void* pBuf = MapViewOfFile(hShm, FILE_MAP_ALL_ACCESS, 0, 0, DATA_SIZE);
    if (pBuf == NULL) {
        std::cerr << "Error: Gagal memetakan view dari Shared Memory." << std::endl;
        CloseHandle(hShm);
        CloseHandle(hSem);
        return 1;
    }

#else
    // --- Implementasi Linux/macOS (POSIX) ---
    std::string sem_posix_name = "/" + std::string(SEM_NAME);
    sem_t* sem = sem_open(sem_posix_name.c_str(), 0);
    if (sem == SEM_FAILED) {
        perror("sem_open");
        std::cerr << "Error: Gagal membuka Semaphore. Pastikan publisher (Python) sudah berjalan." << std::endl;
        return 1;
    }

    int shm_fd = shm_open(SHM_NAME, O_RDWR, 0666);
    if (shm_fd == -1) {
        perror("shm_open");
        std::cerr << "Error: Gagal membuka Shared Memory. Pastikan publisher (Python) sudah berjalan." << std::endl;
        sem_close(sem);
        return 1;
    }

    void* pBuf = mmap(0, DATA_SIZE, PROT_READ | PROT_WRITE, MAP_SHARED, shm_fd, 0);
    if (pBuf == MAP_FAILED) {
        perror("mmap");
        std::cerr << "Error: Gagal memetakan Shared Memory." << std::endl;
        close(shm_fd);
        sem_close(sem);
        return 1;
    }
#endif

    std::cout << "Berhasil terhubung ke Shared Memory dan Semaphore." << std::endl;
    std::cout << "Membaca data kecepatan..." << std::endl;

    try {
        while (true) {
#ifdef _WIN32
            WaitForSingleObject(hSem, INFINITE);
#else
            sem_wait(sem);
#endif
            
            double speed = *(static_cast<double*>(pBuf));
            std::cout << "Kecepatan diterima: " << speed << " km/jam" << std::endl;

#ifdef _WIN32
            ReleaseSemaphore(hSem, 1, NULL);
#else
            sem_post(sem);
#endif
            
            std::this_thread::sleep_for(std::chrono::milliseconds(1000));
        }
    } catch (...) {}

#ifdef _WIN32
    UnmapViewOfFile(pBuf);
    CloseHandle(hShm);
    CloseHandle(hSem);
#else
    munmap(pBuf, DATA_SIZE);
    close(shm_fd);
    sem_close(sem);
#endif
    
    std::cout << "\nProgram reader berhenti." << std::endl;
    return 0;
}