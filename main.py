from font_config import set_chinese_font
from gui import SensorPicker
from utils import pick_file # 保留 pick_file，因為 gui.py 會用到
import pandas as pd
import customtkinter as ctk
from tkinter import messagebox
import sys

def main():
    set_chinese_font()
    app = SensorPicker() # 直接初始化 SensorPicker，不傳入 df 和 time_col
    app.mainloop()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        root = ctk.CTk() 
        root.withdraw()
        messagebox.showerror("執行時錯誤", str(e))
        sys.exit(1)