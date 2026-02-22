#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/gpio.h"
#include "esp_log.h"

static const char *TAG = "QAPASS_LCD";

// XIAO ESP32-S3 pin mapping
#define RS GPIO_NUM_1
#define E  GPIO_NUM_2
#define D4 GPIO_NUM_3
#define D5 GPIO_NUM_4
#define D6 GPIO_NUM_5
#define D7 GPIO_NUM_6

static void lcd_delay_ms(int ms) { vTaskDelay(pdMS_TO_TICKS(ms)); }

// Pulse E pin long enough to latch data
static void lcd_pulse_enable() {
    gpio_set_level(E, 1);
    lcd_delay_ms(5);
    gpio_set_level(E, 0);
    lcd_delay_ms(5);
}

// Send a 4-bit nibble safely
static void lcd_send_nibble(uint8_t nibble) {
    gpio_set_level(D4, (nibble >> 0) & 0x01);
    gpio_set_level(D5, (nibble >> 1) & 0x01);
    gpio_set_level(D6, (nibble >> 2) & 0x01);
    gpio_set_level(D7, (nibble >> 3) & 0x01);
    lcd_pulse_enable();
}

// Send a byte (command or data)
static void lcd_send_byte(uint8_t data, bool is_data) {
    gpio_set_level(RS, is_data ? 1 : 0);
    lcd_send_nibble(data >> 4);   // high nibble first
    lcd_delay_ms(2);              // small delay between nibbles
    lcd_send_nibble(data & 0x0F); // then low nibble
    lcd_delay_ms(2);
}

// Set cursor (line 0/1, column 0–15)
static void lcd_set_cursor(uint8_t line, uint8_t col) {
    uint8_t addr = (line == 0 ? 0x00 : 0x40) + col;
    lcd_send_byte(0x80 | addr, false);
}

// Initialize LCD in 4-bit mode
static void lcd_init() {
    gpio_reset_pin(RS); gpio_set_direction(RS, GPIO_MODE_OUTPUT);
    gpio_reset_pin(E);  gpio_set_direction(E, GPIO_MODE_OUTPUT);
    gpio_reset_pin(D4); gpio_set_direction(D4, GPIO_MODE_OUTPUT);
    gpio_reset_pin(D5); gpio_set_direction(D5, GPIO_MODE_OUTPUT);
    gpio_reset_pin(D6); gpio_set_direction(D6, GPIO_MODE_OUTPUT);
    gpio_reset_pin(D7); gpio_set_direction(D7, GPIO_MODE_OUTPUT);

    lcd_delay_ms(50); // power-up

    // 4-bit init sequence, slow
    lcd_send_nibble(0x03); lcd_delay_ms(10);
    lcd_send_nibble(0x03); lcd_delay_ms(10);
    lcd_send_nibble(0x03); lcd_delay_ms(10);
    lcd_send_nibble(0x02); lcd_delay_ms(10);

    lcd_send_byte(0x28, false); // 4-bit, 2 lines, 5x8 dots
    lcd_send_byte(0x0C, false); // display ON, cursor OFF
    lcd_send_byte(0x06, false); // entry mode
    lcd_send_byte(0x01, false); // clear display
    lcd_delay_ms(10);

    ESP_LOGI(TAG, "LCD Initialized");
}

// Print string safely
static void lcd_print_safe(const char *str) {
    while (*str) {
        lcd_send_byte(*str++, true);
        lcd_delay_ms(3); // tiny delay between characters
    }
}

// Task: write fixed "Tempo High" + "Happy" cleanly
void lcd_test_task(void *arg) {
    while (1) {
        lcd_send_byte(0x01, false); // clear screen
        lcd_delay_ms(10);

        lcd_set_cursor(0,0);       // line 1
        lcd_print_safe("Tempo High");

        lcd_set_cursor(1,0);       // line 2
        lcd_print_safe("Happy");

        lcd_delay_ms(3000);        // wait 3 seconds
    }
}

void app_main(void) {
    lcd_init();
    xTaskCreate(lcd_test_task, "LCD_Test", 4096, NULL, 5, NULL);
}