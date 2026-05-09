/*
 * MIT License
 *
 * Copyright (c) 2023 tinyVision.ai
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */

#include "pico/stdlib.h"
#include "pico/stdio.h"
#include "boards.h"
#include "ice_cram.h"
#include "ice_fpga.h"
#include "ice_led.h"

#include "pulse_count.pio.h"

static const unsigned long bitstreamSizeLengthBytes = 104090;
uint8_t bitstream[bitstreamSizeLengthBytes] = {};

long long watchdogTimout_us = 2'000'000; // 2 seconds
uint32_t numReceivedBitstreamBytes = 0;

#include "ice_usb.h"
#include "leds_helpers.hpp"

// actual definition is handled by preprocessor flags (-DPICO_BOARD=pico2_ice)
// This makes vs code linting not tweak out though which is nice
#ifndef FPGA_DATA
#define FPGA_DATA pico2_fpga
#endif

#define ICE_9 28
#define ICE_11 29
#define ICE_25 30
#define ICE_27 20

enum STATES
{
    INIT,
    WAIT_FOR_USB_CONNECTION,
    USB_CONNECTED,
    USB_DISCONNECTED,
    WAIT_FOR_BITSTREAM_TRANSFER,
    TRANSFER_BITSTREAM,
    FLASH_FPGA,
    IDLE
};
enum STATES currentState = INIT;
enum STATES previousState = INIT;

struct FlashTimePacket
{
    long long initTime;
    long long startTime;
    long long openTime;
    long long writeTime;
    long long closeTime;
};

FlashTimePacket benchmarkFlashTime(const uint8_t *bitstream, uint32_t size)
{
    FlashTimePacket flashTimeResults;
    auto t1 = get_absolute_time();
    if (ice_fpga_init(FPGA_DATA, 48) != 0)
        flashTimeResults.initTime = -1;
    else
        flashTimeResults.initTime = absolute_time_diff_us(t1, get_absolute_time());

    t1 = get_absolute_time();
    if (ice_fpga_start(FPGA_DATA) != 0)
        flashTimeResults.startTime = -1;
    else
        flashTimeResults.startTime = absolute_time_diff_us(t1, get_absolute_time());

    t1 = get_absolute_time();
    if (ice_cram_open(FPGA_DATA) != true)
        flashTimeResults.openTime = -1;
    else
        flashTimeResults.openTime = absolute_time_diff_us(t1, get_absolute_time());

    t1 = get_absolute_time();
    if (ice_cram_write(bitstream, size) != 0)
        flashTimeResults.writeTime = -1;
    else
        flashTimeResults.writeTime = absolute_time_diff_us(t1, get_absolute_time());

    t1 = get_absolute_time();
    if (ice_cram_close() != true)
        flashTimeResults.closeTime = -1;
    else
        flashTimeResults.closeTime = absolute_time_diff_us(t1, get_absolute_time());

    return flashTimeResults;
}

/**
 * @brief Runs and benchmarks the full flashing sequence
 * @param bitstream address of the bitstream
 * @param size length of bitstream
 *
 * @return time in (us) on success, negative on fail
 */
long long checkTotalFlashTime(const uint8_t *bitstream, uint32_t size)
{
    absolute_time_t t1 = get_absolute_time();
    if (ice_fpga_init(FPGA_DATA, 48) != 0)
        return -1;
    if (ice_fpga_start(FPGA_DATA) != 0)
        return -1;
    if (ice_cram_open(FPGA_DATA) != true)
        return -1;
    if (ice_cram_write(bitstream, size) != 0)
        return -1;
    if (ice_cram_close() != true)
        return -1;
    return absolute_time_diff_us(t1, get_absolute_time());
}

// NOT FOR PICO1-ice board
int main(void)
{
    absolute_time_t startTime;

    ice_led_init();
    bool green_status = true;
    bool blue_status = false;
    bool red_status = true;
    ice_led_red(red_status);
    ice_led_green(green_status);

    ice_usb_init();
    stdio_init_all();

    gpio_init(ICE_9);
    gpio_disable_pulls(ICE_9);
    gpio_put(ICE_9, false);
    gpio_set_dir(ICE_9, GPIO_IN);

    gpio_init(ICE_11);
    gpio_disable_pulls(ICE_11);
    gpio_put(ICE_11, false);
    gpio_set_dir(ICE_11, GPIO_IN);

    gpio_init(ICE_25);
    gpio_disable_pulls(ICE_25);
    gpio_put(ICE_25, false);
    gpio_set_dir(ICE_25, GPIO_IN);

    gpio_init(ICE_27);
    gpio_disable_pulls(ICE_27);
    gpio_put(ICE_27, false);
    gpio_set_dir(ICE_27, GPIO_IN);

    PIO pio_9;
    uint sm_9;
    uint offset_9;

    PIO pio_11;
    uint sm_11;
    uint offset_11;

    PIO pio_25;
    uint sm_25;
    uint offset_25;

    PIO pio_27;
    uint sm_27;
    uint offset_27;

    pio_claim_free_sm_and_add_program(&count_pulses_9_program, &pio_9, &sm_9, &offset_9);
    pio_sm_config config_9 = count_pulses_9_program_get_default_config(offset_9);
    pio_sm_init(pio_9, sm_9, offset_9, &config_9);
    pio_sm_set_enabled(pio_9, sm_9, true);

    pio_claim_free_sm_and_add_program(&count_pulses_11_program, &pio_11, &sm_11, &offset_11);
    pio_sm_config config_11 = count_pulses_11_program_get_default_config(offset_11);
    pio_sm_init(pio_11, sm_11, offset_11, &config_11);
    pio_sm_set_enabled(pio_11, sm_11, true);

    pio_claim_free_sm_and_add_program(&count_pulses_25_program, &pio_25, &sm_25, &offset_25);
    pio_sm_config config_25 = count_pulses_25_program_get_default_config(offset_25);
    pio_sm_init(pio_25, sm_25, offset_25, &config_25);
    pio_sm_set_enabled(pio_25, sm_25, true);

    pio_claim_free_sm_and_add_program(&count_pulses_27_program, &pio_27, &sm_27, &offset_27);
    pio_sm_config config_27 = count_pulses_27_program_get_default_config(offset_27);
    pio_sm_init(pio_27, sm_27, offset_27, &config_27);
    pio_sm_set_enabled(pio_27, sm_27, true);

    while (1) {
        startTime = get_absolute_time();
        currentState = WAIT_FOR_USB_CONNECTION;
        while (!tud_cdc_connected())
        {
            tud_task();
            sleep_ms(10);
        }
        tud_cdc_write_str("USB Connected :)\r\n");
        tud_cdc_n_write_flush(0);
        currentState = USB_CONNECTED;
        green_status = true;
        ice_led_green(green_status);
        red_status = false;
        ice_led_red(red_status);

        startTime = get_absolute_time();
        auto numBytesAvailable = -1;
        auto bitstreamStartTime = get_absolute_time();
        // add_repeating_timer_us(blinkPeriod_us / 2, );
        bool done = false;
        while (1)
        {
            if (done) {
                break;
            }
            tud_task(); // tinyusb device task
            switch (currentState)
            {
            case USB_CONNECTED:
                // connected, turn on green led, move to wait for bitstream transfer
                if (previousState != currentState && previousState != INIT)
                {
                    red_status = false;
                    ice_led_red(red_status);
                    green_status = true;
                    ice_led_green(green_status);
                    tud_cdc_n_write_str(0, "USB Reconnected :)\r\n");
                    tud_cdc_n_write_flush(0);
                    previousState = currentState;
                }
                currentState = WAIT_FOR_BITSTREAM_TRANSFER;
                break;
            case USB_DISCONNECTED:
                // usb disconnected, blink red led until reconnected
                if (!tud_cdc_connected())
                {
                    if (previousState != currentState)
                    {
                        red_status = true;
                        ice_led_red(red_status);
                        green_status = false;
                        ice_led_green(green_status);
                        tud_cdc_n_write_str(0, "USB Disconnected :(\r\n");
                        previousState = currentState;
                    }
                    else if (absolute_time_diff_us(startTime, get_absolute_time()) > blinkPeriod_us / 2)
                    {
                        red_status = !red_status;
                        ice_led_red(red_status);
                        startTime = get_absolute_time();
                    }
                }
                // reconnected
                else
                {
                    previousState = currentState;
                    currentState = USB_CONNECTED;
                }

                break;

            case WAIT_FOR_BITSTREAM_TRANSFER:
                // enter this state once usb is connected, blink green led slowly until bitstream transfer starts
                if (previousState != currentState)
                {
                    tud_cdc_n_write_str(0, "Waiting for bitstream transfer\r\n");
                    tud_cdc_n_write_flush(0);
                    previousState = currentState;
                }
                if (absolute_time_diff_us(startTime, get_absolute_time()) > blinkPeriod_us / 2)
                {
                    green_status = !green_status;
                    ice_led_green(green_status);
                    startTime = get_absolute_time();
                }
                if (tud_cdc_available())
                {
                    tud_cdc_n_write_str(0, "Bitstream transfer started\r\n");
                    tud_cdc_n_write_flush(0);
                    currentState = TRANSFER_BITSTREAM;
                }
                if (!tud_cdc_connected())
                {
                    currentState = USB_DISCONNECTED;
                }
                break;
            case TRANSFER_BITSTREAM:
                // Receive bitstream

                if (previousState != currentState)
                {
                    numReceivedBitstreamBytes = 0;
                    bitstreamStartTime = get_absolute_time();
                    green_status = false;
                    ice_led_green(green_status);
                    blue_status = true;
                    ice_led_blue(blue_status);

                    tud_cdc_n_write_str(0, "Receiving bitstream\r\n");
                    tud_cdc_n_write_flush(0);
                    previousState = currentState;
                }
                if (!tud_cdc_connected())
                {
                    previousState = currentState;
                    currentState = USB_DISCONNECTED;
                    blue_status = false;
                    ice_led_blue(blue_status);
                    numReceivedBitstreamBytes = 0;
                    break;
                }
                if (absolute_time_diff_us(startTime, get_absolute_time()) > blinkPeriod_us / 2)
                {
                    blue_status = !blue_status;
                    ice_led_blue(blue_status);
                    startTime = get_absolute_time();
                }
                if (absolute_time_diff_us(bitstreamStartTime, get_absolute_time()) > watchdogTimout_us)
                {
                    char buf[64];
                    snprintf(buf,
                            64,
                            "Watchdog timeout, %lu bytes received of %lu\r\n",
                            (unsigned long)numReceivedBitstreamBytes,
                            (unsigned long)bitstreamSizeLengthBytes);

                    tud_cdc_n_write_str(0, buf);
                    tud_cdc_n_write_flush(0);
                    previousState = currentState;
                    currentState = WAIT_FOR_BITSTREAM_TRANSFER;
                    blue_status = false;
                    ice_led_blue(blue_status);
                    bitstreamStartTime = get_absolute_time();
                }
                numBytesAvailable = tud_cdc_n_available(0);
                if (numBytesAvailable > 0)
                {
                    int numToRead = numBytesAvailable;
                    if (numReceivedBitstreamBytes + numBytesAvailable > bitstreamSizeLengthBytes)
                    {
                        numToRead = bitstreamSizeLengthBytes - numReceivedBitstreamBytes;
                    }
                    uint32_t count = tud_cdc_n_read(0, &bitstream[numReceivedBitstreamBytes], numToRead);
                    numReceivedBitstreamBytes += count;
                }
                if (numReceivedBitstreamBytes >= bitstreamSizeLengthBytes)
                {
                    char buf[64];
                    snprintf(buf,
                            64,
                            "Received bitstream in %lu us :)\r\n",
                            (unsigned long)absolute_time_diff_us(bitstreamStartTime, get_absolute_time()));
                    tud_cdc_n_write_str(0, buf);
                    tud_cdc_n_write_flush(0);
                    previousState = currentState;
                    currentState = FLASH_FPGA;
                }
                break;
            case FLASH_FPGA:
                // Flash FPGA with received bitstream
                if(previousState != currentState)
                {
                    blue_status = true;
                    ice_led_blue(blue_status);
                    red_status = true;
                    ice_led_red(red_status);
                    tud_cdc_n_write_str(0, "Flashing FPGA\r\n");
                    tud_cdc_n_write_flush(0);
                    previousState = currentState;
                }

                {
                    char buf[256];
                    FlashTimePacket flashTimes = benchmarkFlashTime(bitstream, bitstreamSizeLengthBytes);

                    // set pulse count register to 0
                    pio_sm_exec(pio_9, sm_9, pio_encode_set(pio_x, 0));
                    pio_sm_exec(pio_11, sm_11, pio_encode_set(pio_x, 0));
                    pio_sm_exec(pio_25, sm_25, pio_encode_set(pio_x, 0));
                    pio_sm_exec(pio_27, sm_27, pio_encode_set(pio_x, 0));

                    int time = to_ms_since_boot(get_absolute_time());
                    time += 1000;

                    while (to_ms_since_boot(get_absolute_time()) < time) {
                        tud_task();
                    }

                    // Read pulse count from pin 9 (GPIO 28)
                    pio_sm_exec(pio_9, sm_9, pio_encode_mov(pio_isr, pio_x));
                    pio_sm_exec(pio_9, sm_9, pio_encode_push(false, false));
                    uint32_t pulse_count_9 = UINT32_MAX - pio_sm_get_blocking(pio_9, sm_9) + 1;

                    // Read pulse count from pin 11 (GPIO 29)
                    pio_sm_exec(pio_11, sm_11, pio_encode_mov(pio_isr, pio_x));
                    pio_sm_exec(pio_11, sm_11, pio_encode_push(false, false));
                    uint32_t pulse_count_11 = UINT32_MAX - pio_sm_get_blocking(pio_11, sm_11) + 1;

                    // Read pulse count from pin 25 (GPIO 30)
                    pio_sm_exec(pio_25, sm_25, pio_encode_mov(pio_isr, pio_x));
                    pio_sm_exec(pio_25, sm_25, pio_encode_push(false, false));
                    uint32_t pulse_count_25 = UINT32_MAX - pio_sm_get_blocking(pio_25, sm_25) + 1;

                    // Read pulse count from pin 27 (GPIO 20)
                    pio_sm_exec(pio_27, sm_27, pio_encode_mov(pio_isr, pio_x));
                    pio_sm_exec(pio_27, sm_27, pio_encode_push(false, false));
                    uint32_t pulse_count_27 = UINT32_MAX - pio_sm_get_blocking(pio_27, sm_27) + 1;

                    snprintf(buf,
                            256,
                            "FPGA Flash times (us): init %lld, start %lld, open %lld, write %lld, close %lld\r\npulses: %d, %d, %d, %d\r\n",
                            flashTimes.initTime,
                            flashTimes.startTime,
                            flashTimes.openTime,
                            flashTimes.writeTime,
                            flashTimes.closeTime,
                            pulse_count_9, pulse_count_11, pulse_count_25, pulse_count_27);
                    tud_cdc_n_write_str(0, buf);
                    tud_cdc_n_write_flush(0);

                }
                currentState = IDLE;
                break;
            case IDLE:
                // Chill here for now
                if (previousState != currentState)
                {
                    blue_status = true;
                    ice_led_blue(blue_status);
                    green_status = true;
                    ice_led_green(green_status);
                    red_status = true;
                    ice_led_red(red_status);
                    tud_cdc_n_write_str(0, "IDLE\r\n");
                    tud_cdc_n_write_flush(0);
                    previousState = currentState;
                }
                if (absolute_time_diff_us(startTime, get_absolute_time()) > blinkPeriod_us / 2)
                {
                    blue_status = !blue_status;
                    ice_led_blue(blue_status);
                    green_status = !green_status;
                    ice_led_green(green_status);
                    red_status = !red_status;
                    ice_led_red(red_status);
                    startTime = get_absolute_time();
                }
                done = true;
                break;
            default:
                blue_status = false;
                ice_led_blue(blue_status);
                green_status = false;
                ice_led_green(green_status);
                red_status = true;
                ice_led_red(red_status);
                if (absolute_time_diff_us(startTime, get_absolute_time()) > blinkPeriod_us * 2)
                {
                    tud_cdc_n_write_str(0, "UNKNOWN STATE\r\n");
                    tud_cdc_n_write_flush(0);
                    startTime = get_absolute_time();
                }

                break;
            }
        }
    }
    return 0;
}
