import psutil
import sys

def kill_processes():
    targets = ['server.py', 'main.py', 'launcher.py']
    killed = False
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info['cmdline']
            if cmdline:
                flat_cmd = ' '.join(cmdline)
                for target in targets:
                    if target in flat_cmd and 'kill_processes.py' not in flat_cmd:
                        print(f"DTO Killing process {proc.info['pid']}: {flat_cmd}")
                        proc.kill()
                        killed = True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    
    if not killed:
        print("No matching processes found.")

if __name__ == "__main__":
    kill_processes()
