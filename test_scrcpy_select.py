import sys
sys.path.insert(0, 'src')

import socket
import select
import time

# Wait for server to start
time.sleep(2)

# Connect to socket
sock = socket.create_connection(("127.0.0.1", 27183), timeout=30)
print("Connected to socket")

# Read initial data (dummy byte + device name + codec_id + session header)
data = b''
while len(data) < 100:
    try:
        chunk = sock.recv(4096)
        if chunk:
            data += chunk
            print(f"Received {len(chunk)} bytes")
        else:
            print("Socket closed by server")
            break
    except socket.timeout:
        print("Socket timeout")
        break
    except Exception as e:
        print(f"Error: {e}")
        break

print(f"Initial data: {len(data)} bytes")
print(f"First 100 bytes: {data[:100].hex()}")

# Now check if any more data is available
print("\nChecking for more data...")
start_time = time.time()
total_extra = 0
while time.time() - start_time < 10:
    r, _, _ = select.select([sock], [], [], 1.0)
    if r:
        try:
            chunk = sock.recv(4096)
            if chunk:
                total_extra += len(chunk)
                print(f"Received {len(chunk)} bytes: {chunk[:50].hex()}")
            else:
                print("Socket closed")
                break
        except Exception as e:
            print(f"Error: {e}")
            break
    else:
        print("No data available (1s timeout)")

print(f"Total extra data: {total_extra} bytes")
sock.close()
