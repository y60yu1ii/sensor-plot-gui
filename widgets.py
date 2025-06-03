from matplotlib.widgets import RangeSlider
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
import pandas as pd

class DateTimeRangeSlider(RangeSlider):
    def __init__(self, *args, t0=None, t1=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.t0 = t0
        self.t1 = t1
        self.ax.xaxis.set_major_formatter(ticker.FuncFormatter(self._format_datetime))
    def _format_datetime(self, x, pos=None):
        try:
            dt = pd.to_datetime(int(x), unit='s', utc=True).tz_convert('Asia/Taipei')
            return dt.strftime('%m-%d %H:%M')
        except Exception:
            return str(x)
