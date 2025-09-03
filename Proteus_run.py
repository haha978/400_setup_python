import numpy as np
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

def generate_chirp(inst):
    sampleRateDAC = 1.125e9
    ch = 1
    awg_center_freq = 30000
    awg_bw_freq = 10000
    sweep_freq = 100
    srs_freq = 0
    bits = 16
    pol_time = 20
    fCenter = awg_center_freq - srs_freq
    fStart, fStop = fCenter - 0.5*awg_bw_freq, fCenter + 0.5*awg_bw_freq
    rampTime = 1/sweep_freq
    inst.initialize_AWG(ch = 1)
    # set sampleRateDAC
    inst.sampleRateDAC = sampleRateDAC
    # already rounded to 64 samples
    dacWave= makeChirp(sampleRateDAC, rampTime, fStart, fStop, bits)
    # you first have to make chirp
    seg_dict = {}
    seg_dict[1] = dacWave
    seg_dict[2] = np.flip(dacWave)
    for k, dacWave in seg_dict.items():
        inst.downloadIQ(ch = 1, segMem = k, dacWaveI = dacWave, dacWaveQ = dacWave)
    chirp_time = len(dacWave) / sampleRateDAC
    num_reps = int(pol_time//chirp_time)
    
    #CONTINUOUS MODE ON
    inst.send_scpi_cmd(":INIT:CONT OFF")
    inst.send_scpi_cmd(":INIT:CONT ON")
    #TURN ANY OUTPUT OFF
    inst.send_scpi_cmd(":OUTP OFF")
    inst.set_chirp_tasktable(ch = 1, segMem = 1, num_reps=num_reps)
    inst.set_interpolation(ch = 1, interp_factor = 8)
    inst.set_NCO(cfr = srs_freq, phase = 0)
    # TURN ON OUTPUT
    inst.send_scpi_cmd(':SOUR:VOLT MAX')
    inst.send_scpi_cmd(':OUTP ON')
    resp = inst.send_scpi_query(':SYST:ERR?')
    print(resp)
    assert int(resp.split(',')[0]) == 0
    inst.send_scpi_cmd('*TRG')
    
def generate_chirp_external_trigger(inst):
    sampleRateDAC = 1.125e9
    ch = 1
    trig_num = 2
    awg_center_freq = 30000
    awg_bw_freq = 10000
    sweep_freq = 100
    srs_freq = 0
    bits = 16
    pol_time = 20
    fCenter = awg_center_freq - srs_freq
    fStart, fStop = fCenter - 0.5*awg_bw_freq, fCenter + 0.5*awg_bw_freq
    rampTime = 1/sweep_freq
    inst.initialize_AWG(ch = 1)
    # set sampleRateDAC
    inst.sampleRateDAC = sampleRateDAC
    # already rounded to 64 samples
    dacWave= makeChirp(sampleRateDAC, rampTime, fStart, fStop, bits)
    # you first have to make chirp
    seg_dict = {}
    seg_dict[1] = dacWave
    seg_dict[2] = np.flip(dacWave)
    for k, dacWave in seg_dict.items():
        inst.downloadIQ(ch = 1, segMem = k, dacWaveI = dacWave, dacWaveQ = dacWave)
    chirp_time = len(dacWave) / sampleRateDAC
    num_reps = int(pol_time//chirp_time)
    
    #CONTINUOUS MODE ON
    inst.send_scpi_cmd(":INIT:CONT OFF")
    inst.send_scpi_cmd(":INIT:CONT ON")
    #TURN ANY OUTPUT OFF
    inst.send_scpi_cmd(":OUTP OFF")
    
    #set trigger as source
    voltage_level = 1
    inst.send_scpi_cmd(f':TRIG:ACTIVE:SEL TRG{trig_num}')
    inst.send_scpi_cmd(f':TRIG:LEV {voltage_level}')
    inst.send_scpi_cmd(':TRIG:ACTIVE:STAT ON')
    
    inst.set_chirp_tasktable_trig(ch = 1, segMem = 1, num_reps=num_reps, trig_num = trig_num)
    inst.set_interpolation(ch = 1, interp_factor = 8)
    inst.set_NCO(cfr = srs_freq, phase = 0)
    # TURN ON OUTPUT
    inst.send_scpi_cmd(':SOUR:VOLT MAX')
    inst.send_scpi_cmd(':OUTP ON')
    resp = inst.send_scpi_query(':SYST:ERR?')
    print(resp)
    assert int(resp.split(',')[0]) == 0
    breakpoint()

def generate_pulses(inst):
    sampleRateDAC = 1.125e9
    sampleRateADC = 2.25e9
    ADC_ch = 1
    num_Pulses = 5
    cfr = 100e6
    inst.reset()
    inst.initialize_AWG(ch = 1)
    # Set sample rate for ADC and DAC
    inst.sampleRateDAC, inst.sampleRateADC = sampleRateDAC, sampleRateADC
    p1 = defPulse(amp = 1, mod = 0, length = 100e-6, phase = 90, spacing = 100e-6)
    p2 = defPulse(amp = 1, mod = 0, length = 100e-6, phase = 90, spacing = 100e-6)
    b1 = defBlock([p1, p2], reps = [num_Pulses, num_Pulses], markers = [1, 1], trigs = [1, 1])
    b2 = defBlock([p1, p2], reps = [num_Pulses, num_Pulses], markers = [1, 1], trigs = [1, 1])
    inst.makeBlocks([b1, b2], 1, [10000, 10000])
    inst.set_interpolation(ch = 1, interp_factor = 8)
    inst.set_NCO(cfr = 75.38e6, phase = 90)
    numFrames = (b1['reps'][0] + b1['reps'][1])*10000 + (b2['reps'][0] + b2['reps'][1])*10000
    readout_data(inst, 0, cfr, numFrames, ADC_ch)

def readout_data(inst, MODE, cfr, numframes, ADC_ch):
    #need to wait before we apply this TRIG
    # # Digitizer mode -- need this in the updated FW.
    # if MODE == 0:
    #     ret = inst.send_scpi_cmd(':DIG:ACQ:TYPE ALL')
    # elif MODE == 1:
    #     ret = inst.send_scpi_cmd(':DIG:ACQ:TYPE HEAD')  # ALL / HEADers

    # ret = inst.send_scpi_query(':DIG:ACQ:TYPE?')
    
     # SET DIGITIZER
    assert inst.sampleRateDAC / 4 == inst.sampleRateADC, "sampleRateDAC must be set multiple of 4"
    tacq, acq_delay = 10e-6, 12e-6
    readLen, numframes= inst.set_digitizer(inst.sampleRateADC, numframes, cfr, tacq, acq_delay, ADC_ch)
    inst.send_scpi_query(':DIG:ACQuire:FRAM:STATus?')
    breakpoint()
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
        
    if MODE == 0:
        # Choose which frames to read (all in this example)
        inst.send_scpi_cmd(':DIG:DATA:SEL ALL')

        # Choose what to read 
        # (BOTH for frames and headers, FRAM only the frame-data without the header)
        inst.send_scpi_cmd(':DIG:DATA:TYPE FRAM')

        # Get the total data size (in bytes)
        resp = inst.send_scpi_query(':DIG:DATA:SIZE?')
        num_bytes = np.uint32(resp)
        print('Total size in bytes: ' + resp)

        # Read the data that was captured by DDR 1:
        inst.send_scpi_cmd(':DIG:CHAN:SEL 1')
        # because read format is UINT16 we divide byte number by 2
        wavlen = num_bytes // 2
        wav1 = np.zeros(wavlen, dtype=np.uint16)
        rc = inst.read_binary_data(':DIG:DATA:READ?', wav1, num_bytes)
        resp = inst.send_scpi_query(':SYST:ERR?')
        print("read data from DDR1")
        wav1 = np.int32(wav1)
        wave = wav1[0::2] - 16384
        samplesI = wave[0::2]
        samplesQ = wave[1::2]
        samples = samplesI + 1j *samplesQ
        num_frames = len(samples) // readLen
        samples = samples[:num_frames * readLen]  # Trim to full frames only
        frames = samples.reshape((num_frames, readLen))

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

def main():
    inst = TaborProteus()
    generate_pulses(inst)

if __name__ == '__main__':
    main()