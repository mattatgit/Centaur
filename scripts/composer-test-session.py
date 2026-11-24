"""Coordinate one disposable Framework/UTM run. Only the invite and test results cross this endpoint."""
import argparse
import base64
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import ipaddress
import json
from pathlib import Path
import re
import secrets
import ssl
import subprocess
import tempfile
import time
from uuid import UUID


def run(address, revision, output):
    if not ipaddress.ip_address(address).is_private or not re.fullmatch('[a-f0-9]{7}', revision):
        raise ValueError('Use a private IPv4 address and the seven-character build revision.')
    output.mkdir(mode=0o700,parents=True,exist_ok=False)
    token=secrets.token_urlsafe(30)
    machines={'host':'aarch64','guest':'x86_64'}
    joined=set()
    checked={}
    images=set()
    invitation=None

    def matched():
        return set(checked)==set(machines) and checked['host']==checked['guest']

    class Exchange(BaseHTTPRequestHandler):
        def log_message(self,*args): pass  # URLs contain the one-use session identifier.

        def answer(self,status,data=None):
            body=json.dumps(data or {}).encode()
            self.send_response(status)
            self.send_header('Content-Length',str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def route(self):
            parts=self.path.strip('/').split('/')
            if len(parts)==3 and secrets.compare_digest(parts[0],token) and parts[1] in machines:
                return parts[1],parts[2]
            return None,None

        def do_GET(self):
            role,item=self.route()
            if role and item=='ready' and joined==set(machines): self.answer(200,{'ready':True})
            elif role=='guest' and item=='invite' and invitation: self.answer(200,{'invitation':invitation})
            elif role and item=='complete' and matched() and images==set(machines): self.answer(200,{'complete':True})
            else: self.answer(404)

        def do_POST(self):
            nonlocal invitation
            role,item=self.route()
            if role is None:
                self.answer(404); return
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=(8*1024*1024 if item=='result' else 8192):
                    self.answer(413); return
                body=json.loads(self.rfile.read(size))
                if item=='hello' and body=={'revision':revision,'system':machines[role]}:
                    if role in joined:
                        self.answer(409); return
                    joined.add(role)
                elif role not in joined:
                    self.answer(403); return
                elif item=='invite' and role=='host' and re.fullmatch(r'centaur2:[\w-]{1,4086}={0,2}',body['invitation']):
                    if invitation and invitation!=body['invitation']:
                        self.answer(409); return
                    invitation=body['invitation']
                elif item in ('verified','result') and body['revision']==revision and body['system']==machines[role]:
                    messages=body['messages']
                    if set(messages)!=set(machines): raise ValueError()
                    for sender,row in messages.items():
                        UUID(row['id'])
                        if (set(row)!={'id','author','sha256'} or row['author']!='Composer '+sender or
                                not re.fullmatch('[a-f0-9]{64}',row['sha256'])): raise ValueError()
                    if item=='verified':
                        checked[role]=messages
                        (output/(role+'.json')).write_text(json.dumps(body,indent=2))
                    else:
                        if checked.get(role)!=messages: raise ValueError()
                        png=base64.b64decode(body['screenshot'],validate=True)
                        if not png.startswith(b'\x89PNG\r\n\x1a\n'): raise ValueError()
                        (output/(role+'.png')).write_bytes(png)
                        images.add(role)
                elif item=='failure':
                    stage=str(body.get('step',''))
                    if not re.fullmatch('[a-z ]{1,64}',stage): raise ValueError()
                    print(role,'stopped while',stage,flush=True)
                else:
                    self.answer(400); return
                print(role,item,'received',flush=True)
                self.answer(200,{'ok':True})
            except (KeyError,TypeError,ValueError):
                print(role,item,'failed validation',flush=True)
                self.answer(400)

    with tempfile.TemporaryDirectory(prefix='centaur-test-tls-') as tls:
        cert=Path(tls)/'certificate.pem'; key=Path(tls)/'key.pem'
        subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1',
                        '-subj','/CN=Centaur disposable test','-keyout',str(key),'-out',str(cert)],
                       stderr=subprocess.DEVNULL,check=True)
        fingerprint=hashlib.sha256(ssl.PEM_cert_to_DER_cert(cert.read_text())).hexdigest()
        ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); ctx.load_cert_chain(cert,key)
        class Server(HTTPServer):
            def server_bind(self):
                # No hostname lookup is necessary for a local, pinned IP endpoint.
                self.socket.bind(self.server_address)
                self.server_address=self.socket.getsockname()
                self.server_name,self.server_port=self.server_address
            def get_request(self):
                connection,remote=self.socket.accept()
                connection.settimeout(8)
                try: return ctx.wrap_socket(connection,server_side=True),remote
                except OSError:
                    connection.close(); raise
        with Server((address,0),Exchange) as server:
            server.timeout=1
            print(f'https://{address}:{server.server_port}/{token}#{fingerprint}',flush=True)
            end=time.monotonic()+3600
            while time.monotonic()<end:
                server.handle_request()
                if images==set(machines):
                    if not matched(): raise ValueError('The machines returned different message or image records.')
                    end=min(end,time.monotonic()+12)
        if not matched() or images!=set(machines):
            raise SystemExit('The session ended before both machines returned verified images and screenshots.')
        print('Both machines verified the same messages and image files.',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('address'); parser.add_argument('revision'); parser.add_argument('output',type=Path)
    args=parser.parse_args()
    run(args.address,args.revision,args.output)
