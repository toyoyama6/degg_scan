

# ADS4149 Registers.  Add to this list as we use them
ADS_4149_HP1_REG  = {
    "name": "ads4149HighPerformance1",
    "address": 0x03,
    "offset": 0,
    "size": 2,
    "options": {
        "Default": 0,
        "BestPerformance": 3
    }
}


ADS_4149_GAIN_REG = {
    "name": "ads4149Gain",
    "address": 0x25,
    "offset": 4,
    "size": 4,
    "options": {
        "0db0": 0,
        "0db5": 1,
        "1db0": 2,
        "1db5": 3,
        "2db0": 4,
        "2db5": 5,
        "3db0": 6,
        "3db5": 7,
        "4db0": 8,
        "4db5": 9,
        "5db0": 10,
        "5db5": 11,
        "6db0": 12
    }
}


ADS_4149_TP_REG   = {
    "name": "ads4149TestPattern",
    "address": 0x25,
    "offset": 0,
    "size": 3,
    "options": {
        "Default": 0,
        "Zeroes": 1,
        "Ones": 2,
        "Toggle": 3,
        "Ramp": 4,
        "Custom": 5
    }
}


ADS_4149_CUSTOM_PATTERN_HIGH_REG = {
    "name": "ads4149CustomPatternHigh",
    "address": 0x3F,
    "offset": 0,
    "size": 8
}


ADS_4149_CUSTOM_PATTERN_LOW_REG  = {
    "name": "ads4149CustomPattern",
    "address": 0x40,
    "offset": 2,
    "size": 6,
    "help": "Custom ADC value to inject"
}


ADS_4149_DIS_LOW_LATENCY_REG  = {
    "name": "ads4149DisableLowLatency",
    "address": 0x42,
    "offset": 3,
    "size": 1,
}


ADS_4149_EN_CLKOUT_RISE  = {
    "name": "ads4149EnableClkoutRise",
    "address": 0x41,
    "offset": 3,
    "size": 1,
}


ADS_4149_CLKOUT_RISE_POSN  = {
    "name": "ads4149ClkoutRisePosn",
    "address": 0x41,
    "offset": 1,
    "size": 2,
    "options": {
        "Default": 0,
        "FienbergFix": 2
    }
}


ADS_4149_HP2_REG  = {
    "name": "ads4149HighPerformance2",
    "address": 0x4A,
    "offset": 0,
    "size": 1,
    "options": {
        "Default": 0,
        "BestPerformance": 1
    }
}


optionRegisters = [ADS_4149_HP1_REG,
                   ADS_4149_GAIN_REG,
                   ADS_4149_TP_REG,
                   ADS_4149_CUSTOM_PATTERN_LOW_REG,
                   ADS_4149_HP2_REG,
                   ADS_4149_CLKOUT_RISE_POSN]


latencySensitiveRegisters = [ADS_4149_GAIN_REG,
                             ADS_4149_TP_REG]


def createHelp(reg):
    if "help" in reg:
        return reg["help"]
    if "options" in reg:
        return "Options are: %s" % [k for k in reg["options"].keys()]
    return ""


def configureOptions(parser):
    
    for reg in optionRegisters:
        parser.add_option("--" + reg["name"], dest=reg["name"], 
                          default=None, help=createHelp(reg))


def setRegister(session, reg, value, channel):
    if type(value) is str:
        value = reg['options'][value]

    # If we're setting the custom pattern, we have to set the high bits also
    if reg["name"] == "ads4149CustomPattern":
        highBits = value >> reg["size"]
        setRegister(session,
                    ADS_4149_CUSTOM_PATTERN_HIGH_REG, highBits, channel)
        # We only set the low bits here
        value &= ((1 << reg["size"]) - 1)
    # Disable low-latency mode if required
    if reg in latencySensitiveRegisters:
        setRegister(session, ADS_4149_DIS_LOW_LATENCY_REG, 1, channel)
    # Enable clkout rise if needed
    if reg == ADS_4149_CLKOUT_RISE_POSN:
        setRegister(session, ADS_4149_EN_CLKOUT_RISE, 1, channel)
    # First read the register
    oldValue = int(session.readADS4149(channel, reg["address"]))
    mask = ((1 << reg["size"]) - 1) << reg["offset"]
    newValue = (oldValue & ((~mask) & 0xFF)) | ((value << reg["offset"]) & mask)
    # Write the new value
    session.writeADS4149(channel, reg["address"], newValue)



def _setRegister(session, reg, value):
    # Just set both chips
    setRegister(session, reg, value, 0)
    setRegister(session, reg, value, 1)


def init(options, session):
    # First reset the chips
    session.resetADS4149(0)
    session.resetADS4149(1)
    
    # Apply the options
    optDict = vars(options)
    for reg in optionRegisters:
        if reg["name"] in optDict:
            value = optDict[reg["name"]]
            if value is not None:
                _setRegister(session, reg, reg["options"][value])
