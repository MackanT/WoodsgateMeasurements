import sqlite3
import os
import tkinter as tk
from tkinter import messagebox, filedialog as fd
import tkinter.font as tkFont
from functools import partial
import subprocess
import pandas as pd
from datetime import datetime, timedelta

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import (FigureCanvasTkAgg,
                                               NavigationToolbar2Tk)
import matplotlib.ticker as mticker

## TODO fix SCP/Paramiko 
# SCP data automatically
# import paramiko
# from scp import SCPClient


COLS = {
    "primary": "#333333",
    "secondary": "#666666",
    "background": "#FFFFFF",
    "accent": "#F7F7F7",
    "deep accent": "#444444",
    "success": "#8BC34A",
    "failure": "#FF3737"
}

DEFAULT_FILE_NAME = '5400_data.db'
PW_FILE = 'pw.txt'

# Screen Settings
root = tk.Tk()
root.title('Woodsgate Measurement Solutions')
root.geometry('1200x800')
root.resizable(False, False)


def open_database(file_name:str) -> sqlite3.Connection:
  
    if os.path.exists(file_name):
        print(f"Opening file {file_name}")
        conn = sqlite3.connect(file_name)
    else:
        conn = None
    
    return conn



def __get_font(size:int, bold:bool=False):
    if bold:
        return tkFont.Font(family="Bahnscrift", size=size, weight='bold')
    else:
        return tkFont.Font(family="Bahnscrift", size=size)

def __get_color(col:str) -> str:
    return COLS[col]

def __entry_int_check(var:tk.Entry, p:int, *args):
    value = var.get()
    
    # Ignore validation if the value is the placeholder
    if value == p:
        return
    
    if not value.isdigit():
        var.set(''.join(filter(str.isdigit, value)))
     
def __entry_date_check(var: tk.StringVar, p: str, *args):
    value = var.get()

    # Ignore validation if the value is the placeholder
    if value == p:
        return

    # Remove invalid characters (anything other than digits and '-')
    valid_chars = "0123456789-"
    cleaned_value = "".join(filter(lambda c: c in valid_chars, value))
    if cleaned_value != value:
        var.set(cleaned_value)
        return

    # Check if the value follows the `yyyy-mm-dd` format
    parts = cleaned_value.split("-")
    
    # Allow incomplete dates while typing (e.g., "2023-01")
    if len(parts) > 3 or any(len(part) > 4 for part in parts):  # Ensure proper lengths
        var.set(cleaned_value[:-1])
        return

    # Validate when the format is complete (e.g., "yyyy-mm-dd")
    if len(cleaned_value) == 10:  # Full date length in `yyyy-mm-dd` format
        try:
            datetime.strptime(cleaned_value, "%Y-%m-%d")  # Validate date
        except ValueError:
            var.set(cleaned_value[:-1])  # Remove last character if invalid
     
def validate_date(date:str) -> bool:
    if len(date) != 10:
        return False
    return True

# def SCP(self, canvas, txt):
#     if (port.get() == 'None' or proxy.get() == 'None'):
#         return
#     else:
#         client = paramiko.SSHClient()
#         client.load_system_host_keys()
#         client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
#         server = 'proxy{}.rt3.io'.format(proxy.get())
#         try:
#             client.connect(server, port.get(), username='admin',
#                             password=PW)
#             scp = SCPClient(client.get_transport())
#             scp.get("/home/admin/Documents/5400_data.txt")
#             client.close()
#             canvas.itemconfigure(
#                 txt, text='Successfully Downloaded Data', fill='#66ee66')
#         except:
#             canvas.itemconfigure(
#                 txt, text='Wrong Proxy/Port', fill='#ff1111')

def help():

    # Toplevel pop-up window
    top = get_top_level(title="Help", size="615x400", bg=__get_color('background'))
    
    frame = tk.Frame(top, bg=__get_color('background'), )
    frame.pack(fill='x')
    
    texts = [
        "*Password:",
        "If prompted, fill in the password for the RPI connection to allow for data dowloads. Erronous password can be updated in the file: '{PW_FILE}'. An error message will be given upn attemtping data download if the password is wrong, after changing it, a program restart is required.", 
        "*Load Data:",
        "The program will attempt to auto-load any existing 5400_data.db file in the root folder. If it exists the date ranges will be auto-populated with the first and last date with data. Pressing enter or the 'Update Graph'-button will plot the data. For larger sets of data, manually reducing the spann will speed up the process. If the file cannot be found in the root folder, a button will appear to manually find the file. Loading data in other locations is possible through 'file/Load Data'. After downloading new data, it will automatically be loaded into the program.",
        "*Local Instructions:",
        "Log on to the 'Woodsgate' network (both 2.4 and 5GHz work) and select 'file/Download Local Data'. A popup will appear which guides you through the process. After completion the new file will automatically be loaded into the program. If a failure occurs, a message will appear specifying what went wrong",
        "*Remote Instructions:",
        "Currently not enabled as device does not have a year-round internet signal",
        "*Additional Features",
        "Selecting 'File/Save to CSV' will save the current date selections data into a csv format for additional experimentation in excel."
    ]
    
    for i, t in enumerate(texts):
        
        if t[0] == "*":
            t = t[1:]
            
            l = tk.Label(frame, 
                        text=t, 
                        font=__get_font(12, True), 
                        fg=__get_color("primary"),
                        background=__get_color('background')
                        )
        else:
            l = tk.Message(frame,
                           text=t, 
                            font=__get_font(10), 
                            fg=__get_color("primary"),
                            background=__get_color('background'),
                            width=600
                           )
        l.grid(row=i, column=0, sticky="w")
    
    __add_cancel(top, text="Close")

def get_top_level(title:str, size:str='300x120', bg:str="#ffffff") -> tk.Toplevel:
    
    top = tk.Toplevel(root)
    top.geometry(size)
    top.config(bg=bg)
    top.title(title)
    top.resizable(False, False)
    
    return top


def __add_button(frame:tk.Toplevel, text:str, cmd, width:int=8, height:int=1, bg=None, fg=None, font=None, side:str="right", padx:int=10, pady:int=10) -> tk.Button:
        
    bg = bg or __get_color('deep accent')
    fg = fg or __get_color('accent')
    font = font or __get_font(10, True)
        
    button = tk.Button(
        frame, 
        text=text, 
        command=lambda: cmd(), 
        width=width, 
        height=height, 
        bg=bg, 
        fg=fg, 
        font=font, 
        relief='flat'
    )
    button.pack(side=side, padx=padx, pady=pady)
    
    return button

def __add_cancel(frame:tk.Toplevel, side:str='left', text:str='Cancel') -> None:

    __add_button(frame, text=text, cmd=frame.destroy, side=side)

def __add_entry(frame:tk.Toplevel, text_var:tk.StringVar, text:str, label:str, width:int=16) -> tk.Entry:    
    
    entry_frame = tk.Frame(frame, bg=__get_color('background'))
    entry_frame.pack(fill=tk.BOTH, expand=True)
    
    lab = tk.Label(
        entry_frame,
        fg=__get_color("primary"),
        background=__get_color('background'),
        text=label,
        font=__get_font(10)        
    )
    lab.pack(padx=10, pady=10, side="left")
    
    entry = tk.Entry(
            entry_frame, 
            fg=__get_color('deep accent'),
            background=__get_color('accent'), 
            textvariable=text_var if text_var else None,
            width=width,
            font=__get_font(10)
        )
    entry.insert(0, text)
    entry.bind("<FocusIn>", lambda event, p=text: __entry_on_focus_in(event, p))
    entry.bind("<FocusOut>", lambda event, p=text: __entry_on_focus_out(event, p))
    entry.pack(padx=10, pady=10, side="right")
    
    return entry

def __entry_on_focus_in(event, p:str):
    entry = event.widget
    if entry.get() == p:
        entry.delete(0, tk.END)  # Remove placeholder text
        entry.config(fg=__get_color("accent"))

def __entry_on_focus_out(event, p:str):
    entry = event.widget
    if entry.get() == "": # If entry is empty, reinsert placeholder
        entry.insert(0, p)
        entry.config(fg=__get_color("deep accent"))


def __download_local():
    global dl_label, __start
        
    dl_label.config(text="Download ongoing...", fg=__get_color("primary"))
    dl_label.update_idletasks()
    __start.config(state=tk.DISABLED)
    __start.update_idletasks()
    
    if conn:
        conn.close()
        
    cmd = f"pscp -P 22 -pw {PW} admin@192.168.1.74:/home/admin/Documents/5400_data.db {DEFAULT_FILE_NAME}"
    p = subprocess.Popen(cmd, stdin=None, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output, error = p.communicate()
    
    if error or len(output) == 0:
        dl_label.config(text=f"Download Failed: {output}", fg=__get_color('failure'))
    elif output == b'Access denied\r\nFATAL ERROR: Configured password was not accepted\r\n':
        dl_label.config(text="Download Failed: Wrong PW in file", fg=__get_color('failure'))
    else:
        dl_label.config(text="Download Successful", fg=__get_color('success'))
        __start.config(state=tk.NORMAL)
        load_data(DEFAULT_FILE_NAME)
        
    print('1')

def download_data_locally():
    global conn, dl_label, __start
    
    top = get_top_level("Download Local Data")
    dl_label = tk.Label(top, 
                        fg=__get_color("primary"),
                        background=__get_color('background'),
                        text="Download not started",
                        font=__get_font(12, True)
                    )
    dl_label.pack(padx=10, pady=20, side='top')
    __start = __add_button(top, "Download", __download_local)
    __add_cancel(top, text='Close')
    

    

def download_data():

    # Toplevel pop-up window
    top = get_top_level(title='Download Data from RPi', bg=__get_color('background'))
    
    t = "xxx.xxx.xx.x"
    text_var = tk.StringVar()
    text_var.trace_add("write", partial(__entry_int_check, text_var, t))
    entry_proxy = __add_entry(top, text_var, t, label="Proxy Server:")

    t = "xx"
    text_var = tk.StringVar()
    text_var.trace_add("write", partial(__entry_int_check, text_var, t))
    entry_port = __add_entry(top, text_var, t, label="Port Number:")
    
    __add_cancel(top)
    
    # top.bind('<Return>', lambda event: SCP(entry_proxy, entry_port))

    # download_button = tk.Button(
    #     top, 
    #     text="Download", 
    #     command=lambda: lambda: SCP(entry_proxy, entry_port), 
    #     width=8, 
    #     height=1, 
    #     bg=__get_color('green'), 
    #     fg=__get_color('white'), 
    #     font=__get_font(10, True), 
    #     relief='flat'
    # )
    # download_button.pack(padx=10, pady=10, side="left")

def load_data(filename:str=None):
    global df, conn
    
    if not filename:
        filetypes = (('database files', '*.db'),)
        filename = fd.askopenfilename(title='Open a file', filetypes=filetypes)
    
    conn = open_database(filename)
    if conn is None:
        return
    
    df = pd.read_sql("select * from data", conn)
    df['delta'] = df['level'].diff()
    
    min_date = df['time'].min()[:10]
    max_date = df['time'].max()[:10]
    
    entry_sd.delete(0, tk.END)
    entry_sd.insert(0, min_date)
    
    entry_ed.delete(0, tk.END)
    entry_ed.insert(0, max_date)
    
    # update_graph()
    
def get_entry_dates():
    
    d1 = entry_sd.get()
    d2 = entry_ed.get()
    if not validate_date(d1) or not validate_date(d2):
        return
    if d2 < d1:
        return
    
    d2_obj = datetime.strptime(d2, "%Y-%m-%d")
    d2_end = d2_obj + timedelta(days=1)
    d2 = d2_end.strftime('%Y-%m-%d')
    
    return d1, d2
    
def save_data():
    
    d1, d2 = get_entry_dates()
    
    df = pd.read_sql(f"select * from data where time between '{d1}' and '{d2}'", conn)
    file_name = f"csv\\5300_data-{d1}-{d2}.csv"
    if not os.path.exists("csv"):
        os.makedirs("csv")
    df.to_csv(file_name, index=False)
    
    messagebox.showinfo("Success", f"File saved as: {file_name}")
    
def smooth_data():
    
    ## Not implemented
    if globals().get('df') is None:
        print('Msg Box')
        return
    
    
    print('2') 
    1

def __save_pw():
    global entry_pw
    
    pw = entry_pw.get()
    with open(PW_FILE, "w") as f:
        f.writelines(pw)
        
    messagebox.showinfo('Success', f"Password stored in: {PW_FILE}")

def __add_pw():
    global entry_pw
    
    top = get_top_level("Missing PW File")
    
    t = "xxxxxxx"
    entry_pw = __add_entry(top, None, t, label="Password:")
    save_button = __add_button(top, "Save PW", __save_pw)
    entry_pw.bind(save_button.invoke)
    close = __add_cancel(top)

def switch_data():
    global data_plot_type
    
    if data_plot_type == 0:
       data_plot_type = 1
    elif data_plot_type == 1:
        data_plot_type = 0
        
    update_graph()

def update_graph(event=None):
    
    d1, d2 = get_entry_dates()
    
    tmp = df[(df['time'] >= d1) & (df["time"] <= d2)]
    
    tick_spacing = int(len(tmp)/5)
    if tick_spacing == 0:
        tick_spacing = 1
   
    if data_plot_type == 0:
       ydata = tmp['level']
       yleg = 'Level Over Time'
       xlabel = 'Level [m]'
       title = 'Water Level in Tank'
       ylim = 3.3
    elif data_plot_type == 1:
        ydata = tmp['volume']
        yleg = 'Volum Over Time'
        xlabel = 'Volume [m3]'
        title = 'Water Volume in Tank'
        ylim = 60
   
    plt.cla()
    plt.plot(tmp['time'], ydata, label=yleg)

    plt.grid(which="major")
    myLocator = mticker.MultipleLocator(tick_spacing)
    plt.xaxis.set_major_locator(myLocator)
    plt.tick_params(axis='x', rotation=45)
    plt.set_ylim(0, ylim)

    plt.set_ylabel(xlabel)
    plt.set_xlabel("Time")
    plt.set_title(title)

    fig.tight_layout()
    canvas.draw()


# Menu Bar
menu = tk.Menu(root)
root.config(menu=menu)

edit_menu = tk.Menu(menu, tearoff=0)
menu.add_cascade(label="File", menu=edit_menu)
edit_menu.add_command(label="Download Data", command=download_data)
edit_menu.add_command(label="Download Local Data", command=download_data_locally)
edit_menu.add_separator()
edit_menu.add_command(label="Load Database", command=load_data)
edit_menu.add_command(label="Save to csv", command=save_data)
edit_menu.add_command(label="How To Use", command=help)
edit_menu.add_separator()
edit_menu.add_command(label="Exit", command=root.quit)

frame = tk.Frame(root, bg=__get_color('background'), )
frame.pack(fill='x')

# Plot Area
fig = Figure(figsize=(12, 6), dpi=100)
plt = fig.add_subplot(111)
canvas = FigureCanvasTkAgg(fig, root)

toolbarFrame = tk.Frame(root)
toolbar = NavigationToolbar2Tk(canvas, toolbarFrame)
toolbarFrame.pack(side=tk.TOP, fill=tk.X)
canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.X)

# Load PW
if not os.path.exists(PW_FILE):
    __add_pw()
else:
    with open(PW_FILE, "r") as f:
        content = f.readlines() 
    PW = content[0]

# Control Area    
data_plot_type = 0
update_button = __add_button(frame, "Update Graph", cmd=update_graph, height=2, width=12, side="left")
# smooth_button = __add_button(frame, "Smooth Data", cmd=smooth_data, height=2, width=12, side="left")
volumt_button = __add_button(frame, "Volume", cmd=switch_data, height=2, width=12, side="left")

t = "yyyy-mm-dd"
text_var = tk.StringVar()
text_var.trace_add("write", partial(__entry_date_check, text_var, t))
entry_sd = __add_entry(frame, text_var, t, label="Start Date:")
entry_sd.pack(padx=10, pady=10, side="left")
entry_sd.bind("<Return>", lambda event=None: update_button.invoke())

text_var = tk.StringVar()
text_var.trace_add("write", partial(__entry_date_check, text_var, t))
entry_ed = __add_entry(frame, text_var, t, label="End Date:  ")
entry_ed.pack(padx=10, pady=10, side="left")
entry_ed.bind("<Return>", lambda event=None: update_button.invoke())

load_data(DEFAULT_FILE_NAME)

root.mainloop()
