#!/usr/bin/env python3

"""
Heatwave - Real-time RF Spectrum Analyzer with Waterfall Display
for use with Linux framebuffer.
==============================================================

A feature-rich RF spectrum analyzer that provides real-time visualization of radio frequency signals
using RTL-SDR and other SDR devices through the SoapySDR interface.

Features:
- Real-time waterfall display of RF spectrum
- Multiple color schemes and display modes
- Frequency band presets and markers
- Time-based annotations and signal analysis
- Automatic gain control (AGC)
- Recording and export capabilities
- Comprehensive keyboard controls

Requirements:
- Python 3.6+
- numpy
- SoapySDR
- scipy
- PIL (Pillow)
- Compatible SDR device (RTL-SDR, HackRF, etc.)

Author: XQTR // https://github.com/xqtr // https://cp737.net
License: GPL-3.0+
Version: 1.0.0
"""

import numpy as np
import SoapySDR
from SoapySDR import SOAPY_SDR_RX, SOAPY_SDR_CF32
import mmap
import struct
import argparse
import time
from scipy import signal
from PIL import Image, ImageDraw, ImageFont
import os
import sys
import termios
import tty
import select
from datetime import datetime
import json
import os.path

class FrequencyHeatmap:
    def __init__(self, start_freq, end_freq, sample_rate):
        # Remove custom band configuration
        self.config_dir = os.path.expanduser('~/.config/heatwave/')
        os.makedirs(self.config_dir, exist_ok=True)
        self.settings_file = os.path.join(self.config_dir, 'settings.json')
        # Remove: self.band_file = os.path.join(self.config_dir, 'bands.json')
        
        # Initialize basic parameters
        self.start_freq = start_freq
        self.end_freq = end_freq
        self.sample_rate = sample_rate
        self.freq_range = end_freq - start_freq
        self._center_freq = start_freq + (self.freq_range / 2)
        
        # Initialize built-in bands with comprehensive frequency ranges
        self.bands = {
            # Broadcast Bands
            "AM": (535e3, 1.7e6),
            "SW": (2.3e6, 26.1e6),
            "FM": (88e6, 108e6),
            "DAB": (174e6, 240e6),
            
            # Aviation Bands
            "AIR-L": (108e6, 118e6),    # VOR/ILS/Markers
            "AIR-V": (118e6, 137e6),    # Voice Communications
            "AIR-M": (978e6, 1090e6),   # ADS-B/Mode S
            
            # Amateur Radio Bands
            "HAM160": (1.8e6, 2.0e6),
            "HAM80": (3.5e6, 4.0e6),
            "HAM40": (7.0e6, 7.3e6),
            "HAM20": (14.0e6, 14.35e6),
            "HAM2M": (144e6, 148e6),
            "HAM70": (420e6, 450e6),
            
            # Public Safety
            "NOA": (162.4e6, 162.55e6), # NOAA Weather
            "POLICE": (450e6, 470e6),    # Police/Emergency
            "EMG": (851e6, 869e6),       # Emergency Services
            
            # Television
            "VHF-TV": (54e6, 88e6),     # VHF Low
            "VHF-TV2": (174e6, 216e6),  # VHF High
            "UHF-TV": (470e6, 698e6),   # UHF TV
            
            # Satellite
            "GPS-L1": (1575.42e6, 1575.42e6),
            "GOES": (1670e6, 1698e6),
            "NOAA-SAT": (137e6, 138e6),
            "METEOR-SAT": (137.9e6, 137.9e6),
            
            # Mobile & Cellular
            "CELL-850": (824e6, 894e6),
            "GSM900": (890e6, 960e6),
            "GSM1800": (1710e6, 1880e6),
            "DECT": (1880e6, 1900e6),
            
            # ISM & IoT
            "ISM-433": (433.05e6, 434.79e6),
            "ISM-868": (868e6, 868.6e6),
            "ISM-915": (902e6, 928e6),
            "ZIGBEE": (2400e6, 2483.5e6),
            
            # Marine
            "MAR-VHF": (156e6, 174e6),
            "MAR-AIS": (161.975e6, 162.025e6),
            "MAR-DSC": (156.525e6, 156.525e6),
            
            # Digital Radio
            "DAB": (174e6, 240e6),
            "DSTAR": (145.375e6, 145.375e6),
            "DMR": (446e6, 446.2e6),
            "TETRA": (380e6, 400e6),
            
            # Remote Control
            "RC-AIR": (72e6, 73e6),
            "RC-CAR": (26.995e6, 27.255e6),
            "RC-GENERAL": (433e6, 435e6),
            
            # Utilities
            "PAGER": (929e6, 932e6),
            "RFID": (13.56e6, 13.56e6),
            "TRUNKING": (851e6, 869e6),
            "SCADA": (450e6, 470e6),
            
            # Microphones
            "MIC-VHF": (169.445e6, 171.905e6),
            "MIC-UHF": (470e6, 698e6),
            "MIC-PRO": (944e6, 952e6),
            
            # Weather
            "WEATHER-SAT": (137e6, 138e6),
            "WEATHER-RADIO": (162.4e6, 162.55e6),
            "WEATHER-FAX": (2.0e6, 25e6),
            
            # Time Signals
            "WWV": (2.5e6, 20e6),
            "WWVH": (2.5e6, 15e6),
            "DCF77": (77.5e3, 77.5e3),
            "MSF": (60e3, 60e3)
        }
        
        # Initialize band details with comprehensive information
        self.band_details = {
            "AM": {
                "mode": "AM",
                "spacing": 10e3,
                "description": "AM Broadcasting"
            },
            "FM": {
                "mode": "WFM",
                "spacing": 200e3,
                "description": "FM Broadcasting"
            },
            "AIR-V": {
                "mode": "AM",
                "spacing": 25e3,
                "description": "Aircraft Voice Communications"
            },
            "AIR-L": {
                "mode": "AM",
                "spacing": 50e3,
                "description": "Aircraft Navigation (VOR/ILS)"
            },
            "HAM2M": {
                "mode": "NFM",
                "spacing": 12.5e3,
                "description": "2-meter Amateur Radio Band"
            },
            "NOA": {
                "mode": "NFM",
                "spacing": 25e3,
                "description": "NOAA Weather Radio"
            },
            "POLICE": {
                "mode": "NFM",
                "spacing": 12.5e3,
                "description": "Police and Emergency Services"
            },
            "GPS-L1": {
                "mode": "BPSK",
                "spacing": 2e6,
                "description": "GPS L1 Signal"
            },
            "ISM-433": {
                "mode": "NFM",
                "spacing": 25e3,
                "description": "ISM Band 433MHz"
            },
            "MAR-VHF": {
                "mode": "NFM",
                "spacing": 25e3,
                "description": "Marine VHF Communications"
            },
            "CELL-850": {
                "mode": "DIGITAL",
                "spacing": 200e3,
                "description": "Cellular 850MHz Band"
            },
            "DAB": {
                "mode": "DIGITAL",
                "spacing": 1.536e6,
                "description": "Digital Audio Broadcasting"
            },
            "TETRA": {
                "mode": "DIGITAL",
                "spacing": 25e3,
                "description": "TETRA Digital Radio"
            },
            "WEATHER-SAT": {
                "mode": "APT",
                "spacing": 30e3,
                "description": "Weather Satellite Transmissions"
            },
            "WWV": {
                "mode": "AM",
                "spacing": 1e3,
                "description": "NIST Time Signal Station"
            }
            # Add more band details as needed
        }
        
        # Remove: self.load_custom_bands()
        
        # Initialize basic parameters first
        self.ppm = 0  # Initialize PPM correction to 0
        
        # Setup terminal settings first
        self.old_settings = termios.tcgetattr(sys.stdin)
        tty.setcbreak(sys.stdin.fileno())
        
        # Initialize SDR after parameters and terminal settings are set
        self.sdr = None
        self.setup_sdr()
        
        # Now set the center frequency on the SDR
        self.center_freq = self._center_freq
        
        # Detect framebuffer resolution
        with open('/sys/class/graphics/fb0/virtual_size', 'r') as f:
            self.width, self.height = map(int, f.read().strip().split(','))
        
        # Get bits per pixel
        with open('/sys/class/graphics/fb0/bits_per_pixel', 'r') as f:
            self.bits_per_pixel = int(f.read().strip())
            
        # Bytes per pixel
        self.bytes_per_pixel = self.bits_per_pixel // 8
        
        print(f"Framebuffer: {self.width}x{self.height}, {self.bits_per_pixel} bits per pixel")
        
        # Calculate framebuffer size
        self.fb_size = self.width * self.height * self.bytes_per_pixel
        
        # Initialize framebuffer
        self.fb = open('/dev/fb0', 'r+b')
        self.fb_data = mmap.mmap(self.fb.fileno(), self.fb_size, mmap.MAP_SHARED)
        
        # Configure RTL-SDR
        self.sdr.setSampleRate(SOAPY_SDR_RX, 0, self.sample_rate)
        self.sdr.setFrequency(SOAPY_SDR_RX, 0, self._center_freq)  # Use the stored value
        self.sdr.setGain(SOAPY_SDR_RX, 0, 20)  # Initial gain setting
        
        # Add font initialization
        try:
            self.font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
        except:
            # Fallback to default font if DejaVu Sans is not available
            self.font = ImageFont.load_default()
        
        # Reserve space for labels and margins
        self.left_margin = 0      # Space for time labels
        self.top_margin = 30      # Space for information display
        self.bottom_margin = 30   # Space for frequency labels
        self.graph_height = self.height - self.bottom_margin - self.top_margin
        self.graph_width = self.width - self.left_margin
        self.heatmap = np.zeros((self.graph_height, self.graph_width))
        
        # Initialize time tracking
        self.start_time = time.time()
        
        # Initialize cursor at start frequency
        self.cursor_freq = start_freq
        self.cursor_step = 0.1e6  # 0.1MHz step
        
        # Add pause state
        self.paused = False
        
        # Add new state variables
        self.peak_hold = False
        self.averaging = False
        self.auto_scale = True
        self.recording = False
        self.record_file = None
        self.color_scheme = 0  # 0: default, 1: hot, 2: viridis, 3: plasma, 4: magma
        self.scroll_speed = 1.0
        self.markers = {}  # Dictionary to store frequency markers
        self.shift_pressed = False  # For marker setting
        self.last_char = None  # Track the last character pressed
        
        # Initialize peak hold array
        self.peak_values = np.zeros_like(self.heatmap)
        
        # Initialize averaging buffer
        self.avg_buffer = []
        self.avg_length = 5  # Number of spectrums to average
        
        # Add timestamp tracking
        self.last_timestamp = time.time()
        self.timestamps = []  # List to store timestamps
        
        # Add message display variables
        self.display_message = ""
        self.message_time = 0
        self.message_duration = 3  # Message display duration in seconds
        
        # Add AGC parameters
        self.agc_enabled = False
        self.agc_target = -30  # Target power level in dB
        self.agc_speed = 0.3   # AGC adjustment speed (0-1)
        self.agc_min_gain = 0
        self.agc_max_gain = 49.6
        self.current_gain = 20  # Starting gain
        self.agc_history = []
        self.agc_history_len = 10  # Number of measurements to average
        self.last_agc_update = time.time()
        self.agc_update_interval = 0.5  # Seconds between AGC updates
        
        # Get script directory
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Load settings if they exist
        self.load_settings()
        
        # Add time tracking and annotation support
        self.annotations = []
        self.timestamps = []
        self.base_pixels_per_second = self.graph_height / (10 * 60)  # 10 minutes total height
        self.export_directory = os.path.join(self.script_dir, 'exports')
        
        # Create exports directory if it doesn't exist
        if not os.path.exists(self.export_directory):
            os.makedirs(self.export_directory)
        
        # Add annotation position tracking
        self.annotation_positions = {}  # Store y-positions for annotations
        self.annotation_shift = 0       # Track total shift amount
        
        # Add scan time tracking with averaging
        self.last_scan_time = 0
        self.scan_times = []  # List to store recent scan times
        self.scan_times_max = 10  # Number of samples to average
        
        # Initialize FFT planning and window
        self._init_fft_processing()
        
        # Add tracking for framebuffer fill level
        self.fb_fill_level = 0
        self.fb_filled = False
        self.export_count = 0
        self.auto_export_enabled = False  # New flag for automatic export
        
        # Create exports directory if it doesn't exist
        self.export_directory = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'exports')
    
    def setup_sdr(self):
        """Initialize SoapySDR device with user selection"""
        # List all available devices
        results = SoapySDR.Device.enumerate()
        if len(results) == 0:
            raise RuntimeError("No SDR devices found")

        # If only one device, use it automatically
        if len(results) == 1:
            self.sdr = SoapySDR.Device(results[0])
        else:
            # Temporarily restore normal terminal behavior for device selection
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)
            try:
                # Display available devices
                print("\nAvailable SDR devices:")
                print("----------------------")
                for i, device in enumerate(results):
                    # Access device info directly from kwargs
                    try:
                        driver = str(device["driver"]) if "driver" in device else "Unknown"
                        label = str(device["label"]) if "label" in device else "Unnamed"
                        serial = str(device["serial"]) if "serial" in device else "No serial"
                    except:
                        driver = "Unknown"
                        label = "Unnamed"
                        serial = "No serial"
                    
                    print(f"{i + 1}. Driver: {driver}")
                    print(f"   Label: {label}")
                    print(f"   Serial: {serial}")
                    print("----------------------")

                # Get user selection
                while True:
                    try:
                        selection = input(f"Select device (1-{len(results)}): ")
                        device_index = int(selection) - 1
                        if 0 <= device_index < len(results):
                            self.sdr = SoapySDR.Device(results[device_index])
                            break
                        else:
                            print(f"Please enter a number between 1 and {len(results)}")
                    except ValueError:
                        print("Please enter a valid number")

            finally:
                # Restore non-blocking input mode
                tty.setcbreak(sys.stdin.fileno())
                os.system('clear')  # Clear the terminal

        # Setup streaming
        self.sdr.setSampleRate(SOAPY_SDR_RX, 0, self.sample_rate)
        self.sdr.setFrequency(SOAPY_SDR_RX, 0, self._center_freq)
        self.sdr.setGain(SOAPY_SDR_RX, 0, 20)  # Initial gain setting

        # Setup the stream
        self.rx_stream = self.sdr.setupStream(SOAPY_SDR_RX, SOAPY_SDR_CF32)
        self.sdr.activateStream(self.rx_stream)
        
        # Add after other SDR setup commands
        if hasattr(self.sdr, 'setFrequencyCorrection'):
            self.sdr.setFrequencyCorrection(SOAPY_SDR_RX, 0, self.ppm)
    
    def save_settings(self):
        """Save current settings to JSON file"""
        settings = {
            'sample_rate': self.sample_rate,
            'color_scheme': self.color_scheme,
            'scroll_speed': self.scroll_speed,
            'current_gain': self.current_gain,
            'agc_enabled': self.agc_enabled,
            'agc_target': self.agc_target,
            'agc_speed': self.agc_speed,
            'peak_hold': self.peak_hold,
            'averaging': self.averaging,
            'auto_scale': self.auto_scale,
            'markers': {str(k): v for k, v in self.markers.items()},  # Convert keys to strings for JSON
            'cursor_step': self.cursor_step,
            'ppm': self.ppm,
        }
        
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(settings, f, indent=4)
            self.display_message = "Settings saved successfully"
        except Exception as e:
            self.display_message = f"Error saving settings: {str(e)}"
        self.message_time = time.time()
    
    def add_msg(self,msg):
        self.display_message = msg
        self.message_time = time.time()
    
    def load_settings(self):
        """Load settings from JSON file"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                
                # Apply loaded settings
                self.sample_rate = settings.get('sample_rate', self.sample_rate)
                self.sdr.setSampleRate(SOAPY_SDR_RX, 0, self.sample_rate)
                
                self.color_scheme = settings.get('color_scheme', 0)
                self.scroll_speed = settings.get('scroll_speed', 1.0)
                self.current_gain = settings.get('current_gain', 20)
                self.sdr.setGain(SOAPY_SDR_RX, 0, self.current_gain)
                
                self.agc_enabled = settings.get('agc_enabled', False)
                self.agc_target = settings.get('agc_target', -30)
                self.agc_speed = settings.get('agc_speed', 0.3)
                
                self.peak_hold = settings.get('peak_hold', False)
                self.averaging = settings.get('averaging', False)
                self.auto_scale = settings.get('auto_scale', True)
                
                # Convert marker keys back to integers
                markers = settings.get('markers', {})
                self.markers = {int(k): v for k, v in markers.items()}
                
                self.cursor_step = settings.get('cursor_step', 0.1e6)
                
                self.ppm = settings.get('ppm', 0)
                
                self.display_message = "Settings loaded successfully"
        except Exception as e:
            self.display_message = f"Error loading settings: {str(e)}"
        self.message_time = time.time()
    
    def check_keyboard(self):
        """Non-blocking keyboard check"""
        if select.select([sys.stdin], [], [], 0)[0] != []:
            char = sys.stdin.read(1)
            
            # Check if character is a digit and handle shift state
            if char in '12345':
                marker_num = int(char)
                if marker_num in self.markers:
                    self.cursor_freq = self.markers[marker_num]
                    self.add_msg(f"Jumped to marker {marker_num}: {self.cursor_freq/1e6:.3f} MHz")                    
                else:
                    self.add_msg(f"Marker {marker_num} not set")
            # Handle marker sets (6-0 sets markers 1-5)
            elif char in '67890':
                marker_map = {'6': 1, '7': 2, '8': 3, '9': 4, '0': 5}
                marker_num = marker_map[char]
                self.markers[marker_num] = self.cursor_freq
                self.add_msg(f"Marker {marker_num} set to {self.cursor_freq/1e6:.3f} MHz")
            
            elif char == '<':  # Input start frequency
                # Temporarily restore normal terminal behavior for input
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)
                try:
                    self.paused = True
                    # Get user input
                    os.system('clear')
                    start_input = input("\nEnter start frequency in MHz: ")
                    try:
                        new_start = float(start_input) * 1e6  # Convert MHz to Hz
                        # Validate frequency is within reasonable range
                        if 24e6 <= new_start < self.end_freq:  # typical RTL-SDR range
                            self.start_freq = new_start
                            self.freq_range = self.end_freq - self.start_freq
                            self.center_freq = self.start_freq + (self.freq_range / 2)
                            self.sdr.setFrequency(SOAPY_SDR_RX, 0, self.center_freq)
                            self.clear_heatmap()  # Clear display
                            self.add_msg(f"Frequency range: {self.start_freq/1e6:.3f}-{self.end_freq/1e6:.3f} MHz")
                        else:
                            self.add_msg("Start frequency must be between 24 MHz and end frequency")                            
                    except ValueError:
                        self.add_msg("Invalid frequency format. Please enter a number.")
                finally:
                    # Restore non-blocking input mode
                    tty.setcbreak(sys.stdin.fileno())
                    self.paused = False
            
            elif char == '>':  # Input end frequency
                # Temporarily restore normal terminal behavior for input
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)
                try:
                    self.paused = True
                    # Get user input
                    os.system('clear')
                    end_input = input("\nEnter end frequency in MHz: ")
                    try:
                        new_end = float(end_input) * 1e6  # Convert MHz to Hz
                        # Validate frequency is within reasonable range
                        if self.start_freq < new_end <= 1766e6:  # typical RTL-SDR range
                            self.end_freq = new_end
                            self.freq_range = self.end_freq - self.start_freq
                            self.center_freq = self.start_freq + (self.freq_range / 2)
                            self.sdr.setFrequency(SOAPY_SDR_RX, 0, self.center_freq)
                            self.clear_heatmap()  # Clear display
                            self.add_msg(f"Frequency range: {self.start_freq/1e6:.3f}-{self.end_freq/1e6:.3f} MHz")
                            
                        else:
                            self.add_msg(f"End frequency must be between start frequency and 1766 MHz")
                    except ValueError:
                        self.add_msg("Invalid frequency format. Please enter a number.")
                finally:
                    # Restore non-blocking input mode
                    tty.setcbreak(sys.stdin.fileno())
                    self.paused = False
            elif char == 'h':  # Show help
                self.show_help()
            elif char == ' ':  # Space key to toggle pause
                self.paused = not self.paused
                self.add_msg("Scanning " + ("paused" if self.paused else "resumed"))
            elif char == 'k':  # Toggle peak hold
                self.peak_hold = not self.peak_hold
                self.add_msg(f"Peak hold {'enabled' if self.peak_hold else 'disabled'}")
            elif char == 'v':  # Toggle averaging
                self.averaging = not self.averaging
                self.add_msg(f"Averaging {'enabled' if self.averaging else 'disabled'}")
            elif char == 'l':  # Toggle auto-scaling
                self.auto_scale = not self.auto_scale
                self.add_msg(f"Auto-scaling {'enabled' if self.auto_scale else 'disabled'}")
            elif char == 't':  # Cycle color scheme
                self.color_scheme = (self.color_scheme + 1) % 6  # Update to cycle through 6 schemes
                schemes = ['Default', 'Hot', 'Viridis', 'Plasma', 'Magma', 'Grayscale']
                self.add_msg(f"Color scheme: {schemes[self.color_scheme]}")
            elif char == '+':  # Zoom in around cursor
                # Calculate new range (half the current range)
                new_range = max(0.5e6, self.freq_range * 0.5)
                
                # Calculate how much to adjust start/end to maintain cursor position
                cursor_ratio = (self.cursor_freq - self.start_freq) / self.freq_range
                range_change = self.freq_range - new_range
                
                # Adjust start and end frequencies while keeping cursor position ratio
                new_start = self.start_freq + (range_change * cursor_ratio)
                new_end = new_start + new_range
                
                # Check if new range is within original bounds
                if self.start_freq <= new_start and new_end <= self.end_freq:
                    self.freq_range = new_range
                    self.center_freq = new_start + (new_range / 2)
                    self.sdr.setFrequency(SOAPY_SDR_RX, 0, self.center_freq)
                    self.clear_heatmap()  # Clear display when zooming
                    self.add_msg(f"Zoom: {self.freq_range/1e6:.1f} MHz span")
                else:
                    self.add_msg(f"Cannot zoom further: would exceed frequency bounds")
            elif char == '-':  # Zoom out around cursor
                # Calculate new range (double the current range)
                new_range = min(self.end_freq - self.start_freq, self.freq_range * 2)
                
                # Calculate how much to adjust start/end to maintain cursor position
                cursor_ratio = (self.cursor_freq - self.start_freq) / self.freq_range
                range_change = new_range - self.freq_range
                
                # Adjust start and end frequencies while keeping cursor position ratio
                new_start = self.start_freq - (range_change * cursor_ratio)
                new_end = new_start + new_range
                
                # Check if new range is within original bounds
                if new_start >= self.start_freq and new_end <= self.end_freq:
                    self.freq_range = new_range
                    self.center_freq = new_start + (new_range / 2)
                    self.sdr.setFrequency(SOAPY_SDR_RX, 0, self.center_freq)
                    self.clear_heatmap()  # Clear display when zooming
                    self.add_msg(f"Zoom: {self.freq_range/1e6:.1f} MHz span")
                else:
                    self.add_msg("Cannot zoom further: would exceed frequency bounds")
            elif char == 'w':  # Slow down waterfall
                self.scroll_speed = max(0.05, self.scroll_speed - 0.05)
                self.add_msg(f"Waterfall speed: {self.scroll_speed:.2f}x")
            elif char == 'W':  # Speed up waterfall
                self.scroll_speed = min(2.0, self.scroll_speed + 0.05)
                self.add_msg(f"Waterfall speed: {self.scroll_speed:.2f}x")
            elif char == 'R':  # Toggle recording
                if not self.recording:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    self.record_file = f"spectrum_{timestamp}.iq"
                    self.recording = True
                    self.add_msg(f"Recording to {self.record_file}")
                else:
                    self.recording = False
                    self.record_file = None
                    self.add_msg("Recording stopped")
            elif char == 's':  # Save screenshot
                # Calculate frequency range
                freq_start = self.center_freq - (self.freq_range / 2)
                freq_end = self.center_freq + (self.freq_range / 2)
                # Create timestamp
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                # Get script directory
                script_dir = os.path.dirname(os.path.abspath(__file__))
                # Create filename with timestamp and frequency range
                filename = os.path.join(script_dir, 
                    f"spectrum_{timestamp}_{freq_start/1e6:.3f}-{freq_end/1e6:.3f}MHz.png")
                
                # Create PIL image from current display
                img = Image.fromarray(self.get_display_array())
                img.save(filename)
                self.add_msg(f"Saved screenshot to {filename}")
            elif char == 'q':  # Quit on 'q'
                self.add_msg("Quitting...")
                self.cleanup()
                os._exit(0)  # Force exit the program
            elif char == '[':  # Existing controls
                self.cursor_freq = max(
                    self.center_freq - (self.freq_range / 2),
                    self.cursor_freq - self.cursor_step
                )
            elif char == ']':
                self.cursor_freq = min(
                    self.center_freq + (self.freq_range / 2),
                    self.cursor_freq + self.cursor_step
                )
            elif char == ',':  # Fine control (0.001MHz = 1kHz)
                self.cursor_freq = max(
                    self.center_freq - (self.freq_range / 2),
                    self.cursor_freq - 0.001e6
                )
            elif char == '.':
                self.cursor_freq = min(
                    self.center_freq + (self.freq_range / 2),
                    self.cursor_freq + 0.001e6
                )
            elif char == '{':  # Existing controls
                self.cursor_freq = max(
                    self.center_freq - (self.freq_range / 2),
                    self.cursor_freq - self.cursor_step*2
                )
            elif char == '}':
                self.cursor_freq = min(
                    self.center_freq + (self.freq_range / 2),
                    self.cursor_freq + self.cursor_step*2
                )
            elif char == 'j':  # Jump to frequency
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)
                try:
                    self.paused = True
                    os.system('clear')
                    freq_input = input("\nEnter frequency (append 'M' for MHz, or Hz by default): ")
                    try:
                        # Remove any spaces and convert to uppercase
                        freq_input = freq_input.strip().upper()
                        
                        # Check if input ends with 'M' for MHz
                        if freq_input.endswith('M'):
                            freq = float(freq_input[:-1]) * 1e6  # Convert MHz to Hz
                        else:
                            freq = float(freq_input)  # Assume Hz
                        
                        # Validate frequency is within range
                        if self.start_freq <= freq <= self.end_freq:
                            self.cursor_freq = freq
                            self.add_msg(f"Jumped to {freq/1e6:.3f} MHz")
                        else:
                            self.add_msg(f"Frequency must be between {self.start_freq/1e6:.3f} and {self.end_freq/1e6:.3f} MHz")
                    except ValueError:
                        self.add_msg("Invalid frequency format")
                finally:
                    # Restore non-blocking input mode
                    tty.setcbreak(sys.stdin.fileno())
                    self.paused = False
            elif char == 'd':  # Set gain
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)
                try:
                    self.paused = True
                    os.system('clear')
                    gain_input = input("\nEnter gain (0-49.6 dB): ")
                    try:
                        gain = float(gain_input)
                        if 0 <= gain <= 49.6:
                            self.sdr.setGain(SOAPY_SDR_RX, 0, gain)
                            self.add_msg(f"Gain set to: {gain:.1f} dB")
                        else:
                            self.add_msg("Gain must be between 0 and 49.6 dB")
                    except ValueError:
                        self.add_msg("Invalid gain format")
                finally:
                    # Restore non-blocking input mode
                    tty.setcbreak(sys.stdin.fileno())
                    self.paused = False
            elif char == 'r':  # Sample rate control
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)
                try:
                    os.system('clear')
                    rate_input = input("\nEnter sample rate in MHz (0.25-3.2): ")
                    try:
                        new_rate = float(rate_input) * 1e6
                        if 0.25e6 <= new_rate <= 3.2e6:
                            self.sdr.setSampleRate(SOAPY_SDR_RX, 0, new_rate)
                            self.sample_rate = new_rate
                            self.add_msg(f"Sample rate set to: {new_rate/1e6:.2f} MHz")
                        else:
                            self.add_msg("Rate out of valid range (0.25-3.2 MHz)")
                    except ValueError:
                        self.add_msg("Invalid rate format. Please enter a number.")
                finally:
                    tty.setcbreak(sys.stdin.fileno())
            elif char == 'b':  # Band selection
                # Temporarily restore normal terminal behavior for input
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)
                try:
                    self.paused = True
                    selected_band = self.show_band_selection()
                    
                    if selected_band:
                        new_start, new_end = self.bands[selected_band]
                        
                        # Update frequency range
                        self.start_freq = new_start
                        self.end_freq = new_end
                        self.freq_range = new_end - new_start
                        self.center_freq = new_start + (self.freq_range / 2)
                        self.sdr.setFrequency(SOAPY_SDR_RX, 0, self.center_freq)
                        
                        # Update cursor to center of new band
                        self.cursor_freq = self.center_freq
                        
                        # Clear the heatmap for the new band
                        self.clear_heatmap()
                        
                        self.display_message = f"Switched to {selected_band} band"
                
                finally:
                    # Restore non-blocking input mode
                    tty.setcbreak(sys.stdin.fileno())
                    self.paused = False
                    os.system('clear')
            elif char == 'a':  # AGC Toggle (using 'k' for automatic)
                self.agc_enabled = not self.agc_enabled
                if self.agc_enabled:
                    self.agc_history = []  # Reset history when enabling
                    self.display_message = "AGC enabled"
                else:
                    self.display_message = "AGC disabled"
                self.message_time = time.time()
            elif char == 'A':  # AGC target
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)
                try:
                    self.paused = True
                    target = input("\nEnter AGC target level (dB): ")
                    try:
                        new_target = float(target)
                        if -60 <= new_target <= 0:
                            self.agc_target = new_target
                            self.display_message = f"AGC target set to {new_target} dB"
                        else:
                            self.display_message = "Target must be between -60 and 0 dB"
                    except ValueError:
                        self.display_message = "Invalid target value"
                finally:
                    tty.setcbreak(sys.stdin.fileno())
                    self.paused = False
                    self.message_time = time.time()
            elif char == 'z':  # AGC speed
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)
                try:
                    self.paused = True
                    os.system('clear')
                    speed = input("\nEnter AGC speed (0.1-1.0): ")
                    try:
                        new_speed = float(speed)
                        if 0.1 <= new_speed <= 1.0:
                            self.agc_speed = new_speed
                            self.display_message = f"AGC speed set to {new_speed}"
                        else:
                            self.display_message = "Speed must be between 0.1 and 1.0"
                    except ValueError:
                        self.display_message = "Invalid speed value"
                finally:
                    tty.setcbreak(sys.stdin.fileno())
                    self.paused = False
                    self.message_time = time.time()
            elif char == 'y':  # Save settings
                self.save_settings()
            elif char == 'l':  # Load settings
                self.load_settings()
            elif char == 'i':  # Show band information
                self.show_band_info()
            elif char == 'n':  # Add annotation
                self.add_time_annotation()
            elif char == 'e':  # Export data
                self.export_spectrum_data()
            elif char == 'p':  # Decrease PPM
                self.ppm = max(-100, self.ppm - 1)  # Limit to -100 PPM
                if hasattr(self.sdr, 'setFrequencyCorrection'):
                    self.sdr.setFrequencyCorrection(SOAPY_SDR_RX, 0, self.ppm)
                self.add_msg(f"PPM correction: {self.ppm}")
            elif char == 'P':  # Increase PPM
                self.ppm = min(100, self.ppm + 1)  # Limit to +100 PPM
                if hasattr(self.sdr, 'setFrequencyCorrection'):
                    self.sdr.setFrequencyCorrection(SOAPY_SDR_RX, 0, self.ppm)
                self.add_msg(f"PPM correction: {self.ppm}")
            elif char == 'g':  # Decrease gain
                new_gain = max(0, self.current_gain - 1)  # Decrease by 1 dB, minimum 0
                self.sdr.setGain(SOAPY_SDR_RX, 0, new_gain)
                self.current_gain = new_gain
                self.add_msg(f"Gain: {self.current_gain:.1f} dB")
            elif char == 'G':  # Increase gain
                new_gain = min(49.6, self.current_gain + 1)  # Increase by 1 dB, maximum 49.6
                self.sdr.setGain(SOAPY_SDR_RX, 0, new_gain)
                self.current_gain = new_gain
                self.add_msg(f"Gain: {self.current_gain:.1f} dB")
            elif char == 'S':  # Toggle automatic screenshots
                self.auto_export_enabled = not self.auto_export_enabled
                self.add_msg(f"Automatic screenshots {'enabled' if self.auto_export_enabled else 'disabled'}")
    
    def get_power_spectrum(self):
        """Get the power spectrum using SoapySDR with improved error handling"""
        start_time = time.perf_counter()
        
        # Use pre-calculated FFT size
        buffer = np.zeros(self.fft_size, np.complex64)
        
        # Read samples with timeout and retry mechanism
        max_retries = 3
        for retry in range(max_retries):
            try:
                status = self.sdr.readStream(self.rx_stream, [buffer], len(buffer), timeoutUs=1000000)
                
                if status.ret > 0:  # Successful read
                    # Process only valid samples
                    valid_samples = buffer[:status.ret]
                    
                    # Apply pre-calculated window and compute FFT
                    windowed_samples = valid_samples * self._window[:len(valid_samples)]
                    fft = np.fft.fft(windowed_samples)
                    fft_shifted = np.fft.fftshift(fft)
                    
                    # Calculate power spectrum
                    power_db = 20 * np.log10(np.abs(fft_shifted) + 1e-15)
                    
                    # Process spectrum through enhanced signal processing
                    power_db = self.process_spectrum(power_db)
                    
                    # Resample to match display width
                    power_db_resized = signal.resample(
                        power_db, 
                        self.graph_width, 
                        window=('kaiser', 8.0)
                    )
                    
                    # Update scan timing statistics
                    scan_duration = int((time.perf_counter() - start_time) * 1000)
                    if scan_duration > 0:
                        self.scan_times.append(scan_duration)
                        if len(self.scan_times) > self.scan_times_max:
                            self.scan_times.pop(0)
                        self.last_scan_time = int(sum(self.scan_times) / len(self.scan_times))
                    
                    return power_db_resized
                    
                elif status.ret == -4:  # Timeout
                    if retry < max_retries - 1:
                        time.sleep(0.1)
                        continue
                    else:
                        self.display_message = "Stream timeout after retries"
                        return np.zeros(self.graph_width)
                else:
                    self.display_message = f"Stream error: {status.ret}"
                    return np.zeros(self.graph_width)
                    
            except Exception as e:
                if retry < max_retries - 1:
                    self.display_message = f"Read error, retrying... ({e})"
                    time.sleep(0.1)
                else:
                    self.display_message = f"Failed to read spectrum: {e}"
                    return np.zeros(self.graph_width)
        
        return np.zeros(self.graph_width)
    
    def update_agc(self, spectrum):
        """Update AGC based on current signal levels"""
        if not self.agc_enabled:
            return
            
        current_time = time.time()
        if current_time - self.last_agc_update < self.agc_update_interval:
            return
            
        # Calculate current average power
        avg_power = np.mean(spectrum)
        self.agc_history.append(avg_power)
        if len(self.agc_history) > self.agc_history_len:
            self.agc_history.pop(0)
        
        # Calculate smoothed power level
        smoothed_power = np.mean(self.agc_history)
        
        # Calculate error from target
        error = self.agc_target - smoothed_power
        
        # Calculate new gain
        gain_delta = error * self.agc_speed
        new_gain = np.clip(
            self.current_gain + gain_delta,
            self.agc_min_gain,
            self.agc_max_gain
        )
        
        # Update gain if it changed significantly (avoid tiny adjustments)
        if abs(new_gain - self.current_gain) > 0.5:
            self.current_gain = new_gain
            self.sdr.setGain(SOAPY_SDR_RX, 0, self.current_gain)
            self.add_msg(f"AGC: Gain set to {self.current_gain:.1f} dB")
        
        self.last_agc_update = current_time
    
    def update_heatmap(self):
        """Update the heatmap with improved signal distinction"""
        # Get new spectrum data
        spectrum = self.get_power_spectrum()
        
        # Apply median filter to reduce noise
        spectrum = signal.medfilt(spectrum, kernel_size=3)
        
        # Ensure spectrum is the correct shape before adding to buffer
        if spectrum.shape != (self.graph_width,):
            # Resize spectrum to match graph width if needed
            spectrum = signal.resample(spectrum, self.graph_width)
        
        # Existing averaging and peak hold logic
        if self.averaging:
            # Only append if buffer is empty or shapes match
            if not self.avg_buffer or spectrum.shape == self.avg_buffer[0].shape:
                self.avg_buffer.append(spectrum)
                if len(self.avg_buffer) > self.avg_length:
                    self.avg_buffer.pop(0)
                spectrum = np.mean(np.array(self.avg_buffer), axis=0)
        
        if self.peak_hold:
            if self.peak_values.shape != spectrum.shape:
                self.peak_values = np.zeros_like(spectrum)
            self.peak_values = np.maximum(self.peak_values * 0.99, spectrum)  # Added decay factor
            spectrum = self.peak_values
        
        # Enhanced dynamic range compression
        if self.auto_scale:
            p_min, p_max = np.percentile(spectrum, [5, 99.5])
            spectrum = np.clip(spectrum, p_min, p_max)
            spectrum = np.interp(spectrum, (p_min, p_max), (0, 255))
        else:
            # Improved fixed scale normalization
            spectrum = np.clip((spectrum - np.min(spectrum)) * 3, 0, 255)
        
        # Shift existing data down based on scroll speed
        shift = int(self.scroll_speed)
        if shift > 0:
            self.heatmap = np.roll(self.heatmap, -shift, axis=0)
            
            # Update fill level tracking and export if enabled
            if self.auto_export_enabled:  # Only track and export if enabled
                if not self.fb_filled:
                    self.fb_fill_level += shift
                    if self.fb_fill_level >= self.graph_height:
                        self.fb_filled = True
                        self.export_filled_framebuffer()
                        # Reset for next fill
                        self.fb_filled = False
                        self.fb_fill_level = 0
            
            # Update annotation positions when heatmap shifts
            annotations_to_remove = []
            for annotation in self.annotations:
                if annotation['time'] not in self.annotation_positions:
                    # Initialize new annotation at bottom
                    self.annotation_positions[annotation['time']] = self.height - self.bottom_margin
                else:
                    # Shift existing annotation up
                    self.annotation_positions[annotation['time']] -= shift
                    # Mark for removal if scrolled past top margin
                    if self.annotation_positions[annotation['time']] <= self.top_margin:
                        annotations_to_remove.append(annotation)
            
            # Remove annotations that have scrolled off screen
            for annotation in annotations_to_remove:
                self.annotations.remove(annotation)
                self.annotation_positions.pop(annotation['time'], None)
            
            # Add new data at the top with smoothing
            smoothed_spectrum = signal.savgol_filter(spectrum, 5, 2)
            self.heatmap[-shift:, :] = smoothed_spectrum[np.newaxis, :].repeat(shift, axis=0)
    
    def draw_frequency_labels(self, colored):
        # Create PIL Image for text rendering
        img = Image.fromarray(colored)
        draw = ImageDraw.Draw(img)
        
        # Calculate frequency range
        freq_start = self.center_freq - (self.freq_range / 2)
        freq_end = self.center_freq + (self.freq_range / 2)
        
        # Draw frequency marks and labels
        step_small = 0.1e6  # 0.1MHz in Hz for small ticks
        step_large = 0.5e6  # 0.5MHz in Hz for labels and large ticks
        
        # Draw all small ticks first
        for freq in np.arange(freq_start, freq_end, step_small):
            x_pos = int((freq - freq_start) / self.freq_range * self.graph_width)
            if 0 <= x_pos < self.graph_width:
                # Draw small tick mark
                draw.line([(x_pos, self.graph_height), (x_pos, self.graph_height + 2)], 
                         fill=(255, 255, 255))
        
        # Draw large ticks and labels
        for freq in np.arange(freq_start, freq_end, step_large):
            x_pos = int((freq - freq_start) / self.freq_range * self.graph_width)
            if 0 <= x_pos < self.graph_width:
                # Format frequency in MHz
                freq_mhz = freq / 1e6
                label = f"{freq_mhz:.1f}"
                # Draw larger tick mark
                draw.line([(x_pos, self.graph_height), (x_pos, self.graph_height + 5)], 
                         fill=(255, 255, 255))
                # Draw frequency text
                draw.text((x_pos-15, self.graph_height + 10), label, 
                         font=self.font, fill=(255, 255, 255))
        
        return np.array(img)
        
    def draw_time_labels(self, colored):
        img = Image.fromarray(colored)
        draw = ImageDraw.Draw(img)
        
        # Calculate time per pixel
        pixels_per_minute = self.graph_height / (10 * 60)  # 10 minutes for full height
        current_time = time.time()
        
        # Draw minute marks
        for minutes in range(10 * 60):  # 10 minutes in seconds
            y_pos = int(minutes * pixels_per_minute)
            if 0 <= y_pos < self.graph_height:
                # Draw tick mark and label every 10 minutes
                if minutes % 10 == 0:
                    # Draw long tick and label
                    draw.line([(0, y_pos), (10, y_pos)], fill=(255, 255, 255))
                    minutes_ago = int((current_time - self.start_time) / 60) - minutes
                    if minutes_ago >= 0:
                        time_str = f"-{minutes_ago}m"
                        draw.text((10, y_pos-6), time_str, font=self.font, fill=(255, 255, 255))
                elif minutes % 2 == 0:  # 2-minute marks
                    # Draw short tick
                    draw.line([(0, y_pos), (5, y_pos)], fill=(255, 255, 255))
        
        return np.array(img)
        
    def create_status_text(self):
        status = []
        status.extend([
            f"[{'>' if not self.paused else '||'}] {'RUNNING' if not self.paused else 'PAUSED'}",
            f"{'AUTO' if self.auto_scale else 'FIXED'} SCALE",
            f"g:Gain: {self.current_gain:.1f} dB",
            f"r:Rate: {self.sample_rate/1e6:.1f}MHz",
            f"k:Peak: {'ON' if self.peak_hold else 'OFF'}",
            f"v:Avg: {'ON' if self.averaging else 'OFF'}",
            f"a:AGC: {'ON' if self.agc_enabled else 'OFF'}",
            f"t:{['Default', 'Hot', 'Viridis', 'Plasma', 'Magma', 'Gray'][self.color_scheme]}",
            f"w:Wtr.Spd: {self.scroll_speed:.1f}x",
            f"p:PPM: {self.ppm:+d}",  # Added PPM display with sign
            f"S:Auto-export: {'ON' if self.auto_export_enabled else 'OFF'}",  # Add auto-export status
            f"H:Help"
        ])
        return status
    
    def draw_framebuffer(self):
        # Create colored array with new color gradient
        colored = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        # Vectorized color mapping for heatmap - adjust position for top margin
        values = self.heatmap[:self.graph_height, :self.graph_width]
        colored_section = colored[self.top_margin:self.top_margin+self.graph_height, 
                                self.left_margin:self.left_margin+self.graph_width]
        
        # Apply color scheme consistently
        self.apply_color_scheme(values, colored_section)
        
        # Draw cursor line
        freq_start = self.center_freq - (self.freq_range / 2)
        cursor_x = int((self.cursor_freq - freq_start) / self.freq_range * self.graph_width)
        if 0 <= cursor_x < self.graph_width:
            colored[self.top_margin:self.top_margin+self.graph_height, 
                   cursor_x + self.left_margin] = [0, 255, 0]
            if cursor_x > 0:
                colored[self.top_margin:self.top_margin+self.graph_height, 
                       cursor_x + self.left_margin - 1] = [0, 128, 0]
            if cursor_x < self.graph_width - 1:
                colored[self.top_margin:self.top_margin+self.graph_height, 
                       cursor_x + self.left_margin + 1] = [0, 128, 0]

        # Convert to PIL for text drawing
        img = Image.fromarray(colored)
        draw = ImageDraw.Draw(img)
        
        # Draw frequency labels at the bottom
        freq_start = self.center_freq - (self.freq_range / 2)
        freq_end = self.center_freq + (self.freq_range / 2)
        
        # Draw frequency marks and labels
        step_small = 0.1e6  # 0.1MHz
        step_large = 0.5e6  # 0.5MHz
        
        # Draw small ticks
        for freq in np.arange(freq_start, freq_end, step_small):
            x_pos = int((freq - freq_start) / self.freq_range * self.graph_width)
            if 0 <= x_pos < self.graph_width:
                # Draw small tick mark - add left_margin to x_pos
                draw.line([
                    (x_pos + self.left_margin, self.top_margin + self.graph_height),
                    (x_pos + self.left_margin, self.top_margin + self.graph_height + 2)
                ], fill=(255, 255, 255))
        
        # Draw large ticks and labels
        for freq in np.arange(freq_start, freq_end, step_large):
            x_pos = int((freq - freq_start) / self.freq_range * self.graph_width)
            if 0 <= x_pos < self.graph_width:
                freq_mhz = freq / 1e6
                label = f"{freq_mhz:.1f}"
                # Draw larger tick mark - add left_margin to x_pos
                draw.line([
                    (x_pos + self.left_margin, self.top_margin + self.graph_height),
                    (x_pos + self.left_margin, self.top_margin + self.graph_height + 5)
                ], fill=(255, 255, 255))
                # Draw frequency text - add left_margin to x_pos
                draw.text(
                    (x_pos + self.left_margin - 15, self.top_margin + self.graph_height + 10),
                    label,
                    font=self.font,
                    fill=(255, 255, 255))

        # Calculate cursor position
        cursor_x = int((self.cursor_freq - freq_start) / self.freq_range * self.graph_width)
        
        # Draw status information in top right corner
        status_items = self.create_status_text()
                
        # Calculate maximum width needed
        max_width = max(draw.textlength(item, font=self.font) for item in status_items)
        
        # Draw background rectangles for better readability
        margin = 5
        
        # Right status box
        rect_left = int(self.width - max_width - margin * 2)
        rect_top = margin
        rect_right = self.width - margin
        rect_bottom = margin + len(status_items) * 15
        
        # Draw semi-transparent backgrounds
        # Status box (right)
        background = Image.new('RGBA', 
                             (int(rect_right - rect_left), int(rect_bottom - rect_top)), 
                             (0, 0, 0, 128))  # Reduced opacity
        img.paste(background, (rect_left, rect_top), background)
        
        # Draw status items
        x = int(self.width - max_width - margin)
        y = margin
        for item in status_items:
            draw.text((x, y), item, font=self.font, fill=(255, 255, 255))
            y += 15
        
        # Draw cursor info on the left side
        if 0 <= cursor_x < self.graph_width:
            signal_strength = self.heatmap[-1, cursor_x]
            current_time = datetime.now().strftime("%H:%M:%S")
            cursor_freq_mhz = self.cursor_freq / 1e6
            info_text = (f"Frequency: {cursor_freq_mhz:.3f} MHz\n"
                        f"Signal: {signal_strength:.1f} dB\n"
                        f"Time: {current_time}\n"
                        f"Range: {self.start_freq/1e6:.3f}-{self.end_freq/1e6:.3f} MHz\n"
                        f"Scan: {self.last_scan_time}ms avg")
            
            # Left info box - increase height to accommodate new lines
            left_info_width = int(draw.textlength("Frequency: 000.000 MHz", font=self.font))
            left_info_height = 75  # Increased from 45 to accommodate new lines
            left_background = Image.new('RGBA', 
                                     (left_info_width + margin * 2, left_info_height), 
                                     (0, 0, 0, 128))  # Reduced opacity
            img.paste(left_background, (margin, margin), left_background)
            
            # Draw the text
            draw.text((margin * 2, margin), info_text, font=self.font, fill=(255, 255, 255))

        # Draw message if it exists and is within duration
        current_time = time.time()
        if self.display_message and current_time - self.message_time < self.message_duration:
            # Calculate text size
            text_width = draw.textlength(self.display_message, font=self.font)
            text_height = 14  # Approximate font height
            
            # Calculate center position
            x = (self.width - text_width) // 2
            y = self.height // 2
            
            # Draw black background for better visibility
            margin = 5
            draw.rectangle([
                (x - margin, y - margin),
                (x + text_width + margin, y + text_height + margin)
            ], fill=(0, 0, 0))
            
            # Draw text
            draw.text((x, y), self.display_message, font=self.font, fill=(255, 255, 255))

        # Draw time markers and annotations
        self.draw_time_markers(img, draw)

        # Convert back to numpy array
        colored = np.array(img)

        # Write to framebuffer
        if self.bytes_per_pixel == 4:
            # 32-bit color (unchanged)
            fb_array = np.zeros((self.height, self.width, 4), dtype=np.uint8)
            fb_array[..., :3] = colored[..., ::-1]  # RGB -> BGR
            fb_array[..., 3] = 255
            buffer_data = fb_array.tobytes()[:self.fb_size]
            self.fb_data.seek(0)
            self.fb_data.write(buffer_data)
        elif self.bytes_per_pixel == 2:
            # Optimized 16-bit color conversion
            # Convert RGB888 to RGB565 using vectorized operations
            r = (colored[..., 0] >> 3).astype(np.uint16)  # 5 bits for red
            g = (colored[..., 1] >> 2).astype(np.uint16)  # 6 bits for green
            b = (colored[..., 2] >> 3).astype(np.uint16)  # 5 bits for blue
            
            # Combine using bit operations (RGB565 format)
            color = ((r << 11) | (g << 5) | b).astype(np.uint16)
            
            # Create buffer and write directly
            buffer_data = color.tobytes()
            self.fb_data.seek(0)
            self.fb_data.write(buffer_data[:self.fb_size])

    def cleanup(self):
        """Enhanced cleanup of resources"""
        try:
            # Save settings before cleanup
            self.save_settings()
            
            # Cleanup SDR resources
            if hasattr(self, 'rx_stream'):
                try:
                    self.sdr.deactivateStream(self.rx_stream)
                    self.sdr.closeStream(self.rx_stream)
                except Exception as e:
                    print(f"Error cleaning up SDR stream: {e}")
            
            # Cleanup framebuffer
            if hasattr(self, 'fb_data'):
                try:
                    self.fb_data.close()
                except Exception as e:
                    print(f"Error closing framebuffer data: {e}")
            
            if hasattr(self, 'fb'):
                try:
                    self.fb.close()
                except Exception as e:
                    print(f"Error closing framebuffer: {e}")
            
            # Restore terminal settings
            if hasattr(self, 'old_settings'):
                try:
                    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)
                except Exception as e:
                    print(f"Error restoring terminal settings: {e}")
            
        except Exception as e:
            print(f"Error during cleanup: {e}")
        finally:
            print("Cleanup completed")

    def get_display_array(self):
        """Get the current display as a numpy array"""
        # Create colored array with new color gradient
        colored = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        # Copy current heatmap visualization
        values = self.heatmap[:self.graph_height, :self.graph_width]
        colored_section = colored[self.top_margin:self.top_margin+self.graph_height, 
                                self.left_margin:self.left_margin+self.graph_width]
        
        # Use the same color scheme application as draw_framebuffer
        self.apply_color_scheme(values, colored_section)

        # Draw cursor
        freq_start = self.center_freq - (self.freq_range / 2)
        cursor_x = int((self.cursor_freq - freq_start) / self.freq_range * self.graph_width)
        if 0 <= cursor_x < self.graph_width:
            colored[:self.graph_height + self.top_margin, cursor_x + self.left_margin] = [0, 255, 0]
            if cursor_x > 0:
                colored[:self.graph_height + self.top_margin, cursor_x + self.left_margin - 1] = [0, 128, 0]
            if cursor_x < self.graph_width - 1:
                colored[:self.graph_height + self.top_margin, cursor_x + self.left_margin + 1] = [0, 128, 0]

        # Convert to PIL for text drawing
        img = Image.fromarray(colored)
        draw = ImageDraw.Draw(img)
        
        # Draw frequency labels at the bottom
        freq_start = self.center_freq - (self.freq_range / 2)
        freq_end = self.center_freq + (self.freq_range / 2)
        
        # Draw frequency marks and labels
        step_small = 0.1e6  # 0.1MHz
        step_large = 0.5e6  # 0.5MHz
        
        # Draw small ticks
        for freq in np.arange(freq_start, freq_end, step_small):
            x_pos = int((freq - freq_start) / self.freq_range * self.graph_width)
            if 0 <= x_pos < self.graph_width:
                draw.line([(x_pos + self.left_margin, self.graph_height + self.top_margin), 
                          (x_pos + self.left_margin, self.graph_height + self.top_margin + 2)], 
                         fill=(255, 255, 255))
        
        # Draw large ticks and labels
        for freq in np.arange(freq_start, freq_end, step_large):
            x_pos = int((freq - freq_start) / self.freq_range * self.graph_width)
            if 0 <= x_pos < self.graph_width:
                freq_mhz = freq / 1e6
                label = f"{freq_mhz:.1f}"
                draw.line([(x_pos + self.left_margin, self.graph_height + self.top_margin), 
                          (x_pos + self.left_margin, self.graph_height + self.top_margin + 5)], 
                         fill=(255, 255, 255))
                draw.text((x_pos + self.left_margin - 15, self.graph_height + self.top_margin + 10), 
                         label, font=self.font, fill=(255, 255, 255))
        
        # Draw time labels and annotations
        current_time = time.time()
        
        # Draw annotations
        for annotation in self.annotations:
            # Calculate position from bottom instead of top
            time_diff = current_time - annotation['time']
            
            # Calculate y position using effective pixels per second
            effective_pixels_per_second = self.base_pixels_per_second * self.scroll_speed
            y_pos = self.graph_height - int(time_diff * effective_pixels_per_second) + self.top_margin
            
            if self.top_margin <= y_pos < self.height - self.bottom_margin:
                # Draw dashed marker line manually
                dash_length = 4
                for x in range(0, self.width, dash_length * 2):
                    draw.line([(x, y_pos), (x + dash_length, y_pos)], 
                             fill=(255, 255, 0), width=1)
                
                # Draw annotation text with background
                timestamp = datetime.fromtimestamp(annotation['time']).strftime("%H:%M:%S")
                text = f"{annotation['text']} ({annotation['frequency']/1e6:.3f}MHz | {timestamp})"
                text_bbox = draw.textbbox((10, y_pos-6), text, font=self.font)
                
                # Draw semi-transparent background
                draw.rectangle([text_bbox[0]-2, text_bbox[1]-2, text_bbox[2]+2, text_bbox[3]+2],
                             fill=(0, 0, 0))
                
                # Draw text
                draw.text((10, y_pos-6), text, font=self.font, fill=(255, 255, 0))
        
        # Draw status information in top right corner
        status_items = self.create_status_text()
        
        # Calculate maximum width needed
        max_width = max(draw.textlength(item, font=self.font) for item in status_items)
        
        # Draw background rectangles for better readability
        margin = 5
        
        # Right status box
        rect_left = int(self.width - max_width - margin * 2)
        rect_top = margin
        rect_right = self.width - margin
        rect_bottom = margin + len(status_items) * 15
        
        # Draw semi-transparent backgrounds
        background = Image.new('RGBA', 
                             (int(rect_right - rect_left), int(rect_bottom - rect_top)), 
                             (0, 0, 0, 128))
        img.paste(background, (rect_left, rect_top), background)
        
        # Draw status items
        x = int(self.width - max_width - margin)
        y = margin
        for item in status_items:
            draw.text((x, y), item, font=self.font, fill=(255, 255, 255))
            y += 15
        
        # Draw cursor info on the left side
        cursor_x = int((self.cursor_freq - self.start_freq) / self.freq_range * self.graph_width)
        if 0 <= cursor_x < self.graph_width:
            signal_strength = self.heatmap[-1, cursor_x]
            current_time = datetime.now().strftime("%H:%M:%S")
            cursor_freq_mhz = self.cursor_freq / 1e6
            info_text = (f"Frequency: {cursor_freq_mhz:.3f} MHz\n"
                        f"Signal: {signal_strength:.1f} dB\n"
                        f"Time: {current_time}\n"
                        f"Range: {self.start_freq/1e6:.3f}-{self.end_freq/1e6:.3f} MHz\n"
                        f"Scan: {self.last_scan_time}ms avg")
        
        # Left info box
        left_info_width = int(draw.textlength("Frequency: 000.000 MHz", font=self.font))
        left_info_height = 75
        left_background = Image.new('RGBA', 
                                 (left_info_width + margin * 2, left_info_height), 
                                 (0, 0, 0, 128))
        img.paste(left_background, (margin, margin), left_background)
        
        # Draw the text
        draw.text((margin * 2, margin), info_text, font=self.font, fill=(255, 255, 255))

        return np.array(img)

    def apply_color_scheme(self, values, colored_section):
        """Apply color scheme consistently across display methods"""
        if self.color_scheme == 0:  # Default blue-red-yellow gradient
            values_expanded = values[..., np.newaxis]
            blue = np.minimum(values * 3, 255)
            red = np.minimum((values - 85) * 3, 255)
            red[values < 85] = 0
            yellow = np.minimum((values - 170) * 3, 255)
            yellow[values < 170] = 0
            
            colored_section[..., 0] = red  # Red channel
            colored_section[..., 1] = yellow  # Green channel
            colored_section[..., 2] = blue  # Blue channel
        
        elif self.color_scheme == 1:  # Hot
            colored_section[..., 0] = np.minimum(values * 3, 255)  # Red
            colored_section[..., 1] = np.where(values > 85, np.minimum((values - 85) * 3, 255), 0)  # Green
            colored_section[..., 2] = np.where(values > 170, np.minimum((values - 170) * 3, 255), 0)  # Blue
        
        elif self.color_scheme == 2:  # Viridis-like
            colored_section[..., 0] = np.where(values > 170, np.minimum((values - 170) * 3, 255), 0)  # Red
            colored_section[..., 1] = np.minimum(values * 2, 255)  # Green
            colored_section[..., 2] = np.where(values < 127,  # Blue
                np.minimum(values * 2, 255),
                np.maximum(255 - (values - 127) * 2, 0))
        
        elif self.color_scheme == 3:  # Plasma-like
            colored_section[..., 0] = np.where(values > 85, np.minimum((values - 85) * 3, 255), 0)  # Red
            colored_section[..., 1] = np.where(values > 170, np.minimum((values - 170) * 3, 255), 0)  # Green
            colored_section[..., 2] = np.where(values < 127,  # Blue
                np.minimum(values * 2, 255),
                np.maximum(255 - (values - 127) * 2, 0))
        
        elif self.color_scheme == 4:  # Magma-like
            colored_section[..., 0] = np.minimum(values * 2, 255)  # Red
            colored_section[..., 1] = np.where(values > 127, np.minimum((values - 127) * 2, 255), 0)  # Green
            colored_section[..., 2] = np.where(values < 127,  # Blue
                np.minimum(values * 2, 255),
                np.maximum(255 - (values - 127) * 2, 0))
        
        elif self.color_scheme == 5:  # Grayscale
            gray = np.minimum(values, 255)
            colored_section[..., 0] = gray  # Red
            colored_section[..., 1] = gray  # Green
            colored_section[..., 2] = gray  # Blue

    def show_help(self):
        """Display help information with pagination"""
        # Temporarily restore normal terminal behavior
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)
        try:
            self.paused = True
            
            # ANSI color codes
            CYAN = "\033[96m"
            YELLOW = "\033[93m"
            GREEN = "\033[92m"
            RESET = "\033[0m"
            BOLD = "\033[1m"
            
            # ASCII art title
            title = f"""{CYAN}{BOLD}
╦ ╦┌─┐┌─┐┌┬┐┬ ┬┌─┐┬  ┬┌─┐
╠═╣├┤ ├─┤ │ │││├─┤└┐┌┘├┤ 
╩ ╩└─┘┴ ┴ ┴ └┴┘┴ ┴ └┘ └─┘
{RESET}"""
            
            # Get terminal size
            terminal_rows, terminal_cols = os.popen('stty size', 'r').read().split()
            terminal_rows = int(terminal_rows)
            
            help_sections = [
                f"""
{title}
{YELLOW}{BOLD}RTL-SDR Frequency Heatmap - Basic Controls{RESET}
{GREEN}----------------------------------------{RESET}
Space   - Pause/resume scanning
h       - Show this help
q       - Quit program

{YELLOW}{BOLD}Cursor Navigation{RESET}
{GREEN}----------------{RESET}
[/]     - Move cursor left/right (fine step)
{{/}}     - Move cursor left/right (coarse step)
,/.     - Fine tune cursor (1 kHz steps)
j       - Jump to specific frequency
+/-     - Zoom in/out around cursor""",

                f"""
{YELLOW}{BOLD}Frequency Control & Markers{RESET}
{GREEN}-------------------------{RESET}
<       - Set start frequency
>       - Set end frequency
1-5     - Jump to marker positions
6-0     - Set markers 1-5 at cursor
b       - Select predefined frequency band

{YELLOW}{BOLD}Display Settings{RESET}
{GREEN}--------------{RESET}
k       - Toggle peak hold
v       - Toggle averaging
l       - Toggle auto-scaling
t       - Cycle color schemes
w/W     - Adjust waterfall speed""",

                f"""
{YELLOW}{BOLD}Device Configuration{RESET}
{GREEN}------------------{RESET}
q       - Set gain (0-49.6 dB)
r       - Set sample rate (0.25-3.2 MHz)
p/P     - Adjust PPM correction

{YELLOW}{BOLD}AGC (Automatic Gain Control){RESET}
{GREEN}--------------------------{RESET}
g       - Decrease gain
G       - Increase gain 
a       - Toggle AGC
A       - Set AGC target level
z       - Set AGC speed""",

                f"""
{YELLOW}{BOLD}Recording & Analysis{RESET}
{GREEN}------------------{RESET}
s       - Save screenshot
n       - Add time/frequency annotation
i       - Show current band information
e       - Export spectrum data

{YELLOW}{BOLD}Settings Management{RESET}
{GREEN}-----------------{RESET}
w       - Save current settings
l       - Load saved settings"""
            ]

            current_section = 0
            while True:
                os.system('clear')
                print(help_sections[current_section])
                print(f"\n{CYAN}Page {current_section + 1}/{len(help_sections)}{RESET}")
                print(f"\n{GREEN}Use arrow keys or n/p for navigation, q to return{RESET}")
                
                # Get single keypress
                char = sys.stdin.read(1)
                
                if char == 'q':
                    break
                elif char == 'n' or char == '\x1b[C':  # next or right arrow
                    current_section = (current_section + 1) % len(help_sections)
                elif char == 'p' or char == '\x1b[D':  # prev or left arrow
                    current_section = (current_section - 1) % len(help_sections)

        finally:
            # Restore non-blocking input mode
            tty.setcbreak(sys.stdin.fileno())
            self.paused = False
            os.system('clear')

    def show_band_info(self):
        """Display enhanced information about the current frequency's band"""
        current_freq = self.cursor_freq
        
        # Find which band contains the current frequency
        current_band = None
        for band_name, (start, end) in self.bands.items():
            if start <= current_freq <= end:
                current_band = band_name
                break
        
        if current_band:
            details = self.band_details.get(current_band, {})
            
            # Create more detailed information string
            info_parts = [
                f"Band: {current_band}",
                f"Range: {self.bands[current_band][0]/1e6:.3f}-{self.bands[current_band][1]/1e6:.3f} MHz"
            ]
            
            if details:
                if 'mode' in details:
                    info_parts.append(f"Mode: {details['mode']}")
                if 'spacing' in details:
                    info_parts.append(f"Spacing: {details['spacing']/1e3:.1f} kHz")
                if 'description' in details:
                    info_parts.append(f"Use: {details['description']}")
            
            # Find nearby bands
            nearby_bands = []
            for band_name, (start, end) in self.bands.items():
                if band_name != current_band:
                    # Check if band is within ±10MHz
                    if abs(start - current_freq) < 10e6 or abs(end - current_freq) < 10e6:
                        nearby_bands.append(f"{band_name} ({start/1e6:.1f}-{end/1e6:.1f}MHz)")
            
            if nearby_bands:
                info_parts.append("Nearby: " + ", ".join(nearby_bands))
            
            self.add_msg(" | ".join(info_parts))
        else:
            # Show closest bands if not in any band
            closest_bands = []
            for band_name, (start, end) in self.bands.items():
                center = (start + end) / 2
                distance = abs(center - current_freq)
                closest_bands.append((distance, band_name, start, end))
            
            closest_bands.sort()  # Sort by distance
            closest = closest_bands[:3]  # Get 3 closest bands
            
            info = f"No band at {current_freq/1e6:.3f} MHz | Nearest: " + ", ".join(
                f"{band} ({start/1e6:.1f}-{end/1e6:.1f}MHz)" 
                for _, band, start, end in closest
            )
            self.add_msg(info)

    def detect_signals(self, spectrum):
        """Add signal detection capabilities"""
        # Calculate noise floor
        noise_floor = np.median(spectrum)
        noise_std = np.std(spectrum[spectrum < np.percentile(spectrum, 90)])
        
        # Dynamic threshold based on noise statistics
        threshold = noise_floor + (3 * noise_std)
        
        # Find peaks above threshold
        peaks, _ = signal.find_peaks(spectrum, 
                                    height=threshold,
                                    distance=int(self.sample_rate/1e6))  # Min 1MHz spacing
        
        # Calculate SNR for each peak
        peak_snrs = spectrum[peaks] - noise_floor
        
        # Store detected signals
        self.detected_signals = [(self.start_freq + (p * self.freq_range / len(spectrum)),
                                 peak_snrs[i])
                                for i, p in enumerate(peaks)]

    def draw_detected_signals(self, img, draw):
        """Draw markers for detected signals"""
        if hasattr(self, 'detected_signals'):
            for freq, snr in self.detected_signals:
                x_pos = int((freq - self.start_freq) / self.freq_range * self.graph_width)
                if 0 <= x_pos < self.graph_width:
                    # Draw signal marker
                    marker_color = (255, 255, 0)  # Yellow
                    draw.line([(x_pos, 0), (x_pos, self.graph_height)], 
                             fill=marker_color, width=1)
                    
                    # Draw SNR value
                    snr_text = f"{snr:.1f}dB"
                    draw.text((x_pos + 2, 2), snr_text, 
                             font=self.font, fill=marker_color)

    def add_time_annotation(self):
        """Add annotation at current time"""
        # Restore terminal for input
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)
        try:
            self.paused = True
            os.system('clear')
            text = input("\nEnter annotation text: ")
            if text.strip():
                current_time = time.time()
                self.annotations.append({
                    'time': current_time,
                    'text': text,
                    'frequency': self.cursor_freq,
                    'signal_strength': self.heatmap[-1, int((self.cursor_freq - self.start_freq) / self.freq_range * self.graph_width)]
                })
                # Initialize position for new annotation at bottom
                self.annotation_positions[current_time] = self.height - self.bottom_margin
                self.display_message = "Annotation added"
        except Exception as e:
            self.display_message = f"Error adding annotation: {str(e)}"
        finally:
            # Restore non-blocking input mode
            tty.setcbreak(sys.stdin.fileno())
            self.paused = False
            self.message_time = time.time()

    def draw_time_markers(self, img, draw):
        """Draw time markers and annotations"""
        # Draw annotations based on tracked positions
        for annotation in self.annotations:
            y_pos = self.annotation_positions.get(annotation['time'])
            
            if y_pos is None:
                # Initialize position for new annotation at bottom
                y_pos = self.height - self.bottom_margin
                self.annotation_positions[annotation['time']] = y_pos
            
            if self.top_margin <= y_pos < self.height - self.bottom_margin:
                # Draw dashed marker line manually
                dash_length = 4
                for x in range(0, self.width, dash_length * 2):
                    draw.line([(x, y_pos), (x + dash_length, y_pos)], 
                             fill=(255, 255, 0), width=1)
                
                # Draw annotation text with background
                timestamp = datetime.fromtimestamp(annotation['time']).strftime("%H:%M:%S")
                text = f"{annotation['text']} ({annotation['frequency']/1e6:.3f}MHz | {timestamp})"
                text_bbox = draw.textbbox((10, y_pos-6), text, font=self.font)
                
                # Draw semi-transparent background - Fixed the rectangle coordinates format
                draw.rectangle([
                    text_bbox[0]-2, text_bbox[1]-2, text_bbox[2]+2, text_bbox[3]+2
                ], fill=(0, 0, 0))
                
                # Draw text
                draw.text((10, y_pos-6), text, font=self.font, fill=(255, 255, 0))

    def export_spectrum_data(self):
        """Export spectrum data and annotations"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_filename = f"spectrum_export_{timestamp}"
            
            # Export spectrum data
            spectrum_file = os.path.join(self.export_directory, f"{base_filename}.npz")
            np.savez(spectrum_file,
                    spectrum=self.heatmap,
                    frequencies=np.linspace(self.start_freq, self.end_freq, self.graph_width),
                    timestamps=self.timestamps,
                    sample_rate=self.sample_rate)
            
            # Export analysis report
            report_file = os.path.join(self.export_directory, f"{base_filename}_report.json")
            report = self.generate_report()
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=4)
            
            # Export current view as image
            image_file = os.path.join(self.export_directory, f"{base_filename}.png")
            img = Image.fromarray(self.get_display_array())
            img.save(image_file)
            
            self.display_message = f"Data exported to {self.export_directory}"
        except Exception as e:
            self.display_message = f"Export error: {str(e)}"
        self.message_time = time.time()

    def generate_report(self):
        """Generate analysis report"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'time_range': {
                'start': self.start_time,
                'end': time.time(),
                'duration': time.time() - self.start_time
            },
            'frequency_range': {
                'start': self.start_freq,
                'end': self.end_freq,
                'bandwidth': self.freq_range
            },
            'annotations': [{
                'time': ann['time'],
                'text': ann['text'],
                'frequency': ann['frequency'],
                'signal_strength': float(ann['signal_strength'])
            } for ann in self.annotations],
            'settings': {
                'sample_rate': self.sample_rate,
                'gain': self.sdr.getGain(SOAPY_SDR_RX, 0),
                'averaging': self.averaging,
                'peak_hold': self.peak_hold,
                'auto_scale': self.auto_scale,
                'ppm': self.ppm,
            }
        }
        return report

    def clear_heatmap(self):
        """Clear the heatmap buffer"""
        self.heatmap = np.zeros((self.graph_height, self.graph_width))
        self.peak_values = np.zeros_like(self.heatmap)
        self.avg_buffer = []  # Clear averaging buffer
        self.add_msg("Display cleared")

    @property
    def center_freq(self):
        return self.sdr.getFrequency(SOAPY_SDR_RX, 0) if self.sdr else self._center_freq

    @center_freq.setter
    def center_freq(self, freq):
        self._center_freq = freq
        if self.sdr:
            self.sdr.setFrequency(SOAPY_SDR_RX, 0, freq)

    @property
    def gain(self):
        return self.sdr.getGain(SOAPY_SDR_RX, 0)

    @gain.setter
    def gain(self, value):
        self.sdr.setGain(SOAPY_SDR_RX, 0, value)

    def _init_fft_processing(self):
        """Initialize FFT processing resources"""
        # Calculate optimal FFT size (power of 2)
        self.fft_size = max(1024, 2**int(np.log2(self.sample_rate/1000)))  # At least 1kHz resolution
        
        # Pre-calculate window function
        self._window = signal.blackmanharris(self.fft_size)
        
        # Initialize FFT plan
        self._fft_plan = np.fft.fft(np.zeros(self.fft_size, dtype=np.complex64))
        
        # Initialize noise floor tracking
        self._noise_floor = None
        
        # Pre-allocate buffers with size limits
        self.max_buffer_length = 100
        self.avg_buffer = []
        self.agc_history = []

    def process_spectrum(self, spectrum):
        """Enhanced signal processing with noise reduction"""
        # Initialize noise floor if needed
        if self._noise_floor is None:
            self._noise_floor = np.median(spectrum)
        
        # Update noise floor with exponential smoothing
        alpha = 0.1  # Smoothing factor
        self._noise_floor = (1 - alpha) * self._noise_floor + alpha * np.median(spectrum)
        
        # Apply noise reduction and dynamic range compression
        spectrum_processed = np.clip(spectrum - self._noise_floor, 0, None)
        spectrum_processed = np.power(spectrum_processed, 0.7)  # Less aggressive compression
        
        # Apply additional smoothing if averaging is enabled
        if self.averaging:
            self.avg_buffer.append(spectrum_processed)
            if len(self.avg_buffer) > self.max_buffer_length:
                self.avg_buffer.pop(0)
            spectrum_processed = np.mean(self.avg_buffer, axis=0)
        
        return spectrum_processed

    def switch_to_band(self, band_name):
        """Switch to a specific frequency band"""
        if band_name in self.bands:
            start, end = self.bands[band_name]
            
            # Update frequency range
            self.start_freq = start
            self.end_freq = end
            self.freq_range = end - start
            self.center_freq = start + (self.freq_range / 2)
            
            # Update SDR
            self.sdr.setFrequency(SOAPY_SDR_RX, 0, self.center_freq)
            
            # Set appropriate mode and spacing if available
            if band_name in self.band_details:
                details = self.band_details[band_name]
                
                # Adjust sample rate based on spacing if needed
                if details["spacing"]:
                    new_rate = max(self.sample_rate, details["spacing"] * 4)
                    if new_rate != self.sample_rate:
                        self.sample_rate = new_rate
                        self.sdr.setSampleRate(SOAPY_SDR_RX, 0, new_rate)
            
            # Clear display for new band
            self.clear_heatmap()
            
            self.add_msg(f"Switched to {band_name} band")
                        
            return True
        return False

    def export_filled_framebuffer(self):
        """Export the framebuffer as an image when filled, including status text"""
        try:
            # Generate timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Create filename with frequency range and count
            freq_start = self.center_freq - (self.freq_range / 2)
            freq_end = self.center_freq + (self.freq_range / 2)
            filename = os.path.join(
                self.export_directory,
                f"spectrum_{timestamp}_{freq_start/1e6:.3f}-{freq_end/1e6:.3f}MHz_{self.export_count}.png"
            )
            
            # Get the display array (already includes status text from get_display_array)
            img = Image.fromarray(self.get_display_array())
            img.save(filename)
            
            # Increment export counter
            self.export_count += 1
            
            # Show success message
            self.add_msg(f"Exported frame {self.export_count} to {filename}")
            
        except Exception as e:
            self.add_msg(f"Export error: {str(e)}")

    def show_band_selection(self):
        """Display band selection interface with pagination"""
        # ANSI color codes
        CYAN = "\033[96m"
        YELLOW = "\033[93m"
        GREEN = "\033[92m"
        BLUE = "\033[94m"
        MAGENTA = "\033[95m"
        RESET = "\033[0m"
        BOLD = "\033[1m"
        
        # ASCII art title
        title = f"""{CYAN}{BOLD}
╔═══════════════════════╗
║ Frequency Band Select ║
╚═══════════════════════╝{RESET}"""
        
        # Get terminal size
        terminal_rows, terminal_cols = os.popen('stty size', 'r').read().split()
        terminal_rows = int(terminal_rows) - 4  # Leave space for prompt and input
        
        # Prepare band list with categories
        categories = {
            'Broadcast': ['AM', 'FM', 'SW', 'DAB'],
            'Aviation': ['AIR-L', 'AIR-V', 'AIR-M'],
            'Amateur Radio': ['HAM160', 'HAM80', 'HAM40', 'HAM20', 'HAM2M', 'HAM70'],
            'Public Safety': ['NOA', 'POLICE', 'EMG'],
            'Television': ['VHF-TV', 'VHF-TV2', 'UHF-TV'],
            'Satellite': ['GPS-L1', 'GOES', 'NOAA-SAT', 'METEOR-SAT'],
            'Mobile & Cellular': ['CELL-850', 'GSM900', 'GSM1800', 'DECT'],
            'ISM & IoT': ['ISM-433', 'ISM-868', 'ISM-915', 'ZIGBEE'],
            'Marine': ['MAR-VHF', 'MAR-AIS', 'MAR-DSC'],
            'Digital Radio': ['DAB', 'DSTAR', 'DMR', 'TETRA'],
            'Remote Control': ['RC-AIR', 'RC-CAR', 'RC-GENERAL'],
            'Utilities': ['PAGER', 'RFID', 'TRUNKING', 'SCADA'],
            'Microphones': ['MIC-VHF', 'MIC-UHF', 'MIC-PRO'],
            'Weather': ['WEATHER-SAT', 'WEATHER-RADIO', 'WEATHER-FAX'],
            'Time Signals': ['WWV', 'WWVH', 'DCF77', 'MSF']
        }
        
        # Create formatted lines for display
        display_lines = [title, ""]
        band_list = []  # To store bands in order
        
        for category, bands in categories.items():
            display_lines.append(f"{YELLOW}{BOLD}{category}{RESET}")
            display_lines.append(f"{GREEN}{'─' * len(category)}{RESET}")
            for band in bands:
                if band in self.bands:
                    band_num = len(band_list) + 1
                    start, end = self.bands[band]
                    if band in self.band_details:
                        details = self.band_details[band]
                        display_lines.append(
                            f"{CYAN}{band_num:3d}{RESET}. "
                            f"{YELLOW}{band:10s}{RESET}: "
                            f"{RESET}{start/1e6:8.3f}-{end/1e6:8.3f} MHz{RESET} "
                            f"[{GREEN}{details.get('mode', 'Unknown'):6s}{RESET}] "
                            f"{details.get('description', '')}"
                        )
                    else:
                        display_lines.append(
                            f"{CYAN}{band_num:3d}{RESET}. "
                            f"{YELLOW}{band:10s}{RESET}: "
                            f"{RESET}{start/1e6:8.3f}-{end/1e6:8.3f} MHz{RESET}"
                        )
                    band_list.append(band)
            display_lines.append("")  # Add spacing between categories
        
        # Display text page by page
        current_line = 0
        lines_per_page = terminal_rows - 4  # Leave room for navigation text
        
        while True:
            os.system('clear')
            
            # Display one page of text
            end_line = min(current_line + lines_per_page, len(display_lines))
            print("\n".join(display_lines[current_line:end_line]))
            
            # Navigation info
            print(f"\n{CYAN}Page {(current_line // lines_per_page) + 1}/{(len(display_lines) - 1) // lines_per_page + 1}{RESET}")
            if current_line + lines_per_page < len(display_lines):
                print(f"\n{GREEN}Press [n]ext/[p]rev page, enter number to select, or [q] to cancel{RESET}")
            else:
                print(f"\n{GREEN}Press [p]rev page, enter number to select, or [q] to cancel{RESET}")
            
            # Get user input
            selection = input(f"{YELLOW}Selection: {RESET}").strip().lower()
            
            if selection == 'q':
                return None
            elif selection == 'n' and current_line + lines_per_page < len(display_lines):
                current_line += lines_per_page
            elif selection == 'p' and current_line > 0:
                current_line = max(0, current_line - lines_per_page)
            elif selection.isdigit():
                band_num = int(selection)
                if 1 <= band_num <= len(band_list):
                    return band_list[band_num - 1]
                else:
                    print(f"{YELLOW}Invalid band number{RESET}")
                    time.sleep(1)  # Show error briefly
        
        return None

def main():
    parser = argparse.ArgumentParser(description='RTL-SDR Frequency Heatmap')
    parser.add_argument('start_freq', type=float, help='Start frequency in MHz')
    parser.add_argument('end_freq', type=float, help='End frequency in MHz')
    parser.add_argument('--sample-rate', type=float, default=2.4,
                        help='Sample rate in MHz (default: 2.4)')
    args = parser.parse_args()

    # Convert MHz to Hz
    start_freq = args.start_freq * 1e6
    end_freq = args.end_freq * 1e6
    sample_rate = args.sample_rate * 1e6

    heatmap = FrequencyHeatmap(start_freq, end_freq, sample_rate)
    
    try:
        while True:
            if not heatmap.paused:
                heatmap.update_heatmap()
            heatmap.draw_framebuffer()
            heatmap.check_keyboard()
    except KeyboardInterrupt:
        heatmap.cleanup()

if __name__ == "__main__":
    main()





