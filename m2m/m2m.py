import yaml, datetime, time, sys, threading, urllib.request, inspect, os, json, platform
import paho.mqtt.subscribe as subscribe
import paho.mqtt.publish as publish

def get_script_dir(follow_symlinks=True):
    if getattr(sys, 'frozen', False): # py2exe, PyInstaller, cx_Freeze
        path = os.path.abspath(sys.executable)
    else:
        path = inspect.getabsfile(get_script_dir)
    if follow_symlinks:
        path = os.path.realpath(path)
    return os.path.dirname(path)

def get_gpu_info():
    try:
        if "MINER" in CONFIG:
            if CONFIG["MINER"] == "Trex":
                contents = urllib.request.urlopen("http://127.0.0.1:4067/summary").read()
            else: print("WARNING: UNKNOWN MINER")
        else: print("WARNING: UNKNOWN MINER")
    except:
        print("WARNING: NO DATA FROM MINER")
        return
    data = json.loads(contents)
    if "INCLUDE" in CONFIG and CONFIG["INCLUDE"]:
        answ = {}
        for key, value in data.items():
            if key in CONFIG["INCLUDE"]:
                answ[key] = value
    else:
        if "EXCLUDE" in CONFIG and CONFIG["EXCLUDE"]:
            answ = data
            for key in list(data):
                if key in CONFIG["EXCLUDE"]:
                    answ.pop(key)
    if "answ" in locals():
        contents = json.dumps(answ)
    return(contents)

def mqtt_publish(contents, _topic="", retain=False):
    host = CONFIG["MQTT"]["HOST"]
    username = CONFIG["MQTT"]["USERNAME"]
    password = CONFIG["MQTT"]["PASS"]
    topic = CONFIG["MQTT"]["TOPIC"]+_topic
    publish.single(topic, contents, retain=retain, hostname=host, auth = {'username':username, 'password':password})

def polls(interval):
    print("M2M started")
    print("Set interval: "+str(datetime.timedelta(seconds=interval)))
    while True:
        if interval == 0:
            time.sleep(5)
        else:
            gpu_info = get_gpu_info()
            mqtt_publish(gpu_info)
            mqtt_publish("OFF", "/to_miner/refresh")
            time.sleep(interval)

def on_message(client, userdata, message):
    topic = message.topic
    msg = bytes.decode(message.payload, encoding='utf-8')
    if topic == CONFIG["MQTT"]["TOPIC"]+"/to_miner/refresh" and msg == "ON":
        gpu_info = get_gpu_info()
        mqtt_publish(gpu_info)
        mqtt_publish("OFF", "/to_miner/refresh")

        print(topic +": "+msg)
def mqtt_listen(topic, host, username, password):
    topic = topic+"/to_miner/#"
    subscribe.callback(on_message, topic, hostname=host, auth = {'username':username, 'password':password})

if __name__ == '__main__':
    system = platform.system()
    if system == "Linux": CONFIG_PATCH = get_script_dir()+"/config.yaml"
    elif system == "Windows": CONFIG_PATCH = get_script_dir()+"\config.yaml"
    with open(CONFIG_PATCH) as f:
        CONFIG = yaml.load(f.read(), Loader=yaml.FullLoader)
    threading.Thread(target=polls, args=(CONFIG["INTERVAL"],)).start() #запускаем опрос майнера
    threading.Thread(target=mqtt_listen, args=(CONFIG["MQTT"]["TOPIC"],CONFIG["MQTT"]["HOST"],CONFIG["MQTT"]["USERNAME"],CONFIG["MQTT"]["PASS"],)).start() #подписываемся на топик

