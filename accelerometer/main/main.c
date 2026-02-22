#include <stdio.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "driver/i2c.h"

#include "esp_wifi.h"
#include "esp_event.h"
#include "nvs_flash.h"
#include "esp_http_client.h"
#include "esp_crt_bundle.h"

static const char *TAG = "MMA8451_SENSOR";

// Pin Definitions from your table
#define I2C_MASTER_SDA_IO 5 // D4 on your board
#define I2C_MASTER_SCL_IO 6 // D5 on your board
#define I2C_MASTER_NUM I2C_NUM_0
#define I2C_MASTER_FREQ_HZ 400000

// MMA8451 Specifics
#define MMA8451_ADDR 0x1D
#define REG_OUT_X_MSB 0x01
#define REG_WHO_AM_I 0x0D
#define REG_XYZ_DATA_CFG 0x0E
#define REG_CTRL_REG1 0x2A

#define REG_PL_STATUS 0x10 // Portrait/Landscape Status
#define REG_PL_CFG 0x11    // Portrait/Landscape Configuration
#define GRAVITY_CONSTANT 9.80665f

static void process_data(int16_t x_raw, int16_t y_raw, int16_t z_raw, uint8_t pl_status)
{
  // 1. Convert Raw to m/s^2
  // Sensitivity at +/-2g is 4096 LSB/g
  float ax = (x_raw / 4096.0f) * GRAVITY_CONSTANT;
  float ay = (y_raw / 4096.0f) * GRAVITY_CONSTANT;
  float az = (z_raw / 4096.0f) * GRAVITY_CONSTANT;

  // 2. Decode Orientation Status (Bits 2:1 for PL, Bit 0 for B/F)
  const char *pl_state;
  uint8_t pl_bits = (pl_status >> 1) & 0x03;
  switch (pl_bits)
  {
  case 0:
    pl_state = "Portrait Up";
    break;
  case 1:
    pl_state = "Portrait Down";
    break;
  case 2:
    pl_state = "Landscape Right";
    break;
  case 3:
    pl_state = "Landscape Left";
    break;
  default:
    pl_state = "Unknown";
    break;
  }

  const char *side = (pl_status & 0x01) ? "Back" : "Front";

  printf("Accel (m/s^2) -> X: %.2f  Y: %.2f  Z: %.2f | Orientation: %s, %s\n",
         ax, ay, az, pl_state, side);
}

static esp_err_t i2c_master_init(void)
{
  i2c_config_t conf = {
      .mode = I2C_MODE_MASTER,
      .sda_io_num = I2C_MASTER_SDA_IO,
      .scl_io_num = I2C_MASTER_SCL_IO,
      .sda_pullup_en = GPIO_PULLUP_ENABLE,
      .scl_pullup_en = GPIO_PULLUP_ENABLE,
      .master.clk_speed = I2C_MASTER_FREQ_HZ,
  };
  i2c_param_config(I2C_MASTER_NUM, &conf);
  return i2c_driver_install(I2C_MASTER_NUM, conf.mode, 0, 0, 0);
}

static esp_err_t write_reg(uint8_t reg, uint8_t data)
{
  uint8_t write_buf[2] = {reg, data};
  return i2c_master_write_to_device(I2C_MASTER_NUM, MMA8451_ADDR, write_buf, 2, pdMS_TO_TICKS(100));
}

esp_err_t _http_event_handler(esp_http_client_event_t *evt)
{
  if (evt->event_id == HTTP_EVENT_ON_DATA)
  {
    printf("%.*s", evt->data_len, (char *)evt->data);
  }
  return ESP_OK;
}

void make_google_request()
{
  esp_http_client_config_t config = {
      .url = "http://unnoteworthy-pseudoethical-malisa.ngrok-free.dev",
      .method = HTTP_METHOD_GET,
      // .crt_bundle_attach = esp_crt_bundle_attach,
  };

  esp_http_client_handle_t client = esp_http_client_init(&config);

  esp_err_t err = esp_http_client_perform(client);
  if (err == ESP_OK)
  {
    printf("HTTP GET Status = %d, content_length = %lld\n",
           esp_http_client_get_status_code(client),
           esp_http_client_get_content_length(client));
  }
  else
  {
    printf("HTTP GET request failed: %s\n", esp_err_to_name(err));
  }

  esp_http_client_cleanup(client);
}

void app_main(void)
{

  // WIFI
  esp_err_t ret = nvs_flash_init();
  if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND)
  {
    ESP_ERROR_CHECK(nvs_flash_erase());
    ret = nvs_flash_init();
  }
  ESP_ERROR_CHECK(ret);

  // 2. Initialize TCP/IP and Event Loop
  ESP_ERROR_CHECK(esp_netif_init());
  ESP_ERROR_CHECK(esp_event_loop_create_default());
  esp_netif_t *sta_netif = esp_netif_create_default_wifi_sta();
  // esp_netif_create_default_wifi_sta();

  // 3. Wi-Fi Configuration
  wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
  ESP_ERROR_CHECK(esp_wifi_init(&cfg));

  wifi_config_t wifi_config = {
      .sta = {
          .ssid = "MIT",
          .password = "RxS1T7_)hP",
      },
  };

  ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
  ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_config));

  // 4. Start!
  ESP_ERROR_CHECK(esp_wifi_start());
  esp_wifi_connect();

  // 1. Wait here indefinitely until notified by the event_handler
  printf("Waiting for IP...\n");
  esp_netif_ip_info_t ip_info;

  // This loop simply asks the system "Do we have an IP?" every 500ms
  while (esp_netif_get_ip_info(sta_netif, &ip_info) != ESP_OK || ip_info.ip.addr == 0)
  {
    vTaskDelay(pdMS_TO_TICKS(500));
  }

  // 2. SUCCESS! The code only reaches this line once you have an IP.
  printf("IP Received! Connecting to my server...\n");
  make_google_request();

  // 1. Setup I2C
  ESP_ERROR_CHECK(i2c_master_init());
  ESP_LOGI(TAG, "I2C initialized on SDA:5, SCL:6");

  // 2. Identity Check (Optional but recommended)
  uint8_t who_am_i = 0;
  uint8_t reg_who = REG_WHO_AM_I;
  i2c_master_write_read_device(I2C_MASTER_NUM, MMA8451_ADDR, &reg_who, 1, &who_am_i, 1, pdMS_TO_TICKS(100));

  if (who_am_i != 0x1A)
  {
    ESP_LOGE(TAG, "Device ID 0x%02X not recognized! Check wiring.", who_am_i);
    return;
  }

  // 3. Configure Sensor
  write_reg(REG_CTRL_REG1, 0x00); // Standby

  // 2. Setup Orientation Engine
  write_reg(0x11, 0x40); // PL_CFG: Enable PL
  write_reg(0x12, 0x05); // PL_COUNT: Set a small debounce
  write_reg(0x13, 0x44); // PL_BF_ZCOMP: Configure trip angles (Standard 45 deg)

  // 3. Set Range and Data Rate
  write_reg(REG_XYZ_DATA_CFG, 0x00); // +/- 2g

  // 4. Return to ACTIVE mode
  write_reg(REG_CTRL_REG1, 0x01);

  while (1)
  {
    uint8_t data[6];
    uint8_t pl_status = 0;
    uint8_t reg_start = REG_OUT_X_MSB;
    uint8_t reg_pl = REG_PL_STATUS;

    esp_err_t ret = i2c_master_write_read_device(I2C_MASTER_NUM, MMA8451_ADDR, &reg_start, 1, data, 6, pdMS_TO_TICKS(100));

    if (ret == ESP_OK)
    {
      // Convert 14-bit Big-Endian (MSB first)
      int16_t x = ((int16_t)(data[0] << 8 | data[1])) >> 2;
      int16_t y = ((int16_t)(data[2] << 8 | data[3])) >> 2;
      int16_t z = ((int16_t)(data[4] << 8 | data[5])) >> 2;

      process_data(x, y, z, pl_status);
    }

    vTaskDelay(pdMS_TO_TICKS(100));
  }
}