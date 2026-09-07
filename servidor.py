import socket
import json

UDP_PORT = 6005 # Grupo 05
TCP_PORT = 8080 # El puerto donde se levanta el socket TCP

def iniciar_discovery():
    # SOCK_DGRAM indica que es un socket UDP
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_sock:
        # '' (cadena vacía) permite escuchar en todas las interfaces de red
        udp_sock.bind(('', UDP_PORT))
        print(f"Escuchando broadcasts en el puerto UDP {UDP_PORT}...")
        
        while True:
            # recvfrom bloquea hasta recibir un paquete UDP
            data, addr = udp_sock.recvfrom(1024)
            mensaje_cliente = json.loads(data.decode('utf-8'))
            
            tipo_agente = mensaje_cliente.get("tipo")
            print(f"Solicitud de un agente '{tipo_agente}' desde la IP {addr[0]}")
            
            # Responder directamente a la IP y puerto temporal del cliente
            respuesta = {"status": "ok", "tcp_port": TCP_PORT}
            udp_sock.sendto(json.dumps(respuesta).encode('utf-8'), addr)

if __name__ == "__main__":
    iniciar_discovery()