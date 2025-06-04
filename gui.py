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
    # pick_file # utils.py 中已經有 pick_file, 但 gui.py 中直接用 filedialog.askopenfilename
)
import datetime
import sys # 用於關閉程式

class SensorPicker(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("light")  # 設定為淺色模式
        self.title("感測器Plot")
        
        self.df_all = None
        self.time_col = None
        self.time_min = None
        self.time_max = None
        self.start_time = ctk.StringVar()
        self.end_time = ctk.StringVar()
        self._search_after_id = None # 用於延遲搜尋刷新
 
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill=ctk.BOTH, expand=1)

        # 側邊選單
        side_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        side_frame.pack(side=ctk.LEFT, fill=ctk.Y, padx=10, pady=6)

        # 新增 "開啟新 CSV" 按鈕
        ctk.CTkButton(side_frame, text="開啟新 CSV 檔案", command=self.open_new_csv, corner_radius=8).pack(pady=(0,5), ipady=4, fill=ctk.X)

        # 時間區段
        time_frame = ctk.CTkFrame(side_frame, fg_color="transparent")
        time_frame.pack(fill=ctk.X, pady=(10,0))

        start_time_row_frame = ctk.CTkFrame(time_frame, fg_color="transparent")
        start_time_row_frame.pack(fill=ctk.X, pady=(0, 5))
        ctk.CTkLabel(start_time_row_frame, text="起始時間：").pack(side=ctk.LEFT, padx=(0,5))
        self.start_entry = ctk.CTkEntry(start_time_row_frame, textvariable=self.start_time, state='disabled', corner_radius=8) # 初始禁用
        self.start_entry.pack(side=ctk.LEFT, expand=True, fill=ctk.X, padx=(0,5), ipady=2)
        self.pick_start_button = ctk.CTkButton(start_time_row_frame, text="📅", command=self.pick_start_time, width=40, height=28, state='disabled', corner_radius=8) # 初始禁用
        self.pick_start_button.pack(side=ctk.LEFT)

        end_time_row_frame = ctk.CTkFrame(time_frame, fg_color="transparent")
        end_time_row_frame.pack(fill=ctk.X)
        ctk.CTkLabel(end_time_row_frame, text="結束時間：").pack(side=ctk.LEFT, padx=(0,5))
        self.end_entry = ctk.CTkEntry(end_time_row_frame, textvariable=self.end_time, state='disabled', corner_radius=8) # 初始禁用
        self.end_entry.pack(side=ctk.LEFT, expand=True, fill=ctk.X, padx=(0,5), ipady=2)
        self.pick_end_button = ctk.CTkButton(end_time_row_frame, text="📅", command=self.pick_end_time, width=40, height=28, state='disabled', corner_radius=8) # 初始禁用
        self.pick_end_button.pack(side=ctk.LEFT)

        # 下載按鈕
        self.download_csv_button = ctk.CTkButton(side_frame, text="下載資料 (CSV)", command=self.download_csv, state='disabled', corner_radius=8) # 初始禁用
        self.download_csv_button.pack(pady=(10,5), ipady=4, fill=ctk.X)
        self.download_png_button = ctk.CTkButton(side_frame, text="下載圖檔 (PNG)", command=self.download_png, state='disabled', corner_radius=8) # 初始禁用
        self.download_png_button.pack(pady=(0,10), ipady=4, fill=ctk.X)

        # 搜尋框
        ctk.CTkLabel(side_frame, text="搜尋/勾選/顯示：").pack(anchor='w', pady=(10,2))
        self.search_var = ctk.StringVar()
        self.search_var.trace_add('write', self.refresh_panel_if_data_loaded)
        self.search_entry = ctk.CTkEntry(side_frame, textvariable=self.search_var, state='disabled', corner_radius=8) # 初始禁用
        self.search_entry.pack(fill=ctk.X, padx=0, pady=(0,5), ipady=2)
        
        scroll_outer = ctk.CTkFrame(side_frame, fg_color="transparent")
        scroll_outer.pack(fill=ctk.BOTH, expand=1, padx=0, pady=0)
        import tkinter as tk # 保持這個 import
        self.canvas = tk.Canvas(scroll_outer, width=350, height=540, background="#fafbfc", highlightthickness=0)
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

        self.switch_all = []
        self.av_all = []
        self.sensor_all = []
        self.all_cols = []
        self.vars_all = {}
        self.is_visible = {}

        self.start_time.trace_add("write", lambda *_: self.update_plot_if_data_loaded())
        self.end_time.trace_add("write", lambda *_: self.update_plot_if_data_loaded())

        # 主圖表
        self.fig, self.ax = plt.subplots(figsize=(11, 8))
        self.canvas_plot = FigureCanvasTkAgg(self.fig, master=main_frame)
        self.toolbar = NavigationToolbar2Tk(self.canvas_plot, main_frame)
        self.toolbar.update()
        self.canvas_plot.get_tk_widget().pack(side=ctk.RIGHT, fill=ctk.BOTH, expand=1)

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

        self.load_initial_data()

    def _set_controls_state(self, state):
        """啟用或禁用相關控制項"""
        self.start_entry.configure(state=state)
        self.pick_start_button.configure(state=state)
        self.end_entry.configure(state=state)
        self.pick_end_button.configure(state=state)
        self.download_csv_button.configure(state=state)
        self.download_png_button.configure(state=state)
        self.search_entry.configure(state=state)
        # 根據是否有資料來決定 refresh_panel 是否應該執行
        if state == 'disabled':
            for widget in self.scrollable_frame.winfo_children():
                widget.destroy() # 清空欄位列表
        elif state == 'normal' and self.df_all is not None:
             self.refresh_panel()


    def load_data_from_file(self, file_path):
        try:
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
                messagebox.showerror("錯誤", "CSV 沒有 Timestamp 或 Date/Time 欄")
                return False

            self.df_all = df.copy()
            self.time_col = time_col
            self.time_min = pd.Timestamp(df[time_col].min())
            self.time_max = pd.Timestamp(df[time_col].max())
            self.start_time.set(str(self.time_min)[:19])
            self.end_time.set(str(self.time_max)[:19])

            self.switch_all = get_switchable_cols(self.df_all)
            self.av_all = get_av_cols(self.df_all)
            self.sensor_all = get_sensor_cols(self.df_all)
            self.all_cols = self.switch_all + self.sensor_all + self.av_all
            self.vars_all = {} 
            self.is_visible = {col: True for col in self.all_cols}
            
            self._set_controls_state('normal') # 啟用控制項
            self.refresh_panel()
            self.update_plot()
            return True
        except Exception as e:
            messagebox.showerror("讀取檔案錯誤", str(e))
            self._set_controls_state('disabled') # 禁用控制項
            self.ax.clear()
            self.ax.set_title('讀取檔案錯誤或無資料')
            self.canvas_plot.draw()
            return False

    def load_initial_data(self):
        file_path = filedialog.askopenfilename(
            title="選擇 CSV 檔案",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not file_path:
            messagebox.showinfo("提示", "未選擇檔案，程式將關閉。")
            self.destroy()
            sys.exit() # 確保程式退出
            return 
        
        if not self.load_data_from_file(file_path):
            # load_data_from_file 內部已處理錯誤訊息和UI狀態
            # 如果初始載入失敗，也關閉程式
            messagebox.showinfo("提示", "檔案載入失敗，程式將關閉。")
            self.destroy()
            sys.exit() # 確保程式退出


    def open_new_csv(self):
        file_path = filedialog.askopenfilename(
            title="選擇新的 CSV 檔案",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if file_path:
            # 清空舊的勾選狀態和圖表
            self.vars_all = {}
            self.is_visible = {col: True for col in self.all_cols} # 重設可見度
            self.ax.clear() # 清除圖表
            self.canvas_plot.draw() # 更新空白圖表
            
            if not self.load_data_from_file(file_path):
                messagebox.showwarning("提示", "載入新檔案失敗。")
                # 保持UI為禁用狀態，因為新檔案載入失敗
                self._set_controls_state('disabled')
                self.ax.clear()
                self.ax.set_title('載入新檔案失敗')
                self.canvas_plot.draw()
            # 如果成功，load_data_from_file 會處理UI更新
        # else:
            # 使用者取消選擇，不做任何事

    def refresh_panel_if_data_loaded(self, *args):
        if self._search_after_id:
            self.after_cancel(self._search_after_id) # 取消之前的延遲任務
        
        # 延遲 300ms 後執行刷新
        self._search_after_id = self.after(300, self._do_refresh_panel)

    def _do_refresh_panel(self):
        if self.df_all is not None:
            self.refresh_panel()
            
    def update_plot_if_data_loaded(self):
        if self.df_all is not None:
            self.update_plot()

    def refresh_panel(self, *args):
        if self.df_all is None: # 如果沒有載入資料，則不刷新
            return
            
        search_key = self.search_var.get().strip().lower()
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        selected_cols = [col for col in self.all_cols if self.vars_all.get(col, ctk.BooleanVar()).get()]
        if selected_cols:
            ctk.CTkLabel(self.scrollable_frame, text="已勾選 (點擊取消/隱藏)").pack(anchor='w', pady=(5,3), padx=5)
            for col in selected_cols:
                frm = ctk.CTkFrame(self.scrollable_frame, fg_color="transparent")
                frm.pack(anchor='w', fill=ctk.X, padx=5, pady=1)
                checked = "✅"
                btn_check = ctk.CTkButton(frm, text=checked, width=30, height=30, command=lambda c=col: self.toggle_checked(c), corner_radius=6, fg_color="transparent", hover_color="#DCE4EE", text_color_disabled="grey", text_color="black")
                btn_check.pack(side=ctk.LEFT, padx=(0,3))
                eye = "👁️" if self.is_visible.get(col, True) else "🙈"
                btn_eye = ctk.CTkButton(frm, text=eye, width=30, height=30, command=lambda c=col: self.toggle_visible(c), corner_radius=6, fg_color="transparent", hover_color="#DCE4EE", text_color_disabled="grey", text_color="black")
                btn_eye.pack(side=ctk.LEFT, padx=(0,5))
                ctk.CTkLabel(frm, text=col).pack(side=ctk.LEFT, pady=2)

        ctk.CTkLabel(self.scrollable_frame, text="全部感測器 (點擊勾選/隱藏)").pack(anchor='w', pady=(10,3), padx=5)
        for col in self.all_cols:
            if not search_key or search_key in col.lower():
                if col not in self.vars_all:
                    self.vars_all[col] = ctk.BooleanVar()
                frm = ctk.CTkFrame(self.scrollable_frame, fg_color="transparent")
                frm.pack(anchor='w', fill=ctk.X, padx=5, pady=1)
                checked = "✅" if self.vars_all[col].get() else "🔲"
                btn_check = ctk.CTkButton(frm, text=checked, width=30, height=30, command=lambda c=col: self.toggle_checked(c), corner_radius=6, fg_color="transparent", hover_color="#DCE4EE", text_color_disabled="grey", text_color="black")
                btn_check.pack(side=ctk.LEFT, padx=(0,3))
                eye = "👁️" if self.is_visible.get(col, True) else "🙈"
                btn_eye = ctk.CTkButton(frm, text=eye, width=30, height=30, command=lambda c=col: self.toggle_visible(c), corner_radius=6, fg_color="transparent", hover_color="#DCE4EE", text_color_disabled="grey", text_color="black")
                btn_eye.pack(side=ctk.LEFT, padx=(0,5))
                ctk.CTkLabel(frm, text=col).pack(side=ctk.LEFT, pady=2)

    def toggle_visible(self, col):
        if self.df_all is None: return
        self.is_visible[col] = not self.is_visible.get(col, True)
        self.refresh_panel()
        self.update_plot()

    def toggle_checked(self, col):
        if self.df_all is None: return
        v = self.vars_all.get(col, None)
        if v:
            v.set(not v.get())
        self.refresh_panel()
        self.update_plot()

    def pick_start_time(self):
        if self.df_all is None: return
        try:
            current = pd.Timestamp(self.start_time.get())
        except Exception:
            current = self.time_min
        dt = pick_datetime_with_default("選擇起始時間", current)
        if dt:
            self.start_time.set(dt.strftime("%Y-%m-%d %H:%M:%S"))
            # self.update_plot() # trace 會自動呼叫 update_plot_if_data_loaded

    def pick_end_time(self):
        if self.df_all is None: return
        try:
            current = pd.Timestamp(self.end_time.get())
        except Exception:
            current = self.time_max
        dt = pick_datetime_with_default("選擇結束時間", current)
        if dt:
            self.end_time.set(dt.strftime("%Y-%m-%d %H:%M:%S"))
            # self.update_plot() # trace 會自動呼叫 update_plot_if_data_loaded

    def on_press(self, event):
        if self.df_all is None: return
        if event.button == 1 and event.inaxes == self.ax:
            self._dragging = True
            self._drag_start_x = event.xdata
            try:
                self._drag_start_t0 = pd.Timestamp(self.start_time.get())
                self._drag_start_t1 = pd.Timestamp(self.end_time.get())
            except Exception: # 如果時間格式不對，則不進行拖曳
                self._dragging = False
                return
        elif event.button in [2, 3] and event.inaxes == self.ax:
            self._y_drag = True
            self._y_drag_start = event.y
            self._y_lim_start = self.ax.get_ylim()

    def on_motion(self, event):
        if self.df_all is None: return
        if self._dragging and event.inaxes == self.ax and event.xdata is not None and self._drag_start_x is not None:
            offset = self._drag_start_x - event.xdata
            offset_s = offset * 24 * 60 * 60 
            try:
                new_t0 = self._drag_start_t0 + pd.Timedelta(seconds=offset_s)
                new_t1 = self._drag_start_t1 + pd.Timedelta(seconds=offset_s)
                self.start_time.set(new_t0.strftime("%Y-%m-%d %H:%M:%S"))
                self.end_time.set(new_t1.strftime("%Y-%m-%d %H:%M:%S"))
                # self.update_plot() # trace 會自動呼叫
            except Exception:
                pass # 忽略時間轉換錯誤
        if self._y_drag and event.inaxes == self.ax and event.y is not None and self._y_drag_start is not None:
            y0, y1 = self._y_lim_start
            delta = event.y - self._y_drag_start
            pixel_to_data = (y1 - y0) / self.fig.bbox.height
            shift = delta * pixel_to_data
            self.ax.set_ylim(y0 + shift, y1 + shift)
            self.fig.tight_layout()
            self.canvas_plot.draw()

    def on_release(self, event):
        if self.df_all is None: return
        self._dragging = False
        self._drag_start_x = None
        self._y_drag = False
        self._y_drag_start = None
        self._y_lim_start = None

    def on_scroll(self, event):
        if self.df_all is None or event.inaxes != self.ax:
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
        if self.df_all is None:
            messagebox.showwarning("無資料", "請先載入 CSV 檔案")
            return
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
        df_to_download = self.df_all.loc[mask]
        selected_cols_to_download = [col for col, v in self.vars_all.items() if v.get()]
        
        if not selected_cols_to_download or df_to_download.empty:
            messagebox.showwarning("無資料", "此區段無資料可下載，或未勾選任何欄位")
            return
            
        cols_to_export = [self.time_col] + selected_cols_to_download
        export_cols_final = [c for c in cols_to_export if c in df_to_download.columns]
        
        if not export_cols_final:
            messagebox.showwarning("無資料", "選取的欄位在此時間區段內無資料")
            return

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
                df_to_download[export_cols_final].to_csv(fpath, index=False, encoding="utf-8-sig")
            except Exception as e:
                messagebox.showerror("CSV儲存錯誤", str(e))

    def download_png(self):
        if self.df_all is None:
            messagebox.showwarning("無資料", "請先載入 CSV 檔案")
            return
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
        if self.df_all is None or self.time_col is None:
            self.ax.clear()
            self.ax.set_title('請先載入 CSV 檔案')
            self.canvas_plot.draw()
            return

        self.ax.clear()
        tz = pytz.timezone('Asia/Taipei')
        try:
            start_str = self.start_time.get()
            end_str = self.end_time.get()
            if not start_str or not end_str: # 確保時間字串非空
                 self.ax.set_title('時間範圍未設定')
                 self.canvas_plot.draw()
                 return
            start = pd.Timestamp(start_str)
            if start.tzinfo is None:
                start = start.tz_localize(tz)
            end = pd.Timestamp(end_str)
            if end.tzinfo is None:
                end = end.tz_localize(tz)
        except Exception as e:
            self.ax.set_title(f'請正確輸入時間: {e}')
            self.fig.tight_layout()
            self.canvas_plot.draw()
            return

        mask = (self.df_all[self.time_col] >= start) & (self.df_all[self.time_col] <= end)
        df = self.df_all.loc[mask]
        
        if df.empty:
            self.ax.set_title('此時間範圍內無資料')
            self.fig.tight_layout()
            self.canvas_plot.draw()
            return

        selected_cols = [col for col, v in self.vars_all.items() if v.get() and self.is_visible.get(col, True)]
        switch_cols = [col for col in selected_cols if col in self.switch_all]
        sensor_cols = [col for col in selected_cols if col in self.sensor_all]
        av_cols = [col for col in selected_cols if col in self.av_all]

        patch_handles = []
        for col in switch_cols:
            if col not in df.columns or df[col].empty: continue
            times = df[self.time_col].values
            vals = df[col].astype(str).values
            if not len(times): continue # 如果沒有時間資料，跳過
            seg_start = times[0]
            seg_val = vals[0]
            for i in range(1, len(times)):
                if vals[i] != seg_val or i == len(times)-1:
                    seg_end = times[i] if vals[i] != seg_val else times[i]+np.timedelta64(1,'s') # 修正最後一段時間
                    self.ax.axvspan(pd.to_datetime(seg_start), pd.to_datetime(seg_end),
                                    facecolor=state_color(seg_val), alpha=0.30)
                    if i < len(times) -1 or vals[i] == seg_val : # 避免 index out of bounds
                         seg_start = times[i]
                         seg_val = vals[i]
                    elif i == len(times)-1 and vals[i] != seg_val: #處理最後一個點且值不同的情況
                         self.ax.axvspan(pd.to_datetime(times[i]), pd.to_datetime(times[i]+np.timedelta64(1,'s')),
                                    facecolor=state_color(vals[i]), alpha=0.30)


            for state_code in sorted(list(set(vals))): # 確保 vals 不是空的
                patch_handles.append(
                    mpatches.Patch(
                        color=state_color(state_code),
                        label=f"{col} = {state_code}"
                    )
                )
        
        # 確保 sensor_cols 中的欄位存在於 df 中
        valid_sensor_cols = [col for col in sensor_cols if col in df.columns and not df[col].isnull().all()]
        ys_sensor = [pd.to_numeric(df[col], errors='coerce').values for col in valid_sensor_cols]
        
        min_idx = -1 # 初始化 min_idx
        if ys_sensor:
            sensor_ranges = [np.nanmax(y)-np.nanmin(y) if not np.all(np.isnan(y)) else 0 for y in ys_sensor]
            if any(sr > 0 for sr in sensor_ranges): # 確保至少有一個有效的 range
                min_range = np.nanmin([sr for sr in sensor_ranges if sr > 0]) # 只考慮 > 0 的 range
                # 找到第一個達到 min_range 的索引
                min_idx_candidates = [i for i, sr in enumerate(sensor_ranges) if sr == min_range]
                if min_idx_candidates:
                    min_idx = min_idx_candidates[0]
                
                if min_idx != -1:
                    min_sensor_y = ys_sensor[min_idx]
                    min_sensor_min = np.nanmin(min_sensor_y)
                    min_sensor_max = np.nanmax(min_sensor_y)
                    if np.isnan(min_sensor_min) or np.isnan(min_sensor_max) or min_sensor_max == min_sensor_min: #處理全nan或單點情況
                        min_sensor_min = 0
                        min_sensor_max = 1
                else: # 如果所有 range 都是0或nan
                    min_sensor_min = 0
                    min_sensor_max = 1
            else: # 如果所有 range 都是0或nan
                min_sensor_min = 0
                min_sensor_max = 1
        else:
            min_sensor_min = 0
            min_sensor_max = 1

        all_y_flat = [item for sublist in ys_sensor for item in sublist if not np.isnan(item)]
        global_min = np.min(all_y_flat) if all_y_flat else 0
        global_max = np.max(all_y_flat) if all_y_flat else 1
        if global_max - global_min < 1e-8:
            global_max = global_min + 1

        def minrange_downscale(y, min_v, max_v):
            if max_v - min_v < 1e-12: return np.zeros_like(y) # 避免除以零
            norm = (y - min_v) / (max_v - min_v)
            return norm - 0.5
            
        ys_sensor_scaled = []
        for i, y_sensor_raw in enumerate(ys_sensor):
            if i == min_idx :
                ys_sensor_scaled.append(minrange_downscale(y_sensor_raw, min_sensor_min, min_sensor_max))
            else:
                if global_max - global_min < 1e-12:
                    ys_sensor_scaled.append(np.zeros_like(y_sensor_raw))
                else:
                    ys_sensor_scaled.append((y_sensor_raw - global_min)/(global_max - global_min)*2 - 1)

        # 確保 av_cols 中的欄位存在於 df 中
        valid_av_cols = [col for col in av_cols if col in df.columns and not df[col].isnull().all()]
        ys_av_scaled = []
        for col in valid_av_cols:
            y_av = df[col].apply(av_upscale).values.astype(float)
            y_mapped = (y_av+1)/2 * (min_sensor_max-min_sensor_min) + min_sensor_min
            y_scaled = minrange_downscale(y_mapped, min_sensor_min, min_sensor_max)
            ys_av_scaled.append(y_scaled)
            
        all_labels = valid_sensor_cols + [f"{col} (av)" for col in valid_av_cols]
        # 確保顏色和樣式列表長度與繪圖數據匹配
        num_sensor_plots = len(ys_sensor_scaled)
        num_av_plots = len(ys_av_scaled)
        
        base_colors = ['#fc8d62', '#66c2a5', '#8da0cb', '#e78ac3', '#a6d854', '#ffd92f', '#e5c494', '#b3b3b3']
        all_colors = [base_colors[i % len(base_colors)] for i in range(num_sensor_plots + num_av_plots)]
        all_styles = ['-'] * num_sensor_plots + ['--'] * num_av_plots
        all_ys_to_plot = ys_sensor_scaled + ys_av_scaled

        for y_scaled, label, color, style in zip(all_ys_to_plot, all_labels, all_colors, all_styles):
            if not np.all(np.isnan(y_scaled)): # 只繪製非全 NaN 的數據
                self.ax.plot(df[self.time_col], y_scaled, label=label, color=color, linestyle=style)
        
        if any(not np.all(np.isnan(y)) for y in all_ys_to_plot): # 只有在有線條繪製時才畫基準線
            self.ax.axhline(0, color="#999", linestyle=":", linewidth=1, alpha=0.7, label="0 基準線")
        
        line_handles, line_labels = self.ax.get_legend_handles_labels()
        # 過濾掉重複的 label (主要針對基準線)
        unique_labels = {}
        final_handles = []
        final_labels = []
        for handle, label in zip(patch_handles + line_handles, [h.get_label() for h in patch_handles] + line_labels):
            if label not in unique_labels:
                unique_labels[label] = handle
                final_handles.append(handle)
                final_labels.append(label)

        if final_handles:
             self.ax.legend(final_handles, final_labels, loc='upper left', fontsize=9, ncol=1)

        if not (switch_cols or valid_sensor_cols or valid_av_cols):
            self.ax.set_title('請至少勾選一個感測器')
        elif df.empty :
             self.ax.set_title('此時間範圍內無資料')
        # else:
            # 如果有資料且有勾選，則不特別設定標題，讓圖表內容自行呈現
            # pass

        self.ax.set_xlabel('時間')
        self.ax.set_ylabel('標準化數值')
        self.ax.relim()
        self.ax.autoscale_view(tight=False) # tight=False 避免太緊湊
        self.fig.tight_layout()
        self.canvas_plot.draw()
