import numpy as np
import socket
import time

def main():
    # Set up the UDP connection
    remote_addr = '192.168.0.122'  # Replace with the remote server IP address
    remote_port = 2020  # Replace with the remote port
    local_port = 9090  # Replace with the local port you want to listen on

    # Initialize the socket for UDP communication
    u2 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    u2.bind(('0.0.0.0', local_port))  # Bind to all interfaces on the local port

    # Flag to control the connection status
    connect = True  # Equivalent to 'on'
    off = False  # Equivalent to 'off'
    # Measurement loop
    while connect:
        try:
            # Wait for the message (blocking call)
            data, addr = u2.recvfrom(1024)  # Buffer size of 1024 bytes (can be adjusted)
            
            # If we receive data, process it
            if data:
                # Decode the received bytes into a string
                read_bytes = data.decode('utf-8').strip()
                cmd_bytes = read_bytes.split(',')
                cmd_bytes = np.array([float(data) for data in cmd_bytes])
                
                # Process the first command byte
                cmd_byte = cmd_bytes[0]
                
                # Command handling
                if cmd_byte == 1:  # Init
                    print("Initializing...")
                    # Initialize the instrument or device
                    
                elif cmd_byte == 2:  # Aquire on Trigger
                    print("Acquiring data on trigger...")
                    breakpoint()
                    # Handle trigger-based data acquisition
                    
                elif cmd_byte == 3:  # Measure
                    print("Measuring...")
                    # Perform the measurement logic
                    
                elif cmd_byte == 4:  # Cleanup
                    print("Cleaning up and preparing for the next cycle...")
                    # Perform cleanup operations
                    
                elif cmd_byte == 5:  # Disconnect Instrument
                    print("Disconnecting instrument...")
                    connect = off  # End the loop and disconnect
                    
                elif cmd_byte == 6:  # Program MW Chirp Waveform
                    print("Programming MW Chirp waveform...")
                    # Program the MW Chirp waveform
                    
                elif cmd_byte == 7:  # Play MW Chirp Waveform
                    print("Playing MW Chirp waveform...")
                    # Play the MW Chirp waveform

                else:
                    print(f"Unknown command byte: {cmd_byte}")
                
        except Exception as e:
            print(f"Error receiving or processing data: {e}")
            connect = off

        # Sleep to avoid excessive CPU usage (optional)
        time.sleep(0.1)

        # Close the UDP socket after the loop ends
        u2.close()

if __name__ == '__main__':
    main()