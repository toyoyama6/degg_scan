#!/usr/bin/env python
# coding: utf-8


from collections import namedtuple
import numpy as np
from struct import unpack
import sys

ICM_CLOCK_FREQ = 60.0e6
# default clock frequency corresponding to mDOM ADC sampling rate
CLOCK_FREQ = 120.0e6
MDOM_ADC_CLOCK_FREQ = 120.0e6
MDOM_PRECISE_TIME_CLOCK_FREQ = 960.0e6
DEGG_CLOCK_FREQ = 240.0e6
CAL_TIME_CLOCK_FREQ = 480.0e6


# Class implementing the RAPCal module
    
####################
## Utility functions
####################

# Functions to define, and fit a gaussian function
# to a dataset
def gaussian_func(x, a, b, c):
    return a * np.exp( - ((x - b) / c) ** 2)

def fit_gaus_func(xval, yval, xmin, xmax,p0):
    from scipy import optimize

    # the Gaussian function to be fit
    fitfunc = lambda p, x: p[0] * np.exp( - ((x - p[1]) / p[2]) ** 2)
     # the error function which is minimized
    errfunc = lambda p, x, y: (fitfunc(p, x) - y)/np.sqrt(y)  # the error function which is minimized
    
    x = np.array(xval)   
    x_mask = np.array([(xi >= xmin) and (xi < xmax) for xi in x])   # get subset in the ranges xmin <= x < xmax
    entries = np.array(yval)   
    entries_mask = np.array([(n != 0) for n in entries])   # make sure there are no empty bins (used for histogram fitting)
    mask = np.logical_and(x_mask, entries_mask)   # make a logical mask

    # initialize starting parameters
    p_init = p0 
    p_res, p_cov, infodict, errmsg, success = optimize.leastsq(errfunc, p_init, args = (x[mask], entries[mask]), full_output=1)   # minimization procedure
    # Note the following produces: "RuntimeWarning: divide by zero encountered
    # in double_scalars" when the RAPCal iteration count is less than 20.
    s_sq = (errfunc(p_res, x[mask], entries[mask])**2).sum()/(len(entries[mask])-len(p_init))   # get error estimates
    error = []

    if p_cov is None:
        for i in range(len(p_res)):
            error.append(0.)
    else:
        p_cov = p_cov * s_sq
        for i in range(len(p_res)):
            error.append( np.absolute(p_cov[i][i])**0.5)

    return p_res, error, p_cov, s_sq   # return lists of fit parameters p_res and errors

# FUnction that calculate optimal bin width of histogram, following Scott's rule
def get_bin_width(data):
    
    n = data.size
    sigma = np.std(data)
    dx = 3.5 * sigma / (n ** (1 / 3))
    Nbins = np.ceil((data.max() - data.min()) / dx)
    Nbins = max(1, Nbins)
    bins = data.min() + dx * np.arange(Nbins + 1)
    return bins





class RapCalEvent:
    
    global threshold
    global window
    global length
    threshold = 100
    window = 2
    length = 25
    
    CROSS_WINDOW = 2
    BASELINE_SAMPLES = 20
    ALGO_INTERPOLATE = 0
    ALGO_LINEAR_FIT = 1
    ALGO_QUAD_FIT = 2
    """
    Simple Parser for RapCal Event Data Packets
    Parses and checks values where possible      
    """

    # Dictionary of RapCal packet parameters, indexed by packet version.
    _PktFormats = {
        0x00: {'length': 280, 'unpack': '<6s6s6s6s128s128s'},
    }

    @classmethod
    def parse_rapcal_header(cls, header):
        """Class method to parse a RapCal packet header. The returned size can
        be used to read the remainder of the packet.
        """
        resp = {'error': None, 'success': False}
        if not isinstance(header, bytearray) or not len(header) == 4:
            resp['error'] = 'not a 4-byte RapCal header bytearray'
            return resp
        magic, status = unpack('>HH', header)
        if magic != 0x5243:  # 'RC'
            resp['error'] = 'Pkt ID 0x%04x not a RapCal header' % magic
            return resp
        if status & 0x10:
            resp['error'] = 'Missing DOM ack pulse'
            return resp
        if status & 0x20:
            resp['error'] = 'Missing DOM pulse'
            return resp
        version = status >> 9
        try:
            size = cls._PktFormats[version]['length']
        except KeyError:
            size = None
        if size is None:
            resp['error'] = 'Invalid length'
            return resp
        resp['icm_destinations'] = status & 0x0f
        resp['magic'] = magic
        resp['status'] = status
        resp['version'] = version
        resp['size'] = size
        resp['success'] = True
        return resp

    def __init__(self,
                 rapcal_packet,
                 header_size=8,
                 timestamp_size=6,
                 waveform_size=64):
        self.seconds = False
        if isinstance(rapcal_packet, np.ndarray) and len(rapcal_packet) == 288:
            self._ctor_raw_pkt(
                rapcal_packet,
                header_size=header_size,
                timestamp_size=timestamp_size,
                waveform_size=waveform_size)
            return
        elif isinstance(rapcal_packet, tuple):
            version, packet = rapcal_packet
            if version == 0x00:
                self._ctor_verison_0x00(packet)
                return
        raise Exception('unknown RapCal packet type')

    def _ctor_raw_pkt(self,
                      rapcal_packet,
                      header_size=8,
                      timestamp_size=6,
                      waveform_size=64):
        """Constructor for raw packets (version 0x00) read from ICM Rx buf.
        This includes 4 bytes of packet layer data + 4 bytes of RapCal
        header + 280 bytes of RapCal payload.
        """
        self.header_size    = header_size
        self.timestamp_size = timestamp_size
        self.waveform_size  = waveform_size

        self.packet_length  = (rapcal_packet[0]<<8)+rapcal_packet[1]
        self.module_addr    = int(rapcal_packet[2])
        self.packet_id      = rapcal_packet[4:5]

        head = header_size
        tail = header_size+timestamp_size
        self.T_tx_dor = self._parse_time(rapcal_packet[head:tail])


        head = header_size+timestamp_size
        tail = header_size+timestamp_size*2
        self.T_rx_dom = self._parse_time(rapcal_packet[head:tail])


        head = header_size+timestamp_size*2
        tail = header_size+timestamp_size*3
        self.T_tx_dom = self._parse_time(rapcal_packet[head:tail])


        head = header_size+timestamp_size*3
        tail = header_size+timestamp_size*4
        self.T_rx_dor = self._parse_time(rapcal_packet[head:tail])


        head = header_size+timestamp_size*4
        tail = header_size+timestamp_size*4+waveform_size*2
        dom_wv_d = rapcal_packet[head:tail]
        self.dom_waveform, self.dom_trigger = self._parse_wave(dom_wv_d)

        head = header_size+timestamp_size*4+waveform_size*2
        tail = header_size+timestamp_size*4+waveform_size*4
        dor_wv_d = rapcal_packet[head:tail]
        self.dor_waveform, self.dor_trigger = self._parse_wave(dor_wv_d)

    def _ctor_verison_0x00(self, rapcal_packet):
        """Constructor for version 0x00 packets read from fieldHub. The
        packet does not contain any header fields.
        """
        self.waveform_size = 64
        pkt_format = self._PktFormats[0x00]
        if len(rapcal_packet) != pkt_format['length']:
            sys.stderr.write(f'packet length not {pkt_format["length"]}')
            return None
        field_names = ['T_tx_dor', 'T_rx_dom', 'T_tx_dom', 'T_rx_dor',
                       'dom_waveform', 'dor_waveform']
        PktFields = namedtuple('PacketFields', field_names)
        fields = PktFields._make(unpack(pkt_format['unpack'], rapcal_packet))
        self.T_tx_dor = int.from_bytes(fields.T_tx_dor, byteorder='big')
        self.T_rx_dom = int.from_bytes(fields.T_rx_dom, byteorder='big')
        self.T_tx_dom = int.from_bytes(fields.T_tx_dom, byteorder='big')
        self.T_rx_dor = int.from_bytes(fields.T_rx_dor, byteorder='big')
        self.dom_waveform, self.dom_trigger = self._parse_wave(list(
            fields.dom_waveform))
        self.dor_waveform, self.dor_trigger = self._parse_wave(list(
            fields.dor_waveform))

    def _parse_time(self,data):
        timestamp = 0
        for i in range(self.timestamp_size):
            timestamp += data[i]<<((self.timestamp_size-(i+1))*8)
        return timestamp    
    
    def _parse_wave(self,data,backwards=True):
        waveform = np.zeros(int(self.waveform_size))
        trigger = np.zeros(int(self.waveform_size),dtype=np.bool_)
        if backwards:
            for i in range(0,self.waveform_size):
                waveform[i] = (data[-(i+1)*2]&0x7f)*256 + data[(-i*2)-1] 
                trigger[i] = bool(data[-(i*2)]&0x80)         
        else:
            for i in range(0,self.waveform_size):
                waveform[i] = (data[i*2]&0x7f)*256 + data[(i*2)+1] 
                trigger[i] = bool(data[(i*2)]&0x80) 
        return waveform, trigger

    # Should not be needed
    def _bit_error_filter(self,waveform,threshold=200):
        for i in range(len(waveform)-1):
            if waveform[i]-waveform[i+1] > threshold:                    
                waveform[i+1] = waveform[i+1] + 256
            elif waveform[i]-waveform[i+1] < threshold:
                waveform[i+1] = waveform[i+1] - 256


    # Note some implementations have seen this as a public method.
    def _analyze(self,algo):

        result = {'success': False, 'error': None}

        # Perform initial causality sanity checks
        if (self.T_tx_dor >= self.T_rx_dor) or (self.T_tx_dom <= self.T_rx_dom):
            result['error'] = "RAPCal causality violation"
            return result

        # Get the baseline zero_crossing times(fine delay correction)
        dor_result = self.baseline_zero_crossing(self.dor_waveform[1:-1], self.dor_trigger, algo)
        if not dor_result['success']:
            result['error'] = dor_result['error']
            return result
        delay_dor = dor_result['fine_delay']

        dom_result = self.baseline_zero_crossing(self.dom_waveform[1:-1], self.dom_trigger, algo)
        if not dom_result['success']:
            result['error'] = dom_result['error']
            return result
        delay_dom = dom_result['fine_delay']

        # Apply the fine delay correction
        # delay is in units of 30 MHz, the ADC sampling rate
        # timestamp is in units of 60 MHz, aligned with ADC clock
        self.Trx_dor_corrected = self.T_rx_dor - 2*delay_dor
        self.Trx_dom_corrected = self.T_rx_dom - 2*delay_dom
        
        # Calculate the midpoints of waveforms
        self.Tc_dor = 0.5*(self.T_tx_dor + self.Trx_dor_corrected)
        self.Tc_dom = 0.5*(self.T_tx_dom + self.Trx_dom_corrected)
        
        result['success'] = True
        return result

    def analyze(self,algo):
        return self._analyze(algo)

    # Get the cable delay from equation 3.9
    def cable_delay(self,eps):
        
        # cable delays
        return (0.5*((self.Trx_dor_corrected - self.T_tx_dor) - (1 + eps)*(self.T_tx_dom - self.Trx_dom_corrected)))/ICM_CLOCK_FREQ
        
    # Convert the timestamp in seconds, from 60 MHz clock counts
    def convert_in_seconds(self):

        if self.seconds:
            return
        self.Tc_dor = self.Tc_dor/(ICM_CLOCK_FREQ)
        self.Tc_dom =  self.Tc_dom/(ICM_CLOCK_FREQ)
        self.T_tx_dor = self.T_tx_dor/(ICM_CLOCK_FREQ)
        self.T_tx_dom = self.T_tx_dom/(ICM_CLOCK_FREQ)
        self.Trx_dor_corrected = self.Trx_dor_corrected/(ICM_CLOCK_FREQ)
        self.Trx_dom_corrected = self.Trx_dom_corrected/(ICM_CLOCK_FREQ)
        self.seconds = True


    # Function that analyzes the 2 waveforms by calculating the baseling zero_crossing
    # of the falling edge, calculating the fine delay in the received timestamps
        
    @classmethod
    def baseline_zero_crossing(cls, wfm, trigger, algo, plot=False):
        
        resp = {'error': None, 'success': False, 'fine_delay': 0}

        # Subtract the baseline before the pulse
        wfm = wfm - np.mean(wfm[:cls.BASELINE_SAMPLES])
        ADC_max = np.max(wfm)
        #sample end, where the trigger waveform goes high
        index_offset = 3
        high_inds = np.argwhere(trigger[index_offset:-1] == 1)
        if len(high_inds) > 0:
            first_high = high_inds[0][0] + index_offset

        sample_end = first_high
        ADC_sample_end = wfm[sample_end]

        # Look backwards from the trigger point to find the zero zero_crossing sample
        cross_idx = -1
        for i in range(sample_end, 1, -1):
            if (wfm[i-1] > 0) and (wfm[i] <= 0):
                cross_idx = i
                break

        # If no zero crossing was found, bail
        if cross_idx < 0:
            resp['error'] = "No zero crossing in RAPCal waveform: "+str(wfm)
            return resp

        if (algo == cls.ALGO_INTERPOLATE):
            # Interpolate to find zero zero_crossing
            zero_crossing = (cross_idx-1) - wfm[cross_idx-1]/(wfm[cross_idx]-wfm[cross_idx-1])

        elif (algo == cls.ALGO_LINEAR_FIT):
            # Linear fit to find zero zero_crossing
            fit_lo, fit_hi = cross_idx-cls.CROSS_WINDOW, cross_idx+cls.CROSS_WINDOW-1
            x = range(fit_lo, fit_hi)
            y = wfm[fit_lo:fit_hi]
            slope, inter = np.polyfit(x, y, 1)
            zero_crossing = -(inter/slope)

        elif (algo == cls.ALGO_QUAD_FIT):
            fit_lo, fit_hi = cross_idx-cls.CROSS_WINDOW, cross_idx+cls.CROSS_WINDOW
            x = range(fit_lo, fit_hi)
            y = wfm[fit_lo:fit_hi]
            a, b, c = np.polyfit(x, y, 2)
            # the zero-crossing corresponds to the root of the falling edge of the parabola
            zero_crossing =  (-b - np.sqrt(np.power(b,2) - 4*a*c))/(2*a)
            
        resp['success'] = True
        fine_delay = sample_end - zero_crossing
        resp['fine_delay'] = fine_delay
        
        if plot:
            import matplotlib.pyplot as plt
            wfm = np.array(wfm)
            line_height = 0.3*ADC_max
            plt.plot(wfm,'.')
            plt.plot(200*trigger,'.',label='trigger')
            xs = np.arange(int(zero_crossing-window),int(zero_crossing+window-1),.1)
            
            if (algo == cls.ALGO_LINEAR_FIT):
                xs = np.arange(int(zero_crossing-window),int(zero_crossing+window-1),.1)
                plt.plot(xs,slope*xs+inter,label='linear fit')    
            elif (algo == cls.ALGO_QUAD_FIT):
                y = a*(np.power(xs,2)) + b*xs + c
                plt.plot(xs,y,label='quadratic fit')
                
            plt.vlines(x=zero_crossing,ymin=-line_height,ymax=line_height,color='red',ls='-')
            plt.vlines(x=sample_end,ymin=ADC_sample_end - line_height,ymax=ADC_sample_end + line_height,
                       color='green',ls='-')       
            plt.hlines(y=np.mean(wfm[:cls.BASELINE_SAMPLES]),xmin=0,xmax=sample_end,color='red',ls='--')
            plt.annotate(r'$\widetilde{T}_{rx}$', (zero_crossing,0.3*ADC_max))
            plt.annotate(r'$T_{rx}$', (sample_end,0.2*ADC_sample_end))
            plt.axes().arrow(sample_end, ADC_max*0.55, -fine_delay, 0,
                         head_width=0.1*ADC_max, head_length=1, fc='k', ec='k')
            plt.xlim(0,sample_end + 30)
            plt.ylabel('ADC Counts')
            plt.xlabel('Sample (30 MHz ADC)')
            plt.legend(loc='best')
            plt.savefig('rapcal_baseline_zero_crossing.png')
            #plt.show() # FIXME
        return resp


class RapCalPair():

    DOR_PERIOD_NS = 16.67
    
    def __init__(self, rc0, rc1, utc=[0, 0, 0], icm=0):
        
        # A RAPCal pair is needed for timestamp translation
        self.rc0 = rc0
        self.rc1 = rc1
        
        # self.ok = rc0.ok and rc1.ok
        # if self.ok:

        self.utc_in_second = np.float128(self.convert_to_utc_in_seconds(utc))
        self.icm_second = np.float128(icm)/(ICM_CLOCK_FREQ)
        self.delta =  self.utc_in_second - self.icm_second
        self.epsilon = ((rc1.Tc_dor - rc0.Tc_dor)/(rc1.Tc_dom - rc0.Tc_dom)) - 1        
        self.cable_delays = (rc0.cable_delay(self.epsilon), rc1.cable_delay(self.epsilon)) 

    def dom2surface(self, t_dom, device_type):
        
                # Translate a DOM timestamp to a surface timestamp
        # implement the time correction as given by eqns 3.7 and 3.6 
        # from IceCube-Gen1 instrumentation paper
        # https://arxiv.org/pdf/1612.05093.pdf
        
        # Pass t_dom as the time in units of the FPGA clock
        # (120 MHz for mDOM ADC, 960 MHz for mDOM discriminator, 240 MHz for DEgg)
        
        # The device_type argument determines the time bases of waveform timestamp 
        # Can be: "MDOM_ADC", "MDOM_PRECISE", or "DEGG"
        CLOCK_FREQ = MDOM_ADC_CLOCK_FREQ
        if(device_type == 'MDOM_ADC'):
            CLOCK_FREQ = MDOM_ADC_CLOCK_FREQ
        elif(device_type == 'MDOM_PRECISE'):
            CLOCK_FREQ = MDOM_PRECISE_TIME_CLOCK_FREQ
        elif(device_type == 'DEGG'):
            CLOCK_FREQ = DEGG_CLOCK_FREQ
        elif(device_type == 'ICM'):
            CLOCK_FREQ = ICM_CLOCK_FREQ
        elif(device_type == 'CAL_TIME'):
            CLOCK_FREQ = CAL_TIME_CLOCK_FREQ
        else:
            raise Exception("Unsupported device type: %s" % device_type)
            
        return np.float128((1 + self.epsilon) * ((1. * t_dom)/(CLOCK_FREQ) - (self.rc1.Tc_dom)/(ICM_CLOCK_FREQ)) + (self.rc1.Tc_dor)/(ICM_CLOCK_FREQ)) + np.float128(self.delta)

    def dom2utc(self, t_dom, device_type):
        t_dor = self.dom2surface(t_dom, device_type)
        # Convert to 0.1 ns
        # due to resolution issues
        return 10.* self.DOR_PERIOD_NS * t_dor
    
    
    # Function that converts the ICM's UTC register reads to a UTC time in seconds
    def convert_to_utc_in_seconds(self,registers):
        seconds = ((registers[0] & 0xF000) >> 12) * 10 + ((registers[0] & 0x0F00) >> 8)
        minutes = ((registers[0] & 0x00F0) >> 4) * 10 + (registers[0] & 0x000F)
        hours = ((registers[1] & 0xF000) >> 12) * 10 + ((registers[1] & 0x0F00) >> 8)
        day_of_year = ((registers[1] & 0x00F0) >> 4) * 100 + (registers[1] & 0x000F) * 10 + ((registers[2] & 0xF000) >> 12)
        year = ((registers[2] & 0x0F00) >> 8) * 10 + ((registers[2] & 0x00F0) >> 4)
        import datetime
        dt = datetime.datetime(2000 + year, 1, 1, hours, minutes, seconds) + datetime.timedelta(days=day_of_year-1)
        dt_in_seconds = dt.timestamp()
        return dt_in_seconds

class RapCalCollection():
    
    def __init__(self):
       self.rapcals = []
       self.epsilons = []
       self.delays = []
        
    def add_rapcal(self, rp_event):
        self.rapcals.append(rp_event)
    
    def print_collection(self):
        for rp_event in self.rapcals:
            print(rp_event)
            
    def get_rapcal_stats(self, plot=False, gaussian_fit=True):
        # iterate over rapcal pairs
        for rc0, rc1 in zip(self.rapcals,self.rapcals[1:]):          
            rp_pair = RapCalPair(rc0,rc1)
            self.epsilons.append(rp_pair.epsilon)            
            for delay in range(len(rp_pair.cable_delays)):
                self.delays.append(rp_pair.cable_delays[delay]) 
                 
        self.epsilons = np.array(self.epsilons)        
        self.delays = np.array(self.delays)
        
        # Subtract ADC pipeline delay, which is 8 cycles of a 30MHz clock
        self.delays = self.delays - (8/30e6)

        # return a dictionary of statistics
        delays = self.get_cable_stats(plot, gaussian_fit)
        epsilons = self.get_epsilon_stats(plot, gaussian_fit)
        if gaussian_fit:
            stats_fields = ['p_res', 'error', 'p_cov', 'p_chi']
        else:
            stats_fields = ['freq', 'bin_edges', 'mean', 'std']
        return {
            'delays':   dict(zip(stats_fields, delays)),
            'epsilons': dict(zip(stats_fields, epsilons))
        }

    def get_cable_stats(self, plot=False, gaussian_fit=True):
        # Look now at cable delay (in microseconds)
        data = self.delays * 1e6

        # Get optimal bin width of histogram 
        bins = get_bin_width(data)

        # Make a histogram of data
        # note: STF environment can not run matplotlib
        #fig, ax = plt.subplots()
        #n,bin_borders,patches = plt.hist(data,bins)
        n,bin_borders = np.histogram(data,bins)
        bin_centers = bin_borders[:-1] + np.diff(bin_borders) / 2
        
        mean = np.mean(bin_centers)
        max_dist = np.max(n)
        std = np.std(bin_centers)
        if not gaussian_fit:
            # Return simple statistics for small sample sizes
            return n, bin_borders, mean, std

        p0=[max_dist,mean,std]
        # Fit a normal distribution to the data:
        p_res, error, p_cov, p_chi = fit_gaus_func(bin_centers, n, xmin=mean-5*std, xmax=mean+5*std,p0=p0)  
        # Plot the PDF
        x_interval_for_fit = np.linspace(bin_borders[0], bin_borders[-1], 10000)
        
        # If you will, let there be plot
        if(plot):
            from matplotlib.ticker import FormatStrFormatter
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots()
            plt.hist(data,bins)
            plt.plot(x_interval_for_fit, gaussian_func(x_interval_for_fit, *p_res), label='fit')
            plt.title('Cable delay')
            plt.xlabel(r'Delay in cable in $\mu$s')
            plt.ylabel('Entries')
            plt.text(mean+2*std,0.9*np.max(gaussian_func(x_interval_for_fit, *p_res)),r'$\mu$=%3.4f $\pm$ %1.3e'%(p_res[1],error[1]))
            plt.text(mean+2*std,0.8*np.max(gaussian_func(x_interval_for_fit, *p_res)),r'$\sigma$=%1.4e $\pm$ %1.3e'%(p_res[2],error[2]))
            plt.text(mean+2*std,0.7*np.max(gaussian_func(x_interval_for_fit, *p_res)),r'$\chi^{2}/$ndf$=$%3.2f'%(p_chi))
            plt.locator_params(axis='x', nbins=6)
            ax.xaxis.set_major_formatter(FormatStrFormatter('%1.3e'))
            plt.xlim(mean-6*std,mean+6*std)
            plt.savefig('rapcal_cable_stats.png')
            #plt.show()

        print('Cable delay distribution fit statistics')
        print(f' mu = {p_res[1]} +/- {error[1]}')
        print(f' sigma = {p_res[2]} +/- {error[2]}')
        print(f' chi2/ndf = {p_chi}')

        return p_res, error, p_cov, p_chi

    def get_epsilon_stats(self, plot=False, gaussian_fit=True):

        # Look now at epsilon distribution
        data = self.epsilons  
        
        # Get optimal bin width of histogram 
        bins = get_bin_width(data)

        # Make a histogram of data
        # note: STF environment can not run matplotlib
        #fig, ax = plt.subplots()
        #plt.title(r'$\epsilon$ distribution')
        #n,bin_borders,patches = plt.hist(data,bins)
        n,bin_borders = np.histogram(data,bins)
        bin_centers = bin_borders[:-1] + np.diff(bin_borders) / 2
    
        mean = np.mean(data)
        max_dist = np.max(n)
        std = np.std(data)
        if not gaussian_fit:
            # Return simple statistics for small sample sizes
            return n, bin_borders, mean, std

        p0=[max_dist,mean,std]
        # Fit a normal distribution to the data:
        p_res, error, p_cov, p_chi = fit_gaus_func(bin_centers, n, xmin=mean-5*std, xmax=mean+5*std,p0=p0)  

        if(plot):       
            # Plot the PDF
            from matplotlib.ticker import FormatStrFormatter
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots()
            plt.title(r'$\epsilon$ distribution')
            plt.hist(data,bins)
            x_interval_for_fit = np.linspace(bin_borders[0], bin_borders[-1], 10000)
            plt.plot(x_interval_for_fit, gaussian_func(x_interval_for_fit, *p_res), label='fit')
            plt.text(mean+2*std,0.9*np.max(gaussian_func(x_interval_for_fit, *p_res)),r'$\mu$=%1.4e $\pm$ %1.3e'%(p_res[1],error[1]))
            plt.text(mean+2*std,0.8*np.max(gaussian_func(x_interval_for_fit, *p_res)),r'$\sigma$=%1.4e $\pm$ %1.3e'%(p_res[2],error[2]))
            plt.text(mean+2*std,0.7*np.max(gaussian_func(x_interval_for_fit, *p_res)),r'$\chi^{2}/$ndf$=$%3.2f'%(p_chi))
            plt.locator_params(axis='x', nbins=6)
            ax.xaxis.set_major_formatter(FormatStrFormatter('%1.3e'))
            plt.xlim(mean-6*std,mean+6*std)
            plt.savefig('rapcal_epsilon_stats.png')
            #plt.show()    # FIXME

        print('Epsilon distribution fit statistics')
        print(f' mu = {p_res[1]} +/- {error[1]}')
        print(f' sigma = {p_res[2]} +/- {error[2]}')
        print(f' chi2/ndf = {p_chi}')
    
        return p_res, error, p_cov, p_chi

        

