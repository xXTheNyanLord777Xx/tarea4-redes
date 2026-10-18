"""
Experimento de la sección Pruebas (punto 5):
compara Go-Back-N CON y SIN control de congestión.

Para cada corrida levanta un servidor y un cliente (procesos separados),
envía el archivo con mode="go_back_n", mide el tiempo que demora send()
y cuenta los segmentos enviados (number_of_sent_segments).

Uso (con netem ya activado, por ejemplo:
     sudo tc qdisc add dev lo root netem loss 20.0% delay 0.1s):

    python3 experimento.py                       # archivo_grande.txt, 5 corridas por modo
    python3 experimento.py otro_archivo.txt 5
"""
import json
import subprocess
import sys
import time

ARCHIVO = sys.argv[1] if len(sys.argv) > 1 else "archivo_grande.txt"
REPETICIONES = int(sys.argv[2]) if len(sys.argv) > 2 else 5
TIMEOUT_EXPERIMENTO = 0.5   # timeout pedido por el enunciado (menos de 1 s)
PUERTO_BASE = 9100

# Código que corre el servidor en su propio proceso
CODIGO_SERVIDOR = """
import sys, SocketTCP
SocketTCP.TIMEOUT = {timeout}
SocketTCP.DEBUG = False
s = SocketTCP.SocketTCP()
s.bind(("localhost", {puerto}))
c, _ = s.accept()
recibido = c.recv(10**7, mode="go_back_n")
original = open("{archivo}", "rb").read()
print("IDENTICO" if recibido == original else "DISTINTO", flush=True)
c.recv_close()
"""

# Código que corre el cliente en su propio proceso
CODIGO_CLIENTE = """
import json, time, SocketTCP
SocketTCP.TIMEOUT = {timeout}
SocketTCP.DEBUG = False
mensaje = open("{archivo}", "rb").read()
c = SocketTCP.SocketTCP()
c.set_congestion_control({cc_on})
c.connect(("localhost", {puerto}))
inicio = time.time()
c.send(mensaje, mode="go_back_n")
duracion = time.time() - inicio
print(json.dumps({{"tiempo": duracion, "segmentos": c.number_of_sent_segments}}), flush=True)
c.close()
"""


def netem_activo():
    try:
        salida = subprocess.run(["tc", "qdisc", "show", "dev", "lo"],
                                capture_output=True, text=True).stdout
        return "netem" in salida, salida.strip()
    except FileNotFoundError:
        return False, "(no se encontró el comando tc)"


def una_corrida(cc_on, puerto):
    params = dict(timeout=TIMEOUT_EXPERIMENTO, puerto=puerto, archivo=ARCHIVO, cc_on=cc_on)
    servidor = subprocess.Popen([sys.executable, "-c", CODIGO_SERVIDOR.format(**params)],
                                stdout=subprocess.PIPE, text=True)
    time.sleep(0.3)  # darle tiempo al servidor para hacer bind
    cliente = subprocess.run([sys.executable, "-c", CODIGO_CLIENTE.format(**params)],
                             capture_output=True, text=True, timeout=600)
    salida_servidor, _ = servidor.communicate(timeout=600)
    if cliente.returncode != 0:
        raise RuntimeError("el cliente falló:\n" + cliente.stderr)
    datos = json.loads(cliente.stdout.strip().splitlines()[0])
    datos["integro"] = salida_servidor.strip().startswith("IDENTICO")
    return datos


def main():
    activo, estado = netem_activo()
    print("Estado de netem:", estado)
    if not activo:
        print("ADVERTENCIA: netem NO está activo, el experimento correrá SIN pérdidas.")
    largo = len(open(ARCHIVO, "rb").read())
    print(f"Archivo: {ARCHIVO} ({largo} bytes), TIMEOUT = {TIMEOUT_EXPERIMENTO} s, "
          f"{REPETICIONES} corridas por modo\n")

    resultados = {True: [], False: []}
    puerto = PUERTO_BASE
    # Se alternan los modos (con, sin, con, sin, ...) para que ambos se vean
    # afectados por igual si cambian las condiciones del computador.
    for i in range(REPETICIONES):
        for cc_on in (True, False):
            r = una_corrida(cc_on, puerto)
            puerto += 1
            resultados[cc_on].append(r)
            modo = "CON control" if cc_on else "SIN control"
            print(f"corrida {i+1} {modo:12s}: {r['tiempo']:7.2f} s  "
                  f"{r['segmentos']:5d} segmentos  {'íntegro' if r['integro'] else 'NO ÍNTEGRO'}",
                  flush=True)

    print("\n| Corrida | Con CC: tiempo (s) | Con CC: segmentos | Sin CC: tiempo (s) | Sin CC: segmentos |")
    print("|---|---|---|---|---|")
    for i in range(REPETICIONES):
        a, b = resultados[True][i], resultados[False][i]
        print(f"| {i+1} | {a['tiempo']:.2f} | {a['segmentos']} | {b['tiempo']:.2f} | {b['segmentos']} |")
    prom = lambda lista, k: sum(x[k] for x in lista) / len(lista)
    a, b = resultados[True], resultados[False]
    print(f"| **Promedio** | **{prom(a,'tiempo'):.2f}** | **{prom(a,'segmentos'):.1f}** | "
          f"**{prom(b,'tiempo'):.2f}** | **{prom(b,'segmentos'):.1f}** |")
    todos = all(x["integro"] for x in a + b)
    print("\nTodos los archivos llegaron íntegros." if todos
          else "\nATENCIÓN: hubo corridas en que el archivo NO llegó íntegro.")


if __name__ == "__main__":
    main()
