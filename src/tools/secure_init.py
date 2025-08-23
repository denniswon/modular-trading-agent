import argparse, getpass
from src.utils.secure_storage import save_secret

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key-name", required=True)
    args = ap.parse_args()
    secret = getpass.getpass("Enter secret (e.g., base58 private key): ")
    pw = getpass.getpass("Enter AES password: ")
    save_secret(args.key_name, secret, pw)
    print(f"Saved {args.key_name} to encrypted store.")

if __name__ == "__main__":
    main()
