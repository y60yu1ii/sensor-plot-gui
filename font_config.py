import matplotlib
from matplotlib import font_manager

def set_chinese_font():
    font_candidates = [
        "Microsoft JhengHei", "Noto Sans CJK TC", "Noto Sans TC",
        "Heiti TC", "STHeiti", "PingFang TC", "Arial Unicode MS",
    ]
    for font in font_candidates:
        if any(font in f.name for f in font_manager.fontManager.ttflist):
            matplotlib.rc('font', family=font)
            print(f"使用字型: {font}")
            break
    matplotlib.rcParams['axes.unicode_minus'] = False
