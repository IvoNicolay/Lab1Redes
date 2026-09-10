import socket
import threading
import time 

# Configuracion
UDP_PORT = 6005 # Grupo 05
TCP_PORT = 8080
CLAVE_SECRETA = "grupo05"
UMBRAL_CPU = 80
UMBRAL_MEM = 85

# Estado global del servidor
agentes_comunes = {} # Formato: { id_agente: {"socket": conn, "CPU": [], "MEM": []} }
id_generador = 1

#  DESCUBRIMIENTO UDP
def iniciar_servidor_udp():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_sock:
        udp_sock.bind(('', UDP_PORT))
        print(f"UDP: Escuchando broadcasts en el puerto {UDP_PORT}...")
        
        while True:
            data, addr = udp_sock.recvfrom(1024)
            mensaje = data.decode('utf-8').strip()
            
            if mensaje == "DISCOVER":
                print(f"UDP: DISCOVER recibido desde {addr[0]}")
                # Formato: SERVER <umbral_cpu> <umbral_mem> <puerto_tcp>
                respuesta = f"SERVER {UMBRAL_CPU} {UMBRAL_MEM} {TCP_PORT}\n"
                udp_sock.sendto(respuesta.encode('utf-8'), addr)

# CONEXIÓN TCP
def manejar_cliente_tcp(conn, addr):
    print(f"TCP: Nueva conexion entrante desde {addr}")
    with conn:
        try:
            data = conn.recv(1024).decode('utf-8')
            if not data: return
            
            partes = data.strip().split()
            
            # Validacion Agente Común
            if len(partes) == 2 and partes[0] == "REGISTER" and partes[1] == CLAVE_SECRETA:
                conn.sendall(b"REG_RESP\n")
                
                global id_generador
                mi_id = id_generador
                id_generador += 1
                
                # Inicializamos su espacio en memoria
                agentes_comunes[mi_id] = {"socket": conn, "CPU": [], "MEM": []}
                print(f"Agente COMUN aceptado. ID Asignado: {mi_id}")
                
                # Bucle de monitorizacion
                while True:
                    datos_crudos = conn.recv(1024).decode('utf-8')
                    if not datos_crudos: 
                        break 
                        
                    # Procesamos cada mensaje separado por \n
                    mensajes = datos_crudos.split('\n')
                    for msg in mensajes:
                        if not msg.strip(): continue
                        
                        cmd = msg.strip().split()
                        
                        # Guardar hasta 10 metricas de CPU y MEM por agente
                        if cmd[0] == "METRIC" and len(cmd) == 3:
                            metrica = cmd[1] # "CPU" o "MEM"
                            valor = cmd[2]
                            
                            agentes_comunes[mi_id][metrica].append(valor)
                            if len(agentes_comunes[mi_id][metrica]) > 10:
                                agentes_comunes[mi_id][metrica].pop(0)
                                
                        # Recibir la lista de procesos del agente comun
                        elif cmd[0] == "PROC":
                            # Guardamos los procesos temporalmente en la memoria del servidor
                            agentes_comunes[mi_id]["procesos"] = " ".join(cmd[1:])
                        # Registrar alertas en bitácora
                        elif cmd[0] == "ALERT" and len(cmd) == 3:
                            print(f"ALERTA: Agente {mi_id}: {cmd[1]} excedió umbral con {cmd[2]}")
                
                # Limpieza al desconectar (Mensaje END o caida)
                print(f"Agente {mi_id} desconectado.")
                del agentes_comunes[mi_id]

            # Validación Agente Admin
            elif len(partes) == 2 and partes[0] == "ADMIN" and partes[1] == CLAVE_SECRETA:
                conn.sendall(b"ADMIN_RESP\n")
                print(f"Agente ADMIN aceptado: {addr}")
                
                # Bucle para recibir peticiones del administrador
                while True:
                    datos_crudos = conn.recv(1024).decode('utf-8')
                    if not datos_crudos: break
                    
                    mensajes = datos_crudos.split('\n')
                    for msg in mensajes:
                        if not msg.strip(): continue
                        
                        cmd = msg.strip().split()
                        # Evaluamos si solicita la lista de agentes
                        if cmd[0] == "LIST_AGENTS":
                            # Obtenemos las claves (IDs) del diccionario global
                            ids_conectados = list(agentes_comunes.keys())
                            cantidad = len(ids_conectados)
                            
                            # Convertimos la lista de IDs a un string separado por espacios
                            ids_str = " ".join(map(str, ids_conectados))
                            respuesta = f"AGENTS {cantidad} {ids_str}\n"
                            if cantidad == 0:
                                respuesta = f"AGENTS 0\n"
                                
                            conn.sendall(respuesta.encode('utf-8'))
                        # Evaluamos si solicita la lista de procesos de un agente
                        elif cmd[0] == "GET_PROC" and len(cmd) == 2:
                            try:
                                id_agente = int(cmd[1])
                                if id_agente in agentes_comunes:
                                    sock_agente = agentes_comunes[id_agente]["socket"]
                                    agentes_comunes[id_agente]["procesos"] = None
                                    
                                    sock_agente.sendall(b"GET_PROC\n")
                                    
                                    intentos = 0
                                    while agentes_comunes[id_agente].get("procesos") is None and intentos < 50:
                                        time.sleep(0.1)
                                        intentos += 1
                                    
                                    proc_data = agentes_comunes[id_agente].get("procesos")
                                    if proc_data:
                                        conn.sendall(f"PROC {id_agente} {proc_data}\n".encode('utf-8'))
                                    else:
                                        conn.sendall(b"ERROR\n")
                                else:
                                    conn.sendall(b"ERROR\n")
                            except Exception as e:
                                print(f"[SERVER] Error protegido en GET_PROC: {e}")
                                conn.sendall(b"ERROR\n")
                        # Evaluamos si solicita metricas
                        elif cmd[0] == "GET_METRIC" and len(cmd) == 3:
                            try:
                                id_agente = int(cmd[1])
                                metrica = cmd[2]
                                
                                if id_agente in agentes_comunes and metrica in ["CPU", "MEM"]:
                                    valores = agentes_comunes[id_agente][metrica]
                                    cantidad = len(valores)
                                    
                                    # map(str) previene crasheos si Python interpreta algo como float
                                    valores_str = " ".join(map(str, valores))
                                    respuesta = f"MEASUREMENTS {id_agente} {metrica} {cantidad} {valores_str}\n"
                                    conn.sendall(respuesta.encode('utf-8'))
                                else:
                                    conn.sendall(b"ERROR\n")
                            except Exception as e:
                                print(f"[SERVER] Error protegido en GET_METRIC: {e}")
                                conn.sendall(b"ERROR\n")
                        # Manejo del cierre de conexión
                        elif msg.strip() == "END":
                            print(f"Agente ADMIN {addr} se desconectó.")
                            return 
                
        except ConnectionResetError:
            print(f"TCP: Conexión perdida con {addr}")

def iniciar_servidor_tcp():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tcp_sock:
        tcp_sock.bind(('', TCP_PORT))
        tcp_sock.listen()
        print(f"TCP: Escuchando conexiones en el puerto {TCP_PORT}...")
        
        while True:
            conn, addr = tcp_sock.accept()
            hilo = threading.Thread(target=manejar_cliente_tcp, args=(conn, addr))
            hilo.start()

if __name__ == "__main__":
    # Arrancamos el servidor UDP en un hilo en segundo plano
    hilo_udp = threading.Thread(target=iniciar_servidor_udp, daemon=True)
    hilo_udp.start()
    
    # El hilo principal se queda ejecutando el servidor TCP
    iniciar_servidor_tcp()