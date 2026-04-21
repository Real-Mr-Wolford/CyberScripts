import socket

target = "172.20.10.3"
common = [21, 22, 23, 25, 53, 80, 110, 143, 443, 3306] #list of common ports to scan
for port in common: 
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM) #connects to the internet uisng IPv4(INET) and TCP(SOCK_STREAM)
    socket.setdefaulttimeout(0.25) 

    result = s.connect_ex((target,port)) #takes a tuple of (target,port) and returns 0 for open, 10061 for closed, and 10060 for filtered

    if result == 0:
        print(f"Port {port} is open")
    else:
        print(f"Port {port} is closed/filtered")
    s.close()


