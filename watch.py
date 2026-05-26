import curses
import time
import subprocess
import sys
import signal
import textwrap
import shutil
from pathlib import Path
from collections import deque, defaultdict

# ================= 配置区域 =================
DEVICE_PATH = None  # None=自动, 或 "/dev/nvidia0"
REFRESH_RATE = 1.0  # 刷新频率
HISTORY_STEPS = 60  # 历史长度
DETAIL_HEIGHT = 8   # 底部高度

# 快捷键配置
KEY_MAP = {
    'UP':          [curses.KEY_UP, ord('e'), ord('E')],   # 上移
    'DOWN':        [curses.KEY_DOWN, ord('f'), ord('F')], # 下移
    'SWITCH_VIEW': [ord('w'), ord('W')],                  # 切换视图
    'KILL':        [ord('k'), ord('K')],                  # 杀进程
    'CONFIRM':     [ord('y'), ord('Y')],                  # 确认 (Yes)
    'QUIT':        [ord('q'), ord('Q')]                   # 退出
}
# ===========================================

BRAILLE_CHARS = ["⠀", "⡀", "⡄", "⡆", "⡇", "⣇", "⣧", "⣷", "⣿", "|"]

def format_size(bytes_val):
    if bytes_val >= 1024**3: return f"{bytes_val / (1024**3):.1f}g"
    elif bytes_val >= 1024**2: return f"{bytes_val / (1024**2):.0f}m"
    else: return f"{bytes_val / 1024:.0f}k"

# 获取命令绝对路径，适配 WSL2 中 sudo 可能会丢弃的环境变量
def get_smi_path():
    for p in [shutil.which("nvidia-smi"), "/usr/lib/wsl/lib/nvidia-smi", "/usr/bin/nvidia-smi"]:
        if p and Path(p).exists(): return p
    return "nvidia-smi"

def get_ps_path():
    return shutil.which("ps") or "/bin/ps"

class SystemStat:
    def __init__(self):
        self.prev_idle = 0
        self.prev_total = 0

    def get_cpu_usage(self):
        try:
            stat_path = Path('/proc/stat')
            if stat_path.exists():
                line = stat_path.read_text().splitlines()[0]
                fields = [float(x) for x in line.split()[1:]]
                idle, total = fields[3], sum(fields)
                diff_idle, diff_total = idle - self.prev_idle, total - self.prev_total
                self.prev_idle, self.prev_total = idle, total
                return (1.0 - diff_idle / diff_total) * 100.0 if diff_total > 0 else 0.0
        except: pass
        return 0.0

    def get_mem_info(self):
        try:
            mem_path = Path('/proc/meminfo')
            if mem_path.exists():
                mem_total = 0; mem_avail = 0
                for line in mem_path.read_text().splitlines():
                    if line.startswith('MemTotal:'): mem_total = int(line.split()[1]) * 1024
                    elif line.startswith('MemAvailable:'): mem_avail = int(line.split()[1]) * 1024
                    if mem_total and mem_avail: break
                if mem_total > 0:
                    used = mem_total - mem_avail
                    return used, mem_total, (used / mem_total) * 100.0
        except: pass
        return 0, 1, 0.0

class HistoryManager:
    def __init__(self, steps):
        self.steps = steps
        self.g_cpu = deque([0.0]*steps, maxlen=steps)
        self.g_gpu = deque([0.0]*steps, maxlen=steps)
        self.g_mem = deque([0.0]*steps, maxlen=steps)
        self.proc_history = defaultdict(lambda: {
            'cpu': deque([0.0]*steps, maxlen=steps),
            'gpu': deque([0.0]*steps, maxlen=steps),
            'mem': deque([0.0]*steps, maxlen=steps)
        })

    def update_global(self, cpu, gpu_mem_pct, mem):
        self.g_cpu.append(cpu)
        self.g_gpu.append(gpu_mem_pct)
        self.g_mem.append(mem)

    def update_all_processes(self, procs_list, gpu_total_mem):
        active_pids = set()
        for p in procs_list:
            pid = p['pid']
            active_pids.add(pid)
            p_gpu_pct = 0.0
            if gpu_total_mem > 0:
                p_gpu_pct = (p['vram'] / gpu_total_mem) * 100.0
            self.proc_history[pid]['cpu'].append(p['cpu'])
            self.proc_history[pid]['gpu'].append(p_gpu_pct)
            self.proc_history[pid]['mem'].append(p['mem'])

        if len(self.proc_history) > 500:
            existing_pids = list(self.proc_history.keys())
            for pid in existing_pids:
                if pid not in active_pids: del self.proc_history[pid]

    def get_proc_history(self, pid):
        if pid in self.proc_history: return self.proc_history[pid]
        else: return {
                'cpu': deque([0.0]*self.steps, maxlen=self.steps),
                'gpu': deque([0.0]*self.steps, maxlen=self.steps),
                'mem': deque([0.0]*self.steps, maxlen=self.steps)
            }

def get_nvidia_stats():
    try:
        cmd = f"{get_smi_path()} --query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu --format=csv,noheader,nounits"
        out = subprocess.check_output(cmd, shell=True).decode().strip()
        util, used, total, temp = out.split(',')
        # 兼容 WSL2 中可能返回 N/A 或 Not Supported 的情况
        util_val = float(util.strip()) if util.strip().replace('.','',1).isdigit() else 0.0
        return { "util": util_val, "mem_used": int(used)*1024*1024, "mem_total": int(total)*1024*1024, "temp": temp.strip() }
    except: return {"util": 0.0, "mem_used": 0, "mem_total": 1, "temp": "N/A"}

def get_vram_info():
    vram_map, smi_procs = {}, []
    try:
        cmd = f"{get_smi_path()} --query-compute-apps=pid,used_memory,process_name --format=csv,noheader,nounits"
        out = subprocess.check_output(cmd, shell=True).decode().strip()
        if out:
            for line in out.split('\n'):
                parts = line.split(',')
                if len(parts) >= 3:
                    try:
                        pid = int(parts[0].strip())
                        # 规避 WSL2 下返回 N/A 导致报错
                        mem_str = parts[1].strip()
                        mem = int(mem_str) * 1024 * 1024 if mem_str.isdigit() else 0
                        vram_map[pid] = mem
                        smi_procs.append({"pid": pid, "vram": mem, "name": parts[2].strip()})
                    except: pass
    except: pass
    return vram_map, smi_procs

def get_fs_processes():
    procs = []
    proc_dir = Path('/proc')
    if not proc_dir.exists(): return procs

    ps_cmd = get_ps_path()

    for pid_dir in proc_dir.iterdir():
        if not pid_dir.is_dir() or not pid_dir.name.isdigit():
            continue

        pid = pid_dir.name
        fd_dir = pid_dir / 'fd'
        if not fd_dir.exists():
            continue

        is_using = False
        try:
            for fd_path in fd_dir.iterdir():
                if fd_path.is_symlink():
                    target = fd_path.readlink().as_posix()
                    # 【核心修改】扩大匹配范围：WSL2 中直通 GPU 使用 /dev/dxg 句柄
                    if "nvidia" in target or "dxg" in target:
                        is_using = True
                        break
        except: continue

        if is_using:
            cmd_full = ""
            try:
                cmd_path = pid_dir / 'cmdline'
                if cmd_path.exists():
                    cmd_full = cmd_path.read_bytes().decode('utf-8', errors='ignore').replace('\0', ' ').strip()
            except: pass

            user, cpu, mem, time_str = "N/A", 0.0, 0.0, "?"
            try:
                out = subprocess.check_output([ps_cmd, "-p", pid, "-o", "user,%cpu,%mem,etime"]).decode().strip().split('\n')
                if len(out)>1:
                    d = out[1].split()
                    if len(d)>=4: user, cpu, mem, time_str = d[0], float(d[1]), float(d[2]), d[3]
            except: pass

            procs.append({ "pid": int(pid), "user": user, "cpu": cpu, "mem": mem, "time": time_str, "cmd": cmd_full, "vram": 0 })
    return procs

# 11级颜色定义
COLOR_TIERS = [
    (1, curses.A_NORMAL),    # 00-09
    (2, curses.A_NORMAL),    # 10-19
    (3, curses.A_NORMAL),    # 20-29
    (4, curses.A_NORMAL),    # 30-39
    (5, curses.A_NORMAL),    # 40-49
    (6, curses.A_NORMAL),    # 50-59
    (7, curses.A_NORMAL),    # 60-69
    (2, curses.A_BOLD),      # 70-79
    (4, curses.A_BOLD),      # 80-89
    (5, curses.A_BOLD),      # 90-99
    (7, curses.A_BOLD),      # 100+
]

def draw_sparkline(stdscr, y, x, width, height, data_deque):
    if not data_deque or width < 2: return
    data = list(data_deque)[-width:]
    if len(data) < width: data = [0.0]*(width-len(data)) + data

    for i, val in enumerate(data):
        val = max(0.0, val)
        int_val = int(val)

        tier_idx = int_val // 10
        if tier_idx > 10: tier_idx = 10

        char_idx = int_val % 10
        char = BRAILLE_CHARS[char_idx]

        pair_id, attr = COLOR_TIERS[tier_idx]
        final_attr = curses.color_pair(pair_id) | attr

        if char_idx == 0 and int_val > 0:
            final_attr = final_attr | curses.A_REVERSE

        try: stdscr.addstr(y, x + i, char, final_attr)
        except: pass

def draw_legend(stdscr, y, x, width):
    legend_str = " Leg: "
    try: stdscr.addstr(y, x, legend_str, curses.color_pair(8))
    except: return

    start_x = x + len(legend_str)

    for i in range(11):
        if start_x + i >= width - 1: break
        pair_id, attr = COLOR_TIERS[i]
        char = str(i) if i < 10 else "!"
        style = curses.color_pair(pair_id) | attr | curses.A_REVERSE

        try: stdscr.addstr(y, start_x + i, char, style)
        except: pass

def main(stdscr):
    try:
        curses.curs_set(0)
        curses.start_color()
        curses.use_default_colors()
    except: pass

    stdscr.nodelay(True)

    curses.init_pair(1, curses.COLOR_WHITE, -1)
    curses.init_pair(2, curses.COLOR_CYAN, -1)
    curses.init_pair(3, curses.COLOR_BLUE, -1)
    curses.init_pair(4, curses.COLOR_GREEN, -1)
    curses.init_pair(5, curses.COLOR_YELLOW, -1)
    curses.init_pair(6, curses.COLOR_MAGENTA, -1)
    curses.init_pair(7, curses.COLOR_RED, -1)

    curses.init_pair(8, curses.COLOR_BLACK, curses.COLOR_CYAN)
    curses.init_pair(9, curses.COLOR_RED, -1)

    sys_stat = SystemStat()
    hist_mgr = HistoryManager(HISTORY_STEPS)

    dev_full_path = DEVICE_PATH
    if not dev_full_path:
        try:
            dev_dir = Path('/dev')
            cands = [f.name for f in dev_dir.iterdir() if f.name.startswith('nvidia') and f.name[6:].isdigit()]
            cands.sort(key=lambda x: int(x[6:]), reverse=True)
            if cands:
                dev_full_path = f"/dev/{cands[0]}"
            elif (dev_dir / 'dxg').exists():
                dev_full_path = "/dev/dxg (WSL2)"
            else:
                dev_full_path = "/dev/nvidia0"
        except: dev_full_path = "/dev/nvidia0"

    sel_idx = 0
    view_mode_global = True
    last_selected_pid = None

    while True:
        stdscr.erase(); H, W = stdscr.getmaxyx()

        gpu_stats = get_nvidia_stats()
        sys_cpu = sys_stat.get_cpu_usage()
        sys_mem_used, sys_mem_tot, sys_mem_pct = sys_stat.get_mem_info()
        g_vram_pct = 0.0
        if gpu_stats['mem_total'] > 0:
            g_vram_pct = (gpu_stats['mem_used'] / gpu_stats['mem_total']) * 100.0
        hist_mgr.update_global(sys_cpu, g_vram_pct, sys_mem_pct)

        fs_procs = get_fs_processes()
        vram_map, smi_procs = get_vram_info()

        final_procs = []
        is_compat = False
        if fs_procs:
            for p in fs_procs: p['vram'] = vram_map.get(p['pid'], 0)
            final_procs = fs_procs; final_procs.sort(key=lambda x: x['vram'], reverse=True)
        elif smi_procs:
            is_compat = True
            ps_cmd = get_ps_path()
            for sp in smi_procs:
                u, c, m, t = "N/A", 0.0, 0.0, "?"
                try:
                    out = subprocess.check_output([ps_cmd, "-p", str(sp['pid']), "-o", "user,%cpu,%mem,etime"]).decode().strip().split('\n')
                    if len(out)>1:
                        d = out[1].split()
                        if len(d)>=4: u, c, m, t = d[0], float(d[1]), float(d[2]), d[3]
                except: pass
                final_procs.append({ "pid": sp['pid'], "user": u, "cpu": c, "mem": m, "time": t, "cmd": f"[SMI] {sp['name']}", "vram": sp['vram'] })

        hist_mgr.update_all_processes(final_procs, gpu_stats['mem_total'])

        if last_selected_pid is not None and final_procs:
            found = False
            for i, p in enumerate(final_procs):
                if p['pid'] == last_selected_pid:
                    sel_idx = i; found = True; break
            if not found: sel_idx = 0

        if sel_idx >= len(final_procs): sel_idx = max(0, len(final_procs)-1)
        curr_p = final_procs[sel_idx] if final_procs else None

        if curr_p:
            p_hist = hist_mgr.get_proc_history(curr_p['pid'])
            p_gpu_pct = 0.0
            if gpu_stats['mem_total'] > 0: p_gpu_pct = (curr_p['vram']/gpu_stats['mem_total'])*100
        else:
            p_hist = None
            p_gpu_pct = 0.0

        dash_y = 0; col_w = W // 3

        if view_mode_global or not curr_p:
            title_txt = f"== GLOBAL | {dev_full_path} | [W] Process"
            t_col = curses.color_pair(4)|curses.A_BOLD
            d_cpu = (sys_cpu, f"CPU Sys: {sys_cpu:4.1f}% / Mean:{sum(hist_mgr.g_cpu)/HISTORY_STEPS:4.1f}%", hist_mgr.g_cpu)
            d_gpu = (g_vram_pct, f"GPU Mem: {format_size(gpu_stats['mem_used'])} - {g_vram_pct:4.1f}%", hist_mgr.g_gpu)
            d_mem = (sys_mem_pct, f"RAM Sys: {format_size(sys_mem_used)} - {sys_mem_pct:4.1f}%", hist_mgr.g_mem)
        else:
            title_txt = f"== PROCESS [PID: {curr_p['pid']}] | {dev_full_path} | [W] Global"
            t_col = curses.color_pair(2)|curses.A_BOLD
            d_cpu = (curr_p['cpu'], f"CPU PID: {curr_p['cpu']:4.1f}%", p_hist['cpu'])

            # WSL2 下因为读不出单进程 VRAM，这里的曲线图和数值会显示为0，这是正常的
            if is_compat: d_gpu = (g_vram_pct, f"GPU Mem (Global): {g_vram_pct:4.1f}%", hist_mgr.g_gpu)
            else: d_gpu = (p_gpu_pct, f"VRAM PID: {format_size(curr_p['vram'])} - {p_gpu_pct:4.1f}%", p_hist['gpu'])

            d_mem = (curr_p['mem'], f"RAM PID: {format_size(sys_mem_tot*(curr_p['mem']/100))} - {curr_p['mem']:4.1f}%", p_hist['mem'])

        try: stdscr.addstr(dash_y, 0, title_txt.ljust(W, "="), t_col)
        except: pass
        draw_legend(stdscr, dash_y, max(len(title_txt)+2, W - 25), W)

        for idx, (val, txt, hist) in enumerate([d_cpu, d_gpu, d_mem]):
            x = idx * col_w
            try: stdscr.addstr(dash_y+1, x+1, txt[:col_w-2], curses.color_pair(1))
            except: pass
            draw_sparkline(stdscr, dash_y+2, x+1, col_w-3, 1, hist)
            if idx < 2:
                for y in range(1, 4):
                    try: stdscr.addch(dash_y+y, (idx+1)*col_w, '|')
                    except: pass
        try: stdscr.addstr(dash_y+3, 0, "-"*W, curses.color_pair(5))
        except: pass

        list_y = 4
        try: stdscr.addstr(list_y, 3, f"{'PID':<8} {'USER':<10} {'GPU MEM':<10} {'CPU%':<6} {'MEM%':<6} {'TIME':<10} {'COMMAND':<20}", curses.color_pair(5)|curses.A_BOLD)
        except: pass
        list_h = H - list_y - DETAIL_HEIGHT - 2

        for i, p in enumerate(final_procs):
            if i >= list_h: break
            y = list_y + 1 + i
            try: stdscr.addstr(y, 0, "   ")
            except: pass

            if i == sel_idx:
                try: stdscr.addstr(y, 1, "->", curses.color_pair(2)|curses.A_BOLD)
                except: pass
                style = curses.color_pair(2)|curses.A_BOLD
            else:
                style = curses.color_pair(1)

            if i != sel_idx and p['vram'] > 1024**3:
                style = curses.color_pair(9)

            # 在 WSL 环境下合理显示显存
            v_str = format_size(p['vram']) if p['vram'] > 0 else "N/A"
            line = f"{p['pid']:<8} {p['user']:<10} {v_str:<10} {p['cpu']:<6.1f} {p['mem']:<6.1f} {p['time']:<10} {p['cmd'][:W-65]}"

            try: stdscr.addstr(y, 3, line, style)
            except: pass

        if not final_procs:
            try: stdscr.addstr(list_y+2, 3, "No processes found.", curses.color_pair(9))
            except: pass

        det_y = H - DETAIL_HEIGHT
        try: stdscr.addstr(det_y, 0, "="*W, curses.color_pair(4))
        except: pass

        if curr_p:
            try: stdscr.addstr(det_y, 2, f" [DETAIL] PID: {curr_p['pid']} | Started: {curr_p['time']} | Full Command:", curses.color_pair(1)|curses.A_BOLD)
            except: pass
            for i, l in enumerate(textwrap.wrap(curr_p['cmd'], width=W-4)):
                if i>=DETAIL_HEIGHT-2: break
                try: stdscr.addstr(det_y+1+i, 2, l, curses.color_pair(1))
                except: pass

        stat_bar = f" [W]: Toggle View | [E/F]: Select | [K]: Kill | [Y]: Confirm | [Q]: Quit | Rate: {REFRESH_RATE}s"
        try: stdscr.addstr(H-1, 0, stat_bar.ljust(W-1), curses.color_pair(8))
        except: pass
        stdscr.refresh()

        curses.halfdelay(int(REFRESH_RATE*10))
        try: k = stdscr.getch()
        except: k = -1

        if final_procs and sel_idx < len(final_procs):
            last_selected_pid = final_procs[sel_idx]['pid']
        else:
            last_selected_pid = None

        if k in KEY_MAP['QUIT']: break

        elif k in KEY_MAP['UP']:
            sel_idx -= 1
            if sel_idx < 0: sel_idx = 0
            view_mode_global = False
            if final_procs: last_selected_pid = final_procs[sel_idx]['pid']

        elif k in KEY_MAP['DOWN']:
            sel_idx += 1
            if sel_idx >= len(final_procs): sel_idx = max(0, len(final_procs)-1)
            view_mode_global = False
            if final_procs: last_selected_pid = final_procs[sel_idx]['pid']

        elif k in KEY_MAP['SWITCH_VIEW']:
            view_mode_global = not view_mode_global

        elif k in KEY_MAP['KILL']:
            if final_procs:
                curses.cbreak(); stdscr.nodelay(False)
                t = final_procs[sel_idx]
                msg = f" KILL PID {t['pid']}? (Y/N) "
                try:
                    stdscr.addstr(H-2, W-len(msg)-2, msg, curses.color_pair(9)|curses.A_REVERSE)
                    stdscr.refresh()
                except: pass

                check_k = stdscr.getch()
                if check_k in KEY_MAP['CONFIRM']:
                    import os
                    try: os.kill(t['pid'], signal.SIGKILL)
                    except: pass

                curses.halfdelay(int(REFRESH_RATE*10)); stdscr.nodelay(True)

if __name__ == "__main__":
    import os
    if os.geteuid() != 0: print("Need root (sudo)."); sys.exit(1)
    try:
        os.environ.setdefault('ESCDELAY', '25')
        curses.wrapper(main)
    except KeyboardInterrupt: pass
    except Exception as e:
        import traceback
        print("Fatal Error:")
        traceback.print_exc()