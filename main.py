from font_config import set_chinese_font
from gui import SensorPicker
from utils import pick_file
import pandas as pd
import tkinter as tk
from tkinter import messagebox
import sys

def main():
    set_chinese_font()
    file_path = pick_file()
    df = pd.read_csv(file_path)
    if 'Timestamp' in df.columns:
        df['Timestamp'] = pd.to_datetime(df['Timestamp'], unit='s', errors='coerce', utc=True)
        df['Timestamp'] = df['Timestamp'].dt.tz_convert('Asia/Taipei')
        df = df.sort_values('Timestamp')
        time_col = 'Timestamp'
    elif 'Date' in df.columns and 'Time' in df.columns:
        df['Datetime'] = pd.to_datetime(df['Date'] + ' ' + df['Time'], errors='coerce')
        df['Datetime'] = df['Datetime'].dt.tz_localize('Asia/Taipei')
        df = df.sort_values('Datetime')
        time_col = 'Datetime'
    else:
        raise Exception("CSV 沒有 Timestamp 或 Date/Time 欄")
    app = SensorPicker(df, time_col)
    app.mainloop()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # 彈出錯誤視窗，不會閃退
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("執行時錯誤", str(e))
        sys.exit(1)