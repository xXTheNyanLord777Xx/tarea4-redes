import sys
import SocketTCP

# Uso: python3 servidor_gbn.py localhost 8000
# Recibe un archivo con Go-Back-N y lo guarda en recibido.txt
address = (sys.argv[1], int(sys.argv[2]))
server_socketTCP = SocketTCP.SocketTCP()
server_socketTCP.bind(address)
connection_socketTCP, new_address = server_socketTCP.accept()
message = connection_socketTCP.recv(10000000, mode="go_back_n")
with open("recibido.txt", "wb") as f:
    f.write(message)
print("recibidos", len(message), "bytes (guardados en recibido.txt)")
connection_socketTCP.recv_close()
