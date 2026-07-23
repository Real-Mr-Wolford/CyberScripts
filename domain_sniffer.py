import whois
import dns.resolver
def profile_domain(domain):
    try:
        w = whois.whois(domain)
        print("\n WHOIS Info:")
        print(f"Registrar: {w.registrar}")
        print(f"Date of Creation: {w.creation_date}")
        print(f"Date of Expiration: {w.expiration_date}")
    except Exception as e:
        return {"error": str(e)}

    print("\n DNS Information:")
    record_types = ["A", "MX", "NS", "TXT"]
    for record_type in record_types:
        try:
            answers = dns.resolver.resolve(domain, record_type)
            print(f"\n{record_type}")
            for record_data in answers:
                print(f" {record_data} ")
        except Exception as e:
            print(f"Error retrieving {record_type} records: {e}")

def run():
    target = input("Enter the domain to profile: ").strip()
    profile_domain(target)
    choice = input("Do you want to scan a domain? (y/n): ").strip().lower()
    if choice == 'y':
        run()
    else:
        print("Exiting the program.")
        return;




if __name__=="__main__":
    run()
    
