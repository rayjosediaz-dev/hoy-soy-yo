import os, re, secrets, sqlite3, hashlib, hmac, json, urllib.request
from datetime import datetime, timezone, timedelta
from contextlib import contextmanager
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

DB=os.getenv('DB_PATH','/data/panther.db')
BOT=os.getenv('TELEGRAM_BOT_TOKEN','')
ADMIN=int(os.getenv('TELEGRAM_ADMIN_ID','0'))
WEBHOOK_SECRET=os.getenv('TELEGRAM_WEBHOOK_SECRET','')
app=FastAPI(title='Panther iOS API')
@contextmanager
def db():
    os.makedirs(os.path.dirname(os.path.abspath(DB)),exist_ok=True)
    conn=sqlite3.connect(DB,timeout=20)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('CREATE TABLE IF NOT EXISTS licenses (key_hash TEXT PRIMARY KEY, expires TEXT NOT NULL, device_hash TEXT)')
    conn.execute('CREATE TABLE IF NOT EXISTS patches (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, url TEXT NOT NULL, created TEXT NOT NULL)')
    try: yield conn; conn.commit()
    finally: conn.close()
def kh(k): return hashlib.sha256(k.encode()).hexdigest()
def now(): return datetime.now(timezone.utc)
def send(chat, msg):
    if not BOT: return
    data=json.dumps({'chat_id':chat,'text':msg}).encode()
    req=urllib.request.Request(f'https://api.telegram.org/bot{BOT}/sendMessage',data=data,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=10): pass
class Activation(BaseModel):
    key: str
    device_id: str
@app.get('/health')
def health(): return {'ok':True}
@app.post('/v1/activate')
def activate(a:Activation):
    if not re.fullmatch(r'panther-\d{8}',a.key): raise HTTPException(401,'Invalid key')
    if not (16 <= len(a.device_id) <= 256): raise HTTPException(400,'Invalid device identifier')
    device=kh(a.device_id)
    with db() as c:
        row=c.execute('SELECT expires,device_hash FROM licenses WHERE key_hash=?',(kh(a.key),)).fetchone()
        if not row or datetime.fromisoformat(row[0])<=now(): raise HTTPException(401,'Expired or unknown key')
        if row[1] and not hmac.compare_digest(row[1],device): raise HTTPException(403,'Key already linked to another device')
        if not row[1]:
            c.execute('UPDATE licenses SET device_hash=? WHERE key_hash=? AND device_hash IS NULL',(device,kh(a.key)))
            row=c.execute('SELECT expires,device_hash FROM licenses WHERE key_hash=?',(kh(a.key),)).fetchone()
            if row[1]!=device: raise HTTPException(403,'Key already linked to another device')
        return {'valid':True,'role':'patches','expires_at':row[0]}
@app.post('/v1/patches')
def patches(a:Activation):
    activate(a)
    with db() as c:
        return {'patches':[{'id':i,'name':n,'url':u} for i,n,u in c.execute('SELECT id,name,url FROM patches ORDER BY id DESC').fetchall()]}
@app.post('/telegram/webhook')
async def telegram(request:Request):
    if not WEBHOOK_SECRET or not hmac.compare_digest(request.headers.get('X-Telegram-Bot-Api-Secret-Token',''),WEBHOOK_SECRET):
        raise HTTPException(403,'Forbidden')
    update=await request.json()
    msg=update.get('message') or {}
    user=msg.get('from') or {}
    if int(user.get('id',0))!=ADMIN: return {'ok':True}
    chat=(msg.get('chat') or {}).get('id')
    command=(msg.get('text') or '').strip().split()
    if not chat or not command: return {'ok':True}
    cmd=command[0].split('@')[0]
    response='Comandos: /generar 1-100, /keys, /revocar KEY, /patch NAME URL, /patches, /quitar ID'
    with db() as c:
        if cmd=='/generar' and len(command)==2:
            try: days=int(command[1])
            except ValueError: days=0
            if 1<=days<=100:
                for _ in range(30):
                    key='panther-'+str(secrets.randbelow(100000000)).zfill(8)
                    if not c.execute('SELECT 1 FROM licenses WHERE key_hash=?',(kh(key),)).fetchone(): break
                expiry=(now()+timedelta(days=days)).isoformat()
                c.execute('INSERT INTO licenses VALUES (?,?,NULL)',(kh(key),expiry))
                response=f'Key: {key}\nVence: {expiry}\nDispositivo: 1'
            else: response='Duración permitida: 1 a 100 días.'
        elif cmd=='/keys':
            rows=c.execute('SELECT expires,device_hash FROM licenses ORDER BY expires DESC LIMIT 20').fetchall()
            response='Últimas licencias (keys ocultas):\n'+'\n'.join(f'{e[:10]} | {"activada" if d else "sin activar"}' for e,d in rows) if rows else 'Sin licencias.'
        elif cmd=='/revocar' and len(command)==2:
            c.execute('DELETE FROM licenses WHERE key_hash=?',(kh(command[1]),))
            response='Key revocada si existía.'
        elif cmd=='/patch' and len(command)>=3:
            name=' '.join(command[1:-1]); url=command[-1]
            if url.startswith('https://') and len(name)<=100 and len(url)<=2048:
                c.execute('INSERT INTO patches(name,url,created) VALUES (?,?,?)',(name,url,now().isoformat()))
                response='Patch agregado al catálogo.'
            else: response='Uso: /patch Nombre https://example.com/archivo'
        elif cmd=='/patches':
            rows=c.execute('SELECT id,name FROM patches ORDER BY id DESC LIMIT 30').fetchall()
            response='\n'.join(f'{i}: {n}' for i,n in rows) or 'No hay patches.'
        elif cmd=='/quitar' and len(command)==2 and command[1].isdigit():
            c.execute('DELETE FROM patches WHERE id=?',(int(command[1]),))
            response='Patch quitado si existía.'
    send(chat,response)
    return {'ok':True}
