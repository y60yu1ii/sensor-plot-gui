import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import pytz
import customtkinter as ctk
from tkinter import ttk, filedialog, messagebox
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.patches as mpatches
import threading # <--- Added import
from utils import (
    pick_datetime_with_default,
    get_switchable_cols,
    get_sensor_cols,
    state_color,
    av_upscale,
    get_equipment_chinese_name # 新增導入
    # pick_file # utils.py 中已經有 pick_file, 但 gui.py 中直接用 filedialog.askopenfilename
)
import datetime
import sys # 用於關閉程式

class SensorPicker(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("light")  # 設定為淺色模式
        self.title("感測器Plot")

        # 定義中文字體
        self.chinese_font = ctk.CTkFont(family="Microsoft JhengHei", size=12)
        self.chinese_font_bold = ctk.CTkFont(family="Microsoft JhengHei", size=12, weight="bold")
        # 移除錯誤的字體設定和日誌
        
        self.df_all = None
        self.time_col = None
        self.time_min = None
        self.time_max = None
        self.start_time = ctk.StringVar()
        self.end_time = ctk.StringVar()
        self._search_after_id = None # 用於延遲搜尋刷新
        self.ax2 = None # 次要 Y 軸
        self.RANGE_SIMILARITY_FACTOR = 2.5 # 用於判斷範圍是否相近的因子

        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill=ctk.BOTH, expand=1)

        # 側邊選單
        side_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        side_frame.pack(side=ctk.LEFT, fill=ctk.Y, padx=10, pady=6)

        # 新增 "開啟新 CSV" 按鈕
        ctk.CTkButton(side_frame, text="開啟新 CSV 檔案", command=self.open_new_csv, corner_radius=8, font=self.chinese_font_bold).pack(pady=(0,5), ipady=4, fill=ctk.X)

        # 時間區段
        time_frame = ctk.CTkFrame(side_frame, fg_color="transparent")
        time_frame.pack(fill=ctk.X, pady=(10,0))

        start_time_row_frame = ctk.CTkFrame(time_frame, fg_color="transparent")
        start_time_row_frame.pack(fill=ctk.X, pady=(0, 5))
        ctk.CTkLabel(start_time_row_frame, text="起始時間：", font=self.chinese_font).pack(side=ctk.LEFT, padx=(0,5))
        self.start_entry = ctk.CTkEntry(start_time_row_frame, textvariable=self.start_time, state='disabled', corner_radius=8, font=self.chinese_font) # 初始禁用
        self.start_entry.pack(side=ctk.LEFT, expand=True, fill=ctk.X, padx=(0,5), ipady=2)
        self.pick_start_button = ctk.CTkButton(start_time_row_frame, text="📅", command=self.pick_start_time, width=40, height=28, state='disabled', corner_radius=8) # 初始禁用
        self.pick_start_button.pack(side=ctk.LEFT)

        end_time_row_frame = ctk.CTkFrame(time_frame, fg_color="transparent")
        end_time_row_frame.pack(fill=ctk.X)
        ctk.CTkLabel(end_time_row_frame, text="結束時間：", font=self.chinese_font).pack(side=ctk.LEFT, padx=(0,5))
        self.end_entry = ctk.CTkEntry(end_time_row_frame, textvariable=self.end_time, state='disabled', corner_radius=8, font=self.chinese_font) # 初始禁用
        self.end_entry.pack(side=ctk.LEFT, expand=True, fill=ctk.X, padx=(0,5), ipady=2)
        self.pick_end_button = ctk.CTkButton(end_time_row_frame, text="📅", command=self.pick_end_time, width=40, height=28, state='disabled', corner_radius=8) # 初始禁用
        self.pick_end_button.pack(side=ctk.LEFT)

        # 下載按鈕
        self.download_csv_button = ctk.CTkButton(side_frame, text="下載資料 (CSV)", command=self.download_csv, state='disabled', corner_radius=8, font=self.chinese_font_bold) # 初始禁用
        self.download_csv_button.pack(pady=(10,5), ipady=4, fill=ctk.X)
        self.download_png_button = ctk.CTkButton(side_frame, text="下載圖檔 (PNG)", command=self.download_png, state='disabled', corner_radius=8, font=self.chinese_font_bold) # 初始禁用
        self.download_png_button.pack(pady=(0,10), ipady=4, fill=ctk.X)

        # 搜尋框
        ctk.CTkLabel(side_frame, text="搜尋/勾選/顯示：", font=self.chinese_font).pack(anchor='w', pady=(10,2))
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

        # self.load_initial_data() # <-- 移除啟動時自動載入
        self.update_plot() # <-- 新增，確保啟動時顯示初始圖表

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
             self.refresh_panel_if_data_loaded() # <--- Changed


    def load_data_from_file(self, file_path):
        try:
            # 增加錯誤處理選項，跳過格式錯誤的行
            # 使用 on_bad_lines='skip' 替代 error_bad_lines=False (適用於 pandas 1.3.0+)
            df = pd.read_csv(file_path, low_memory=False, on_bad_lines='skip')
            # 處理混合類型，並確保字串中的逗號不會導致欄位解析錯誤
            # 預設情況下，pandas 會處理引號內的逗號，但明確指定 quotechar 和 doublequote 可以增加健壯性
            # df = pd.read_csv(file_path, low_memory=False, on_bad_lines='skip', sep=',', quotechar='"', doublequote=True)
            
            # Handle mixed types for column 'lt-302m' (column 104)
            if 'lt-302m' in df.columns:
                # Attempt to convert to numeric, coercing errors to NaN
                df['lt-302m'] = pd.to_numeric(df['lt-302m'], errors='coerce')
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
            self.sensor_all = get_sensor_cols(self.df_all)
            self.all_cols = self.switch_all + self.sensor_all
            # self.vars_all = {} # Old line
            self.vars_all = {col: ctk.BooleanVar(value=False) for col in self.all_cols} # New: Initialize all
            self.is_visible = {col: True for col in self.all_cols}
            
            self._set_controls_state('normal') # 啟用控制項
            self.refresh_panel_if_data_loaded() # 替換為正確的方法
            self.update_plot()
            return True
        except Exception as e:
            messagebox.showerror("讀取檔案錯誤", str(e))
            self._set_controls_state('disabled') # 禁用控制項
            self.ax.clear()
            self.ax.set_title('讀取檔案錯誤或無資料')
            self.canvas_plot.draw()
            return False

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
            if self.ax2: # Clear secondary axis if it exists
                if self.ax2.get_figure(): self.ax2.remove()
                self.ax2 = None
            self.canvas_plot.draw() # 更新空白圖表
            
            if not self.load_data_from_file(file_path):
                messagebox.showwarning("提示", "載入新檔案失敗。")
                # 保持UI為禁用狀態，因為新檔案載入失敗
                self._set_controls_state('disabled')
                self.ax.clear()
                if self.ax2:
                    if self.ax2.get_figure(): self.ax2.remove()
                    self.ax2 = None
                self.ax.set_title('載入新檔案失敗')
                self.canvas_plot.draw()
            # 如果成功，load_data_from_file 會處理UI更新
        # else:
            # 使用者取消選擇，不做任何事

    def refresh_panel_if_data_loaded(self, *args):
        if self._search_after_id:
            self.after_cancel(self._search_after_id) # 取消之前的延遲任務
        
        # 延遲 500ms 後執行刷新 (原為 300ms)
        self._search_after_id = self.after(500, self._do_refresh_panel)

    def _do_refresh_panel(self):
        if self.df_all is not None:
            # self.refresh_panel() # Old direct call
            search_key = self.search_var.get().strip().lower()
            # Create a snapshot of vars_all and is_visible for thread safety
            vars_all_snapshot = {k: v.get() for k, v in self.vars_all.items()}
            is_visible_snapshot = self.is_visible.copy()
            
            # Start a new thread for filtering
            thread = threading.Thread(target=self._filter_columns_thread_target,
                                      args=(search_key, vars_all_snapshot, is_visible_snapshot, self.all_cols[:])) # Pass a copy of all_cols
            thread.daemon = True # Allow main program to exit even if threads are still running
            thread.start()

    def _filter_columns_thread_target(self, search_key, vars_all_snapshot, is_visible_snapshot, all_cols_snapshot):
        if self.df_all is None:
            return

        selected_cols_data = []
        all_sensors_data = []

        # Process selected columns
        # Ensure vars_all_snapshot is used correctly
        current_selected_cols = [col for col in all_cols_snapshot if vars_all_snapshot.get(col, False)]

        for col in current_selected_cols:
            # No search filter for already selected items, they always show in "已勾選"
            selected_cols_data.append({
                'name': col,
                'is_checked': True, # They are by definition checked
                'is_visible': is_visible_snapshot.get(col, True)
            })

        # Process all sensors for the "全部感測器" list
        for col in all_cols_snapshot:
            if not search_key or search_key in col.lower():
                all_sensors_data.append({
                    'name': col,
                    'is_checked': vars_all_snapshot.get(col, False),
                    'is_visible': is_visible_snapshot.get(col, True)
                })
        
        # Schedule the UI update on the main thread
        self.after(0, self._render_panel_from_data, selected_cols_data, all_sensors_data)

    def _render_panel_from_data(self, selected_cols_data, all_sensors_data):
        if self.df_all is None: # Double check if data is still loaded
            return

        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        if selected_cols_data:
            ctk.CTkLabel(self.scrollable_frame, text="已勾選 (點擊取消/隱藏)", font=self.chinese_font_bold).pack(anchor='w', pady=(5,3), padx=5)
            for item_data in selected_cols_data:
                col = item_data['name']
                frm = ctk.CTkFrame(self.scrollable_frame, fg_color="transparent")
                frm.pack(anchor='w', fill=ctk.X, padx=5, pady=1)
                checked_text = "✅" # Always checked in this section
                btn_check = ctk.CTkButton(frm, text=checked_text, width=30, height=30, command=lambda c=col: self.toggle_checked(c), corner_radius=6, fg_color="transparent", hover_color="#DCE4EE", text_color_disabled="grey", text_color="black", font=self.chinese_font)
                btn_check.pack(side=ctk.LEFT, padx=(0,3))
                
                eye_text = "👁️" if item_data['is_visible'] else "🙈"
                btn_eye = ctk.CTkButton(frm, text=eye_text, width=30, height=30, command=lambda c=col: self.toggle_visible(c), corner_radius=6, fg_color="transparent", hover_color="#DCE4EE", text_color_disabled="grey", text_color="black", font=self.chinese_font)
                btn_eye.pack(side=ctk.LEFT, padx=(0,5))
                display_text = f"{get_equipment_chinese_name(col)} ({col})" # 顯示中文名稱和原始 tag
                ctk.CTkLabel(frm, text=display_text, font=self.chinese_font).pack(side=ctk.LEFT, pady=2)

        ctk.CTkLabel(self.scrollable_frame, text="全部感測器 (點擊勾選/隱藏)", font=self.chinese_font_bold).pack(anchor='w', pady=(10,3), padx=5)
        for item_data in all_sensors_data:
            col = item_data['name']
            frm = ctk.CTkFrame(self.scrollable_frame, fg_color="transparent")
            frm.pack(anchor='w', fill=ctk.X, padx=5, pady=1)
            
            checked_text = "✅" if item_data['is_checked'] else "🔲"
            btn_check = ctk.CTkButton(frm, text=checked_text, width=30, height=30, command=lambda c=col: self.toggle_checked(c), corner_radius=6, fg_color="transparent", hover_color="#DCE4EE", text_color_disabled="grey", text_color="black", font=self.chinese_font)
            btn_check.pack(side=ctk.LEFT, padx=(0,3))
            
            eye_text = "👁️" if item_data['is_visible'] else "🙈"
            btn_eye = ctk.CTkButton(frm, text=eye_text, width=30, height=30, command=lambda c=col: self.toggle_visible(c), corner_radius=6, fg_color="transparent", hover_color="#DCE4EE", text_color_disabled="grey", text_color="black", font=self.chinese_font)
            btn_eye.pack(side=ctk.LEFT, padx=(0,5))
            display_text = f"{get_equipment_chinese_name(col)} ({col})" # 顯示中文名稱和原始 tag
            ctk.CTkLabel(frm, text=display_text, font=self.chinese_font).pack(side=ctk.LEFT, pady=2)
            
    def update_plot_if_data_loaded(self):
        if self.df_all is not None:
            self.update_plot()

    # refresh_panel method is now removed, its logic is split into
    # _filter_columns_thread_target and _render_panel_from_data

    def toggle_visible(self, col):
        if self.df_all is None: return
        self.is_visible[col] = not self.is_visible.get(col, True)
        self.refresh_panel_if_data_loaded()
        self.after(1, self.update_plot)

    def toggle_checked(self, col):
        if self.df_all is None: return
        v = self.vars_all.get(col, None)
        if v:
            v.set(not v.get())
        self.refresh_panel_if_data_loaded()
        self.after(1, self.update_plot)

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
        elif event.button in [2, 3] and event.inaxes == self.ax: # Middle or Right click for Y-axis drag
            active_ax = event.inaxes
            if self.ax2 and active_ax == self.ax2: # If event is on ax2, drag ax2
                 self._y_drag_ax = self.ax2
            else: # Otherwise, drag ax1 (self.ax)
                 self._y_drag_ax = self.ax

            if self._y_drag_ax:
                self._y_drag = True
                self._y_drag_start = event.y
                self._y_lim_start = self._y_drag_ax.get_ylim()


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
            except Exception:
                pass 
        if self._y_drag and self._y_drag_ax and event.inaxes == self._y_drag_ax and event.y is not None and self._y_drag_start is not None:
            y0, y1 = self._y_lim_start
            delta = event.y - self._y_drag_start
            pixel_to_data = (y1 - y0) / self._y_drag_ax.get_figure().bbox.height
            shift = delta * pixel_to_data
            self._y_drag_ax.set_ylim(y0 + shift, y1 + shift)
            self.fig.tight_layout()
            self.canvas_plot.draw()

    def on_release(self, event):
        if self.df_all is None: return
        self._dragging = False
        self._drag_start_x = None
        self._y_drag = False
        self._y_drag_start = None
        self._y_lim_start = None
        self._y_drag_ax = None # Reset dragged axis

    def on_scroll(self, event):
        if self.df_all is None or event.inaxes not in [self.ax, self.ax2]: # Check if scroll is on ax or ax2
            return
        
        active_ax = event.inaxes # Determine which axis the scroll event occurred on
        cur_ylim = active_ax.get_ylim()
        y_mouse = event.ydata
        if y_mouse is None:
            return
        scale_factor = 1.25 if event.button == 'up' else 0.8
        new_height = (cur_ylim[1] - cur_ylim[0]) * scale_factor
        rel_pos = (y_mouse - cur_ylim[0]) / (cur_ylim[1] - cur_ylim[0])
        
        new_ymin = y_mouse - new_height * rel_pos
        new_ymax = y_mouse + new_height * (1 - rel_pos)
        
        active_ax.set_ylim([new_ymin, new_ymax])
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
            if self.ax2:
                if self.ax2.get_figure(): self.ax2.remove()
                self.ax2 = None
            self.ax.set_title('請先載入 CSV 檔案')
            self.canvas_plot.draw()
            return

        self.ax.clear()
        if self.ax2:
            if self.ax2.get_figure(): self.ax2.remove()
            self.ax2 = None

        tz = pytz.timezone('Asia/Taipei')
        try:
            start_str = self.start_time.get()
            end_str = self.end_time.get()
            if not start_str or not end_str:
                self.ax.set_title('時間範圍未設定')
                self.canvas_plot.draw()
                return
            start = pd.Timestamp(start_str)
            if start.tzinfo is None: start = start.tz_localize(tz)
            end = pd.Timestamp(end_str)
            if end.tzinfo is None: end = end.tz_localize(tz)
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
        switch_cols_selected = [col for col in selected_cols if col in self.switch_all]
        sensor_cols_selected = [col for col in selected_cols if col in self.sensor_all]

        patch_handles = []
        short_bar_ymin = 0.85
        short_bar_height = 0.03
        short_bar_gap = 0.01
        short_bar_levels = []
        short_bar_pos_map = {}
        for col in switch_cols_selected:
            if col.startswith("b-") or col.startswith("p-") or col.startswith("av-"):
                y_base = short_bar_ymin - (len(short_bar_levels) * (short_bar_height + short_bar_gap))
                short_bar_pos_map[col] = (y_base, y_base + short_bar_height)
                short_bar_levels.append(col)

        for col_name in switch_cols_selected:
            if col_name not in df.columns or df[col_name].empty: continue
            times = df[self.time_col].values
            vals = df[col_name].astype(str).values
            if not len(times): continue
            seg_start = times[0]
            seg_val = vals[0]
            for i in range(1, len(times)):
                if vals[i] != seg_val or i == len(times)-1:
                    seg_end = times[i] if vals[i] != seg_val else times[i]+np.timedelta64(1,'s')
                    y0, y1 = short_bar_pos_map.get(col_name, (0.0, 1.0))
                    self.ax.axvspan(pd.to_datetime(seg_start), pd.to_datetime(seg_end),
                                    facecolor=state_color(seg_val, col_name), alpha=0.45,
                                    ymin=y0, ymax=y1)
                    if i < len(times) -1 or vals[i] == seg_val:
                        seg_start = times[i]
                        seg_val = vals[i]
                    elif i == len(times)-1 and vals[i] != seg_val:
                        y0, y1 = short_bar_pos_map.get(col_name, (0.0, 1.0))
                        self.ax.axvspan(pd.to_datetime(times[i]), pd.to_datetime(times[i]+np.timedelta64(1,'s')),
                                        facecolor=state_color(vals[i], col_name), alpha=0.45,
                                        ymin=y0, ymax=y1)
            unique_switch_vals = sorted(list(set(vals)))
            for state_val in unique_switch_vals:
                patch_handles.append(mpatches.Patch(color=state_color(state_val), label=f"{col_name} = {state_val}"))
    
        # --- 準備 sensor data 並分類 (移出迴圈) ---
        valid_sensor_cols = [col for col in sensor_cols_selected if col in df.columns and not df[col].isnull().all()]
        ys_sensor_raw_map = {col: pd.to_numeric(df[col], errors='coerce').values for col in valid_sensor_cols}
        sensor_means_map = {col: np.nanmean(ys_sensor_raw_map[col]) if col in ys_sensor_raw_map and not np.all(np.isnan(ys_sensor_raw_map[col])) else np.nan for col in valid_sensor_cols}
        
        reference_cols_list = []
        scaled_cols_list = []
    
        if valid_sensor_cols:
            sensor_ranges_map = {}
            for col_name in valid_sensor_cols:
                y_raw = ys_sensor_raw_map[col_name]
                if not np.all(np.isnan(y_raw)):
                    min_v, max_v = np.nanmin(y_raw), np.nanmax(y_raw)
                    sensor_ranges_map[col_name] = max_v - min_v if (max_v - min_v) > 1e-9 else 0.0
                else:
                    sensor_ranges_map[col_name] = 0.0
            
            if sensor_ranges_map:
                positive_ranges = [r for r in sensor_ranges_map.values() if r > 1e-9]
                min_overall_positive_range = min(positive_ranges) if positive_ranges else 0.0
    
                for col_name in valid_sensor_cols:
                    current_range = sensor_ranges_map.get(col_name, 0.0)
                    if min_overall_positive_range == 0.0 or current_range <= min_overall_positive_range * self.RANGE_SIMILARITY_FACTOR:
                        reference_cols_list.append(col_name)
                    else:
                        scaled_cols_list.append(col_name)
            else:
                reference_cols_list = list(valid_sensor_cols)
        
        # --- Y 軸管理 ---
        ax1_has_data_lines = bool(reference_cols_list)
        ax2_needs_creation = bool(scaled_cols_list)
    
        if ax2_needs_creation:
            self.ax2 = self.ax.twinx() # Create secondary axis
        
        # --- 繪製 reference_cols_list (主 Y 軸) ---
        for col_name in reference_cols_list:
            y_raw = ys_sensor_raw_map.get(col_name)
            if y_raw is not None and not np.all(np.isnan(y_raw)):
                self.ax.plot(df[self.time_col], y_raw, label=f"{get_equipment_chinese_name(col_name)} (μ: {sensor_means_map.get(col_name, np.nan):.2f})")
    
        # --- 繪製 scaled_cols_list (次 Y 軸) ---
        if self.ax2 and scaled_cols_list:
            # 定義一組高對比度的顏色
            colors = plt.cm.get_cmap('tab10').colors
            for i, col_name in enumerate(scaled_cols_list):
                y_raw = ys_sensor_raw_map.get(col_name)
                mean_v = sensor_means_map.get(col_name, np.nan)
                if y_raw is not None and not np.all(np.isnan(y_raw)):
                    min_v, max_v = np.nanmin(y_raw), np.nanmax(y_raw)
                    color = colors[i % len(colors)] # 循環使用顏色
                    if (max_v - min_v) > 1e-9:
                        y_scaled = (y_raw - min_v) / (max_v - min_v) # Scale to [0,1]
                        self.ax2.plot(df[self.time_col], y_scaled, label=f"{get_equipment_chinese_name(col_name)} (scaled, μ: {mean_v:.2f})", color=color)
                    else: # Constant value, plot as 0.5 on scaled axis
                        self.ax2.plot(df[self.time_col], np.full_like(y_raw, 0.5), label=f"{get_equipment_chinese_name(col_name)} (scaled, μ: {mean_v:.2f})", color=color)
        
        # --- 圖例 ---
        h1, l1 = self.ax.get_legend_handles_labels()
        h2, l2 = [], []
        if self.ax2: # If ax2 was created
            h2_temp, l2_temp = self.ax2.get_legend_handles_labels()
            if h2_temp: # If ax2 actually plotted something
                h2, l2 = h2_temp, l2_temp
        
        all_handles = patch_handles + h1 + h2
        all_labels_text = [h.get_label() for h in patch_handles] + l1 + l2
        
        unique_labels_map = {} # To store unique labels and their handles
        final_handles, final_labels_text_ordered = [], []
        for handle, label_text_item in zip(all_handles, all_labels_text):
            if label_text_item not in unique_labels_map: # Ensure unique labels in legend
                unique_labels_map[label_text_item] = handle
                final_handles.append(handle)
                final_labels_text_ordered.append(label_text_item)
    
        if final_handles:
             self.ax.legend(final_handles, final_labels_text_ordered, loc='upper left', fontsize=9, ncol=1)
        
        # --- Y 軸標籤 ---
        self.ax.set_ylabel("絕對數值 (基準組)" if ax1_has_data_lines else "數值") # Set primary Y-axis label
        if self.ax2 and scaled_cols_list: # Only set label and make visible if ax2 has data
            self.ax2.set_ylabel("正規化數值 (其他組)")
            self.ax2.set_visible(True)
        elif self.ax2: # ax2 exists but has no data, make it invisible
             self.ax2.set_visible(False)
    
    
        # --- 圖表標題 ---
        if not (switch_cols_selected or valid_sensor_cols):
            self.ax.set_title('請至少勾選一個感測器')
        # df.empty case is handled at the beginning, no need to set title here for it
        
        # --- Final adjustments ---
        self.ax.set_xlabel('時間')
        self.ax.relim()
        self.ax.autoscale_view(tight=True)
        if self.ax2 and self.ax2.get_visible():
            self.ax2.relim()
            self.ax2.autoscale_view(tight=True)
        self.fig.tight_layout()
        self.canvas_plot.draw()

