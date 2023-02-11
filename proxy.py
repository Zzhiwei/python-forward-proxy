import sys,time, socket
import _thread as thread

# configs
SERVER_NAME = ''
BACKLOG = 40
MAX_RECV_BYTES = 256000
PORT = IS_FLAG = ATK_FLAG = None

# constants
CLRF = b'\r\n'
REFERER_LOCATOR = b'Referer: '
HOST_LOCATOR = b'Host: '
DOC_IDENTIFIER = b'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp'
IMAGE_IDENTIFIER = b'Accept: image/avif,image/webp'
SUBSTITUTION = b'GET http://ocna0.d2.comp.nus.edu.sg:50000/change.jpg HTTP/1.0\r\nHost: ocna0.d2.comp.nus.edu.sg:50000\r\n'
STARTED = 'started'
ENDED = 'ended'
TOTAL = 'tolal'
ATTACK_HTML = b'<html><head><title>You are being attacked</title></head><body><center><h1>You are being attacked</h1></center></body></html>'

# store
telemetry_store = dict({}) 

def main():
    global IS_FLAG, ATK_FLAG
    if len(sys.argv) < 4:
        print('ERROR: missing arguments')
        sys.exit(1)
    else:
        try:
            PORT = int(sys.argv[1])
            IS_FLAG = int(sys.argv[2])
            ATK_FLAG = int(sys.argv[3])
        except ValueError:
            print('ERROR: invalid argument types, please enter numbers')
            sys.exit(1)
        
    try:
        helloSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        helloSocket.bind((SERVER_NAME, PORT))
        helloSocket.listen(BACKLOG)
    except socket.error as e:
        print(e)
        print('ERROR: fail to open hello socket, port could be still in use')
        if helloSocket:
            helloSocket.close()
        sys.exit(1)        

    while True:       
        try:
            connection, client_address = helloSocket.accept()
            thread.start_new_thread(proxy_thread, (connection, client_address))
        except KeyboardInterrupt:
            helloSocket.close()


def proxy_thread(client_conn: socket.socket, client_address):
    timeout_count = 0
    while True:
        try:
            client_conn.settimeout(5)
            request = client_conn.recv(MAX_RECV_BYTES)
            client_conn.settimeout(None)
            
            if not len(request): 
                client_conn.close()
                return
            if ATK_FLAG:
                send_attack_message(client_conn)
                client_conn.close()
                return 
            
            port, hostname, http_method, url = get_fields(request)
            
            
            if is_html_request(request):
                referer = remove_end_slash(url).decode()
            else:
                referer = remove_end_slash(get_referer(request)).decode()
            
            # log
            # print(http_method.decode(),'\t',f'hostname={hostname.decode()}', '\t', f'port={port}','\t',f'url={url.decode()}', '\t', f'referer={referer}')

            if not telemetry_store.get(referer):
                telemetry_store[referer] = {STARTED: 1, ENDED: 0, TOTAL: 0}
            else:
                telemetry_store[referer][STARTED] += 1
            
            
            if IS_FLAG and is_image_request(request):
                hostname, port, request = "ocna0.d2.comp.nus.edu.sg", 50000, modify_req(request)
                
            # make request on behalf of client
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.connect((hostname, port))
                    s.sendall(request)
                    in_body = False
                    header = b''
                    payload_len = 0
                    
                    while True:
                        try:
                            s.settimeout(5)
                            if not in_body:
                                header += s.recv(8)
                                header_end_pos = header.find(CLRF+CLRF)
                                if header_end_pos != -1:
                                    payload_len += len(header[header_end_pos+4:])
                                    client_conn.sendall(header)
                                    in_body = True
                            else:
                                content = s.recv(4096)
                                size = len(content)
                                if size:
                                    payload_len += size
                                    client_conn.sendall(content)
                            s.settimeout(None)
                        except socket.timeout:
                            break
                    
                    telemetry_store[referer][TOTAL] += payload_len
                    telemetry_store[referer][ENDED] += 1
                    if telemetry_store[referer][STARTED] == telemetry_store[referer][ENDED]:
                        # time out wait to check no more requests from website
                        thread.start_new_thread(telemetry_thread, (referer,))
                        
                except socket.error as e:
                    send_error_response(str(e), client_conn)
                    client_conn.close()
                    sys.exit(1)
                    
        except socket.timeout:
            timeout_count += 1
            if timeout_count > 3:
                client_conn.close()
                break
        except ProxyException as e:
            send_error_response(str(e), client_conn)
            client_conn.close()
            sys.exit(1)
        except (ConnectionResetError, OSError):
            return

def send_attack_message(conn: socket.socket):
    conn.send(b'HTTP/1.0 200 OK' + CLRF)
    conn.send(b'Content-Type: text/html' + CLRF + CLRF)
    conn.send(ATTACK_HTML) 

def modify_req(request: bytes):
    start_index = request.find(CLRF, request.find(CLRF) + 4) + 4
    return SUBSTITUTION + request[start_index:]
    
def telemetry_thread(referer: str):
    time.sleep(1)
    if telemetry_store[referer][STARTED] == telemetry_store[referer][ENDED]:
        print(f'{referer}, ', telemetry_store[referer][TOTAL])
        del telemetry_store[referer]

def is_html_request(request: bytes):
    return request.find(DOC_IDENTIFIER) != -1 and request.find(DOC_IDENTIFIER) < request.find(CLRF + CLRF)

def is_image_request(request: bytes):
    return request.find(IMAGE_IDENTIFIER) != -1 and request.find(IMAGE_IDENTIFIER) < request.find(CLRF + CLRF)

def get_referer(request: bytes):
    referer_pos = request.find(REFERER_LOCATOR)
    if referer_pos == -1:
        return b''
    cut_request = request[referer_pos:]
    end_pos = cut_request.find(CLRF)
    referer = cut_request[9:end_pos]
    return referer

def remove_end_slash(s: bytes):
    if not s:
        return b''
    # 47 is code for b'/', negative indexing work differently from str for bytes
    return s[:-1] if s[-1] == 47 else s

def get_fields(request: bytes):
    try:
        first_line = request.split(CLRF)[0]
        first_line_arr = first_line.split(b' ')
        http_method = first_line_arr[0]
        url =  first_line_arr[1] # example: http://localhost:3000/
        
        url_start = url.find(b'://')
        if (url_start == -1):
            truncated_url = url 
        else:
            truncated_url = url[url_start+3:] # example: www.google.com:3000/
        
        end_pos = truncated_url.find(b'/')
        port_colon_pos = truncated_url.find(b':') 
        
        if end_pos == -1:
            end_pos = len(truncated_url)
        
        if (port_colon_pos == -1):
            port = 80
            hostname = truncated_url[:end_pos]
        elif port_colon_pos > end_pos:
            raise ProxyException('')
        else:
            port = int(truncated_url[port_colon_pos+1:end_pos])
            hostname = truncated_url[:port_colon_pos]
    except Exception:
        raise ProxyException('invalid url provided')

    return port, hostname, http_method, url

def send_error_response(e: str, client_conn: socket.socket):
    # use HTTP 1.0 (works for hosts using both 1.0 and 1.1 due to backward compatibility)
    try:
        client_conn.sendall(b'HTTP/1.0 400 Bad Request' + CLRF)
        client_conn.sendall(b'Content-Type: text/html' + CLRF*2)
        client_conn.sendall(b'<h1>Invalid Request: %s</h1>' % e.encode())
        client_conn.sendall(b'<h2>Check your request and try again!</h2>')
    except BrokenPipeError:
        return

class ProxyException(Exception):
    pass

if __name__ == '__main__':
   main()
