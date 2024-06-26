import logging
import tkinter as tk


def get_logger(logger_name=__name__):
    # 创建日志记录器
    logger = logging.getLogger(logger_name)

    # 避免重复添加处理器
    if not logger.hasHandlers():
        # 设置日志记录器的日志级别
        logger.setLevel(logging.DEBUG)

        # 创建控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)

        # 创建日志格式器
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s: %(message)s')

        # 设置格式器到控制台处理器
        console_handler.setFormatter(formatter)

        # 将控制台处理器添加到日志记录器
        logger.addHandler(console_handler)

    return logger


class TextHandler(logging.Handler):
    def __init__(self, widget):
        super().__init__()
        self.widget = widget

    def emit(self, record):
        msg = self.format(record)
        self.widget.configure(state='normal')
        self.widget.insert(tk.END, msg + '\n')
        self.widget.configure(state='disabled')
        self.widget.yview(tk.END)
