import requests
import tkinter as tk
import logging
import io
import threading
import uuid
import json
import math
import pandas as pd
from urllib import parse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from logger_config import get_logger, TextHandler
from tkinter import filedialog, messagebox, scrolledtext


def get_token(domain, client_id, client_secret, scope="", logger=get_logger()):
    url = f"{domain}/connect/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    payload_dict = {"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret,
                    "scope": scope}
    payload = parse.urlencode(payload_dict)
    r = _request("POST", url=url, headers=headers, data=payload, logger=logger)
    r_json = r.json()
    return f'{r_json["token_type"]} {r_json["access_token"]}'


BMS_sub_error_component = ('BMSWarnings', 'BMSErrors', 'BMSFatalErrors')


def normalize_newlines(text):
    return text.replace("\r\n", "\n").replace("\r", "\n")


def check_mandatory_field(field):
    if field is None or field == '':
        return False
    elif isinstance(field, float) and math.isnan(field):
        return False
    else:
        return True


def check_error_return(row, domain, access_token, sub_error_dict, logger=get_logger()):
    result = {"result": "Pass", "detail": ""}

    for _ in ['product', 'model number', 'language', 'error code']:
        if not check_mandatory_field(row[_]):
            logger.error(f'Missing required field [{_}] in \n[{row}]\nPlease check your error code excel')
            result["result"] = f'Error'
            result["detail"] = f'Missing required field [{_}]'
            return result
    try:
        product = row['product']
        model = row['model number']
        if isinstance(model, float):  # 处理纯数字的model number
            if math.isnan(model):
                model = ""
            else:
                model = (int(model))
        model = str(model)
        language = row['language']
        component = row['component']
        datapoint_component = row['datapoint_component']
        error_code = row['error code']
        fault_code = row['fault code']
        content = row['content']
        suggestion = row['suggestion']
        error_level = row['error level']
        error_category = row['error category']
        if isinstance(error_category, float):  # 处理没有值的error category
            if math.isnan(error_category):
                error_category = ""
        version = row['version']
        sub_error = None if row['is sub'] == 0 else row['is sub']
        _format = row['format']
        if _format == "Bin" and not sub_error:  # 处理Bin格式的主error code
            error_code = 2 ** int(error_code)
    except KeyError as e:
        logger.error(e, exc_info=True)
        logger.error(f'An error occurred while checking \n[{row}]\nError is {e}')
        result["result"] = f'Error'
        result["detail"] = f'Cannot load data from column [{str(e).replace('KeyError: ', '')}]'
        return result

    def call_check_error_codes(row, domain, access_token, sub_error_dict, product, model, language, component,
                               datapoint_component, error_code, fault_code, content, suggestion, error_level,
                               error_category, version, sub_error, _format, logger):
        return check_error_codes(row, domain, access_token, sub_error_dict, product, model, language, component,
                                 datapoint_component, error_code, fault_code, content, suggestion, error_level,
                                 error_category, version, sub_error, _format, logger)

    def call_check_error_descriptions(domain, access_token, product, model, language, datapoint_component, error_code,
                                      fault_code, content, suggestion, sub_error, _format, logger):
        return check_error_descriptions(domain, access_token, product, model, language, datapoint_component, error_code,
                                        fault_code, content, suggestion, sub_error, _format, logger)

    # 用 ThreadPoolExecutor 调用两个方法并等待返回
    with ThreadPoolExecutor(max_workers=2) as executor:
        future1 = executor.submit(call_check_error_codes, row, domain, access_token, sub_error_dict, product, model,
                                  language,
                                  component, datapoint_component, error_code, fault_code, content, suggestion,
                                  error_level,
                                  error_category, version, sub_error, _format, get_logger())
        future2 = executor.submit(call_check_error_descriptions, domain, access_token, product, model, language,
                                  datapoint_component, error_code, fault_code, content, suggestion, sub_error, _format,
                                  get_logger())

        # 获取结果
        error_codes_result = future1.result()
        error_descriptions_result = future2.result()

    if error_codes_result["result"] == 'Error' or error_descriptions_result["result"] == 'Error':
        result["result"] = 'Error'
        result["detail"] = 'Please check the sub detail'
    elif error_codes_result["result"] == 'Failed' or error_descriptions_result["result"] == 'Failed':
        result["result"] = 'Failed'
        result["detail"] = 'Please check the sub detail'

    result["error_codes_detail"] = error_codes_result["detail"]
    result["error_descriptions_detail"] = error_descriptions_result["detail"]

    return result


def check_data(name, _result, expected, actual):
    if isinstance(expected, str) and isinstance(actual, str):
        expected = normalize_newlines(expected)
        actual = normalize_newlines(actual)
    matched = True
    list_matched = True
    if isinstance(expected, list) and isinstance(actual, list):
        expected_hashed = [frozenset(d.items()) if isinstance(d, dict) else d for d in expected]
        actual_hashed = [frozenset(d.items()) if isinstance(d, dict) else d for d in actual]
        list_matched = Counter(expected_hashed) == Counter(actual_hashed)
    elif isinstance(expected, float) and isinstance(actual, str):
        expected = '' if math.isnan(expected) else expected
        matched = expected == actual
    else:
        matched = expected == actual
    if not list_matched or not matched:
        _result["result"] = "Failed"
        _result["detail"] = f'{_result["detail"]}[{name}] -> expected: [{expected}], but got [{actual}]\n'


def check_error_codes(row, domain, access_token, sub_error_dict,
                      product,
                      model,
                      language,
                      component,
                      datapoint_component,
                      error_code,
                      fault_code,
                      content,
                      suggestion,
                      error_level,
                      error_category,
                      version,
                      sub_error,
                      _format,
                      logger=get_logger()):
    logger.info(f"Checking FaultCodeCategory/errorcodes API... {product=} {model=} {language=} {error_code=} {fault_code=}")
    result = {"result": "Pass", "detail": ""}
    url = f"{domain}/api/FaultCodeCategory/errorcodes"

    if datapoint_component not in BMS_sub_error_component:
        payload_dict = {
            "productCode": product,
            "modelNumber": model,
            "language": language,
            "errorCodes": [
                {
                    "datapointComponent": datapoint_component,
                    "code": str(error_code)
                }
            ]
        }
    else:
        if sub_error == 1:
            result["result"] = f'Ignore'
            result["detail"] = f'This is sub error, it will be verified on the main error.'
            return result
        payload_dict = {
            "productCode": product,
            "modelNumber": model,
            "language": language,
            "errorCodes": [
                {
                    "datapointComponent": "BatteryPackErrorCode",
                    "code": str(error_code)
                },
                {
                    "datapointComponent": datapoint_component,
                    "code": str(error_code)
                }
            ]
        }
        sub_error = sub_error_dict[
            f'{row["model number"]}_{row["datapoint_component"]}_{row["error code"]}_{row["language"]}']

    headers = {"Content-Type": "application/json", "Authorization": access_token}
    payload = json.dumps(payload_dict)
    r = requests.request("POST", url=url, headers=headers, data=payload)
    try:
        if r.status_code == 200:
            r_json = r.json()
            if not (r_json.get("data") and r_json.get("data").get("errorList")):
                msg = f'The response do not have "errorList" item\nResponse is {r.text}'
                result["result"] = f'Failed'
                result["detail"] = msg
                return result
        else:
            msg = f'Response code is {r.status_code}\nResponse is {r.text}'
            result["result"] = f'Failed'
            result["detail"] = msg
            return result

        if datapoint_component not in BMS_sub_error_component:
            _i = 0
        else:
            _i = 1
        check_data("component", result, component, r_json["data"]["errorList"][_i]["component"])
        check_data("dataPointComponent", result, datapoint_component,
                   r_json["data"]["errorList"][_i]["dataPointComponent"])
        check_data("faultCode", result, fault_code, r_json["data"]["errorList"][_i]["faultCode"])
        check_data("content", result, content, r_json["data"]["errorList"][_i]["content"])
        check_data("suggestion", result, suggestion, r_json["data"]["errorList"][_i]["suggestion"])
        check_data("error level", result, error_level, r_json["data"]["errorList"][_i]["level"])
        check_data("error category", result, error_category, r_json["data"]["errorList"][_i]["errorCategory"])
        check_data("version", result, version, r_json["data"]["errorList"][_i]["version"])
        check_data("sub error", result, sub_error, r_json["data"]["errorList"][_i]["subError"])
    except Exception as e:
        logger.error(e, exc_info=True)
        logger.error(
            f'An error occurred while checking {product=} {model=} {language=} {error_code=} {fault_code=}.\nError is {e}\nResponse is {r.text}')
        result["result"] = f'Error'
        result["detail"] = f'{result["detail"]}\nError is {e}\nResponse is {r.text}'

    return result


def check_error_descriptions(domain, access_token,
                             product,
                             model,
                             language,
                             datapoint_component,
                             error_code,
                             fault_code,
                             content,
                             suggestion,
                             sub_error,
                             _format,
                             logger=get_logger()):
    logger.info(f"Checking FaultCodeCategory/errorDescriptions API... {product=} {model=} {language=} {error_code=} {fault_code=}")
    result = {"result": "Pass", "detail": ""}
    url = f"{domain}/api/FaultCodeCategory/errorDescriptions"

    if datapoint_component in BMS_sub_error_component and sub_error == 1:
        result["result"] = f'Ignore'
        result["detail"] = f'This is sub error, it will be verified on the main error.'
        return result
    else:
        payload_dict = {
            "productCode": product,
            "modelNumber": model,
            "language": language,
            "faultCodes": [fault_code]
        }

    headers = {"Content-Type": "application/json", "Authorization": access_token}
    payload = json.dumps(payload_dict)
    r = requests.request("POST", url=url, headers=headers, data=payload)

    try:
        if r.status_code == 200:
            r_json = r.json()
            if not r_json.get("data"):
                msg = f'The response do not have "data" item\nResponse is {r.text}'
                result["result"] = f'Failed'
                result["detail"] = msg
                return result
        else:
            msg = f'Response code is {r.status_code}\nResponse is {r.text}'
            result["result"] = f'Failed'
            result["detail"] = msg
            return result

        _i = 0
        if datapoint_component == 'BMSWarnings':
            _i = 1
        elif datapoint_component == 'BMSErrors':
            _i = 2
        elif datapoint_component == 'BMSFatalErrors':
            _i = 3
        check_data("source fault code", result, fault_code, r_json["data"][_i]["sourceFaultCode"])
        check_data("fault code", result, fault_code, r_json["data"][_i]["faultCode"])
        check_data("content", result, content, r_json["data"][_i]["content"])
        check_data("suggestion", result, suggestion, r_json["data"][_i]["suggestion"])
    except Exception as e:
        logger.error(e, exc_info=True)
        logger.error(
            f'An error occurred while checking {product=} {model=} {language=} {error_code=} {fault_code=}.\nError is {e}\nResponse is {r.text}')
        result["result"] = f'Error'
        result["detail"] = f'{result["detail"]}\nError is {e}\nResponse is {r.text}'

    return result


def generate_rule_df(domain, token, df, logger=get_logger()):
    rule_df = df[df['is sub'] == 0]
    key_columns = ["product", "model number", "datapoint index", "component", "datapoint_component"]
    rule_df = rule_df[key_columns].drop_duplicates()

    # 多线程处理函数
    def process_row_with_closure(domain, token, key_columns, logger):  # 将额外参数封闭到函数内部，避免显式传递参数
        def inner(x):
            return check_fault_code_rule(x, domain, token, key_columns, logger)

        return inner

    # 使用 ThreadPoolExecutor 并行处理
    with ThreadPoolExecutor() as executor:
        process_row = process_row_with_closure(domain, token, key_columns, logger)
        results = list(executor.map(process_row, [row for _, row in rule_df.iterrows()]))

    # 确保 rule_df 的索引与 results 对齐
    rule_df = rule_df.reset_index(drop=True)
    rule_df[["result", "detail"]] = pd.DataFrame(results, columns=["result", "detail"])
    rule_df["fault code"] = "(check the fault coder rule)"  # 添加说明

    return rule_df


def check_fault_code_rule(row, domain, access_token, key_columns, logger=get_logger()):
    result = {"result": "Pass", "detail": ""}

    for _ in key_columns:
        if not check_mandatory_field(row[_]):
            logger.error(f'Missing required field [{_}] in \n[{row}]\nPlease check your error code excel')
            result["result"] = f'Error'
            result["detail"] = f'Missing required field [{_}]'
            return result

    product = row['product']
    model = row['model number']
    if isinstance(model, float):
        if math.isnan(model):
            model = ""
        else:
            model = int(model)
    model = str(model)
    datapoint = str(row['datapoint index'])
    component = row['component']
    datapoint_component = row['datapoint_component']

    logger.info(f"Checking FaultCodeRule/datapoints API... {product=} {model=}")
    url = f"{domain}/api/FaultCodeRule/datapoints"
    payload_dict = {
        product: [model]
    }

    headers = {"Content-Type": "application/json", "Authorization": access_token}
    payload = json.dumps(payload_dict)
    r = requests.request("POST", url=url, headers=headers, data=payload)

    try:
        if r.status_code == 200:
            r_json = r.json()
            if not (r_json.get("data") and r_json.get("data").get(product) and r_json.get("data").get(product).get(
                    model)):
                msg = f'The response do not have corresponding item\nResponse is {r.text}'
                result["result"] = f'Failed'
                result["detail"] = msg
                return result
        else:
            msg = f'Response code is {r.status_code}\nResponse is {r.text}'
            result["result"] = f'Failed'
            result["detail"] = msg
            return result

        datapoints_list = r_json["data"][product][model]
        datapoints_dict = {x["datapoint"]: x for x in datapoints_list}
        if datapoint in datapoints_dict:
            _ = datapoints_dict[datapoint]
            check_data(f"DP[{datapoint}]|[component]", result, component, _.get("component"))
            check_data(f"DP[{datapoint}]|[datapoint component]", result, datapoint_component, _.get("datapointComponent"))
        else:
            result["result"] = "Failed"
            result["detail"] = f'Missing information of datapoint [{datapoint}]'

    except Exception as e:
        logger.error(e, exc_info=True)
        logger.error(
            f'An error occurred while checking {product=} {model=}.\nError is {e}\nResponse is {r.text}')
        result["result"] = f'Error'
        result["detail"] = f'{result["detail"]}\nError is {e}\nResponse is {r.text}'

    return result


# 将数字转换为二进制形式，然后拆解为其二进制位对应的权值，例如11变为[8, 2, 1]
def decompose_to_powers_of_two(number):
    binary = bin(int(number))[2:]  # 转换为二进制并去掉 "0b"
    result = []
    for i, bit in enumerate(reversed(binary)):  # 从低位开始遍历
        if bit == '1':
            result.append(2 ** i)  # 计算对应权值
    return result[::-1]  # 翻转结果使其从大到小排列


def get_BMS_sub_error_dict(df) -> dict:
    filtered_df = df[(df['datapoint_component'].isin(BMS_sub_error_component)) & (df['is sub'] == 0)]
    result_dict = dict()
    for index, row in filtered_df.iterrows():
        sub_code_list = [str(x) for x in decompose_to_powers_of_two(row["error code"])]
        if '1' in sub_code_list:
            sub_code_list.append("SystemClock")
        sub_error_df = df[(df['model number'] == row["model number"]) &
                          (df['datapoint_component'] == row["datapoint_component"]) &
                          (df['language'] == row["language"]) &
                          (df['is sub'] == 1) &
                          (df['error code'].isin(sub_code_list))]
        sub_error_list = list()
        for index, sub_error_row in sub_error_df.iterrows():
            _ = {
                "faultCode": sub_error_row['fault code'],
                "content": sub_error_row['content'],
                "suggestion": '' if math.isnan(sub_error_row['suggestion']) else sub_error_row['suggestion'],
                "level": str(sub_error_row['error level']),
            }
            sub_error_list.append(_)
        result_dict[
            f'{row["model number"]}_{row["datapoint_component"]}_{row["error code"]}_{row["language"]}'] = sub_error_list
    return result_dict


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

        # 生成sub error dict
        sub_error_dict = get_BMS_sub_error_dict(df)

        # 逐行处理
        # df["result"] = df.apply(lambda x: check_error_return(domain, token, x['product'], x['model number'], x['component'], x['language'], x['error code'], x['fault code'], x['content'], x['suggestion'], logger=logger), axis=1)

        # 多线程处理函数
        def process_row_with_closure(domain, token, sub_error_dict, logger):  # 将额外参数封闭到函数内部，避免显式传递参数
            def inner(x):
                return check_error_return(x, domain, token, sub_error_dict, logger)

            return inner

        # 使用 ThreadPoolExecutor 并行处理
        with ThreadPoolExecutor() as executor:
            process_row = process_row_with_closure(domain, token, sub_error_dict, logger)
            results = list(executor.map(process_row, [row for _, row in df.iterrows()]))

        # 将结果分配回 DataFrame
        df[["result", "detail", "error codes detail", "error descriptions detail"]] = pd.DataFrame(results,
                                                                                                   columns=["result",
                                                                                                            "detail",
                                                                                                            "error_codes_detail",
                                                                                                            "error_descriptions_detail"])

        rule_df = generate_rule_df(domain, token, df, logger)
        df = pd.concat([df, rule_df], ignore_index=True)

        # 保存结果为 Excel 文件
        df.to_excel(save_path, index=False)

        # 统计结果
        result_counts = dict(Counter(item["result"] for item in results))
        messagebox.showinfo("Completed", f"Process completed, {result_counts}, result detail saved to: {save_path}")

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


def _request(method, url, headers=None, files=None, data=None, params=None, auth=None, cookies=None, hooks=None,
             json=None, logger=get_logger(), highlight_error=False):
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

        process_excel_files(entry_es_url, token, excel_file, save_path, my_app.logger)
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

        def async_call(func, *args, **kwargs):
            self.button_start.config(text="Running", state=tk.DISABLED)
            t = threading.Thread(target=func, args=args, kwargs=kwargs)
            self.tasks.append(t)
            t.daemon = True
            t.start()

        def check_task_status():
            i = 0
            while i < len(self.tasks):
                if not self.tasks[i].is_alive():
                    self.tasks.pop(i)
                    self.button_start.config(text="Start Test", state=tk.NORMAL)
                i += 1

        def loop_update():
            check_task_status()
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

        self.entry_guc_url = create_label_entry(left_frame, name="GUC URL", default="https://dev6-guc.globetools.com",
                                                width=50, row=i)
        i += 1

        self.entry_es_url = create_label_entry(left_frame, name="Error Service URL",
                                               default="https://dev6-cantondeviis.globetools.com:5028", width=50, row=i)
        i += 1

        self.entry_client_id = create_label_entry(left_frame, name="Client ID", default="A3SService", width=50, row=i)
        i += 1

        self.entry_client_secret = create_label_entry(left_frame, name="Client Secret",
                                                      default="7E11D61D-F3A4-11EC-A1DF-8C47BE2B163E", width=50, row=i)
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
        self.button_start = tk.Button(left_frame, text="Start Test", command=lambda: async_call(start_processing, self))
        self.button_start.grid(row=i, column=0, columnspan=3, pady=20)

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
