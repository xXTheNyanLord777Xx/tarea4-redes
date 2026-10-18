import SocketTCP

address = ("localhost", 8000)

# CLIENT
client_socketTCP = SocketTCP.SocketTCP()
client_socketTCP.connect(address)
# test 1
message = "Mensje de len=16".encode()
client_socketTCP.send(message, mode="go_back_n")
# test 2
message = "Mensaje de largo 19".encode()
client_socketTCP.send(message, mode="go_back_n")
# test 3
message = "Mensaje de largo 19".encode()
client_socketTCP.send(message, mode="go_back_n")
# test 4
message = ("a" * 21 + "b" * 21).encode()
client_socketTCP.send(message, mode="go_back_n")

client_socketTCP.close()
print("OK")