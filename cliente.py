import socket

HOST = '127.0.0.1'  # La misma IP del servidor
PORT = 65432        # El mismo puerto del servidor

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT))
    
    # Codificamos el string a bytes y lo enviamos
    mensaje = "Hola Servidor, soy el Cliente"
    s.sendall(mensaje.encode('utf-8'))
    
    # Esperamos la respuesta
    data = s.recv(1024)

print(f"Respuesta del servidor: {data.decode('utf-8')}")