#!/usr/bin/env python3
"""Debug scrcpy raw socket data to understand why no frames are received."""
import sys
import os
import time
import socket
import threading

project_root = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(project_root, "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from core.capability.device.adb_manager import ADBDeviceManager
from core.capability.input.screenshot.scrcpy_core import ScrcpyCore

adb = ADBDeviceManager(
    adb_path=os.path.join(project_root, "3rd-part", "adb", "adb.exe"),
    timeout=30
)

print("Starting ScrcpyCore...")
core = ScrcpyCore(adb, "192.168.1.12:16512")
core.start()
print("ScrcpyCore started.")

# Raw socket reader
def raw_reader():
    sock = core._video_socket
    print(f"Socket connected: {sock is not None}")
    if sock:
        print(f"Socket timeout: {sock.gettimeout()}")
        print(f"Socket blocking: {sock.getblocking()}")

    data = b''
    start = time.time()
    while time.time() - start < 20:
        try:
            if sock is None:
                print("Socket is None, exiting")
                break
            chunk = sock.recv(4096)
            if chunk:
                data += chunk
                print(f"RECV {len(chunk)} bytes | total={len(data)} | hex={chunk[:64].hex()}")
            else:
                print("Socket closed by server")
                break
        except socket.timeout:
            print("Socket timeout")
            break
        except BlockingIOError:
            time.sleep(0.05)
        except Exception as e:
            print(f"Error: {e}")
            break

    print(f"Total raw received: {len(data)} bytes")
    if len(data) > 0:
        print(f"First 128 bytes hex: {data[:128].hex()}")
        # Try to parse as scrcpy packets
        offset = 0
        pkt_idx = 0
        while offset < len(data) - 12:
            header = data[offset:offset+12]
            if len(header) < 12:
                break
            flags = header[0]
            size = int.from_bytes(header[8:12], 'big')
            is_session = bool(flags & 0x80)
            print(f"Packet {pkt_idx}: offset={offset} flags=0x{flags:02x} size={size} session={is_session}")
            if is_session:
                width = int.from_bytes(header[4:8], 'big')
                height = int.from_bytes(header[8:12], 'big')
                print(f"  -> Session packet: {width}x{height}")
                offset += 12
            elif size > 0 and size < 2 * 1024 * 1024:
                payload = data[offset+12:offset+12+size]
                print(f"  -> Media packet: {len(payload)} bytes, first 32 bytes={payload[:32].hex()}")
                offset += 12 + size
            else:
                print(f"  -> Invalid packet size, stopping")
                break
            pkt_idx += 1

t = threading.Thread(target=raw_reader, daemon=True)
t.start()
t.join(timeout=25)

print("Stopping ScrcpyCore...")
core.stop()
print("Done.")
