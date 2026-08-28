# cliente.py y servidor.py — Documentación del código existente

Este documento explica en detalle el funcionamiento del código **actualmente
presente** en `servidor.py` y `cliente.py`. Se trata de un ejemplo mínimo de
comunicación cliente-servidor sobre TCP usando la API de sockets de Python
(el mismo tipo de programa de referencia usado en la Parte 1 del obligatorio
para practicar capturas con `tcpdump`/`wireshark`). Este README **no**
documenta el protocolo completo de monitorización pedido en la Parte 2
(agentes `comun`/`admin`, descubrimiento por UDP, métricas, etc.); solo
describe qué hace el código tal como está escrito hoy.

## Resumen general

- Ambos programas usan el módulo estándar `socket` de Python, sin ninguna
  librería que oculte el uso de sockets.
- La comunicación es **TCP** (`socket.SOCK_STREAM`) sobre **IPv4**
  (`socket.AF_INET`).
- El servidor escucha en `127.0.0.1:65432` (loopback, solo accesible desde la
  misma máquina) y atiende **una única conexión de cliente a la vez**.
- Todo el intercambio de datos se hace como texto codificado/decodificado en
  UTF-8 (`str.encode('utf-8')` / `bytes.decode('utf-8')`), ya que los sockets
  transmiten `bytes`, no `str`.

## `servidor.py`

```python
HOST = '127.0.0.1'
PORT = 65432
```
Define la dirección IP y el puerto donde el servidor va a escuchar
conexiones entrantes. Al ser `127.0.0.1`, solo procesos de la misma máquina
pueden conectarse.

### Creación y configuración del socket

```python
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
```
Crea un socket TCP/IPv4. El uso de `with` garantiza que el socket se cierre
automáticamente (se libera el file descriptor / puerto) al salir del bloque,
incluso si ocurre una excepción.

```python
s.bind((HOST, PORT))
```
Asocia (*bind*) el socket a la dirección IP y puerto indicados. A partir de
este punto el sistema operativo sabe que las conexiones dirigidas a
`127.0.0.1:65432` deben entregarse a este proceso.

```python
s.listen()
```
Pone el socket en modo pasivo/escucha: el socket queda habilitado para
aceptar conexiones entrantes en una cola interna, pero todavía no acepta
ninguna.

```python
print(f"Servidor escuchando en {HOST}:{PORT}...")
```
Mensaje informativo por consola indicando que el servidor está listo.

### Aceptar una conexión

```python
conn, addr = s.accept()
```
Llamada **bloqueante**: el programa se detiene aquí hasta que llega una
conexión entrante. Cuando un cliente se conecta, `accept()` devuelve:
- `conn`: un **nuevo socket**, distinto del socket de escucha `s`, que se usa
  exclusivamente para intercambiar datos con ese cliente en particular.
- `addr`: una tupla `(ip, puerto)` con el origen de la conexión entrante.

Como el servidor solo llama a `accept()` una vez (no hay bucle alrededor de
esta línea), **atiende una sola conexión por ejecución** y luego termina.

```python
with conn:
    print(f"Conectado por el cliente: {addr}")
```
El socket de la conexión (`conn`) también se maneja con `with` para
asegurar su cierre automático. Se imprime la dirección del cliente
conectado.

### Bucle de recepción y respuesta

```python
while True:
    data = conn.recv(1024)
    if not data:
        break
```
El servidor entra en un bucle infinito en el que:
1. `conn.recv(1024)` espera (de forma bloqueante) datos del cliente, leyendo
   hasta 1024 bytes por llamada. TCP es un protocolo orientado a flujo de
   bytes, por lo que `recv` puede devolver menos datos de los que el cliente
   envió en un solo `send`, o fragmentos de varios envíos juntos; en este
   ejemplo no se hace ningún tipo de reensamblado porque el intercambio es
   trivial (un mensaje, una respuesta).
2. Si `data` es un objeto de bytes vacío (`b''`), significa que el cliente
   cerró la conexión (envió un FIN); el `break` saca al servidor del bucle.

```python
    print(f"Recibido: {data.decode('utf-8')}")
    conn.sendall(b"Mensaje recibido por el servidor!")
```
Si llegaron datos, se decodifican de bytes a texto UTF-8 y se muestran por
consola. Luego, el servidor responde siempre con el mismo mensaje fijo
`"Mensaje recibido por el servidor!"` (ya codificado como bytes con el
prefijo `b`), usando `sendall`, que garantiza que **todos** los bytes se
envíen (a diferencia de `send`, que puede enviar solo una parte).

Nótese que el contenido recibido no se interpreta ni se usa para decidir la
respuesta: cualquier mensaje que mande el cliente obtiene siempre la misma
contestación (es un servidor de eco fijo, no un eco literal ni un parser de
comandos).

Cuando el cliente cierra la conexión, el bucle `while True` termina
(`break`), se sale del `with conn:` (cerrando `conn`) y luego del `with
socket(...)` externo (cerrando el socket de escucha `s`), y el proceso del
servidor finaliza. Es decir, **el servidor no vuelve a llamar a `accept()`**,
por lo que no admite un segundo cliente sin reiniciar el programa.

## `cliente.py`

```python
HOST = '127.0.0.1'
PORT = 65432
```
Misma IP y puerto que el servidor, para poder conectarse a él.

### Conexión

```python
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT))
```
Crea un socket TCP/IPv4 (también gestionado con `with` para cierre
automático) e inicia activamente la conexión hacia el servidor
(`connect`), realizando el three-way handshake de TCP. Esta llamada
bloquea hasta que la conexión se establece (o falla, p. ej. si no hay
ningún servidor escuchando en ese puerto, lo que lanzaría una excepción
`ConnectionRefusedError`).

### Envío del mensaje

```python
mensaje = "Hola Servidor, soy el Cliente"
s.sendall(mensaje.encode('utf-8'))
```
Define un string fijo y lo codifica a bytes UTF-8 antes de enviarlo, ya que
los sockets solo transmiten bytes. `sendall` asegura que se transmita el
mensaje completo.

### Recepción de la respuesta

```python
data = s.recv(1024)
```
Bloquea esperando la respuesta del servidor, leyendo hasta 1024 bytes.

```python
print(f"Respuesta del servidor: {data.decode('utf-8')}")
```
Esta línea está **fuera** del bloque `with`, por lo que se ejecuta después
de que el socket ya se cerró automáticamente al salir del `with`. Como
`data` fue leída dentro del bloque (antes del cierre), su valor sigue
disponible y se puede decodificar e imprimir sin problema.

Tras enviar un único mensaje y recibir una única respuesta, el cliente no
tiene ningún bucle: termina su ejecución después de este `print`, cerrando
implícitamente la conexión (al salir del `with`, lo que envía un FIN al
servidor y es lo que provoca que `conn.recv` en el servidor devuelva datos
vacíos y este último corte su bucle).

## Flujo completo de una ejecución

1. Se ejecuta `servidor.py`. Este hace `bind` + `listen` y queda bloqueado en
   `accept()`, imprimiendo que está escuchando.
2. Se ejecuta `cliente.py`. Este hace `connect()`, lo que desbloquea el
   `accept()` del servidor.
3. El servidor imprime la dirección del cliente y queda esperando en
   `recv()`.
4. El cliente envía `"Hola Servidor, soy el Cliente"` con `sendall`.
5. El servidor recibe esos bytes, los imprime, y responde con
   `"Mensaje recibido por el servidor!"`.
6. El cliente recibe esa respuesta con `recv` e imprime
   `"Respuesta del servidor: Mensaje recibido por el servidor!"`.
7. El cliente sale de su bloque `with`, cerrando el socket y por lo tanto la
   conexión TCP.
8. El servidor detecta la conexión cerrada (`recv` devuelve `b''`), sale del
   bucle `while True`, cierra `conn` y luego el socket de escucha, y el
   programa termina.

## Cómo ejecutarlo

En dos terminales distintas (el servidor debe iniciarse primero):

```bash
# Terminal 1
python servidor.py

# Terminal 2 (una vez que el servidor esté escuchando)
python cliente.py
```

Cada ejecución de `servidor.py` atiende exactamente un cliente y luego
finaliza; para aceptar una nueva conexión hay que volver a ejecutar
`servidor.py`.

## Relación con el enunciado del Obligatorio 1

Este par de archivos corresponde al ejemplo mínimo de socket TCP mencionado
en la **Parte 1** del enunciado (`Obligatorio1-2026.pdf`), usado allí como
material de referencia para practicar capturas con `tcpdump`/`wireshark`
sobre tráfico TCP en loopback. Cabe notar dos diferencias respecto a lo
descripto en esa parte del enunciado (sin que esto implique un error, ya que
el enunciado deja el puerto y los comandos como algo a adaptar):

- El puerto usado aquí es `65432`, mientras que el ejercicio de captura de
  la Parte 1 indica usar el puerto `2026`.
- Este servidor no interpreta comandos de texto (`par <n>` / `impar <n>`)
  como se describe en ese ejercicio de la Parte 1: siempre responde el mismo
  mensaje fijo, sin importar lo que reciba.

Este código **no** implementa aún el protocolo de monitorización de la
**Parte 2** (fase de descubrimiento por UDP, `REGISTER`/`REG_RESP`,
`METRIC`, `ALERT`, agentes `comun`/`admin`, `cliente_comun.py`,
`cliente_admin.py`, etc.); es simplemente el punto de partida sobre sockets
TCP básicos.
