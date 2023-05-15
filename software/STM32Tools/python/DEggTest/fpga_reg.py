#
# Utility functions for fpga reads and writes
#
# Aaron Fienberg
#

REG_MAP = {
    'fw_vnum': 0xfff,
    # SDRAM
    'sdram_task': 0xffe,
    'sdram_adr_low': [0xffc, 0xff8],
    'sdram_adr_high': [0xffd, 0xff9],
    'sdram_status': 0xdc7,
    # ADC/SPI/triggering
    'adc_spi_wr_data': 0xefc,
    'adc_spi_rd_data': 0xefb,
    'adc_spi_chip_sel': 0xefa,
    'dac_spi_adr': 0xefe,
    'dac_spi_data': 0xefd,
    'spi_exec': 0xeff,
    'trig_settings': [0xef9, 0xef7],
    'test_conf': [0xef1, 0xeeb],
    'sw_trigger': [0xee5, 0xee4],
    'test_pulse': 0xde2,
    'const_conf': [0xef2, 0xeec],
    'pre_conf': [0xef4, 0xeeee],
    'post_conf': [0xef3, 0xeed],
    'const_run': [0xee7, 0xee6],
    'trig_arm': [0xef5, 0xeef],
    'trig_armed': [0xee9, 0xee8],
    'trig_thresh': [0xef8, 0xef6],
    'trig_mode': [0xef0, 0xeea],
    # waveform buffer read/write controls and status
    'evt_len': 0xdfe,
    'evt_done': 0xdff,
    'event_data': 0x0,
    'wvb_reader_enable': 0xdf4,
    'wvb_overflow_req': 0xdf0,
    'wvb_overflow_ack': 0xdef,
    'wvb_n_wfms': [0xde1, 0xde0],                
    'dig_logic_reset': 0xde5,
    # addresses for controlling the DAC values
    'dac0_spi_adr': 0xefe,
    'dac0_spi_data': 0xefd,
    'dpram_select': 0xdf9,
    'dpram_mode': 0xdf2,
    # AFE pulser
    'afe_pulser_fire': 0xdfd,
    'afe_pulser_conf': 0xde6,
    'afe_pulser_period_high': [0xdea, 0xde8],
    'afe_pulser_period_low': [0xde9, 0xde7],
    # SLO ADC addresses
    'slo_select': 0xdf6,
    'nconvst': 0xdf5,
    'spim2_wr_high': 0xdf8,
    'spim2_wr_low': 0xde4,
    'spim2_rd_high': 0xdf7,
    'spim2_rd_low': 0xde3,
    # hit buffer controller
    'hbuf_ctrl_enbl_lock' : 0xddf,
    'hbuf_ctrl_flush': 0xdde,
    'hbuf_ctrl_start_addr_high': 0xddd,
    'hbuf_ctrl_start_addr_low': 0xddc,
    'hbuf_ctrl_stop_addr_high': 0xddb,
    'hbuf_ctrl_stop_addr_low': 0xdda,
    # rate scaler controls
    'scaler_count_high' : [0xdd3, 0xdd1],
    'scaler_count_low' : [0xdd2, 0xdd0],
    'scaler_period_high': [0xdcf, 0xdcd],
    'scaler_period_low': [0xdce, 0xdcc],
    'scaler_deadtime_high': [0xdcb, 0xdc9],
    'scaler_deadtime_low': [0xdca, 0xdc0],
    # FIR filter controls
    'fir_coeff_wr_high': [0xcfd, 0xcdd],
    'fir_coeff_rd_low': [0xcee, 0xcce],
    'fir_coeff_wr_op': [0xcfe, 0xcde],
    'fir_coeff_task': [0xcff, 0xcdf],
    'fir_thresh_high': [0xceb, 0xccb],
    'fir_thresh_low': [0xcea, 0xcca],
    'fir_conf': [0xced, 0xccd],
    'fir_bsum_reset': [0xcec, 0xccc]
}


def fpga_write(session, adr, data):
    int_adr = adr_lookup(adr)

    session.fpgaWrite(int_adr, [data])


def fpga_read(session, adr, n_words=1):
    int_adr = adr_lookup(adr)

    read_data = session.fpgaRead(int_adr, n_words)

    if n_words == 1:
        return read_data[0]
    else:
        return read_data


def fpga_burst_write(session, adr, data_words):
    int_adr = adr_lookup(adr)

    session.fpgaWrite(adr, data_words)


def parse_int_arg(arg):
    try:
        return int(arg)
    except ValueError:
        return int(arg, 16)


def parse_str_arg(arg, table):
    return table[arg]


def parse_indexed_arg(arg, table):
    start_ind = arg.index('[')
    end_ind = arg.index(']')

    key = arg[:start_ind]
    index = int(arg[start_ind+1:end_ind])

    return table[key][index]


def parse_arg(arg, table):
    try:
        return parse_int_arg(arg)
    except ValueError:
        pass

    try:
        return parse_str_arg(arg, table)
    except (ValueError, KeyError):
        pass

    return parse_indexed_arg(arg, table)


def adr_lookup(arg):
    return parse_arg(arg, table=REG_MAP)
