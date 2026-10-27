import os,sqlite3,hashlib,secrets,shutil,threading,io,zipfile,json,urllib.parse
from datetime import datetime
from functools import wraps
from flask import Flask,request,jsonify,render_template_string,session,redirect,send_file,Response
app=Flask(__name__);app.secret_key=os.getenv('SECRET_KEY','change-me');BASE=os.path.dirname(__file__);ROOT='/tmp' if os.getenv('VERCEL') else BASE;DB=os.path.join(ROOT,'store_prices.db');LOCK=threading.RLock()
def blob_ready():return bool(os.getenv('VERCEL') and (os.getenv('BLOB_STORE_ID') or os.getenv('BLOB_READ_WRITE_TOKEN')))
def pull():
 if not blob_ready():return
 try:
  from vercel.blob import sync as b;x=b.get_blob('gamek-data/store_prices.db',access='private');d=x.body if hasattr(x,'body') else x;d=d.read() if hasattr(d,'read') else d
  if d:open(DB+'.new','wb').write(d);os.replace(DB+'.new',DB)
 except:pass
def push():
 if not blob_ready():return
 try:
  from vercel.blob import sync as b;b.put_blob('gamek-data/store_prices.db',open(DB,'rb').read(),access='private',allow_overwrite=True,content_type='application/x-sqlite3',cache_control_max_age=0)
 except:pass
if not os.path.exists(DB):pull();shutil.copy2(os.path.join(BASE,'seed_store_prices.db'),DB) if not os.path.exists(DB) else None
def hp(v,salt=b'gamek-v3'):return hashlib.pbkdf2_hmac('sha256',v.encode(),salt,260000).hex()
def valid_password(saved,password):
 return saved in (hp(password,b'gamek-v3'),hp(password,b'gamek-portal-v2'),hp(password,b'gamek-portal-v1'))
def auth(f):
 @wraps(f)
 def w(*a,**k):return f(*a,**k) if session.get('user_id') else redirect('/login')
 return w
def dev(f):
 @wraps(f)
 def w(*a,**k):return f(*a,**k) if session.get('role')=='developer' else ('Forbidden',403)
 return w
CSS='''<style>*{box-sizing:border-box}body{margin:0;font-family:Inter,Segoe UI,Arial;background:#f6f8fb;color:#14213d}.top{background:#0b2545;color:#fff;padding:14px 5%;display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}.brand{font-size:20px;font-weight:800}.sub{font-size:12px;color:#b9d6f2}.nav{display:flex;gap:8px;flex-wrap:wrap}.btn,button{border:0;border-radius:10px;padding:10px 14px;font-weight:700;cursor:pointer;text-decoration:none;display:inline-block;background:#0f6fff;color:#fff}.btn.alt{background:#e8eef7;color:#123}.btn.red{background:#ef4444}.wrap{max-width:1180px;margin:24px auto;padding:0 18px}.hero{background:linear-gradient(135deg,#fff,#eef6ff);padding:24px;border-radius:18px;border:1px solid #dbe7f5;display:flex;justify-content:space-between;gap:20px;align-items:center}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-top:18px}.card{background:#fff;border:1px solid #e2e8f0;border-radius:16px;padding:18px;box-shadow:0 4px 16px #0b25450c}.card h3{margin:0 0 12px}.kpi{font-size:28px;font-weight:800;color:#0f6fff}.full{grid-column:1/-1}input,select{width:100%;padding:11px;border:1px solid #cad5e3;border-radius:9px;margin:6px 0 10px;background:#fff}.row{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.item{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:12px 0;border-top:1px solid #edf1f7}.pill{background:#e8f1ff;color:#0757c7;padding:5px 9px;border-radius:20px;font-size:12px}.status{padding:10px;border-radius:10px;background:#e8fff5;color:#087a55;margin-bottom:12px}.login{min-height:100vh;display:grid;place-items:center;background:linear-gradient(135deg,#081f37,#0f6fff)}.login .card{width:min(410px,90vw);padding:28px}.prices{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}.result{padding:14px;border:1px solid #e2e8f0;border-radius:12px;margin-top:10px}@media(max-width:850px){.grid{grid-template-columns:1fr}.row,.prices{grid-template-columns:1fr 1fr}}@media(max-width:480px){.row,.prices{grid-template-columns:1fr}}</style>'''
LOGIN='''<!doctype html><meta name=viewport content="width=device-width,initial-scale=1">'''+CSS+'''<body class=login><form class=card method=post><h1>Store Price Portal</h1><p>Fast, secure multi-store workspace</p>{% if err %}<div class=status style="background:#fee2e2;color:#991b1b">{{err}}</div>{% endif %}<label>User ID</label><input name=user_id required autofocus><label>Password</label><input type=password name=password required><button style="width:100%">Sign in</button><p class=sub style="color:#64748b;text-align:center">Portal Developed By Sonu Kumar (NCSA0608)</p></form>'''
HOME='''<!doctype html><meta name=viewport content="width=device-width,initial-scale=1"><link rel=manifest href=/manifest.json>'''+CSS+'''<body><header class=top><div><div class=brand>Store Price Portal</div><div class=sub>Store {{store}} · {{user}}</div></div><nav class=nav>{% if role=='developer' %}<a class="btn alt" href=/developer>Developer Control</a>{% endif %}<button id=install hidden>Install App</button><a class="btn red" href=/logout>Logout</a></nav></header><main class=wrap><section class=hero><div><h1>Find and update prices quickly</h1><p>Search by article, EAN or product name. Results load only when searched, so the page opens fast.</p></div><div class=pill id=net>Online</div></section><section class="card" style="margin-top:18px"><h3>Product Search</h3><input id=q placeholder="Scan EAN or type article/name" autofocus><div id=results></div></section></main><script>let prompt;addEventListener('beforeinstallprompt',e=>{e.preventDefault();prompt=e;install.hidden=false});install.onclick=async()=>{if(prompt){await prompt.prompt();prompt=null;install.hidden=true}};function net(){document.querySelector('#net').textContent=navigator.onLine?'Online':'Offline cache'}addEventListener('online',net);addEventListener('offline',net);net();let t;q.oninput=()=>{clearTimeout(t);t=setTimeout(search,250)};async function search(){let v=q.value.trim();if(!v)return results.innerHTML='';try{let a=await fetch('/api/search?q='+encodeURIComponent(v));let d=await a.json();localStorage.setItem('last:'+v,JSON.stringify(d));draw(d)}catch(e){let d=JSON.parse(localStorage.getItem('last:'+v)||'{"items":[]}');draw(d)}}function draw(d){results.innerHTML=(d.items||[]).map(x=>`<div class=result><b>${x.name}</b><div class=sub style="color:#64748b">${x.barcode}</div><div class=prices>${['price_cx','price_emb','price_pc_kgm','price_bag'].map((k,i)=>`<label>${['CX','EMB','PC/KGM','BAG'][i]}<input data-code="${x.barcode}" data-k="${k}" value="${x[k]||''}"></label>`).join('')}</div><button onclick="save(this,'${x.barcode}')">Save Prices</button></div>`).join('')||'<p>No result</p>'}async function save(b,code){let box=b.parentElement,o={barcode:code};box.querySelectorAll('input').forEach(i=>o[i.dataset.k]=i.value);await fetch('/api/update',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(o)});b.textContent='Saved';setTimeout(()=>b.textContent='Save Prices',1500)}if('serviceWorker'in navigator)navigator.serviceWorker.register('/sw.js')</script>'''
DEV='''<!doctype html><meta name=viewport content="width=device-width,initial-scale=1">'''+CSS+'''<body><header class=top><div><div class=brand>Developer Control</div><div class=sub>Portal Developed By Sonu Kumar (NCSA0608)</div></div><nav class=nav><a class="btn alt" href=/>Price Portal</a><a class="btn red" href=/logout>Logout</a></nav></header><main class=wrap>{% if msg %}<div class=status>{{msg}}</div>{% endif %}<section class=hero><div><h1>Multi-store administration</h1><p>Create stores and users, reset passwords and download store-specific print bridges.</p></div><div><span class=pill>{{stores|length}} Stores</span> <span class=pill>{{users|length}} Users</span></div></section><div class=grid><section class=card><h3>Create Store</h3><form method=post action=/developer/store><input name=store_id placeholder="Store ID" required><input name=store_name placeholder="Store name" required><input name=whatsapp placeholder="WhatsApp with country code"><button>Create Store</button></form></section><section class=card><h3>Create User</h3><form method=post action=/developer/user><input name=user_id placeholder="User ID" required><input name=display_name placeholder="Employee name" required><input name=password placeholder="Temporary password" required><select name=store_id>{% for s in stores %}<option>{{s.store_id}}</option>{% endfor %}</select><button>Create User</button></form></section><section class=card><h3>Change My Login</h3><form method=post action=/developer/me><input name=new_user_id placeholder="New developer ID" required><input name=password placeholder="New password" required><button>Update Login</button></form></section><section class="card full"><h3>Stores & Bridges</h3>{% for s in stores %}<div class=item><div><b>{{s.store_id}} · {{s.store_name}}</b><div class=sub style="color:#64748b">{{s.whatsapp or 'No WhatsApp saved'}}</div></div><div><a class=btn href="/developer/bridge/{{s.store_id}}">Download Bridge</a><a class="btn alt" target=_blank href="{{s.wa}}">WhatsApp</a><form style="display:inline" method=post action="/developer/bridge-key/{{s.store_id}}"><button class="btn alt">Reset Bridge Key</button></form></div></div>{% endfor %}</section><section class="card full"><h3>Users & Password Reset</h3>{% for u in users %}<div class=item><div><b>{{u.user_id}}</b> · {{u.display_name}} <span class=pill>{{u.store_id}}</span></div><form method=post action="/developer/reset-user/{{u.user_id}}" style="display:flex;gap:8px"><input style="margin:0" name=password placeholder="New password" required><button>Change Password</button></form></div>{% endfor %}</section></div></main>'''
@app.route('/login',methods=['GET','POST'])
def login():
 err=''
 if request.method=='POST':
  u=request.form['user_id'].strip().upper();p=request.form['password']
  with sqlite3.connect(DB) as c:c.row_factory=sqlite3.Row;r=c.execute('select * from users where user_id=? and active=1',(u,)).fetchone()
  if r and valid_password(r['password_hash'],p):session.update(user_id=u,role=r['role'],store_id=r['store_id']);return redirect('/')
  err='Invalid User ID or Password'
 return render_template_string(LOGIN,err=err)
@app.get('/logout')
def logout():session.clear();return redirect('/login')
@app.get('/')
@auth
def home():return render_template_string(HOME,store=session['store_id'],user=session['user_id'],role=session['role'])
@app.get('/developer')
@auth
@dev
def developer():
 with sqlite3.connect(DB) as c:c.row_factory=sqlite3.Row;ss=[dict(x) for x in c.execute('select * from stores where active=1 order by store_id')];us=[dict(x) for x in c.execute('select user_id,display_name,role,store_id from users where active=1 order by store_id,user_id')]
 for s in ss:s['wa']='https://wa.me/'+''.join(x for x in s['whatsapp'] if x.isdigit())+'?text='+urllib.parse.quote('Download '+s['store_id']+' bridge: '+request.url_root.rstrip('/')+'/developer/bridge/'+s['store_id'])
 return render_template_string(DEV,stores=ss,users=us,msg=request.args.get('msg'))
@app.post('/developer/store')
@auth
@dev
def addstore():
 f=request.form;sid=f['store_id'].strip().upper()
 with sqlite3.connect(DB) as c:c.execute('insert into stores values(?,?,?,?,1,?)',(sid,f['store_name'],sid+'-'+secrets.token_urlsafe(24),f.get('whatsapp',''),datetime.now().isoformat()));c.commit()
 push();return redirect('/developer?msg=Store+created')
@app.post('/developer/user')
@auth
@dev
def adduser():
 f=request.form;now=datetime.now().isoformat();uid=f['user_id'].strip().upper();store=f['store_id'].strip().upper()
 with sqlite3.connect(DB) as c:
  if not c.execute('select 1 from stores where store_id=? and active=1',(store,)).fetchone():return redirect('/developer?msg=Store+not+found')
  c.execute('insert into users values(?,?,?,?,?,1,?,?)',(uid,hp(f['password']),f['display_name'].strip(),'employee',store,now,now));c.commit()
 push();return redirect('/developer?msg=User+created')
@app.post('/developer/reset-user/<uid>')
@auth
@dev
def resetuser(uid):
 with sqlite3.connect(DB) as c:c.execute('update users set password_hash=?,updated_at=? where user_id=?',(hp(request.form['password']),datetime.now().isoformat(),uid));c.commit()
 push();return redirect('/developer?msg=Password+changed')
@app.post('/developer/me')
@auth
@dev
def me():
 old=session['user_id'];new=request.form['new_user_id'].strip().upper()
 with sqlite3.connect(DB) as c:c.execute('update users set user_id=?,password_hash=?,updated_at=? where user_id=?',(new,hp(request.form['password']),datetime.now().isoformat(),old));c.commit()
 session['user_id']=new;push();return redirect('/developer?msg=Developer+login+updated')
@app.post('/developer/bridge-key/<sid>')
@auth
@dev
def bridgekey(sid):
 with sqlite3.connect(DB) as c:c.execute('update stores set bridge_key=? where store_id=?',(sid+'-'+secrets.token_urlsafe(24),sid));c.commit()
 push();return redirect('/developer?msg=Bridge+key+reset')
@app.get('/developer/bridge/<sid>')
@auth
@dev
def bridge(sid):
 with sqlite3.connect(DB) as c:c.row_factory=sqlite3.Row;s=c.execute('select * from stores where store_id=?',(sid,)).fetchone()
 m=io.BytesIO();cfg={'portal_url':request.url_root.rstrip('/'),'store_id':sid,'bridge_key':s['bridge_key'],'printer_name':'EPSON TM-T88VII Receipt','poll_seconds':3}
 with zipfile.ZipFile(m,'w',zipfile.ZIP_DEFLATED) as z:z.write(BASE+'/bridge_template.py','fresmart_render_print_bridge.py');z.write(BASE+'/bridge_requirements.txt','print_bridge_requirements.txt');z.write(BASE+'/bridge_installer.bat','INSTALL_PRINT_BRIDGE.bat');z.writestr('print_bridge_config.json',json.dumps(cfg,indent=2))
 m.seek(0);return send_file(m,as_attachment=True,download_name='Fresmart_Bridge_'+sid+'.zip')
@app.get('/api/search')
@auth
def search():
 q=request.args.get('q','').strip();store=session['store_id']
 with sqlite3.connect(DB) as c:c.row_factory=sqlite3.Row;rs=c.execute("""select p.barcode,p.name,coalesce(s.price_cx,'') price_cx,coalesce(s.price_emb,'') price_emb,coalesce(s.price_pc_kgm,'') price_pc_kgm,coalesce(s.price_bag,'') price_bag from products p left join store_prices s on s.barcode=p.barcode and s.store_id=? where p.barcode=? or p.barcode in(select article_code from ean_aliases where ean_code=?) or p.name like ? limit 30""",(store,q,q,'%'+q+'%')).fetchall()
 return jsonify(items=[dict(x) for x in rs])
@app.post('/api/update')
@auth
def update():
 d=request.json;code=d['barcode'];now=datetime.now().isoformat()
 with sqlite3.connect(DB) as c:c.execute("""insert into store_prices values(?,?,?,?,?,?,?,?) on conflict(store_id,barcode) do update set price_cx=excluded.price_cx,price_emb=excluded.price_emb,price_pc_kgm=excluded.price_pc_kgm,price_bag=excluded.price_bag,updated_at=excluded.updated_at,updated_by=excluded.updated_by""",(session['store_id'],code,d.get('price_cx',''),d.get('price_emb',''),d.get('price_pc_kgm',''),d.get('price_bag',''),now,session['user_id']));c.commit()
 push();return jsonify(success=True)
@app.get('/manifest.json')
def manifest():return jsonify(name='Store Price Portal',short_name='Price Portal',start_url='/',display='standalone',theme_color='#0b2545',background_color='#f6f8fb')
@app.get('/sw.js')
def sw():return Response("const C='gamek-v3';self.addEventListener('install',e=>e.waitUntil(caches.open(C).then(c=>c.addAll(['/','/login']))));self.addEventListener('fetch',e=>{if(e.request.method==='GET')e.respondWith(fetch(e.request).then(r=>{let x=r.clone();caches.open(C).then(c=>c.put(e.request,x));return r}).catch(()=>caches.match(e.request)))})",mimetype='application/javascript')
if __name__=='__main__':app.run(debug=True)
