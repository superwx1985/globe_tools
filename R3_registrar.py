from wsgiref import headers

import requests
import tkinter as tk
import logging
import io
import threading
import uuid
from logger_config import get_logger, TextHandler
from datetime import datetime
from tkinter import ttk
from tkinter import scrolledtext


def make_file_object(file_content):
    file_like_object = io.StringIO(file_content)
    return {'file': ('example.txt', file_like_object, 'text/plain')}


def raise_connection_error(response):
    raise ConnectionError(f"Connection error, please check the response of Request ID: {response._id}")


def print_request_info(prepared_request, logger):
    msg = f"""
====================
Request ID: {prepared_request._id}
Request URL: {prepared_request.url}
Request Method: {prepared_request.method}
Request Headers: {prepared_request.headers}
Request Body: {prepared_request.body}
===================="""
    logger.info(msg)


def print_response_info(response, logger, highlight_error=False):
    msg = f"""
====================
Request ID: {response._id}
Response Code: {response.status_code}
Response Message: {response.text}
Response Elapsed: {response.elapsed}
===================="""
    if highlight_error and response.status_code >= 400:
        logger.error(msg)
    else:
        logger.info(msg)


def request(method, url, headers=None, files=None, data=None, params=None, auth=None, cookies=None, hooks=None, json=None, logger=get_logger(), highlight_error=False):
    session = requests.Session()
    _id = str(uuid.uuid4())
    req = requests.Request(method, url, headers, files, data, params, auth, cookies, hooks, json)
    prepared_request = session.prepare_request(req)
    prepared_request._id = _id
    print_request_info(prepared_request, logger)
    rep = session.send(prepared_request)
    rep._id = _id
    print_response_info(rep, logger, highlight_error)
    return rep


def register(env, device_type, row, sn, mcu1, mcu2, logger=get_logger()):
    try:
        envs = {"DEV": {"centralized_endpoint_api": "https://center-api.globe-groups.com/globe",
                        "client_id": "SendService",
                        "client_secret": "339ded25-e049-4a75-aa82-e635be12a412",
                        "username": "vic.wang@globetools.com",
                        "password": "Glb123456",
                        "regionIso3": "CHN",
                        "type": "0"
                        },
                "DEMO": {"centralized_endpoint_api": "https://api.globetechcorp.com/globe",
                         "client_id": "SendService",
                         "client_secret": "339ded25-e049-4a75-aa82-e635be12a412",
                         "username": "vic.wang@globetools.com",
                         "password": "Glb123456",
                         "regionIso3": "SWE",
                         "type": "1"
                         },
                }

        centralized_endpoint_api = envs[env]["centralized_endpoint_api"]
        client_id = envs[env]["client_id"]
        client_secret = envs[env]["client_secret"]
        username = envs[env]["username"]
        password = envs[env]["password"]
        region_iso3 = envs[env]["regionIso3"]
        _type = envs[env]["type"]
        device_api = ""
        app_api = ""
        guc_api = ""

        get_region_body = {
            "merchantId": "100000000000000000",
            "type": _type,
            "regionIso3": region_iso3
        }
        get_region_rep = request("POST", f"{centralized_endpoint_api}/world/country/getRegion", json=get_region_body, logger=logger, highlight_error=True)
        if get_region_rep.status_code == 200:
            urls = get_region_rep.json()["info"]["apiUrl"]
            device_api = urls["app"]
            app_api = urls["globe"]
            guc_api = urls["guc"]
        else:
            raise_connection_error(get_region_rep)

        get_token_payload = f"grant_type=password&client_id={client_id}&client_secret={client_secret}&username={username}&password={password}"
        access_token = ""
        get_token_rep = request("POST", f"{guc_api}/connect/token", headers={"Content-Type": "application/x-www-form-urlencoded"}, data=get_token_payload, logger=logger, highlight_error=True)
        if get_token_rep.status_code == 200:
            _ = get_token_rep.json()
            access_token = f"{_["token_type"]} {_["access_token"]}"
        else:
            raise_connection_error(get_token_rep)

        formatted_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        if device_type == "Mower":
            register_mower_app_board_payload = f"{row};000042;{formatted_time};{sn};{mcu1};{mcu2};221;1;0;040085400;05;"
            register_mower_app_board_rep = request("POST", f"{app_api}/v3/service/common/RLM3/device/1", params={"fileName": "1.csv"}, headers={"Access-Token": access_token}, data=register_mower_app_board_payload, logger=logger, highlight_error=True)
            _ = register_mower_app_board_rep.json()
            if register_mower_app_board_rep.status_code == 200 and row in _["data"]["success"]:
                logger.info(f"{row} mower_app_board register successfully")
            else:
                logger.error(f"mower_app_board register failed: {_["message"]}")
    
            register_mower_info_payload = f"{row};000028;{formatted_time};{sn};1109-030-B-10A:010;1109-030-B-10B:3;1109-030-B-10C:01;1109-030-B-10D:000000000;1109-030-B-10E:00;1109-030-B-10F:0000000000;1109-030-B-20A:040077800;1109-030-B-20B:06;1109-030-B-20C:235040013;1109-030-B-20D:1703887890;1109-030-B-25A:040085400;1109-030-B-25B:05;1109-030-B-25C:1704192278;1109-030-B-30:000000000021;1109-030-B-40:001693398400;1109-030-B-45:001703254987;1109-030-B-50A:000000000000000;1109-030-B-50B:00000000000000000000;1109-030-B-50C:000000000000000000000000000000;1109-030-B-60A:000000000;1109-030-B-60B:00;1109-030-B-60C:0000000000;1109-030-B-60D:00000000;1109-030-B-60E:000000000;1109-030-B-60F:000;1109-030-B-60G:0;1109-030-B-60H:00;1109-030-B-60I:000;1109-030-B-60J:0;1109-030-B-60K:00;1109-030-B-60L:000000000;1109-030-B-60M:00;1109-030-B-60N:0;1109-030-B-70:0000;"
            register_mower_info_rep = request("POST", f"{app_api}/v3/service/common/RLM3/device/2", params={"fileName": "2.csv"}, headers={"Access-Token": access_token}, data=register_mower_info_payload, logger=logger, highlight_error=True)
            _ = register_mower_info_rep.json()
            if register_mower_info_rep.status_code == 200 and row in _["data"]["success"]:
                logger.info(f"{row} mower_info register successfully")
            else:
                logger.error(f"mower_info register failed: {_["message"]}")
        else:
            register_ra_info_payload = f"{row};000038;{formatted_time};{sn};{mcu1};{mcu2};16;1;1;040099000;04;"
            register_ra_info_rep = request("POST", f"{app_api}/v3/service/common/RA/device/3",
                                                   params={"fileName": "3.csv"}, headers={"Access-Token": access_token},
                                                   data=register_ra_info_payload, logger=logger,
                                                   highlight_error=True)
            _ = register_ra_info_rep.json()
            if register_ra_info_rep.status_code == 200 and row in _["data"]["success"]:
                logger.info(f"{row} ra_info register successfully")
            else:
                logger.error(f"ra_info register failed: {_["message"]}")

    except Exception as e:
        logger.error(e)
        raise e


class MyApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.log_handler = None
        self.xlink_vehicle = None
        self.logger = get_logger()
        self.logger.setLevel(logging.DEBUG)
        self.tasks = list()

        def async_call(func, *args, **kwargs):
            self.register_button.config(text="Running", state=tk.DISABLED)
            t = threading.Thread(target=func, args=args, kwargs=kwargs)
            self.tasks.append(t)
            t.daemon = True
            t.start()

        def check_register_status():
            i = 0
            while i < len(self.tasks):
                if not self.tasks[i].is_alive():
                    self.tasks.pop(i)
                    self.register_button.config(text="Register", state=tk.NORMAL)
                i += 1

        def loop_update():
            check_register_status()
            # 1 秒后再次调用自己
            self.after(1000, loop_update)

        # 创建主窗口
        self.title("R3 Registrar")
        # self.geometry("400x200")

        left_frame = tk.Frame(self)
        left_frame.grid(row=0, column=0, sticky="nsew")

        right_frame = tk.Frame(self)
        right_frame.grid(row=0, column=1, sticky="nsew")

        # 配置行和列，使其随窗口大小调整
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=0)  # 左框架不自适应大小
        self.grid_columnconfigure(1, weight=1)

        i = 0
        # 创建环境下拉框
        label = tk.Label(left_frame, text="Environment")
        label.grid(row=i, column=0, padx=2, pady=2, sticky='e')
        self.env_combo = ttk.Combobox(left_frame, state="readonly", width=25)
        self.env_combo['values'] = ('DEV', 'DEMO')
        self.env_combo.current(0)
        self.env_combo.grid(row=i, column=1, padx=2, pady=2, sticky='w')
        i += 1

        # 创建类型下拉框
        label = tk.Label(left_frame, text="Device Type")
        label.grid(row=i, column=0, padx=2, pady=2, sticky='e')
        self.type_combo = ttk.Combobox(left_frame, state="readonly", width=25)
        self.type_combo['values'] = ('Mower', 'RA')
        self.type_combo.current(0)
        self.type_combo.grid(row=i, column=1, padx=2, pady=2, sticky='w')
        i += 1

        def create_label_entry_button(frame, name, default="", width=40, row=0, column=0):
            label = tk.Label(frame, text=name)
            label.grid(row=row, column=0, padx=2, pady=2, sticky='e')
            entry = tk.Entry(frame, width=width)
            entry.config(textvariable=tk.StringVar(value=default), font=("Consolas", 9))
            entry.grid(row=row, column=1, padx=2, pady=2, sticky='w')
            return frame, label, entry

        def create_label_text_button(frame, name, default="", width=40, row=0, column=0):
            label = tk.Label(frame, text=name)
            label.grid(row=row, column=0, padx=2, pady=2, sticky='e')
            text = tk.Text(frame, width=width, height=3)
            text.config(font=("Consolas", 9))
            text.insert(tk.END, default)
            text.grid(row=row, column=1, padx=2, pady=2, sticky='w')
            return frame, label, text

        self.row_entry = create_label_entry_button(left_frame, "Equipment ID", "00001560", row=i)[2]
        i += 1

        self.sn_entry = create_label_entry_button(left_frame, "SN", "235060013", row=i)[2]
        i += 1

        self.MCU1_text = create_label_text_button(left_frame, "MCU1", "045D4989617E00FA68B6B765C8B4F72D", row=i)[2]
        i += 1

        self.MCU2_text = create_label_text_button(left_frame, "MCU2", "F7E8625100283EAF37F852F7617B47A1", row=i)[2]
        i += 1

        def click_register():
            env = self.env_combo.get()
            device_type = self.type_combo.get()
            row = self.row_entry.get().strip().replace(" ", "")
            sn = self.sn_entry.get().strip().replace(" ", "")
            mcu1 = self.MCU1_text.get("1.0", tk.END).strip().replace(" ", "")
            mcu2 = self.MCU2_text.get("1.0", tk.END).strip().replace(" ", "")
            self.logger.info(f"{env=} {row=} {sn=} {mcu1=} {mcu2=}")
            register(env, device_type, row, sn, mcu1, mcu2, self.logger)

        self.register_button = tk.Button(left_frame, text="Register", fg="green", width=10, command=lambda: async_call(click_register))
        self.register_button.grid(row=i, column=1, padx=2, sticky='w')

        # 创建一个 ScrolledText 小部件用于显示日志
        i = 0
        self.log_widget = scrolledtext.ScrolledText(right_frame, state='disabled', wrap='none', font=('Consolas', 8))
        self.log_widget.grid(row=i, column=0, padx=2, pady=2, sticky="nsew")
        right_frame.grid_rowconfigure(i, weight=1)
        right_frame.grid_columnconfigure(0, weight=1)

        i += 1
        # 创建并配置水平滚动条
        x_scrollbar = tk.Scrollbar(right_frame, orient=tk.HORIZONTAL, command=self.log_widget.xview)
        x_scrollbar.grid(row=i, column=0, sticky='ew')
        self.log_widget.configure(xscrollcommand=x_scrollbar.set)
        i += 1

        # 创建自定义日志处理器
        self.log_handler = TextHandler(self.log_widget)

        # 设置日志格式
        formatter = logging.Formatter('%(asctime)s - %(levelname)s: %(message)s')
        self.log_handler.setFormatter(formatter)

        # 获取根日志记录器并添加处理器
        logger = get_logger()
        logger.setLevel(logging.INFO)
        logger.addHandler(self.log_handler)

        def clear():
            self.log_widget.configure(state='normal')
            self.log_widget.delete(1.0, tk.END)  # 清空内容
            self.log_widget.configure(state='disabled')

        clean_log_button = tk.Button(right_frame, text="Clear Log", command=clear, width=10)
        clean_log_button.grid(row=i, column=0, padx=2, pady=2)
        i += 1

        loop_update()


if __name__ == "__main__":
    pass
    app = MyApp()
    app.mainloop()
