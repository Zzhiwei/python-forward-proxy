import os,sys,time, socket, select
import _thread as thread



SERVER_NAME = 'localhost'
BACKLOG = 40
MAX_RECV_BYTES = 256000
CLRF = b'\r\n'
REFERER_LOCATOR = b'Referer: '
DOC_IDENTIFIER = b'Accept: text/html'


# value: first number is opened connection, second is closed connection
referer_db = dict({ 'dummy': [0, 0] }) 
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
            print(f'connecting to client: {client_address}, connection={i}')
            i+=1
            thread.start_new_thread(proxy_thread, (connection, client_address))
        except KeyboardInterrupt:
            helloSocket.shutdown(socket.SHUT_WR)


def proxy_thread(client_conn: socket.socket, client_address):
    referers = {}
    # keeping this will lead to diff websites using same TCP connection
    # (firefox uses same network client process even for different websites?)
    while True: 
        request = client_conn.recv(MAX_RECV_BYTES) # get client request
        if not len(request): 
            client_conn.close()
            return
        
        port, hostname, http_method, url = get_fields(request)
        # get origin
        if request.find(DOC_IDENTIFIER) != -1 and request.find(DOC_IDENTIFIER) < request.find(CLRF + CLRF):
            referer = remove_end_slash(url)
        else:
            referer = remove_end_slash(get_referer(request))
        
        if referer not in referers:
            referers[referer] = 0 # init 0 bytes
            
        
        print(http_method.decode(),'\t',url.decode(), '\t', f'referer={referer.decode()}')
            
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
                            payload_len += len(header[header_end_pos+8:])
                            client_conn.sendall(header)
                            in_body = False
                        else:
                            content = s.recv(4096)
                            size = len(content)
                            if size:
                                payload_len += size
                                client_conn.sendall(content)
                        s.settimeout(None)
                    except socket.timeout:
                        break
                
            except socket.error as e:
                print(e)
                client_conn.sendall(b"HTTP/1.0 400 Bad Request" + CLRF)
            
    # client_conn.close()
    # sys.exit(0)
            

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
        print('ERROR: invalid url')
        sys.exit(1)
    else:
        port = int(truncated_url[port_colon_pos+1:end_pos])
        hostname = truncated_url[:port_colon_pos]

    return port, hostname, http_method, url
        

if __name__ == '__main__':
   main()
   
   


""" this won't work (long time to load first image)
d = s.recv(2048)
if len(d):
    client_conn.sendall(d)
else:
    break
"""