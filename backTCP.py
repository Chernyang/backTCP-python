import os
import socket
import time
import threading

from utils import log


class BTcpConnection:
    def __init__(self, mode, addr, port):
        # Create a TCP socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.conn = None
        self.remote_addr = None

        if mode == 'send':
            self.remote_addr = addr, port
            self.sock.connect(self.remote_addr)
            self.conn = self.sock

        elif mode == 'recv':
            self.sock.bind((addr, port))
            log('info', f"Listening on {addr} port {port}")
            self.sock.listen(1)
            self.conn, self.remote_addr = self.sock.accept()
            log('info', f"Accepted connection from {self.remote_addr[0]} port {self.remote_addr[1]}")
        else:
            raise ValueError(f"Unexpected mode {mode}")

    def __del__(self):
        self.close()

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass
        try:
            self.sock.close()
        except Exception:
            pass
        # set them to None so other code knows
        self.conn = None
        self.sock = None

    def settimeout(self, timeout):
        self.sock.settimeout(timeout)

    def send(self, packet):
        if packet is None:
            packet = b''
        self.conn.sendall(bytes(packet))

    def recv(self):
        return BTcpPacket.from_bytes(self.conn.recv(7 + 64))


class BTcpPacket:
    def __init__(self, sport=0, dport=0, seq=0, ack=0, data_off=0, win_size=0, flag=0, data=b""):
        self.sport = sport
        self.dport = dport
        self.seq = seq
        self.ack = ack
        self.data_off = data_off
        self.win_size = win_size
        self.flag = flag
        self.data = data

    def regulate(self):
        # Make sure the values don't stir up
        self.seq &= 0xFF
        self.ack &= 0xFF
        self.data_off &= 0xFF
        self.win_size &= 0xFF
        self.flag &= 1  # Could be 0xFF, but we only need "retransmission" flag

    def __bytes__(self):
        self.regulate()
        return bytes([
            self.sport, self.dport, self.seq, self.ack,
            self.data_off, self.win_size, self.flag,
        ]) + bytes(self.data)

    @staticmethod
    def from_bytes(data):
        if not data:
            return None
        return BTcpPacket(
            sport=data[0], dport=data[1], seq=data[2], ack=data[3],
            data_off=data[4], win_size=data[5], flag=data[6], data=data[7:]
        )

    def __repr__(self):
        if len(self.data) > 1:
            s = f"<{len(self.data)} bytes>"
        elif len(self.data) == 0:
            s = "<empty>"
        else:
            s = "<1 byte>"
        return f"BTcpPacket(seq={self.seq}, ack={self.ack}, win_size={self.win_size}, flag={self.flag}, data={s})"


def sender_recv(conn, nextseqnum, length, List):
    while (List[0] < length):
        s = conn.recv()
        # print("s.ack: " + str(s.ack))
        if (s and s.ack == List[0] & 0xFF):
            List[0] = List[0] + 1
            if (List[0] == nextseqnum):
                # Window is empty
                List[2] = 0
            else:
                List[1] = time.time()
                List[2] = 1


def send(data, addr, port):
    conn = BTcpConnection('send', addr, port)

    chunks = [data[x * 64:x * 64 + 64] for x in range((len(data) - 1) // 64 + 1)]
    packets = [BTcpPacket(seq=i & 0xFF, data_off=7, data=chunk) for i, chunk in enumerate(chunks)]

    # TODO: "data" is a bytes object
    #       You should split it up into BTcpPacket objects, and call conn.send(pkt) on each one
    # Example: > p = BTcpPacket(data=b"hello")
    #          > conn.send(p)

    # TODO: Delete the following code and add your own
    nextseqnum = 0
    List = [0, 0, 0]    # List[0] is base, List[1] is t, List[2] is timer
    thr = threading.Thread(target=sender_recv, args=(conn, nextseqnum, len(packets), List))
    thr.start()
    while (List[0] < len(packets)):
        if (nextseqnum < List[0] + 8 and nextseqnum < len(packets)):
            conn.send(packets[nextseqnum])
            if (List[0] == nextseqnum):
                List[1] = time.time()  # start timer
                List[2] = 1
            nextseqnum += 1
        if (time.time() - List[1] >= 0.010 and List[2] == 1):
            # timeout
            for i in range(List[0], nextseqnum):
                packets[i].flag = 1
            nextseqnum = List[0]
            List[2] = 0
    conn.close()
    # End of your own code
    return


def recv(addr, port):
    conn = BTcpConnection('recv', addr, port)

    data = b''  # Nothing received yet

    # TODO: Call conn.recv to receive packets
    #       Received packets are of class BTcpPacket, so you can access packet information and content easily
    # Example: > p = conn.recv()
    #          Now p.seq, p.ack, p.data (and everything else) are available

    # TODO: Assemble received binary data into `data` variable.
    #       Make sure you're handling disorder and timeouts properly
    expectedseqnum = 0
    ackpkt = BTcpPacket(ack=255, data=b"nnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnn")
    while True:
        p = conn.recv()
        if (p is None):
            break
        if (p.seq == expectedseqnum):
            data += p.data
            ackpkt = BTcpPacket(ack=expectedseqnum, data=b"nnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnn")
            conn.send(ackpkt)
            expectedseqnum = (expectedseqnum + 1) & 0xFF
        else:
            conn.send(ackpkt)

    # while True:
    #     p = conn.recv()
    #     if p is None:  # No more packets
    #         break
    #     data += p.data

    # End of your own code
    conn.close()
    return data
