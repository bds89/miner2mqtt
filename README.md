# Miner2MQTT

Доступ к вашему GPU майнеру через MQTT.

<img src="screenshots/ha.jpg" width="400"> <img src="screenshots/ha_t.jpg" width="400">

## Изменения

<details>
  <summary>1.0</summary>

- EXE файл для Windows
</details>

## Описание

**Поддерживаемые ОС**

- Linux
- Windows (не тестировалось)

**Поддерживаемые майнеры**

- T-Rex

**Воможности:**
- Публикация всей информации от майнера в MQTT
- Возможность выборочной публикации (`INCLUDE` и `EXCLUDE` параметры в `config.yaml`)
- Обновление с указанным интервалом или по требованию (путем публикации `"ON"` в `ваш_топик/to_miner/refresh`)

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
MINER: Trex
    #выбор GPU майнера, на данный моменр только T-rex
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
EXCLUDE: {}
    #фильтры по ключам из JSON словаря вашего майнера (поддерживаются только ключи первого уровня)
```

## Примеры интеграции в Home Asistant:
<details>
  <summary>Сборный сенсор GPU0</summary>

```yaml
sensor:
  - platform: mqtt
    name: "GPU0"
    state_topic: "miner2mqtt/rig0"
    unit_of_measurement: "MH/s"
    value_template: "{{ (value_json.gpus.0.hashrate_minute/1000000)|round(2) }}"
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

## Планы
- Windows
- Управление майнером
- NBMiner
