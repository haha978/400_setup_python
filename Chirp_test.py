import sys
import os
# please change the source path appropriately
srcpath = os.path.realpath('D:/400_AWT/400_setup_python/Tabor Library/')
print(srcpath)
sys.path.append(srcpath)
from tevisainst import TEVisaInst
import matplotlib.pyplot as plt
import numpy as np
import time
from TaborProteus import TaborProteus
import scipy as sp
from teproteus import TEProteusAdmin as TepAdmin
from teproteus_functions_v3 import get_cpatured_header
from teproteus_functions_v3 import connect, disconnect

def ampScale(bits, rawSignal):
    rawSignal = np.array(rawSignal)
    verticalScale = np.exp2(bits-1) - 1
    vertScaled = (rawSignal / np.max(rawSignal)) * verticalScale
    dacSignal = vertScaled + verticalScale
    return dacSignal

def makeChirp(sampleRateDAC, rampTime, fStart, fStop, bits):
    dt = 1/sampleRateDAC
    t = np.arange(0, rampTime + dt/2, dt)
    # round t to valid number
    t = t[:len(t)//64 * 64]
    dacWave = sp.signal.chirp(t, fStart, np.max(t), fStop)
    dacWave = ampScale(bits, dacWave)
    return dacWave

def download_waveform(inst, ch, segMem, dacWave):
    print(f"Downloading segment: {segMem}, channel: {ch}")
    res = inst.send_scpi_cmd(f':INST:CHAN {ch}')
    # inst.send_scpi_cmd(f':TRAC:FORM U16')
    inst.send_scpi_cmd(f':TRAC:DEF {segMem}, {len(dacWave)}')
    inst.send_scpi_cmd(f':TRAC:SEL {segMem}')
    
    # Download the binary data to segment
    prefix = '*OPC?; :TRAC:DATA'
    dacWave = dacWave.astype(np.uint16)
    inst.timeout = 30000
    inst.write_binary_data(prefix, dacWave)
    inst.timeout = 10000
    resp = inst.send_scpi_query(':SYST:ERR?')
    assert int(resp.split(',')[0]) == 0, f"IQ segment not downloaded correctly. Error code: {resp}"

def chirp_wout_trig():
    print("Initializing AWG...")
    sid = 8
    ch = 3
    inst = TaborProteus()
    inst.send_scpi_cmd("*CLS")
    resp = inst.send_scpi_cmd("*RST")
    inst.send_scpi_cmd(f':INST:CHAN {ch}')
    # pseudo command to use 16 bit mode
    inst.send_scpi_cmd(':FREQ:RAST 2.5E9')
    inst.send_scpi_cmd(':SOUR:VOLT MAX')
    inst.send_scpi_cmd(':INIT:CONT ON')
    inst.send_scpi_cmd(':TRAC:DEL:ALL')

    sampleRateDAC = 9e9
    awg_center_freq = 3e6
    awg_bw_freq = 100
    sweep_freq = 1000
    srs_freq = 1e6
    bits = 16
    pol_time = 20

    fCenter = awg_center_freq - srs_freq
    fStart, fStop = fCenter - 0.5*awg_bw_freq, fCenter + 0.5*awg_bw_freq
    rampTime = 1/sweep_freq

    seg_dict = {}
    chirp = makeChirp(sampleRateDAC, rampTime, fStart, fStop, bits)

    seg_dict[1] = chirp
    seg_dict[2] = np.flip(chirp)

    inst.send_scpi_cmd(f':FREQ:RAST {sampleRateDAC}')
    # DOWNLOAD TWO SEGMENTS
    for k, dacWave in seg_dict.items():
        segMem = k
        download_waveform(inst, ch, segMem, dacWave)
    

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
    
    ret = inst.send_scpi_query(':SOUR:IQM?')
    print(ret)
    ret = inst.send_scpi_query(':SOUR:INT?')
    print(ret)
    ret = inst.send_scpi_query(':SOUR:MODE?')
    print(ret)

    
    # FIRST JUST REPEAT 1 segment and see what happens
    print("generate task table")
    num_cycles = int(np.floor(pol_time * sweep_freq))
    print(num_cycles)
    print(ch)
    inst.send_scpi_cmd(f':INST:CHAN {ch}')
    inst.send_scpi_cmd('TASK:ZERO:ALL')
    inst.send_scpi_cmd(f':TASK:COMP:LENG 1')
    inst.send_scpi_cmd(f':TASK:COMP:SEL 1')
    inst.send_scpi_cmd(f':TASK:COMP:LOOP {num_cycles}')
    inst.send_scpi_cmd(':TASK:COMP:ENAB CPU')
    inst.send_scpi_cmd(f':TASK:COMP:SEGM 1')
    inst.send_scpi_cmd(f':TASK:COMP:NEXT1 1')
    inst.send_scpi_cmd(':TASK:COMP:TYPE SING')
    inst.send_scpi_cmd(':TASK:COMP:WRITE')
    inst.send_scpi_cmd(':SOUR:FUNC:MODE TASK')


    # TURN ON OUTPUT
    inst.send_scpi_cmd(':SOUR:VOLT MAX')
    inst.send_scpi_cmd(':SOUR:FUNC:MODE TASK')
    breakpoint()
    inst.send_scpi_cmd(':OUTP ON')
    resp = inst.send_scpi_query(':SYST:ERR?')
    print(resp)
    
    inst.send_scpi_cmd('*TRG')

def chirp_w_trig():
    print("Initializing AWG...")
    sid = 8
    ch = 3
    inst = TaborProteus()
    print("Programming MW Chirp waveform...")
    # Program the MW Chirp waveform
    sampleRateDAC = 9e9
    awg_center_freq = 3e6
    awg_bw_freq = 100
    sweep_freq = 1000
    srs_freq = 1e6
    bits = 16
    pol_time = 40
    fCenter = awg_center_freq - srs_freq
    fStart, fStop = fCenter - 0.5*awg_bw_freq, fCenter + 0.5*awg_bw_freq
    rampTime = 1/sweep_freq
    dac_chan = 3
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
        inst.download_waveform(dac_chan, segMem, dacWave)
    
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

    #set trigger as source
    voltage_level = 1
    inst.send_scpi_cmd(f':TRIG:ACTIVE:SEL TRG{trig_num}')
    inst.send_scpi_cmd(f':TRIG:LEV {voltage_level}')
    inst.send_scpi_cmd(':TRIG:ACTIVE:STAT ON')
    num_cycles = int(np.floor(pol_time * sweep_freq))
    
    inst.set_chirp_tasktable_trig(ch = dac_chan, segMem = 1, num_reps = num_cycles, trig_num = trig_num)

    # TURN ON OUTPUT WITH NCO FREQUENCY SET AS CARRIER FREQUENCY
    # TURN ON OUTPUT
    inst.send_scpi_cmd(':SOUR:VOLT MAX')
    inst.send_scpi_cmd(':SOUR:FUNC:MODE TASK')
    breakpoint()
    inst.send_scpi_cmd(':OUTP ON')
    resp = inst.send_scpi_query(':SYST:ERR?')
    print(resp)
    breakpoint()
    inst.send_scpi_cmd(':OUTP OFF')

def main():
    chirp_w_trig()

if __name__ == "__main__":
    main()