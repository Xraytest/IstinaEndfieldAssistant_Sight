import sys
sys.path.insert(0, 'src')

import socket
import time

# Wait for server to start
time.sleep(2)

# Connect to socket
sock = socket.create_connection(("127.0.0.1", 27183), timeout=30)
print("Connected to socket")

# Set non-blocking
sock.setblocking(False)

data = b''
start_time = time.time()
while time.time() - start_time < 10:
    try:
        chunk = sock.recv(4096)
        if chunk:
            data += chunk
            print(f"Received {len(chunk)} bytes: {chunk[:100].hex()}")
        else:
            print("Socket closed by server")
            break
    except BlockingIOError:
        time.sleep(0.1)
    except socket.timeout:
        print("Socket timeout")
        break
    except Exception as e:
        print(f"Error: {e}")
        break

print(f"Total received: {len(data)} bytes")
sock.close()
