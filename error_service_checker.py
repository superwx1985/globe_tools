import requests
import tkinter as tk
import logging
import io
import threading
import uuid
import json
import pandas as pd
from urllib import parse
from concurrent.futures import ThreadPoolExecutor
from logger_config import get_logger, TextHandler
from tkinter import filedialog, messagebox, scrolledtext


def async_call(func, *args, **kwargs):
    t = threading.Thread(target=func, args=args, kwargs=kwargs)
    t.daemon = True
    t.start()


def get_token(domain, client_id, client_secret, scope="", logger=get_logger()):
    url = f"{domain}/connect/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    payload_dict = {"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret, "scope": scope}
    payload = parse.urlencode(payload_dict)
    r = _request("POST", url=url, headers=headers, data=payload, logger=logger)
    r_json = r.json()
    return f'{r_json["token_type"]} {r_json["access_token"]}'


def check_error_return(domain, access_token, product, model, component, language, error_code, fault_code, content, suggestion, logger=get_logger()):
    logger.info(f"Checking {product=} {model=} {language=} {error_code=} {fault_code=}")
    url = f"{domain}/api/FaultCodeCategory/errorcodes"
    payload_dict = {
        "productCode": product,
        "modelNumber": model,
        "language": language,
        "errorCodes": [
            {
                "datapointComponent": component,
                "code": str(error_code)
            }
        ]
    }
    headers = {"Content-Type": "application/json", "Authorization": access_token}
    payload = json.dumps(payload_dict)
    result = {"result": "Pass", "detail": ""}
    r = requests.request("POST", url=url, headers=headers, data=payload)
    try:
        r_json = r.json()

        def normalize_newlines(text):
            return text.replace("\r\n", "\n").replace("\r", "\n")

        def check_data(name, _result, expected, actual):
            expected = normalize_newlines(expected)
            actual = normalize_newlines(actual)
            if expected != actual:
                _result["result"] = "Failed"
                _result["detail"] = f'{_result["detail"]}{name} -> expected: [{expected}], but got [{actual}]\n'

        check_data("component", result, r_json["data"]["errorList"][0]["component"], component)
        check_data("dataPointComponent", result, r_json["data"]["errorList"][0]["dataPointComponent"], component)
        check_data("faultCode", result, r_json["data"]["errorList"][0]["faultCode"], fault_code)
        check_data("content", result, r_json["data"]["errorList"][0]["content"], content)
        check_data("suggestion", result, r_json["data"]["errorList"][0]["suggestion"], suggestion)
    except Exception as e:
        logger.error(e)
        result["result"] = f'Error'
        result["detail"] = f'{result["detail"]}\nError is {e}\nResponse is {r.text}'

    return result


# 处理 Excel 文件函数
def process_excel_files(domain, token, file_list, save_path, logger):
    try:
        # 读取表
        df = pd.DataFrame()
        for f in file_list.split("|"):
            excel_f = pd.ExcelFile(f)
            for sheet_name in excel_f.sheet_names:
                _ = pd.read_excel(f, sheet_name=sheet_name)
                df = pd.concat([df, _], ignore_index=True)

        # 逐行处理
        # df["result"] = df.apply(lambda x: check_error_return(domain, token, x['product'], x['model number'], x['component'], x['language'], x['error code'], x['fault code'], x['content'], x['suggestion'], logger=logger), axis=1)

        # 多线程处理函数
        def process_row_with_closure(domain, token, logger):  # 将额外参数封闭到函数内部，避免显式传递参数
            def inner(x):
                return check_error_return(domain, token, x['product'], x['model number'], x['component'], x['language'], x['error code'], x['fault code'], x['content'], x['suggestion'], logger=logger)
            return inner

        # 使用 ThreadPoolExecutor 并行处理
        with ThreadPoolExecutor() as executor:
            process_row = process_row_with_closure(domain, token, logger)
            results = list(executor.map(process_row, [row for _, row in df.iterrows()]))

        # 将结果分配回 DataFrame
        df[["result", "detail"]] = pd.DataFrame(results, columns=["result", "detail"])

        # 保存结果为 Excel 文件
        df.to_excel(save_path, index=False)
        messagebox.showinfo("Completed", f"Processing completed, file saved to: {save_path}")

    except Exception as e:
        messagebox.showerror("错误", str(e))
        logger.error(e, exc_info=True)
        raise e


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


def _request(method, url, headers=None, files=None, data=None, params=None, auth=None, cookies=None, hooks=None, json=None, logger=get_logger(), highlight_error=False):
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


# 执行处理函数
def start_processing(my_app):
    try:
        entry_guc_url = my_app.entry_guc_url.get()
        entry_es_url = my_app.entry_es_url.get()
        client_id = my_app.entry_client_id.get()
        client_secret = my_app.entry_client_secret.get()
        excel_file = my_app.entry_a.get()
        save_path = my_app.entry_save.get()

        if not (entry_guc_url and entry_es_url and client_id and client_secret and excel_file and save_path):
            messagebox.showerror("Error", "Please completed all fields.")
            return

        token = get_token(entry_guc_url, client_id, client_secret, scope='ErrorServiceApi', logger=my_app.logger)
        my_app.logger.info(token)

        async_call(process_excel_files, entry_es_url, token, excel_file, save_path, my_app.logger)
    except Exception as e:
        my_app.logger.error(e)
        messagebox.showerror("Error", str(e))
        raise e
    return


class MyApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.log_handler = None
        self.logger = get_logger()
        self.logger.setLevel(logging.DEBUG)
        self.tasks = list()

        def _async_call(func, *args, **kwargs):
            # self.register_button.config(text="Running", state=tk.DISABLED)
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
        self.title("Error Service Checker")
        # self.geometry("400x200")

        left_frame = tk.Frame(self)
        left_frame.grid(row=0, column=0, sticky="nsew")

        right_frame = tk.Frame(self)
        right_frame.grid(row=0, column=1, sticky="nsew")

        # 配置行和列，使其随窗口大小调整
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=0)  # 左框架不自适应大小
        self.grid_columnconfigure(1, weight=1)

        def create_label_entry(frame, name, default="", width=40, row=0, column=0):
            label = tk.Label(frame, text=name)
            label.grid(row=row, column=0, padx=2, pady=2, sticky='e')
            entry = tk.Entry(frame, width=width)
            entry.config(textvariable=tk.StringVar(value=default), font=("Consolas", 9))
            entry.grid(row=row, column=1, padx=2, pady=2, sticky='w')
            return entry

        def create_label_text(frame, name, default="", width=40, row=0, column=0):
            label = tk.Label(frame, text=name)
            label.grid(row=row, column=0, padx=2, pady=2, sticky='e')
            text = tk.Text(frame, width=width, height=3)
            text.config(font=("Consolas", 9))
            text.insert(tk.END, default)
            text.grid(row=row, column=1, padx=2, pady=2, sticky='w')
            return text

        # 选择文件函数
        def select_file(entry):
            file_paths = filedialog.askopenfilenames(filetypes=[("Excel Files", "*.xlsx *.xls")])
            entry.delete(0, tk.END)
            file_paths = "|".join(file_paths)
            entry.insert(0, file_paths)

        # 选择保存路径函数
        def select_save_path(entry):
            save_path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel Files", "*.xlsx")])
            entry.delete(0, tk.END)
            entry.insert(0, save_path)

        i = 0

        self.entry_guc_url = create_label_entry(left_frame, name="GUC URL", default="https://dev6-guc.globetools.com", width=50, row=i)
        i += 1

        self.entry_es_url = create_label_entry(left_frame, name="Error Service URL", default="https://dev6-cantondeviis.globetools.com:5028", width=50, row=i)
        i += 1

        self.entry_client_id = create_label_entry(left_frame, name="Client ID", default="A3SService", width=50, row=i)
        i += 1

        self.entry_client_secret = create_label_entry(left_frame, name="Client Secret", default="BD2F91CB-6DCD-4BB1-82EE-5951C4753EBE", width=50, row=i)
        i += 1

        # A 表选择框
        tk.Label(left_frame, text="Error list Excel").grid(row=i, column=0, padx=2, pady=2, sticky='e')
        self.entry_a = tk.Entry(left_frame, width=50)
        self.entry_a.grid(row=i, column=1, padx=2, pady=2, sticky='w')
        button_a = tk.Button(left_frame, text="Browse", command=lambda: select_file(self.entry_a))
        button_a.grid(row=i, column=2, padx=2, pady=2)
        i += 1

        # 保存路径选择框
        tk.Label(left_frame, text="Result save as").grid(row=i, column=0, padx=2, pady=2, sticky='e')
        self.entry_save = tk.Entry(left_frame, width=50)
        self.entry_save.grid(row=i, column=1, padx=2, pady=2, sticky='w')
        button_save = tk.Button(left_frame, text="Browse", command=lambda: select_save_path(self.entry_save))
        button_save.grid(row=i, column=2, padx=2, pady=2)
        i += 1

        # 开始处理按钮
        button_start = tk.Button(left_frame, text="Start Test", command=lambda: async_call(start_processing, self))
        button_start.grid(row=i, column=0, columnspan=3, pady=20)

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
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(self.log_handler)

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
