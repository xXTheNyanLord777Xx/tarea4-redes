import sys
import SocketTCP

# Uso: python3 cliente_gbn.py localhost 8000 [on|off] < archivo
# El tercer argumento activa (on, por defecto) o desactiva (off) el control de congestión.
address = (sys.argv[1], int(sys.argv[2]))
cc_on = len(sys.argv) < 4 or sys.argv[3] != "off"
message = sys.stdin.buffer.read()

client_socketTCP = SocketTCP.SocketTCP()
client_socketTCP.set_congestion_control(cc_on)
client_socketTCP.connect(address)
client_socketTCP.send(message, mode="go_back_n")
print("control de congestion:", "on" if cc_on else "off")
print("segmentos enviados:", client_socketTCP.number_of_sent_segments)
client_socketTCP.close()
