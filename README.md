# Scan 192.168.x.x network
python sbf.py 192.168 -t 100

# Scan 10.0.1.x network
python sbf.py 10.0.1 -to 2.0

# Use custom credentials file
python sbf.py 192.168.0 -c custom_creds.txt
