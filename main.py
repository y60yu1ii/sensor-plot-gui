<![CDATA[from font_config import set_chinese_font
from gui import SensorPicker
from utils import pick_file # 保留 pick_file，因為 gui.py 會用到
import pandas as pd
import customtkinter as ctk
from tkinter import messagebox
import sys

def main():
    set_chinese_font()
    # 移除檔案選擇和讀取 CSV 的部分
    # file_path = pick_file()
    # df = pd.read_csv(file_path)
    # if 'Timestamp' in df.columns:
    #     df['Timestamp'] = pd.to_datetime(df['Timestamp'], unit='s', errors='coerce', utc=True)
    #     df['Timestamp'] = df['Timestamp'].dt.tz_convert('Asia/Taipei')
    #     df = df.sort_values('Timestamp')
    #     time_col = 'Timestamp'
    # elif 'Date' in df.columns and 'Time' in df.columns:
    #     df['Datetime'] = pd.to_datetime(df['Date'] + ' ' + df['Time'], errors='coerce')
    #     df['Datetime'] = df['Datetime'].dt.tz_localize('Asia/Taipei')
    #     df = df.sort_values('Datetime')
    #     time_col = 'Datetime'
    # else:
    #     raise Exception("CSV 沒有 Timestamp 或 Date/Time 欄")
    app = SensorPicker() # 直接初始化 SensorPicker，不傳入 df 和 time_col
    app.mainloop()

if __name__ == "__main__":
    try:
        # CustomTkinter 預設自動暗黑/亮色，無需自己設 theme
        main()
    except Exception as e:
        # CustomTkinter 也能和 tkinter 的 messagebox 共用
        root = ctk.CTk()  # 這裡用 ctk.CTk()
        root.withdraw()
        messagebox.showerror("執行時錯誤", str(e))
        sys.exit(1)
]]>
