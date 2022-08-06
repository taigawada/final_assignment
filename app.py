from pyngrok import conf, ngrok, installer
import os
import stat
from flask import Flask, request, abort
import datetime
import asyncio
import tkinter as tk
from tkinter import messagebox
from tkinter import filedialog
from PIL import ImageTk
import json
import ssl
from logging import config
import time
import usb
from escpos.printer import Usb
import csv
import numpy as np

from middleware.environment_settings import Env
from middleware.save_log import to_csv

def resource_path(filename):
    return os.path.join(os.path.abspath("."), filename)

#my src files
from src.webhook_subscription import WebhookSubscription
from src.escpos_print import print_main, preview_create

# logging settings
from middleware.log_util import StringHandler
config.dictConfig({
    'version': 1,
    'formatters': {
        'simple': {
            'format': '%(message)s'
        }
    },
    'handlers': {
        'string': {
            'class': 'middleware.log_util.StringHandler',
            'formatter': 'simple'
        }
    },
    'root': {
        'level': 'INFO',
        'handlers': ['string']
    }
})

def flask_logger():
    while True:
        current_log = StringHandler.str_io.getvalue()
        time.sleep(0.1)
        log.config(text=current_log.replace('(Press CTRL+C to quit)', ''))

# global var
app = Flask(__name__)
ngrok_https_url = None
app_name: str = 'clpos'
settings: Env = None
printer_is_con = False
printer = None
log_file_name: str = None
footer_image_path = None
probably = None
debug_mode = False

def find_app_file():
    current_path = os.path.expanduser('~')
    fullpath = os.path.join(current_path,'Library','Application Support',app_name)
    if not os.path.isfile(fullpath + '/.env'):
        if not os.path.isdir(fullpath):
            os.makedirs(fullpath, exist_ok=True)
            os.chmod(fullpath, 0o744)
        f = open(os.path.join(fullpath,'.env.txt'), 'w')
        f.write("PORT='4000'\n")
        f.write("SAVE_PATH=''\n")
        f.write("FOOTER_PATH=''\n")
        f.write("MY_SERVER_URL='https://hogehoge.com/'\n")
        f.write("LUCKEY_PROBABLY='25'\n")
        f.write("WEBHOOK_SECRET_KEY='ae0d02ff9dc81bb9c570d95d15ad5264b71ed8a14703b81dcee819530426625e'\n")
        f.write("VENDER_ID=''\n")
        f.write("PRODUCT_ID=''\n")
        f.close()
        os.rename(os.path.join(fullpath,'.env.txt'), os.path.join(fullpath,'.env'))
    conf.get_default().ngrok_path = os.path.join(fullpath, 'ngrok')
    global settings
    settings = Env(fullpath)

def json_fix_indent(jsonText):
    try:
        return json.dumps(jsonText, indent=2, ensure_ascii=False)
    except json.JSONDecodeError:
        return ''

@app.route('/recieve_json',methods=['POST'])
def webhook_recieve():
    # verified = verifyRequest(request, settings)
    verified = True
    if not verified:
        abort(401)
    json_data = request.get_json()
    if json_data["source_name"] == 'pos':
        if probably != 0:
            prob_list = [1/probably, 1 - (1/probably)]
            is_luckey = np.random.choice(a=[True, False], size=1, p=prob_list)[0]
        else:
            is_luckey = False
        if csv_save.get():
            try:
                to_csv(log_file_name, json_data, is_luckey)
            except Exception as e:
                print(e)
        try:
            asyncio.new_event_loop().run_in_executor(None, lambda: print_main(json_data, printer, footer_image_path, is_luckey))
            return 'success', 200
        except Exception as e:
            print(e)
            return 'success', 200
    else:
        return 'success', 200


def start_ngrok(port):
    ngrok.kill()
    ngrok.connect(port, 'http')
    tunnels: list[ngrok.NgrokTunnel] = ngrok.get_tunnels()
    for ngrok_tunnel in tunnels:
        if 'https://' in ngrok_tunnel.public_url:
            global ngrok_https_url
            ngrok_https_url = ngrok_tunnel.public_url
    return

def create_server_sync():
    port_number = settings.get('PORT')
    start_ngrok(port_number)
    if ngrok_https_url is None:
        messagebox.showerror('エラー','failed to start tunnels.')
    if debug_mode == True:
        webhook_subscription_succcess = True
    else:
        webhook_subscription_succcess = WebhookSubscription(settings, ngrok_https_url).create().success()
    if webhook_subscription_succcess:
        sample_json = json.dumps(json.loads(open(resource_path('sample.json'), 'r').read()),separators=(',', ':'))
        sample_cmd.insert(tk.END,
        '''curl -X POST -H "Content-Type: application/json" -d '%s' %s/recieve_json'''%(sample_json, ngrok_https_url))
        server_status_page.tkraise()
        start_btn["state"] = tk.ACTIVE
        start_btn.config(text='起動')
        start_btn.update_idletasks()
        app.run(port=int(port_number))
    else:
        messagebox.showerror('エラー','webhook subscription failed')
        start_btn["state"] = tk.ACTIVE
        start_btn.update_idletasks()

def create_server():
    start_btn["state"] = tk.DISABLED
    try:
        global probably
        probably = int(probability_input.get())
        if probably >= 0:
            settings.changeENV('LUCKEY_PROBABLY', str(probably))
        else:
            raise ValueError('xxx')
    except Exception as e:
        messagebox.showerror('エラー', '当たりの確率が無効です')
        start_btn["state"] = tk.ACTIVE
        start_btn.update_idletasks()
        return
    if not port_input.get():
        messagebox.showerror('エラー', 'ポート番号が未設定です')
        start_btn["state"] = tk.ACTIVE
        start_btn.update_idletasks()
        return
    if not printer_is_con:
        messagebox.showerror('エラー', 'プリンターが未接続です')
        start_btn["state"] = tk.ACTIVE
        start_btn.update_idletasks()
        return
    try:
        sixteen_vender_id = int(settings.get('VENDER_ID'), 16)
        sixteen_product_id = int(settings.get('PRODUCT_ID'), 16)
    except ValueError:
        start_btn["state"] = tk.ACTIVE
        start_btn.update_idletasks()
        return None
    try:
        if debug_mode == True:
            pass
        else:
            global printer
            printer = Usb(sixteen_vender_id, sixteen_product_id, 0)
    except Exception as e:
        messagebox.showerror('エラー',e)
        start_btn["state"] = tk.ACTIVE
        start_btn.update_idletasks()
        return
    if not save_dir_input.get():
        csv_save.set(False)
    now_date = datetime.datetime.now()
    if csv_save.get():
        global log_file_name
        if save_dir_input.get() != settings.get('SAVE_PATH'):
            settings.changeENV('SAVE_PATH', save_dir_input.get())
        log_file_name = os.path.join(settings.get('SAVE_PATH'),now_date.strftime('%Y-%m-%dT%H:%M:%S.csv'))
        log_file = open(log_file_name, 'a')
        csv.writer(log_file).writerow(['注文番号', '販売', '注文日時', '商品名', 'バリエーション', '数量', '価格', '割引', '小計', '割引', '合計', '当たり'])
        log_file.close()
    pyngrok_config_path: str = conf.get_default().ngrok_path
    if not os.path.exists(pyngrok_config_path):
        start_btn.config(text='ngrok downloading...')
        start_btn.update_idletasks()
        myssl = ssl.create_default_context()
        myssl.check_hostname = False
        myssl.verify_mode = ssl.CERT_NONE
        installer.install_ngrok(pyngrok_config_path.replace('ngrok', ''), context = myssl)
        os.chmod(pyngrok_config_path, stat.S_IXUSR)
    start_btn.config(text='now starting...')
    start_btn.update_idletasks()
    if (port_input.get() != settings.get('PORT')):
        settings.changeENV('PORT', port_input.get())
    logging_loop = asyncio.new_event_loop()
    logging_loop.call_soon(flask_logger)
    logging_loop.run_in_executor(None, flask_logger)
    server_loop = asyncio.new_event_loop()
    server_loop.call_soon(create_server_sync)
    server_loop.run_in_executor(None, create_server_sync)
    return

def on_exit():
    ngrok.kill()
    if ngrok_https_url is not None and debug_mode != True:
        WebhookSubscription(settings, ngrok_https_url).delete()
    os._exit(0) # flask is allowed only _exit of os module.

def usb_printer_connct(vender_id, product_id):
    if vender_id is None or product_id is None:
        return None
    try:
        sixteen_vender_id = int(vender_id, 16)
        sixteen_product_id = int(product_id, 16)
    except ValueError:
        return None
    device = usb.core.find(idVendor=sixteen_vender_id, idProduct=sixteen_product_id)
    if device is None:
        return None
    else:
        device_name = usb.util.get_string(device, 2)
        if device.bDeviceClass != 7: # todo !=　を == に
                return device_name
        for cfg in device:
            if usb.util.find_descriptor(cfg, bInterfaceClass=7) is not None:
                return device_name

def initial_printer_connect(vender_id, product_id):
    res = usb_printer_connct(vender_id, product_id)
    global printer_is_con
    if res is None:
        printer_is_con = False
        return
    else:
        printer_info.config(text='接続済み: {}'.format(res))
        printer_is_con = True

def footer_img_dialog():
    path = settings.get('FOOTER_PATH')
    if not os.path.isdir(path):
        path = os.path.expanduser('~')
    iDir = os.path.abspath(path)
    image_path = filedialog.askopenfilename(title="ファイル選択", initialdir=iDir, filetypes=[("Image File","*.png"), ("Image File","*.jpg")])
    if image_path:
        global footer_image_path
        footer_image_path = image_path
        settings.changeENV('FOOTER_PATH', image_path)
        select_image.insert(0, image_path)

def save_path_dialog():
    path = settings.get('SAVE_PATH')
    if not os.path.isdir(path):
        path = os.path.expanduser('~')
    iDir = os.path.abspath(path)
    iDirPath = filedialog.askdirectory(initialdir = iDir)
    if iDirPath:
        settings.changeENV('SAVE_PATH', iDirPath)
        save_dir_input.delete(0,tk.END)
        save_dir_input.insert(0, iDirPath)

def copy_to_clipboard():
    root.clipboard_clear()
    root.clipboard_append(sample_cmd.get())

def create_usb_setting_modal():
    def printer_connect(vender_id, product_id):
        global printer_is_con
        if vender_id == '0x0000' and product_id =='0x0000':
            printer_name.config(text='デバッグモード', foreground='blue')
            printer_name.update_idletasks()
            printer_is_con = True
            global debug_mode
            debug_mode = True
            dlg_modal.destroy()
        else:
            res = usb_printer_connct(vender_id, product_id)
            if res is None:
                messagebox.showerror('エラー', 'プリンターに接続できません')
                start_btn["state"] = tk.ACTIVE
                start_btn.update_idletasks()
            else:
                printer_name.config(text=res, foreground='green')
                printer_name.update_idletasks()
                settings.changeENV('VENDER_ID', vender_id)
                settings.changeENV('PRODUCT_ID', product_id)
                printer_is_con = True
                dlg_modal.destroy()
    dlg_modal = tk.Toplevel()
    dlg_modal.title("プリンター接続設定")
    dlg_modal.geometry("500x400")
    dlg_modal.grab_set()
    dlg_modal.focus_set()
    dlg_modal.transient(root)
    titleLabel = tk.Label(dlg_modal, text='プリンターと接続します', font=('Helvetica', '15'))
    titleLabel.pack(pady=10)
    product_id_text = tk.Label(dlg_modal, text='製品ID')
    product_id_text.pack(anchor=tk.W, pady=3)
    product_id_input = tk.Entry(dlg_modal, width=40)
    product_id_input.insert(0,settings.get('PRODUCT_ID'))
    product_id_input.pack(pady=3)
    vender_id_text = tk.Label(dlg_modal, text='製造元ID')
    vender_id_text.pack(anchor=tk.W, pady=3)
    vender_id_input = tk.Entry(dlg_modal, width=40)
    vender_id_input.insert(0,settings.get('VENDER_ID'))
    vender_id_input.pack(pady=3)
    connect_btn = tk.Button(dlg_modal, text="接続", command=lambda:printer_connect(vender_id_input.get(), product_id_input.get()), padx=14, pady=5)
    connect_btn.pack(pady=5)

def receipt_preview_modal():
    preview_image = preview_create(footer_image_path)
    pre_width, pre_height = preview_image.size
    preview_modal = tk.Toplevel()
    preview_modal.title("プレビュー")
    preview_modal.geometry("{0}x{1}".format(pre_width+20, scr_height))
    global tk_pre_image
    tk_pre_image = ImageTk.PhotoImage(image=preview_image)
    canvas = tk.Canvas(preview_modal, width=pre_width, height=scr_height)
    canvas.configure(scrollregion=(0,0,0,int(pre_height)+150))
    canvas.create_image(pre_width//2, pre_height//2, image=tk_pre_image)
    scrollbar = tk.Scrollbar(preview_modal, orient=tk.VERTICAL, command=canvas.yview)
    canvas["yscrollcommand"] = scrollbar.set
    canvas.grid(row=0, column=0)
    scrollbar.grid(row=0, column=1,sticky=tk.N + tk.S)
    preview_modal.grab_set()
    preview_modal.focus_set()
    preview_modal.transient(root)

# file initialize
find_app_file()
if (settings.get('VENDER_ID') != '' and settings.get('PRODUCT_ID') != ''):
    initial_printer_connect(settings.get('VENDER_ID'), settings.get('PRODUCT_ID'))

root = tk.Tk()
root.title(app_name)
scr_width = root.winfo_screenwidth()
scr_height = root.winfo_screenheight()
root.minsize(width=800, height=450)
root.geometry("{0}x{1}".format(scr_width, scr_height))
root.grid_rowconfigure(0, weight=1)
root.grid_columnconfigure(0, weight=1)
root.protocol("WM_DELETE_WINDOW", on_exit)

#landing page
landing_page = tk.Frame()
landing_page.grid(row=0, column=0, sticky="nsew")
landing_page.grid_columnconfigure(0, weight=5)
landing_page.grid_columnconfigure(1, weight=1)
landing_page.grid_columnconfigure(2, weight=5)
landing_page.grid_columnconfigure(3, weight=1)
landing_page.grid_columnconfigure(4, weight=5)

titleLabel = tk.Label(landing_page, text='設定', font=('Helvetica', '25'))
printer_info = tk.Label(landing_page, text="プリンター", font=('Helvetica', '18'))
printer_name = tk.Label(landing_page, text="未接続", foreground='red', font=('Helvetica', '18'))
printer_con = tk.Button(landing_page, text='プリンター接続', command=create_usb_setting_modal)
footer_img_select = tk.Label(landing_page, text="フッター画像選択", font=('Helvetica', '18'))
footer_img_btn = tk.Button(landing_page, text="選択", command=footer_img_dialog)
select_image = tk.Entry(landing_page)
default_footer_path = settings.get('FOOTER_PATH')
if os.path.exists(default_footer_path):
    footer_image_path = default_footer_path
    select_image.config(text=default_footer_path)
    select_image.update_idletasks()
preview_btn = tk.Button(landing_page, text="プレビュー", command=receipt_preview_modal, padx=14, pady=5)
probability_title = tk.Label(landing_page, text='当たりの確率', font=('Helvetica', '18'))
probability_input = tk.Entry(landing_page)
probability_input.insert(0, int(settings.get('LUCKEY_PROBABLY')))
probability_safix = tk.Label(landing_page, text='人に1人')
save_dir_text = tk.Label(landing_page, text="ログ保存先", font=('Helvetica', '18'))
save_dir_input = tk.Entry(landing_page)
save_dir_input.insert(0, settings.get('SAVE_PATH'))
save_dir_btn = tk.Button(landing_page, text="選択", command=save_path_dialog)
csv_save = tk.BooleanVar()
csv_save.set(True)
csv_save_check = tk.Checkbutton(landing_page, variable=csv_save, text='CSVファイルを保存')
port_text = tk.Label(landing_page, text="port番号", font=('Helvetica', '18'))
port_input = tk.Entry(landing_page)
port_input.insert(0, settings.get('PORT'))
start_btn = tk.Button(landing_page, text="起動", command=create_server, padx=14, pady=5)

# Layout
titleLabel.grid(row=0, column=1, sticky=tk.W, pady=15)
printer_info.grid(row=1, column=1, sticky=tk.W, pady=5)
printer_name.grid(row=1, column=2, sticky=tk.W)
printer_con.grid(row=1, column=3, sticky=tk.W)
footer_img_select.grid(row=2, column=1, sticky=tk.W, pady=5)
select_image.grid(row=2, column=2, sticky=tk.EW)
footer_img_btn.grid(row=2, column=3, sticky=tk.W)
probability_title.grid(row=3, column=1, sticky=tk.W, pady=5)
probability_input.grid(row=3, column=2, sticky=tk.EW)
probability_safix.grid(row=3, column=3, sticky=tk.W)
save_dir_text.grid(row=4, column=1, sticky=tk.W, pady=5)
save_dir_input.grid(row=4, column=2, sticky=tk.EW)
save_dir_btn.grid(row=4, column=3, sticky=tk.W)
csv_save_check.grid(row=5, column=2, pady=5)
port_text.grid(row=6, column=1, sticky=tk.W, pady=5)
port_input.grid(row=6, column=2, sticky=tk.EW)
preview_btn.grid(row=7, column=2)
start_btn.grid(row=8, column=2)

#server_status_page
server_status_page = tk.Frame()
server_status_page.grid(row=0, column=0, sticky=tk.NSEW)

sample_cmd_text = tk.Label(server_status_page, text='サンプルコマンド(ターミナルで実行してください)')
sample_cmd = tk.Entry(server_status_page)
copy_btn = tk.Button(server_status_page, text="コピー", command=copy_to_clipboard, padx=14, pady=5)
log_text = tk.Label(server_status_page, text='ログ')
log = tk.Label(server_status_page, text='')
stop_btn = tk.Button(server_status_page, text="終了", command=on_exit, padx=14, pady=5)

# Layout
stop_btn.pack(anchor=tk.E, pady=30)
sample_cmd_text.pack()
sample_cmd.pack(pady=3, fill=tk.X)
copy_btn.pack(pady=3)
log_text.pack(pady=15)
log.pack(pady=5)


landing_page.tkraise()
root.update_idletasks()
root.mainloop()