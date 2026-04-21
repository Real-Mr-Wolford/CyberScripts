import requests # type: ignore
import tkinter as tk
from tkinter import messagebox, scrolledtext

class ThreatApp:
    def __init__(self, root):
        self.root = root
        self.root.title("CISA Threat and Vulnerability Information")
        self.root.geometry("600x400")
        self.root.configure(bg="#030a90")

        self.label = tk.Label(
            root,
            text = "CISA Known Exploited Vulnerabilities",
            fg = "white",bg = "#2c3e50",
            font = ("Arial", 16, "bold")
        )
        self.label.pack(pady=10)

        self.btn = tk.Button(
            root,
            text = "Fetch Critical Threats",
            command = self.get_threat,
            bg="#e74c3c", fg="white", 
            font=("Arial", 10, "bold"),
            padx=20, pady=10
        )
        self.btn.pack(pady=5)
        self.output_area = scrolledtext.ScrolledText(
            root, 
            width=80, 
            height=20, 
            font=("Consolas", 10),
            bg="#ecf0f1"
        )

        self.output_area.pack(padx=20,pady=20)

    def get_threat(self):
        self.output_area.delete('1.0',tk.END)
        self.output_area.insert(tk.END, "Fetching data from CISA...\n")

        url = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"

        try:
            response= requests.get(url, timeout = 10)
            response.raise_for_status()
            data = response.json()
            vulner = data.get("vulnerabilities", [])

            count = 0
            for vuln in vulner:
                desc = vuln.get('shortDescription',"")

                if "critical" in desc.lower():
                    count +=1
                    cve_id = vuln.get('cveID')
                    vendor = vuln.get('vendorProject')
                    product = vuln.get('product')

                    entry = f"[!] ALERT: {cve_id} \nVendor: {vendor} | Product: {product}\n"
                    entry+= f"Summary: {desc[:2000]}...\n"
                    entry += "-"*50 + "\n"

                    self.output_area.insert(tk.END, entry)
            if count ==0:
                self.output_area.insert(tk.END, "No critical vulnerabilities found in the latest feed.\n")
            else:
                self.output_area.insert(tk.END, f"Total Critical Vulnerabilities: {count}\n")
        
        except Exception as e:
            messagebox.showerror("Connection Error",f"Failed to fetch data: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = ThreatApp(root)
    root.mainloop()



    
