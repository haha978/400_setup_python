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
from teproteus import TEProteusAdmin as TepAdmin
from teproteus_functions_v3 import get_cpatured_header
from teproteus_functions_v3 import connect, disconnect, convert_binoffset_to_signed, printProteusHeader

def makeSqPulse(segLen, amp, phase, sampleRateDAC):
    """
    Make square pulse segment of length segLen
    
    Returns:
        dacWaveI: in-phase component
        dacWaveQ: quadrature component
    """
    assert segLen % 64 == 0, "segment length must be multiple of 64"
    ampI, ampQ = amp, amp
    dt = 1 / sampleRateDAC
    omega = 0
    time = np.arange(0, segLen - 0.5, 1)
    modWave = np.ones(segLen)
    max_dac = 2**16 - 1
    half_dac = np.floor(max_dac / 2)

    dacWaveI_modulation = ampI * np.cos(omega*time/segLen + np.pi*phase/180)
    dacWaveI = half_dac * (np.multiply(dacWaveI_modulation, modWave)+1)

    dacWaveQ_modulation = ampQ * np.sin(omega * time/segLen + np.pi * phase/180)
    dacWaveQ = half_dac * (np.multiply(dacWaveQ_modulation, modWave) + 1)

    return dacWaveI, dacWaveQ

def makeDC(segLen):
    """
    Make DC segment of length segLen
    
    Returns:
        dacWaveI: in-phase component
        dacWaveQ: quadrature component
    """
    assert segLen % 64 == 0, "segment length must be multiple of 64"
    max_dac = np.exp2(16) - 1
    half_dac = np.floor(max_dac/2)

    dacWave = np.zeros(segLen) + half_dac
    dacWaveI, dacWaveQ = dacWave.copy(), dacWave.copy()
    return dacWaveI, dacWaveQ

def main():
    print("Initializing AWG...")
    sid = 8
    ch = 1
    admin = TepAdmin() #required to control PXI module
    inst = admin.open_instrument(slot_id=sid)
    # inst = connect('192.168.0.121')
    resp = inst.send_scpi_query("*IDN?")
    resp = inst.send_scpi_cmd("*RST")
    # set active channel
    inst.send_scpi_cmd(f':INST:CHAN {ch}')
    # pseudo command to use 16 bit mode
    inst.send_scpi_cmd(':FREQ:RAST 2.5E9')
    inst.send_scpi_cmd(':SOUR:VOLT MAX')
    inst.send_scpi_cmd(':INIT:CONT ON')
    inst.send_scpi_cmd(':TRAC:DEL:ALL')
    print("AWG Initialization done.")
    resp = inst.send_scpi_query(":SYSTem:INFormation:FPGA:VERsion? ")
    print(resp)

    sampleRateDAC = 675e6
    interp_factor = 8
    spacing_t, pulse_t = 15e-6, 300e-6
    cfr, phase = 75.38e6, 90
    num_Pulses = 10
    spacingPt = sampleRateDAC * spacing_t // 64 * 64
    lengthPt = sampleRateDAC * pulse_t // 64 * 64
    spacingPt, lengthPt = int(spacingPt), int(lengthPt)
    spacing_I, spacing_Q = makeDC(spacingPt)
    mark_DC, mark_DC2 = np.zeros(spacingPt), np.zeros(spacingPt)
    ON_I, ON_Q = makeSqPulse(segLen = lengthPt, amp = 0.5, phase = 0, sampleRateDAC = sampleRateDAC)
    pulse_I, pulse_Q = np.concatenate((ON_I, spacing_I)), np.concatenate((ON_Q, spacing_Q))
    # GENERATE MARKERS

    mark_IQ, mark_IQ2  = np.zeros(lengthPt) + 1, np.zeros(lengthPt) + 1
    pulse_I, pulse_Q = np.concatenate((ON_I, spacing_I)), np.concatenate((ON_Q, spacing_Q))
    mark1, mark2 = np.concatenate((mark_IQ, mark_DC)).astype(np.uint8), np.concatenate((mark_IQ2, mark_DC2)).astype(np.uint8)
    x = range(len(pulse_I))

    segMem = 1
    print(f"Downloading waveform to channel {ch}, segment {segMem}")
    res = inst.send_scpi_cmd(f':INST:CHAN {ch}')
    dacWave_IQ = np.vstack((pulse_I, pulse_Q)).reshape((-1,), order = 'F')
    inst.send_scpi_cmd(f':TRAC:FORM U16')
    inst.send_scpi_cmd(f':TRAC:DEF {segMem}, {len(dacWave_IQ)}')
    inst.send_scpi_cmd(f":TRAC:SEL {segMem}")
    # Download the binary data to segment
    prefix = '*OPC?; :TRAC:DATA'
    myWfm = dacWave_IQ.astype(np.uint16)
    inst.timeout = 30000
    inst.write_binary_data(prefix, myWfm)
    inst.timeout = 10000
    resp = inst.send_scpi_query(':SYST:ERR?')
    assert int(resp.split(',')[0]) == 0, f"IQ segment not downloaded correctly. Error code: {resp}"

    print(f"Downloading marker to channel: {ch}, segment: {segMem} \n")
    myMkr = np.uint8(mark1 + 2*mark2)

    # set DAC channel
    res = inst.send_scpi_cmd(f':INST:CHAN {ch}')
    assert res == 0, "channel not correctly set"
    inst.send_scpi_cmd(f":TRAC:SEL {segMem}")

    myMkr = myMkr[0::2] + 16 * myMkr[1::2]
    myMkr = myMkr.astype(np.uint8)
    prefix = ':MARK:DATA 0,'
    inst.write_binary_data(prefix, myMkr)
    resp = inst.send_scpi_query(':SYST:ERR?')
    print(resp)
    assert int(resp.split(',')[0]) == 0
    inst.send_scpi_cmd(':MARK:SEL 1')
    inst.send_scpi_cmd(':MARK:STAT ON')
    inst.send_scpi_cmd(':MARK:SEL 2')
    inst.send_scpi_cmd(':MARK:STAT ON')
    resp = inst.send_scpi_query(':SYST:ERR?')
    print(resp)

    print("generate task table")
    inst.send_scpi_cmd(f':INST:CHAN {ch}')
    inst.send_scpi_cmd('TASK:ZERO:ALL')
    inst.send_scpi_cmd(f':TASK:COMP:LENG 1')
    inst.send_scpi_cmd(f':TASK:COMP:SEL 1')
    inst.send_scpi_cmd(f':TASK:COMP:LOOP {num_Pulses}')
    inst.send_scpi_cmd(':TASK:COMP:ENAB CPU')
    inst.send_scpi_cmd(f':TASK:COMP:SEGM 1')
    inst.send_scpi_cmd(f':TASK:COMP:NEXT1 1')
    inst.send_scpi_cmd(':TASK:COMP:TYPE SING')
    inst.send_scpi_cmd(':TASK:COMP:WRITE')
    inst.send_scpi_cmd(':SOUR:FUNC:MODE TASK')

    print("Setting NCO IQ modulation...")
    inst.send_scpi_cmd(f':INST:CHAN {ch}')
    # pseudo command to use 16 bit mode, also for IQ Modulation
    inst.send_scpi_cmd(':FREQ:RAST 2.5E9')

    inst.send_scpi_cmd(f':SOUR:INT X{interp_factor}')

    inst.send_scpi_cmd(':MODE DUC')
    inst.send_scpi_cmd(':IQM ONE')
    # multiply sampleRateDAC by 8 -- the interpolation factor -- and set it to AWG.
    sampleRateDAC = sampleRateDAC * interp_factor
    inst.send_scpi_cmd(f':FREQ:RAST {sampleRateDAC}')
    inst.send_scpi_cmd(':SOUR:NCO:SIXD1 ON')
    inst.send_scpi_cmd(f':SOUR:NCO:CFR1 {cfr}')
    inst.send_scpi_cmd(f':SOUR:NCO:PHAS1 {phase}')
    resp = inst.send_scpi_cmd(':OUTP ON')
    assert resp == 0, "NCO not correctly set"
    print("NCO IQ modulation set.")

    # MODE 0: reading out frames, MODE 1: reading out Header
    # Set to readout header or the full frame
    MODE = 1

    if MODE == 0:
        ret = inst.send_scpi_cmd(':DIG:ACQ:TYPE ALL')
    elif MODE == 1:
        ret = inst.send_scpi_cmd(':DIG:ACQ:TYPE HEAD')  # ALL / HEADers

    ret = inst.send_scpi_query(':DIG:ACQ:TYPE?')
    print(ret)

    sampleRateADC = sampleRateDAC / 4
    numframes = num_Pulses
    # tacq = 50
    # readLen = int(50*1e-6*(2.7*1e9)/4) // 96 * 96
    readLen = 2016 * 2 # = 2016, largest transmission length with granularity of 36 and below 2048/4 for DSP capturing length
    cmd = ':DIG:MODE DUAL'
    inst.send_scpi_cmd(cmd)
    print('ADC Clk Freq {0}'.format(sampleRateADC))
    cmd = ':DIG:FREQ  {0}'.format(sampleRateADC)
    inst.send_scpi_cmd(cmd)
    resp = inst.send_scpi_query(':DIG:FREQ?')
    print("Dig Frequency = ")
    print(resp)

    # Enable capturing data from channel 1
    cmd = ':DIG:CHAN:SEL 1'
    inst.send_scpi_cmd(cmd)
    resp = inst.send_scpi_query(':SYST:ERR?')
    print("Dig error = ")
    print(resp)
    # DDC activation to complex i+jq
    inst.send_scpi_cmd(':DIG:DDC:MODE COMP')
    inst.send_scpi_cmd(':DIG:DDC:CFR1 {0}'.format(cfr))
    inst.send_scpi_cmd(':DIG:DDC:PHAS1 90')
    inst.send_scpi_cmd(':DIG:DDC:CLKS AWG')
    resp = inst.send_scpi_query(':SYST:ERR?')
    print("Set complex error = ")
    print(resp)
    inst.send_scpi_cmd(':DIG:CHAN:STATE ENAB')

    # trigger from external source
    inst.send_scpi_cmd(':DIG:TRIG:SOUR EXT')
    inst.send_scpi_cmd(':DIG:TRIG:SLOP NEG')
    inst.send_scpi_cmd(':DIG:TRIG:LEV1 1')
    inst.send_scpi_cmd(f':DIG:TRIG:DEL:EXT {12e-6}' )
    resp = inst.send_scpi_query(':SYST:ERR?')
    print("Set complex error = ")
    print(resp)

    print(f"numframes = {numframes}, readLen = {readLen}")
    inst.send_scpi_cmd(':DIG:ACQ:DEF {0},{1}'.format(numframes, 2*readLen))
    # inst.send_scpi_cmd(':DIG:ACQ:DEF {0},{1}'.format(numframes, readLen))
    # inst.send_scpi_cmd(f':DIG:ACQ:FRAM:CAPT 1, {numframes}')
    inst.send_scpi_cmd(':DIG:ACQ:FRAM:CAPT:ALL')
    inst.send_scpi_cmd(':DIG:ACQ:ZERO:ALL')

    # Enable capturing data from DDR 1
    inst.send_scpi_cmd(':DIG:CHAN:SEL 1')
    inst.send_scpi_cmd(':DIG:CHAN:STATE ENAB')
    inst.send_scpi_cmd(':DIG:CHAN:RANGe {0}'.format("HIGH"))

    # Enable capturing data from DDR 2
    inst.send_scpi_cmd(':DIG:CHAN:SEL 2')
    inst.send_scpi_cmd(':DIG:CHAN:STATE ENAB')
    inst.send_scpi_cmd(':DIG:CHAN:RANGe {0}'.format("HIGH"))

    inst.send_scpi_cmd(':DIG:DDC:BIND ON')

    # Select to store the DSP1 data
    inst.send_scpi_cmd(':DSP:STOR DSP')  # DIRect | DSP | FFT
    resp = inst.send_scpi_query(':SYST:ERR?')
    print(resp)

    # dsp decision frame
    inst.send_scpi_cmd(':DSP:DEC:FRAM {0}'.format(readLen / 4)) # 2016 / 4 < 512
    resp = inst.send_scpi_query(':SYST:ERR?')
    print(resp)

    print("waiting for input ...")
    input()
    # resp = inst.send_scpi_query(':DIG:ACQuire:FRAM:STATus?')
    print(resp)
    inst.send_scpi_cmd('*TRG')
    max_iter = 12
    frameRx = 0
    times = 0
    FRAME_NMB = numframes
    print("This is number of frames to capture: ", FRAME_NMB)
    while (frameRx < FRAME_NMB):
        # inst.send_scpi_cmd(':DIG:TRIG:IMM')
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
        inst.send_scpi_cmd(':DIG:CHAN:SEL 2')
        # because read format is UINT16 we divide byte number by 2
        wavlen = num_bytes // 2
        wav1 = np.zeros(wavlen, dtype=np.uint16)
        rc = inst.read_binary_data(':DIG:DATA:READ?', wav1, num_bytes)
        resp = inst.send_scpi_query(':SYST:ERR?')
        print(resp)
        print("read data from DDR1")

    if MODE == 0 or MODE == 1:
        read = time.time()
        # Choose what to read
        ret = inst.send_scpi_cmd(':DIG:DATA:TYPE HEAD')
        ret = inst.send_scpi_query(':DIG:DATA:TYPE?')
        print(ret)
        header_size=88
        num_bytes = numframes * header_size
        print('Total Headers size in bytes: {0} '.format(num_bytes))
        header = np.zeros(int(num_bytes), dtype=np.uint8)
        # Read the data that was captured by DDR 1:
        inst.send_scpi_cmd(':DIG:CHAN:SEL 2')
        rc = inst.read_binary_data(':DIG:DATA:READ?', header, num_bytes)
        print("Length of the header buffer")
        print(len(header))
        print("First 800 points of the header")
        print(header[:800])
        resp = inst.send_scpi_query(':SYSTem:INFormation:FPGA:VERsion?')
        print(resp)
    
    proteus_header = get_cpatured_header(printHeader=True,N=10,buf=header,dspEn=True)
    # print(len(proteus_header))
    printProteusHeader(proteus_header, 9, avgEn=True)
    print(proteus_header[1].real1_dec)
    print(proteus_header[1].im1_dec)

    if MODE == 0:
        # wav1 = np.int32(wav1)
        print(wav1)
        print(len(wav1))
        print(len(wav1)/numframes)
        # wave_q = wav1[0:readLen:4]
        # wave_i = wav1[1:readLen:4]
        print("This is readLen: ", readLen)
        print("This is numframes: ", numframes)
        num1 = 19
        wave_q = wav1[int(readLen*(num1-1)):int(readLen*int(num1)):4]
        wave_i = wav1[1+int(readLen*(num1-1)):int(readLen*(num1)):4]
        
        wave_q = np.floor((wave_q / 2))
        wave_i = np.floor((wave_i / 2))
        
        # x=range((int)(readLen / 4))
        # print(len(wave_i))
        # plt.plot(x, wave_q, x, wave_i)
        # plt.show

        wave_q = convert_binoffset_to_signed(wave_q, 15)
        wave_i = convert_binoffset_to_signed(wave_i, 15)
        x=range((int)(readLen / 4))
        print(len(wave_i))
        plt.plot(x, wave_q, x, wave_i)
        plt.show


        # for i in range(500):
        #     print(format(wav1[i], 'x'))
        sum = 0
        for i in range((int)(readLen / 4)):
            sum = sum + wave_i[i]
            # print(wave_i[i], format((int)(wave_i[i]), '#x'), ', ', format((int)(sum), 'x'))
        print(np.sum(wave_i[:(int)(readLen / 4)]))
        print(np.sum(wave_q[:(int)(readLen / 4)]))
        del(wave_i)
        del(wave_q)



if __name__== "__main__":
    main()