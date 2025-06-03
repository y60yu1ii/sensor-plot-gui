import matplotlib
from matplotlib import font_manager
import platform

# 中文字型自動設定
font_candidates = [
    "Microsoft JhengHei", "Noto Sans CJK TC", "Noto Sans TC",
    "Heiti TC", "STHeiti", "PingFang TC", "Arial Unicode MS",
]
font_found = False
for font in font_candidates:
    if any(font in f.name for f in font_manager.fontManager.ttflist):
        matplotlib.rc('font', family=font)
        font_found = True
        print(f"使用字型: {font}")
        break
if not font_found:
    print("⚠️ 找不到常見中文字型，請安裝 Noto Sans CJK 或 Microsoft JhengHei。")
matplotlib.rcParams['axes.unicode_minus'] = False

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.widgets import RangeSlider
import tkinter as tk
from tkinter import filedialog, ttk
from tkcalendar import Calendar
from datetime import datetime
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
import pytz

def pick_file():
    root = tk.Tk()
    root.withdraw()
    file_path = filedialog.askopenfilename(
        title="選擇 CSV 檔案",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
    )
    root.destroy()
    if not file_path:
        raise Exception("未選擇檔案")
    return file_path

def pick_datetime_with_default(title="選擇日期時間", default_dt=None):
    top = tk.Toplevel()
    top.title(title)
    cal = Calendar(top, selectmode='day', date_pattern='yyyy-mm-dd')
    if default_dt:
        cal.set_date(default_dt.strftime("%Y-%m-%d"))
    cal.pack(padx=10, pady=10)
    frm = tk.Frame(top)
    frm.pack(pady=5)
    tk.Label(frm, text="時:").grid(row=0, column=0)
    hour_var = tk.StringVar(value=f"{default_dt.hour:02d}" if default_dt else "00")
    tk.Entry(frm, textvariable=hour_var, width=3).grid(row=0, column=1)
    tk.Label(frm, text="分:").grid(row=0, column=2)
    min_var = tk.StringVar(value=f"{default_dt.minute:02d}" if default_dt else "00")
    tk.Entry(frm, textvariable=min_var, width=3).grid(row=0, column=3)
    tk.Label(frm, text="秒:").grid(row=0, column=4)
    sec_var = tk.StringVar(value=f"{default_dt.second:02d}" if default_dt else "00")
    tk.Entry(frm, textvariable=sec_var, width=3).grid(row=0, column=5)
    result = {}
    def ok():
        try:
            dt_str = cal.get_date() + f" {hour_var.get()}:{min_var.get()}:{sec_var.get()}"
            dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
            result['datetime'] = dt
            top.destroy()
        except Exception as e:
            tk.messagebox.showerror("格式錯誤", str(e))
    tk.Button(top, text="確定", command=ok).pack(pady=10)
    top.wait_window()
    return result.get('datetime')

def get_switchable_cols(df):
    return [col for col in df.columns if col.startswith(('av-', 'p-', 'b-'))]

def get_sensor_cols(df):
    return [col for col in df.columns if col not in ('ID', 'Timestamp', 'Date', 'Time', 'Datetime') and not col.startswith(('av-', 'p-', 'b-'))]

def state_color(state):
    mapping = {
        '00': '#e6e6e6', '01': '#b3ffd9', '10': '#99cfff', '11': '#ffb3b3',
        '0000': '#f0f0f0', '1000': '#a6e3e9', '1001': '#ffd6a5', '0100': '#caf7e3',
        '0001': '#c2f784', '0010': '#d3bfff', '0011': '#fff5ba'
    }
    return mapping.get(str(state), '#f6ffed')

class SensorPicker(tk.Tk):
    def __init__(self, df, time_col):
        super().__init__()
        self.title("感測器/狀態軸 勾選與即時畫圖＋可互動影片時間軸")
        self.df_all = df.copy()
        self.time_col = time_col

        self.time_min = pd.Timestamp(df[time_col].min())
        self.time_max = pd.Timestamp(df[time_col].max())
        self.start_time = tk.StringVar(value=str(self.time_min)[:19])
        self.end_time = tk.StringVar(value=str(self.time_max)[:19])

        main_frame = tk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=1)

        # 選擇欄
        side_frame = tk.Frame(main_frame)
        side_frame.pack(side=tk.LEFT, fill=tk.Y, padx=8, pady=6)

        selected_status_frame = tk.Frame(side_frame)
        selected_status_frame.pack(fill=tk.X)
        tk.Label(selected_status_frame, text="已選狀態開關", fg='purple').pack(anchor='w')
        self.selected_status_var = tk.StringVar()
        self.selected_status_label = tk.Label(selected_status_frame, text="", fg="red")
        self.selected_status_label.pack(anchor='w')
        self.clear_status_btn = tk.Button(selected_status_frame, text="移除", command=self.clear_status)
        self.clear_status_btn.pack(anchor='w')

        # 時間區段
        time_frame = tk.Frame(side_frame)
        time_frame.pack(fill=tk.X, pady=(8,0))
        tk.Label(time_frame, text="起始時間：").pack(side=tk.LEFT)
        self.start_entry = tk.Entry(time_frame, textvariable=self.start_time, width=20)
        self.start_entry.pack(side=tk.LEFT)
        tk.Button(time_frame, text="📅", command=self.pick_start_time).pack(side=tk.LEFT, padx=(0,8))
        tk.Label(time_frame, text="結束時間：").pack(side=tk.LEFT)
        self.end_entry = tk.Entry(time_frame, textvariable=self.end_time, width=20)
        self.end_entry.pack(side=tk.LEFT)
        tk.Button(time_frame, text="📅", command=self.pick_end_time).pack(side=tk.LEFT)

        # 搜尋與選欄
        panel_label = tk.Label(side_frame, text="搜尋/勾選感測器、開關：", fg='blue')
        panel_label.pack(anchor='w', pady=(8,0))
        self.search_var = tk.StringVar()
        self.search_var.trace_add('write', self.refresh_panel)
        search_entry = tk.Entry(side_frame, textvariable=self.search_var)
        search_entry.pack(fill=tk.X, padx=0, pady=2)
        scroll_outer = tk.Frame(side_frame)
        scroll_outer.pack(fill=tk.BOTH, expand=1, padx=0, pady=4)
        self.canvas = tk.Canvas(scroll_outer, width=330, height=540)
        scrollbar = ttk.Scrollbar(scroll_outer, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas)
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 感測器/狀態欄狀態
        self.switch_all = get_switchable_cols(df)
        self.sensor_all = get_sensor_cols(df)
        self.vars_main = {}
        self.vars_aux = {}
        self.status_radio_var = tk.StringVar()
        self.refresh_panel()

        self.start_time.trace_add("write", lambda *_: self.sync_slider_from_entry())
        self.end_time.trace_add("write", lambda *_: self.sync_slider_from_entry())

        # 主圖 + slider 軸
        self.fig, (self.ax, self.ax_slider) = plt.subplots(
            2, 1, figsize=(11, 8), gridspec_kw={'height_ratios': [12,1]}
        )
        plt.subplots_adjust(hspace=0.24)
        self.canvas_plot = FigureCanvasTkAgg(self.fig, master=main_frame)
        self.canvas_plot.get_tk_widget().pack(side=tk.RIGHT, fill=tk.BOTH, expand=1)

        # slider 初始化
        t0 = self.time_min.value // 10**9
        t1 = self.time_max.value // 10**9
        self.slider = RangeSlider(
            self.ax_slider, "時間區間", t0, t1, valinit=(t0, t1),
            valstep=1, orientation='horizontal'
        )
        self.ax_slider.set_yticks([])
        self.ax_slider.set_xticks([])
        self.ax_slider.set_frame_on(False)
        self.ax_slider.set_position([0.1, 0.05, 0.8, 0.1])

        self.slider.on_changed(self.on_slider_change)
        self._slider_updating = False

        self.update_plot()

    def refresh_panel(self, *args):
        search_key = self.search_var.get().strip().lower()
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        tk.Label(self.scrollable_frame, text="狀態開關 (單選)", fg='purple').pack(anchor='w')
        for col in self.switch_all:
            if not search_key or search_key in col.lower():
                rb = tk.Radiobutton(self.scrollable_frame, text=col, variable=self.status_radio_var, value=col, command=self.set_status)
                rb.pack(anchor='w')
        tk.Label(self.scrollable_frame, text="主軸感測器", fg='blue').pack(anchor='w', pady=(10,0))
        for sensor in self.sensor_all:
            if not search_key or search_key in sensor.lower():
                if sensor not in self.vars_main:
                    self.vars_main[sensor] = tk.BooleanVar()
                chk = tk.Checkbutton(self.scrollable_frame, text=sensor, variable=self.vars_main[sensor], command=self.update_plot)
                chk.pack(anchor='w')
        tk.Label(self.scrollable_frame, text="副軸感測器", fg='green').pack(anchor='w', pady=(10,0))
        for sensor in self.sensor_all:
            if not search_key or search_key in sensor.lower():
                if sensor not in self.vars_aux:
                    self.vars_aux[sensor] = tk.BooleanVar()
                chk = tk.Checkbutton(self.scrollable_frame, text=sensor, variable=self.vars_aux[sensor], command=self.update_plot)
                chk.pack(anchor='w')
        self.update_status_label()

    def set_status(self):
        col = self.status_radio_var.get()
        self.selected_status_var.set(col)
        self.update_status_label()
        self.update_plot()

    def clear_status(self):
        self.status_radio_var.set('')
        self.selected_status_var.set('')
        self.update_status_label()
        self.update_plot()

    def update_status_label(self):
        val = self.selected_status_var.get()
        if val:
            self.selected_status_label.config(text=f"{val}")
            self.clear_status_btn.config(state=tk.NORMAL)
        else:
            self.selected_status_label.config(text="")
            self.clear_status_btn.config(state=tk.DISABLED)

    def pick_start_time(self):
        try:
            current = datetime.fromisoformat(self.start_time.get())
        except Exception:
            current = self.time_min
        dt = pick_datetime_with_default("選擇起始時間", current)
        if dt:
            self.start_time.set(dt.strftime("%Y-%m-%d %H:%M:%S"))
            self.sync_slider_from_entry()

    def pick_end_time(self):
        try:
            current = datetime.fromisoformat(self.end_time.get())
        except Exception:
            current = self.time_max
        dt = pick_datetime_with_default("選擇結束時間", current)
        if dt:
            self.end_time.set(dt.strftime("%Y-%m-%d %H:%M:%S"))
            self.sync_slider_from_entry()

    def sync_slider_from_entry(self):
        # 只要 entry 有改動就同步 RangeSlider
        try:
            t0 = pd.Timestamp(self.start_time.get()).value // 10**9
            t1 = pd.Timestamp(self.end_time.get()).value // 10**9
            if hasattr(self, "slider"):
                self._slider_updating = True
                self.slider.set_val((t0, t1))
                self._slider_updating = False
                self.update_plot()
        except Exception as e:
            pass

    def on_slider_change(self, val):
        if getattr(self, "_slider_updating", False):
            return
        vmin, vmax = val
        tmin = pd.to_datetime(int(vmin), unit='s', utc=True).tz_convert('Asia/Taipei')
        tmax = pd.to_datetime(int(vmax), unit='s', utc=True).tz_convert('Asia/Taipei')
        self.start_time.set(tmin.strftime("%Y-%m-%d %H:%M:%S"))
        self.end_time.set(tmax.strftime("%Y-%m-%d %H:%M:%S"))
        self.update_plot()

    def update_plot(self):
        self.ax.clear()
        tz = pytz.timezone('Asia/Taipei')
        try:
            start = pd.Timestamp(self.start_time.get())
            if start.tzinfo is None:
                start = start.tz_localize(tz)
            end = pd.Timestamp(self.end_time.get())
            if end.tzinfo is None:
                end = end.tz_localize(tz)
        except Exception:
            self.ax.set_title('請正確輸入時間')
            self.fig.tight_layout()
            self.canvas_plot.draw()
            return

        mask = (self.df_all[self.time_col] >= start) & (self.df_all[self.time_col] <= end)
        df = self.df_all.loc[mask]
        main_sensors = [s for s in self.sensor_all if self.vars_main.get(s, tk.BooleanVar()).get()]
        aux_sensors = [s for s in self.sensor_all if self.vars_aux.get(s, tk.BooleanVar()).get()]

        handles = []
        switch_col = self.selected_status_var.get()
        if switch_col and switch_col in df.columns and not df.empty:
            times = df[self.time_col].values
            status = df[switch_col].astype(str).values
            seg_start = times[0]
            seg_val = status[0]
            for i in range(1, len(times)):
                if status[i] != seg_val or i == len(times)-1:
                    seg_end = times[i] if status[i] != seg_val else times[i]+np.timedelta64(1,'s')
                    self.ax.axvspan(pd.to_datetime(seg_start), pd.to_datetime(seg_end),
                                    facecolor=state_color(seg_val), alpha=0.28)
                    seg_start = times[i]
                    seg_val = status[i]
            for state_code in sorted(set(status)):
                handles.append(mpatches.Patch(color=state_color(state_code), label=f"{switch_col}={state_code}"))

        ymain_all = []
        if main_sensors and not df.empty:
            for sensor in main_sensors:
                y = pd.to_numeric(df[sensor], errors='coerce')
                ymain_all.append(y.values)
                line, = self.ax.plot(df[self.time_col], y, label=sensor)
                handles.append(line)
            ymain_all = np.concatenate([y[~np.isnan(y)] for y in ymain_all]) if ymain_all else np.array([])
            if aux_sensors and len(ymain_all) > 0:
                main_min, main_max = np.nanmin(ymain_all), np.nanmax(ymain_all)
                ycenter = (main_min + main_max) / 2
                yquarter = (main_max - main_min) / 8
                for sensor in aux_sensors:
                    y_orig = pd.to_numeric(df[sensor], errors='coerce').values
                    aux_mean = np.nanmean(y_orig)
                    aux_diff = y_orig - aux_mean
                    if np.nanmax(np.abs(aux_diff)) > 0:
                        y_scaled = ycenter + aux_diff * yquarter / np.nanmax(np.abs(aux_diff))
                    else:
                        y_scaled = np.full_like(y_orig, ycenter)
                    line, = self.ax.plot(df[self.time_col], y_scaled, 
                        label=f"{sensor} (副軸標準化)", linestyle="--")
                    handles.append(line)
        else:
            for v in self.vars_aux.values():
                v.set(False)
            self.ax.set_title('請至少勾選一個主軸感測器')
            self.fig.tight_layout()
            self.canvas_plot.draw()
            return

        if df.empty:
            self.ax.set_title('此時間段沒有資料')
        self.ax.set_xlabel('時間')
        self.ax.set_ylabel('數值')
        self.ax.legend(handles=handles, loc='upper left', fontsize=8)
        self.ax.relim()
        self.ax.autoscale_view()
        self.fig.tight_layout()
        self.canvas_plot.draw()

def main():
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
    main()
