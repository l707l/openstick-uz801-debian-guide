import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.200.1', 22, 'user', '1')

def sudo_cmd(cmd):
    print(f">> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(f"echo 1 | sudo -S {cmd}")
    out = stdout.read().decode('utf-8', errors='ignore')
    err = stderr.read().decode('utf-8', errors='ignore')
    if out:
        print(out.strip())
    if err:
        clean = "\n".join([l for l in err.splitlines() if not l.startswith("[sudo]")])
        if clean.strip():
            print("[ERR]", clean.strip())

print("[*] Creating 512MB swapfile on eMMC...")
sudo_cmd("fallocate -l 512M /swapfile 2>/dev/null || dd if=/dev/zero of=/swapfile bs=1M count=512")
sudo_cmd("chmod 600 /swapfile")
sudo_cmd("mkswap /swapfile")
sudo_cmd("swapon /swapfile")

# Persistence in /etc/fstab
sudo_cmd("grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab")

# Sysctl optimization
sudo_cmd("sysctl -w vm.swappiness=60")
sudo_cmd("sysctl -w vm.vfs_cache_pressure=50")

# Check free -m
sudo_cmd("free -m")

ssh.close()
