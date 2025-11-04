#!/usr/bin/python3
import sys
import struct
import wrapper
import threading
import time
from wrapper import recv_from_any_link, send_to_link, get_switch_mac, get_interface_name

def parse_ethernet_header(data):
    # Unpack the header fields from the byte array
    #dest_mac, src_mac, ethertype = struct.unpack('!6s6sH', data[:14])
    dest_mac = data[0:6]
    src_mac = data[6:12]
    
    # Extract ethertype. Under 802.1Q, this may be the bytes from the VLAN TAG
    ether_type = (data[12] << 8) + data[13]

    vlan_id = -1
    # Check for VLAN tag (0x8100 in network byte order is b'\x81\x00')
    if ether_type == 0x8200:
        vlan_tci = int.from_bytes(data[14:16], byteorder='big')
        vlan_id = vlan_tci & 0x0FFF  # extract the 12-bit VLAN ID
        ether_type = (data[16] << 8) + data[17]

    return dest_mac, src_mac, ether_type, vlan_id

def create_vlan_tag(vlan_id):
    # 0x8100 for the Ethertype for 802.1Q
    # vlan_id & 0x0FFF ensures that only the last 12 bits are used
    return struct.pack('!H', 0x8200) + struct.pack('!H', vlan_id & 0x0FFF)

def initialize_stp(switch):
    for i in range(switch.num_interfaces):
        if switch.port_type_table.get(get_interface_name(i)) == 'Trunk':
            switch.port_states[i] = 'Blocking'

    switch.root_bridge_id = switch.own_bridge_id
    switch.root_path_cost = 0

    if switch.own_bridge_id == switch.root_bridge_id:
        for interface in range(switch.num_interfaces):
            switch.port_states[interface] = 'Listening'

def send_bdpu_every_sec(switch):
    while True:
        if switch.root_bridge_id == switch.own_bridge_id:
            for interface in range(switch.num_interfaces):
                if switch.port_type_table.get(get_interface_name(interface)) == 'Trunk':

                    # Create the BPDU frame and send it
                    mac_dest = struct.pack('!6B', 0x01, 0x80, 0xc2, 0x00, 0x00, 0x00)
                    sender_bridge_id = struct.pack('!Q', switch.own_bridge_id)
                    sender_path_cost = struct.pack('!I', 0)
                    root_bridge_id = struct.pack('!Q', switch.root_bridge_id)

                    bpdu = mac_dest + sender_bridge_id + sender_path_cost + root_bridge_id
                    send_to_link(interface, len(bpdu), bpdu)
        time.sleep(1)

def process_bpdu(switch, data, length, interface):

    # extract necessary fields from the BPDU
    bpdu_sender_bridge_id = struct.unpack('!Q', data[6:14])[0]
    bpdu_sender_path_cost = struct.unpack('!I', data[14:18])[0]
    bpdu_root_bridge_id = struct.unpack('!Q', data[18:26])[0]

    # save the old values
    old_root_bridge_id = switch.root_bridge_id
    old_root_path_cost = switch.root_path_cost
    
    if bpdu_root_bridge_id < switch.root_bridge_id:
        switch.root_bridge_id = bpdu_root_bridge_id
        switch.root_path_cost = bpdu_sender_path_cost + 10
        switch.root_port = interface

        if switch.own_bridge_id == old_root_bridge_id:
            for i in range(switch.num_interfaces):
                if switch.port_type_table.get(get_interface_name(i)) == 'Trunk':
                    if i != switch.root_port:
                        switch.port_states[i] = 'Blocking'

        if switch.port_states[switch.root_port] == 'Blocking':
            switch.port_states[switch.root_port] = 'Listening'

        for i in range(switch.num_interfaces):
            if switch.port_type_table.get(get_interface_name(i)) == 'Trunk':

                bpdu_sender_bridge_id = struct.pack('!Q', switch.own_bridge_id)
                bpdu_sender_path_cost = struct.pack('!I', old_root_path_cost)
                bpdu_root_bridge_id = struct.pack('!Q', old_root_bridge_id)

                bpdu = data[0:6] + bpdu_sender_bridge_id + bpdu_sender_path_cost + bpdu_root_bridge_id
                send_to_link(i, length, bpdu)

    elif bpdu_root_bridge_id == switch.root_bridge_id:
        if (interface == switch.root_port) and (bpdu_sender_path_cost + 10 < switch.root_path_cost):
            switch.root_path_cost = bpdu_sender_path_cost + 10

        elif interface != switch.root_port:
            if bpdu_sender_path_cost > switch.root_path_cost:
                if switch.port_states[interface] != 'Listening':
                    switch.port_states[interface] = 'Listening'

    elif bpdu_sender_bridge_id == switch.own_bridge_id:
        switch.port_states[interface] = 'Blocking'
    else:
        pass
    if switch.own_bridge_id == switch.root_bridge_id:
        for i in range(switch.num_interfaces):
            switch.port_states[i] = 'Listening'
        
def is_unicast(mac):
    # Check if the least significant bit of the first byte is 0
    first_byte = int(mac.split(':')[0], 16)
    return first_byte & 1 == 0

def load_switch_config(switch_id):
    vlan_table = {}
    port_type_table = {}

    with open(f'configs/switch{switch_id}.cfg', 'r') as file:

        priority = int(file.readline().strip())

        for line in file:
            parts = line.strip().split()

            interface_name = parts[0]

            if parts[1] == 'T':
                port_type_table[interface_name] = 'Trunk'
            else:
                vlan_id = int(parts[1])
                vlan_table[interface_name] = vlan_id
                port_type_table[interface_name] = 'Access'

    return vlan_table, port_type_table, priority

def add_vlan_tag(data, vlan_id):
    return data[:12] + create_vlan_tag(vlan_id) + data[12:]

def remove_vlan_tag(data):
    # save without the VLAN tag
    return data[:12] + data[16:]
    
def manage_packet_transmission(switch, src_interface, dest_interface, length, data, vlan_id, vlan_table, port_type_table):

    # don't send the frame to the port on blocking state
    if switch.port_states[dest_interface] == 'Blocking':
        return

    src_interface_name = get_interface_name(src_interface)
    dest_interface_name = get_interface_name(dest_interface)

    if port_type_table[src_interface_name] == 'Trunk':

        if port_type_table[dest_interface_name] == 'Trunk':

            # send without any modifications
            send_to_link(dest_interface, length, data)

        elif port_type_table[dest_interface_name] == 'Access':

            # Check if the source and destination interfaces are in the same VLAN
            if (vlan_id == vlan_table[dest_interface_name]):
                data = remove_vlan_tag(data)
                send_to_link(dest_interface, length - 4, data)

    elif port_type_table[src_interface_name] == 'Access':
        vlan_id = vlan_table[src_interface_name]

        if port_type_table[dest_interface_name] == 'Trunk':
            data = add_vlan_tag(data, vlan_id)
            send_to_link(dest_interface, length + 4, data)

        elif port_type_table[dest_interface_name] == 'Access':
            if (vlan_id == vlan_table[dest_interface_name]):
                send_to_link(dest_interface, length, data)
        

def main():
    switch_id = sys.argv[1]

    num_interfaces = wrapper.init(sys.argv[2:])
    interfaces = range(0, num_interfaces)

    mac_table = {}
    vlan_table, port_type_table, priority = load_switch_config(switch_id)

    # Create a switch object
    switch = type('', (), {})()
    switch.own_bridge_id = priority
    switch.root_bridge_id = switch.own_bridge_id
    switch.root_path_cost = 0
    switch.root_port = -1
    switch.num_interfaces = num_interfaces
    switch.port_states = {}
    switch.port_type_table = port_type_table

    initialize_stp(switch)

    # Create and start a new thread that deals with sending BDPU
    t = threading.Thread(target = send_bdpu_every_sec, args = (switch,))
    t.start()

    for i in interfaces:
        print(get_interface_name(i))

    while True:
        interface, data, length = recv_from_any_link()

        dest_mac, src_mac, ethertype, vlan_id = parse_ethernet_header(data)

        # for testing using mininet
        # for port in range(switch.num_interfaces):
        #     print(f'Port {get_interface_name(port)} is in state {switch.port_states[port]}')

        # id we receive from a trunk port and it is blocking, we ignore the frame
        if switch.port_type_table.get(get_interface_name(interface)) == 'Trunk' and switch.port_states[interface] == 'Blocking':
            continue

        if dest_mac == b'\x01\x80\xC2\x00\x00\x00':
            process_bpdu(switch, data, length, interface)
            continue
        else:
            # Print the MAC src and MAC dst in human readable format
            dest_mac = ':'.join(f'{b:02x}' for b in dest_mac)
            src_mac = ':'.join(f'{b:02x}' for b in src_mac)

            print(f'Destination MAC: {dest_mac}')
            print(f'Source MAC: {src_mac}')
            print(f'EtherType: {ethertype}')

            print("Received frame of size {} on interface {}".format(length, interface), flush=True)


            # Update MAC table with the source MAC and interface
            mac_table[src_mac] = interface

            src_interface_name = get_interface_name(interface)
            src_port_type = port_type_table[src_interface_name]

            # Process frame based on destination MAC
            if is_unicast(dest_mac):
                if dest_mac in mac_table:
                    dest_interface = mac_table[dest_mac]
                    manage_packet_transmission(switch, interface, dest_interface, length, data, vlan_id, vlan_table, port_type_table)
                else:
                    for i in interfaces:
                        if i != interface:
                            manage_packet_transmission(switch, interface, i, length, data, vlan_id, vlan_table, port_type_table)
            else:
                for i in interfaces:
                    if i != interface:
                        manage_packet_transmission(switch, interface, i, length, data, vlan_id, vlan_table, port_type_table)

if __name__ == "__main__":
    main()
