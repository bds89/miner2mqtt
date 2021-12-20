import yaml, datetime, time, sys, threading, urllib.request, inspect, os, json, platform, requests, re, subprocess, psutil
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

def run(command):
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False, encoding="utf-8", bufsize=1, universal_newlines=True)
    while True:
        line = process.stderr.readline().rstrip()
        if not line and process.poll() != None:
            break
        yield line

def danila_parser(command):
    for log in run(command):
        print("danila log: "+log)
        matches_gpus_name = re.findall(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} [|] Starting benchmarks for device (.+)...", log)
        if matches_gpus_name: 
            for name in matches_gpus_name: globals()["GPUS_names"].append(name) 
        if not GPUS:
            matches_gpus = re.findall(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) [|] Total devices: (\d+)", log)
            if matches_gpus: globals()["GPUS"] = int(matches_gpus[0][1])
        matches = re.findall(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) [|] Total system hashrate (\d+.\d+) ([KkMG])hash/s, (\d+.\d+)s, (\d+) shares found", log)
        if matches:
            time_timestam = datetime.datetime.strptime(matches[0][0], "%Y-%m-%d %H:%M:%S,%f")
            hash = float(matches[0][1])*CONVERT[matches[0][2]]
            globals()["AVG_hash_now"][time_timestam] = hash
            globals()["AVG_hash_60"][time_timestam] = hash
            delta_time = matches[0][3]
            globals()["SHARES"] = matches[0][4]
            # print("{0}\nHASH: {1}; DELTA Time: {2}; SHARES: {3}".format(time_timestam, hash, delta_time, shares))


def get_gpu_info():
    try:
        if "MINER" in CONFIG:
            if CONFIG["MINER"] == "Trex":
                contents = urllib.request.urlopen("http://127.0.0.1:4067/summary").read()
                globals()["CONTENTS"] = contents
                data = json.loads(contents)
            #Для данилы
            elif CONFIG["MINER"] == "danila-miner": 
                #обновим средний хэш
                i = 0
                hash_1 = 0
                if AVG_hash_now:
                    for time_st in list(AVG_hash_now):
                        if datetime.datetime.now() - time_st < datetime.timedelta(seconds=60):
                            hash_1 += AVG_hash_now[time_st]
                            i += 1
                        if datetime.datetime.now() - time_st > datetime.timedelta(seconds=CONFIG["INTERVAL"]):
                            AVG_hash_now.pop(time_st)
                    hash_1 = hash_1/i
                if AVG_hash_now: 
                    hash_now = AVG_hash_now[list(AVG_hash_now)[-1]]
                else:
                    hash_now = 0
                    hash_1 = 0
                i = 0
                hash_60 = 0
                if AVG_hash_60:
                    for time_st in list(AVG_hash_60):
                        if datetime.datetime.now() - time_st > datetime.timedelta(minutes=60):
                            AVG_hash_60.pop(time_st)
                        else:
                            hash_60 += AVG_hash_60[time_st]
                            i += 1
                    hash_60 = hash_60/i
                
                data = {}
                data["gpus"] = []
                for gpu in range(GPUS):
                    if len(globals()["GPUS_names"]) < gpu+1:
                        globals()["GPUS_names"].append("unknown card")
                    #Возьмем данные с драйвера
                    p = subprocess.Popen(['sudo', '-S', 'nvidia-smi', '-i', str(gpu), '-q', '-x'], stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
                    text = p.communicate(CONFIG["SUDO_PASS"] + '\n')[0]
                    match_fan = re.findall(r".*<fan_speed>(\d+) %</fan_speed>.*", text)
                    if match_fan: fan_speed = float(match_fan[0])
                    match_temp = re.findall(r".*<gpu_temp>(\d+) C</gpu_temp>.*", text)
                    if match_temp: gpu_temp = float(match_temp[0])
                    match_pl = re.findall(r".*<power_limit>(\d+.\d+) W</power_limit>.*", text)
                    if match_pl: power_limit = float(match_pl[0])
                    #создадим словарь как в майнере.
                    data["gpus"].append({"hashrate":hash_now, "hashrate_hour":hash_60, "hashrate_minute":hash_1, "name": globals()["GPUS_names"][gpu], "power":power_limit, "fan_speed":int(fan_speed), "temperature":gpu_temp, "efficiency":round(hash_now/power_limit), "shares":SHARES})

                
            else: print("WARNING: unknown miner")
        else:
            data = {} 
            print("WARNING: unknown miner")
    except:
        print("WARNING: No data from miner")
        return
    #возьмем еще параметры компьютера из psutil
    USED_RAM = psutil.virtual_memory()[2]
    CPU_temp = psutil.sensors_temperatures(fahrenheit=False)["coretemp"][0][1]
    CPU_freq = round(psutil.cpu_freq(percpu=False)[0])
    fan_list = psutil.sensors_fans()
    CPU_FAN = "no fan"
    for key, value in fan_list.items():
        for i in value:
            if i[1]>0:
                CPU_FAN = i[1]
    data["sys_params"] = {"used_ram":USED_RAM, "cpu_temp":CPU_temp, "cpu_freq": CPU_freq, "cpu_fan":CPU_FAN}
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
            if len(MEMBER["fan_state"]) < gpu[0]+1: globals()["MEMBER"]["fan_state"].append(state)
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
        text = os.popen('nvidia-settings -a "[gpu:'+str(card)+']/GPUFanControlstate=1" -a ["fan:'+str(card*2)+']/GPUTargetFanSpeed='+str(MEMBER["fan_speed"][card])+'" -a ["fan:'+str(card*2+1)+']/GPUTargetFanSpeed='+str(MEMBER["fan_speed"][card])+'"').read()
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
    text = os.popen('nvidia-settings -a "[gpu:'+str(card)+']/GPUFanControlstate=1" -a ["fan:'+str(card*2)+']/GPUTargetFanSpeed='+str(fan)+'" -a ["fan:'+str(card*2+1)+']/GPUTargetFanSpeed='+str(fan)+'"').read()
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
    #Данила майнер
    if "MINER" in CONFIG and CONFIG["MINER"] == "danila-miner":
        CONVERT = {"k":1*10**3, "K":1*10**3, "M":1*10**6, "G":1*10**9}
        AVG_hash_now = {}
        AVG_hash_60 = {}
        SHARES = 0
        GPUS = 0
        GPUS_names = []
        threading.Thread(target=danila_parser, args=(CONFIG["danila_command"].split(),)).start() #запускаем данилу

    threading.Thread(target=polls, args=(CONFIG["INTERVAL"],)).start() #запускаем опрос майнера
    threading.Thread(target=mqtt_listen, args=(CONFIG["MQTT"]["TOPIC"],CONFIG["MQTT"]["HOST"],CONFIG["MQTT"]["USERNAME"],CONFIG["MQTT"]["PASS"],)).start() #подписываемся на топик

