import os, time, json, re, datetime as dt
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError
from PIL import Image, ImageDraw, ImageFont, ImageOps

PRINTER_NAME = "EPSON TM-T88VII Receipt"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "print_bridge_config.json")
LOGO_FILE = os.path.join(BASE_DIR, "fresmart_logo.png")
ARTICLE_BADGE_FILE = os.path.join(BASE_DIR, "article_badge_logo.png")
POLL_SECONDS = 3
WIDTH, HEIGHT = 512, 244


def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f: cfg=json.load(f)
    portal=str(cfg.get("portal_url","")).strip().rstrip("/")
    key=str(cfg.get("bridge_key","")).strip()
    store_id=str(cfg.get("store_id","")).strip()
    if not portal.startswith("https://") or not key: raise RuntimeError("Invalid print_bridge_config.json")
    return portal,key,store_id


def api_json(method,url,key,payload=None,store_id=""):
    data=None if payload is None else json.dumps(payload).encode("utf-8")
    req=urlrequest.Request(url,data=data,method=method)
    req.add_header("X-Print-Bridge-Key",key); req.add_header("X-Store-ID",store_id); req.add_header("Content-Type","application/json")
    with urlrequest.urlopen(req,timeout=20) as resp: return json.loads(resp.read().decode("utf-8"))


def font(size,bold=False):
    paths=[r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",r"C:\Windows\Fonts\calibrib.ttf" if bold else r"C:\Windows\Fonts\calibri.ttf"]
    for path in paths:
        if os.path.exists(path): return ImageFont.truetype(path,size)
    return ImageFont.load_default()


def fit_font(draw,text,max_width,start,minimum,bold=True):
    for size in range(start,minimum-1,-1):
        f=font(size,bold)
        if draw.textbbox((0,0),text,font=f)[2] <= max_width: return f
    return font(minimum,bold)


def wrap_product_name(draw, name, max_width=268, max_lines=3):
    """Return every part of the product name, wrapped and fitted to the label."""
    text = " ".join(str(name or "ARTICLE").strip().upper().split()) or "ARTICLE"

    # Start large and reduce only when the complete name does not fit.
    for size in range(27, 8, -1):
        name_font = font(size, True)
        lines = []
        current = ""

        for word in text.split(" "):
            candidate = (current + " " + word).strip()
            if draw.textbbox((0, 0), candidate, font=name_font)[2] <= max_width:
                current = candidate
                continue

            if current:
                lines.append(current)
                current = ""

            # Split an unusually long article code/word instead of clipping it.
            chunk = ""
            for char in word:
                test_chunk = chunk + char
                if chunk and draw.textbbox((0, 0), test_chunk, font=name_font)[2] > max_width:
                    lines.append(chunk)
                    chunk = char
                else:
                    chunk = test_chunk
            current = chunk

        if current:
            lines.append(current)

        if len(lines) <= max_lines:
            return lines, name_font

    # Extreme fallback: shrink further so the complete name still fits in exactly 3 lines.
    for size in range(8, 5, -1):
        name_font = font(size, True)
        total_width = draw.textbbox((0, 0), text, font=name_font)[2]
        if total_width <= max_width * max_lines:
            target = max_width
            lines, current = [], ""
            for char in text:
                candidate = current + char
                if current and draw.textbbox((0, 0), candidate, font=name_font)[2] > target:
                    lines.append(current.rstrip())
                    current = char.lstrip()
                else:
                    current = candidate
            if current:
                lines.append(current.rstrip())
            if len(lines) <= max_lines:
                return lines, name_font

    # Safety fallback for exceptionally long input; preserve all text in three balanced lines.
    name_font = font(6, True)
    chars_per_line = max(1, (len(text) + max_lines - 1) // max_lines)
    lines = [text[i:i + chars_per_line] for i in range(0, len(text), chars_per_line)]
    return lines[:max_lines], name_font


def price_and_unit(job):
    raw=str(job.get("price","")).strip().upper().replace("AOA","").replace("KZ","").strip()
    unit=str(job.get("unit","UN")).strip().upper() or "UN"
    m=re.match(r"^(.*?)\s*/\s*([A-Z]+)\s*$",raw)
    if m: raw,unit=m.group(1).strip(),m.group(2).strip()
    unit={"PC":"UN","PC/KGM":"UN","KG":"KGM"}.get(unit,unit)
    try:
        n=float(raw.replace(" ","").replace(",",""))
        price=f"{int(n):,}" if n.is_integer() else f"{n:,.2f}"
    except Exception: price=raw
    return price,unit


def load_logo():
    logo=Image.open(LOGO_FILE).convert("L")
    # Trim white margins from uploaded logo and make a crisp 1-bit thermal image.
    inv=ImageOps.invert(logo)
    bbox=inv.getbbox()
    if bbox: logo=logo.crop(bbox)
    logo.thumbnail((210,52),Image.Resampling.LANCZOS)
    canvas=Image.new("L",(210,52),255)
    canvas.paste(logo,((210-logo.width)//2,(52-logo.height)//2))
    return canvas.point(lambda p: 0 if p<180 else 255,"1")


def load_article_badge():
    badge=Image.open(ARTICLE_BADGE_FILE).convert("L")
    badge=badge.point(lambda p: 0 if p < 190 else 255, mode="1")
    badge.thumbnail((70,52),Image.Resampling.LANCZOS)
    return badge


def draw_store_icon(img,x,y):
    badge=load_article_badge()
    img.paste(badge,(x,y))


def make_ticket(job):
    img=Image.new("1",(WIDTH,HEIGHT),1); d=ImageDraw.Draw(img)
    # Border is only 1 dot from image edges, eliminating internal top/bottom margins.
    d.rectangle((1,1,WIDTH-2,HEIGHT-2),outline=0,width=2)
    name_lines, name_font = wrap_product_name(d, job.get("item_name", "ARTICLE"))
    line_box = d.textbbox((0, 0), "Ag", font=name_font)
    line_height = max(13, line_box[3] - line_box[1] + 3)
    for i, line in enumerate(name_lines):
        d.text((12, 10 + i * line_height), line, font=name_font, fill=0)
    brand_logo=load_logo()
    brand_logo.thumbnail((202,55),Image.Resampling.LANCZOS)
    img.paste(brand_logo,(292,12))
    d.text((448,65),"KZ",font=font(22,True),fill=0)
    price,unit=price_and_unit(job)
    amount_fonts=[r"C:\Windows\Fonts\ariblk.ttf",r"C:\Windows\Fonts\arialbd.ttf"]
    pf=None
    for amount_path in amount_fonts:
        if os.path.exists(amount_path):
            for amount_size in range(66,43,-1):
                candidate=ImageFont.truetype(amount_path,amount_size)
                if d.textbbox((0,0),price,font=candidate)[2] <= 265:
                    pf=candidate; break
        if pf: break
    if pf is None: pf=fit_font(d,price,265,66,44,True)
    pw=d.textbbox((0,0),price,font=pf)[2]
    # Draw twice with one-dot offset for stronger thermal boldness.
    amount_x=494-pw
    d.text((amount_x,78),price,font=pf,fill=0)
    d.text((amount_x+1,78),price,font=pf,fill=0)
    d.text((amount_x,79),price,font=pf,fill=0)
    unit_text="PREÇO POR UN"; uf=fit_font(d,unit_text,245,21,17,True); uw=d.textbbox((0,0),unit_text,font=uf)[2]
    d.text((494-uw,174),unit_text,font=uf,fill=0)
    iva="IVA INCLUIDO"; ivaf=font(20,True); ivaw=d.textbbox((0,0),iva,font=ivaf)[2]
    d.text((494-ivaw,208),iva,font=ivaf,fill=0)
    draw_store_icon(img,14,137)
    d.text((14,207),str(job.get("article_code","")),font=font(20,True),fill=0)
    date_text=dt.datetime.now().strftime("%m/%d/%y")
    date_font=font(20,True)
    date_width=d.textbbox((0,0),date_text,font=date_font)[2]
    d.text(((WIDTH-date_width)//2,207),date_text,font=date_font,fill=0)
    return img


def raster_bytes(img):
    """Create one ticket raster without initialization or paper-cut commands."""
    w,h=img.size; width_bytes=(w+7)//8; out=bytearray(); pix=img.load()
    for y in range(h):
        for xb in range(width_bytes):
            value=0
            for bit in range(8):
                x=xb*8+bit
                if x<w and pix[x,y]==0: value |= 1 << (7-bit)
            out.append(value)
    return b"\x1dv0\x00"+bytes([width_bytes&255,(width_bytes>>8)&255,h&255,(h>>8)&255])+bytes(out)


def raw_print(ticket_data,copies=1):
    """Print all requested copies continuously and cut the paper only once."""
    import win32print
    copy_count=max(1,min(int(copies or 1),10))

    # One copy keeps the existing ticket size. For multiple copies, add a
    # small 16-dot paper-feed gap only between tickets, then cut once at the end.
    ticket_gap = b"\x1b\x4a\x10"
    combined_tickets = ticket_gap.join([ticket_data] * copy_count)
    print_data = b"\x1b@" + combined_tickets + b"\x1d\x56\x42\x00"

    h=win32print.OpenPrinter(PRINTER_NAME)
    try:
        win32print.StartDocPrinter(h,1,("Fresmart Price Ticket",None,"RAW"))
        try:
            win32print.StartPagePrinter(h)
            win32print.WritePrinter(h,print_data)
            win32print.EndPagePrinter(h)
        finally:
            win32print.EndDocPrinter(h)
    finally:
        win32print.ClosePrinter(h)


def main():
    portal,key,store_id=load_config(); print("Fresmart Logo Tight-Margin Bridge",portal)
    while True:
        try:
            result=api_json("GET",portal+"/api/print-jobs/next",key,store_id=store_id); job=result.get("job")
            if job:
                try:
                    raw_print(raster_bytes(make_ticket(job)),job.get("copies",1))
                    api_json("POST",portal+f"/api/print-jobs/{job['id']}/complete",key,{"success":True},store_id); print("Printed",job["id"])
                except Exception as exc:
                    api_json("POST",portal+f"/api/print-jobs/{job['id']}/complete",key,{"success":False,"error":str(exc)},store_id); print("Print error",exc)
        except (HTTPError,URLError,TimeoutError,OSError) as exc: print("Portal retry",exc)
        except Exception as exc: print("Bridge error",exc)
        time.sleep(POLL_SECONDS)

if __name__=="__main__": main()
