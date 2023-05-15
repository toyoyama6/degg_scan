""" ICM register interfaces """

class Name:
    """String constants catch register typos at compile time."""
    # 0x00
    CTRL1 = "CTRL1"
    CTRL2 = "CTRL2"
    CSTAT = "CSTAT"
    CONN_ICMS = "CONN_ICMS"
    CERR = "CERR"
    MB_PWR = "MB_PWR"
    STATE_MON1 = "STATE_MON1"
    RXBUF = "RXBUF"
    RXBUF_BC = "RXBUF_BC"
    ICM_TXBUF = "ICM_TXBUF"
    CRC_STAT = "CRC_STAT"
    CRC_RETRY = "CRC_RETRY"
    PKT_CNT = "PKT_CNT"
    # 0x10
    ICM_RCFG_CTRL = "RCFG_CTRL"
    ICM_FLASHP_CFG = "FLASHP_CFG"
    ICM_MULTIB_ID = "MULTIB_ID"
    ICM_RCFG_STAT = "RCFG_STAT"
    ICM_RCFG_ERR = "RCFG_ERR"
    ICM_RCFG_DATA = "RCFG_DATA"
    # 0x20
    FH_GSTAT = "GPS_STAT"
    FH_PSTAT_FUSE_CTRL = "PSTAT"
    WP_CUR = "WP_CUR"
    WP_VOLT = "WP_VOLT"
    FH_CUR_MAX_FST = "MAX_CUR_FAST"
    FH_CUR_MAX_SLW = "MAX_CUR_SLOW"
    FH_VOLT_MAX_FST = "MAX_VOLT_FAST"
    FH_VOLT_MAX_SLW = "MAX_VOLT_SLOW"
    FH_VOLT_MIN_FST = "MIN_VOLT_FAST"
    FH_VOLT_MIN_SLW = "MIN_VOLT_SLOW"
    GPS_CTRL = "GPS_CTRL"
    GPS_TIME = "GPS_TIME"
    RAPCAL_TIME = "RAPCAL_TIME"
    # 0x33
    WP_PWR = "WP_PWR"
    ENA_TK = "ENA_TK"
    RAPCAL_CTRL = "RAPCAL_CTRL"
    RAPCAL_STAT = "RAPCAL_STAT"
    CAL_PULSE_TIME2 = "CAL_PULSE_TIME2"
    CAL_PULSE_TIME1 = "CAL_PULSE_TIME1"
    CAL_PULSE_PER = "CAL_PULSE_PER"
    CAL_PULSE_COUNT = "CAL_PULSE_COUNT"
    EEPROM_CTRL = "EEPROM_CTRL"
    # 0x40
    EEPROM_DATA = "EEPROM_DATA"
    RESTART_COUNT = "RESTART_COUNT"
    EEPROM_START = "EEPROM_START"
    EEPROM_END = "EEPROM_END"
    CAL_TRIG_BUF_COUNT = "CAL_TRIG_BUF_COUNT"
    CAL_TRIG_RAPCAL = "CAL_TRIG_RAPCAL"
    CAL_TRIG_FINE = "CAL_TRIG_FINE"
    # 0x9f
    FPGA_ALARMS = "FPGA_ALARMS"
    # 0xe0
    FPGA_TEMP_MAX = "FPGA_TEMP_MAX"
    FPGA_TEMP_MIN = "FPGA_TEMP_MIN"
    FPGA_TEMP = "FPGA_TEMP"
    FPGA_VCCINT = "FPGA_VCCINT"
    FPGA_VCCBRAM = "FPGA_VCCBRAM"
    FPGA_VCCAUX = "FPGA_VCCAUX"
    FIFO_FULL_COUNTER = "FIFO_FULL_COUNTER"
    NOISE_CONTROL = "NOISE_CONTROL"
    NOISE_MAX = "NOISE_MAX"
    NOISE_MIN = "NOISE_MIN"
    CRST_CNT = "CRST_CNT"
    DAC_AMP = "DAC_AMP"
    ADC_THRESH = "ADC_THRESH"
    ALT_ADDR = "ALT_ADDR"
    # 0xf0
    ICM_ID = "ICM_ID"
    MB_ID = "MB_ID"
    WP_ADDR = "WP_ADDR"
    TEST_DATA = "TEST_DATA"
    GI_IND = "GI_IND"
    FW_VERS = "FW_VERS"

# Register map
Address = {
    Name.CTRL1:                 0x00,
    Name.CTRL2:                 0x01,
    Name.CSTAT:                 0x02,
    Name.CONN_ICMS:             0x03,
    Name.CERR:                  0x04,
    Name.MB_PWR:                0x06,
    Name.STATE_MON1:            0x07,
    Name.RXBUF:                 0x08,
    Name.RXBUF_BC:              0x09,
    Name.ICM_TXBUF:             0x0A,
    Name.CRC_STAT:              0x0C,
    Name.CRC_RETRY:             0x0D,
    Name.PKT_CNT:               0x0E,

    Name.ICM_RCFG_CTRL:         0x10,
    Name.ICM_FLASHP_CFG:        0x11,
    Name.ICM_MULTIB_ID:         0x12,
    Name.ICM_RCFG_STAT:         0x14,
    Name.ICM_RCFG_ERR:          0x15,
    Name.ICM_RCFG_DATA:         0x16,

    Name.FH_GSTAT:              0x20,
    Name.FH_PSTAT_FUSE_CTRL:    0x21,
    Name.WP_CUR:                0x22,
    Name.WP_VOLT:               0x23,
    Name.FH_CUR_MAX_FST:        0x24,
    Name.FH_CUR_MAX_SLW:        0x25,
    Name.FH_VOLT_MAX_FST:       0x26,
    Name.FH_VOLT_MAX_SLW:       0x27,
    Name.FH_VOLT_MIN_FST:       0x28,
    Name.FH_VOLT_MIN_SLW:       0x29,
    Name.GPS_CTRL:              0x2A,
    Name.GPS_TIME:              0x2B,
    Name.RAPCAL_TIME:           0x2F,

    Name.WP_PWR:                0x33,
    Name.ENA_TK:                0x34,
    Name.RAPCAL_CTRL:           0x35,
    Name.RAPCAL_STAT:           0x36,
    Name.CAL_PULSE_TIME2:       0x37,
    Name.CAL_PULSE_TIME1:       0x38,
    Name.CAL_PULSE_PER:         0x39,
    Name.CAL_PULSE_COUNT:       0x3A,
    Name.EEPROM_CTRL:           0x3F,

    Name.EEPROM_DATA:           0x40,
    Name.RESTART_COUNT:         0x40,
    Name.EEPROM_START:          0x42,
    Name.EEPROM_END:            0x7F,

    Name.CAL_TRIG_BUF_COUNT:    0x9A,
    Name.CAL_TRIG_RAPCAL:       0x9B,
    Name.CAL_TRIG_FINE:         0x9E,
    Name.FPGA_ALARMS:           0x9F,

    Name.FPGA_TEMP_MAX:         0xE0,
    Name.FPGA_TEMP_MIN:         0xE1,
    Name.FPGA_TEMP:             0xE2,
    Name.FPGA_VCCINT:           0xE3,
    Name.FPGA_VCCBRAM:          0xE4,
    Name.FPGA_VCCAUX:           0xE5,
    Name.FIFO_FULL_COUNTER:     0xE8,
    Name.NOISE_CONTROL:         0xE9,
    Name.NOISE_MAX:             0xEA,
    Name.NOISE_MIN:             0xEB,
    Name.CRST_CNT:              0xEC,
    Name.DAC_AMP:               0xED,
    Name.ADC_THRESH:            0xEE,
    Name.ALT_ADDR:              0xEF,

    Name.ICM_ID:                0xF0,
    Name.MB_ID:                 0xF4,
    Name.WP_ADDR:               0xFC,
    Name.TEST_DATA:             0xFD,
    Name.GI_IND:                0xFE,
    Name.FW_VERS:               0xFF,
}

class CTRL1:
    COMMS_RESET         = 0x0002
    MCU_RESET           = 0x0004
    CLEAR_ERRORS        = 0x0008
    WIREPAIR_TERM       = 0x0010
    GPS_CLK_ENA         = 0x0100

class CTRL2:
    """reg 0x01 constants"""
    INTLK_0             = 0x0001
    INTLK_MCU_FLASH     = INTLK_0
    INTLK_1             = 0x0002
    INTLK_FPGA_CONFIG   = INTLK_1
    INTLK_2             = 0x0004
    INTLK_LID           = INTLK_2
    INTLK_3             = 0x0008
    INTLK_PMT_HV        = INTLK_3
    INTLK_ENA           = 0x0010
    RESET = (INTLK_ENA | INTLK_FPGA_CONFIG)

class MB_PWR:
    """reg 0x06 constants"""
    MB_PWR_OFF          = 0x6469
    MB_PWR_ON           = 0x454e

class RCFG_STAT:
    """reg 0x14 constants"""
    ERROR_DETECTED      = 0x0001
    FLASH_READY         = 0x0002
    FLASH_PROG_RUN      = 0x0004
    # reserved
    FLASH_PROG_DONE     = 0x0020
    FWR_PROTECT_DONE    = 0x0040
    SUBPROC_DONE        = 0x0080
    # reserved
    HW_WRITE_PROT       = 0x8000

class RCFG_ERR:
    """reg 0x15 constants"""
    FP_TIMEOUT_ERR      = 0x0001
    FP_CHKSUM_ERR       = 0x0002
    FP_ERASE_ERR        = 0x0004
    FP_READBACK_ERR     = 0x0008
    FAIL_FWR_PROTECT    = 0x0010
    INSUFFICIENT_DATA   = 0x0020
    ILLEGAL_OP_FOUND    = 0x0040
    ERROR_DETECTED      = 0x0080

class WP_PWR:
    """reg 0x33 constants"""
    WP_PWR_OFF          = 0x6469
    WP_PWR_ON           = 0x454e

class EEPROM_CTRL:
    """reg 0x3f constants for accessing ICM or mainboard EEPROMs"""
    READ_EEPROM             = 0x0003
    OW_DEV_USR_SELECT_ICM   = 0x0000
    OW_DEV_USR_SELECT_MB    = 0x0004
    OW_DATA_READY_MASK      = 0x0010
    OW_DATA_READY_VAL       = 0x0010
    OW_DEV_SELECT_MASK      = 0x0020
    OW_DEV_SELECT_MB        = 0x0020
    OW_DEV_SELECT_ICM       = 0x0000
    MB_OW_RESET_MASK        = 0x0040
    MB_OW_RESET_VAL         = 0x0040
    ICM_ID_VALID_MASK       = 0x0080
    ICM_ID_VALID_VAL        = 0x0080
    EEPROM_WRITE            = 0x5700

class GI_IND:
    """reg 0xfe constants"""
    GI_IND_MASK         = 0x0003
    GI_IND_PRIMARY      = 0x0001
    GI_IND_SECONDARY    = 0x0002
    GI_IND_RUNTIME      = 0x0000
    EEPROM_WRITE_EN_MASK= 0x0010
    EEPROM_WRITE_EN_VAL = 0x0010


