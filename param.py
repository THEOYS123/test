#!/usr/bin/env python3
"""
Advanced Deep Parameter Finder
Deep crawling untuk mendeteksi URL dengan parameter (query string) atau seluruh URL,
dengan auto-install modul eksternal jika belum terpasang serta auto-detect & bypass WAF.
"""

import importlib.util
import subprocess
import sys

# Daftar modul yang wajib terpasang beserta nama paket pip-nya
required_packages = {
    "requests": "requests",
    "bs4": "beautifulsoup4",
    "rich": "rich"
}

def install(package):
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
    except Exception as e:
        print(f"Gagal menginstall {package}: {e}")
        sys.exit(1)

# Cek dan install modul yang belum terpasang
for module, package in required_packages.items():
    if importlib.util.find_spec(module) is None:
        print(f"Modul '{module}' tidak ditemukan. Menginstall {package}...")
        install(package)

# Setelah modul terpasang, import modul-modul yang diperlukan
import argparse
import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs
from random import choice, randint
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
import re
import string
import random
import time
import signal
import threading
from queue import Queue, Empty

console = Console()

# Variabel global untuk multi-threading
visited = set()
visited_lock = threading.Lock()
matching_urls = {}  # Format: { filter: set([url1, url2, ...]) }
matching_lock = threading.Lock()
url_queue = Queue()
stop_event = threading.Event()

# Session global untuk reuse koneksi
session = requests.Session()

# Global flag untuk mode bypass WAF
waf_mode = False

# Default User-Agent (jika file tidak ditemukan)
default_user_agents = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Linux; Android 10; SM-G970F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Mobile Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
]

def load_user_agents(filename="user-agent.txt"):
    """Muat daftar User-Agent dari file, jika gagal gunakan default."""
    try:
        with open(filename, "r", encoding="utf-8") as f:
            agents = [line.strip() for line in f if line.strip()]
        if agents:
            return agents
    except Exception as e:
        console.log(f"[yellow][INFO] Tidak dapat memuat '{filename}': {e}. Menggunakan default.[/yellow]")
    return default_user_agents

# Muat User-Agent dari file atau gunakan default
user_agents = load_user_agents()

# Extra headers untuk bypass 403/WAF
extra_headers = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Cache-Control': 'no-cache',
    'Pragma': 'no-cache',
    'DNT': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
}

# Header tambahan untuk bypass WAF
waf_bypass_headers = {
    'X-Bypass-WAF': 'True',
    'Cache-Control': 'no-cache',
    'Pragma': 'no-cache'
}

def signal_handler(sig, frame):
    """Menangani CTRL+C: tampilkan hasil dan simpan file hasil, lalu keluar."""
    console.print("\n[bold red][CTRL+C] Skrip dihentikan paksa oleh pengguna.[/bold red]")
    stop_event.set()
    display_results()
    save_results(current_domain, matching_urls, full_mode)
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def generate_random_parameter(length=10):
    """Menghasilkan string acak untuk parameter."""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def detect_waf(response):
    """
    Mendeteksi kemungkinan adanya WAF berdasarkan status code dan konten respons.
    Jika ditemukan indikasi WAF, kembalikan True.
    """
    waf_signatures = ["waf", "firewall", "access denied", "blocked", "captcha"]
    if response.status_code == 403:
        content = response.text.lower()
        for sig in waf_signatures:
            if sig in content:
                return True
    return False

def make_request(url, base_url):
    """
    Melakukan request dengan teknik bypass canggih:
      - Rotasi User-Agent
      - Header acak (X-Forwarded-For, Cookie, dll)
      - Jika WAF terdeteksi, aktifkan mode bypass dengan menambahkan header tambahan.
      - Delay dinamis jika mendeteksi 403/WAF.
    """
    global waf_mode
    for attempt in range(3):
        try:
            headers = {
                'User-Agent': choice(user_agents),
                'Referer': base_url,
                **extra_headers,
            }
            if waf_mode:
                headers.update(waf_bypass_headers)
            headers['X-Forwarded-For'] = '.'.join(str(random.randint(0, 255)) for _ in range(4))
            headers['Cookie'] = f"session={generate_random_parameter(16)}"
            response = session.get(url, timeout=15, headers=headers)
            if response.status_code == 403:
                if detect_waf(response):
                    waf_mode = True
                    console.log(f"[red][WAF] Terdeteksi WAF pada: {url}. Mengaktifkan mode bypass...[/red]")
                time.sleep(randint(10, 20))
                continue
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            console.log(f"[yellow][ERROR] Gagal mengakses {url}: {e} (percobaan {attempt+1})[/yellow]")
            time.sleep(randint(5, 10))
    return None

def has_query_parameter(url):
    """Mengembalikan True jika URL memiliki query string."""
    return '?' in url and '=' in url

def extract_urls(soup, base_url):
    """
    Mengekstrak URL dari berbagai tag HTML (misalnya <a>, <form>, <script>, <link>)
    dan mengembalikan list URL absolut.
    """
    urls = set()
    tags = {
        'a': 'href',
        'form': 'action',
        'script': 'src',
        'link': 'href'
    }
    for tag, attr in tags.items():
        for element in soup.find_all(tag):
            url = element.get(attr)
            if url:
                abs_url = urljoin(base_url, url)
                urls.add(abs_url)
    return list(urls)

def crawl_worker(base_url, filters, params_only, random_search, full_mode):
    """Worker thread untuk melakukan deep crawling pada domain target."""
    while not stop_event.is_set():
        try:
            current_url = url_queue.get(timeout=3)
        except Empty:
            break

        with visited_lock:
            if current_url in visited:
                url_queue.task_done()
                continue
            visited.add(current_url)

        console.log(f"[blue][SCAN] Memeriksa: {current_url}[/blue]")
        response = make_request(current_url, base_url)
        if response:
            try:
                soup = BeautifulSoup(response.text, 'html.parser')
            except Exception as e:
                console.log(f"[yellow][ERROR] Gagal parsing {current_url}: {e}[/yellow]")
                url_queue.task_done()
                continue

            new_urls = extract_urls(soup, base_url)
            for full_url in new_urls:
                parsed = urlparse(full_url)
                if parsed.netloc == urlparse(base_url).netloc:
                    with visited_lock:
                        if full_url not in visited:
                            url_queue.put(full_url)
                    # Jika mode full aktif, kumpulkan seluruh URL
                    if full_mode:
                        with matching_lock:
                            matching_urls.setdefault("FULL", set()).add(full_url)
                    else:
                        # Proses filter manual
                        for filter_type in filters:
                            if filter_type and isinstance(filter_type, str):
                                if re.search(re.escape(filter_type), full_url):
                                    if params_only and not has_query_parameter(full_url):
                                        break
                                    with matching_lock:
                                        matching_urls.setdefault(filter_type, set()).add(full_url)
                                    break
                        if random_search and has_query_parameter(full_url):
                            with matching_lock:
                                matching_urls.setdefault("ALL_PARAMS", set()).add(full_url)
        url_queue.task_done()

def crawl_website_mt(base_url, filters, threads, random_search, af_search, pr_search, full_mode):
    """
    Melakukan deep crawling dengan fitur:
      - Filter tambahan untuk admin finder dan parameter rentan.
      - Jika opsi -pr atau -random aktif, hanya URL dengan query disimpan.
      - Jika -random aktif, semua URL dengan parameter dikumpulkan di kategori ALL_PARAMS.
      - Jika -full aktif, seluruh URL yang ditemukan dikumpulkan di kategori FULL.
    """
    params_only = (pr_search or random_search) and not full_mode

    if af_search:
        admin_paths = [
            '/admin', '/admin.php', '/administrator', '/adminarea', '/wp-admin', '/cpanel',
            '/admin-login', '/adminpanel', '/admin-dashboard', '/controlpanel', '/login', '/admin_login'
        ]
        filters.extend(admin_paths)
        console.print("[bold yellow][INFO] Mencari halaman admin dengan filter yang relevan.[/bold yellow]")

    if random_search:
        console.print("[bold yellow][INFO] Mode filter random aktif: semua URL dengan parameter akan dikumpulkan di kategori [ALL_PARAMS].[/bold yellow]")
    if full_mode:
        console.print("[bold yellow][INFO] Mode full aktif: seluruh URL akan dikumpulkan di kategori [FULL].[/bold yellow]")

    url_queue.put(base_url)

    thread_list = []
    for _ in range(threads):
        t = threading.Thread(target=crawl_worker, args=(base_url, filters, params_only, random_search, full_mode), daemon=True)
        t.start()
        thread_list.append(t)

    url_queue.join()
    for t in thread_list:
        t.join(timeout=1)

    display_results()
    save_results(base_url, matching_urls, full_mode)

def display_results():
    """Menampilkan hasil crawling ke konsol."""
    console.print("\n[bold green][HASIL] URL yang ditemukan:[/bold green]")
    if matching_urls:
        for filter_type, urls in matching_urls.items():
            if urls:
                table = Table(title=f"Filter: {filter_type}", show_lines=True)
                table.add_column("No", justify="center", style="cyan", no_wrap=True)
                table.add_column("URL", justify="left", style="magenta")
                table.add_column("Parameters", justify="left", style="green")
                for i, url in enumerate(sorted(urls), 1):
                    query = urlparse(url).query
                    params = parse_qs(query) if query else {}
                    param_str = ", ".join([f"{k}={','.join(v)}" for k, v in params.items()]) if params else "-"
                    table.add_row(str(i), url, param_str)
                console.print(table)
    else:
        console.print("[yellow][INFO] Tidak ada URL yang cocok ditemukan.[/yellow]")

def save_results(base_url, results, full_mode):
    """
    Menyimpan hasil crawling ke file.
    Hasil disimpan di folder 'result/' dengan nama file berdasarkan domain target.
    Jika full_mode aktif, simpan seluruh URL; jika tidak, hanya simpan URL dengan query.
    Setiap URL disimpan satu baris (plain text).
    """
    parsed = urlparse(base_url)
    domain = parsed.netloc.replace(":", "_")
    result_folder = "result"
    os.makedirs(result_folder, exist_ok=True)
    filename = os.path.join(result_folder, f"{domain}.txt")
    
    with open(filename, "w", encoding="utf-8") as f:
        if results:
            for key, urls in results.items():
                for url in sorted(urls):
                    if full_mode:
                        f.write(url + "\n")
                    else:
                        if has_query_parameter(url):
                            f.write(url + "\n")
    console.print(f"[bold green][INFO] Hasil telah disimpan di: {filename}[/bold green]")

def show_help():
    console.print(Panel.fit("""
[bold yellow]Cara Penggunaan:[/bold yellow]
  python script.py [bold cyan]URL[/bold cyan] [opsi tambahan]

  Opsi-opsi:
    -f, --filter    : Menentukan filter parameter yang dicari (contoh: .php .html .json)
    -random         : Menggunakan filter random otomatis (mendeteksi URL dengan parameter)
    -af             : Mencari halaman admin (admin finder)
    -pr             : Mencari parameter rentan (hanya menyimpan URL dengan query)
    -full           : Mencari seluruh URL di website (deep full crawling)
    --threads       : Menentukan jumlah thread untuk crawling (default: 10)
    -h, --help      : Menampilkan panduan interaktif

[bold yellow]Contoh Penggunaan:[/bold yellow]
  python script.py https://example.com -f .php .html .json --threads 10
  python script.py https://example.com -pr
  python script.py https://example.com -random
  python script.py https://example.com -full
  python script.py https://example.com -f ?id= --threads 20
    """, title="[bold blue]Parameter Finder - Help[/bold blue]", border_style="bold green"))

def main():
    parser = argparse.ArgumentParser(
        description="Script untuk mencari parameter di website dengan filter canggih, multi-threaded, dan deep crawling.",
        add_help=False
    )
    parser.add_argument("url", nargs="?", help="URL target (contoh: https://example.com)")
    parser.add_argument("-f", "--filter", nargs="*", help="Jenis parameter yang dicari (contoh: .php .html .json)")
    parser.add_argument("-random", action="store_true", help="Menggunakan filter random otomatis (mendeteksi URL dengan parameter)")
    parser.add_argument("-af", action="store_true", help="Mencari halaman admin (admin finder)")
    parser.add_argument("-pr", action="store_true", help="Mencari parameter rentan (hanya menyimpan URL dengan query)")
    parser.add_argument("-full", action="store_true", help="Mencari seluruh URL di website (deep full crawling)")
    parser.add_argument("--threads", type=int, default=10, help="Jumlah thread untuk crawling (default: 10)")
    parser.add_argument("-h", "--help", action="store_true", help="Menampilkan panduan interaktif")

    args = parser.parse_args()

    if args.help or not args.url or (not args.filter and not args.random and not args.af and not args.pr and not args.full):
        show_help()
        return

    if not args.url.startswith(("http://", "https://")):
        console.print("[red][ERROR] Masukkan URL yang valid (harus diawali http:// atau https://)[/red]")
        return

    global current_domain
    current_domain = args.url

    filters = args.filter if args.filter else []
    console.print(f"[bold green][INFO] Memulai crawling untuk: {args.url}[/bold green]")

    # Flag full_mode untuk mode -full
    full_mode = args.full

    crawl_website_mt(args.url, filters, args.threads, random_search=args.random, af_search=args.af, pr_search=args.pr, full_mode=full_mode)

if __name__ == "__main__":
    main()
