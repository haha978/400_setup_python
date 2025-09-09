import numpy as np
import time
import matplotlib.pyplot as plt
import os
import sys
srcpath = os.path.realpath('D:/400_AWT/400_setup_python/Tabor Library')
sys.path.append(srcpath)
from tevisainst import TEVisaInst
from teproteus import TEProteusAdmin as TepAdmin
from teproteus import TEProteusInst as TepInst
from proteus_utils import makeDC, makeSqPulse

class TaborProteus:
    @staticmethod
    def proteus_instance():
        # Connect to instrument via PXI
        admin = TepAdmin()
        # Get list of available PXI slots
        slot_ids = admin.get_slot_ids()
        # Assume that at least one slot was found
        sid = slot_ids[0]
        # Open a single-slot instrument:
        inst = admin.open_instrument(slot_id=sid)
        return inst

    def __init__(self, sampleRateDAC = 675e6, sampleRateADC = 2.7e9, bits = 16, interp = 8, adcChan = 1, dacChan = 1):
        # initialize Proteus Parameters
        self.inst = self.proteus_instance()
        self._sampleRateDAC = sampleRateDAC
        self._sampleRateADC = sampleRateADC
        self._bits = bits
        self._interp = interp
        self._adcChan = adcChan
        self._dacChan = dacChan
    
    # Getter and Setter for sampleRateDAC
    @property
    def sampleRateDAC(self):
        return self._sampleRateDAC
    
    @sampleRateDAC.setter
    def sampleRateDAC(self, value):
        self._sampleRateDAC = value

    # Getter and Setter for sampleRate for the digitizer
    @property
    def sampleRateADC(self):
        return self._sampleRateADC
    
    @sampleRateADC.setter
    def sampleRateADC(self, value):
        self._sampleRateADC = value

    @property
    def interp(self):
        return self._interp
    
    @interp.setter
    def interp(self, value):
        self._interp = value

    # Getter and Setter for ADC Channel
    @property
    def adcChan(self):
        return self._adcChan
    
    @adcChan.setter
    def adcChan(self, value):
        assert value == 1 or value == 2, "Digitizer's channel should be 1 or 2."
        self._adcChan = value

    @property
    def dacChan(self):
        return self._dacChan
    
    @dacChan.setter
    def dacChan(self, value):
        self._dacChan = value

    def reset(self):
        """
        Resets the Proteus
        """
        # Get the instrument's *IDN
        inst = self.inst
        resp = inst.send_scpi_query('*IDN?')
        print('Connected to: ' + resp)

        # Get the model name
        resp = inst.send_scpi_query(":SYST:iNF:MODel?")
        print("Model: " + resp)

        resp = inst.send_scpi_cmd('*CLS; *RST')
        print("Reset complete")
    
    def downloadIQ(self, ch, segMem, dacWaveI, dacWaveQ):
        """
        Downloads IQ waveform data to the specified channel and segment.
        
        This function interleaves I and Q data and downloads it to the AWG's
        segment memory. The data is formatted as 16-bit unsigned integers.
        
        Args:
            ch (int): Channel number to download waveform to
            segMem (int): Segment memory number
            dacWaveI (numpy.ndarray): In-phase (I) component of the waveform
            dacWaveQ (numpy.ndarray): Quadrature (Q) component of the waveform
            
        Note:
            - Data is converted to 16-bit unsigned integers for AWG compatibility
            - Timeout is temporarily increased to 30s for large data transfers
        """
        inst = self.inst
        print(f"Downloading waveform to channel {ch}, segment {segMem}")
        
        self.dacChan = ch
        res = inst.send_scpi_cmd(f':INST:CHAN {ch}')

        # Interleave I and Q data using Fortran-style ordering (column-major)
        dacWave_IQ = np.vstack((dacWaveI, dacWaveQ)).reshape((-1,), order = 'F')
        inst.send_scpi_cmd(f':TRAC:FORM U16')
        inst.send_scpi_cmd(f':TRAC:DEF {segMem}, {len(dacWave_IQ)}')
        inst.send_scpi_cmd(f':TRAC:SEL {segMem}')

        # Download the binary data to segment with increased timeout for large transfers
        prefix = '*OPC?; :TRAC:DATA'
        myWfm = dacWave_IQ.astype(np.uint16)
        inst.timeout = 30000
        inst.write_binary_data(prefix, myWfm)
        inst.timeout = 10000
        resp = inst.send_scpi_query(':SYST:ERR?')
        assert int(resp.split(',')[0]) == 0, f"IQ segment not downloaded correctly. Error code: {resp}"

    def download_waveform(self, ch, segMem, dacWave):
        print(f"Downloading segment: {segMem}, channel: {ch}")
        inst = self.inst
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

    def download_marker(self, ch, segMem, mark1, mark2):
        """
        Downloads marker data to the specified channel and segment.
        
        This function should always be called after the corresponding downloadIQ function
        because markers are associated with specific waveform segments and need the
        segment to be properly defined first.
        
        Args:
            ch (int): Channel number to download marker to
            segMem (int): Segment memory number
            mark1 (numpy.ndarray): First marker data array
            mark2 (numpy.ndarray): Second marker data array
            
        Note:
            - Markers are used for triggering external devices or synchronization
            - The marker data is combined as: mark1 + 2*mark2
            - Both markers are enabled after download
        """
        inst = self.inst
        print(f"Downloading marker to channel: {ch}, segment: {segMem} \n")
        myMkr = np.uint8(mark1 + 2*mark2)
        # set DAC channel
        self.dacChan = ch
        res = inst.send_scpi_cmd(f':INST:CHAN {ch}')
        assert res == 0, "channel not correctly set"
        inst.send_scpi_cmd(f":TRAC:SEL {segMem}")
        myMkr = myMkr[0::2] + 16 * myMkr[1::2]
        myMkr = myMkr.astype(np.uint8)
        prefix = ':MARK:DATA 0,'
        inst.write_binary_data(prefix, myMkr)
        resp = inst.send_scpi_query(':SYST:ERR?')
        assert int(resp.split(',')[0]) == 0
        inst.send_scpi_cmd(':MARK:SEL 1')
        # delete below line once update
        inst.send_scpi_cmd(':MARK:VOLT:PTOP 1')
        inst.send_scpi_cmd(':MARK:STAT ON')
        inst.send_scpi_cmd(':MARK:SEL 2')

        # delete below line once update
        inst.send_scpi_cmd(':MARK:VOLT:PTOP 1')
        inst.send_scpi_cmd(':MARK:STAT ON')
        resp = inst.send_scpi_query(':SYST:ERR?')
        assert int(resp.split(',')[0]) == 0

    def makeBlocks(self, block_l, ch, repeatSeq):
        inst = self.inst
        assert len(block_l) == len(repeatSeq), "length of the array"
        numBlocks = len(block_l)
        numPulses = 0
        lengthPts = []
        spacingsPts = []
        seg_dict = {}

        # holding segment
        DClen = 64
        holdI, holdQ = makeDC(DClen)
        markHold = np.zeros(DClen).astype(np.uint8)

        # Flatten the pulse list from the block_l
        seg_num = 1
        self.downloadIQ(ch, seg_num, holdI, holdQ)
        self.download_marker(ch, seg_num, markHold, markHold)
        seg_num = seg_num + 1
        for block in block_l:
            pulse_l = block['pulse_l']
            markers = block['markers']
            trigs = block['trigs']
            for pulse_idx, pulse in enumerate(pulse_l):
                #hard coded for now
                spacingPt = self.sampleRateDAC * pulse['spacing'] // 64 * 64
                lengthPt = self.sampleRateDAC * pulse['length'] // 64 * 64
                spacingPt, lengthPt = int(spacingPt), int(lengthPt)

                print(f"This is new pulse length for pulse: {pulse_idx}")
                pulse_len = lengthPt / self.sampleRateDAC
                spacing_len = spacingPt / self.sampleRateDAC
                pulse['length'], pulse['spacing'] = pulse_len, spacing_len

                spacing_I, spacing_Q = makeDC(spacingPt)
                mark_DC, mark_DC2 = np.zeros(spacingPt), np.zeros(spacingPt)
                
                # Make Pulse
                ON_I, ON_Q = makeSqPulse(modFreq = 0, segLen = lengthPt, amp = pulse['amp'], \
                                    phase = pulse['phase'], mods = pulse['mod'], sampleRateDAC = self.sampleRateDAC)
                mark_IQ, mark_IQ2  = np.zeros(lengthPt) + markers[pulse_idx], np.zeros(lengthPt) + trigs[pulse_idx]
                pulse_I, pulse_Q = np.concatenate((ON_I, spacing_I)), np.concatenate((ON_Q, spacing_Q))
                mark1, mark2 = np.concatenate((mark_IQ, mark_DC)).astype(np.uint8), np.concatenate((mark_IQ2, mark_DC2)).astype(np.uint8)

                # downloadIQ and download_marker
                self.downloadIQ(ch, seg_num, pulse_I, pulse_Q)
                self.download_marker(ch, seg_num, mark1, mark2)
                seg_num = seg_num + 1
        self.downloadIQ(ch, seg_num, holdI, holdQ)
        self.download_marker(ch, seg_num, markHold, markHold)
        self.setTask_Pulse(block_l, ch, numSegs = seg_num, repeatSeq=repeatSeq)

    def setTask_Pulse(self, block_l, ch, numSegs, repeatSeq):
        print('setting task table')
        inst = self.inst
        SEGM_num = 1
        inst.send_scpi_cmd(f':INST:CHAN {ch}')
        self.dacChan = ch
        inst.send_scpi_cmd('TASK:ZERO:ALL')
        inst.send_scpi_cmd(f':TASK:COMP:LENG {numSegs}')
        inst.send_scpi_cmd(f':TASK:COMP:SEL {SEGM_num}')
        inst.send_scpi_cmd(':TASK:COMP:LOOP 1')
        inst.send_scpi_cmd(':TASK:COMP:ENAB CPU')
        inst.send_scpi_cmd(f':TASK:COMP:SEGM {SEGM_num}')
        inst.send_scpi_cmd(f':TASK:COMP:NEXT1 {SEGM_num+1}')
        inst.send_scpi_cmd(':TASK:COMP:TYPE SING')
        SEGM_num += 1
        for b_idx, block in enumerate(block_l):
            pulse_l, reps, trigs = block['pulse_l'], block['reps'], block['trigs']
            for p_idx in range(len(pulse_l)):
                inst.send_scpi_cmd(f':TASK:COMP:SEL {SEGM_num}')
                inst.send_scpi_cmd(f':TASK:COMP:SEGM {SEGM_num}')
                inst.send_scpi_cmd(f':TASK:COMP:LOOP {reps[p_idx]}')
                
                if repeatSeq[b_idx] > 1 and p_idx == 0:
                    inst.send_scpi_cmd('TASK:COMP:TYPE STAR')
                    inst.send_scpi_cmd(f':TASK:COMP:SEQ {repeatSeq[b_idx]}')
                elif repeatSeq[b_idx] > 1 and p_idx != (len(pulse_l) - 1):
                    inst.send_scpi_cmd('TASK:COMP:TYPE SEQ')
                elif repeatSeq[b_idx] > 1 and p_idx == (len(pulse_l) - 1):
                    inst.send_scpi_cmd('TASK:COMP:TYPE END')
                else:
                    inst.send_scpi_cmd(':TASK:COMP:TYPE SING')
                inst.send_scpi_cmd(f':TASK:COMP:NEXT1 {SEGM_num+1}')
                SEGM_num += 1
        
        inst.send_scpi_cmd(f':TASK:COMP:SEL {SEGM_num}')
        inst.send_scpi_cmd(':TASK:COMP:LOOP 1')
        inst.send_scpi_cmd(':TASK:COMP:ENAB CPU')
        inst.send_scpi_cmd(f':TASK:COMP:SEGM {SEGM_num}')
        inst.send_scpi_cmd(':TASK:COMP:NEXT1 1')
        inst.send_scpi_cmd(':TASK:COMP:TYPE SING')

        inst.send_scpi_cmd(':TASK:COMP:WRITE')
        inst.send_scpi_cmd(':SOUR:FUNC:MODE TASK')
    
    def initialize_AWG(self, ch):
        print("Initializing AWG...")
        inst = self.inst
        # set active channel
        inst.send_scpi_cmd(f':INST:CHAN {ch}')
        self.dacChan = ch
        # pseudo command to use 16 bit mode
        inst.send_scpi_cmd(':FREQ:RAST 2.5E9')
        inst.send_scpi_cmd(':SOUR:VOLT MAX')
        inst.send_scpi_cmd(':INIT:CONT ON')
        inst.send_scpi_cmd(':TRAC:DEL:ALL')
        print("AWG Initialization done.")
    
    def set_NCO(self, cfr, phase):
        print("Setting NCO...")
        inst = self.inst
        inst.send_scpi_cmd(':SOUR:NCO:SIXD1 ON')
        inst.send_scpi_cmd(f':SOUR:NCO:CFR1 {cfr}')
        inst.send_scpi_cmd(f':SOUR:NCO:PHAS1 {phase}')
        resp = inst.send_scpi_cmd(':OUTP ON')
        assert resp == 0, "NCO not correctly set"
        print("NCO IQ modulation set.")

    def set_interpolation(self, ch, interp_factor):
        """
        Returns new DAC's sample rate.
        """
        inst = self.inst
        print("Setting Interpolation...")
        inst.send_scpi_cmd(f':INST:CHAN {ch}')
        self.dacChan = ch
        # pseudo command to use 16 bit mode, also for IQ Modulation
        inst.send_scpi_cmd(':FREQ:RAST 2.5E9')

        inst.send_scpi_cmd(f':SOUR:INT X{interp_factor}')

        inst.send_scpi_cmd(':MODE DUC')
        inst.send_scpi_cmd(':IQM ONE')
        # multiply sampleRateDAC by 8 -- the interpolation factor -- and set it to AWG.
        self.sampleRateDAC = self.sampleRateDAC * interp_factor
        inst.send_scpi_cmd(f':FREQ:RAST {self.sampleRateDAC}')
        print("Done setting interpolation factor.")
        return self.sampleRateDAC
        
    def set_digitizer(self, sampleRateADC, numframes, cfr, tacq, acq_delay, ADC_ch):
        inst = self.inst
        readLen = int(tacq*(sampleRateADC)/16) // 96 * 96
        cmd = ':DIG:MODE DUAL'
        inst.send_scpi_cmd(cmd)
        print('ADC Clk Freq {0}'.format(sampleRateADC))
        cmd = ':DIG:FREQ  {0}'.format(sampleRateADC)
        inst.send_scpi_cmd(cmd)
        resp = inst.send_scpi_query(':DIG:FREQ?')
        print("Dig Frequency = ")
        print(resp)

        # Enable capturing data from channel 1
        cmd = f':DIG:CHAN:SEL {ADC_ch}'
        inst.send_scpi_cmd(cmd)
        self.adcChan = ADC_ch
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
        
        # This trig level needs to change for the updated software and firmware
        inst.send_scpi_cmd(':DIG:TRIG:LEV1 1.0')
        inst.send_scpi_cmd(f':DIG:TRIG:DEL:EXT {acq_delay}' )
        resp = inst.send_scpi_query(':SYST:ERR?')
        print("Set complex error = ")
        print(resp)
        inst.send_scpi_cmd(':DIG:DDC:DEC X16')

        print(f"numframes = {numframes}, readLen = {readLen}")
        inst.send_scpi_cmd(':DIG:ACQ:DEF {0},{1}'.format(numframes, 2*readLen))
        inst.send_scpi_cmd(':DIG:ACQ:FRAM:CAPT:ALL')
        inst.send_scpi_cmd(':DIG:ACQ:ZERO:ALL')
        ################################################################################
        # Start the digitizer's capturing machine
        inst.send_scpi_cmd(':DIG:INIT OFF')
        inst.send_scpi_cmd(':DIG:INIT ON')
        return readLen, numframes
    
    def send_scpi_cmd(self, cmd):
        self.inst.send_scpi_cmd(cmd)
        
    def send_scpi_query(self, cmd):
        return self.inst.send_scpi_query(cmd)
    
    def read_binary_data(self, cmd, data, num_bytes):
        return self.inst.read_binary_data(cmd, data, num_bytes)

    def set_chirp_tasktable(self, ch, segMem, num_reps):
        inst = self.inst
        reps_per_entry = int(1e6)
        num_full_reps = num_reps // reps_per_entry
        num_left = num_reps % reps_per_entry
        num_total_entries = num_full_reps + (1 if num_left else 0)

        inst.send_scpi_cmd(f':INST:CHAN {ch}')
        inst.send_scpi_cmd('TASK:ZERO:ALL')
        inst.send_scpi_cmd(f':TASK:COMP:LENG {num_total_entries}')
        inst.send_scpi_cmd(':TASK:COMP:ENAB CPU')

        segNum = 1
        for _ in range(int(num_full_reps)):
            inst.send_scpi_cmd(f':TASK:COMP:SEL {segMem}')
            inst.send_scpi_cmd(f':TASK:COMP:LOOP {reps_per_entry}')
            inst.send_scpi_cmd(f':TASK:COMP:SEGM {segNum}')
            inst.send_scpi_cmd(':TASK:COMP:TYPE SING')
            inst.send_scpi_cmd(f':TASK:COMP:NEXT1 {segNum+1}')
            segNum += 1

        if num_left:
            inst.send_scpi_cmd(f':TASK:COMP:SEL {segMem}')
            inst.send_scpi_cmd(f':TASK:COMP:LOOP {int(num_left)}')
            inst.send_scpi_cmd(f':TASK:COMP:SEGM {segNum}')
            inst.send_scpi_cmd(':TASK:COMP:TYPE SING')
            inst.send_scpi_cmd(f':TASK:COMP:NEXT1 0')
        inst.send_scpi_cmd(':TASK:COMP:WRITE')
        inst.send_scpi_cmd(':SOUR:FUNC:MODE TASK')
    
    def set_chirp_tasktable_trig(self, ch, segMem, num_reps, trig_num):
        inst = self.inst
        reps_per_entry = int(1e6)
        num_full_reps = num_reps // reps_per_entry
        num_left = num_reps % reps_per_entry
        num_total_entries = num_full_reps + (1 if num_left else 0)

        inst.send_scpi_cmd(f':INST:CHAN {ch}')
        inst.send_scpi_cmd('TASK:ZERO:ALL')
        inst.send_scpi_cmd(f':TASK:COMP:LENG {num_total_entries}')
        inst.send_scpi_cmd(f':TASK:COMP:ENAB TRG{int(trig_num)}')

        segNum = 1
        for _ in range(int(num_full_reps)):
            inst.send_scpi_cmd(f':TASK:COMP:SEL {segMem}')
            inst.send_scpi_cmd(f':TASK:COMP:LOOP {reps_per_entry}')
            inst.send_scpi_cmd(f':TASK:COMP:SEGM {segNum}')
            inst.send_scpi_cmd(':TASK:COMP:TYPE SING')
            inst.send_scpi_cmd(f':TASK:COMP:NEXT1 {segNum+1}')
            segNum += 1

        if num_left:
            inst.send_scpi_cmd(f':TASK:COMP:SEL {segMem}')
            inst.send_scpi_cmd(f':TASK:COMP:LOOP {int(num_left)}')
            inst.send_scpi_cmd(f':TASK:COMP:SEGM {segNum}')
            inst.send_scpi_cmd(':TASK:COMP:TYPE SING')
            inst.send_scpi_cmd(f':TASK:COMP:NEXT1 0')
        inst.send_scpi_cmd(':TASK:COMP:WRITE')
        inst.send_scpi_cmd(':SOUR:FUNC:MODE TASK')