import discord
import re
import subprocess
import threading
import time
import json
import customtkinter as ctk
from tkinter import messagebox
from plyer import notification
import traceback
from pystray import Icon, MenuItem, Menu
from PIL import Image, ImageDraw

CONFIG_FILE = "config.json"
ERROR_LOG = "logs.txt"


def log_error(error: Exception, context=""):
    full_trace = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    log_entry = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {context}\n{full_trace}\n{'-' * 60}\n"
    with open(ERROR_LOG, "a", encoding="utf-8") as f:
        f.write(log_entry)


def load_settings():
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except:
        return {"token": "", "delay": 0.5}


def save_settings(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=4)


def create_image():
    width = 64
    height = 64
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, width, height), fill="blue")
    return image


class RobloxSniperBot(discord.Client):
    def __init__(self, gui, channel_id, delay, **kwargs):
        super().__init__(**kwargs)
        self.gui = gui
        self.channel_id = int(channel_id)
        self.delay = delay
        self.reconnect_attempts = 0

    async def on_ready(self):
        self.gui.set_status(f"Logged in as {self.user.name}", "green")

    async def on_message(self, message):
        if message.channel.id == self.channel_id and "roblox.com" in message.content.lower():
            urls = re.findall(r"https?://(?:www\\.)?roblox\\.com[^\\s<>\"']+", message.content)
            for url in urls:
                try:
                    self.gui.set_status("Found Roblox link - joining...", "lime")
                    subprocess.Popen(["start", "", url], shell=True)
                    notification.notify(title="Joining Roblox Game", message=url, timeout=3)
                    time.sleep(self.delay)
                except Exception as e:
                    log_error(e, context=f"Error opening URL: {url}")

    async def on_disconnect(self):
        if self.reconnect_attempts < 5:
            self.reconnect_attempts += 1
            self.gui.set_status(f"Reconnecting ({self.reconnect_attempts})...", "orange")
            await self.connect(reconnect=True)
        else:
            self.gui.set_status("Max reconnect attempts reached", "red")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Roblox URL Sniper")
        self.geometry("600x350")
        self.resizable(False, False)

        try:
            self.iconbitmap("icon.ico")
        except Exception:
            pass

        self.settings = load_settings()
        self.bot_thread = None
        self.bot = None
        self.bot_running = False

        self.create_widgets()

    def create_widgets(self):
        self.tabs = ctk.CTkTabview(self)
        self.tabs.pack(fill="both", expand=True, padx=10, pady=10)
        self.tabs.add("Main")
        self.tabs.add("Settings")

        main_tab = self.tabs.tab("Main")
        ctk.CTkLabel(main_tab, text="Discord Channel ID:").pack(pady=(30, 5))
        self.channel_entry = ctk.CTkEntry(main_tab, width=300)
        self.channel_entry.pack()

        self.status_label = ctk.CTkLabel(main_tab, text="Status: Not running", text_color="red", font=ctk.CTkFont(size=16, weight="bold"))
        self.status_label.pack(pady=20)

        self.toggle_button = ctk.CTkButton(main_tab, text="Start Bot", command=self.toggle_bot, width=120)
        self.toggle_button.pack(pady=10)

        settings_tab = self.tabs.tab("Settings")
        ctk.CTkLabel(settings_tab, text="Discord Token:").pack(pady=(30, 5))
        self.token_entry = ctk.CTkEntry(settings_tab, width=400, show="*")
        self.token_entry.insert(0, self.settings.get("token", ""))
        self.token_entry.pack()

        ctk.CTkLabel(settings_tab, text="Delay before opening links (seconds):").pack(pady=(20, 5))
        self.delay_entry = ctk.CTkEntry(settings_tab, width=100)
        self.delay_entry.insert(0, str(self.settings.get("delay", 0.5)))
        self.delay_entry.pack()

        self.save_button = ctk.CTkButton(settings_tab, text="Save Settings", command=self.save_settings, width=120)
        self.save_button.pack(pady=20)

    def set_status(self, message, color="blue"):
        self.status_label.configure(text=f"Status: {message}", text_color=color)

    def save_settings(self):
        token = self.token_entry.get().strip()
        delay = self.delay_entry.get().strip()

        try:
            delay_val = float(delay)
            if delay_val < 0:
                raise ValueError("Delay can't be negative")
        except Exception:
            messagebox.showerror("Invalid Input", "Please enter a valid positive number for delay.")
            return

        if not token:
            messagebox.showerror("Missing Token", "Discord token cannot be empty.")
            return

        self.settings["token"] = token
        self.settings["delay"] = delay_val
        save_settings(self.settings)
        messagebox.showinfo("Saved", "Settings saved successfully.")
        self.set_status("Settings saved!", "green")

    def toggle_bot(self):
        if self.bot_running:
            self.stop_bot()
        else:
            self.start_bot()

    def start_bot(self):
        channel_id = self.channel_entry.get().strip()
        token = self.settings.get("token", "").strip()

        if not channel_id or not token:
            messagebox.showerror("Missing Info", "Please fill in both Channel ID and Token.")
            return

        if self.bot_thread and self.bot_thread.is_alive():
            messagebox.showinfo("Running", "The bot is already running.")
            return

        self.set_status("Starting the bot...", "orange")

        def bot_runner():
            try:
                self.bot = RobloxSniperBot(gui=self, channel_id=channel_id, delay=self.settings.get("delay", 0.5))
                self.bot_running = True
                self.toggle_button.configure(text="Stop Bot")
                self.bot.run(token)
            except Exception as e:
                log_error(e, context="Bot failed to start")
                self.set_status("Bot failed to start", "red")
                messagebox.showerror("Error", f"Could not start bot:\n{e}")
                self.bot_running = False
                self.toggle_button.configure(text="Start Bot")

        self.bot_thread = threading.Thread(target=bot_runner, daemon=True)
        self.bot_thread.start()

    def stop_bot(self):
        if self.bot:
            try:
                self.bot.loop.call_soon_threadsafe(self.bot.close)
                self.set_status("Bot stopped.", "red")
                self.bot_running = False
                self.toggle_button.configure(text="Start Bot")
            except Exception as e:
                log_error(e, context="Error stopping bot")
                messagebox.showerror("Error", f"Could not stop bot:\n{e}")
        else:
            messagebox.showinfo("Not Running", "The bot is not currently running.")

    def on_close(self):
        self.withdraw()
        self.show_tray_icon()
        notification.notify(title="Minimized to Tray", message="The bot is still running in the tray.", timeout=4)

    def show_tray_icon(self):
        def quit_action(icon, item):
            icon.stop()
            self.quit()

        menu = Menu(MenuItem("Quit", lambda icon, item: quit_action(icon, item)))
        icon = Icon("Roblox Sniper Bot", create_image(), menu=menu)
        threading.Thread(target=icon.run, daemon=True).start()


if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
