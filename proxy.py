import os,sys,time, socket, select
import _thread as thread



SERVER_NAME = 'localhost'
BACKLOG = 40
MAX_RECV_BYTES = 256000
CLRF = b'\r\n'
REFERER_LOCATOR = b'Referer: '
DOC_IDENTIFIER = b'Accept: text/html'

STARTED = 'started'
ENDED = 'ended'
TOTAL = 'tolal'


class ProxyException(Exception):
    pass

# value: first number is opened connection, second is closed connection
telemetry_store = dict({ 'dummy': [0, 0] }) 

def main():
    i=0
    if len(sys.argv) < 2:
        print('no port provided, using 8080')
        PORT = 8080
    else:
        PORT = int(sys.argv[1])
        
    try:
        helloSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        helloSocket.bind((SERVER_NAME, PORT))
        helloSocket.listen(BACKLOG)
    except socket.error as e:
        print('CRITICAL ERROR: fail to open hello socket')
        print(e)
        if helloSocket:
            helloSocket.close()
        sys.exit(1)        

    # helloSocket.settimeout(7) -> can't do this because if no request, program is blocked at accept(), this is normal behavior
    while True:       
        try:
            connection, client_address = helloSocket.accept()
            # print(f'connecting to client: {client_address}, connection={i}')
            print(f'connection={i}')
            i+=1
            thread.start_new_thread(proxy_thread, (connection, client_address))
        except KeyboardInterrupt:
            helloSocket.shutdown(socket.SHUT_RDWR)


def proxy_thread(client_conn: socket.socket, client_address):
    while True:
        try:
            ## using while true will lead to diff websites using same TCP connection
            ## (firefox uses same network client process even for different websites?)
            request = client_conn.recv(MAX_RECV_BYTES)

            if not len(request): 
                client_conn.close()
                return
            
            port, hostname, http_method, url = get_fields(request)
            # print('fields:', port, hostname, http_method, url)
            
            if is_html_request(request):
                referer = remove_end_slash(url).decode()
            else:
                referer = remove_end_slash(get_referer(request)).decode()
            
            
            
            ## log
            # print(http_method.decode(),'\t',f'hostname={hostname.decode()}','\t',f'url={url.decode()}', '\t', f'referer={referer}')

            if not telemetry_store.get(referer):
                telemetry_store[referer] = {STARTED: 1, ENDED: 0, TOTAL: 0}
            else:
                telemetry_store[referer][STARTED] += 1
            
                
            ## make request on behalf of client
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
                        
                    
                    # print(f'payload_len:', payload_len)
                    telemetry_store[referer][TOTAL] += payload_len
                    telemetry_store[referer][ENDED] += 1
                    if telemetry_store[referer][STARTED] == telemetry_store[referer][ENDED]:
                        time.sleep(0.3)
                        if telemetry_store[referer][STARTED] == telemetry_store[referer][ENDED]:
                            print(referer, '\t', telemetry_store[referer][TOTAL])
                            del telemetry_store[referer]
                except socket.error as e:
                    print(e)
                    send_error_response(str(e), client_conn)
        
        except ProxyException as e:
            send_error_response(str(e), client_conn)
        # finally:
        #     client_conn.close()
    
            

def is_html_request(request: bytes):
    return request.find(DOC_IDENTIFIER) != -1 and request.find(DOC_IDENTIFIER) < request.find(CLRF + CLRF)

def get_referer(request: bytes):
    referer_pos = request.find(REFERER_LOCATOR)
    if referer_pos == -1:
        return b''
    cut_request = request[referer_pos:]
    end_pos = cut_request.find(CLRF)
    referer = cut_request[9:end_pos]
    # need error handling for if request is invalid
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
    client_conn.sendall(b"HTTP/1.0 400 Bad Request" + CLRF + CLRF 
                                    + b"###############################################\r\n"
                                    + b"Invalid Request. Please Check Your Request.\r\n"
                                    + e.encode()
                                    + b'\r\n'
                                    + b"###############################################\r\n")

if __name__ == '__main__':
   main()






   


""" this won't work (long time to load first image)
d = s.recv(2048)
if len(d):
    client_conn.sendall(d)
else:
    break
"""