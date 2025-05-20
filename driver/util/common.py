import os
import shutil
import orjson
import ipaddress
from itertools import islice

def clear_or_create_directory(dir_path):
    # Check if the directory exists
    if os.path.exists(dir_path):
        shutil.rmtree(dir_path)
    os.makedirs(dir_path)


def output_lines(path, lines):
    with open(path, 'w+') as f:
        f.write('\n'.join(lines))


def output_string(path, string):
    with open(path, 'w+') as f:
        f.write(string)


def output_dict_as_json(path, data):
    try:
        with open(path, "wb") as f:  # Open file in binary mode for best performance
            f.write(orjson.dumps(data, option=orjson.OPT_SERIALIZE_NUMPY))  
        print(f"JSON saved successfully at {path}")
    except Exception as e:
        print(f"Error saving JSON: {e}")


class IPv4AddressGenerator:
    def __init__(self, starting_address: str):
        # Initialize with the starting IPv6 address
        self.current_address = ipaddress.IPv4Address(starting_address)

    def is_multicast(self, ip):
        # Check if the address is a multicast address
        return ip.is_multicast

    def ends_with_zero(self, ip):
        # Check if the address ends with ::0 (address with trailing zeros)
        return ip == ipaddress.IPv4Address(int(ip) & ~(1 << 0))

    def get_next_ipaddr(self):
        rtr = str(self.current_address)
        # Increment the current address until it is not a multicast address or ends with ::0
        while True:
            # if not self.is_multicast(next_address) and not self.ends_with_zero(next_address):
            self.current_address += 1
            if not self.is_multicast(self.current_address):
                break
        return rtr


class IPv6AddressGenerator:
    def __init__(self, starting_address: str):
        # Initialize with the starting IPv6 address
        self.current_address = ipaddress.IPv6Address(starting_address)

    def is_multicast(self, ip):
        # Check if the address is a multicast address
        return ip.is_multicast

    def ends_with_zero(self, ip):
        # Check if the address ends with ::0 (address with trailing zeros)
        return ip == ipaddress.IPv6Address(int(ip) & ~(1 << 0))

    def get_next_ipaddr(self):
        rtr = str(self.current_address)
        # Increment the current address until it is not a multicast address or ends with ::0
        while True:
            # if not self.is_multicast(next_address) and not self.ends_with_zero(next_address):
            self.current_address += 1
            if not self.is_multicast(self.current_address):
                break
        return rtr

 
def count_lines_islice(file_path, chunk_size=1024):
    count = 0
    with open(file_path, 'r') as file:
        while True:
            buffer = list(islice(file, chunk_size))
            if not buffer:
                break
            count += len(buffer) - buffer.count('')
    return count