import socket

UDP_PORT = 6005 # Grupo 05

def descubrir_servidor():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_sock:
        udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        udp_sock.settimeout(5.0)
        print(f"AGENTE ADMIN: Buscando servidor en la red local...")
        udp_sock.sendto(b"DISCOVER\n", ('<broadcast>', UDP_PORT))
        try:
            data, addr = udp_sock.recvfrom(1024)
            partes = data.decode('utf-8').strip().split()
            if len(partes) == 4 and partes[0] == "SERVER":
                return addr[0], int(partes[3])
        except socket.timeout:
            return None, None
    return None, None

def iniciar_conexion_tcp_admin(ip_servidor, puerto_tcp, clave):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tcp_sock:
        print(f"TCP: Conectando al servidor {ip_servidor}:{puerto_tcp}...")
        tcp_sock.connect((ip_servidor, puerto_tcp))
        
        # Armamos el mensaje de autenticación Admin usando la clave tipeada
        mensaje_registro = f"ADMIN {clave}\n"
        tcp_sock.sendall(mensaje_registro.encode('utf-8'))
        
        respuesta = tcp_sock.recv(1024).decode('utf-8').strip()
        
        if respuesta == "ADMIN_RESP":
            print("TCP: ¡Registro exitoso como Agente Administrador!")
            print("--- CONSOLA DE ADMINISTRACIÓN ---")
            print("Comandos disponibles:")
            print("  L               -> Listar agentes conectados")
            print("  M <x> <metric>  -> Obtener métrica (CPU/MEM) del agente <x>")
            print("  P <x>           -> Obtener procesos del agente <x>")
            print("  END             -> Finalizar sesión de administración")
            
            # Bucle interactivo de consola
            while True:
                comando = input("\nAdmin> ").strip()
                
                if not comando:
                    continue
                    
                # Procesamos el comando L (Listado de agentes)
                if comando.upper() == 'L':
                    # Enviamos el mensaje al servidor asegurando el salto de línea
                    tcp_sock.sendall(b"LIST_AGENTS\n")
                    
                    datos = tcp_sock.recv(1024).decode('utf-8').strip()
                    
                    # El servidor debe responder con el formato AGENTS
                    if datos.startswith("AGENTS"):
                        partes = datos.split()
                        cantidad = partes[1]
                        
                        # Extraemos los IDs si la cantidad es mayor a 0
                        ids = partes[2:] if len(partes) > 2 else []
                        
                        print(f"Se encontraron {cantidad} agentes comunes:")
                        for id_agente in ids:
                            print(f"   - Agente ID: {id_agente}")
                    elif datos == "ERROR":
                        print("ERROR: El servidor rechazó la solicitud.")
                    else:
                        print(f"INFO: Respuesta: {datos}")

                elif comando.upper().startswith('M '):
                    partes = comando.split()
                    if len(partes) == 3:
                        id_agente = partes[1] # Asumimos que el usuario ingresa directamente el ID del agente
                        metrica = partes[2].upper()
                        
                        # Armamos el mensaje GET_METRIC <id_agente> <nombre_metrica>
                        mensaje = f"GET_METRIC {id_agente} {metrica}\n"
                        tcp_sock.sendall(mensaje.encode('utf-8'))
                        
                        respuesta = tcp_sock.recv(4096).decode('utf-8').strip()
                        
                        # Formato esperado: MEASUREMENTS <id> <métrica> <cant> <valores...>
                        if respuesta.startswith("MEASUREMENTS"):
                            resp_partes = respuesta.split()
                            valores = resp_partes[4:] # Los valores empiezan en el indice 4
                            print(f"Ultimos valores de {metrica} para el Agente {id_agente}: {', '.join(valores)}")
                        else:
                            print("ERROR: No se pudieron obtener las métricas.")
                    else:
                        print("ERROR: Formato incorrecto. Uso: M <id> <CPU|MEM>")

                elif comando.upper().startswith('P '):
                    partes = comando.split()
                    if len(partes) == 2:
                        id_agente = partes[1]
                        
                        # Mensaje GET_PROC <id_agente>
                        tcp_sock.sendall(f"GET_PROC {id_agente}\n".encode('utf-8'))
                        
                        respuesta = tcp_sock.recv(4096).decode('utf-8').strip()
                        if respuesta.startswith("PROC"):
                            print(f"Procesos del Agente {id_agente}:")
                            resp_partes = respuesta.split(" ", 2)
                            if len(resp_partes) == 3:
                                lista_procesos = resp_partes[2].split(',')
                                for p in lista_procesos:
                                    print(f"   - {p}")
                        else:
                            print("ERROR: No se pudo obtener la lista de procesos.")
                        
                elif comando.upper() == 'END':
                    tcp_sock.sendall(b"END\n")
                    break
                else:
                    print("ERROR: Comando no implementado")
        else:
            print(f"TCP: Error en el registro: {respuesta}")

if __name__ == "__main__":
    # Descubrimiento del servidor
    ip, puerto = descubrir_servidor()
    
    if ip and puerto:
        # Solicitamos la clave de administración
        clave_ingresada = input("Ingrese la clave secreta de administración: ")
        
        iniciar_conexion_tcp_admin(ip, puerto, clave_ingresada)