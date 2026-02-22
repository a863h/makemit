#include <stdio.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "led_strip.h"
#include <math.h> // Required for sinf()

// Configuration
#define LED_STRIP_BLINK_GPIO 0                  // D0 on Seeed XIAO ESP32-C6
#define LED_STRIP_LED_NUM 10                    // Change to your actual LED count
#define LED_STRIP_RMT_RES_HZ (10 * 1000 * 1000) // 10MHz resolution

#define PULSE_BPM 80
#define MS_PER_BEAT (60000 / PULSE_BPM)

static const char *TAG = "LED_RAINBOW";
led_strip_handle_t led_strip;

/**
 * Helper to convert HSV to RGB
 * WLED and FastLED have this built-in, but for raw IDF we use a simple version
 */
void led_strip_hsv2rgb(uint32_t h, uint32_t s, uint32_t v, uint32_t *r, uint32_t *g, uint32_t *b)
{
    h %= 360;
    uint32_t rgb_max = v * 255 / 200;
    uint32_t rgb_min = rgb_max * (100 - s) / 100;
    uint32_t i = h / 60;
    uint32_t diff = h % 60;
    uint32_t rgb_adj = (rgb_max - rgb_min) * diff / 60;

    switch (i)
    {
    case 0:
        *r = rgb_max;
        *g = rgb_min + rgb_adj;
        *b = rgb_min;
        break;
    case 1:
        *r = rgb_max - rgb_adj;
        *g = rgb_max;
        *b = rgb_min;
        break;
    case 2:
        *r = rgb_min;
        *g = rgb_max;
        *b = rgb_min + rgb_adj;
        break;
    case 3:
        *r = rgb_min;
        *g = rgb_max - rgb_adj;
        *b = rgb_max;
        break;
    case 4:
        *r = rgb_min + rgb_adj;
        *g = rgb_min;
        *b = rgb_max;
        break;
    default:
        *r = rgb_max;
        *g = rgb_min;
        *b = rgb_max - rgb_adj;
        break;
    }
}

void led_rainbow_task(void *pvParameters)
{
    uint32_t start_rgb = 0;
    uint32_t r, g, b;

    ESP_LOGI(TAG, "Starting Rainbow Loop...");
    while (1)
    {
        for (int i = 0; i < LED_STRIP_LED_NUM; i++)
        {
            uint32_t hue = (start_rgb + i * 10) % 360;
            led_strip_hsv2rgb(hue, 100, 100, &r, &g, &b);
            // Write to the internal buffer
            led_strip_set_pixel(led_strip, i, r, g, b);
        }
        // Push the buffer to the hardware
        led_strip_refresh(led_strip);

        start_rgb += 2;                // Speed of the rainbow cycle
        vTaskDelay(pdMS_TO_TICKS(20)); // ~50 FPS
    }
}

void led_pulse_task(void *pvParameters)
{
    ESP_LOGI(TAG, "Starting 80 BPM Blue Pulse...");

    float angle = 0.0;
    // We want to complete one full breath (up and down) every 750ms.
    // The sine wave completes a full cycle every 2*PI radians.
    // If we update every 20ms, the step size is:
    const float step = (2.0 * M_PI) / (MS_PER_BEAT / 20.0);

    while (1)
    {
        // sinf gives -1 to 1. We transform it to 0 to 1.
        // (sin(x) + 1) / 2
        float brightness = (sinf(angle) + 1.0f) / 2.0f;

        // Apply blue color scaled by brightness
        // RGB: 0, 0, 255 (Full Blue)
        uint32_t blue_val = (uint32_t)(200 * brightness);

        for (int i = 0; i < LED_STRIP_LED_NUM; i++)
        {
            led_strip_set_pixel(led_strip, i, 0, 0, blue_val);
        }

        led_strip_refresh(led_strip);

        angle += step;
        if (angle > 2.0 * M_PI)
        {
            angle -= 2.0 * M_PI;
        }

        vTaskDelay(pdMS_TO_TICKS(20)); // 50Hz update rate for smooth fading
    }
}

extern "C" void app_main(void)
{
    led_strip_config_t strip_config = {
        .strip_gpio_num = LED_STRIP_BLINK_GPIO,
        .max_leds = LED_STRIP_LED_NUM,
        .led_model = LED_MODEL_WS2812,
        .color_component_format = LED_STRIP_COLOR_COMPONENT_FMT_GRB, // Fixed field name and enum
        .flags = {
            .invert_out = false,
        }};

    /* 2. RMT Specific Configuration (Required for ESP32-C6) */
    led_strip_rmt_config_t rmt_config = {
        .clk_src = RMT_CLK_SRC_DEFAULT,
        .resolution_hz = LED_STRIP_RMT_RES_HZ,
        .flags = {
            .with_dma = false, // Set to true if using many LEDs (e.g. >100)
        }};

    /* 3. Initialize the Device */
    ESP_ERROR_CHECK(led_strip_new_rmt_device(&strip_config, &rmt_config, &led_strip));
    ESP_LOGI(TAG, "Created LED strip object with RMT backend");

    /* 4. Start the Animation Task */
    // xTaskCreate(led_rainbow_task, "led_rainbow_task", 4096, NULL, 5, NULL);
    xTaskCreate(led_pulse_task, "led_pulse_task", 4096, NULL, 5, NULL);
}