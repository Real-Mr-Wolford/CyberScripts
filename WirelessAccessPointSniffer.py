import re
import sys
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("Required module 'pyserial' is not installed. Install it with 'pip install pyserial'.")
    sys.exit(1)

TIMEOUT_SECONDS = 10

# ---------------------------------------------------------------------------
# Expected serial line formats from the companion ESP32 sketch:
#
#   TYPE:WIFI  | SSID:<name>       | MAC:<xx:xx:xx:xx:xx:xx> | RSSI:<-nn>
#   TYPE:BLE   | NAME:<name>       | MAC:<xx:xx:xx:xx:xx:xx> | RSSI:<-nn>
#   TYPE:PROBE | SSID:<name>       | MAC:<xx:xx:xx:xx:xx:xx> | RSSI:<-nn>
#
# The parser also handles legacy / freeform lines as a fallback.
# ---------------------------------------------------------------------------

STRUCTURED_RE = re.compile(
    r"TYPE:(\w+)"
    r".*?(?:SSID|NAME):([^|]*)"
    r".*?MAC:([\w:]{11,17})"
    r".*?RSSI:(-\d+)",
    re.IGNORECASE,
)

# Fallback: grab whatever appears before RSSI as the name
LEGACY_RE = re.compile(
    r"^(.*?)\s*RSSI:\s*(-\d+)\s*[|,]?\s*(?:From\s+)?MAC:\s*([\w:]{11,17})",
    re.IGNORECASE,
)

# Last-ditch: just a MAC + RSSI anywhere on the line
MINIMAL_RE = re.compile(
    r"([\w:]{11,17}).*?(-\d{2,3})\s*dBm",
    re.IGNORECASE,
)


def parse_line(line: str):
    """
    Return (mac, rssi, device_type, display_name) or None if unparseable.
    display_name is the best human-readable label we could find.
    """
    # --- Structured format (preferred) ---
    m = STRUCTURED_RE.search(line)
    if m:
        dev_type  = m.group(1).upper().strip()
        raw_name  = m.group(2).strip().strip('"').strip("'")
        mac       = m.group(3).upper()
        rssi      = int(m.group(4))
        name      = raw_name if raw_name else f"({dev_type})"
        return mac, rssi, dev_type, name

    # --- Legacy / freeform format ---
    m = LEGACY_RE.search(line)
    if m:
        raw_name = m.group(1).strip().rstrip('|').strip()
        rssi     = int(m.group(2))
        mac      = m.group(3).upper()
        name     = raw_name if raw_name else "Unknown"
        return mac, rssi, "LEGACY", name

    # --- Minimal: MAC + dBm anywhere ---
    m = MINIMAL_RE.search(line)
    if m:
        mac  = m.group(1).upper()
        rssi = int(m.group(2))
        return mac, rssi, "?", "Unknown"

    return None


class ESP32RadarGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("ESP32 WAP / BLE Radar")
        self.root.geometry("1050x560")
        self.root.configure(bg="#1e1e1e")

        # devices[mac] = {"rssi": int, "ts": float, "type": str, "name": str}
        self.devices: dict = {}
        self.is_running = False
        self.ser = None
        self._lock = threading.Lock()

        self.setup_ui()
        self.populate_ports()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def setup_ui(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Treeview",
            background="#2d2d2d", foreground="white",
            fieldbackground="#2d2d2d", rowheight=23,
        )
        style.map("Treeview", background=[("selected", "#007acc")])
        style.configure(
            "Treeview.Heading",
            background="#3c3c3c", foreground="white", relief="flat",
        )

        # ---- Top controls ----
        ctrl = tk.Frame(self.root, bg="#1e1e1e", padx=10, pady=10)
        ctrl.pack(fill=tk.X)

        tk.Label(ctrl, text="Serial Port:", fg="white", bg="#1e1e1e",
                 font=("Arial", 10)).pack(side=tk.LEFT, padx=5)

        self.port_combobox = ttk.Combobox(ctrl, width=15, state="readonly")
        self.port_combobox.pack(side=tk.LEFT, padx=5)

        tk.Button(ctrl, text="🔄", command=self.populate_ports,
                  bg="#3c3c3c", fg="white", relief="flat").pack(side=tk.LEFT, padx=3)

        self.toggle_btn = tk.Button(
            ctrl, text="Start Scan", command=self.toggle_scan,
            bg="#28a745", fg="white", font=("Arial", 10, "bold"),
            width=12, relief="flat",
        )
        self.toggle_btn.pack(side=tk.LEFT, padx=15)

        # Filter entry
        tk.Label(ctrl, text="Filter:", fg="white", bg="#1e1e1e",
                 font=("Arial", 10)).pack(side=tk.LEFT, padx=(20, 3))
        self.filter_var = tk.StringVar()
        self.filter_var.trace_add("write", lambda *_: None)  # just holds value
        tk.Entry(ctrl, textvariable=self.filter_var, width=18,
                 bg="#3c3c3c", fg="white", insertbackground="white").pack(side=tk.LEFT)

        self.status_label = tk.Label(
            ctrl, text="Status: Stopped", fg="#ffc107",
            bg="#1e1e1e", font=("Arial", 10, "italic"),
        )
        self.status_label.pack(side=tk.RIGHT, padx=10)

        # ---- Table ----
        table_frame = tk.Frame(self.root, bg="#1e1e1e", padx=10, pady=5)
        table_frame.pack(fill=tk.BOTH, expand=True)

        cols = ("type", "mac", "name", "rssi", "bar")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")

        self.tree.heading("type", text="TYPE")
        self.tree.heading("mac",  text="MAC ADDRESS")
        self.tree.heading("name", text="DEVICE NAME / SSID")
        self.tree.heading("rssi", text="RSSI")
        self.tree.heading("bar",  text="SIGNAL STRENGTH")

        self.tree.column("type", width=70,  anchor=tk.CENTER)
        self.tree.column("mac",  width=145, anchor=tk.CENTER)
        self.tree.column("name", width=230, anchor=tk.W)
        self.tree.column("rssi", width=80,  anchor=tk.CENTER)
        self.tree.column("bar",  width=480, anchor=tk.W)

        # Colour tags: WiFi = teal, BLE = violet, probe = yellow, other = default
        self.tree.tag_configure("WIFI",   foreground="#4fc3f7")
        self.tree.tag_configure("BLE",    foreground="#ce93d8")
        self.tree.tag_configure("PROBE",  foreground="#fff176")
        self.tree.tag_configure("LEGACY", foreground="#a5d6a7")

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL,
                                  command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # ---- Status bar ----
        self.count_label = tk.Label(
            self.root, text="Devices: 0", fg="#aaaaaa",
            bg="#1e1e1e", font=("Arial", 9), anchor=tk.W, padx=12,
        )
        self.count_label.pack(fill=tk.X)

    # ------------------------------------------------------------------
    # Port management
    # ------------------------------------------------------------------
    def populate_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_combobox["values"] = ports
        if ports:
            self.port_combobox.current(0)
        else:
            self.port_combobox.set("No ports found")

    # ------------------------------------------------------------------
    # Scan control
    # ------------------------------------------------------------------
    def toggle_scan(self):
        if self.is_running:
            self.stop_scan()
        else:
            self.start_scan()

    def start_scan(self):
        port = self.port_combobox.get()
        if not port or port == "No ports found":
            messagebox.showerror("Error", "Please select a valid COM port.")
            return
        try:
            self.ser = serial.Serial(port, 115200, timeout=1)
        except Exception as e:
            messagebox.showerror("Connection Error",
                                 f"Could not open {port}:\n{e}")
            return

        self.is_running = True
        with self._lock:
            self.devices.clear()

        self.toggle_btn.config(text="Stop Scan", bg="#dc3545")
        self.status_label.config(text="Status: Scanning…", fg="#28a745")

        self.thread = threading.Thread(target=self.read_serial_loop, daemon=True)
        self.thread.start()
        self.update_gui_loop()

    def stop_scan(self):
        self.is_running = False
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.toggle_btn.config(text="Start Scan", bg="#28a745")
        self.status_label.config(text="Status: Stopped", fg="#ffc107")

    # ------------------------------------------------------------------
    # Serial reader (background thread)
    # ------------------------------------------------------------------
    def read_serial_loop(self):
        while self.is_running:
            try:
                line = self.ser.readline().decode("utf-8", errors="ignore").strip()
            except Exception:
                break
            if not line:
                continue

            parsed = parse_line(line)
            if parsed is None:
                continue

            mac, rssi, dev_type, name = parsed

            with self._lock:
                existing = self.devices.get(mac)
                # Keep the best (highest RSSI) name if we've seen the device before
                if existing and existing["name"] not in ("Unknown", f"({dev_type})"):
                    name = existing["name"]
                self.devices[mac] = {
                    "rssi": rssi,
                    "ts":   time.time(),
                    "type": dev_type,
                    "name": name,
                }

    # ------------------------------------------------------------------
    # GUI refresh (main thread, every 250 ms)
    # ------------------------------------------------------------------
    def update_gui_loop(self):
        if not self.is_running:
            return

        now = time.time()
        filt = self.filter_var.get().lower()

        with self._lock:
            # Expire old entries
            self.devices = {
                m: d for m, d in self.devices.items()
                if (now - d["ts"]) < TIMEOUT_SECONDS
            }
            snapshot = dict(self.devices)

        # Sort by RSSI descending, cap at 30 rows
        sorted_devs = sorted(
            snapshot.items(), key=lambda kv: kv[1]["rssi"], reverse=True
        )[:30]

        # Apply filter
        if filt:
            sorted_devs = [
                (m, d) for m, d in sorted_devs
                if filt in m.lower()
                or filt in d["name"].lower()
                or filt in d["type"].lower()
            ]

        for row in self.tree.get_children():
            self.tree.delete(row)

        for mac, d in sorted_devs:
            rssi      = d["rssi"]
            dev_type  = d["type"]
            name      = d["name"]

            # Signal bar: scale -100 dBm → 0 bars, -30 dBm → 35 bars
            bar_len   = max(0, min(35, int((rssi + 100) * 35 / 70)))
            bar_str   = "█" * bar_len

            tag = dev_type if dev_type in ("WIFI", "BLE", "PROBE", "LEGACY") else "other"
            self.tree.insert(
                "", tk.END,
                values=(dev_type, mac, name, f"{rssi} dBm", bar_str),
                tags=(tag,),
            )

        self.count_label.config(text=f"Devices seen: {len(snapshot)}")
        self.root.after(250, self.update_gui_loop)

    # ------------------------------------------------------------------
    def on_close(self):
        self.stop_scan()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = ESP32RadarGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
