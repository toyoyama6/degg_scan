from goldschmidt.magnetometer import ThermometerTM947SD


def readout_temperature(device, channel):
    meter = ThermometerTM947SD(device=device)
    meter.select_channel(channel)
    temp = meter.measure()
    return temp


if __name__ == '__main__':
    # Testing
    # Channel 1: D-Egg surface
    # Channel 2: Box surface (outside)
    # Channel 3: Box surface (inside)
    device = '/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_AH065JA8-if00-port0'
    channels = [1, 2, 3]
    for channel in channels:
        temp = readout_temperature(device, channel)
        print(temp)

