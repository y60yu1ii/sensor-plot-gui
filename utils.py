import tkinter as tk
from tkinter import filedialog
from tkcalendar import Calendar
from datetime import datetime

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
    return [col for col in df.columns if not col.startswith(('av-', 'p-', 'b-')) and col not in ('ID', 'Timestamp', 'Date', 'Time', 'Datetime')]

def state_color(state):
    """
    0開頭淡色，1開頭深色，預設 fallback 色。
    """
    if not isinstance(state, str):
        state = str(state)
    state = state.strip().lstrip("'").lstrip('"').rstrip("'").rstrip('"')
    
    if state in ['00', '01', '10', '11']:
        mapping = {
            '00': '#e6e6e6',   # 灰白
            '01': '#b3ffd9',   # 淡綠
            '10': '#99cfff',   # 淡藍
            '11': '#ff0000',   # 淡紅
        }
        return mapping[state]
    
    if len(state) == 4 and all(c in '01' for c in state):
        if state.startswith('0'):
            mapping = {
                '0000': '#f2f2f2',
                '0001': '#d1ffd6',
                '0010': '#cbe6ff', 
                '0011': '#ffecc2',   
                '0100': '#bff2fa',   
                '0101': '#c4f9cb',   
                '0110': '#d6d8ff',   
                '0111': '#fffacc',   
            }
            return mapping.get(state, '#d4edfa')
        elif state.startswith('1'):
            # 深色系
            mapping = {
                '1000': '#4fd0e9',   # 藍綠深
                '1001': '#44d18d',   # 深綠
                '1010': '#ffecc2',   # 深藍
                '1011': '#ffecc2',   # 橙
                '1100': '#ffb3b3',   # 深紅
                '1101': '#ff0000',   # 深紫
                '1110': '#ffecc2',   # 深粉紅
                '1111': '#ffecc2',   # 深橘
            }
            return mapping.get(state, '#d4edfa')  # 預設深藍
    # 其他（fallback）
    return '#f6ffed'
