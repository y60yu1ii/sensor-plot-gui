import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import pytz
import customtkinter as ctk
from tkinter import ttk, filedialog, messagebox
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.patches as mpatches
from utils import (
    pick_datetime_with_default,
    get_switchable_cols,
    get_av_cols,
    get_sensor_cols,
    state_color,
    av_upscale,
)
import datetime

class SensorPicker(ctk.CTk):
    def __init__(self, df, time_col):
        super().__init__()
        self.title("感測器/狀態/AV 多選＋背景色＋legend＋Emoji顯示/勾選")
        self.df_all = df.copy()
        self.time_col = time_col

        self.time_min = pd.Timestamp(df[time_col].min())
        self.time_max = pd.Timestamp(df[time_col].max())
        self.start_time = ctk.StringVar(value=str(self.time_min)[:19])
        self.end_time = ctk.StringVar(value=str(self.time_max)[:19])

        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill=ctk.BOTH, expand=1)

        # 側邊選單
        side_frame = ctk.CTkFrame(main_frame)
        side_frame.pack(side=ctk.LEFT, fill=ctk.Y, padx=8, pady=6)

        # 時間區段
        time_frame = ctk.CTkFrame(side_frame)
        time_frame.pack(fill=ctk.X, pady=(8,0))
        ctk.CTkLabel(time_frame, text="起始時間：").pack(side=ctk.LEFT)
        self.start_entry = ctk.CTkEntry(time_frame, textvariable=self.start_time, width=140)
        self.start_entry.pack(side=ctk.LEFT)
        ctk.CTkButton(time_frame, text="📅", command=self.pick_start_time, width=36).pack(side=ctk.LEFT, padx=(0,8))
        ctk.CTkLabel(time_frame, text="結束時間：").pack(side=ctk.LEFT)
        self.end_entry = ctk.CTkEntry(time_frame, textvariable=self.end_time, width=140)
        self.end_entry.pack(side=ctk.LEFT)
        ctk.CTkButton(time_frame, text="📅", command=self.pick_end_time, width=36).pack(side=ctk.LEFT)

        # 下載按鈕
        ctk.CTkButton(side_frame, text="下載資料（CSV）", command=self.download_csv).pack(pady=(8,2), fill=ctk.X)
        ctk.CTkButton(side_frame, text="下載圖檔（PNG）", command=self.download_png).pack(pady=(0,8), fill=ctk.X)

        # 搜尋框
        ctk.CTkLabel(side_frame, text="搜尋/勾選/顯示：", text_color='blue').pack(anchor='w', pady=(8,0))
        self.search_var = ctk.StringVar()
        self.search_var.trace_add('write', self.refresh_panel)
        search_entry = ctk.CTkEntry(side_frame, textvariable=self.search_var)
        search_entry.pack(fill=ctk.X, padx=0, pady=2)
        scroll_outer = ctk.CTkFrame(side_frame)
        scroll_outer.pack(fill=ctk.BOTH, expand=1, padx=0, pady=4)
        import tkinter as tk
        self.canvas = tk.Canvas(scroll_outer, width=350, height=540)
        scrollbar = ttk.Scrollbar(scroll_outer, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ctk.CTkFrame(self.canvas)
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 欄位分類
        self.switch_all = get_switchable_cols(df)
        self.av_all = get_av_cols(df)
        self.sensor_all = get_sensor_cols(df)
        self.all_cols = self.switch_all + self.sensor_all + self.av_all
        self.vars_all = {}
        self.is_visible = {col: True for col in self.all_cols}
        self.refresh_panel()

        self.start_time.trace_add("write", lambda *_: self.update_plot())
        self.end_time.trace_add("write", lambda *_: self.update_plot())

        # 主圖表
        self.fig, self.ax = plt.subplots(figsize=(11, 8))
        self.canvas_plot = FigureCanvasTkAgg(self.fig, master=main_frame)
        self.toolbar = NavigationToolbar2Tk(self.canvas_plot, main_frame)
        self.toolbar.update()
        self.canvas_plot.get_tk_widget().pack(side=ctk.RIGHT, fill=ctk.BOTH, expand=1)

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
        # 上方：已勾選欄位（固定順序），有自己的 emoji 勾選＋emoji顯示
        selected_cols = [col for col in self.all_cols if self.vars_all.get(col, ctk.BooleanVar()).get()]
        if selected_cols:
            ctk.CTkLabel(self.scrollable_frame, text="已勾選 (可直接取消/隱藏)", text_color='purple').pack(anchor='w', pady=(4,2))
            for col in selected_cols:
                frm = ctk.CTkFrame(self.scrollable_frame, fg_color="transparent")
                frm.pack(anchor='w', fill=ctk.X, padx=0)
                # 勾選 emoji（點一下就是取消該欄位）
                checked = "✅"
                btn_check = ctk.CTkButton(frm, text=checked, width=28, command=lambda c=col: self.toggle_checked(c))
                btn_check.pack(side=ctk.LEFT, padx=(0,2))
                # 眼睛 emoji
                eye = "👁️" if self.is_visible.get(col, True) else "🙈"
                btn_eye = ctk.CTkButton(frm, text=eye, width=28, command=lambda c=col: self.toggle_visible(c))
                btn_eye.pack(side=ctk.LEFT, padx=(0,2))
                ctk.CTkLabel(frm, text=col, text_color="black").pack(side=ctk.LEFT)
        # 下方：全部清單（用 emoji 直接切換勾選/取消，與上方完全分離）
        ctk.CTkLabel(self.scrollable_frame, text="全部感測/AV/開關", text_color='blue').pack(anchor='w', pady=(8,0))
        for col in self.all_cols:
            if not search_key or search_key in col.lower():
                if col not in self.vars_all:
                    self.vars_all[col] = ctk.BooleanVar()
                frm = ctk.CTkFrame(self.scrollable_frame, fg_color="transparent")
                frm.pack(anchor='w', fill=ctk.X, padx=0)
                checked = "✅" if self.vars_all[col].get() else "⬜️"
                btn_check = ctk.CTkButton(frm, text=checked, width=28, command=lambda c=col: self.toggle_checked(c))
                btn_check.pack(side=ctk.LEFT, padx=(0,2))
                eye = "👁️" if self.is_visible.get(col, True) else "🙈"
                btn_eye = ctk.CTkButton(frm, text=eye, width=28, command=lambda c=col: self.toggle_visible(c))
                btn_eye.pack(side=ctk.LEFT, padx=(0,2))
                ctk.CTkLabel(frm, text=col, text_color="black").pack(side=ctk.LEFT)

    def toggle_visible(self, col):
        self.is_visible[col] = not self.is_visible.get(col, True)
        self.refresh_panel()
        self.update_plot()

    def toggle_checked(self, col):
        v = self.vars_all.get(col, None)
        if v:
            v.set(not v.get())
        self.refresh_panel()
        self.update_plot()

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

    def on_press(self, event):
        if event.button == 1 and event.inaxes == self.ax:
            self._dragging = True
            self._drag_start_x = event.xdata
            self._drag_start_t0 = pd.Timestamp(self.start_time.get())
            self._drag_start_t1 = pd.Timestamp(self.end_time.get())
        elif event.button in [2, 3] and event.inaxes == self.ax:
            self._y_drag = True
            self._y_drag_start = event.y
            self._y_lim_start = self.ax.get_ylim()

    def on_motion(self, event):
        if self._dragging and event.inaxes == self.ax and event.xdata is not None and self._drag_start_x is not None:
            offset = self._drag_start_x - event.xdata
            offset_s = offset * 24 * 60 * 60
            new_t0 = self._drag_start_t0 + pd.Timedelta(seconds=offset_s)
            new_t1 = self._drag_start_t1 + pd.Timedelta(seconds=offset_s)
            self.start_time.set(new_t0.strftime("%Y-%m-%d %H:%M:%S"))
            self.end_time.set(new_t1.strftime("%Y-%m-%d %H:%M:%S"))
            self.update_plot()
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
        selected_cols = [col for col, v in self.vars_all.items() if v.get()]
        if not selected_cols or df.empty:
            messagebox.showwarning("無資料", "此區段無資料可下載")
            return
        cols = [self.time_col] + selected_cols
        export_cols = [c for c in cols if c in df.columns]
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
        selected_cols = [col for col, v in self.vars_all.items() if v.get() and self.is_visible.get(col, True)]
        switch_cols = [col for col in selected_cols if col in self.switch_all]
        sensor_cols = [col for col in selected_cols if col in self.sensor_all]
        av_cols = [col for col in selected_cols if col in self.av_all]

        patch_handles = []
        for col in switch_cols:
            if col not in df.columns: continue
            times = df[self.time_col].values
            vals = df[col].astype(str).values
            seg_start = times[0]
            seg_val = vals[0]
            for i in range(1, len(times)):
                if vals[i] != seg_val or i == len(times)-1:
                    seg_end = times[i] if vals[i] != seg_val else times[i]+np.timedelta64(1,'s')
                    self.ax.axvspan(pd.to_datetime(seg_start), pd.to_datetime(seg_end),
                                    facecolor=state_color(seg_val), alpha=0.30)
                    seg_start = times[i]
                    seg_val = vals[i]
            for state_code in sorted(set(vals)):
                patch_handles.append(
                    mpatches.Patch(
                        color=state_color(state_code),
                        label=f"{col} = {state_code}"
                    )
                )

        ys_sensor = [pd.to_numeric(df[col], errors='coerce').values for col in sensor_cols]
        if ys_sensor:
            sensor_ranges = [np.nanmax(y)-np.nanmin(y) for y in ys_sensor]
            min_range = np.nanmin(sensor_ranges)
            min_idx = np.nanargmin(sensor_ranges)
            min_sensor_y = ys_sensor[min_idx]
            min_sensor_min = np.nanmin(min_sensor_y)
            min_sensor_max = np.nanmax(min_sensor_y)
        else:
            min_sensor_min = 0
            min_sensor_max = 1
        all_y = np.concatenate([y[~np.isnan(y)] for y in ys_sensor]) if ys_sensor else np.array([0,1])
        global_min, global_max = np.nanmin(all_y), np.nanmax(all_y)
        if global_max - global_min < 1e-8:
            global_max = global_min + 1
        def minrange_downscale(y, min_v, max_v):
            norm = (y - min_v) / (max_v - min_v + 1e-12)
            return norm - 0.5
        ys_sensor_scaled = []
        for i, y in enumerate(ys_sensor):
            if i == min_idx:  # 只有最小range那條
                ys_sensor_scaled.append(minrange_downscale(y, min_sensor_min, min_sensor_max))
            else:
                ys_sensor_scaled.append((y - global_min)/(global_max - global_min)*2 - 1)
        ys_av_scaled = []
        for col in av_cols:
            y_av = df[col].apply(av_upscale).values.astype(float)
            y_mapped = (y_av+1)/2 * (min_sensor_max-min_sensor_min) + min_sensor_min
            y_scaled = minrange_downscale(y_mapped, min_sensor_min, min_sensor_max)
            ys_av_scaled.append(y_scaled)
        all_labels = sensor_cols + [f"{col} (av)" for col in av_cols]
        all_colors = ['#fc8d62', '#66c2a5', '#8da0cb', '#e78ac3', '#a6d854', '#ffd92f', '#e5c494', '#b3b3b3']
        all_styles = ['-'] * len(sensor_cols) + ['--'] * len(av_cols)
        all_ys = ys_sensor_scaled + ys_av_scaled
        for y_scaled, label, color, style in zip(all_ys, all_labels, all_colors, all_styles):
            self.ax.plot(df[self.time_col], y_scaled, label=label, color=color, linestyle=style)
        self.ax.axhline(0, color="#999", linestyle=":", linewidth=1, alpha=0.7, label="0 基準線")
        line_handles, line_labels = self.ax.get_legend_handles_labels()
        handles = patch_handles + line_handles
        labels = [h.get_label() for h in patch_handles] + line_labels
        self.ax.legend(handles, labels, loc='upper left', fontsize=9, ncol=1)
        if not (switch_cols or sensor_cols or av_cols) or df.empty:
            self.ax.set_title('請至少勾選一個感測器/狀態/AV')
        self.ax.set_xlabel('時間')
        self.ax.set_ylabel('標準化數值')
        self.ax.relim()
        self.ax.autoscale_view()
        self.fig.tight_layout()
        self.canvas_plot.draw()
