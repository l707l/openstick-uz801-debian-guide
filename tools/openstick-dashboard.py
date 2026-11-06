import http.server
import json
import os
import subprocess
import time
import socket
import re

PORT = 80

def get_cpu_temp():
    temps = []
    for i in range(5):
        p = f"/sys/class/thermal/thermal_zone{i}/temp"
        if os.path.exists(p):
            try:
                with open(p, "r") as f:
                    temps.append(int(f.read().strip()) / 1000.0)
            except Exception:
                pass
    return max(temps) if temps else 0.0

def get_cpu_info():
    freqs = []
    for i in range(4):
        p = f"/sys/devices/system/cpu/cpu{i}/cpufreq/scaling_cur_freq"
        if os.path.exists(p):
            try:
                with open(p, "r") as f:
                    freqs.append(int(f.read().strip()) // 1000)
            except Exception:
                pass
    return freqs

def get_mem():
    mem = {}
    with open("/proc/meminfo", "r") as f:
        for line in f:
            parts = line.split(":")
            if len(parts) == 2:
                key = parts[0].strip()
                val = parts[1].strip().split()[0]
                mem[key] = int(val) // 1024
    total = mem.get("MemTotal", 0)
    avail = mem.get("MemAvailable", 0)
    used = total - avail
    swap_total = mem.get("SwapTotal", 0)
    swap_free = mem.get("SwapFree", 0)
    swap_used = swap_total - swap_free
    return {
        "ram_total": total, "ram_used": used, "ram_free": avail,
        "swap_total": swap_total, "swap_used": swap_used, "swap_free": swap_free
    }

def get_disk():
    st = os.statvfs("/")
    total = (st.f_blocks * st.f_frsize) // (1024*1024)
    free = (st.f_bavail * st.f_frsize) // (1024*1024)
    used = total - free
    return {"total": total, "used": used, "free": free}

def get_modem():
    try:
        out = subprocess.check_output(["mmcli", "-m", "0", "-j"], stderr=subprocess.DEVNULL)
        return json.loads(out.decode("utf-8"))
    except Exception:
        # Fallback text parse
        try:
            out = subprocess.check_output(["mmcli", "-m", "0"], stderr=subprocess.DEVNULL).decode("utf-8")
            imei = re.search(r"equipment id:\s*(\S+)", out)
            state = re.search(r"state:\s*(\S+)", out)
            operator = re.search(r"operator name:\s*([^\n]+)", out)
            return {
                "modem": {
                    "3gpp": {"imei": imei.group(1) if imei else "N/A", "operator-name": operator.group(1) if operator else "Desconocido"},
                    "generic": {"state": state.group(1) if state else "Desconectado"}
                }
            }
        except Exception:
            return {"modem": {"generic": {"state": "No detectado"}}}

def get_clients():
    clients = []
    try:
        with open("/proc/net/arp", "r") as f:
            lines = f.readlines()[1:]
            for line in lines:
                parts = line.split()
                if len(parts) >= 6 and parts[3] != "00:00:00:00:00:00":
                    clients.append({"ip": parts[0], "mac": parts[3], "iface": parts[5]})
    except Exception:
        pass
    return clients

def get_leds():
    leds = {}
    for name in ["red:power", "green:wlan", "blue:wan"]:
        p = f"/sys/class/leds/{name}/trigger"
        if os.path.exists(p):
            with open(p, "r") as f:
                content = f.read()
                m = re.search(r"\[([^\]]+)\]", content)
                leds[name] = m.group(1) if m else "none"
    return leds

INDEX_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OpenStick UZ801 - Control Center</title>
<style>
:root { --bg: #0f172a; --card: #1e293b; --text: #f8fafc; --accent: #38bdf8; --green: #4ade80; --red: #f87171; --orange: #fb923c; }
body { margin:0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: var(--bg); color: var(--text); padding: 20px; }
.header { display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #334155; padding-bottom: 15px; margin-bottom: 20px; }
.header h1 { margin: 0; font-size: 1.5rem; display: flex; align-items: center; gap: 10px; }
.badge { background: #0369a1; padding: 4px 10px; border-radius: 999px; font-size: 0.75rem; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }
.card { background: var(--card); border-radius: 12px; padding: 18px; border: 1px solid #334155; }
.card h2 { margin: 0 0 12px 0; font-size: 1.05rem; color: var(--accent); display: flex; justify-content: space-between; }
.stat-row { display: flex; justify-content: space-between; margin: 8px 0; font-size: 0.9rem; }
.stat-val { font-weight: 600; color: #fff; }
.progress-bg { background: #334155; height: 8px; border-radius: 4px; overflow: hidden; margin-top: 6px; }
.progress-bar { height: 100%; background: var(--accent); border-radius: 4px; transition: width 0.4s; }
.progress-bar.green { background: var(--green); }
.progress-bar.orange { background: var(--orange); }
.progress-bar.red { background: var(--red); }
.btn { background: #0284c7; color: white; border: none; padding: 8px 14px; border-radius: 6px; cursor: pointer; font-size: 0.85rem; font-weight: 500; transition: 0.2s; }
.btn:hover { background: #0369a1; }
.btn-red { background: #dc2626; }
.btn-red:hover { background: #b91c1c; }
.actions { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 10px; }
table { width: 100%; border-collapse: collapse; font-size: 0.85rem; margin-top: 8px; }
th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid #334155; }
th { color: #94a3b8; }
</style>
</head>
<body>
<div class="header">
  <h1>⚡ OpenStick UZ801 <span class="badge">Debian 12 Mainline</span></h1>
  <div style="font-size: 0.85rem; color: #94a3b8;">MSM8916 Snapdragon 410</div>
</div>

<div class="grid">
  <div class="card">
    <h2>Procesador (CPU) <span id="cpu-temp" style="color:var(--orange)">-- °C</span></h2>
    <div class="stat-row"><span>Frecuencia Núcleos:</span><span id="cpu-freq" class="stat-val">--</span></div>
    <div class="stat-row"><span>Temperatura:</span><span id="temp-val" class="stat-val">--</span></div>
    <div class="progress-bg"><div id="temp-bar" class="progress-bar orange" style="width: 40%"></div></div>
  </div>

  <div class="card">
    <h2>Memoria RAM y Swap</h2>
    <div class="stat-row"><span>RAM:</span><span id="ram-text" class="stat-val">-- / -- MB</span></div>
    <div class="progress-bg"><div id="ram-bar" class="progress-bar" style="width: 0%"></div></div>
    <div class="stat-row" style="margin-top:14px;"><span>Swap eMMC (ZRAM/Swap):</span><span id="swap-text" class="stat-val">-- / -- MB</span></div>
    <div class="progress-bg"><div id="swap-bar" class="progress-bar green" style="width: 0%"></div></div>
  </div>

  <div class="card">
    <h2>Módem 4G LTE <span id="modem-state" class="badge">--</span></h2>
    <div class="stat-row"><span>Operador:</span><span id="modem-op" class="stat-val">--</span></div>
    <div class="stat-row"><span>IMEI:</span><span id="modem-imei" class="stat-val">--</span></div>
    <div class="actions">
      <button class="btn" onclick="apiAction('lte-up')">📶 Conectar LTE</button>
      <button class="btn btn-red" onclick="apiAction('lte-down')">Desconectar</button>
    </div>
  </div>

  <div class="card">
    <h2>Almacenamiento eMMC</h2>
    <div class="stat-row"><span>Partición Rootfs (/):</span><span id="disk-text" class="stat-val">-- / -- MB</span></div>
    <div class="progress-bg"><div id="disk-bar" class="progress-bar green" style="width: 0%"></div></div>
  </div>

  <div class="card">
    <h2>Dispositivos Conectados (Wi-Fi / USB)</h2>
    <table>
      <thead><tr><th>IP</th><th>MAC</th><th>Interfaz</th></tr></thead>
      <tbody id="clients-table"><tr><td colspan="3">Cargando...</td></tr></tbody>
    </table>
  </div>

  <div class="card">
    <h2>Control del Sistema</h2>
    <p style="font-size:0.85rem; color:#94a3b8; margin:0 0 10px 0;">Acciones de reinicio y sincronización.</p>
    <div class="actions">
      <button class="btn" onclick="apiAction('sync-time')">🕒 Sincronizar Reloj</button>
      <button class="btn btn-red" onclick="if(confirm('¿Reiniciar el OpenStick?')) apiAction('reboot')">🔄 Reiniciar Módem</button>
    </div>
  </div>
</div>

<script>
async function refresh() {
  try {
    const res = await fetch('/api/status');
    const d = await res.json();
    
    // CPU & Temp
    document.getElementById('cpu-temp').innerText = d.temp.toFixed(1) + ' °C';
    document.getElementById('temp-val').innerText = d.temp.toFixed(1) + ' °C';
    document.getElementById('temp-bar').style.width = Math.min(100, (d.temp / 85) * 100) + '%';
    document.getElementById('cpu-freq').innerText = d.cpu.join(', ') + ' MHz';
    
    // RAM
    const ramPct = Math.round((d.mem.ram_used / d.mem.ram_total) * 100);
    document.getElementById('ram-text').innerText = `${d.mem.ram_used} / ${d.mem.ram_total} MB (${ramPct}%)`;
    document.getElementById('ram-bar').style.width = ramPct + '%';
    
    // Swap
    if (d.mem.swap_total > 0) {
      const swapPct = Math.round((d.mem.swap_used / d.mem.swap_total) * 100);
      document.getElementById('swap-text').innerText = `${d.mem.swap_used} / ${d.mem.swap_total} MB (${swapPct}%)`;
      document.getElementById('swap-bar').style.width = swapPct + '%';
    } else {
      document.getElementById('swap-text').innerText = 'Desactivado';
    }
    
    // Disk
    const diskPct = Math.round((d.disk.used / d.disk.total) * 100);
    document.getElementById('disk-text').innerText = `${d.disk.used} / ${d.disk.total} MB (${diskPct}%)`;
    document.getElementById('disk-bar').style.width = diskPct + '%';
    
    // Modem
    const m = d.modem.modem || {};
    const state = (m.generic && m.generic.state) || 'Desconocido';
    document.getElementById('modem-state').innerText = state;
    document.getElementById('modem-imei').innerText = (m['3gpp'] && m['3gpp'].imei) || '868589080718516';
    document.getElementById('modem-op').innerText = (m['3gpp'] && m['3gpp']['operator-name']) || (state === 'failed' ? 'Sin Tarjeta SIM' : 'Buscando...');
    
    // Clients
    const tbody = document.getElementById('clients-table');
    if (d.clients.length === 0) {
      tbody.innerHTML = '<tr><td colspan="3" style="color:#64748b">No hay clientes activos</td></tr>';
    } else {
      tbody.innerHTML = d.clients.map(c => `<tr><td>${c.ip}</td><td>${c.mac}</td><td><span class="badge">${c.iface}</span></td></tr>`).join('');
    }
  } catch(e) { console.error(e); }
}

async function apiAction(action) {
  await fetch('/api/' + action, { method: 'POST' });
  setTimeout(refresh, 800);
}

setInterval(refresh, 2500);
refresh();
</script>
</body>
</html>
"""

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(INDEX_HTML.encode("utf-8"))
        elif self.path == "/api/status":
            data = {
                "temp": get_cpu_temp(),
                "cpu": get_cpu_info(),
                "mem": get_mem(),
                "disk": get_disk(),
                "modem": get_modem(),
                "clients": get_clients(),
                "leds": get_leds()
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode("utf-8"))
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/api/lte-up":
            subprocess.Popen(["nmcli", "connection", "up", "lte"])
            self.send_response(200); self.end_headers()
        elif self.path == "/api/lte-down":
            subprocess.Popen(["nmcli", "connection", "down", "lte"])
            self.send_response(200); self.end_headers()
        elif self.path == "/api/reboot":
            subprocess.Popen(["reboot"])
            self.send_response(200); self.end_headers()
        elif self.path == "/api/sync-time":
            subprocess.Popen(["chronyd", "-q"] if os.path.exists("/usr/sbin/chronyd") else ["date"])
            self.send_response(200); self.end_headers()
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        pass

if __name__ == "__main__":
    server = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"OpenStick Dashboard running on port {PORT}...")
    server.serve_forever()
