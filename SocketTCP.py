import socket
import random
import time

from socketUDP import SocketUDP
from slidingWindowCC import SlidingWindowCC
from CongestionControl import CongestionControl

TIMEOUT = 1
DEBUG = True
LOSS_RATE = 0.0
HEADER_SIZE = 5
MAX_DATA_SIZE = 16
UDP_BUFF = HEADER_SIZE + MAX_DATA_SIZE  

def debug(msj):
    if DEBUG:
        print("debug: ", msj)

class SocketTCP:
    def __init__(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.dest = None
        self.seq = None
        self.bytes_faltantes = 0
        self.buff = b""
        #parte 3
        self.congestion_control_on = True   
        self.congestion_controler = None      
        self.number_of_sent_segments = 0     

    @staticmethod
    def parse_segment(seg):
        flags = seg[0]
        return {"SYN": flags & 4 != 0,
                "ACK": flags & 2 != 0,
                "FIN": flags & 1 != 0,
                "SEQ": int.from_bytes(seg[1:5],"big"),
                "DATA": seg[5:]
                }

    @staticmethod
    def create_segment(seg):
        flags = 0
        if seg["SYN"]:
            flags += 4
        if seg["ACK"]:
            flags += 2
        if seg["FIN"]:
            flags += 1
        return bytes([flags]) + seg["SEQ"].to_bytes(4,"big") + seg["DATA"]

    @staticmethod
    def new_segment(seq, syn = False, ack = False, fin = False, data = b""):
        return {"SYN": syn,
                "ACK": ack,
                "FIN": fin,
                "SEQ": seq,
                "DATA": data
                }

    def send_segment(self, seg, address = None):
        if address is None:
            address = self.dest
        if random.random() < LOSS_RATE:
            debug("LOST %s" % seg)
        else:
            self.socket.sendto(self.create_segment(seg),address)

    def recive_segment(self):
        data, address = self.socket.recvfrom(UDP_BUFF)
        return self.parse_segment(data), address

    def bind(self, address):
        self.socket.bind(address)

    def connect(self, address):
        self.seq = random.randint(0,100)
        self.socket.settimeout(TIMEOUT)
        while True:
            self.send_segment(self.new_segment(self.seq, syn = True), address)
            try:
                seg, naddress = self.recive_segment()
            except socket.timeout:
                debug("TIMEOUT, reenviando SYNC")
                continue
            if seg["SYN"] and seg["ACK"] and seg["SEQ"] == self.seq + 1:
                break
        self.dest = naddress
        self.seq += 2
        self.send_segment(self.new_segment(self.seq, ack = True))
        debug("conexion establecida")

    def accept(self):
        self.socket.settimeout(None)
        while True:
            seg, caddress = self.recive_segment()
            if seg["SYN"] and not seg["ACK"]:
                break
        tcp = SocketTCP()
        tcp.socket.bind((self.socket.getsockname()[0],0))
        tcp.dest = caddress
        tcp.seq = seg["SEQ"] + 1
        tcp.socket.settimeout(TIMEOUT)
        while True:
            tcp.send_segment(self.new_segment(tcp.seq, syn = True, ack = True))
            try:
                res, _ = tcp.recive_segment()
            except socket.timeout:
                debug("TIMEOUT esperando ACK del handshake, reenviando SYN+ACK")
                continue
            if res["ACK"] and not res["SYN"] and res["SEQ"] == tcp.seq + 1:
                break
        tcp.seq += 1
        debug("conexion establecida")
        return tcp, tcp.socket.getsockname()

    def send_stop_and_wait(self, data):
        seg = self.new_segment(self.seq, data = data)
        ack = self.seq + len(data)
        self.socket.settimeout(TIMEOUT)
        while True:
            self.send_segment(seg)
            try:
                while True:
                    res, _ = self.recive_segment()
                    if res["ACK"] and not res["SYN"] and res["SEQ"] == ack:
                        self.seq = ack
                        return
                    if res["SYN"] and res["ACK"]:
                        debug("SYN+ACK repetido, reenviando ACK del handshake")
                        self.send_segment(self.new_segment(self.seq, ack = True))
            except socket.timeout:
                debug("TIMEOUT esperando ACK %d, retransmitiendiendo %s" % (ack, data))

    def send_using_stop_and_wait(self, msj):
        self.send_stop_and_wait(str(len(msj)).encode())
        for i in range(0, len(msj), MAX_DATA_SIZE):
            self.send_stop_and_wait(msj[i:i+MAX_DATA_SIZE])

    def recv_data(self):
        self.socket.settimeout(None)
        while True:
            seg, _ = self.recive_segment()
            if seg["SYN"] or seg["ACK"] or seg["FIN"]:
                continue
            if seg["SEQ"] == self.seq:
                self.seq = self.seq + len(seg["DATA"])
                self.send_segment(self.new_segment(self.seq, ack = True))
                return seg["DATA"]
            debug("dato repetido, reenviando ACK %d" % self.seq)
            self.send_segment(self.new_segment(self.seq, ack = True))

    def recv_using_stop_and_wait(self, buff_size):
        if self.bytes_faltantes == 0:
            self.bytes_faltantes = int(self.recv_data().decode())
        cantidad = min(self.bytes_faltantes, buff_size)
        while len(self.buff) < cantidad:
            self.buff += self.recv_data()
        res = self.buff[:cantidad]
        self.buff = self.buff[cantidad:]
        self.bytes_faltantes -= cantidad
        return res

    def close(self):
        self.socket.settimeout(TIMEOUT)
        recv = False
        for intento in range(3):
            self.send_segment(self.new_segment(self.seq, fin = True))
            try:
                while True:
                    res, _ = self.recive_segment()
                    if res["FIN"] and res["ACK"] and res["SEQ"] == self.seq + 1:
                        recv = True
                        break
                break
            except socket.timeout:
                debug("timeout esperando FIN+ACK, reenviando FIN")
        if recv:
            for i in range(3):
                self.send_segment(self.new_segment(self.seq + 2, ack = True))
                time.sleep(TIMEOUT)
            debug("conexion cerrada")
        else:
            debug("3 TIMEOUTs sin FIN+ACK, se asume que la contraparte cerro")
        self.socket.close()

    def recv_close(self):
        self.socket.settimeout(None)
        while True:
            seg, _ = self.recive_segment()
            if seg["FIN"] and not seg["ACK"]:
                break
            if not seg["SYN"] and not seg["ACK"]:
                self.send_segment(self.new_segment(self.seq, ack = True))
        fin_ack = self.new_segment(seg["SEQ"] + 1, fin = True, ack = True)
        ack_esperado = seg["SEQ"] + 2
        self.socket.settimeout(TIMEOUT)
        self.send_segment(fin_ack)
        timeouts = 0
        while timeouts < 3:
            try:
                res, _ = self.recive_segment()
            except socket.timeout:
                timeouts += 1
                if timeouts < 3:
                    debug("TIMEOUT esperando ultimo ACK, reenviando FIN+ACK")
                    self.send_segment(fin_ack)
                continue
            if res["ACK"] and not res["FIN"] and res["SEQ"] == ack_esperado:
                debug("conexion cerrada")
                break
            if res["FIN"] and not res["ACK"]:
                debug("FIN repetido, reenviando FIN+ACK")
                self.send_segment(fin_ack)
        if timeouts == 3:
            debug("3 TIMEOUTs sin ACK, se asume que la contraparte cerro")
        self.socket.close()


#ACTIVIDAD CONTROL DE CONGESTION:

    def send(self, message, mode="stop_and_wait"):
        if mode == "stop_and_wait":
            self.send_using_stop_and_wait(message)
        elif mode == "go_back_n":
            self.send_using_go_back_n(message)
    
    def recv(self, buff_size, mode="stop_and_wait"):
        if mode == "stop_and_wait":
            return self.recv_using_stop_and_wait(buff_size)
        elif mode == "go_back_n":
            return self.recv_using_go_back_n(buff_size)

    #ya viene implementada la logica :3, el receptor gobackn es igual al de
    #stop and wait
    def recv_using_go_back_n(self, buff_size):
        return self.recv_using_stop_and_wait(buff_size)


    def send_using_go_back_n(self, msj):
        #CAMBIOS PARTE 3
        MSS = 8
        data_list = [str(len(msj)).encode()] + [msj[i:i+MSS] for i in range(0, len(msj), MSS)]
        if self.congestion_control_on:
            self.congestion_controler = CongestionControl(MSS)
            window_size = self.congestion_controler.get_MSS_in_cwnd()    
            self.debug_cc("inicio", window_size)
        else:
            window_size = 8
        window = SlidingWindowCC(window_size, data_list, self.seq)
        #socket
        udp = SocketUDP()
        udp.socket_udp.close()
        udp.socket_udp = self.socket
        self.socket.setblocking(False)
        udp.settimeout(TIMEOUT)

        def enviar(i):
            seg = self.new_segment(window.get_sequence_number(i), data=window.get_data(i))
            udp.sendto(self.create_segment(seg), self.dest, timer_index=0)
            #PARTE 3
            self.number_of_sent_segments += 1

        #enviar toda la ventana
        for i in range(window_size):
            if window.get_data(i) is not None:
                enviar(i)

        while window.get_data(0) is not None:
            try:
                ans, _ = udp.recvfrom(UDP_BUFF)
            except TimeoutError:
                debug("TIMEOUT, reenviando ventana")
                udp.stop_timer(0)
                if self.congestion_control_on:
                    self.congestion_controler.event_timeout()
                    window_size = self.congestion_controler.get_MSS_in_cwnd()
                    window.update_window_size(window_size)
                    self.debug_cc("timeout", window_size)
                for i in range(window_size):
                    if window.get_data(i) is not None:
                        enviar(i)
                continue

            res = self.parse_segment(ans)
            if res["SYN"] and res["ACK"]:
                debug("SYN+ACK repetido, reenviando ACK del handshake")
                self.send_segment(self.new_segment(self.seq, ack=True))
                continue
            if not res["ACK"] or res["FIN"]:
                continue

            ack = res["SEQ"]
            pasos = 0
            while (window.get_data(0) is not None and window.get_sequence_number(0) + len(window.get_data(0)) <= ack):
                window.move_window(1)
                pasos += 1
            if pasos == 0:
                continue  
            self.seq = ack

            #debug
            tamano_anterior = window_size
            if self.congestion_control_on:
                self.congestion_controler.event_ack_received()
                window_size = self.congestion_controler.get_MSS_in_cwnd()
                window.update_window_size(window_size)
                self.debug_cc("ack %d" % ack, window_size)
            #nuevas casillas
            primero_nuevo = max(0, tamano_anterior - pasos)
            nuevos = [i for i in range(primero_nuevo, window_size) if window.get_data(i) is not None]
            if nuevos or window.get_data(0) is None:
                udp.stop_timer(0)
            for i in nuevos:
                enviar(i)

        if udp.timer_list[0] is not None:
            udp.stop_timer(0)
        self.socket.setblocking(True)

    #parte 3
    def set_congestion_control(self, on):
        self.congestion_control_on = on

    def debug_cc(self, evento, window_size):
        cc = self.congestion_controler
        estado = "slow start" if cc.is_state_slow_start() else "congestion avoidance"
        debug("[CC] %-12s estado=%-20s cwnd=%6.2f ssthresh=%s window_size=%d"
            % (evento, estado, cc.get_cwnd(), cc.get_ssthresh(), window_size))

        
        