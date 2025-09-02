import numpy as np
import scipy as sp

def makeDC(segLen):
    """
    Generate a DC (constant) waveform for both I and Q channels.

    Parameters:
    segLen (int):
        The length of the segment (number of samples). Must be a multiple of 64.

    Returns:
    tuple of np.ndarray:
        (dacWaveI, dacWaveQ) where both are 1D numpy arrays of length segLen,
        filled with the mid-scale DAC value (DC level) for a 16-bit DAC.
        This represents a constant (DC) output for both I and Q channels.

    Example:
        dacWaveI, dacWaveQ = makeDC(6400)
    """
    assert segLen % 64 == 0, "segment length must be multiple of 64"
    max_dac = np.exp2(16) - 1
    half_dac = np.floor(max_dac/2)

    dacWave = np.zeros(segLen) + half_dac
    dacWaveI, dacWaveQ = dacWave.copy(), dacWave.copy()
    return dacWaveI, dacWaveQ

def makeSqPulse(modFreq, segLen, amp, phase, mods, sampleRateDAC):
    assert segLen % 64 == 0, "segment length must be multiple of 64"
    ampI, ampQ = amp, amp
    dt = 1 / sampleRateDAC
    cycles = segLen * dt * modFreq
    time = np.arange(0, segLen - 0.5, 1)
    omega = 2 * np.pi * cycles

    if mods == 0:
        #simple square pulse
        modWave = np.ones(segLen)
    elif mods == 1:
        # plot gaussian -- sigma hardcoded
        timeGauss = np.arange(-segLen/2, segLen/2-0.5, 1)
        sigma = segLen/6
        modWave = np.exp(-0.5*(timeGauss/sigma)**2)
    elif mods == 2:
        # Cosh^(-2) function
        timeCosh = np.arange(-segLen/2, segLen/2-0.5, 1)
        tau= 2.355/1.76*segLen/6
        modWave = np.cosh(timeCosh/tau)**(-2)
    elif mods == 3:
        timeHerm = np.arange(-segLen/2, segLen/2 - 0.5, 1)
        sigma = segLen/6
        factor = 0.667
        modWave = np.multiply((1 - factor*0.5*(timeHerm/sigma)**2), np.exp(-0.5*(timeHerm/sigma)**2))
    else:
        raise ValueError("mods form not valid")
    
    max_dac = 2**16 - 1
    half_dac = np.floor(max_dac / 2)

    dacWaveI_modulation = ampI * np.cos(omega*time/segLen + np.pi*phase/180)
    dacWaveI = half_dac * (np.multiply(dacWaveI_modulation, modWave)+1)

    dacWaveQ_modulation = ampQ * np.sin(omega * time/segLen + np.pi * phase/180)
    dacWaveQ = half_dac * (np.multiply(dacWaveQ_modulation, modWave) + 1)

    return dacWaveI, dacWaveQ

def defPulse(amp, mod, length, phase, spacing):
    """
    Define Pulse

    Parameters:
    amp: amplitude of the pulse when pulse is ON
    mod: shape of the pulse (mod0: square, mod1: gaussian, mod2: cosh^(-2), mod3: Hermite)
    length: length of time in which a pulse is turned on [s]
    phase: phase of the pulse can be any number
    spacing: time in which pulse is OFF after pulse turned off [s]
    
    Returns:
    Dictionary that contains all parameters that realize a pulse
    """
    for num in [amp, mod, length, phase, spacing]:
        assert isinstance(num, (int, float, np.number))
    pulse = {'amp': amp, 'mod': mod, 'length': length, 'phase': phase, 'spacing': spacing} 
    return pulse

def defBlock(pulse_l, reps, markers, trigs):
    """
    Define Block

    Parameters:
    pulse_l: list of pulses
    reps: number of repetition for each pulse in pulse_l (List of int)
    markers: trigger for pulse amplifier for each pulse in pulse_l (0 or 1)
    trigs: trigger for digitizer for each pulse in pulse_l (0 or 1)

    Returns:
    Dictionary that contains all information about a pulse block that can be repeated.
    """
    assert  all([is_pulse(pulse) for pulse in pulse_l]), "pulse_l contains list of pulses"
    assert is_reps(reps) and is_markers(markers) and is_trigs(trigs)
    block = {'pulse_l': pulse_l, 'reps': reps, 'markers': markers, 'trigs': trigs}
    return block

def is_pulse(pulse):
    key_l = {'amp', 'mod', 'length','phase', 'spacing'}
    return key_l == pulse.keys()

def is_reps(reps):
    for rep in reps:
        if isinstance(rep, int) == False:
            return False
    return True

def is_markers(markers):
    for marker in markers:
        if not (marker == 0 or marker == 1):
            print("marker should be 0 or 1")
            return False
    return True

def is_trigs(trigs):
    for trig in trigs:
        if not (trig == 0 or trig == 1):
            print("trigger should be 0 or 1")
            return False
    return True

def is_block(block):
    keys = {'pulse_l', 'reps', 'markers','trigs'}
    if not (keys == block.keys()):
        return False
    if all([is_pulse(pulse) for pulse in block['pulse_l']]) == False:
        return False
    return is_reps(block['reps']) and is_trigs(block['trigs']) and is_markers(block['markers'])

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
