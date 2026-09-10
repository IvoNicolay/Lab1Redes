# Sistema de Monitorización Distribuida — Documentación del código

Este documento explica en detalle el funcionamiento del código **actualmente
presente** en `servidor.py`, `cliente_comun.py` y `cliente_admin.py`. Implementa
el protocolo de monitorización de la **Parte 2** del enunciado
(`Obligatorio1-2026.pdf`): un servidor central que recibe métricas de varios
*agentes comunes* y responde consultas de un *agente administrador*, con
descubrimiento automático por broadcast UDP y comunicación de datos por TCP.

## Arquitectura general

Hay tres roles, cada uno en su propio archivo:

| Archivo               | Rol                                                                 |
|-----------------------|----------------------------------------------------------------------|
| `servidor.py`         | Servidor central. Escucha UDP (descubrimiento) y TCP (datos).       |
| `cliente_comun.py`    | Agente monitoreado: reporta CPU/MEM y responde pedidos de procesos. |
| `cliente_admin.py`    | Consola de administración: consulta agentes conectados.             |

El flujo siempre es el mismo:

1. El cliente (común o admin) hace **descubrimiento por UDP** (broadcast) para
   encontrar la IP del servidor y el puerto TCP a usar.
2. El cliente abre una **conexión TCP** contra ese puerto y se autentica con
   una clave compartida (`CLAVE_SECRETA`).
3. A partir de ahí, cliente y servidor intercambian mensajes de texto en
   líneas terminadas en `\n`, cada uno con un formato `COMANDO arg1 arg2 ...`.

Todos los mensajes se codifican/decodifican como UTF-8, igual que en el
ejemplo básico de sockets: los sockets solo transmiten `bytes`.

## Configuración compartida

```python
UDP_PORT = 6005        # Grupo 05 — puerto de descubrimiento
TCP_PORT = 8080        # Puerto de datos (servidor.py)
CLAVE_SECRETA = "grupo05"
UMBRAL_CPU = 80
UMBRAL_MEM = 85
```

`UDP_PORT` está hardcodeado igual en los tres archivos (debe coincidir para
que el descubrimiento funcione). `CLAVE_SECRETA`, `UMBRAL_CPU` y `UMBRAL_MEM`
solo existen en `servidor.py`; los umbrales se envían a los clientes comunes
durante el descubrimiento, y la clave la debe ingresar manualmente el usuario
en ambos clientes (no está hardcodeada en ellos).

## `servidor.py`

### Estado global

```python
agentes_comunes = {}   # { id_agente: {"socket": conn, "CPU": [...], "MEM": [...], "procesos": "..."} }
id_generador = 1
```

Un diccionario en memoria (compartido entre hilos) que guarda, por cada
agente común conectado, su socket TCP y el historial de sus métricas. No hay
lock explícito protegiendo este diccionario pese a que se accede desde
múltiples hilos (uno por conexión); funciona porque el GIL de Python serializa
las operaciones individuales sobre el dict, pero no hay atomicidad entre
lecturas/escrituras compuestas.

### Hilo de descubrimiento UDP (`iniciar_servidor_udp`)

Escucha datagramas en `UDP_PORT`. Ante un mensaje `DISCOVER`, responde al
remitente (unicast, usando la dirección de origen del datagrama) con:

```
SERVER <umbral_cpu> <umbral_mem> <puerto_tcp>
```

Este hilo corre en modo `daemon=True` en segundo plano; el hilo principal del
proceso queda dedicado al servidor TCP.

### Servidor TCP (`iniciar_servidor_tcp`)

Bucle clásico de servidor concurrente: `bind` + `listen` en `TCP_PORT`, y por
cada conexión aceptada (`accept()`) se lanza un **hilo nuevo**
(`manejar_cliente_tcp`) para atenderla. A diferencia del ejemplo mínimo de
socket con una sola conexión, este servidor sí soporta múltiples clientes
simultáneos, cada uno en su propio hilo.

### Manejo de cada conexión (`manejar_cliente_tcp`)

El primer mensaje recibido decide el rol de la conexión:

- **`REGISTER <clave>`** → agente común.
- **`ADMIN <clave>`** → agente administrador.

Cualquier otro primer mensaje no es validado explícitamente (la función
simplemente no entra en ninguna de las dos ramas y termina, cerrando la
conexión por el `with conn:`).

#### Rama agente común

1. Responde `REG_RESP\n`.
2. Asigna un `id` autoincremental (`id_generador`) y crea su entrada en
   `agentes_comunes`.
3. Entra en un bucle de `recv` que puede traer **varios mensajes pegados**
   en un mismo `recv` (TCP es un flujo de bytes, no de mensajes); por eso se
   hace `datos_crudos.split('\n')` y se procesa cada línea no vacía por
   separado. Comandos soportados desde el agente común:
   - `METRIC <CPU|MEM> <valor>` — agrega el valor a la lista correspondiente,
     recortando a los últimos 10 valores (`pop(0)` si se supera ese tamaño).
   - `PROC <p1> <p2> ...` — guarda la lista de procesos recibida (como string)
     en `agentes_comunes[id]["procesos"]`, para responder a una consulta
     pendiente del admin.
   - `ALERT <CPU|MEM> <valor>` — solo se imprime en la consola del servidor a
     modo de bitácora; no se reenvía a ningún admin ni se persiste.
4. Cuando `recv` devuelve vacío (el agente se desconectó), se elimina su
   entrada de `agentes_comunes`.

#### Rama agente admin

1. Responde `ADMIN_RESP\n`.
2. Entra en un bucle similar, aceptando estos comandos:
   - **`LIST_AGENTS`** → responde `AGENTS <cantidad> <id1> <id2> ...\n` (o
     `AGENTS 0\n` si no hay agentes conectados), listando las claves actuales
     del diccionario `agentes_comunes`.
   - **`GET_PROC <id_agente>`** → si el `id` existe, reenvía `GET_PROC\n` **al
     socket del agente común correspondiente** y espera (haciendo *polling*
     con `time.sleep(0.1)`, hasta 50 intentos ≈ 5 s) a que aparezca el campo
     `"procesos"` en su entrada del diccionario. Si llega a tiempo, responde
     `PROC <id_agente> <procesos>\n`; si no, o si el agente no existe,
     responde `ERROR\n`.
   - **`GET_METRIC <id_agente> <CPU|MEM>`** → si el agente y la métrica son
     válidos, responde `MEASUREMENTS <id> <metrica> <cantidad> <v1> <v2> ...\n`
     con el historial guardado (hasta 10 valores); si no, `ERROR\n`.
   - **`END`** → corta el bucle y termina la conexión de ese admin (no afecta
     a otros clientes).

Nótese que `GET_PROC` viaja **dos veces** por la red: el admin se lo pide al
servidor, y el servidor a su vez se lo reenvía al agente común dueño de esos
procesos; el servidor actúa de intermediario, no guarda los procesos de forma
proactiva (solo cuando se los piden).

## `cliente_comun.py`

### Descubrimiento (`descubrir_servidor`)

Envía `DISCOVER\n` por broadcast UDP y espera (con timeout de 5 s) una
respuesta `SERVER <umbral_cpu> <umbral_mem> <puerto_tcp>`. Devuelve la IP de
origen de la respuesta, el puerto TCP y ambos umbrales ya convertidos a
`float`. Si no hay respuesta a tiempo, devuelve una tupla de `None`.

### Registro y bucle de métricas (`iniciar_conexion_tcp_comun`)

1. Se conecta por TCP y envía `REGISTER <clave>\n` (la clave la tipea el
   usuario por consola al arrancar el programa).
2. Si el servidor responde `REG_RESP`, lanza un **hilo secundario**
   (`escuchar_peticiones_servidor`) dedicado exclusivamente a escuchar
   pedidos entrantes del servidor (hoy en día, solo `GET_PROC`), mientras el
   hilo principal queda libre para el bucle de métricas.
3. Cada 15 segundos (`time.sleep(15)`), usando `psutil`:
   - Mide `cpu_percent()` y `virtual_memory().percent`.
   - Envía `METRIC CPU <valor>\n` y `METRIC MEM <valor>\n`.
   - Si algún valor supera su umbral asignado, además envía
     `ALERT CPU <valor>\n` / `ALERT MEM <valor>\n`.
4. Si la conexión se cae (`ConnectionResetError` / `BrokenPipeError`), el
   bucle termina y el programa finaliza.

### Hilo de escucha (`escuchar_peticiones_servidor`)

Corre en paralelo al bucle de métricas, compartiendo el mismo socket TCP.
Ante un mensaje `GET_PROC` proveniente del servidor, usa
`psutil.process_iter(['pid', 'name'])` para listar procesos del sistema,
ignorando los que generan `NoSuchProcess`/`AccessDenied`/`ZombieProcess`
(errores de permisos típicos en Windows), se queda con los primeros 10, y
responde `PROC <pid1>:<nombre1>,<pid2>:<nombre2>,...\n`.

Como dos hilos distintos escriben sobre el mismo socket (el bucle de
métricas y este hilo de escucha), existe la posibilidad teórica de que dos
`sendall` se intercalen; en la práctica no se observó problema porque cada
mensaje se manda en una sola llamada a `sendall` con salto de línea al final.

## `cliente_admin.py`

### Descubrimiento y registro

Igual mecanismo UDP que el agente común (`descubrir_servidor`), pero sin
umbrales: solo interesan la IP y el puerto TCP. Luego se conecta por TCP y
envía `ADMIN <clave>\n` (la clave también se pide por consola). Si el
servidor responde `ADMIN_RESP`, entra en una consola interactiva.

### Consola interactiva (`iniciar_conexion_tcp_admin`)

Bucle `input("\nAdmin> ")` que interpreta comandos tipeados por el operador:

| Comando           | Efecto                                                                 |
|-------------------|--------------------------------------------------------------------------|
| `L`               | Envía `LIST_AGENTS`, muestra la cantidad e IDs de agentes conectados.  |
| `M <id> <CPU\|MEM>` | Envía `GET_METRIC <id> <metrica>`, muestra los últimos valores recibidos. |
| `P <id>`          | Envía `GET_PROC <id>`, muestra la lista de procesos de ese agente.     |
| `END`             | Envía `END` y cierra la sesión de administración.                     |

Cualquier otro texto imprime `ERROR: Comando no implementado`. Las
respuestas del servidor se parsean con `split()` asumiendo el formato exacto
descrito en la sección de `servidor.py` (por ejemplo, en `M` los valores
empiezan en el índice 4 de `MEASUREMENTS <id> <metrica> <cant> <v1> ...`).

## Formato de mensajes (resumen del protocolo)

Todos los mensajes son texto plano terminado en `\n`, con campos separados
por espacios.

**Descubrimiento (UDP):**
```
Cliente → Servidor:  DISCOVER
Servidor → Cliente:  SERVER <umbral_cpu> <umbral_mem> <puerto_tcp>
```

**Registro (TCP):**
```
Agente común  → Servidor:  REGISTER <clave>
Servidor      → Agente:    REG_RESP
Agente admin  → Servidor:  ADMIN <clave>
Servidor      → Admin:     ADMIN_RESP
```

**Reporte del agente común (TCP, cada 15 s):**
```
METRIC <CPU|MEM> <valor>
ALERT  <CPU|MEM> <valor>          (solo si se superó el umbral)
```

**Consultas del admin (TCP):**
```
LIST_AGENTS                  → AGENTS <cant> <id1> <id2> ...
GET_METRIC <id> <CPU|MEM>    → MEASUREMENTS <id> <metrica> <cant> <v1> ... | ERROR
GET_PROC <id>                → PROC <id> <procesos> | ERROR
END                           → (cierra la sesión, sin respuesta)
```

**Reenvío interno del servidor al agente (TCP):**
```
Servidor → Agente común:  GET_PROC
Agente común → Servidor:  PROC <pid1>:<nombre1>,<pid2>:<nombre2>,...
```

## Cómo ejecutarlo

En tres terminales distintas (el servidor debe iniciarse primero; requiere
`psutil` instalado para el agente común: `pip install psutil`):

```bash
# Terminal 1 — servidor
python servidor.py

# Terminal 2 — uno o más agentes comunes (repetir en más terminales para simular varios)
python cliente_comun.py
# pide la clave secreta ("grupo05") por consola

# Terminal 3 — consola de administración
python cliente_admin.py
# pide la clave secreta ("grupo05") por consola
```

El servidor y los clientes deben estar en la misma red local (o el mismo
host) para que el broadcast UDP de descubrimiento llegue.

## Limitaciones conocidas

- No hay ningún lock protegiendo `agentes_comunes` frente a acceso
  concurrente entre hilos; funciona por la serialización que impone el GIL,
  pero no es una solución explícitamente sincronizada.
- Los mensajes `ALERT` del agente común solo se imprimen por consola en el
  servidor; no hay forma de que un admin consulte alertas pasadas ni de que
  se le notifiquen alertas en tiempo real.
- `GET_PROC` desde el admin usa espera activa (*polling* con `sleep(0.1)`)
  en vez de un mecanismo de sincronización como un evento o condición.
- La clave secreta (`CLAVE_SECRETA`) viaja en texto plano por la red sin
  ningún cifrado.
