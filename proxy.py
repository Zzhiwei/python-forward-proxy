import os,sys,time, socket, select
import _thread as thread



SERVER_NAME = 'localhost'
BACKLOG = 40
MAX_RECV_BYTES = 256000
CLRF = b'\r\n'
i = 0


def main():
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
        connection, client_address = helloSocket.accept()
        print('#####################accepted connection', i) 
        print(f'connecting to {connection}, {client_address}')
        thread.start_new_thread(proxy_thread, (connection, client_address))

    
def proxy_thread(client_conn: socket.socket, client_address):
    global i
    print('#####################starting thread:', i)
    j = i
    i += 1
    
    # client_conn.settimeout(7)
    request = client_conn.recv(MAX_RECV_BYTES)
    print(request)
    
    first_line = request.split(CLRF)[0]
    first_line_arr = first_line.split(b' ')
    request_type = first_line_arr[0]
    url =  first_line_arr[1]
    
    print(">>>>>>>>>>>>>>>>>>>>>>>",request_type,'\t',url)
    port, hostname = get_port_and_hostname(url)
        
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.connect((hostname, port))
            s.sendall(request)
            # response = b''
            
            while True:
                try:
                    s.settimeout(5)
                    client_conn.sendall(s.recv(4096))
                    s.settimeout(None)
                except socket.timeout:
                    break
                
            # client_conn.sendall(response)
            client_conn.close() 
            
        except socket.error as e:
            print(e, j)
            if client_conn:
                client_conn.sendall(b"HTTP/1.0 400 Bad Request" + CLRF)
                client_conn.close()
            sys.exit(1)
            


def get_port_and_hostname(url: str):
    # url -> http://localhost:3000/
    url_start = url.find(b'://')
    if (url_start == -1):
        truncated_url = url 
    else:
        truncated_url = url[url_start+3:]
    # truncated_url -> www.google.com:3000/
    
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

    return port, hostname
        

if __name__ == '__main__':
   main()