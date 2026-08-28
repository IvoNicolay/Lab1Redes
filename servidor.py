import socket

HOST = '127.0.0.1'  # IP Local
PORT = 65432        # Puerto de escucha

# with garantiza que el socket se cierre automáticamente al terminar
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind((HOST, PORT)) # asocia el socket a la dirección y puerto especificados
    s.listen() # pone el socket en modo escucha, esperando conexiones entrantes
    print(f"Servidor escuchando en {HOST}:{PORT}...")
    
    # conn es el nuevo socket para interactuar con este cliente específico
    conn, addr = s.accept() # Operacion bloquante hasta recibir una conexión entrante
    with conn:
        print(f"Conectado por el cliente: {addr}")
        while True:
            data = conn.recv(1024) # Recibir hasta 1024 bytes
            if not data:
                break # Si data está vacío, el cliente cerro la conexión
            
            print(f"Recibido: {data.decode('utf-8')}")
            # Enviar de vuelta una respuesta
            conn.sendall(b"Mensaje recibido por el servidor!")