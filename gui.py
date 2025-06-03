import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pytz
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from utils import (
    pick_datetime_with_default, get_switchable_cols, get_sensor_cols, state_color
)
import datetime

class SensorPicker(tk.Tk):
    def __init__(self, df, time_col):
        super().__init__()
        self.title("感測器/狀態軸 勾選＋滑鼠X軸平移、Y軸縮放/移動＋下載")
        self.df_all = df.copy()
        self.time_col = time_col

        self.time_min = pd.Timestamp(df[time_col].min())
        self.time_max = pd.Timestamp(df[time_col].max())
        self.start_time = tk.StringVar(value=str(self.time_min)[:19])
        self.end_time = tk.StringVar(value=str(self.time_max)[:19])

        main_frame = tk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=1)

        # 側欄
        side_frame = tk.Frame(main_frame)
        side_frame.pack(side=tk.LEFT, fill=tk.Y, padx=8, pady=6)

        # 狀態開關單選
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

        # 下載按鈕（分開）
        csv_btn = tk.Button(side_frame, text="下載資料（CSV）", command=self.download_csv)
        csv_btn.pack(pady=(8,2), fill=tk.X)
        png_btn = tk.Button(side_frame, text="下載圖檔（PNG）", command=self.download_png)
        png_btn.pack(pady=(0,8), fill=tk.X)

        # 搜尋、主副軸、多選
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

        # 感測器/狀態元件管理
        self.switch_all = get_switchable_cols(df)
        self.sensor_all = get_sensor_cols(df)
        self.vars_main = {}
        self.vars_aux = {}
        self.status_radio_var = tk.StringVar()
        self.refresh_panel()

        self.start_time.trace_add("write", lambda *_: self.update_plot())
        self.end_time.trace_add("write", lambda *_: self.update_plot())

        # 主圖表
        self.fig, self.ax = plt.subplots(figsize=(11, 8))
        self.canvas_plot = FigureCanvasTkAgg(self.fig, master=main_frame)
        self.toolbar = NavigationToolbar2Tk(self.canvas_plot, main_frame)
        self.toolbar.update()
        self.canvas_plot.get_tk_widget().pack(side=tk.RIGHT, fill=tk.BOTH, expand=1)

        # --- 滑鼠平移/縮放支援 ---
        self._dragging = False
        self._drag_start_x = None
        self._drag_start_t0 = None
        self._drag_start_t1 = None
        self._y_drag = False
        self._y_drag_start = None
        self._y_lim_start = None
        self.fig.canvas.mpl_connect("button_press_event", self.on_press)
        self.fig.canvas.mpl_connect("motion_notify_event", self.on_motion)
        self.fig.canvas.mpl_connect("button_release_event", self.on_release)
        self.fig.canvas.mpl_connect("scroll_event", self.on_scroll)

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
            current = pd.Timestamp(self.start_time.get())
        except Exception:
            current = self.time_min
        dt = pick_datetime_with_default("選擇起始時間", current)
        if dt:
            self.start_time.set(dt.strftime("%Y-%m-%d %H:%M:%S"))
            self.update_plot()

    def pick_end_time(self):
        try:
            current = pd.Timestamp(self.end_time.get())
        except Exception:
            current = self.time_max
        dt = pick_datetime_with_default("選擇結束時間", current)
        if dt:
            self.end_time.set(dt.strftime("%Y-%m-%d %H:%M:%S"))
            self.update_plot()

    # --- 滑鼠平移/縮放功能 ---
    def on_press(self, event):
        if event.button == 1 and event.inaxes == self.ax:
            self._dragging = True
            self._drag_start_x = event.xdata
            self._drag_start_t0 = pd.Timestamp(self.start_time.get())
            self._drag_start_t1 = pd.Timestamp(self.end_time.get())
        elif event.button in [2, 3] and event.inaxes == self.ax:  # 中鍵/右鍵
            self._y_drag = True
            self._y_drag_start = event.y
            self._y_lim_start = self.ax.get_ylim()

    def on_motion(self, event):
        # X軸平移
        if self._dragging and event.inaxes == self.ax and event.xdata is not None and self._drag_start_x is not None:
            offset = self._drag_start_x - event.xdata  # 方向顛倒
            offset_s = offset * 24 * 60 * 60
            new_t0 = self._drag_start_t0 + pd.Timedelta(seconds=offset_s)
            new_t1 = self._drag_start_t1 + pd.Timedelta(seconds=offset_s)
            self.start_time.set(new_t0.strftime("%Y-%m-%d %H:%M:%S"))
            self.end_time.set(new_t1.strftime("%Y-%m-%d %H:%M:%S"))
            self.update_plot()
        # Y軸上下平移
        if self._y_drag and event.inaxes == self.ax and event.y is not None and self._y_drag_start is not None:
            y0, y1 = self._y_lim_start
            delta = event.y - self._y_drag_start
            pixel_to_data = (y1 - y0) / self.fig.bbox.height
            shift = delta * pixel_to_data
            self.ax.set_ylim(y0 + shift, y1 + shift)
            self.fig.tight_layout()
            self.canvas_plot.draw()

    def on_release(self, event):
        self._dragging = False
        self._drag_start_x = None
        self._y_drag = False
        self._y_drag_start = None
        self._y_lim_start = None

    def on_scroll(self, event):
        # Y軸縮放
        if event.inaxes != self.ax:
            return
        cur_ylim = self.ax.get_ylim()
        y_mouse = event.ydata
        if y_mouse is None:
            return
        scale_factor = 1.25 if event.button == 'up' else 0.8
        new_height = (cur_ylim[1] - cur_ylim[0]) * scale_factor
        y_center = y_mouse
        self.ax.set_ylim([y_center - new_height/2, y_center + new_height/2])
        self.fig.tight_layout()
        self.canvas_plot.draw()

    def download_csv(self):
        tz = pytz.timezone('Asia/Taipei')
        try:
            start = pd.Timestamp(self.start_time.get())
            if start.tzinfo is None:
                start = start.tz_localize(tz)
            end = pd.Timestamp(self.end_time.get())
            if end.tzinfo is None:
                end = end.tz_localize(tz)
        except Exception:
            messagebox.showerror("錯誤", "請正確輸入時間")
            return

        mask = (self.df_all[self.time_col] >= start) & (self.df_all[self.time_col] <= end)
        df = self.df_all.loc[mask]
        main_sensors = [s for s in self.sensor_all if self.vars_main.get(s, tk.BooleanVar()).get()]
        aux_sensors = [s for s in self.sensor_all if self.vars_aux.get(s, tk.BooleanVar()).get()]
        sensors = sorted(set(main_sensors + aux_sensors))
        switch_col = self.selected_status_var.get()
        cols = [self.time_col] + sensors
        if switch_col and switch_col not in cols:
            cols.append(switch_col)
        export_cols = [c for c in cols if c in df.columns]
        if df.empty or not export_cols:
            messagebox.showwarning("無資料", "此區段無資料可下載")
            return
        # 建議檔名
        timefmt = "%Y%m%d_%H%M%S"
        fname = f"sensor_{start.strftime(timefmt)}_{end.strftime(timefmt)}.csv"
        fpath = filedialog.asksaveasfilename(
            title="儲存資料為CSV",
            defaultextension=".csv",
            initialfile=fname,
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
        )
        if fpath:
            try:
                df[export_cols].to_csv(fpath, index=False, encoding="utf-8-sig")
            except Exception as e:
                messagebox.showerror("CSV儲存錯誤", str(e))

    def download_png(self):
        tz = pytz.timezone('Asia/Taipei')
        try:
            start = pd.Timestamp(self.start_time.get())
            if start.tzinfo is None:
                start = start.tz_localize(tz)
            end = pd.Timestamp(self.end_time.get())
            if end.tzinfo is None:
                end = end.tz_localize(tz)
        except Exception:
            messagebox.showerror("錯誤", "請正確輸入時間")
            return
        timefmt = "%Y%m%d_%H%M%S"
        fname = f"plot_{start.strftime(timefmt)}_{end.strftime(timefmt)}.png"
        img_path = filedialog.asksaveasfilename(
            title="儲存目前圖表為PNG",
            defaultextension=".png",
            initialfile=fname,
            filetypes=[("PNG Images", "*.png"), ("All Files", "*.*")]
        )
        if img_path:
            try:
                self.fig.savefig(img_path, dpi=180, bbox_inches='tight', transparent=False)
            except Exception as e:
                messagebox.showerror("圖表儲存錯誤", str(e))

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
