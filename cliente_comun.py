import socket
import time
import psutil
import threading

UDP_PORT = 6005 # Grupo 05

def descubrir_servidor():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_sock:
        udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        udp_sock.settimeout(5.0)
        print(f"AGENTE COMÚN: Buscando servidor en la red local...")
        udp_sock.sendto(b"DISCOVER\n", ('<broadcast>', UDP_PORT))
        try:
            data, addr = udp_sock.recvfrom(1024)
            partes = data.decode('utf-8').strip().split()
            if len(partes) == 4 and partes[0] == "SERVER":
                return addr[0], int(partes[3]), float(partes[1]), float(partes[2])
        except socket.timeout:
            return None, None, None, None
    return None, None, None, None

# Funcion para hilo que escucha peticiones del servidor para obtener la lista de procesos
def escuchar_peticiones_servidor(tcp_sock):
    while True:
        try:
            datos = tcp_sock.recv(4096).decode('utf-8')
            if not datos: break
            
            mensajes = datos.split('\n')
            for msg in mensajes:
                if msg.strip() == "GET_PROC":
                    procesos = []
                    
                    # Capturamos los errores de permisos específicos de Windows (mitigacion a error registrado en informe)
                    for p in psutil.process_iter(['pid', 'name']):
                        try:
                            procesos.append(f"{p.info['pid']}:{p.info['name']}")
                        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                            pass # Ignoramos este proceso y continuamos
                    
                    proc_str = ",".join(procesos[:10])
                    respuesta = f"PROC {proc_str}\n"
                    tcp_sock.sendall(respuesta.encode('utf-8'))
        except Exception as e:
            print(f"[HILO ESCUCHA] Error: {e}")
            break

def iniciar_conexion_tcp_comun(ip_servidor, puerto_tcp, umbral_cpu, umbral_mem, clave):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tcp_sock:
        print(f"TCP: Conectando al servidor {ip_servidor}:{puerto_tcp}...")
        tcp_sock.connect((ip_servidor, puerto_tcp))
        
        # Fase de registro
        mensaje_registro = f"REGISTER {clave}\n"
        tcp_sock.sendall(mensaje_registro.encode('utf-8'))
        
        respuesta = tcp_sock.recv(1024).decode('utf-8').strip()
        
        if respuesta == "REG_RESP":
            print("TCP: ¡Registro exitoso como Agente Común!")
            print(f"Umbrales asignados: CPU={umbral_cpu}%, MEM={umbral_mem}%")

            #Lanzamos un hilo para escuchar peticiones del servidor
            hilo_escucha = threading.Thread(target=escuchar_peticiones_servidor, args=(tcp_sock,), daemon=True)
            hilo_escucha.start()

            # Inicializamos psutil.
            psutil.cpu_percent()
            print("Iniciando envío de metricas cada 15 segundos")
            
            while True:
                try:
                    #Recolectar datos con psutil
                    val_cpu = psutil.cpu_percent()
                    val_mem = psutil.virtual_memory().percent
                    
                    #Armar y enviar mensajes METRIC
                    msg_cpu = f"METRIC CPU {val_cpu}\n"
                    msg_mem = f"METRIC MEM {val_mem}\n"
                    
                    tcp_sock.sendall(msg_cpu.encode('utf-8'))
                    tcp_sock.sendall(msg_mem.encode('utf-8'))
                    print(f"METRIC Enviado: CPU: {val_cpu}% y MEM: {val_mem}%")
                    
                    #Validar umbrales y enviar mensajes ALERT si corresponde
                    if val_cpu > umbral_cpu:
                        msg_alert_cpu = f"ALERT CPU {val_cpu}\n"
                        tcp_sock.sendall(msg_alert_cpu.encode('utf-8'))
                        print(f"ALERTA CPU supero el umbral ({val_cpu} > {umbral_cpu})")
                        
                    if val_mem > umbral_mem:
                        msg_alert_mem = f"ALERT MEM {val_mem}\n"
                        tcp_sock.sendall(msg_alert_mem.encode('utf-8'))
                        print(f"ALERTA MEM supero el umbral ({val_mem} > {umbral_mem})")
                    
                    # Esperar 15 segundos antes de la siguiente lectura
                    time.sleep(15)
                    
                except (ConnectionResetError, BrokenPipeError):
                    print("ERROR: El servidor cerró la conexión inesperadamente.")
                    break # Salimos del bucle si el servidor se cae
        else:
            print(f"TCP: Error en el registro: {respuesta}")

if __name__ == "__main__":
    # Descubrimiento del servidor
    ip, puerto, u_cpu, u_mem = descubrir_servidor()
    
    if ip and puerto:
        # Solicitamos al usuario que ingrese la clave por consola
        clave_ingresada = input("Por favor, ingrese la clave secreta del servidor: ")
        iniciar_conexion_tcp_comun(ip, puerto, u_cpu, u_mem, clave_ingresada)