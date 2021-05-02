import socket
import struct
import threading
import time
import binascii


class MulticastSendProcess:

    def __init__(self):
        self.mcast_group_ip = '239.0.0.1'
        self.mcast_group_port = 23456
        self.message_max_size = 2048
        self.base = 0
        self.next_seq_num = 0
        self.window_size = 4
        self.window_is_full = False
        self.window_is_ack = [0, 0, 0, 0]
        self.window_is_nak = [0, 0, 0, 0]
        self.total_nak_num = 0
        self.message_nak_num = {}
        self.group_size = 1
        self.struct = struct.Struct('IIII')
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.file_buffer = [[i, bytes(1000)] for i in range(20)]
        self.congestion_window = 1
        self.timer = threading.Timer(0.2, self.resent_message)

    def multicast_send(self, buffer_block):
        data = (buffer_block[0], 0, 0, len(buffer_block[1]))
        s = struct.Struct('IIII')
        packed_data = s.pack(*data) + buffer_block[1]
        self.sock.sendto(packed_data, (self.mcast_group_ip, self.mcast_group_port))
        print(
            f'{time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())}: message ' + str(buffer_block[0]) + ' send finish')

    def send_buffer(self):
        buffer_length = len(self.file_buffer)
        self.timer.start()
        while True:
            if buffer_length >= self.base and not self.window_is_full and self.next_seq_num - self.base < self.congestion_window:
                self.multicast_send(self.file_buffer[self.next_seq_num])
                self.next_seq_num += 1
                self.window_is_full = False if self.next_seq_num - self.base < self.window_size else True

    def multicast_receive(self):
        while True:
            data, address = self.sock.recvfrom(self.message_max_size)
            (message_id, is_ack, is_nak, message_length) = self.struct.unpack(data[0:16])
            window_current = message_id - self.base
            if window_current <= 3:
                if is_ack:
                    self.window_is_ack[window_current] += 1
                    self.check_window()
                    print(message_id, "ACK", address)
                elif is_nak:
                    self.total_nak_num += 1
                    self.congestion_window -= 1 / self.group_size
                    if self.message_nak_num.get(message_id) is None:
                        self.message_nak_num[message_id] = 1
                    else:
                        self.message_nak_num[message_id] += 1
                    print(message_id, "NAK", address)
                    self.check_nak()
                else:
                    pass
            else:
                raise ValueError

    def check_window(self):
        while self.window_is_ack[0] > 0:
            self.window_is_ack.pop(0)
            self.window_is_ack.append(0)
            self.base += 1
            self.timer.cancel()
            self.new_timer()
            self.timer.start()
            self.congestion_window += 1
            self.window_is_full = False if self.next_seq_num - self.base < self.window_size else True

    def check_nak(self):
        if self.total_nak_num > 0:
            while len(self.message_nak_num) > 0:
                self.multicast_send(self.file_buffer[self.message_nak_num.popitem()[0]])
                self.total_nak_num -= 1

    def resent_message(self):
        print("resend message: ", self.base)
        self.timer.cancel()
        self.multicast_send(self.file_buffer[self.base])
        self.new_timer()
        self.timer.start()
        self.congestion_window = 1

    def new_timer(self):
        self.timer = threading.Timer(0.2, self.resent_message)

    def run(self):
        thread_routines = [
            self.send_buffer,
            self.multicast_receive
        ]
        threads = []
        for thread_routine in thread_routines:
            thread = threading.Thread(target=thread_routine)
            thread.daemon = True
            thread.start()
            threads.append(thread)
        for thread in threads:
            thread.join()


if __name__ == '__main__':
    multicast_send_process = MulticastSendProcess()
    multicast_send_process.run()
