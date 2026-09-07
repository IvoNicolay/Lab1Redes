import socket
import json

UDP_PORT = 6005 # Grupo 05
TIPO_AGENTE = "admin"

def descubrir_servidor():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_sock:
        udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        udp_sock.settimeout(5.0)
        
        mensaje = {"tipo": TIPO_AGENTE}
        payload = json.dumps(mensaje).encode('utf-8')
        
        print(f"AGENTE ADMIN: Buscando servidor en la red local...")
        udp_sock.sendto(payload, ('<broadcast>', UDP_PORT))
        
        try:
            data, addr = udp_sock.recvfrom(1024)
            respuesta = json.loads(data.decode('utf-8'))
            return addr[0], respuesta["tcp_port"]
        except socket.timeout:
            print("AGENTE ADMIN: No se encontró ningún servidor.")
            return None, None

if __name__ == "__main__":
    ip_servidor, puerto_tcp = descubrir_servidor()
    if ip_servidor and puerto_tcp:
        print(f"AGENTE ADMIN: Servidor de monitorización en {ip_servidor}:{puerto_tcp}")
        print("AGENTE ADMIN: Listo para iniciar conexión TCP y solicitar datos de clientes")
        # ACA SIGUE LA LOGICA PARA CONECTARSE AL SERVIDOR Y SOLICITAR DATOS DE LOS CLIENTES