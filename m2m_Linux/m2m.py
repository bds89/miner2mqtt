import yaml, datetime, time, sys, threading, urllib.request, inspect, os, json, platform, requests, re, subprocess
import paho.mqtt.subscribe as subscribe
import paho.mqtt.publish as publish

bool_conv = {"true": "ON", "false": "OFF", "ON":True, "OFF":False, "0":"auto", "1": "manual"}


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
                globals()["CONTENTS"] = contents
            else: print("WARNING: unknown miner")
        else: print("WARNING: unknown miner")
    except:
        print("WARNING: No data from miner")
        return
    data = json.loads(contents)
    #обновим power_limit, fan
    try:
        for gpu in enumerate(data["gpus"]):
            #power_limit
            mqtt_publish(gpu[1]["power"], "/from_miner/"+str(gpu[0])+"/power_limit")
            if gpu[1]["power"] > 20:
                mqtt_publish("ON", "/from_miner/"+str(gpu[0])+"/state")
            else: mqtt_publish("OFF", "/from_miner/"+str(gpu[0])+"/state")
            #fan
            mqtt_publish(gpu[1]["fan_speed"], "/from_miner/"+str(gpu[0])+"/fan_speed")
            if len(MEMBER["fan_speed"]) < gpu[0]+1:
                globals()["MEMBER"]["fan_speed"].append(gpu[1]["fan_speed"])
            else: 
                globals()["MEMBER"]["fan_speed"][gpu[0]] = gpu[1]["fan_speed"]
            if len(MEMBER["fan_mode"]) < gpu[0]+1:
                text = os.popen('nvidia-settings -q "[gpu:'+str(gpu[0])+']/GPUFanControlstate"').read()
                fan_mode = re.findall(r"gpu:\d+[]][)]: (\d)", text)
                if fan_mode:
                    globals()["MEMBER"]["fan_mode"].append(bool_conv[fan_mode[0]])
                    mqtt_publish(MEMBER["fan_mode"][gpu[0]], "/from_miner/"+str(gpu[0])+"/fan_mode")
            else: mqtt_publish(MEMBER["fan_mode"][gpu[0]], "/from_miner/"+str(gpu[0])+"/fan_mode")
            
            if len(MEMBER["fan_mode"]) >= gpu[0]+1 and re.search(r"[Mm][Aa][Nn][Uu][Aa][Ll]", MEMBER["fan_mode"][gpu[0]]) and gpu[1]["fan_speed"] == 0:
                state = "OFF"
                mqtt_publish(state, "/from_miner/"+str(gpu[0])+"/fan_state")
                
            else: 
                state = "ON"
                mqtt_publish(state, "/from_miner/"+str(gpu[0])+"/fan_state")
            if not MEMBER["fan_state"]: globals()["MEMBER"]["fan_state"].append(state)
            else: globals()["MEMBER"]["fan_state"][gpu[0]] = state

                
    except(KeyError): print("WARNING: Can't update fan in MQTT")
    
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

def gpu_pause(pause, card):
    if "MINER" in CONFIG:
        if CONFIG["MINER"] == "Trex":
            requests.post('http://127.0.0.1:4067/control', json={"pause": "{0}:{1}".format(pause, card)})
            print({"pause": "{0}:{1}".format(pause, card)})
        else: print("WARNING: can't pause this mainer")
    else: print("WARNING: can't pause this mainer")
    return

def power_limit(pl, card):
    if not "SUDO_PASS" in CONFIG:
        CONFIG["SUDO_PASS"] = ""
        print("INFO: havn't sudo password")
    try:
        pl = int(pl)
    except(ValueError, TypeError):
        print("WARNING: can't change power limit, bad value")
        return(False)
    if pl <= 0:
        print("INFO: power limit must be positive")
        return(False)
    p = subprocess.Popen(['sudo', '-S', 'nvidia-smi', '-i', str(card), '-pl', str(pl)], stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    text = p.communicate(CONFIG["SUDO_PASS"] + '\n')[0]
    if "All done" in text:
        print("INFO: "+text)
        return(True)
    if not text:
        print("WARNING: can't change power limit, no responce from NVIDIA")
        return(False)

def fan_state(fan, card):
    if fan in bool_conv: fan_bool = bool_conv[fan]
    else:
        print("WARNING: can't fan on/off, bad value")
        return(False)
    if fan_bool:
        sucses = fan_mode("auto", card)
    else:
        sucses = fan_speed(0, card)
    if sucses:
        globals()["MEMBER"]["fan_state"][card] = fan
        mqtt_publish(MEMBER["fan_state"][card], "/from_miner/"+str(card)+"/fan_state")
        return(True)
    else:
        print("WARNING: can't change fan on/off")
        return(False)

def fan_mode(fan, card):
    if re.search(r"[Aa][Uu][Tt][Oo]", fan):
        text = os.popen('nvidia-settings -a "[gpu:'+str(card)+']/GPUFanControlstate=0"').read()
    elif re.search(r"[Mm][Aa][Nn][Uu][Aa][Ll]", fan):
        text = os.popen('nvidia-settings -a "[gpu:'+str(card)+']/GPUFanControlstate=1" -a ["fan:0]/GPUTargetFanSpeed='+str(MEMBER["fan_speed"][card])+'" -a ["fan:1]/GPUTargetFanSpeed='+str(MEMBER["fan_speed"][card])+'"').read()
    else:
        print("WARNING: can't change fan mode, bad value")
        return(False)
    if "assigned value" in text:
        globals()["MEMBER"]["fan_mode"][card] = fan
        mqtt_publish(fan, "/from_miner/"+str(card)+"/fan_mode")
        print("INFO: "+text)
        return(True)
    else: 
        print("WARNING: can't change fan mode, NVIDIA error")
        return(False)

def fan_speed(fan, card):
    try:
        fan = int(fan)
    except(ValueError, TypeError):
        print("WARNING: can't fan speed, bad value")
        return(False)
    if fan < 0:
        print("INFO: fan speed must be positive")
        return(False)
    text = os.popen('nvidia-settings -a "[gpu:'+str(card)+']/GPUFanControlstate=1" -a ["fan:0]/GPUTargetFanSpeed='+str(fan)+'" -a ["fan:1]/GPUTargetFanSpeed='+str(fan)+'"').read()
    if "assigned value" in text:
        globals()["MEMBER"]["fan_mode"][card] = "manual"
        print("INFO: "+text)
        return(True)
    else:
        print("WARNING: can't change fan speed, NVIDIA error")
        return(False)

def mqtt_publish(contents, _topic="", retain=False, multiple=False):
    host = CONFIG["MQTT"]["HOST"]
    username = CONFIG["MQTT"]["USERNAME"]
    password = CONFIG["MQTT"]["PASS"]
    topic = CONFIG["MQTT"]["TOPIC"]+_topic
    try:
        if multiple: publish.multiple(msgs=contents, retain=retain, hostname=host, auth = {'username':username, 'password':password})
        else: publish.single(topic, contents, retain=retain, hostname=host, auth = {'username':username, 'password':password})
    except(TimeoutError): print("WARNING: Can't connect to MQTT")
        

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

def on_message(client, userdata, message):  #Здесь все команды получаемые ботом
    topic = message.topic
    msg = bytes.decode(message.payload, encoding='utf-8')
    #Обновление по запросу
    if topic == CONFIG["MQTT"]["TOPIC"]+"/to_miner/refresh" and msg == "ON":
        print(topic +": "+msg)
        gpu_info = get_gpu_info()
        mqtt_publish(gpu_info)
        mqtt_publish("OFF", "/to_miner/refresh")
        return

    #Пауза видеокарты
    if re.search(CONFIG["MQTT"]["TOPIC"]+r"/to_miner/[\d+]/state", topic):
        card = re.findall(r".+/(\d+)/state", topic)
        if card and msg in bool_conv:
            pause = bool_conv[msg]
            gpu_pause(pause, card[0])
            time.sleep(10)
            gpu_info = get_gpu_info()
            mqtt_publish(gpu_info)
        return

    #Изменение power limit
    if re.search(CONFIG["MQTT"]["TOPIC"]+r"/to_miner/[\d+]/power_limit", topic):
        card = re.findall(r".+/(\d+)/power_limit", topic)
        if card:
            card = int(card[0])
            print(topic +": "+msg)
            sucses = power_limit(msg, card)
            if sucses:
                time.sleep(5)
                gpu_info = get_gpu_info()
                mqtt_publish(gpu_info) 
        return

    #Изменение fan (on/off)
    if re.search(CONFIG["MQTT"]["TOPIC"]+r"/to_miner/[\d+]/fan_state", topic):
        card = re.findall(r".+/(\d+)/fan_state", topic)
        if card:
            card = int(card[0])
            print(topic +": "+msg)
            sucses = fan_state(msg, card)
            if sucses:
                time.sleep(10)
                gpu_info = get_gpu_info()
                mqtt_publish(gpu_info)
        return

    #Изменение fan mode
    if re.search(CONFIG["MQTT"]["TOPIC"]+r"/to_miner/[\d+]/fan_mode", topic):
        card = re.findall(r".+/(\d+)/fan_mode", topic)
        if card:
            card = int(card[0])
            print(topic +": "+msg)
            sucses = fan_mode(msg, card)
            if sucses:
                time.sleep(10)
                gpu_info = get_gpu_info()
                mqtt_publish(gpu_info)
        return

    #Изменение fan speed
    if re.search(CONFIG["MQTT"]["TOPIC"]+r"/to_miner/[\d+]/fan_speed", topic):
        card = re.findall(r".+/(\d+)/fan_speed", topic)
        if card:
            card = int(card[0])
            print(topic +": "+msg)
            sucses = fan_speed(msg, card)
            if sucses:
                time.sleep(10)
                gpu_info = get_gpu_info()
                mqtt_publish(gpu_info)
        return

def mqtt_listen(topic, host, username, password):
    topic = topic+"/to_miner/#"
    try: subscribe.callback(on_message, topic, hostname=host, auth = {'username':username, 'password':password})
    except(TimeoutError): print("WARNING: Can't connect to MQTT")

if __name__ == '__main__':
    system = platform.system()
    if system == "Linux": CONFIG_PATCH = get_script_dir()+"/config.yaml"
    elif system == "Windows": CONFIG_PATCH = get_script_dir()+"\config.yaml"
    else:
        try: CONFIG_PATCH = get_script_dir()+"/config.yaml" 
        except: 
            print("Not supported os")
            quit()
    with open(CONFIG_PATCH) as f:
        CONFIG = yaml.load(f.read(), Loader=yaml.FullLoader)
    
    MEMBER = {"fan_state":[], "fan_mode":[], "fan_speed":[]} #Запоминаем всякую всячину
    threading.Thread(target=polls, args=(CONFIG["INTERVAL"],)).start() #запускаем опрос майнера
    threading.Thread(target=mqtt_listen, args=(CONFIG["MQTT"]["TOPIC"],CONFIG["MQTT"]["HOST"],CONFIG["MQTT"]["USERNAME"],CONFIG["MQTT"]["PASS"],)).start() #подписываемся на топик

