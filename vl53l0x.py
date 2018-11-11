# This is a modified version of https://github.com/adafruit/Adafruit_CircuitPython_VL53L0X.git

# The MIT License (MIT)
#
# Copyright (c) 2017 Tony DiCola for Adafruit Industries
# Copyright (c) 2018 Loic Poulain <loic.poulain@linaro.org>
#
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import math
import time

__version__ = "0.0.0-auto.0"
__repo__ = ""

# Configuration constants:
# pylint: disable=bad-whitespace
_SYSRANGE_START                              = 0x00
_SYSTEM_THRESH_HIGH                          = 0x0C
_SYSTEM_THRESH_LOW                           = 0x0E
_SYSTEM_SEQUENCE_CONFIG                      = 0x01
_SYSTEM_RANGE_CONFIG                         = 0x09
_SYSTEM_INTERMEASUREMENT_PERIOD              = 0x04
_SYSTEM_INTERRUPT_CONFIG_GPIO                = 0x0A
_GPIO_HV_MUX_ACTIVE_HIGH                     = 0x84
_SYSTEM_INTERRUPT_CLEAR                      = 0x0B
_RESULT_INTERRUPT_STATUS                     = 0x13
_RESULT_RANGE_STATUS                         = 0x14
_RESULT_CORE_AMBIENT_WINDOW_EVENTS_RTN       = 0xBC
_RESULT_CORE_RANGING_TOTAL_EVENTS_RTN        = 0xC0
_RESULT_CORE_AMBIENT_WINDOW_EVENTS_REF       = 0xD0
_RESULT_CORE_RANGING_TOTAL_EVENTS_REF        = 0xD4
_RESULT_PEAK_SIGNAL_RATE_REF                 = 0xB6
_ALGO_PART_TO_PART_RANGE_OFFSET_MM           = 0x28
_I2C_SLAVE_DEVICE_ADDRESS                    = 0x8A
_MSRC_CONFIG_CONTROL                         = 0x60
_PRE_RANGE_CONFIG_MIN_SNR                    = 0x27
_PRE_RANGE_CONFIG_VALID_PHASE_LOW            = 0x56
_PRE_RANGE_CONFIG_VALID_PHASE_HIGH           = 0x57
_PRE_RANGE_MIN_COUNT_RATE_RTN_LIMIT          = 0x64
_FINAL_RANGE_CONFIG_MIN_SNR                  = 0x67
_FINAL_RANGE_CONFIG_VALID_PHASE_LOW          = 0x47
_FINAL_RANGE_CONFIG_VALID_PHASE_HIGH         = 0x48
_FINAL_RANGE_CONFIG_MIN_COUNT_RATE_RTN_LIMIT = 0x44
_PRE_RANGE_CONFIG_SIGMA_THRESH_HI            = 0x61
_PRE_RANGE_CONFIG_SIGMA_THRESH_LO            = 0x62
_PRE_RANGE_CONFIG_VCSEL_PERIOD               = 0x50
_PRE_RANGE_CONFIG_TIMEOUT_MACROP_HI          = 0x51
_PRE_RANGE_CONFIG_TIMEOUT_MACROP_LO          = 0x52
_SYSTEM_HISTOGRAM_BIN                        = 0x81
_HISTOGRAM_CONFIG_INITIAL_PHASE_SELECT       = 0x33
_HISTOGRAM_CONFIG_READOUT_CTRL               = 0x55
_FINAL_RANGE_CONFIG_VCSEL_PERIOD             = 0x70
_FINAL_RANGE_CONFIG_TIMEOUT_MACROP_HI        = 0x71
_FINAL_RANGE_CONFIG_TIMEOUT_MACROP_LO        = 0x72
_CROSSTALK_COMPENSATION_PEAK_RATE_MCPS       = 0x20
_MSRC_CONFIG_TIMEOUT_MACROP                  = 0x46
_SOFT_RESET_GO2_SOFT_RESET_N                 = 0xBF
_IDENTIFICATION_MODEL_ID                     = 0xC0
_IDENTIFICATION_REVISION_ID                  = 0xC2
_OSC_CALIBRATE_VAL                           = 0xF8
_GLOBAL_CONFIG_VCSEL_WIDTH                   = 0x32
_GLOBAL_CONFIG_SPAD_ENABLES_REF_0            = 0xB0
_GLOBAL_CONFIG_SPAD_ENABLES_REF_1            = 0xB1
_GLOBAL_CONFIG_SPAD_ENABLES_REF_2            = 0xB2
_GLOBAL_CONFIG_SPAD_ENABLES_REF_3            = 0xB3
_GLOBAL_CONFIG_SPAD_ENABLES_REF_4            = 0xB4
_GLOBAL_CONFIG_SPAD_ENABLES_REF_5            = 0xB5
_GLOBAL_CONFIG_REF_EN_START_SELECT           = 0xB6
_DYNAMIC_SPAD_NUM_REQUESTED_REF_SPAD         = 0x4E
_DYNAMIC_SPAD_REF_EN_START_OFFSET            = 0x4F
_POWER_MANAGEMENT_GO1_POWER_FORCE            = 0x80
_VHV_CONFIG_PAD_SCL_SDA__EXTSUP_HV           = 0x89
_ALGO_PHASECAL_LIM                           = 0x30
_ALGO_PHASECAL_CONFIG_TIMEOUT                = 0x30
_VCSEL_PERIOD_PRE_RANGE   = 0
_VCSEL_PERIOD_FINAL_RANGE = 1
# pylint: enable=bad-whitespace


def _decode_timeout(val):
    # format: "(LSByte * 2^MSByte) + 1"
    return float(val & 0xFF) * math.pow(2.0, ((val & 0xFF00) >> 8)) + 1

def _encode_timeout(timeout_mclks):
    # format: "(LSByte * 2^MSByte) + 1"
    timeout_mclks = int(timeout_mclks) & 0xFFFF
    ls_byte = 0
    ms_byte = 0
    if timeout_mclks > 0:
        ls_byte = timeout_mclks - 1
        while ls_byte > 255:
            ls_byte >>= 1
            ms_byte += 1
        return ((ms_byte << 8) | (ls_byte & 0xFF)) & 0xFFFF
    return 0

def _timeout_mclks_to_microseconds(timeout_period_mclks, vcsel_period_pclks):
    macro_period_ns = (((2304 * (vcsel_period_pclks) * 1655) + 500) // 1000)
    return ((timeout_period_mclks * macro_period_ns) + (macro_period_ns // 2)) // 1000

def _timeout_microseconds_to_mclks(timeout_period_us, vcsel_period_pclks):
    macro_period_ns = (((2304 * (vcsel_period_pclks) * 1655) + 500) // 1000)
    return ((timeout_period_us * 1000) + (macro_period_ns // 2)) // macro_period_ns

class VL53L0X(object):
    """Driver for the VL53L0X distance sensor."""
    # Class-level buffer for reading and writing data with the sensor.
    # This reduces memory allocations but means the code is not re-entrant or
    # thread safe!
    _BUFFER = bytearray(3)

    def __init__(self, bus, address=41, io_timeout_s=0):
        # pylint: disable=too-many-statements
        self.bus = bus
        self.address = address
        self.io_timeout_s = io_timeout_s
        # Check identification registers for expected values.
        # From section 3.2 of the datasheet.
        #if (self._read_u8(0xC0) != 0xEE or self._read_u8(0xC1) != 0xAA or
                #self._read_u8(0xC2) != 0x10):
            #raise RuntimeError('Failed to find expected ID register values. Check wiring!')
        # Initialize access to the sensor.  This is based on the logic from:
        #   https://github.com/pololu/vl53l0x-arduino/blob/master/VL53L0X.cpp
        # Set I2C standard mode.
        print('Initializing VL53L0X')
        for pair in ((0x88, 0x00), (0x80, 0x01), (0xFF, 0x01), (0x00, 0x00)):
            self._write_u8(pair[0], pair[1])
        self._stop_variable = self._read_u8(0x91)
        for pair in ((0x00, 0x01), (0xFF, 0x00), (0x80, 0x00)):
            self._write_u8(pair[0], pair[1])
        # disable SIGNAL_RATE_MSRC (bit 1) and SIGNAL_RATE_PRE_RANGE (bit 4)
        # limit checks
        config_control = self._read_u8(_MSRC_CONFIG_CONTROL) | 0x12
        self._write_u8(_MSRC_CONFIG_CONTROL, config_control)
        # set final range signal rate limit to 0.25 MCPS (million counts per
        # second)
        self.signal_rate_limit = 0.25
        self._write_u8(_SYSTEM_SEQUENCE_CONFIG, 0xFF)
        spad_count, spad_is_aperture = self._get_spad_info()
        # The SPAD map (RefGoodSpadMap) is read by
        # VL53L0X_get_info_from_device() in the API, but the same data seems to
        # be more easily readable from GLOBAL_CONFIG_SPAD_ENABLES_REF_0 through
        # _6, so read it from there.
        ref_spad_map = bytearray(7)
        ref_spad_map[0] = _GLOBAL_CONFIG_SPAD_ENABLES_REF_0
        #with self._device:
            #self._device.write(ref_spad_map, end=1)
            #self._device.readinto(ref_spad_map, start=1)

        for pair in ((0xFF, 0x01),
                     (_DYNAMIC_SPAD_REF_EN_START_OFFSET, 0x00),
                     (_DYNAMIC_SPAD_NUM_REQUESTED_REF_SPAD, 0x2C),
                     (0xFF, 0x00),
                     (_GLOBAL_CONFIG_REF_EN_START_SELECT, 0xB4)):
            self._write_u8(pair[0], pair[1])

        first_spad_to_enable = 12 if spad_is_aperture else 0
        spads_enabled = 0
        for i in range(48):
            if i < first_spad_to_enable or spads_enabled == spad_count:
                # This bit is lower than the first one that should be enabled,
                # or (reference_spad_count) bits have already been enabled, so
                # zero this bit.
                ref_spad_map[1 + (i // 8)] &= ~(1 << (i % 8))
            elif (ref_spad_map[1 + (i // 8)] >> (i % 8)) & 0x1 > 0:
                spads_enabled += 1
        #with self._device:
            #self._device.write(ref_spad_map)
        for pair in ((0xFF, 0x01), (0x00, 0x00), (0xFF, 0x00), (0x09, 0x00),
                     (0x10, 0x00), (0x11, 0x00), (0x24, 0x01), (0x25, 0xFF),
                     (0x75, 0x00), (0xFF, 0x01), (0x4E, 0x2C), (0x48, 0x00),
                     (0x30, 0x20), (0xFF, 0x00), (0x30, 0x09), (0x54, 0x00),
                     (0x31, 0x04), (0x32, 0x03), (0x40, 0x83), (0x46, 0x25),
                     (0x60, 0x00), (0x27, 0x00), (0x50, 0x06), (0x51, 0x00),
                     (0x52, 0x96), (0x56, 0x08), (0x57, 0x30), (0x61, 0x00),
                     (0x62, 0x00), (0x64, 0x00), (0x65, 0x00), (0x66, 0xA0),
                     (0xFF, 0x01), (0x22, 0x32), (0x47, 0x14), (0x49, 0xFF),
                     (0x4A, 0x00), (0xFF, 0x00), (0x7A, 0x0A), (0x7B, 0x00),
                     (0x78, 0x21), (0xFF, 0x01), (0x23, 0x34), (0x42, 0x00),
                     (0x44, 0xFF), (0x45, 0x26), (0x46, 0x05), (0x40, 0x40),
                     (0x0E, 0x06), (0x20, 0x1A), (0x43, 0x40), (0xFF, 0x00),
                     (0x34, 0x03), (0x35, 0x44), (0xFF, 0x01), (0x31, 0x04),
                     (0x4B, 0x09), (0x4C, 0x05), (0x4D, 0x04), (0xFF, 0x00),
                     (0x44, 0x00), (0x45, 0x20), (0x47, 0x08), (0x48, 0x28),
                     (0x67, 0x00), (0x70, 0x04), (0x71, 0x01), (0x72, 0xFE),
                     (0x76, 0x00), (0x77, 0x00), (0xFF, 0x01), (0x0D, 0x01),
                     (0xFF, 0x00), (0x80, 0x01), (0x01, 0xF8), (0xFF, 0x01),
                     (0x8E, 0x01), (0x00, 0x01), (0xFF, 0x00), (0x80, 0x00)):
            self._write_u8(pair[0], pair[1])

        self._write_u8(_SYSTEM_INTERRUPT_CONFIG_GPIO, 0x04)
        gpio_hv_mux_active_high = self._read_u8(_GPIO_HV_MUX_ACTIVE_HIGH)
        self._write_u8(_GPIO_HV_MUX_ACTIVE_HIGH,
                       gpio_hv_mux_active_high & ~0x10) # active low
        self._write_u8(_SYSTEM_INTERRUPT_CLEAR, 0x01)
        self._measurement_timing_budget_us = self.measurement_timing_budget
        self._write_u8(_SYSTEM_SEQUENCE_CONFIG, 0xE8)
        self.measurement_timing_budget = self._measurement_timing_budget_us
        self._write_u8(_SYSTEM_SEQUENCE_CONFIG, 0x01)
        self._perform_single_ref_calibration(0x40)
        self._write_u8(_SYSTEM_SEQUENCE_CONFIG, 0x02)
        self._perform_single_ref_calibration(0x00)
        # "restore the previous Sequence Config"
        self._write_u8(_SYSTEM_SEQUENCE_CONFIG, 0xE8)
        print('Initializing complete')

    def _read_u8(self, addr):
        # Read an 8-bit unsigned value from the specified 8-bit address.
        return self.bus.read_byte_data(self.address, addr)

    def _read_u16(self, addr):
        # Read a 16-bit BE unsigned value from the specified 8-bit address.
        byte0 = self.bus.read_byte_data(self.address, addr)
        byte1 = self.bus.read_byte_data(self.address, addr + 1)
        return ((byte0 << 8) | byte1)

    def _write_u8(self, addr, val):
        self.bus.write_byte_data(self.address, addr, val)

    def _write_u16(self, addr, val):
        # Write a 16-bit BE unsigned value to the specified 8-bit address.
        self.bus.write_byte_data(self.address, addr, val >> 8)
        self.bus.write_byte_data(self.address, addr, val & 0xff)


    def _get_spad_info(self):
        # Get reference SPAD count and type, returned as a 2-tuple of
        # count and boolean is_aperture.  Based on code from:
        #   https://github.com/pololu/vl53l0x-arduino/blob/master/VL53L0X.cpp
        for pair in ((0x80, 0x01), (0xFF, 0x01), (0x00, 0x00), (0xFF, 0x06)):
            self._write_u8(pair[0], pair[1])
        self._write_u8(0x83, self._read_u8(0x83) | 0x04)
        for pair in ((0xFF, 0x07), (0x81, 0x01), (0x80, 0x01),
                     (0x94, 0x6b), (0x83, 0x00)):
            self._write_u8(pair[0], pair[1])
        start = time.monotonic()
        while self._read_u8(0x83) == 0x00:
            if self.io_timeout_s > 0 and \
               (time.monotonic() - start) >= self.io_timeout_s:
                raise RuntimeError('Timeout waiting for VL53L0X!')
        self._write_u8(0x83, 0x01)
        tmp = self._read_u8(0x92)
        count = tmp & 0x7F
        is_aperture = ((tmp >> 7) & 0x01) == 1
        for pair in ((0x81, 0x00), (0xFF, 0x06)):
            self._write_u8(pair[0], pair[1])
        self._write_u8(0x83, self._read_u8(0x83) & ~0x04)
        for pair in ((0xFF, 0x01), (0x00, 0x01), (0xFF, 0x00), (0x80, 0x00)):
            self._write_u8(pair[0], pair[1])
        return (count, is_aperture)

    def _perform_single_ref_calibration(self, vhv_init_byte):
        # based on VL53L0X_perform_single_ref_calibration() from ST API.
        self._write_u8(_SYSRANGE_START, 0x01 | vhv_init_byte & 0xFF)
        start = time.monotonic()
        while (self._read_u8(_RESULT_INTERRUPT_STATUS) & 0x07) == 0:
            if self.io_timeout_s > 0 and \
               (time.monotonic() - start) >= self.io_timeout_s:
                raise RuntimeError('Timeout waiting for VL53L0X!')
        self._write_u8(_SYSTEM_INTERRUPT_CLEAR, 0x01)
        self._write_u8(_SYSRANGE_START, 0x00)

    def _get_vcsel_pulse_period(self, vcsel_period_type):
        # pylint: disable=no-else-return
        # Disable should be removed when refactor can be tested
        if vcsel_period_type == _VCSEL_PERIOD_PRE_RANGE:
            val = self._read_u8(_PRE_RANGE_CONFIG_VCSEL_PERIOD)
            return (((val) + 1) & 0xFF) << 1
        elif vcsel_period_type == _VCSEL_PERIOD_FINAL_RANGE:
            val = self._read_u8(_FINAL_RANGE_CONFIG_VCSEL_PERIOD)
            return (((val) + 1) & 0xFF) << 1
        return 255

    def _get_sequence_step_enables(self):
        # based on VL53L0X_GetSequenceStepEnables() from ST API
        sequence_config = self._read_u8(_SYSTEM_SEQUENCE_CONFIG)
        # pylint: disable=bad-whitespace
        tcc         = (sequence_config >> 4) & 0x1 > 0
        dss         = (sequence_config >> 3) & 0x1 > 0
        msrc        = (sequence_config >> 2) & 0x1 > 0
        pre_range   = (sequence_config >> 6) & 0x1 > 0
        final_range = (sequence_config >> 7) & 0x1 > 0
        return (tcc, dss, msrc, pre_range, final_range)

    def _get_sequence_step_timeouts(self, pre_range):
        # based on get_sequence_step_timeout() from ST API but modified by
        # pololu here:
        #   https://github.com/pololu/vl53l0x-arduino/blob/master/VL53L0X.cpp
        pre_range_vcsel_period_pclks = self._get_vcsel_pulse_period(_VCSEL_PERIOD_PRE_RANGE)
        msrc_dss_tcc_mclks = (self._read_u8(_MSRC_CONFIG_TIMEOUT_MACROP) + 1) & 0xFF
        msrc_dss_tcc_us = _timeout_mclks_to_microseconds(
            msrc_dss_tcc_mclks, pre_range_vcsel_period_pclks)
        pre_range_mclks = _decode_timeout(self._read_u16(_PRE_RANGE_CONFIG_TIMEOUT_MACROP_HI))
        pre_range_us = _timeout_mclks_to_microseconds(pre_range_mclks, pre_range_vcsel_period_pclks)
        final_range_vcsel_period_pclks = self._get_vcsel_pulse_period(_VCSEL_PERIOD_FINAL_RANGE)
        final_range_mclks = _decode_timeout(self._read_u16(_FINAL_RANGE_CONFIG_TIMEOUT_MACROP_HI))
        if pre_range:
            final_range_mclks -= pre_range_mclks
        final_range_us = _timeout_mclks_to_microseconds(
            final_range_mclks, final_range_vcsel_period_pclks)
        return (msrc_dss_tcc_us,
                pre_range_us,
                final_range_us,
                final_range_vcsel_period_pclks,
                pre_range_mclks)

    @property
    def signal_rate_limit(self):
        """The signal rate limit in mega counts per second."""
        val = self._read_u16(_FINAL_RANGE_CONFIG_MIN_COUNT_RATE_RTN_LIMIT)
        # Return value converted from 16-bit 9.7 fixed point to float.
        return val / (1 << 7)

    @signal_rate_limit.setter
    def signal_rate_limit(self, val):
        assert 0.0 <= val <= 511.99
        # Convert to 16-bit 9.7 fixed point value from a float.
        val = int(val * (1 << 7))
        self._write_u16(_FINAL_RANGE_CONFIG_MIN_COUNT_RATE_RTN_LIMIT, val)

    @property
    def measurement_timing_budget(self):
        """The measurement timing budget in microseconds."""
        budget_us = 1910 + 960  # Start overhead + end overhead.
        tcc, dss, msrc, pre_range, final_range = self._get_sequence_step_enables()
        step_timeouts = self._get_sequence_step_timeouts(pre_range)
        msrc_dss_tcc_us, pre_range_us, final_range_us, _, _ = step_timeouts
        if tcc:
            budget_us += (msrc_dss_tcc_us + 590)
        if dss:
            budget_us += 2*(msrc_dss_tcc_us + 690)
        elif msrc:
            budget_us += (msrc_dss_tcc_us + 660)
        if pre_range:
            budget_us += (pre_range_us + 660)
        if final_range:
            budget_us += (final_range_us + 550)
        self._measurement_timing_budget_us = budget_us
        return budget_us

    @measurement_timing_budget.setter
    def measurement_timing_budget(self, budget_us):
        # pylint: disable=too-many-locals
        assert budget_us >= 20000
        used_budget_us = 1320 + 960  # Start (diff from get) + end overhead
        tcc, dss, msrc, pre_range, final_range = self._get_sequence_step_enables()
        step_timeouts = self._get_sequence_step_timeouts(pre_range)
        msrc_dss_tcc_us, pre_range_us, _ = step_timeouts[:3]
        final_range_vcsel_period_pclks, pre_range_mclks = step_timeouts[3:]
        if tcc:
            used_budget_us += (msrc_dss_tcc_us + 590)
        if dss:
            used_budget_us += 2*(msrc_dss_tcc_us + 690)
        elif msrc:
            used_budget_us += (msrc_dss_tcc_us + 660)
        if pre_range:
            used_budget_us += (pre_range_us + 660)
        if final_range:
            used_budget_us += 550
            # "Note that the final range timeout is determined by the timing
            # budget and the sum of all other timeouts within the sequence.
            # If there is no room for the final range timeout, then an error
            # will be set. Otherwise the remaining time will be applied to
            # the final range."
            if used_budget_us > budget_us:
                raise ValueError('Requested timeout too big.')
            final_range_timeout_us = budget_us - used_budget_us
            final_range_timeout_mclks = _timeout_microseconds_to_mclks(
                final_range_timeout_us,
                final_range_vcsel_period_pclks)
            if pre_range:
                final_range_timeout_mclks += pre_range_mclks
            self._write_u16(_FINAL_RANGE_CONFIG_TIMEOUT_MACROP_HI,
                            _encode_timeout(final_range_timeout_mclks))
            self._measurement_timing_budget_us = budget_us


    def read(self):
        """Perform a single reading of the range for an object in front of
        the sensor and return the distance in millimeters.
        """
        # Adapted from readRangeSingleMillimeters &
        # readRangeContinuousMillimeters in pololu code at:
        #   https://github.com/pololu/vl53l0x-arduino/blob/master/VL53L0X.cpp
        for pair in ((0x80, 0x01), (0xFF, 0x01), (0x00, 0x00),
                     (0x91, self._stop_variable), (0x00, 0x01), (0xFF, 0x00),
                     (0x80, 0x00), (_SYSRANGE_START, 0x01)):
            self._write_u8(pair[0], pair[1])
        start = time.monotonic()
        while (self._read_u8(_SYSRANGE_START) & 0x01) > 0:
            if self.io_timeout_s > 0 and \
               (time.monotonic() - start) >= self.io_timeout_s:
                raise RuntimeError('Timeout waiting for VL53L0X!')
        start = time.monotonic()
        while (self._read_u8(_RESULT_INTERRUPT_STATUS) & 0x07) == 0:
            if self.io_timeout_s > 0 and \
               (time.monotonic() - start) >= self.io_timeout_s:
                raise RuntimeError('Timeout waiting for VL53L0X!')
        # assumptions: Linearity Corrective Gain is 1000 (default)
        # fractional ranging is not enabled
        range_mm = self._read_u16(_RESULT_RANGE_STATUS + 10)
        self._write_u8(_SYSTEM_INTERRUPT_CLEAR, 0x01)
        return range_mm
