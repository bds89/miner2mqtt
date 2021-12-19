# Miner2MQTT

Доступ к вашему GPU майнеру через MQTT.

<img src="screenshots/ha.jpg" width="250"> <img src="screenshots/ha_t.jpg" width="250"> <img src="screenshots/ha_fan.jpeg" width="250">

## Изменения

<details>
  <summary>1.0</summary>

- EXE файл для Windows
</details>
<details>
  <summary>1.1(Linux)</summary>

- Управление вентиляторами видеокарт (Linux)

- Упраление power limit видеокарт (требуется SU) (Linux)
</details>
<details>
  <summary>1.2(Linux)</summary>

- Поддержка `danila miner` для майнинга `TON`. (Майнер запускается m2m.py, поэтому необходимо прописать команду для запуска в `config.yaml`. Хэшрейт для нескольких видеокарт будет одинаковым(общим))

- Вывод дополнительных системных параметров: `USED_RAM`, `CPU_temp`, `CPU_freq`, `CPU_FAN`. (если использовали параметр `INCLUDE` в `config.yaml`, необходимо в него добавить: `sys_params`)

- Исправление работы регулировки вентиляторов видекарт с двумя и тремя вентиляторами. (Для видеокарт с одним вентилятором возможны проблемы, не на чем протестировать)
</details>
## Описание

**Поддерживаемые ОС**

- Linux
- Windows (версия 1.0)

**Поддерживаемые майнеры**

- T-Rex
- danila miner

**Воможности:**
- Публикация всей информации от майнера в MQTT
- Возможность выборочной публикации (`INCLUDE` и `EXCLUDE` параметры в `config.yaml`)
- Обновление с указанным интервалом или по требованию (путем публикации `"ON"` в `ваш_топик/to_miner/refresh`)
<details>
  <summary>Управление вентиляторами видеокарт</summary>

- Изменение скорости: публикация значения в процентах в топик `ваш_топик/to_miner/<GPU_number>/fan_speed`, топик с текущими значениями в процентах `ваш_топик/from_miner/<GPU_number>/fan_speed`. 
- Включение вентилятора: публикация значения `ON` в топик `ваш_топик/to_miner/<GPU_number>/fan_state`, топик с текущим состоянием `ваш_топик/from_miner/<GPU_number>/fan_state`.
- Изменение режима auto/manual: публикация значения `auto` / `manual`в топик `ваш_топик/to_miner/<GPU_number>/fan_mode`, топик с текущим режимом `ваш_топик/from_miner/<GPU_number>/fan_mode`.
</details>
<details>
  <summary>Управление power limit видеокарт</summary>

- Изменение power limit: публикация значения в процентах в топик `ваш_топик/to_miner/<GPU_number>/power_limit`, топик с текущими значениями в процентах `ваш_топик/from_miner/<GPU_number>/power_limit`. 
- Для изменения power limit требуются права SU, необходимо либо вписать `SUDO_PASS` в `config.yaml` либо запускать `m2m.py` с правами sudo.
</details>


## Установка:

  <summary>Ubuntu </summary>
  
  ```bash
  sudo apt install python3-setuptools
  git clone https://github.com/bds89/miner2mqtt.git
  cd miner2mqtt
  sudo python3 setup.py install   
  gedit m2m/config.yaml   #Редактируем config.yaml
  ```

## Запуск:
  ```bash
  python3 m2m/m2m.py
  ```

## Обновление:
- Сохраните ваш config.yaml
  ```bash
  cd miner2mqtt
  git pull origin
  ```
- Скопируйте ваш сохраненный `config.yaml` в `miner2mqtt/m2m`
  
## Редактирование config.yaml:
```yaml
MINER: Trex/danila-miner
    #выбор GPU майнера
SUDO_PASS: pass
    #пароль суперпользователя, для изменения power_limit
MQTT:
  TOPIC: miner2mqtt/rig0
  HOST: 192.168.0.120
  USERNAME: user
  PASS: pass
    #Подключение к вашему MQTT
INTERVAL: 300
    #интервал сбора и публикации информации в секундах
INCLUDE:
- active_pool
- gpus
- sys_params
EXCLUDE: {}
    #фильтры по ключам из JSON словаря вашего майнера (поддерживаются только ключи первого уровня)
```
## Примеры публикации в MQTT:
<details>
  <summary>Trex в miner2mqtt/rig0/#</summary>

```json
{
  // Number of accepted shares count
  "accepted_count": 6,
  
  // Information about the pool your miner is currently connected to
  "active_pool":
  {
    // Current pool difficulty
    "difficulty": 5,
    
    // Pool latency
    "ping": 97,
    
    // Number of connection attempts in case of connection loss
    "retries": 0,
    
    // Pool connection string
    "url": "stratum+tcp://...",
    
    // Usually your wallet address
    "user": "..."
  },
  
  // Algorithm which was set in config
  "algorithm": "x16r",

  // HTTP API protocol version   
  "api": "1.2",

  // CUDA toolkit version used to built the miner
  "cuda": "9.10",

  // Software description
  "description": "T-Rex NVIDIA GPU miner",
  
  // Current network difficulty
  "difficulty": 31968.245093004043,

  // Total number of GPUs installed in your system
  "gpu_total": 1,
  
  // List of all currently working GPUs in your system with its stats
  "gpus": [{
    // Internal device id, useful for devs
    "device_id": 0,                        

    // Fan blades rotation speed in % of the max speed
    "fan_speed": 66,                       

    // User defined device id in config
    "gpu_user_id": 0,                        

    // Average hashrate per N sec defined in config
    "hashrate": 4529054,                   

    // Average hashrate per day
    "hashrate_day": 5023728,    

    // Average hashrate per hour
    "hashrate_hour": 0,          

    // Average hashrate per minute
    "hashrate_minute": 4671930,    

    // User defined intensity
    "intensity": 21.5,        

    // Current device name.
    "name": "GeForce GTX 1050",

    // Current device temperature.
    "temperature": 80,            

    // Current device vendor.
    "vendor": "Gigabyte", 

    // Device state. Might appear if device reached heat limit. (set by --temperature-limit)
    "disabled":true,                       

    // Device temperature at disable. Might appear if device reached heat limit.
    "disabled_at_temperature": 77,
    
    // Shares stat for the device.
    "shares": {
        "accepted_count": 3,
        "invalid_count": 0,
        "rejected_count": 0,
        "solved_count": 0
    }
  }],
  
  // Total average sum of hashrates for all active devices per N sec defined in config.
  "hashrate": 4529054,                       

  // Total average sum of hashrates for a day.
  "hashrate_day": 5023728,                   

  // Total average sum of hashrates for an hour.
  "hashrate_hour": 0,                        

  // Total average sum of hashrates for a minute.
  "hashrate_minute": 4671930,                

  // Application name
  "name": "t-rex",

  // Operating system
  "os": "linux",

  // This is number of rejected shares count.
  "rejected_count": 0,                       

  // This is number of found blocks.
  "solved_count": 0,                

  // Current time in sec from the beginning of the epoch. (ref: https://www.epochconverter.com)
  "ts": 1537095257,                          

  // Uptime in sec. This shows how long the miner has been running for.
  "uptime": 108,                             

  // Miner version.
  "version": "0.6.5",

  // Information about available update. Appears in case update is available.
  "updates":{                                

    // Url of file archive to download.
    "url": "https://fileurl",          

    // Signature of update pack (md5).
    "md5sum": "md5...",               

    // T-Rex version in update.
    "version": "0.8.0",        

    // Short info about changes in update.
    "notes": "short update info",         

    // Whole info about changes in update.
    "notes_full": "full update info",     

    // Information about current update download.
    "download_status":
    {
      // Total bytes downloaded.
      "downloaded_bytes": 1775165,

      // Total bytes to download.
      "total_bytes": 5245345,

      // Last error if download failed.
      "last_error":"",

      // Time elapsed since first byte downloaded.
      "time_elapsed_sec": 2.887111,

      // Download service state.
      "update_in_progress": true,

      // Download service named state. ("started", "downloading", "finished", "error", "idle")
      "update_state": "downloading",

      // Url of file in operation.
      "url": "https://fileurl"
    },
  "sys_params": {
        "used_ram": 77.9,
        "cpu_temp": 40,
        "cpu_freq": 3300,
        "cpu_fan": 986
  }
}
```
</details>

<details>
  <summary>Danila-miner в miner2mqtt/rig0/#</summary>

```json
{
    "gpus": [
        {
            "hashrate": 1019340000,
            "hashrate_hour": 1019340000,
            "name": "NVIDIA GeForce RTX 3060 Ti",
            "power": 156,
            "fan_speed": 40,
            "temperature": 38,
            "efficiency": 6534231,
            "shares": "0"
        }
    ],
    "sys_params": {
        "used_ram": 77.1,
        "cpu_temp": 37,
        "cpu_freq": 3300,
        "cpu_fan": 986
    }
}
```
</details>

## Примеры интеграции в Home Asistant:
<details>
  <summary>Сборный сенсор GPU0</summary>

```yaml
sensor:
  - platform: mqtt
    name: "GPU0"
    state_topic: "miner2mqtt/rig0"
    unit_of_measurement: "MH/s"
    value_template: "{{ (value_json.gpus.0.hashrate/1000000)|round(2) }}"
    device_class: power
    expire_after: 660
    json_attributes_topic: "miner2mqtt/rig0"
    json_attributes_template: >
      { "name": "{{value_json.gpus.0.name}}",
        "temperature": "{{value_json.gpus.0.temperature}}",
        "fan_speed": "{{value_json.gpus.0.fan_speed}}",
        "power": "{{value_json.gpus.0.power}}",
        "efficiency": "{{value_json.gpus.0.efficiency}}" }
```
</details>
<details>
  <summary>Отдельные сенсоры</summary>

```yaml
sensor:
  - platform: mqtt
    name: "GPU0_hash"
    state_topic: "miner2mqtt/rig0"
    unit_of_measurement: "MH/s"
    value_template: "{{ (value_json.gpus.0.hashrate_minute/1000000)|round(2) }}"
    device_class: power
    expire_after: 660
    json_attributes_topic: "miner2mqtt/rig0"

  - platform: mqtt
    name: "GPU0_name"
    state_topic: "miner2mqtt/rig0"
    value_template: "{{value_json.gpus.0.vendor|string + ' '|string + value_json.gpus.0.name|string}}"
    json_attributes_topic: "miner2mqtt/rig0"
    
  - platform: mqtt
    name: "GPU0_temperature"
    state_topic: "miner2mqtt/rig0"
    unit_of_measurement: "°C"
    value_template: "{{value_json.gpus.0.temperature}}"
    expire_after: 660
    json_attributes_topic: "miner2mqtt/rig0"
    
  - platform: mqtt
    name: "GPU0_fan_speed"
    state_topic: "miner2mqtt/rig0"
    unit_of_measurement: "%"
    value_template: "{{value_json.gpus.0.fan_speed}}"
    device_class: power_factor
    expire_after: 660
    json_attributes_topic: "miner2mqtt/rig0"
    
  - platform: mqtt
    name: "GPU0_power"
    state_topic: "miner2mqtt/rig0"
    unit_of_measurement: "kW/h"
    value_template: "{{value_json.gpus.0.power}}"
    device_class: power
    expire_after: 660
    json_attributes_topic: "miner2mqtt/rig0"   
    
  - platform: mqtt
    name: "GPU0_efficiency"
    state_topic: "miner2mqtt/rig0"
    unit_of_measurement: "kH/W"
    value_template: "{{value_json.gpus.0.efficiency.split('kH/W')[0]|int}}"
    device_class: power
    expire_after: 660
    json_attributes_topic: "miner2mqtt/rig0" 
```
</details>
<details>
  <summary>Кнопка обновить</summary>

```yaml
switch:
  - platform: mqtt
    unique_id: m2m_refresh
    name: "m2m_refresh"
    state_topic: "miner2mqtt/rig0/to_miner/refresh"
    command_topic: "miner2mqtt/rig0/to_miner/refresh"
    payload_on: "ON"
    payload_off: "OFF"
    state_on: "ON"
    state_off: "OFF"
```
</details>
<details>
  <summary>Вентилятор</summary>

```yaml
fan:
  - platform: mqtt
    name: "GPU0_fan"
    state_topic: "miner2mqtt/rig0/from_miner/0/fan_state"
    command_topic: "miner2mqtt/rig0/to_miner/0/fan_state"
    percentage_state_topic: "miner2mqtt/rig0/from_miner/0/fan_speed"
    percentage_command_topic: "miner2mqtt/rig0/to_miner/0/fan_speed"
    preset_mode_state_topic: "miner2mqtt/rig0/from_miner/0/fan_mode"
    preset_mode_command_topic: "miner2mqtt/rig0/to_miner/0/fan_mode"
    preset_modes:
      -  "auto"
      -  "manual"
```
</details>
<details>
  <summary>Power limit видеокарты (вариант light.)</summary>

```yaml
light:
  - platform: mqtt
    name: "GPU0_power_limit"
    state_topic: "miner2mqtt/rig0/from_miner/0/state"
    command_topic: "miner2mqtt/rig0/to_miner/0/state"
    icon: mdi:lightning-bolt-circle
    brightness_scale: 240
    max_mireds: 240
    min_mireds: 100
    brightness_state_topic: "miner2mqtt/rig0/from_miner/0/power_limit"
    brightness_command_topic: "miner2mqtt/rig0/to_miner/0/power_limit"
```
</details>
<details>
  <summary>Power limit видеокарты (вариант number.)</summary>

```yaml
number:
  - platform: mqtt
    name: "GPU0_power_limit"
    state_topic: "miner2mqtt/rig0/from_miner/0/power_limit"
    command_topic: "miner2mqtt/rig0/to_miner/0/power_limit"
    icon: mdi:lightning-bolt-circle
    min: 100
    max: 240
```
</details>

## Планы
- Windows
- cpuminer-gr-avx2
