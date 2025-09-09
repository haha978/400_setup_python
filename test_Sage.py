import numpy as np
import socket
import signal
import time
import matplotlib.pyplot as plt
import os
import sys
srcpath = os.path.realpath('D:/400_AWT/400_setup_python/Tabor Library')
sys.path.append(srcpath)
from teproteus_functions_v3 import get_cpatured_header
from teproteus_functions_v3 import connect, disconnect
from tevisainst import TEVisaInst
from teproteus import TEProteusAdmin as TepAdmin
from teproteus import TEProteusInst as TepInst
from TaborProteus import TaborProteus
from proteus_utils import defPulse, defBlock, makeChirp

def main():
    # Set up the UDP connection
    remote_addr = '192.168.0.122'  # Replace with the remote server IP address
    remote_port = 2020  # Replace with the remote port
    local_port = 9090  # Replace with the local port you want to listen on

    # Initialize the socket for UDP communication
    u2 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    u2.bind(('0.0.0.0', local_port))  # Bind to all interfaces on the local port

    #initialize Proteus
    inst = TaborProteus()

    # Flag to control the connection status
    connect = True  # Equivalent to 'on'
    off = False  # Equivalent to 'off'

    print("Waiting for command...")
    # Measurement loop
    while connect:
        try:
            # Wait for the message (blocking call)
            data, addr = u2.recvfrom(4096)  # Buffer size of 1024 bytes (can be adjusted)
            
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
                    inst.reset()
                    inst.initialize_AWG(ch = 1)
                    print("Done initializing.")
                    
                elif cmd_byte == 2:  # Pulse sequence on CPU Trigger
                    sampleRateDAC = 1.125e9
                    sampleRateADC = 2.25e9
                    ADC_ch = 2
                    num_Pulses = 5
                    cfr = 100e6
                    # Set sample rate for ADC and DAC
                    inst.sampleRateDAC, inst.sampleRateADC = sampleRateDAC, sampleRateADC
                    
                    print("Generating pulse sequence...")
                    p1 = defPulse(amp = 1, mod = 0, length = 50e-6, phase = 0, spacing = 100e-6)
                    p2 = defPulse(amp = 1, mod = 0, length = 50e-6, phase = 90, spacing = 100e-6)
                    b1 = defBlock([p1, p2], reps = [1, 10000], markers = [1, 1], trigs = [1, 1])
                    # b2 = defBlock([p1, p2], reps = [num_Pulses, num_Pulses], markers = [1, 1], trigs = [1, 1])
                    inst.makeBlocks(block_l = [b1], ch = 1, repeatSeq = [1])
                    print("Pulse sequence generation done.")
                    
                    inst.set_interpolation(ch = 1, interp_factor = 8)
                    inst.set_NCO(cfr = 75.38e6, phase = 90)

                    # This is hard-coded for now.
                    numframes = b1['reps'][0] + b1['reps'][1]
                    
                    # Handle trigger-based data acquisition
                    # SET DIGITIZER
                    assert inst.sampleRateDAC / 4 == inst.sampleRateADC, "sampleRateDAC must be set multiple of 4"
                    
                    print("Setting Digitizer...")
                    tacq, acq_delay = 10e-6, 12e-6
                    readLen, numframes= inst.set_digitizer(inst.sampleRateADC, numframes, cfr, tacq, acq_delay, ADC_ch)
                    inst.send_scpi_query(':DIG:ACQuire:FRAM:STATus?')
                    print("Done setting digitizer.")

                elif cmd_byte == 3:  # Measure
                    print("Measuring...")
                    # Perform the measurement logic
                    inst.send_scpi_cmd('*TRG')
                    max_iter = 1200
                    frameRx = 0
                    times = 0
                    FRAME_NMB = numframes
                    while (frameRx < FRAME_NMB):
                        resp = inst.send_scpi_query(':DIG:ACQuire:FRAM:STATus?')
                        print(resp)
                        framesParam = resp.split(",")
                        frameRx = int(framesParam[3])
                        times += 1
                        time.sleep(0.1)
                        if times > max_iter:
                            break
                    print(resp)
                    inst.send_scpi_cmd(':DIG:INIT OFF')
                    
                    # Choose which frames to read (all in this example)
                    inst.send_scpi_cmd(':DIG:DATA:SEL ALL')

                    # Choose what to read 
                    inst.send_scpi_cmd(':DIG:DATA:TYPE FRAM')

                    # Get the total data size (in bytes)
                    resp = inst.send_scpi_query(':DIG:DATA:SIZE?')
                    num_bytes = np.uint32(resp)
                    print('Total size in bytes: ' + resp)

                    # Read the data that was captured by DDR 1:
                    inst.send_scpi_cmd(':DIG:CHAN:SEL 2')

                    # because read format is UINT16 we divide byte number by 2
                    wavlen = num_bytes // 2
                    wav1 = np.zeros(wavlen, dtype=np.uint16)
                    rc = inst.read_binary_data(':DIG:DATA:READ?', wav1, num_bytes)
                    resp = inst.send_scpi_query(':SYST:ERR?')
                    print("read data from DDR2")
                    wav1 = np.int32(wav1)
                    wave = wav1[0::2] - 16384
                    samplesI = wave[0::2]
                    samplesQ = wave[1::2]
                    samples = samplesI + 1j *samplesQ
                    num_frames = len(samples) // readLen
                    samples = samples[:num_frames * readLen]  # Trim to full frames only
                    frames = samples.reshape((num_frames, readLen))

                    # NEED TO generate time-axis TODO
                    time_axis = np.concatenate( (), axis = 0)

                    # Compute averages for each frame
                    frame_means = frames.mean(axis=1)  # This will be complex: mean I + 1j*mean Q
                    frame_means_I = frames.real.mean(axis=1)
                    frame_means_Q = frames.imag.mean(axis=1)
                    # After the code that creates 'frames'
                    first_frame = frames[0]

                    plt.figure(figsize=(6, 6))
                    plt.scatter(first_frame.real, first_frame.imag, s= 1, alpha= 1)
                    plt.xlabel('I (Real)')
                    plt.ylabel('Q (Imaginary)')
                    plt.title(f'IQ Plot of First Frame ({readLen} samples)')
                    plt.grid(True)
                    plt.axis('equal')  # Ensures aspect ratio is 1:1
                    plt.show()

                elif cmd_byte == 4:  # Cleanup
                    print("Cleaning up and preparing for the next cycle...")
                    # Perform cleanup operations
                    
                elif cmd_byte == 5:  # Disconnect Instrument
                    print("Disconnecting instrument...")
                    connect = off  # End the loop and disconnect
                    
                elif cmd_byte == 6:  # Program MW Chirp Waveform
                    print("Programming MW Chirp waveform...")
                    # Program the MW Chirp waveform
                    sampleRateDAC = 9e9
                    awg_center_freq = 3e9
                    awg_bw_freq = 100
                    sweep_freq = 1000
                    srs_freq = 1e6
                    bits = 16
                    pol_time = 20
                    fCenter = awg_center_freq - srs_freq
                    fStart, fStop = fCenter - 0.5*awg_bw_freq, fCenter + 0.5*awg_bw_freq
                    rampTime = 1/sweep_freq
                    dac_chan = 2
                    trig_num = 2

                    print("Initializing...")
                    # Initialize the instrument or device
                    inst.reset()
                    inst.initialize_AWG(ch = dac_chan)
                    print("Done initializing.")
                    
                    # generate chirp form
                    seg_dict = {}
                    chirp = makeChirp(sampleRateDAC, rampTime, fStart, fStop, bits)

                    seg_dict[1] = chirp
                    seg_dict[2] = np.flip(chirp)

                    inst.send_scpi_cmd(f':FREQ:RAST {sampleRateDAC}')
                    # DOWNLOAD TWO SEGMENTS
                    for k, dacWave in seg_dict.items():
                        segMem = k
                        inst.download_waveform(inst, dac_chan, segMem, dacWave)
                    
                    #CONTINUOUS MODE ON
                    inst.send_scpi_cmd(":INIT:CONT OFF")
                    inst.send_scpi_cmd(":INIT:CONT ON")

                    #TURN ANY OUTPUT OFF
                    inst.send_scpi_cmd(":OUTP OFF")

                    # TURN ON OUTPUT WITH NCO FREQUENCY SET AS CARRIER FREQUENCY
                    # maybe need to create a image frequency
                    inst.send_scpi_cmd(f":SOUR:NCO:CFR1 {srs_freq}")
                    inst.send_scpi_cmd(':NCO:SIXD1 ON')
                    inst.send_scpi_cmd(':SOUR:MODE DUC')

                    # no interpolation
                    inst.send_scpi_cmd(':SOUR:INT:NONE')

                    #set trigger as source
                    voltage_level = 1
                    inst.send_scpi_cmd(f':TRIG:ACTIVE:SEL TRG{trig_num}')
                    inst.send_scpi_cmd(f':TRIG:LEV {voltage_level}')
                    inst.send_scpi_cmd(':TRIG:ACTIVE:STAT ON')
                    # ret = inst.send_scpi_query(':SOUR:IQM?')
                    # print(ret)
                    # ret = inst.send_scpi_query(':SOUR:INT?')
                    # print(ret)
                    # ret = inst.send_scpi_query(':SOUR:MODE?')
                    # print(ret)

                elif cmd_byte == 7:  # Play MW Chirp Waveform
                    print("Playing MW Chirp waveform...")
                    # Play the MW Chirp waveform
                    # TURN ON OUTPUT
                    inst.send_scpi_cmd(':SOUR:VOLT MAX')
                    inst.send_scpi_cmd(':SOUR:FUNC:MODE TASK')
                    inst.send_scpi_cmd(':OUTP ON')
                    resp = inst.send_scpi_query(':SYST:ERR?')
                    assert int(resp.split(',')[0]) == 0
                    inst.send_scpi_cmd('*TRG')

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