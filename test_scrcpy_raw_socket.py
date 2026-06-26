import sys
sys.path.insert(0, 'src')

import socket
import threading
import time

def read_socket():
    sock = socket.create_connection(("127.0.0.1", 27183), timeout=30)
    print("Connected to socket")
    
    data = b''
    start_time = time.time()
    while time.time() - start_time < 15:
        try:
            chunk = sock.recv(4096)
            if chunk:
                data += chunk
                print(f"Received {len(chunk)} bytes: {chunk[:100].hex()}")
            else:
                print("Socket closed by server")
                break
        except socket.timeout:
            print("Socket timeout")
            break
        except Exception as e:
            print(f"Error: {e}")
            break
    
    print(f"Total received: {len(data)} bytes")
    sock.close()

if __name__ == "__main__":
    # First start the server
    from core.capability.device.adb_manager import ADBDeviceManager
    from core.capability.input.screenshot.scrcpy_core import ScrcpyCore
    
    adb = ADBDeviceManager(adb_path='3rd-part/adb/adb.exe')
    core = ScrcpyCore(adb, '192.168.1.12:16512')
    
    print("Starting scrcpy server...")
    core.start()
    
    print("Server started. Reading from socket...")
    read_socket()
    
    print("Stopping server...")
    core.stop()
