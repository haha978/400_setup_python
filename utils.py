import numpy as np

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

def get_pulse(on_t, off_t, phase, sampleRateDAC):
    lengthPt = int(sampleRateDAC * on_t // 64 * 64)
    spacingPt = int(sampleRateDAC * off_t // 64 * 64)
    spacing_I, spacing_Q = makeDC(spacingPt)
    ON_I, ON_Q = makeSqPulse(segLen = lengthPt, amp = 0.5, phase = 0, sampleRateDAC = sampleRateDAC)
    pulse_I, pulse_Q = np.concatenate((ON_I, spacing_I)), np.concatenate((ON_Q, spacing_Q))
    dacWave_IQ = np.vstack((pulse_I, pulse_Q)).reshape((-1,), order = 'F')
    return dacWave_IQ

def get_markers(on_t, off_t, sampleRateDAC):
    lengthPt = int(sampleRateDAC * on_t // 64 * 64)
    spacingPt = int(sampleRateDAC * off_t // 64 * 64)
    mark_on1, mark_on2  = np.ones(lengthPt), np.ones(lengthPt)
    mark_off1, mark_off2 = np.zeros(spacingPt), np.zeros(spacingPt)
    mark1 = np.concatenate((mark_on1, mark_off1)).astype(np.uint8)
    mark2 = np.concatenate((mark_on2, mark_off2)).astype(np.uint8)
    return mark1, mark2