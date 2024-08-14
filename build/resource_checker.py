import psutil
from telegram import Bot
from telegram.error import TelegramError
import time
import os
from datetime import datetime
import logging
import gc

# Cấu hình logging
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s %(levelname)s:%(message)s',
    handlers=[
        logging.FileHandler("/app/data/resource_checker.log"),
        logging.StreamHandler()
    ]
)

# Đọc thông tin từ biến môi trường
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', 'YOUR_TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID', 'YOUR_TELEGRAM_CHAT_ID')
CPU_THRESHOLD = float(os.getenv('CPU_THRESHOLD', 70))
RAM_THRESHOLD = float(os.getenv('RAM_THRESHOLD', 70))
HDD_THRESHOLD = float(os.getenv('HDD_THRESHOLD', 70))
TRANSFER_THRESHOLD = float(os.getenv('TRANSFER_THRESHOLD', 5)) * (1024**4)
DELAY_SECONDS = float(os.getenv('DELAY_SECONDS', 5))
COOLDOWN_SECONDS = float(os.getenv('COOLDOWN_SECONDS', 300))
TRANSFER_CHECK_INTERVAL = 1
TRANSFER_SAVE_INTERVAL = 60

# Kiểm tra token và chat ID
if not TELEGRAM_TOKEN or not CHAT_ID:
    logging.error("TELEGRAM_TOKEN hoặc CHAT_ID không được thiết lập.")
    exit(1)

# Khởi tạo bot
bot = Bot(token=TELEGRAM_TOKEN)

# Đường dẫn tới tệp tin lưu trữ dữ liệu transfer
TRANSFER_FILE = '/app/data/transfer_usage.txt'
LAST_MONTH_FILE = '/app/data/last_month.txt'

# Thời gian bắt đầu vượt ngưỡng
cpu_threshold_time = 0
ram_threshold_time = 0
hdd_threshold_time = 0
transfer_threshold_time = 0

# Thời gian gửi thông báo gần nhất
last_cpu_notification = 0
last_ram_notification = 0
last_hdd_notification = 0
last_transfer_notification = 0

# Lưu trữ số liệu transfer trong bộ nhớ
total_transfer_usage = 0
last_transfer_check_time = time.time()
last_transfer_save_time = time.time()

def send_telegram_message(message):
    try:
        bot.send_message(chat_id=CHAT_ID, text=message)
        logging.info(f"Đã gửi thông báo: {message}")
    except TelegramError as e:
        logging.error(f"Lỗi khi gửi tin nhắn: {e}")

def get_transfer_usage():
    try:
        net_before = psutil.net_io_counters()
        time.sleep(1)
        net_after = psutil.net_io_counters()
        sent_bytes = net_after.bytes_sent - net_before.bytes_sent
        recv_bytes = net_after.bytes_recv - net_before.bytes_recv
        return sent_bytes + recv_bytes
    except Exception as e:
        logging.error(f"Lỗi khi lấy số liệu transfer: {e}")
        return 0

def load_transfer_usage():
    if os.path.exists(TRANSFER_FILE):
        try:
            with open(TRANSFER_FILE, 'r') as file:
                return float(file.read().strip())
        except Exception as e:
            logging.error(f"Lỗi khi đọc dữ liệu transfer: {e}")
    return 0

def save_transfer_usage(usage):
    try:
        with open(TRANSFER_FILE, 'w') as file:
            file.write(f"{usage}")
    except Exception as e:
        logging.error(f"Lỗi khi lưu dữ liệu transfer: {e}")

def load_last_month():
    if os.path.exists(LAST_MONTH_FILE):
        try:
            with open(LAST_MONTH_FILE, 'r') as file:
                return file.read().strip()
        except Exception as e:
            logging.error(f"Lỗi khi đọc tháng trước: {e}")
    return ""

def save_last_month(month):
    try:
        with open(LAST_MONTH_FILE, 'w') as file:
            file.write(month)
    except Exception as e:
        logging.error(f"Lỗi khi lưu tháng trước: {e}")

def log_memory_usage():
    try:
        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()
        logging.info(f"Mức sử dụng bộ nhớ: {mem_info.rss / (1024**2):.2f} MB")
    except Exception as e:
        logging.error(f"Lỗi khi kiểm tra mức sử dụng bộ nhớ: {e}")

def check_resources():
    global cpu_threshold_time, ram_threshold_time, hdd_threshold_time, transfer_threshold_time
    global last_cpu_notification, last_ram_notification, last_hdd_notification, last_transfer_notification
    global total_transfer_usage, last_transfer_check_time, last_transfer_save_time

    current_time = time.time()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Kiểm tra CPU
    cpu_usage = psutil.cpu_percent(interval=1)
    if cpu_usage > CPU_THRESHOLD:
        if cpu_threshold_time == 0:
            cpu_threshold_time = current_time
        elif current_time - cpu_threshold_time >= DELAY_SECONDS:
            if current_time - last_cpu_notification >= COOLDOWN_SECONDS:
                message = (f"Cảnh báo: Sử dụng CPU đạt {cpu_usage}%\n"
                           f"Ngưỡng cảnh báo: {CPU_THRESHOLD}%\n"
                           f"Thời gian vượt ngưỡng: {int(current_time - cpu_threshold_time)} giây")
                send_telegram_message(message)
                last_cpu_notification = current_time
            cpu_threshold_time = current_time
    else:
        cpu_threshold_time = 0

    # Kiểm tra RAM
    ram_usage = psutil.virtual_memory().percent
    if ram_usage > RAM_THRESHOLD:
        if ram_threshold_time == 0:
            ram_threshold_time = current_time
        elif current_time - ram_threshold_time >= DELAY_SECONDS:
            if current_time - last_ram_notification >= COOLDOWN_SECONDS:
                message = (f"Cảnh báo: Sử dụng RAM đạt {ram_usage}%\n"
                           f"Ngưỡng cảnh báo: {RAM_THRESHOLD}%\n"
                           f"Thời gian vượt ngưỡng: {int(current_time - ram_threshold_time)} giây")
                send_telegram_message(message)
                last_ram_notification = current_time
            ram_threshold_time = current_time
    else:
        ram_threshold_time = 0

    # Kiểm tra HDD
    disk_usage = psutil.disk_usage('/').percent
    if disk_usage > HDD_THRESHOLD:
        if hdd_threshold_time == 0:
            hdd_threshold_time = current_time
        elif current_time - hdd_threshold_time >= DELAY_SECONDS:
            if current_time - last_hdd_notification >= COOLDOWN_SECONDS:
                message = (f"Cảnh báo: Sử dụng HDD đạt {disk_usage}%\n"
                           f"Ngưỡng cảnh báo: {HDD_THRESHOLD}%\n"
                           f"Thời gian vượt ngưỡng: {int(current_time - hdd_threshold_time)} giây")
                send_telegram_message(message)
                last_hdd_notification = current_time
            hdd_threshold_time = current_time
    else:
        hdd_threshold_time = 0

    # Kiểm tra Transfer
    if current_time - last_transfer_check_time >= TRANSFER_CHECK_INTERVAL:
        transfer_usage = get_transfer_usage()
        total_transfer_usage += transfer_usage

        # Kiểm tra tháng hiện tại
        current_month = datetime.now().strftime("%Y-%m")
        last_month = load_last_month()

        if current_month != last_month:
            total_transfer_usage = 0
            save_transfer_usage(0)
            save_last_month(current_month)

        if total_transfer_usage > TRANSFER_THRESHOLD:
            if transfer_threshold_time == 0:
                transfer_threshold_time = current_time
            elif current_time - transfer_threshold_time >= DELAY_SECONDS:
                if current_time - last_transfer_notification >= COOLDOWN_SECONDS:
                    message = (f"Cảnh báo: Sử dụng Transfer đạt {total_transfer_usage / (1024**4):.2f} TB\n"
                               f"Ngưỡng cảnh báo: {TRANSFER_THRESHOLD / (1024**4):.2f} TB\n"
                               f"Thời gian vượt ngưỡng: {int(current_time - transfer_threshold_time)} giây")
                    send_telegram_message(message)
                    last_transfer_notification = current_time
                transfer_threshold_time = current_time
        else:
            transfer_threshold_time = 0

        last_transfer_check_time = current_time

    # Lưu số liệu transfer usage vào file mỗi 60 giây
    if current_time - last_transfer_save_time >= TRANSFER_SAVE_INTERVAL:
        save_transfer_usage(total_transfer_usage)
        last_transfer_save_time = current_time

def main_loop():
    while True:
        check_resources()
        log_memory_usage()
        time.sleep(1)

if __name__ == "__main__":
    try:
        total_transfer_usage = load_transfer_usage()
        last_transfer_save_time = time.time()
        main_loop()
    except Exception as e:
        logging.error(f"Lỗi trong quá trình kiểm tra: {e}")
