# from asyncio import threads
# from concurrent.futures import thread
from concurrent.futures import thread
from curses import savetty
from lib2to3.pgen2.token import STAR
from unicodedata import numeric
import yaml, datetime, time, sys, threading, urllib.request, inspect, os, json, platform, requests, re, subprocess, psutil, socket, pickle, hashlib, sqlite3, signal
import paho.mqtt.subscribe as subscribe
import paho.mqtt.publish as publish
from flask import Flask, request, session

STOP, START, RUNNING, RESTART = range(4)
bool_conv = {"true": "ON", "false": "OFF", "ON":True, "OFF":False, "0":"auto", "1": "manual"}
app = Flask(__name__)
lock = threading.Lock()

lol_adapter_dict = {
    "Index":"device_id",
    "Fan_Speed":"fan_speed",
    "Name":"name",
    "Core_Temp":"temperature",
    "Power":"power",
    "vendor":""
}

nb_adapter_dict = {
    "core_clock":"CCLK",
    "fan":"fan_speed",
    "info":"name",
    "mem_clock":"MCLK",
    "lhr":"LHR",
    "id":"device_id",
    "hashrate_raw":"hashrate",
    "hashrate2_raw":"hashrate2",
    "vendor":""
}
def get_script_dir(follow_symlinks=True):
    if getattr(sys, 'frozen', False): # py2exe, PyInstaller, cx_Freeze
        path = os.path.abspath(sys.executable)
    else:
        path = inspect.getabsfile(get_script_dir)
    if follow_symlinks:
        path = os.path.realpath(path)
    return os.path.dirname(path)

def value_to_SI(value, dict):
    suffs = ""
    for suff in dict.keys():
        suffs += suff
    find_str = f"(\d+\.\d+).*([{suffs}])"
    match = re.findall(find_str, value)
    if len(match) == 2:
        return (int(match[0])*dict[match[1]])
    elif len(match) == 1:
        return (int(match[0]))
    else:
        find_str = f"(\d+).*([{suffs}])"
        match = re.findall(find_str, value)
        if len(match) == 2:
            return (int(match[0])*dict[match[1]])
        elif len(match) == 1:
            return (int(match[0]))
        else:
            return value

def kill_proc_tree(pid):
    parent = psutil.Process(pid)
    children = parent.children(recursive=True)
    if ("SUDO_PASS" in CONFIG):
        p = subprocess.Popen(['sudo', '-S', 'pwd'], stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        p.communicate(CONFIG["SUDO_PASS"] + '\n')
    for p in children:
        print(f"Terminate process: {p.pid}")
        subprocess.Popen(args=f"sudo kill {p.pid}", shell=True)


def run(command, std_type):
    state = "unknown"
    while True:
        if RUN_STATE == STOP:
            if state != "Stop":
                state = "Stop"
                mqtt_publish(state, "/from_miner/miner_state")
            if not "process" in locals() or ("process" in locals() and process.poll() != None):
                time.sleep(3)
                continue
            else:
                pid = os.getpgid(process.pid)
                print(kill_proc_tree(pid))
                time.sleep(5)
                continue
        elif RUN_STATE == START:
            if state != "Start":
                state = "StStartop"
                mqtt_publish(state, "/from_miner/miner_state")
            if not "process" in locals() or ("process" in locals() and process.poll() != None):
                if ("SUDO_PASS" in CONFIG):
                    p = subprocess.Popen(['sudo', '-S', 'pwd'], stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
                    p.communicate(CONFIG["SUDO_PASS"] + '\n')
                    process = subprocess.Popen(["sudo", "-S"]+command, stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.PIPE, shell=False, encoding="utf-8", bufsize=1, universal_newlines=True)
                    print(f"start with SUDO process: {process.pid}")
                else: 
                    process = subprocess.Popen(command, stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.PIPE, shell=False, encoding="utf-8", bufsize=1, universal_newlines=True)
                    print("start without SUDO")
                globals()["RUN_STATE"] = RUNNING
                continue
            else:
                pid = os.getpgid(process.pid)
                print(kill_proc_tree(pid))
                time.sleep(5)
                continue
        elif RUN_STATE == RUNNING:
            if state != "Running":
                state = "Running"
                mqtt_publish(state, "/from_miner/miner_state")
            try:
                if std_type == "err": line = process.stderr.readline().rstrip()
                elif std_type == "out": line = process.stdout.readline().rstrip()
                else: break
            except(UnicodeDecodeError) as e:
                print(e)
                pass
            if not line and process.poll() != None:
                print("Miner process stoped")
                globals()["RUN_STATE"] = STOP
            yield line
        elif RUN_STATE == RESTART:
            if state != "Restart":
                state = "Restart"
                mqtt_publish(state, "/from_miner/miner_state")
            if not "process" in locals() or ("process" in locals() and process.poll() != None):
                globals()["RUN_STATE"] = START
                continue
            else:
                pid = os.getpgid(process.pid)
                print(kill_proc_tree(pid))
                globals()["RUN_STATE"] = START
                time.sleep(5)
                continue
 

def danila_parser(command, std_type):
    for log in run(command, std_type):
        print(">: "+log)
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

def nb_parser(command, std_type):
    if command:
        for log in run(command, std_type):
            print(">: "+log)
            if "API" in CONFIG:
                url = str(CONFIG["API"])+"/api/v1/status"
                if re.search(r"Summary", log):
                    try:
                        contents = urllib.request.urlopen(url).read()
                        data = json.loads(contents)
                        time_timestam = datetime.datetime.now()
                        if not GPUS: globals()["GPUS"] = len(data["miner"]["devices"])
                        for i in range(GPUS):
                            if len(AVG_hash_now) < i+1:
                                AVG_hash_now.append({})
                                AVG_hash2_now.append({})
                                AVG_hash_60.append({})
                                AVG_hash2_60.append({})
                            globals()["AVG_hash_now"][i].update({time_timestam:data["miner"]["devices"][0]["hashrate_raw"]})
                            globals()["AVG_hash_60"][i].update({time_timestam:data["miner"]["devices"][0]["hashrate_raw"]})
                            if data["stratum"]["dual_mine"] == "true":
                                globals()["AVG_hash2_now"][i].update({time_timestam:data["miner"]["devices"][0]["hashrate2_raw"]})
                                globals()["AVG_hash2_60"][i].update({time_timestam:data["miner"]["devices"][0]["hashrate2_raw"]})
                    except Exception as e:
                        print("WARNING: No data from NBMiner API")
                        print(e)
                        if "sys_params" in overload_limits: globals()["overload_limits"]["sys_params"][PC_NAME] = "No data from NBMiner"
                        else: globals()["overload_limits"].update({"sys_params":{PC_NAME:"No data from NBMiner"}})

    else:
        if "API" in CONFIG:
            url = str(CONFIG["API"])+"/api/v1/status"
            while True:
                try:
                    contents = urllib.request.urlopen(url).read()
                    data = json.loads(contents)
                    time_timestam = datetime.datetime.now()
                    if not GPUS: globals()["GPUS"] = len(data["miner"]["devices"])
                    for i in range(GPUS):
                        if len(AVG_hash_now) < i+1:
                            AVG_hash_now.append({})
                            AVG_hash2_now.append({})
                            AVG_hash_60.append({})
                            AVG_hash2_60.append({})
                        globals()["AVG_hash_now"][i].update({time_timestam:data["miner"]["devices"][0]["hashrate_raw"]})
                        globals()["AVG_hash_60"][i].update({time_timestam:data["miner"]["devices"][0]["hashrate_raw"]})
                        if data["stratum"]["dual_mine"]:
                            globals()["AVG_hash2_now"][i].update({time_timestam:data["miner"]["devices"][0]["hashrate2_raw"]})
                            globals()["AVG_hash2_60"][i].update({time_timestam:data["miner"]["devices"][0]["hashrate2_raw"]})
                except Exception as e:
                    print("WARNING: No data from NBMiner API")
                    print(e)
                    if "sys_params" in overload_limits: globals()["overload_limits"]["sys_params"][PC_NAME] = "No data from NBMiner"
                    else: globals()["overload_limits"].update({"sys_params":{PC_NAME:"No data from NBMiner"}})
                time.sleep(18)

def lol_parser(command, std_type):
    name_hash = ""
    if command:
        lhrtune_str = 0
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        for log in run(command, std_type):
            print(">: "+log)
            if "API" in CONFIG:
                if log.find("--lhrtune") != -1: lhrtune_str = log.find("--lhrtune")
                if log.find("LHR") != -1: lhrtune_str = log.find("LHR")
                GPU_num = re.findall(r"GPU (.+):.need.to", log)
                if GPU_num:
                    GPU_num = int(ansi_escape.sub('', GPU_num[0]))
                    if GPU_num in lock_nums.keys(): globals()["lock_nums"][GPU_num] +=1
                    else: globals()["lock_nums"][GPU_num] = 1
                    print("LHR LOCK!")

                if lhrtune_str != 0:
                    matches_gpu = re.findall(r"GPU (\d+) .+", log)
                    matches_lhr = re.findall(r"(\d+\.\d+)", log[lhrtune_str-1:])
                    if matches_gpu and matches_lhr:
                        print(matches_lhr)
                        globals()["LHRtune"][int(matches_gpu[0])] = matches_lhr[0]
                matches = re.findall(r"(.+): Average speed .+: (\d+.\d+)", log)
                if matches:
                    if not name_hash: name_hash = matches[0][0]
                    if name_hash == matches[0][0]:
                        url = str(CONFIG["API"])
                        try:
                            contents = urllib.request.urlopen(url).read()
                            data = json.loads(contents)
                            time_timestam = datetime.datetime.now()
                            if not GPUS: globals()["GPUS"] = int(data["Num_Workers"])
                            K1 = re.findall("([MKkG])h",data["Algorithms"][0]["Performance_Unit"])
                            if K1: K1 = K1[0]
                            else: K1 = 10**6
                            for i in range(GPUS):
                                if len(AVG_hash_now) < i+1:
                                    AVG_hash_now.append({})
                                    AVG_hash2_now.append({})
                                    AVG_hash_60.append({})
                                    AVG_hash2_60.append({})
                                globals()["AVG_hash_now"][i].update({time_timestam:data["Algorithms"][0]["Worker_Performance"][i]*CONVERT[K1]})
                                globals()["AVG_hash_60"][i].update({time_timestam:data["Algorithms"][0]["Worker_Performance"][i]*CONVERT[K1]})
                                if len(data["Algorithms"]) > 1:
                                    K2 = re.findall("([MKkG])h",data["Algorithms"][1]["Performance_Unit"])[0]
                                    globals()["AVG_hash2_now"][i].update({time_timestam:data["Algorithms"][1]["Worker_Performance"][i]*CONVERT[K2]})
                                    globals()["AVG_hash2_60"][i].update({time_timestam:data["Algorithms"][1]["Worker_Performance"][i]*CONVERT[K2]})
                            
                        except:
                            print("WARNING: No data from lol-miner API")
                            if "sys_params" in overload_limits: globals()["overload_limits"]["sys_params"][PC_NAME] = "No data from lol-miner"
                            else: globals()["overload_limits"].update({"sys_params":{PC_NAME:"No data from lol-miner"}})
    elif "API" in CONFIG:
        url = str(CONFIG["API"])
        while True:
            try:
                contents = urllib.request.urlopen(url).read()
                data = json.loads(contents)
                time_timestam = datetime.datetime.now()
                if not GPUS: globals()["GPUS"] = int(data["Num_Workers"])
                K1 = re.findall("([MKkG])h",data["Algorithms"][0]["Performance_Unit"])
                if K1: K1 = K1[0]
                else: K1 = 10**6
                for i in range(GPUS):
                    if len(AVG_hash_now) < i+1:
                        AVG_hash_now.append({})
                        AVG_hash2_now.append({})
                        AVG_hash_60.append({})
                        AVG_hash2_60.append({})
                    globals()["AVG_hash_now"][i].update({time_timestam:data["Algorithms"][0]["Worker_Performance"][i]*CONVERT[K1]})
                    globals()["AVG_hash_60"][i].update({time_timestam:data["Algorithms"][0]["Worker_Performance"][i]*CONVERT[K1]})
                    if len(data["Algorithms"]) > 1:
                        K2 = re.findall("([MKkG])h",data["Algorithms"][1]["Performance_Unit"])[0]
                        globals()["AVG_hash2_now"][i].update({time_timestam:data["Algorithms"][1]["Worker_Performance"][i]*CONVERT[K2]})
                        globals()["AVG_hash2_60"][i].update({time_timestam:data["Algorithms"][1]["Worker_Performance"][i]*CONVERT[K2]})
            except:
                print("WARNING: No data from lol-miner API")
                if "sys_params" in overload_limits: globals()["overload_limits"]["sys_params"][PC_NAME] = "No data from lol-miner"
                else: globals()["overload_limits"].update({"sys_params":{PC_NAME:"No data from lol-miner"}})
            time.sleep(18)
    else: print("WARNING: Can't work without lol-command or lolAPI")

def dict_rename_keys(iterable, keys):
    if isinstance(iterable, dict):
        for key, value in keys.items(): 
            if key in iterable: iterable[value] = iterable.pop(key)
            else: iterable.update({key:value})
    return iterable

def get_gpu_info():
    if "MINER" in CONFIG:
        if CONFIG["MINER"] == "Trex":
            try:
                if "API" in CONFIG: url1 = str(CONFIG["API"])
                else: url1 = "http://127.0.0.1:4067"
                if globals()["SID"]: url = url1+"/summary?sid="+SID
                else: url = url1+"/summary"
                contents = urllib.request.urlopen(url).read()
                globals()["CONTENTS"] = contents
                data = json.loads(contents)
                if "dual_stat" in data:
                    for gpu in enumerate(data["dual_stat"]["gpus"]):
                        data["gpus"][gpu[0]].update({
                        "hashrate2":gpu[1]["hashrate"],
                        "hashrate_minute2":gpu[1]["hashrate_minute"], 
                        "hashrate_hour2":gpu[1]["hashrate_hour"], 
                        "hashrate_day2":gpu[1]["hashrate_day"]})
            except:
                print("WARNING: No data from Trex miner. Trying to reconnect")
                connectToTrex()
        #NBMiner
        elif CONFIG["MINER"] == "NBMiner":
            try:
                if "API" in CONFIG: url1 = str(CONFIG["API"])
                else: url1 = "http://127.0.0.1:4067"
                url = url1+"/api/v1/status"
                contents = urllib.request.urlopen(url).read()
                globals()["CONTENTS"] = contents
                data_nb = json.loads(contents)

                data = {}
                data["hashrate"] = data_nb["miner"]["total_hashrate_raw"]
                data["dual_mine"] = data_nb["stratum"]["dual_mine"]
                if data_nb["stratum"]["dual_mine"]: data["hashrate2"] = data_nb["miner"]["total_hashrate2_raw"]
                data["reboot_times"] = data_nb["reboot_times"]
                data["uptime"] = time.time() - int(data_nb["start_time"])
                data["accepted_shares"] = data_nb["stratum"]["accepted_shares"]
                data["invalid_shares"] = data_nb["stratum"]["invalid_shares"]
                data["reboot_times"] = data_nb["reboot_times"]
                data["gpu_total"] = len(data_nb["miner"]["devices"])

                #GPUS
                data["gpus"] = []
                for num, gpu in enumerate(data_nb["miner"]["devices"]):
                    data["gpus"].append(dict_rename_keys(gpu, nb_adapter_dict))

                    if not data_nb["stratum"]["dual_mine"]: data["gpus"][num].pop('hashrate2')
                    #efficiency
                    if data["gpus"][num]["power"] != 0:
                        data["gpus"][num].update({"efficiency":round(data["gpus"][num]["hashrate"]/data["gpus"][num]["power"])})
                        if data_nb["stratum"]["dual_mine"]: data["gpus"][num].update({"efficiency2":round(data["gpus"][num]["hashrate2"]/data["gpus"][num]["power"])})
                    else: 
                        data["gpus"][num].update({"efficiency":0})
                        if data_nb["stratum"]["dual_mine"]: data["gpus"][num].update({"efficiency2":0})
                #обновим средний хэш
                i = 0
                for num_gpu in range(GPUS):
                    hash_1 = 0
                    hash2_1 = 0
                    if AVG_hash_now[num_gpu]:
                        for time_st in list(AVG_hash_now[num_gpu]):
                            if datetime.datetime.now() - time_st < datetime.timedelta(seconds=60):
                                hash_1 += AVG_hash_now[num_gpu][time_st]
                                if AVG_hash2_now and time_st in AVG_hash2_now[num_gpu]:
                                    hash2_1 += AVG_hash2_now[num_gpu][time_st]
                                i += 1
                            else:
                                AVG_hash_now[num_gpu].pop(time_st)
                                if AVG_hash2_now and time_st in AVG_hash2_now[num_gpu]:
                                    AVG_hash2_now[num_gpu].pop(time_st)
                        if i > 0: 
                            hash_1 = round(hash_1/i, 2)
                            hash2_1 = round(hash2_1/i, 2)
                    if len(data["gpus"]) > num_gpu:
                        data["gpus"][num_gpu].update({"hashrate_minute":hash_1})
                        if AVG_hash2_now:
                            data["gpus"][num_gpu].update({"hashrate_minute2":hash2_1})

                    i = 0
                    hash_60 = 0
                    hash2_60 = 0
                    if AVG_hash_60[num_gpu]:
                        for time_st in list(AVG_hash_60[num_gpu]):
                            if datetime.datetime.now() - time_st < datetime.timedelta(minutes=60):
                                hash_60 += AVG_hash_60[num_gpu][time_st]
                                if AVG_hash2_60 and time_st in AVG_hash2_60[num_gpu]:
                                    hash2_60 += AVG_hash2_60[num_gpu][time_st]
                                i += 1
                            else:
                                AVG_hash_60[num_gpu].pop(time_st)
                                if AVG_hash2_60 and time_st in AVG_hash2_60[num_gpu]:
                                    AVG_hash2_60[num_gpu].pop(time_st)
                        if i > 0: 
                            hash_60 = round(hash_60/i, 2)
                            hash2_60 = round(hash2_60/i, 2)
                    if len(data["gpus"]) > num_gpu:
                        data["gpus"][num_gpu].update({"hashrate_hour":hash_60})
                        if AVG_hash2_60:
                            data["gpus"][num_gpu].update({"hashrate_hour2":hash2_60})
            except Exception as e:
                print(e)
                print("WARNING: No data from NBMiner miner. Trying to reconnect")
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
                    else:
                        AVG_hash_now.pop(time_st)
                if i > 0: hash_1 = round(hash_1/i,2)

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
                if i > 0: hash_60 = round(hash_60/i, 2)
            #обновим средний хэш2
            hash2_now = 0
            hash2_1 = 0
            hash2_60 = 0

            data = {}
            data["gpus"] = []
            gpu_name = ""
            gpu_vendor = ""
            fan_speed = 0
            gpu_temp = 0
            power_limit = 0
            for gpu in range(GPUS):
                try:
                    if system == "Linux":
                        #Возьмем данные с драйвера
                        p = subprocess.Popen(['sudo', '-S', 'nvidia-smi', '-i', str(gpu), '-q', '-x'], stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
                        text = p.communicate(CONFIG["SUDO_PASS"] + '\n')[0]
                        match_name = re.findall(r".*<product_name>(.+)</product_name>.*", text)
                        if match_name: gpu_name = match_name[0]
                        match_vendor = re.findall(r".*<product_brand>(.+)</product_brand>.*", text)
                        if match_vendor: gpu_vendor = match_vendor[0]

                        match_fan = re.findall(r".*<fan_speed>(\d+) %</fan_speed>.*", text)
                        if match_fan: fan_speed = float(match_fan[0])
                        match_temp = re.findall(r".*<gpu_temp>(\d+) C</gpu_temp>.*", text)
                        if match_temp: gpu_temp = float(match_temp[0])
                        match_pl = re.findall(r".*<power_limit>(\d+.\d+) W</power_limit>.*", text)
                        if match_pl: power_limit = float(match_pl[0])
                        else: power_limit = 1
                    #создадим словарь как в майнере.
                    if gpu == 0:
                        data["gpu_total"] = GPUS
                        data["hashrate"] = hash_now
                        data["hashrate_minute"] = hash_1
                        data["hashrate_hour"] = hash_60
                    data["gpus"].append({"power":power_limit, 
                    "temperature":gpu_temp, 
                    "hashrate":hash_now, 
                    "hashrate_minute":hash_1, 
                    "hashrate_hour":hash_60, 
                    "hashrate2":hash2_now, 
                    "hashrate_minute2":hash2_1, 
                    "hashrate_hour2":hash2_60, 
                    "name": gpu_name, 
                    "vendor": gpu_vendor,  
                    "fan_speed":int(fan_speed), 
                    "efficiency":round(hash_1/power_limit), 
                    "efficiency2":round(hash2_1/power_limit), 
                    "shares":SHARES})
                except:
                    print("WARNING: No data from Nvidia")
        #Для lol-miner
        elif CONFIG["MINER"] == "lol-miner" and "API" in CONFIG:
            data = {"gpus":[], "uptime":""}
            url = str(CONFIG["API"])
            try:
                contents = urllib.request.urlopen(url).read()
                lol_data = json.loads(contents)
                for i in enumerate(lol_data["Workers"]):
                    data["gpus"].append(dict_rename_keys(lol_data["Workers"][i[0]], lol_adapter_dict))
                data["uptime"] = lol_data["Session"]["Uptime"]
                data["gpu_total"] = GPUS


                K1 = re.findall("([MKkG])h",lol_data["Algorithms"][0]["Performance_Unit"])
                if K1: K1 = K1[0]
                else: K1 = 10**6
                for i in enumerate(lol_data["Algorithms"][0]["Worker_Performance"]):
                    data["gpus"][i[0]].update({"hashrate":i[1]*CONVERT[K1]})
                    data["gpus"][i[0]].update({"efficiency":i[1]*CONVERT[K1]/data["gpus"][i[0]]["power"]})
                    if len(lol_data["Algorithms"]) > 1:
                        K2 = re.findall("([MKkG])h",lol_data["Algorithms"][1]["Performance_Unit"])[0]
                        data["gpus"][i[0]].update({"hashrate2":lol_data["Algorithms"][1]["Worker_Performance"][i[0]]*CONVERT[K2]})
                        data["gpus"][i[0]].update({"efficiency2":i[1]*CONVERT[K2]/data["gpus"][i[0]]["power"]})
                    if LHRtune:
                        data["gpus"][i[0]].update({"LHR":LHRtune[i[0]]})
                    if i[0] in lock_nums:
                        data["gpus"][i[0]].update({"re-calibrate":lock_nums[i[0]]})


                data["hashrate"] = lol_data["Algorithms"][0]["Total_Performance"]*CONVERT[K1]
                if len(lol_data["Algorithms"]) > 1:
                    data["hashrate2"] = lol_data["Algorithms"][1]["Total_Performance"]*CONVERT[K2]
            except: 
                print("WARNING: No data from lol-miner API")
                if "sys_params" in overload_limits: globals()["overload_limits"]["sys_params"][PC_NAME] = "No data from lol-miner"
                else: globals()["overload_limits"].update({"sys_params":{PC_NAME:"No data from lol-miner"}})
            #обновим средний хэш
            i = 0
            for num_gpu in range(GPUS):
                hash_1 = 0
                hash2_1 = 0
                if AVG_hash_now[num_gpu]:
                    for time_st in list(AVG_hash_now[num_gpu]):
                        if datetime.datetime.now() - time_st < datetime.timedelta(seconds=60):
                            hash_1 += AVG_hash_now[num_gpu][time_st]
                            if AVG_hash2_now and time_st in AVG_hash2_now[num_gpu]:
                                hash2_1 += AVG_hash2_now[num_gpu][time_st]
                            i += 1
                        else:
                            AVG_hash_now[num_gpu].pop(time_st)
                            if AVG_hash2_now and time_st in AVG_hash2_now[num_gpu]:
                                AVG_hash2_now[num_gpu].pop(time_st)
                    if i > 0: 
                        hash_1 = round(hash_1/i, 2)
                        hash2_1 = round(hash2_1/i, 2)
                if len(data["gpus"]) > num_gpu:
                    data["gpus"][num_gpu].update({"hashrate_minute":hash_1})
                    if AVG_hash2_now:
                        data["gpus"][num_gpu].update({"hashrate_minute2":hash2_1})

                i = 0
                hash_60 = 0
                hash2_60 = 0
                if AVG_hash_60[num_gpu]:
                    for time_st in list(AVG_hash_60[num_gpu]):
                        if datetime.datetime.now() - time_st < datetime.timedelta(minutes=60):
                            hash_60 += AVG_hash_60[num_gpu][time_st]
                            if AVG_hash2_60 and time_st in AVG_hash2_60[num_gpu]:
                                hash2_60 += AVG_hash2_60[num_gpu][time_st]
                            i += 1
                        else:
                            AVG_hash_60[num_gpu].pop(time_st)
                            if AVG_hash2_60 and time_st in AVG_hash2_60[num_gpu]:
                                AVG_hash2_60[num_gpu].pop(time_st)
                    if i > 0: 
                        hash_60 = round(hash_60/i, 2)
                        hash2_60 = round(hash2_60/i, 2)
                if len(data["gpus"]) > num_gpu:
                    data["gpus"][num_gpu].update({"hashrate_hour":hash_60})
                    if AVG_hash2_60:
                        data["gpus"][num_gpu].update({"hashrate_hour2":hash2_60})

        else: print("WARNING: unknown miner or no API")
    else:
        data = {} 
        print("WARNING: unknown miner")
    if not "data" in locals(): data = {} 
    #возьмем еще параметры компьютера из psutil
    USED_RAM = psutil.virtual_memory()[2]
    CPU_freq = round(psutil.cpu_freq(percpu=False)[0])
    CPU_temp = 0
    CPU_FAN = "no fan"
    if system == "Linux":
        try:
            CPU_temp = psutil.sensors_temperatures(fahrenheit=False)["coretemp"][0][1]
        except: CPU_temp = 0
        fan_list = psutil.sensors_fans()
        for key, value in fan_list.items():
            for i in value:
                if i[1]>0:
                    CPU_FAN = i[1]
    data["sys_params"] = {"used_ram":USED_RAM, "cpu_temp":CPU_temp, "cpu_freq": CPU_freq, "cpu_fan":CPU_FAN}
    #обновим power_limit, fan
    if system == "Linux":
        try:
            for gpu in enumerate(data["gpus"]):
                #power_limit
                mqtt_publish(gpu[1]["power"], "/from_miner/"+str(gpu[0])+"/power_limit")
                if gpu[1]["power"] > 5:
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

                    
        except(KeyError): print("WARNING: Can't update power limit and fan in MQTT")
    
    if "INCLUDE" in CONFIG and CONFIG["INCLUDE"]:
        answ = {}
        for key, value in data.items():
            if key in CONFIG["INCLUDE"]:
                answ[key] = value
    elif "EXCLUDE" in CONFIG and CONFIG["EXCLUDE"]:
        answ = data
        for key in list(data):
            if key in CONFIG["EXCLUDE"]:
                answ.pop(key)
    else: answ = data
    data_answ = {"code": 200, "text": "success", "data": answ}
    #add limits
    if "LIMITS" in globals(): data_answ["limits"] = LIMITS
    # print("========================"); print(data_answ); print("=============================")
    return(data_answ)

def gpu_pause(pause, card):
    if "MINER" in CONFIG:
        if CONFIG["MINER"] == "Trex":
            if "API" in CONFIG: url1 = str(CONFIG["API"])
            else: url1 = "http://127.0.0.1:4067"
            if "SID" in globals(): url = url1+"/control?sid="+SID
            else: url = url1+"/control"
            requests.post(url, json={"pause": "{0}:{1}".format(pause, card)})
            print({"pause": "{0}:{1}".format(pause, card)})
        else: print("WARNING: can't pause this mainer")
    else: print("WARNING: can't pause this mainer")
    return

def power_limit(pl, card, m2a=False):
    card = int(card)
    if not "SUDO_PASS" in CONFIG:
        CONFIG["SUDO_PASS"] = ""
        print("INFO: havn't sudo password")
    try:
        pl = int(pl)
    except(ValueError, TypeError):
        print("WARNING: can't change power limit, bad value")
        text = "Can't change power limit, bad value"
        if m2a: return {"code": 100, "text": text}
        return(False)
    if pl <= 0:
        print("INFO: power limit must be positive")
        text = "Power limit must be positive"
        if m2a: return {"code": 100, "text": text}
        return(False)
    p = subprocess.Popen(['sudo', '-S', 'nvidia-smi', '-i', str(card), '-pl', str(pl)], stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    text = p.communicate(CONFIG["SUDO_PASS"] + '\n')[0]
    if "All done" in text:
        text += "\n" + save_to_db_start_params(ptype=card, pname="power_limit", val=pl)
        print("INFO: "+text)
        if m2a: return {"code": 200, "text": text, "data":{}}
        return(True)
    if not text:
        print("WARNING: can't change power limit, no responce from NVIDIA")
        text = "Can't change power limit, no responce from NVIDIA"
        if m2a: return {"code": 100, "text": text}
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

def fan_mode(fan, card, m2a=False):
    card = int(card)
    if re.search(r"[Aa][Uu][Tt][Oo]", fan):
        fan = "auto"
        text = os.popen('nvidia-settings -a "[gpu:'+str(card)+']/GPUFanControlstate=0"').read()
    elif re.search(r"[Mm][Aa][Nn][Uu][Aa][Ll]", fan):
        fan = "manual"
        text = os.popen('nvidia-settings -a "[gpu:'+str(card)+']/GPUFanControlstate=1" -a ["fan:'+str(card*2)+']/GPUTargetFanSpeed='+str(MEMBER["fan_speed"][card])+'" -a ["fan:'+str(card*2+1)+']/GPUTargetFanSpeed='+str(MEMBER["fan_speed"][card])+'"').read()
    else:
        print("WARNING: can't change fan mode, bad value")
        text = "Can't change fan mode, bad value"
        if m2a: return {"code": 100, "text": text}
        return(False)
    if "assigned value" in text:
        globals()["MEMBER"]["fan_mode"][card] = fan
        if "MQTT" in CONFIG: mqtt_publish(fan, "/from_miner/"+str(card)+"/fan_mode")
        text += "\n" + save_to_db_start_params(ptype=card, pname="fan_mode", val=fan)
        print("INFO: "+text)
        if m2a: return {"code": 200, "text": text, "data":{"fan_mode":fan}}
        return(True)
    else: 
        print("WARNING: can't change fan mode, NVIDIA error")
        text = "Can't change fan mode, NVIDIA error"
        if m2a: return {"code": 100, "text": text}
        return(False)

def fan_speed(fan, card, m2a=False):
    try:
        fan = int(fan)
        card = int(card)
    except(ValueError, TypeError):
        print("WARNING: can't change fan speed, bad value")
        text = "Can't change fan speed, bad value"
        if m2a: return {"code": 100, "text": text}
        return(False)
    if fan < 0:
        print("INFO: fan speed must be positive")
        text = "Fan speed must be positive"
        if m2a: return {"code": 100, "text": text}
        return(False)
    text = os.popen('nvidia-settings -a "[gpu:'+str(card)+']/GPUFanControlstate=1" -a ["fan:'+str(card*2)+']/GPUTargetFanSpeed='+str(fan)+'" -a ["fan:'+str(card*2+1)+']/GPUTargetFanSpeed='+str(fan)+'"').read()
    if "assigned value" in text:
        globals()["MEMBER"]["fan_mode"][card] = "manual"
        text += "\n" + save_to_db_start_params(ptype=card, pname="fan_speed", val=fan)
        text += "\n" + save_to_db_start_params(ptype=card, pname="fan_mode", val="manual")
        print("INFO: "+text)
        if m2a: return {"code": 200, "text": text, "data":{"fan_mode":"manual"}}
        return(True)
    else:
        print("WARNING: can't change fan speed, NVIDIA error")
        text = "Can't change fan speed, NVIDIA error"
        if m2a: return {"code": 100, "text": text}
        return(False)

def miner_state(state, m2a=False):
    state_list = ["Stop", "Start", "Running", "Restart"]
    text = ""
    if re.search(r"[Ss][Tt][Oo][Pp]", state): 
        globals()["RUN_STATE"] = STOP
        text += state_list[RUN_STATE]
    elif re.search(r"[Rr][Ee][Ss][Tt][Aa][Rr][Tt]", state): 
        globals()["RUN_STATE"] = RESTART
        text += state_list[RUN_STATE]
    elif re.search(r"[Ss][Tt][Aa][Rr][Tt]", state): 
        globals()["RUN_STATE"] = START
        text += state_list[RUN_STATE]
    elif state == "Refresh" and m2a: 
        text += state_list[RUN_STATE]
    else: text += "Unknown state"
    if m2a: return {"code": 200, "text": text}
    return(True)


@app.route('/get_fan_mode', methods=['POST'])
def m2a_get_fan_mode(card=False):  #Получить режим вентилятора
    if system == "Linux":
        if request:
            if request.is_json:
                request_data = request.get_json()
                if isauth(request_data):
                    print("Mobile App: Get fan mode")
                    if request_data["ex_IP"] == "" or request_data["in_IP"] == "":        
                        return json.dumps({"code": 200, "text": "", "data":{"fan_mode":MEMBER["fan_mode"][int(request_data["card"])]}})
                    host = request_data["in_IP"]
                    port = int(request_data["in_port"])
                    params = [request_data["card"]]
                    data = socket_client(host, port, "m2a_get_fan_mode", params)
                    return json.dumps(data)
                answer = {"code": 300, "text": "Authorisation Error"}
                if "sys_params" in overload_limits: globals()["overload_limits"]["sys_params"][PC_NAME] = "Authorisation Error"
                else: globals()["overload_limits"].update({"sys_params":{PC_NAME:"Authorisation Error"}})
                return json.dumps(answer)
            return {"code": 100, "text": "Missing JSON in request"}
        else: 
            if card != False and len(MEMBER["fan_mode"]) > int(card): return {"code": 200, "text": "", "data":{"fan_mode":MEMBER["fan_mode"][int(card)]}}
            else: return {"code": 100, "text": "bad value"}
    else: return {"code": 100, "text": "Not supported OS"}

#Graph
@app.route('/graph', methods=['POST'])
def m2a_graph():
    if request.is_json:
        request_data = request.get_json()
        if isauth(request_data):
            print("Mobile App: "+request_data["request"])
            if request_data["ex_IP"] == "" or request_data["in_IP"] == "" or request_data["request"] == "check_limits":
                if request_data["request"] == "graph": return json.dumps(load_from_db_gpu_info(request_data["pname"], request_data["ptype"]))
                else: return {"code": 100, "text": "Bad request"}
                
            host = request_data["in_IP"]
            port = int(request_data["in_port"])
            if request_data["request"] == "graph": params = [request_data["pname"], request_data["ptype"]]
            else: params = ""
            data = socket_client(host, port, request_data['request'], params)
            return json.dumps(data)
        answer = {"code": 300, "text": "Authorisation Error"}
        if "sys_params" in overload_limits: globals()["overload_limits"]["sys_params"][PC_NAME] = "Authorisation Error"
        else: globals()["overload_limits"].update({"sys_params":{PC_NAME:"Authorisation Error"}})
        return json.dumps(answer)
    return {"code": 100, "text": "Missing JSON in request"}   
#Управление из приложения!!!!!!!!!!!!!!!!!!!!!!!!
@app.route('/control', methods=['POST'])
def m2a_control():
    if system == "Linux":
        if request.is_json:
            request_data = request.get_json()
            if isauth(request_data):
                print("Mobile App: "+request_data["request"])
                if request_data["ex_IP"] == "" or request_data["in_IP"] == "" or request_data["request"] == "check_limits":
                    if request_data["request"] == "fan_speed": return json.dumps(fan_speed(request_data["value"], request_data["card"], True))
                    elif request_data["request"] == "fan_mode": return json.dumps(fan_mode(request_data["value"], request_data["card"], True))
                    elif request_data["request"] == "miner_state": return json.dumps(miner_state(request_data["value"], True))
                    elif request_data["request"] == "power_limit": return json.dumps(power_limit(request_data["value"], request_data["card"], True))
                    elif request_data["request"] == "send_limits": return json.dumps(send_limits(request_data["value"]))
                    elif request_data["request"] == "check_limits":
                        if not "full_check" in request_data: request_data["full_check"] = False
                        return json.dumps(check_limits(request_data["name"], request_data["value"], request_data["full_check"]))
                    elif request_data["request"] == "graph": return json.dumps(load_from_db_gpu_info(request_data["pname"], request_data["ptype"]))
                    else: return {"code": 100, "text": "Bad request"}
                    
                host = request_data["in_IP"]
                port = int(request_data["in_port"])
                if request_data["request"] == "send_limits" or request_data["request"] == "miner_state": params = [request_data["value"]]
                elif request_data["request"] == "graph": params = [request_data["pname"], request_data["ptype"]]
                else: params = [request_data["value"], request_data["card"]]
                data = socket_client(host, port, request_data['request'], params)
                return json.dumps(data)
            answer = {"code": 300, "text": "Authorisation Error"}
            if "sys_params" in overload_limits: globals()["overload_limits"]["sys_params"][PC_NAME] = "Authorisation Error"
            else: globals()["overload_limits"].update({"sys_params":{PC_NAME:"Authorisation Error"}})
            return json.dumps(answer)
        return {"code": 100, "text": "Missing JSON in request"}
    else: return {"code": 100, "text": "Not supported OS"}

def check_limits(this_pc_name, ips=False, full_check=False):
    output_text = {"code": 200, "data": {this_pc_name: int(time.time())}}
    if full_check:
        gpu_info = get_gpu_info()
        if "LIMITS" in globals() and "data" in gpu_info: 
            periodic_check_limits(gpu_info["data"])
    if "overload_limits" in globals() and overload_limits:
        output_text["data"][this_pc_name] = overload_limits
    if ips:
        for name, ip in ips.items():
            ipport = ip.split(":")
            params = [name, full_check]
            data = socket_client(ipport[0], int(ipport[1]), "check_limits", params)
            if data["code"] == 200 and data["data"]: output_text["data"].update(data["data"])
            else: output_text["data"].update({name:data})
    globals()["overload_limits"] = {}
    print(output_text)
    return output_text

def send_limits(limits):
    if "LIMITS" in globals() and limits:
        with lock:
            for key1, one_type in limits.items():
                for key2, lim in one_type.items():
                    if key1 in LIMITS:
                        if key2 in LIMITS[key1] and len(LIMITS[key1][key2])>2 and LIMITS[key1][key2][2] > lim[2]: continue
                        else: globals()["LIMITS"][key1][key2] = lim
                    else: globals()["LIMITS"][key1] = {key2:lim}
    else: globals()["LIMITS"] = limits
    print(LIMITS)
    with open(LIMITS_PATCH, "wb") as f:
        pickle.dump(limits, f)
    globals()["overload_limits"] = {}
    return {"code": 200, "text": "succes"}

def mqtt_publish(contents, _topic="", retain=False, multiple=False):
    host = CONFIG["MQTT"]["HOST"]
    username = CONFIG["MQTT"]["USERNAME"]
    password = CONFIG["MQTT"]["PASS"]
    topic = CONFIG["MQTT"]["TOPIC"]+_topic
    try:
        if multiple: publish.multiple(msgs=contents, retain=retain, hostname=host, auth = {'username':username, 'password':password})
        else: publish.single(topic, contents, retain=retain, hostname=host, auth = {'username':username, 'password':password})
    except: print("WARNING: Can't connect to MQTT")
    #   TimeoutError, ConnectionRefusedError, paho.mqtt.MQTTException


def periodic_check_limits(gpu_info, is_dict=True, item_num="other"):
    if is_dict:
        for key, value in gpu_info.items():
            if type(value) == list: periodic_check_limits(value, False)
            elif type(value) == dict: periodic_check_limits(value, True, key)
            else:
                if type(value) == int or type(value) == float or (type(value) == str and value.isnumeric()):
                    if float(value) > 1000000: value = float(value)/1000000
                    else: value = float(value)
                item_num = str(item_num)
                #for sys params
                if item_num == "sys_params" and "99999" in LIMITS and key in LIMITS["99999"]:
                    if LIMITS["99999"][key][1]:
                        if value > float(LIMITS["99999"][key][0]): 
                            if "sys_params" in overload_limits: globals()["overload_limits"]["sys_params"][key] = value
                            else: globals()["overload_limits"]["sys_params"] = {key:value}
                    else:
                        if value < float(LIMITS["99999"][key][0]):
                            if "sys_params" in overload_limits: globals()["overload_limits"]["sys_params"][key] = value
                            else: globals()["overload_limits"]["sys_params"] = {key:value}
                #for gpu and other
                if item_num in LIMITS and key in LIMITS[item_num]:
                    if LIMITS[item_num][key][1]:
                        if value > float(LIMITS[item_num][key][0]):
                            if "GPU"+item_num in overload_limits: globals()["overload_limits"]["GPU"+item_num][key] = value
                            else: globals()["overload_limits"]["GPU"+item_num] = {key:value}
                    else:
                        if value < float(LIMITS[item_num][key][0]):
                            if "GPU"+item_num in overload_limits: globals()["overload_limits"]["GPU"+item_num][key] = value
                            else: globals()["overload_limits"]["GPU"+item_num] = {key:value}
    else:
        for item in enumerate(gpu_info):
            if type(item[1]) == list: periodic_check_limits(item[1], False)
            elif type(item[1]) == dict: periodic_check_limits(item[1], True, item[0])
            else: pass

def polls(interval):
    print("M2M started")
    print("Set interval: "+str(datetime.timedelta(seconds=interval)))
    while True:
        if interval == 0:
            time.sleep(5)
        else:
            gpu_info = get_gpu_info()
            if "MQTT" in CONFIG:
                if "data" in gpu_info:
                    mqtt_publish(json.dumps(gpu_info["data"]))
            #check_limits
            if "LIMITS" in globals() and "data" in gpu_info: 
                periodic_check_limits(gpu_info["data"])
            #BD
            if "APP" in CONFIG:
                save_to_db_gpu_info(gpu_info["data"])
            time.sleep(interval)

def on_message(client, userdata, message):  #Здесь все команды получаемые ботом
    topic = message.topic
    msg = bytes.decode(message.payload, encoding='utf-8')
    #Обновление по запросу
    if topic == CONFIG["MQTT"]["TOPIC"]+"/to_miner/refresh" and msg == "ON":
        print(topic +": "+msg)
        gpu_info = get_gpu_info()
        if gpu_info:
            mqtt_publish(json.dumps(gpu_info["data"]))
        mqtt_publish("OFF", "/to_miner/refresh")
        return

    #Пауза видеокарты
    if re.search(CONFIG["MQTT"]["TOPIC"]+r"/to_miner/[\d+]/state", topic):
        card = re.findall(r".+/(\d+)/state", topic)
        if card and msg in bool_conv:
            if msg == "ON": pause = "false"
            else: pause = "true"
            gpu_pause(pause, card[0])
            time.sleep(2)
            gpu_info = get_gpu_info()
            mqtt_publish(json.dumps(gpu_info["data"]))
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
                mqtt_publish(json.dumps(gpu_info["data"])) 
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
                mqtt_publish(json.dumps(gpu_info["data"]))
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
                mqtt_publish(json.dumps(gpu_info["data"]))
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
                mqtt_publish(json.dumps(gpu_info["data"]))
        return

    #Изменение miner_state
    if re.search(CONFIG["MQTT"]["TOPIC"]+r"/to_miner/miner_state", topic):
        print(topic +": "+msg)
        miner_state(msg)
        return

def mqtt_listen(topic, host, username, password):
    while True:
        topic = topic+"/to_miner/#"
        try: subscribe.callback(on_message, topic, hostname=host, auth = {'username':username, 'password':password})
        except: 
            print("WARNING: Can't connect to MQTT")
            time.sleep(CONFIG["INTERVAL"])
            continue

def flask(CONFIG):
    net_info = psutil.net_if_addrs()
    if not "IP_FLASK" in CONFIG["APP"]: 
        address = "127.0.0.1"
        for value in net_info.values():
            if re.findall(r"\d+\.\d+\.\d+\.\d+", value[0].address) and value[0].address != '127.0.0.1':
                address = value[0].address
            if len(value) > 1:
                if re.findall(r"\d+\.\d+\.\d+\.\d+", value[1].address) and value[1].address != '127.0.0.1':
                    address = value[1].address
    else: address = str(CONFIG["APP"]["IP_FLASK"])
    if not "PORT_FLASK" in CONFIG["APP"]: port = 5000
    else: port = int(CONFIG["APP"]["PORT_FLASK"])
    from waitress import serve
    print("Your IP(Gateway IP): {0}, Port(Gateway Port): {1}".format(address, port))
    serve(app, host=address, port=port, threads=20)

def socket_server(CONFIG):
    host = "0.0.0.0"
    if not "PORT_SOCKET" in CONFIG["APP"]: port = 5100
    else: port = int(CONFIG["APP"]["PORT_SOCKET"])
    if "SUDO_PASS" in CONFIG:
        while True:
            p = subprocess.Popen(['sudo', '-S', 'lsof', '-i', ':'+str(port)], stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            text = p.communicate(str(CONFIG["SUDO_PASS"]) + '\n')[0]
            if not text: break
            time.sleep(5)

    global mySocket
    mySocket = socket.socket()
    print("Binding socket")
    try_n = 0
    while try_n < 7:
        try:
            mySocket.bind((host,port))
            print("socket server started at port "+str(port))
            break
        except(OSError): 
            time.sleep(10)
            try_n += 1

    while True:
        mySocket.listen(1)
        conn, addr = mySocket.accept()
        print ("Connection from: " + str(addr[0]))
        try: data = pickle.loads(conn.recv(2048))
        except: data = "error_data"
        if not data:
            conn.close()
            time.sleep(1)
            continue

            
        if data == "error_data":
            conn.sendall(pickle.dumps({"code": 100, "text": "slave_pc not recieved request"}))
        else:
            #Code in slavePC
            if data[0] == "fan_speed": data = fan_speed(data[1][0], data[1][1], True)
            elif data[0] == "fan_mode": data = fan_mode(data[1][0], data[1][1], True)
            elif data[0] == "power_limit": data = power_limit(data[1][0], data[1][1], True)
            elif data[0] == "send_limits": data = send_limits(data[1][0])
            elif data[0] == "miner_state": data = miner_state(data[1][0], True)
            elif data[0] == "m2a_get_fan_mode": data = m2a_get_fan_mode(data[1][0])
            elif data[0] == "check_limits": data = check_limits(data[1][0], False, data[1][1])
            elif data[0] == "get_gpu_info": data = get_gpu_info()
            elif data[0] == "m2a_ping": data = m2a_ping()
            elif data[0] == "graph": data = load_from_db_gpu_info(data[1][0], data[1][1])
            else: data = {"code": 100, "text": "Bad request"}
            data = pickle.dumps(data)
            conn.sendall(data)
    conn.close()

def socket_client(host, port, request, params=""):

        mySocket = socket.socket()
        mySocket.settimeout(5)
        try:
            mySocket.connect((host,port))
            mySocket.settimeout(None)
        except(ConnectionRefusedError, OSError):
            data = {"code": 100, "text": "Can't connect to "+str(host)+"\n"}
            return data
        for_send = [request, params]
        mySocket.send(pickle.dumps(for_send))
        data = mySocket.recv(2048)
        while data:
            try: 
                data_unpickle = pickle.loads(data)
                break
            except: 
                dat = mySocket.recv(2048)
                if not dat:
                    break
                data += dat
        if not data:
            data = {"code": 100, "text": "Not received data\n"}
            mySocket.close()
            return data
        mySocket.close()
        return data_unpickle

@app.route('/refresh', methods=['POST'])
def m2a_refresh():  #Обнолвение из приложения
    if request.is_json:
        request_data = request.get_json()
        if isauth(request_data):
            print("Mobile App: Refresh")
            if request_data["ex_IP"] == "" or request_data["in_IP"] == "":
                return json.dumps(get_gpu_info())
            host = request_data["in_IP"]
            port = int(request_data["in_port"])
            data = socket_client(host, port, "get_gpu_info")
            return json.dumps(data)
        answer = {"code": 300, "text": "Authorisation Error"}
        if "sys_params" in overload_limits: globals()["overload_limits"]["sys_params"][PC_NAME] = "Authorisation Error"
        else: globals()["overload_limits"].update({"sys_params":{PC_NAME:"Authorisation Error"}})
        return json.dumps(answer)
    return {"code": 100, "text": "Missing JSON in request"}

@app.route('/ping', methods=['POST'])
def m2a_ping():  #Обнолвение из приложения
    if request:
        request_data = request.get_json()
        if isauth(request_data):
            print("Mobile App: ping")
            if request_data["ex_IP"] == "" or request_data["in_IP"] == "":
                answer = {"code": 200, "text": "ping ok"}
                return json.dumps(answer)
            host = request_data["in_IP"]
            port = int(request_data["in_port"])
            data = socket_client(host, port, "m2a_ping")
            return json.dumps(data)
        else:
            print("Mobile App: Authorisation Error")
            answer = {"code": 300, "text": "Authorisation Error"}
            if "sys_params" in overload_limits: globals()["overload_limits"]["sys_params"][PC_NAME] = "Authorisation Error"
            else: globals()["overload_limits"].update({"sys_params":{PC_NAME:"Authorisation Error"}})
            return json.dumps(answer)
    return {"code": 200, "text": "ping ok"}

def isauth(pc):
    globals()["PC_NAME"] = pc["name"]
    if "id" in session: return True
    else:
        if CONFIG["APP"]["PASS"] == pc["upass"]:
            session["id"] = pc["id"]
            # print("New session for pc: "+str(pc["name"]))
            return True
    return False

def connectToTrex():
    if "MINER" in CONFIG and CONFIG["MINER"] == "Trex":
        if "TrexAPIPASS" in CONFIG:
            if "API" in CONFIG: url1 = str(CONFIG["API"])
            else: url1 = "http://127.0.0.1:4067"
            password = str(CONFIG["TrexAPIPASS"])
            try: 
                contents = urllib.request.urlopen(url1+"/login?password="+password).read()
                data = json.loads(contents)
                if data["success"] == 1: 
                    globals()["SID"] = data["sid"]
                    print("Trex authorization success")
                else: print("WARNING: Trex authorization error")
            except: 
                print("WARNING: No data from Trex miner")
                if "sys_params" in overload_limits: globals()["overload_limits"]["sys_params"][PC_NAME] = "No data from Trex miner"
                else: globals()["overload_limits"].update({"sys_params":{PC_NAME:"No data from Trex miner"}})
                
def apply_params_on_start(cursor):
    try:
        cursor.execute("SELECT * FROM system_start_params")
        data = cursor.fetchall()
        print("Applying parameters on start:")
        start_params = {}
        if data:
            for row in data:
                if row[0] in start_params:
                    start_params[row[0]].update({row[1]:row[2]})
                else:
                    start_params[row[0]] = {}
                    start_params[row[0]].update({row[1]:row[2]})

            for card, params in start_params.items():
                if "power_limit" in params:
                    p = subprocess.Popen(['sudo', '-S', 'nvidia-smi', '-i', str(card), '-pl', str(params["power_limit"])], stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
                    text = p.communicate(CONFIG["SUDO_PASS"] + '\n')[0]
                    print(text)
                if "fan_mode" in params and params["fan_mode"] == "auto":
                    text = os.popen('nvidia-settings -a "[gpu:'+str(card)+']/GPUFanControlstate=0"').read()
                    print(text)
                    continue
                if "fan_speed" in params and "fan_mode" in params and params["fan_mode"] == "manual":
                    text = os.popen('nvidia-settings -a "[gpu:'+str(card)+']/GPUFanControlstate=1" -a ["fan:'+str(card*2)+']/GPUTargetFanSpeed='+str(params["fan_speed"])+'" -a ["fan:'+str(card*2+1)+']/GPUTargetFanSpeed='+str(params["fan_speed"])+'"').read()
                    print(text)
        else: print("no parameters")
    except Exception as e:
        print(e)

def save_to_db_start_params(ptype, pname, val):
    sqlite_connection = sqlite3.connect(DB_PATCH)
    cursor = sqlite_connection.cursor()
    one_string = (ptype, pname, val)
    try: cursor.execute('''INSERT OR REPLACE INTO system_start_params VALUES(?,?,?)''', one_string)
    except Exception as e: 
        print(e)
        return "Error save value to DB"
    sqlite_connection.commit()
    sqlite_connection.close()
    return "Successful save to db"

def load_from_db_gpu_info(pname, ptype):
    sqlite_connection = sqlite3.connect(DB_PATCH)
    cursor = sqlite_connection.cursor()
    try:
        cursor.execute("SELECT date, value FROM all_params WHERE ptype = '"+ptype+"' AND pname = '"+pname+"' ORDER BY date ASC")
        data = cursor.fetchall()
        sqlite_connection.close()
        return {"code": 200, "data": data}
    except Exception as e:
        print(e)
        return {"code": 100, "text": "Error load from DB"}


def save_to_db_gpu_info(gpu_info):
    sqlite_connection = sqlite3.connect(DB_PATCH)
    cursor = sqlite_connection.cursor()
    now_datetime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for key, value in gpu_info.items():
        if key == "gpus":
            for gpu in enumerate(value):
                for pname, val in gpu[1].items():
                    if type(val) == list or type(val) == dict:continue
                    one_string = (now_datetime, "GPU"+str(gpu[0]), pname, val)
                    try: cursor.execute('''INSERT INTO all_params VALUES(?,?,?,?)''', one_string)
                    except Exception as e: 
                        print(e)
                        break
        elif key == "sys_params":
            for pname, val in value.items():
                one_string = (now_datetime, "sys_params", pname, val)
                try: cursor.execute('''INSERT INTO all_params VALUES(?,?,?,?)''', one_string)
                except Exception as e: 
                    print(e)
                    print(val)
                    continue
        elif type(key) != list and type(key) != dict and type(value) != list and type(value) != dict:
            one_string = (now_datetime, "main", key, value)
            try: cursor.execute('''INSERT INTO all_params VALUES(?,?,?,?)''', one_string)
            except Exception as e: 
                print(e)
                print(value)
                continue
        else: continue

    try:
        cursor.execute("DELETE FROM all_params WHERE date < DATE('"+datetime.datetime.now().strftime('%Y-%m-%d')+"','-1 day')")
    except Exception as e: 
        print(e)
    sqlite_connection.commit()
    sqlite_connection.close()


if __name__ == '__main__':
    system = platform.system()
    if system == "Linux": 
        CONFIG_PATCH = get_script_dir()
        LIMITS_PATCH = CONFIG_PATCH+"/limits.sys"
        DB_PATCH = CONFIG_PATCH+"/values.db"
        CONFIG_PATCH = CONFIG_PATCH+"/config.yaml"
    elif system == "Windows": 
        CONFIG_PATCH = get_script_dir()
        LIMITS_PATCH = CONFIG_PATCH+"\limits.sys"
        CONFIG_PATCH = CONFIG_PATCH+"\config.yaml"
    else:
        try: 
            CONFIG_PATCH = get_script_dir()
            LIMITS_PATCH = CONFIG_PATCH+"/limits.sys"
            CONFIG_PATCH = CONFIG_PATCH+"/config.yaml"
        except:
            print("Not supported os")
            quit()
    with open(CONFIG_PATCH) as f:
        CONFIG = yaml.load(f.read(), Loader=yaml.FullLoader)
    
    MEMBER = {"fan_state":[], "fan_mode":[], "fan_speed":[]} #Запоминаем всякую всячину
    RUN_STATE = START
    SID = "" #SID for Trex
    #limits
    overload_limits = {}
    #Trex майнер
    connectToTrex()
    #NBMiner
    if "MINER" in CONFIG and CONFIG["MINER"] == "NBMiner":
        CONVERT = {"k":1*10**3, "K":1*10**3, "M":1*10**6, "G":1*10**9}
        AVG_hash_now = []
        AVG_hash_60 = []
        AVG_hash2_now = []
        AVG_hash2_60 = []
        GPUS = 0
        if "COMMAND" in CONFIG: command = CONFIG["COMMAND"]
        else: command = ""
        threading.Thread(target=nb_parser, args=(command.split(), "err",)).start() #запускаем NBMiner
        time.sleep(5)
    #Данила майнер
    if "MINER" in CONFIG and CONFIG["MINER"] == "danila-miner":
        CONVERT = {"k":1*10**3, "K":1*10**3, "M":1*10**6, "G":1*10**9}
        AVG_hash_now = {}
        AVG_hash_60 = {}
        SHARES = 0
        GPUS = 0
        threading.Thread(target=danila_parser, args=(CONFIG["COMMAND"].split(), "err",)).start() #запускаем данилу
        time.sleep(5)
    #Lol майнер
    if "MINER" in CONFIG and CONFIG["MINER"] == "lol-miner":
        CONVERT = {"k":1*10**3, "K":1*10**3, "M":1*10**6, "G":1*10**9}
        AVG_hash_now = []
        AVG_hash_60 = []
        AVG_hash2_now = []
        AVG_hash2_60 = []
        LHRtune = {}
        lock_nums = {}
        GPUS = 0
        if "COMMAND" in CONFIG: command = CONFIG["COMMAND"]
        else: command = ""
        threading.Thread(target=lol_parser, args=(command.split(), "out",)).start() #запускаем LolMiner
        time.sleep(5)

    if "MQTT" in CONFIG:
        threading.Thread(target=mqtt_listen, args=(CONFIG["MQTT"]["TOPIC"],CONFIG["MQTT"]["HOST"],CONFIG["MQTT"]["USERNAME"],CONFIG["MQTT"]["PASS"],)).start() #подписываемся на топик
    threading.Thread(target=polls, args=(CONFIG["INTERVAL"],)).start() #запускаем опрос майнера

    if "APP" in CONFIG and not CONFIG["APP"]: CONFIG["APP"] = {"SLAVE_PC":False}
    if "APP" in CONFIG and "SLAVE_PC" in CONFIG["APP"] and CONFIG["APP"]["SLAVE_PC"]:
        threading.Thread(target=socket_server, args=(CONFIG,)).start() #Server socket for slave pc
    else:
        if "APP" in CONFIG:
            if "SESSIONKEY" in CONFIG["APP"]: app.secret_key = str(CONFIG["APP"]["SESSIONKEY"])
            else: app.secret_key = b"123456789a"
            threading.Thread(target=flask, args=(CONFIG,)).start() #Flask for miner2android
            if "PASS" in CONFIG["APP"]:
                hash_object = hashlib.sha1(CONFIG["APP"]["PASS"].encode('utf-8'))
            else: hash_object = hashlib.sha1("".encode('utf-8'))
            CONFIG["APP"]["PASS"] = hash_object.hexdigest()
    if "APP" in CONFIG:
        PC_NAME = "Gateway PC"
        if os.path.exists(LIMITS_PATCH):
            with open(LIMITS_PATCH, "rb") as f:
                LIMITS = pickle.load(f)
        #create DB
    #DB CONNECT
    sqlite_connection = sqlite3.connect(DB_PATCH)
    cursor = sqlite_connection.cursor()
    try:
        cursor.execute("""CREATE TABLE if not exists all_params
                        (date timestamp, ptype text, pname text, value text)
                    """)

        cursor.execute("""CREATE TABLE if not exists system_start_params
                        (ptype INT, pname text, value INT, UNIQUE(ptype,pname))
                    """)
        sqlite_connection.commit()
    except Exception as e:
        print(e)

    apply_params_on_start(cursor)
    sqlite_connection.close()
            

