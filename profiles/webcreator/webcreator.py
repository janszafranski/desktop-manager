#!/usr/bin/env python3
# just a... WEBcreator
# A desktop website designer for Linux, built on Qt 6 (PySide6).
# It follows your desktop theme: colours, accent, fonts and icons all come
# from the system (KDE Plasma colour scheme, Breeze/your icon theme, etc).

import sys, os, re, json, copy, uuid, base64, hashlib, math, tempfile, collections, html as H
import subprocess, shutil

try:
    from PySide6.QtCore import (Qt, QRectF, QPointF, QSizeF, QTimer, QSettings, QUrl,
                                QByteArray, QBuffer, QIODevice, QSize, QLineF, QEvent,
                                Signal, QMimeData, QPoint)
    from PySide6.QtGui import (QAction, QActionGroup, QIcon, QPixmap, QImage, QPainter, QColor, QDrag,
                               QPen, QBrush, QFont, QFontMetrics, QPainterPath, QPalette, QTransform,
                               QTextDocument, QTextOption, QTextCursor, QTextCharFormat, QTextFormat,
                               QTextBlockFormat, QAbstractTextDocumentLayout, QKeySequence,
                               QDesktopServices, QPolygonF, QCursor, QLinearGradient)
    from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QGraphicsView, QGraphicsScene,
                                   QGraphicsItem, QGraphicsTextItem, QToolBar, QDockWidget,
                                   QLabel, QComboBox, QFontComboBox, QSpinBox, QDoubleSpinBox,
                                   QToolButton, QPushButton, QVBoxLayout, QHBoxLayout, QGridLayout,
                                   QFormLayout, QDialog, QDialogButtonBox, QLineEdit, QCheckBox,
                                   QRadioButton, QButtonGroup, QListWidget, QListWidgetItem,
                                   QTreeWidget, QTreeWidgetItem, QTreeWidgetItemIterator,
                                   QStackedWidget, QFileDialog, QTabWidget,
                                   QMessageBox, QColorDialog, QSlider, QPlainTextEdit,
                                   QTableWidget, QTableWidgetItem, QMenu, QFrame, QSizePolicy,
                                   QGroupBox, QAbstractItemView, QStyle, QInputDialog)
except ImportError:
    print("just a... WEBcreator needs PySide6 (use your distro package, not pip, so it follows your theme):\n"
          "  Arch/CachyOS:        sudo pacman -S --needed pyside6\n"
          "  Debian/Ubuntu/Mint:  sudo apt install python3-pyside6.qtwidgets python3-pyside6.qtwebenginewidgets\n"
          "  Fedora:              sudo dnf install python3-pyside6\n"
          "  openSUSE:            sudo zypper install python3-PySide6")
    sys.exit(1)

APP = "just a... WEBcreator"
ORG = "justawebcreator"
EXT = ".webc"
VERSION = "1.10-30"
# Bump when the default docks/toolbars change so a stale saved layout is discarded
# (restoreState ignores a state saved under a different version) and users see the new panels.
# v8: discard layouts that had collapsed the Site studio group (file-list + its toolbar) to zero.
LAYOUT_VERSION = 8


def open_external(target, is_file=False):
    """Open a URL or local file/folder in the user's default app.

    Qt's QDesktopServices.openUrl silently fails on some Wayland desktops
    (returns False, nothing happens), which left every link and 'open folder'
    button dead. xdg-open honours the user's defaults and works there, so we
    use it first and fall back to Qt only if it isn't available.

    A local .html page is a *preview of a website*, so it must open in a web
    BROWSER — not whatever happens to be registered for .html files (which can
    be an office suite or a browser the desktop can't keep open). We launch the
    default web browser directly for HTML; everything else uses xdg-open.
    """
    is_html = is_file and str(target).lower().endswith(('.html', '.htm'))
    try:
        if is_html:
            browser = None
            # Ask the desktop for its default browser, resolve its launcher.
            try:
                bid = subprocess.run(['xdg-settings', 'get', 'default-web-browser'],
                                     capture_output=True, text=True, timeout=5).stdout.strip()
            except Exception:
                bid = ''
            cmd = None
            if bid:
                for d in (os.path.expanduser('~/.local/share/applications'),
                          '/usr/share/applications', '/usr/local/share/applications'):
                    p = os.path.join(d, bid)
                    if os.path.exists(p):
                        for line in open(p, encoding='utf-8', errors='ignore'):
                            if line.startswith('Exec='):
                                exe = line[5:].split()[0]
                                if shutil.which(exe): cmd = exe
                                break
                        if cmd: break
            # Known-good fallbacks in preference order.
            if not cmd:
                for c in ('floorp', 'firefox', 'chromium', 'google-chrome-stable', 'brave'):
                    if shutil.which(c): cmd = c; break
            if cmd:
                subprocess.Popen([cmd, target],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 start_new_session=True)
                return True
        opener = shutil.which('xdg-open')
        if opener:
            subprocess.Popen([opener, target],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
            return True
    except Exception:
        pass
    try:
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        return QDesktopServices.openUrl(QUrl.fromLocalFile(target) if is_file else QUrl(target))
    except Exception:
        return False


def _sniff_mime(data):
    """Detect image type from magic bytes (providers don't always honour the format asked)."""
    if data[:8] == b'\x89PNG\r\n\x1a\n': return 'png'
    if data[:3] == b'\xff\xd8\xff': return 'jpeg'
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP': return 'webp'
    if data[:6] in (b'GIF87a', b'GIF89a'): return 'gif'
    return 'png'


def ai_generate_image(prompt, provider, settings):
    """Return (image_bytes, mime) for a text prompt.

    Providers:
      pollinations — FREE, no account, no key. Just needs internet.
      openai       — DALL·E; needs the user's OpenAI API key (settings 'aiOpenAIKey').
      stability    — Stable Diffusion; needs 'aiStabilityKey'.
    Default is pollinations so the feature works out of the box.
    """
    import urllib.request, urllib.parse, ssl, json as _json
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    provider = (provider or 'pollinations').lower()

    if provider == 'pollinations':
        # GET an image straight back. 1024px square, no logo.
        q = urllib.parse.quote(prompt)
        url = (f'https://image.pollinations.ai/prompt/{q}'
               f'?width=1024&height=1024&nologo=true&model=flux')
        req = urllib.request.Request(url, headers={'User-Agent': 'WEBcreator'})
        with urllib.request.urlopen(req, timeout=120, context=ctx) as r:
            data = r.read()
        return data, _sniff_mime(data)

    if provider == 'openai':
        key = settings.value('aiOpenAIKey', '')
        if not key: raise RuntimeError('No OpenAI API key. Add it in Help ▸ Settings.')
        body = _json.dumps({'model': 'gpt-image-1', 'prompt': prompt, 'size': '1024x1024', 'n': 1}).encode()
        req = urllib.request.Request('https://api.openai.com/v1/images/generations', data=body,
                                     headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=120, context=ctx) as r:
            out = _json.loads(r.read())
        import base64 as _b64
        d = out['data'][0]
        if d.get('b64_json'): return _b64.b64decode(d['b64_json']), 'png'
        img_url = d['url']
        with urllib.request.urlopen(img_url, timeout=120, context=ctx) as r2:
            return r2.read(), 'png'

    if provider == 'stability':
        key = settings.value('aiStabilityKey', '')
        if not key: raise RuntimeError('No Stability API key. Add it in Help ▸ Settings.')
        # Stability v2 core: multipart form. Build minimal multipart body.
        boundary = '----wcboundary'
        parts = []
        for name, val in (('prompt', prompt), ('output_format', 'png'), ('aspect_ratio', '1:1')):
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{val}\r\n')
        bodyb = (''.join(parts) + f'--{boundary}--\r\n').encode()
        req = urllib.request.Request('https://api.stability.ai/v2beta/stable-image/generate/core', data=bodyb,
                                     headers={'Authorization': 'Bearer ' + key, 'Accept': 'image/*',
                                              'Content-Type': f'multipart/form-data; boundary={boundary}'})
        with urllib.request.urlopen(req, timeout=120, context=ctx) as r:
            return r.read(), 'png'

    raise RuntimeError(f'Unknown AI provider: {provider}')


# Where updates come from: a public GitHub repository holding a copy of this
# file. UPDATE_PATH is where in that repository it sits — the top level if the
# app has a repository to itself, a subdirectory if it ships inside a bigger
# one. All three are overridable in the app (Help ▸ Update Settings…).
UPDATE_REPO = "janszafranski/just-a-collection-of-apps"
UPDATE_BRANCH = "main"     # that repository's default branch
UPDATE_PATH = "apps/webcreator/webcreator.py"

# ----------------------------------------------------------------------------
# Data model
# ----------------------------------------------------------------------------

def uid():
    return uuid.uuid4().hex[:8]

DEF = {
    'text':     dict(w=320, h=120, font='Noto Sans', size=16, color='#2b2b2b', html='<p>Type your text here. Frame text wraps inside the frame.</p>',
                     align='left', lh=1.5, pad=8, fill='', stroke='#333333', strokeW=0, radius=0, bold=False, italic=False, underline=False),
    'artistic': dict(w=300, h=54, font='Noto Sans', size=40, color='#1f2a30', html='<p>Artistic Text</p>', align='left', lh=1.15,
                     bold=True, italic=False, underline=False, fill='', stroke='#333333', strokeW=0, radius=0),
    'shape':    dict(w=200, h=140, shape='rect', fill='#9fc3d6', stroke='#2b3a42', strokeW=0, radius=0, dash='solid'),
    'line':     dict(w=240, h=2, stroke='#2b3a42', strokeW=2, flip=False, dash='solid'),
    'picture':  dict(w=320, h=220, src=None, fit='cover', radius=0, strokeW=0, stroke='#333333', fill=''),
    'nav':      dict(w=420, h=40, style='pills', orient='h', align='left', font='Noto Sans', size=15, bold=False, color='#1f2a30',
                     accent='#2a7d6b', accentInk='#ffffff', fill=''),
    'button':   dict(w=180, h=46, html='<p>Find out more</p>', font='Noto Sans', size=15, bold=True, italic=False, underline=False,
                     color='#ffffff', fill='#2a7d6b', radius=6, strokeW=0, stroke='#333333', align='center', lh=1.2),
    'table':    dict(w=480, h=160, font='Noto Sans', size=14, color='#2b2b2b', fill='#ffffff', stroke='#c9d1d6', head='#e9eff2',
                     cells=[['Heading', 'Heading', 'Heading'], ['Cell', 'Cell', 'Cell'], ['Cell', 'Cell', 'Cell']]),
    'html':     dict(w=300, h=120, code='<p style="font:14px sans-serif">Your HTML here</p>'),
    'gallery':  dict(w=600, h=300, images=[], interval=5, fade=0.5, fit='cover', radius=0, strokeW=0, stroke='#333333', fill=''),
    'share':    dict(w=480, h=40, nets=['facebook', 'x', 'linkedin', 'email'], style='colour', font='Arial', size=14, radius=6, gap=8),
    'form':     dict(w=360, h=300, font='Noto Sans', size=14, color='#2b2b2b', accent='#2a7d6b', fields=['Name', 'Email', 'Message'], submit='Send'),
}
SHARE_NETS = [  # id, label, button colour, share address ({u} = page address, {t} = page title)
    ('facebook', 'Facebook', '#1877f2', 'https://www.facebook.com/sharer/sharer.php?u={u}'),
    ('x', 'X (Twitter)', '#111111', 'https://twitter.com/intent/tweet?url={u}&text={t}'),
    ('linkedin', 'LinkedIn', '#0a66c2', 'https://www.linkedin.com/sharing/share-offsite/?url={u}'),
    ('whatsapp', 'WhatsApp', '#1f9e57', 'https://wa.me/?text={t}%20{u}'),
    ('bluesky', 'Bluesky', '#1185fe', 'https://bsky.app/intent/compose?text={t}%20{u}'),
    ('reddit', 'Reddit', '#e0461b', 'https://www.reddit.com/submit?url={u}&title={t}'),
    ('threads', 'Threads', '#000000', 'https://www.threads.net/intent/post?text={t}%20{u}'),
    ('email', 'Email', '#5a6872', 'mailto:?subject={t}&body={u}'),
]
NET = {n[0]: n for n in SHARE_NETS}

TYPE_NAMES = dict(text='Text frame', artistic='Artistic text', shape='QuickShape', line='Line', picture='Picture',
                  nav='Navigation bar', button='Button', table='Table', html='HTML fragment', form='Form', gallery='Photo gallery', share='Share buttons')

def mk(t, x, y, w=None, h=None, **p):
    o = dict(id=uid(), type=t, x=x, y=y, rot=0, opacity=1.0, hidden=False, locked=False, link=None)
    o.update(copy.deepcopy(DEF[t]))
    if w is not None: o['w'] = w
    if h is not None: o['h'] = h
    o.update(p)
    return o

def slug(title, existing):
    base = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-') or 'page'
    name, i = base + '.html', 2
    while name in existing:
        name, i = f'{base}-{i}.html', i + 1
    return name

def index_section(p):
    # Generic section label from a page's file stem: the part before the first '-',
    # humanised. Flat hyphenated names (news-2024, about) thus group sensibly; any
    # site's page names produce usable sections without hard-coding.
    stem = re.sub(r'\.html?$', '', (p.get('file') or '').lower())
    head = stem.split('-', 1)[0] if '-' in stem else ''
    if not head or head in ('index',): return 'Main Pages'
    return re.sub(r'[-_]+', ' ', head).strip().title() or 'Main Pages'

def build_index_html(site, target_page_id=None):
    # Returns (html, count) — a grouped, hyperlinked site index as <p> lines using
    # wcpage:<id> links so they resolve both in-editor and on publish.
    groups = collections.OrderedDict()
    n = 0
    for p in site['pages']:
        if p['id'] == target_page_id: continue
        t = (p.get('title') or '').strip().lower()
        if t in ('index', 'sitemap') or 'site map' in t: continue
        groups.setdefault(index_section(p), []).append(p)
        n += 1
    def gkey(name):  # Main Pages first, then alphabetical
        return (0 if name == 'Main Pages' else 1, name.lower())
    lines = []
    for sec in sorted(groups, key=gkey):
        lines.append('<p><span style="font-size:22px; font-weight:bold; color:#0089c9;">%s</span></p>' % esc(sec))
        for p in sorted(groups[sec], key=lambda q: (q.get('title') or '').lower()):
            lines.append('<p>&#8226; <a href="wcpage:%s"><span style="text-decoration:underline; color:#0089c9;">%s</span></a></p>'
                         % (p['id'], esc(p.get('title') or p.get('file') or 'Page')))
    return ''.join(lines), n

def base_site(name, **kw):
    m = dict(id=uid(), name='Master A', bg='#ffffff', objects=[])
    s = dict(name=name, width=960, height=1100, bg='#ffffff', palette=[], masters=[m], pages=[], assets={})
    s.update(kw)
    add_page(s, 'Home', file='index.html')
    return s

def add_page(s, title, level=0, file=None, index=None, master=None):
    p = dict(id=uid(), title=title, file=file or slug(title, {q['file'] for q in s['pages']}),
             master=master or s['masters'][0]['id'], nav=True, level=level, height=None, bg='', objects=[])
    if index is None: s['pages'].append(p)
    else: s['pages'].insert(index, p)
    return p

def add_asset(site, data_uri):
    key = hashlib.sha1(data_uri.encode()).hexdigest()[:12]
    site.setdefault('assets', {})[key] = data_uri
    return key

# Dragging a thumbnail OUT of the Assets panel onto the page carries just the asset key
# under this private MIME type; dragging a picture file IN from another app carries file
# URLs (handled via picture_uri). These extensions are what we accept from outside drops.
ASSET_MIME = 'application/x-webcreator-asset'
IMG_DROP_EXTS = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.bmp', '.tif', '.tiff')

# ----------------------------------------------------------------------------
# Procedural artwork for the design templates (original, generated here)
# ----------------------------------------------------------------------------

def make_art(kind, cols, w=720, h=480):
    img = QImage(w, h, QImage.Format_RGB32)
    p = QPainter(img); p.setRenderHint(QPainter.Antialiasing)
    c = [QColor(x) for x in cols]
    p.fillRect(0, 0, w, h, c[0]); p.setPen(Qt.NoPen)
    def wave(y0, amp, col):
        path = QPainterPath(); path.moveTo(0, y0)
        path.cubicTo(w * .3, y0 - amp, w * .6, y0 + amp, w, y0 - amp * .3)
        path.lineTo(w, h); path.lineTo(0, h); path.closeSubpath()
        p.setBrush(col); p.drawPath(path)
    if kind == 'waves':
        p.setBrush(c[3]); p.drawEllipse(QPointF(w * .76, h * .3), h * .15, h * .15)
        wave(h * .6, h * .16, c[2]); wave(h * .74, h * .12, c[1])
    elif kind == 'hills':
        p.setBrush(c[3]); p.drawEllipse(QPointF(w * .22, h * .3), h * .12, h * .12)
        for i, col in enumerate([c[2], c[1]]):
            path = QPainterPath(); y0 = h * (.58 + .14 * i); path.moveTo(0, h)
            path.lineTo(0, y0); path.quadTo(w * (.35 + .25 * i), y0 - h * .35, w, y0 + h * .05)
            path.lineTo(w, h); path.closeSubpath(); p.setBrush(col); p.drawPath(path)
    elif kind == 'blocks':
        p.setBrush(c[1]); p.drawRect(QRectF(w * .08, h * .18, w * .42, h * .64))
        p.setBrush(c[2]); p.drawRect(QRectF(w * .38, h * .38, w * .5, h * .44))
        p.setBrush(c[3]); p.drawEllipse(QPointF(w * .74, h * .26), h * .1, h * .1)
    elif kind == 'rings':
        for i, col in enumerate([c[1], c[2], c[3], c[0]]):
            r = h * (.42 - i * .1); p.setBrush(col); p.drawEllipse(QPointF(w * .5, h * .5), r, r)
    elif kind == 'grid':
        p.setPen(QPen(c[1], 3))
        for x in range(0, w, 60): p.drawLine(x, 0, x, h)
        for y in range(0, h, 60): p.drawLine(0, y, w, y)
        p.setPen(Qt.NoPen); p.setBrush(c[2]); p.drawEllipse(QPointF(w * .4, h * .55), h * .26, h * .2)
        p.setBrush(c[3]); p.drawEllipse(QPointF(w * .55, h * .45), 18, 18)
    elif kind == 'sun':
        p.setBrush(c[2]); p.drawEllipse(QPointF(w * .5, h * .62), h * .32, h * .32)
        p.setBrush(c[1]); p.drawRect(QRectF(0, h * .62, w, h * .38))
        p.setBrush(c[3]); p.drawRect(QRectF(0, h * .72, w, 6)); p.drawRect(QRectF(w * .2, h * .82, w * .6, 6))
    elif kind == 'stripes':
        for i in range(8):
            p.setBrush(c[1 + i % 3]); p.drawRect(QRectF(i * w / 8, h * (.2 + (i % 3) * .1), w / 8 - 10, h))
    p.end()
    ba = QByteArray(); buf = QBuffer(ba); buf.open(QIODevice.WriteOnly); img.save(buf, 'PNG')
    return 'data:image/png;base64,' + bytes(ba.toBase64()).decode()

# ----------------------------------------------------------------------------
# Design templates
# ----------------------------------------------------------------------------

SERIF, SANS = 'Noto Serif', 'Noto Sans'

def tpl_harbour():
    pal = ['#13324a', '#1f4e6e', '#e8dcc4', '#c2703d', '#f7f4ee', '#2b2b2b']
    s = base_site('Harbour & Co. Joinery', palette=pal)
    A = lambda k, cols: add_asset(s, make_art(k, cols))
    m = s['masters'][0]; m['bg'] = '#f7f4ee'
    home = s['pages'][0]
    about, serv, cont = add_page(s, 'About Us'), add_page(s, 'Services'), add_page(s, 'Contact')
    m['objects'] = [
        mk('shape', 0, 0, 960, 96, fill='#13324a'),
        mk('artistic', 40, 24, 320, 48, html='<p>Harbour &amp; Co.</p>', font=SERIF, size=34, color='#f7f4ee'),
        mk('nav', 430, 28, 490, 40, style='underline', align='right', color='#e8dcc4', accent='#c2703d', size=15),
        mk('shape', 0, 1020, 960, 80, fill='#13324a'),
        mk('text', 40, 1044, 880, 34, html='<p>© 2026 Harbour &amp; Co. Joinery · Unit 4, Quay Street · 01234 567890</p>', size=13, color='#e8dcc4', pad=0),
    ]
    home['objects'] = [
        mk('picture', 0, 96, 960, 380, src=A('waves', ['#1f4e6e', '#13324a', '#2c6a8f', '#e8dcc4'])),
        mk('artistic', 60, 230, 720, 74, html='<p>Joinery made to last</p>', font=SERIF, size=58, color='#ffffff'),
        mk('text', 60, 316, 560, 64, html='<p>Kitchens, staircases and restoration work, built by hand in our harbourside workshop.</p>', size=19, color='#f7f4ee', pad=0),
        mk('button', 60, 396, 200, 48, html='<p>See our services</p>', fill='#c2703d', link={'type': 'page', 'target': serv['id']}),
        mk('artistic', 60, 520, 400, 44, html='<p>What we do</p>', font=SERIF, size=30, color='#13324a'),
    ]
    cols = [('Fitted kitchens', 'Solid oak and painted tulipwood kitchens, designed around how you cook.', 'blocks'),
            ('Staircases', 'New staircases and careful repairs to old ones, from treads to handrails.', 'stripes'),
            ('Restoration', 'Sash windows, panelled doors and period details brought back to life.', 'sun')]
    for i, (t, d, k) in enumerate(cols):
        x = 60 + i * 300
        home['objects'] += [
            mk('picture', x, 580, 260, 170, src=A(k, ['#e8dcc4', '#1f4e6e', '#c2703d', '#13324a']), radius=4),
            mk('artistic', x, 766, 260, 30, html=f'<p>{t}</p>', font=SERIF, size=21, color='#13324a'),
            mk('text', x, 802, 260, 120, html=f'<p>{d}</p>', size=15, color='#2b2b2b', pad=0),
        ]
    about['objects'] = [
        mk('artistic', 60, 140, 400, 52, html='<p>About us</p>', font=SERIF, size=40, color='#13324a'),
        mk('text', 60, 212, 520, 380, size=16, color='#2b2b2b', pad=0, html=(
            '<p>We are a family workshop of five joiners on the harbour front. Everything we make is drawn, cut and finished in-house.</p>'
            '<p>We started out restoring sash windows for neighbours on the old quay. Twenty years later we build kitchens, staircases and furniture across the county, and we still restore windows.</p>'
            '<p>We use timber from managed forests and finish with oils and paints that are easy to repair.</p>')),
        mk('picture', 620, 212, 280, 360, src=A('rings', ['#e8dcc4', '#c2703d', '#1f4e6e', '#f7f4ee']), radius=4),
        mk('shape', 60, 640, 840, 150, fill='#e8dcc4', radius=4),
        mk('text', 96, 672, 768, 100, html='<p>“They rebuilt our staircase in a week and you would never know it wasn’t original.”</p>',
           font=SERIF, size=21, italic=True, color='#13324a', pad=0),
    ]
    serv['objects'] = [
        mk('artistic', 60, 140, 400, 52, html='<p>Services</p>', font=SERIF, size=40, color='#13324a'),
        mk('text', 60, 206, 700, 60, html='<p>Every job starts with a free visit and a written quote. Typical lead times and starting prices:</p>', size=16, pad=0),
        mk('table', 60, 280, 840, 230, size=15, head='#e8dcc4', stroke='#d3c7ad', cells=[
            ['Service', 'Typical lead time', 'From'], ['Fitted kitchens', '8–10 weeks', '£9,500'],
            ['Staircases', '6 weeks', '£4,200'], ['Sash window restoration', '2–3 weeks', '£650 per window'],
            ['Bespoke furniture', '4–6 weeks', '£1,200']]),
        mk('button', 60, 550, 200, 48, html='<p>Ask for a quote</p>', fill='#c2703d', link={'type': 'page', 'target': cont['id']}),
    ]
    cont['objects'] = [
        mk('artistic', 60, 140, 400, 52, html='<p>Contact</p>', font=SERIF, size=40, color='#13324a'),
        mk('text', 60, 212, 380, 200, size=16, pad=0, html=(
            '<p><b>Harbour &amp; Co. Joinery</b><br>Unit 4, Quay Street</p><p>Phone 01234 567890<br>Workshop open Monday to Friday, 8am to 5pm</p>')),
        mk('picture', 60, 420, 380, 260, src=A('grid', ['#e8dcc4', '#d3c7ad', '#1f4e6e', '#c2703d']), radius=4),
        mk('form', 520, 212, 380, 340, accent='#c2703d', fields=['Name', 'Email', 'Phone', 'Message'], submit='Send enquiry'),
    ]
    return s

def tpl_meadow():
    pal = ['#2f5d3a', '#6a9a4f', '#f1efe2', '#e3b23c', '#ffffff', '#26302a']
    s = base_site('Riverside Wellbeing Hub', palette=pal)
    A = lambda k, cols: add_asset(s, make_art(k, cols))
    m = s['masters'][0]; m['bg'] = '#f1efe2'
    home = s['pages'][0]
    groups, events, inv = add_page(s, 'Our Groups'), add_page(s, 'Events'), add_page(s, 'Get Involved')
    add_page(s, 'Volunteering', level=1)
    m['objects'] = [
        mk('artistic', 40, 28, 520, 46, html='<p>Riverside Wellbeing Hub</p>', font=SERIF, size=32, color='#2f5d3a'),
        mk('nav', 40, 92, 880, 42, style='pills', color='#26302a', accent='#2f5d3a', size=15, bold=True),
        mk('line', 40, 1010, 880, 2, stroke='#c9c5ad', strokeW=2),
        mk('text', 40, 1030, 880, 40, html='<p>Riverside Wellbeing Hub · Registered charity · The Old Boathouse, Mill Lane</p>', size=13, color='#4d5a50', pad=0),
    ]
    home['objects'] = [
        mk('picture', 40, 156, 880, 300, src=A('hills', ['#cfe0c3', '#6a9a4f', '#2f5d3a', '#e3b23c']), radius=16),
        mk('artistic', 40, 486, 520, 52, html='<p>Come as you are</p>', font=SERIF, size=40, color='#2f5d3a'),
        mk('text', 40, 548, 560, 140, size=17, color='#26302a', pad=0, html=(
            '<p>We run free, friendly groups for adults who want company, a change of scene or a bit of support. No referral needed: just turn up.</p>')),
        mk('button', 40, 680, 260, 50, html='<p>See this month’s events</p>', fill='#2f5d3a', radius=25, link={'type': 'page', 'target': events['id']}),
        mk('shape', 640, 486, 280, 230, fill='#ffffff', radius=16),
        mk('artistic', 664, 508, 240, 32, html='<p>Drop-in times</p>', font=SERIF, size=22, color='#2f5d3a'),
        mk('text', 664, 548, 240, 150, size=15, pad=0, html='<p>Tuesday 10am – 1pm<br>Thursday 1pm – 4pm<br>Saturday 10am – 12pm</p><p>Tea and biscuits always on.</p>'),
    ]
    gs = [('Gardening Club', 'Grow food and flowers in our riverside beds. Gloves and tools provided.'),
          ('Book Circle', 'One book a month, chosen together, talked about over coffee.'),
          ('Walking Group', 'An easy-paced hour along the river path, whatever the weather.'),
          ('Coffee & Chat', 'Our longest-running group: no plan, just good company.')]
    groups['objects'] = [mk('artistic', 40, 170, 500, 52, html='<p>Our groups</p>', font=SERIF, size=40, color='#2f5d3a')]
    for i, (t, d) in enumerate(gs):
        x, y = 40 + (i % 2) * 450, 250 + (i // 2) * 230
        groups['objects'] += [mk('shape', x, y, 430, 200, fill='#ffffff', radius=16),
                              mk('artistic', x + 24, y + 24, 380, 34, html=f'<p>{t}</p>', font=SERIF, size=24, color='#2f5d3a'),
                              mk('text', x + 24, y + 70, 380, 110, html=f'<p>{d}</p>', size=16, pad=0)]
    events['objects'] = [
        mk('artistic', 40, 170, 500, 52, html='<p>Events</p>', font=SERIF, size=40, color='#2f5d3a'),
        mk('table', 40, 250, 880, 260, size=15, head='#dfe8d6', stroke='#c9c5ad', cells=[
            ['Date', 'Group', 'Time', 'Where'], ['Tue 3rd', 'Coffee & Chat', '10am', 'Main room'],
            ['Thu 5th', 'Walking Group', '1pm', 'Meet at the gate'], ['Sat 7th', 'Gardening Club', '10am', 'Riverside beds'],
            ['Tue 10th', 'Book Circle', '11am', 'Library corner'], ['Thu 12th', 'Coffee & Chat', '1pm', 'Main room']]),
    ]
    inv['objects'] = [
        mk('artistic', 40, 170, 500, 52, html='<p>Get involved</p>', font=SERIF, size=40, color='#2f5d3a'),
        mk('text', 40, 240, 420, 220, size=16, pad=0, html='<p>Volunteers make the hub work. Lend a hand for an hour a week or help at a single event.</p><p>Leave your details and we will be in touch.</p>'),
        mk('form', 500, 240, 420, 360, accent='#2f5d3a', fields=['Name', 'Email', 'How would you like to help?'], submit='Send'),
    ]
    s['pages'][-1]['objects'] = [
        mk('artistic', 40, 170, 500, 52, html='<p>Volunteering</p>', font=SERIF, size=40, color='#2f5d3a'),
        mk('text', 40, 240, 600, 120, size=16, pad=0, html='<p>Roles include welcoming, group leading, gardening and making the tea.</p>')]
    return s

def tpl_folio():
    pal = ['#16181a', '#26292c', '#f2efe9', '#d9a441', '#8a9096', '#ffffff']
    s = base_site('Rowan Ellis Illustration', palette=pal, bg='#16181a')
    A = lambda k, cols: add_asset(s, make_art(k, cols))
    m = s['masters'][0]; m['bg'] = '#16181a'
    work = s['pages'][0]; work['title'] = 'Work'
    about, cont = add_page(s, 'About'), add_page(s, 'Contact')
    m['objects'] = [
        mk('artistic', 48, 40, 360, 40, html='<p>Rowan Ellis</p>', font=SANS, size=28, color='#f2efe9'),
        mk('nav', 520, 40, 392, 40, style='plain', align='right', color='#8a9096', accent='#d9a441', size=15),
        mk('text', 48, 1040, 864, 30, html='<p>Illustration for books, packaging and editorial · © 2026</p>', size=13, color='#8a9096', pad=0),
    ]
    kinds = ['rings', 'sun', 'blocks', 'waves', 'stripes', 'hills']
    palettes = [['#26292c', '#d9a441', '#f2efe9', '#c4553a'], ['#2d3b4a', '#1c2630', '#d9a441', '#f2efe9'],
                ['#f2efe9', '#26292c', '#d9a441', '#c4553a'], ['#1e3a3a', '#2f5d5d', '#4d8a7d', '#d9a441'],
                ['#f2efe9', '#c4553a', '#26292c', '#d9a441'], ['#3a2f45', '#6b4f7a', '#2a2233', '#d9a441']]
    titles = ['Night Garden', 'Low Tide', 'Paper City', 'Under the Pier', 'Market Day', 'Hill Fort']
    work['objects'] = [mk('artistic', 48, 120, 860, 70, html='<p>Pictures that tell the story.</p>', font=SERIF, size=48, color='#f2efe9', bold=False)]
    for i in range(6):
        x, y = 48 + (i % 3) * 296, 230 + (i // 3) * 380
        work['objects'] += [mk('picture', x, y, 272, 300, src=A(kinds[i], palettes[i])),
                            mk('text', x, y + 312, 272, 36, html=f'<p>{titles[i]}</p>', size=15, color='#f2efe9', pad=0)]
    about['objects'] = [
        mk('artistic', 48, 120, 600, 60, html='<p>About</p>', font=SERIF, size=48, color='#f2efe9', bold=False),
        mk('text', 48, 210, 520, 300, size=17, color='#d8d4cc', pad=0, html=(
            '<p>I draw with ink and gouache, then finish digitally. Most of my work is for picture books and food packaging.</p>'
            '<p>Recent clients include independent publishers, a cider maker and a city museum.</p>')),
        mk('picture', 620, 210, 292, 360, src=A('rings', ['#26292c', '#c4553a', '#d9a441', '#16181a'])),
    ]
    cont['objects'] = [
        mk('artistic', 48, 120, 600, 60, html='<p>Say hello</p>', font=SERIF, size=48, color='#f2efe9', bold=False),
        mk('text', 48, 210, 520, 80, html='<p>For commissions and availability, email me. I usually reply within two working days.</p>', size=17, color='#d8d4cc', pad=0),
        mk('button', 48, 310, 240, 50, html='<p>studio@rowanellis.example</p>', fill='#d9a441', color='#16181a', radius=0,
           link={'type': 'email', 'target': 'studio@rowanellis.example'}),
    ]
    return s

def tpl_blank(name='My Site', width=960, height=1100):
    s = base_site(name, width=width, height=height,
                  palette=['#1f2a30', '#2a7d6b', '#f4f1ea', '#e0a43a', '#ffffff', '#5d6a71'])
    s['masters'][0]['objects'] = [mk('nav', 40, 30, min(600, width - 80), 40)]
    return s

TEMPLATES = [('Harbour', 'Small business', tpl_harbour), ('Meadow', 'Community group', tpl_meadow),
             ('Folio', 'Portfolio', tpl_folio)]

# ----------------------------------------------------------------------------
# The 89 templates WebPlus X8 shipped
# ----------------------------------------------------------------------------
# serif-templates.json carries what Serif's own Startup Assistant needed to
# offer a template and nothing more: each one's page tree — the names, the
# filenames they publish as, and which page hangs off which — and the colour
# schemes its picker offered, with their twelve colours.
#
# It carries no artwork, no copy and no objects, because this app is a
# recreation and not a copy: the structure is Serif's, every page below is
# drawn here, from this file, in the scheme you pick. A site you start from
# Active gets Active's nine pages with Active's filenames in Active 01's
# colours, and then it is yours.

SERIF_CATALOGUE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'serif-templates.json')
_SERIF = None

def serif_catalogue():
    """The shipped catalogue, read once. An empty dict if it isn't there."""
    global _SERIF
    if _SERIF is None:
        try:
            with open(SERIF_CATALOGUE, encoding='utf-8') as fh:
                _SERIF = json.load(fh)
        except Exception:
            _SERIF = {}
    return _SERIF

def serif_tree(chooser_only=True):
    """[(category, [(surface, [row, ...]), ...]), ...] in the catalogue's order.

    ``chooser_only`` leaves out the eleven Sample documents, which Serif
    catalogued but never offered as something to start a site from.
    """
    out = []
    for row in serif_catalogue().get('templates', []):
        if chooser_only and not row.get('in_chooser'):
            continue
        cat, surf = row.get('category', ''), row.get('surface', '')
        if not out or out[-1][0] != cat:
            out.append((cat, []))
        surfaces = out[-1][1]
        if not surfaces or surfaces[-1][0] != surf:
            surfaces.append((surf, []))
        surfaces[-1][1].append(row)
    return out

#: What a catalogue category is called in the file list. The catalogue keeps
#: the name the disc used; the chooser shows the short one.
CATEGORY_LABELS = {'WebPlus X8 Pro Templates': 'Pro Templates'}

def category_label(cat):
    return CATEGORY_LABELS.get(cat, cat)

def serif_row(key):
    return next((r for r in serif_catalogue().get('templates', []) if r.get('key') == key), None)

def serif_schemes(row):
    """What the scheme picker offers: the template's own first, then the 21."""
    cat = serif_catalogue()
    return list(row.get('schemes') or []) + list(cat.get('generic_schemes') or [])

def serif_pages(row):
    """The page tree in tree order, which is not the order it is stored in.

    Four of the 89 — Bygone, Doodle, Eco, Quote — keep their nine Product
    sub-pages after Terms & Conditions, because that is the order Serif saved
    the spreads in. ``parent`` is what actually says which page a sub-page
    hangs off, and the Site tab nests by position, so walk the tree: each
    page, then its children, before the next one at its own level.
    """
    pages = list(row.get('pages') or [])
    kids = {}
    for i, p in enumerate(pages):
        kids.setdefault(p.get('parent', -1), []).append(i)
    out, seen = [], set()

    def walk(i, depth):
        if i in seen:
            return                                  # a loop; none on the disc has one
        seen.add(i)
        p = dict(pages[i]); p['depth'] = depth
        out.append(p)
        for child in kids.get(i, []):
            walk(child, depth + 1)

    for i in kids.get(-1, []):
        walk(i, 0)
    for i in range(len(pages)):                     # an orphan beats a lost page
        if i not in seen:
            walk(i, 0)
    return out

# --- scheme colours -> the roles a page layout actually needs ----------------
# Serif's twelve are numbered, not named, and what each number does is up to
# the template using it. So the roles are read off the colours themselves —
# the lightest is the paper, the darkest is the ink, the one with the most
# colour in it is the accent. Every one of the 138 schemes gets a usable
# answer that way, which guessing at Serif's intent would not give.

def _lum(c):
    col = QColor(c)
    f = lambda v: v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4
    return .2126 * f(col.redF()) + .7152 * f(col.greenF()) + .0722 * f(col.blueF())

def _chroma(c):
    col = QColor(c)
    v = [col.red(), col.green(), col.blue()]
    return (max(v) - min(v)) / 255.0

def shade(c, pct):
    col = QColor(c)
    return (col.lighter(100 + pct) if pct > 0 else col.darker(100 - pct)).name()

def _ink_on(c):
    return '#ffffff' if _lum(c) < .45 else '#1b1b1b'

def scheme_roles(cols):
    uniq = list(dict.fromkeys(QColor(c).name() for c in (cols or []) if QColor(c).isValid()))
    if not uniq:
        uniq = ['#ffffff', '#3a3a3a', '#2a7d6b']
    by_lum = sorted(uniq, key=_lum)
    lights = [c for c in by_lum if _lum(c) >= .5] or [by_lum[-1]]
    darks = [c for c in by_lum if _lum(c) < .5] or [by_lum[0]]
    page = lights[-1]
    panel = lights[-2] if len(lights) > 1 else shade(page, -5)
    rule = lights[0] if len(lights) > 2 else shade(page, -14)
    mids = [c for c in uniq if .03 <= _lum(c) <= .7] or uniq
    accent = max(mids, key=lambda c: (round(_chroma(c), 2), -abs(_lum(c) - .22)))
    rest = [c for c in darks if c != accent] or darks
    bar = max(rest, key=_lum)
    ink = min(rest, key=_lum)
    if _lum(ink) > .3:
        ink = shade(bar, -40)
    return dict(page=page, panel=panel, rule=rule, bar=bar, barInk=_ink_on(bar),
                ink=ink, head=bar if _lum(bar) < .4 else ink,
                accent=accent, accentInk=_ink_on(accent),
                mute=shade(ink, 45) if _lum(ink) < .4 else shade(ink, -20))

# --- placeholder copy, varied per template so no two read the same ----------

def _pick(seq, key, salt=0):
    # 37 is prime and bigger than every list below, so a step of it never
    # lands back on the same entry — three cards on one page read as three.
    return seq[(sum(ord(c) for c in key) + salt * 37) % len(seq)]

SERIF_TAGLINE = [
    'Made properly, made to last', 'Everything in one place', 'Good work, close to home',
    'Simple, honest, done right', 'A warm welcome awaits', 'One thing, done well',
    'Clear advice and fair prices', 'Built around what you need',
]
SERIF_INTRO = [
    'This is the opening paragraph of your home page. Say who you are and what you do, in one or two plain sentences — it is the first thing anybody reads.',
    'Replace this with a short welcome. Visitors want to know what you offer and whether they are in the right place, and nothing else yet.',
    'A few lines here about what you do and who you do it for. Keep it short; the pages behind this one have room for the detail.',
    'Write your introduction here. One idea per sentence reads best on a screen, and the menu above takes people wherever they need to go next.',
]
SERIF_BODY = [
    'This is a text frame. Click it twice to type in it, and drag its handles to change its shape — the words reflow to fit.',
    'Everything on this page is an object you can move, resize or delete. Nothing here is fixed, and nothing is locked.',
    'The header and the menu live on a master page, so changing them once changes them on every page of the site.',
    'Add your own pictures with Insert ▸ Picture, or drop an image file straight onto the page.',
    'When the site reads the way you want it, File ▸ Publish writes plain HTML into a folder you can upload anywhere.',
]
SERIF_CARDS = [
    ('What we do', 'A short description of your main service or product, and who it suits.'),
    ('How it works', 'Three or four lines on what happens after someone gets in touch.'),
    ('Why us', 'What you do differently. Specifics read better here than adjectives.'),
    ('Get started', 'Tell people the one next step you want them to take, and make it easy.'),
    ('Where we are', 'Your area, your opening times, and how to find you.'),
    ('Who we help', 'The kind of customer, client or member you are looking for.'),
]
SERIF_ART = ['waves', 'hills', 'blocks', 'rings', 'grid', 'sun', 'stripes']

SERIF_KINDS = (
    (r'contact|enquir|e-?mail|find us|get in touch|book|reserv', 'contact'),
    (r'galler|photo|picture|portfolio|our work|showcase|image', 'gallery'),
    (r'price|rate|tariff|menu|package|plan|fee|cost|timetable|schedule|opening', 'table'),
    (r'product|service|room|class|course|treatment|what we do|facilit|range|shop', 'cards'),
    (r'term|privacy|condition|cookie|legal|disclaimer|policy', 'legal'),
    (r'link|resource|partner|supplier|useful', 'links'),
    (r'news|blog|article|event|diary|journal|update|press|offer', 'news'),
    (r'faq|question|help|support', 'faq'),
)

def serif_kind(name, index):
    if index == 0:
        return 'home'
    low = (name or '').lower()
    for pattern, kind in SERIF_KINDS:
        if re.search(pattern, low):
            return kind
    return 'about'

class _Flow:
    """Stack objects down a column and remember where the bottom got to."""

    def __init__(self, objects, x, y, w, gap=22):
        self.o, self.x, self.y, self.w, self.gap = objects, x, y, w, gap

    def add(self, kind, h, **kw):
        w = kw.pop('w', self.w)
        obj = mk(kind, kw.pop('x', self.x), self.y, w, h, **kw)
        self.o.append(obj)
        self.y += h + self.gap
        return obj

    def at(self, kind, x, y, w, h, **kw):
        obj = mk(kind, x, y, w, h, **kw)
        self.o.append(obj)
        self.y = max(self.y, y + h + self.gap)
        return obj

    def heading(self, text, C, size):
        return self.add('artistic', int(size * 1.35), html=f'<p>{H.escape(text)}</p>',
                        font=SERIF, size=size, color=C['head'], bold=False)

def serif_site(row, scheme=None):
    """Build an editable site from one catalogue row, in one colour scheme."""
    cat = serif_catalogue()
    offered = serif_schemes(row)
    if scheme not in offered:
        scheme = offered[0] if offered else None
    C = scheme_roles(cat.get('schemes', {}).get(scheme) or [])
    key = row.get('key') or row.get('name') or 'template'
    brand = row.get('name') or 'My Site'
    mobile = 'Mobile' in (row.get('surface') or '')
    W = 480 if mobile else 960
    M = 20 if mobile else 40
    CW = W - 2 * M
    top = 150 if mobile else 128

    s = base_site(brand, width=W, bg=C['page'],
                  palette=[C['bar'], C['accent'], C['page'], C['panel'], C['ink'], C['rule']])
    s['pages'] = []
    s['serif'] = {'key': key, 'name': brand, 'scheme': scheme,
                  'category': row.get('category', ''), 'surface': row.get('surface', '')}
    for p in serif_pages(row):
        add_page(s, p.get('name') or 'Page', level=max(0, int(p.get('depth') or 0)),
                 file=p.get('file') or None)
    if not s['pages']:
        add_page(s, 'Home', file='index.html')

    A = lambda i, light=False: add_asset(s, make_art(
        _pick(SERIF_ART, key, i),
        [C['panel'] if light else C['bar'], shade(C['bar'], 25 if light else -25),
         C['accent'], C['page']], 720, 480))
    title_size = 30 if mobile else 46
    head_size = 24 if mobile else 36

    second = s['pages'][1] if len(s['pages']) > 1 else None
    for i, page in enumerate(s['pages']):
        kind = serif_kind(page['title'], i)
        f = _Flow(page['objects'], M, top, CW)
        if kind == 'home':
            f.add('picture', 200 if mobile else 330, src=A(0), radius=4)
            f.add('artistic', int(title_size * 1.4), html=f'<p>{H.escape(brand)}</p>',
                  font=SERIF, size=title_size, color=C['head'], bold=False)
            f.add('text', 46 if mobile else 38, pad=0, size=17 if mobile else 20,
                  color=C['mute'], html=f"<p>{_pick(SERIF_TAGLINE, key)}</p>")
            f.add('text', 150 if mobile else 92, pad=0, size=15 if mobile else 17,
                  color=C['ink'], html=f'<p>{_pick(SERIF_INTRO, key)}</p>')
            btn = f.add('button', 48, w=min(CW, 240), html='<p>Find out more</p>',
                        fill=C['accent'], color=C['accentInk'], radius=4)
            if second:
                btn['link'] = {'type': 'page', 'target': second['id']}
            cards = [_pick(SERIF_CARDS, key, n) for n in range(3)]
            cw = CW if mobile else (CW - 2 * 24) // 3
            y0 = f.y
            for n, (t, d) in enumerate(cards):
                x = M if mobile else M + n * (cw + 24)
                y = y0 + (n * 330 if mobile else 0)
                f.at('picture', x, y, cw, 160, src=A(n + 1, light=True), radius=4)
                f.at('artistic', x, y + 176, cw, 30, html=f'<p>{H.escape(t)}</p>',
                     font=SERIF, size=20, color=C['head'], bold=False)
                f.at('text', x, y + 212, cw, 100, pad=0, size=15, color=C['ink'],
                     html=f'<p>{H.escape(d)}</p>')
        else:
            f.heading(page['title'], C, head_size)
            if kind == 'about':
                paras = ''.join(f'<p>{_pick(SERIF_BODY, key, n + i)}</p>' for n in range(3))
                if mobile:
                    f.add('text', 230, pad=0, size=15, color=C['ink'], html=paras)
                    f.add('picture', 200, src=A(i + 2, light=True), radius=4)
                else:
                    tw = int(CW * .56)
                    f.at('text', M, f.y, tw, 300, pad=0, size=16, color=C['ink'], html=paras)
                    f.at('picture', M + tw + 32, f.y, CW - tw - 32, 300,
                         src=A(i + 2, light=True), radius=4)
            elif kind == 'gallery':
                f.add('text', 50, pad=0, size=15, color=C['mute'],
                      html='<p>Replace these with your own pictures — Insert ▸ Picture, or drop an image file onto the page.</p>')
                across = 2 if mobile else 3
                tw = (CW - (across - 1) * 18) // across
                y0 = f.y
                for n in range(6):
                    f.at('picture', M + (n % across) * (tw + 18),
                         y0 + (n // across) * (int(tw * .72) + 18), tw, int(tw * .72),
                         src=A(n + i, light=n % 2 == 0), radius=4)
            elif kind == 'table':
                f.add('text', 50, pad=0, size=15, color=C['ink'],
                      html='<p>Type over these cells, and use Table ▸ Insert Row to add more.</p>')
                f.add('table', 200, size=14, color=C['ink'], fill=C['page'],
                      head=C['panel'], stroke=C['rule'],
                      cells=[['Item', 'Detail', 'From'],
                             ['First item', 'What it includes', '£00'],
                             ['Second item', 'What it includes', '£00'],
                             ['Third item', 'What it includes', '£00'],
                             ['Fourth item', 'What it includes', '£00']])
            elif kind == 'cards':
                f.add('text', 50, pad=0, size=15, color=C['ink'],
                      html='<p>One panel each. Copy a panel and its text to add another.</p>')
                across = 1 if mobile else 2
                tw = (CW - (across - 1) * 24) // across
                y0 = f.y
                for n in range(4):
                    x = M + (n % across) * (tw + 24)
                    y = y0 + (n // across) * 190
                    t, d = _pick(SERIF_CARDS, key, n + 2)
                    f.at('shape', x, y, tw, 170, fill=C['panel'], radius=4)
                    f.at('artistic', x + 20, y + 20, tw - 40, 30, html=f'<p>{H.escape(t)}</p>',
                         font=SERIF, size=20, color=C['head'], bold=False)
                    f.at('text', x + 20, y + 58, tw - 40, 96, pad=0, size=15, color=C['ink'],
                         html=f'<p>{H.escape(d)}</p>')
            elif kind == 'contact':
                if mobile:
                    f.add('text', 150, pad=0, size=15, color=C['ink'], html=(
                        f'<p><b>{H.escape(brand)}</b><br>Your address here</p>'
                        '<p>Phone 01234 567890<br>Open Monday to Friday</p>'))
                    f.add('form', 320, accent=C['accent'], color=C['ink'],
                          fields=['Name', 'Email', 'Message'], submit='Send')
                else:
                    tw = int(CW * .44)
                    f.at('text', M, f.y, tw, 180, pad=0, size=16, color=C['ink'], html=(
                        f'<p><b>{H.escape(brand)}</b><br>Your address here</p>'
                        '<p>Phone 01234 567890<br>Open Monday to Friday</p>'))
                    f.at('picture', M, f.y + 200, tw, 200, src=A(i, light=True), radius=4)
                    f.at('form', M + tw + 32, f.y, CW - tw - 32, 340, accent=C['accent'],
                         color=C['ink'], fields=['Name', 'Email', 'Phone', 'Message'],
                         submit='Send enquiry')
            elif kind == 'news':
                f.add('text', 46, pad=0, size=15, color=C['mute'],
                      html='<p>Newest at the top. Each entry is a heading and a text frame.</p>')
                for n in range(4):
                    f.add('artistic', 28, html=f'<p>Headline {n + 1}</p>', font=SERIF,
                          size=19, color=C['head'], bold=False)
                    f.add('text', 62, pad=0, size=15, color=C['ink'],
                          html=f'<p>{_pick(SERIF_BODY, key, n + i + 1)}</p>')
                    f.add('line', 2, stroke=C['rule'], strokeW=1)
            elif kind == 'faq':
                for n in range(4):
                    f.add('artistic', 26, html=f'<p>A question people ask ({n + 1})</p>',
                          font=SERIF, size=18, color=C['accent'], bold=False)
                    f.add('text', 60, pad=0, size=15, color=C['ink'],
                          html=f'<p>{_pick(SERIF_BODY, key, n + i)}</p>')
            elif kind == 'links':
                f.add('text', 46, pad=0, size=15, color=C['ink'],
                      html='<p>Select a line and use Insert ▸ Hyperlink to point it somewhere.</p>')
                for n in range(5):
                    f.add('text', 44, pad=0, size=16, color=C['accent'], underline=True,
                          html=f'<p>A useful link ({n + 1})</p>')
            else:                                     # legal
                f.add('text', 420, pad=0, size=14, color=C['ink'], html=''.join(
                    f'<p>{_pick(SERIF_BODY, key, n)}</p>' for n in range(5)) + (
                    '<p>This page is a placeholder. Write your own terms, or delete the '
                    'page from the Site tab if you do not need it.</p>'))

    bottom = max([max([o['y'] + o['h'] for o in p['objects']], default=0) for p in s['pages']],
                 default=0)
    s['height'] = int(max(900, bottom + (150 if mobile else 170)))

    m = s['masters'][0]
    m['bg'] = C['page']
    fy = s['height'] - (92 if mobile else 96)
    if mobile:
        m['objects'] = [
            mk('shape', 0, 0, W, 108, fill=C['bar']),
            mk('artistic', M, 22, CW, 34, html=f'<p>{H.escape(brand)}</p>', font=SERIF,
               size=24, color=C['barInk'], bold=False),
            mk('nav', M, 66, CW, 32, style='pills', align='center', size=13, color=C['barInk'],
               accent=C['accent'], accentInk=C['accentInk']),
            mk('line', M, fy, CW, 2, stroke=C['rule'], strokeW=2),
            mk('text', M, fy + 16, CW, 54, pad=0, size=12, color=C['mute'],
               html=f'<p>© {H.escape(brand)}. Made with just a... WEBcreator.</p>'),
        ]
    else:
        m['objects'] = [
            mk('shape', 0, 0, W, 96, fill=C['bar']),
            mk('artistic', M, 26, 380, 44, html=f'<p>{H.escape(brand)}</p>', font=SERIF,
               size=30, color=C['barInk'], bold=False),
            mk('nav', W - M - 480, 28, 480, 40, style='underline', align='right', size=15,
               color=C['barInk'], accent=C['accent'], accentInk=C['accentInk']),
            mk('shape', 0, fy, W, 96, fill=C['bar']),
            mk('text', M, fy + 24, CW, 48, pad=0, size=13, color=C['barInk'],
               html=f'<p>© {H.escape(brand)} · Your address here · 01234 567890</p>'),
        ]
    return s

# ----------------------------------------------------------------------------
# Painting objects (canvas, thumbnails)
# ----------------------------------------------------------------------------

_PIX = {}
def pixmap_for(site, key):
    src = site.get('assets', {}).get(key)
    if not src: return None
    if key not in _PIX:
        pm = QPixmap(); pm.loadFromData(QByteArray.fromBase64(src.split(',', 1)[1].encode()))
        _PIX[key] = pm
    return _PIX[key]

ALIGN = {'left': Qt.AlignLeft, 'center': Qt.AlignHCenter, 'right': Qt.AlignRight, 'justify': Qt.AlignJustify}
DASH = {'solid': Qt.SolidLine, 'dashed': Qt.DashLine, 'dotted': Qt.DotLine}

def qfont(o):
    f = QFont(o.get('font', SANS)); f.setPixelSize(max(1, int(o.get('size', 16))))
    f.setBold(bool(o.get('bold'))); f.setItalic(bool(o.get('italic'))); f.setUnderline(bool(o.get('underline')))
    return f

def make_doc(o):
    doc = QTextDocument(); doc.setDocumentMargin(0); doc.setDefaultFont(qfont(o))
    opt = QTextOption(); opt.setAlignment(ALIGN.get(o.get('align', 'left'), Qt.AlignLeft))
    if o['type'] == 'artistic': opt.setWrapMode(QTextOption.NoWrap)
    doc.setDefaultTextOption(opt)
    doc.setHtml(o.get('html', ''))
    cur = QTextCursor(doc); blk = doc.begin(); gap = round(o.get('size', 16) * o.get('pgap', .6))
    while blk.isValid():
        cur.setPosition(blk.position())
        bf = blk.blockFormat(); bf.setTopMargin(0)
        bf.setBottomMargin(0 if not blk.next().isValid() or o['type'] != 'text' else gap)
        lh = o.get('lh', 1.4)
        if lh != 'normal':
            bf.setLineHeight(float(lh) * o.get('size', 16), 3)  # 3 = MinimumHeight, like CSS line-height
        if not bf.hasProperty(QTextBlockFormat.BlockAlignment):
            bf.setAlignment(ALIGN.get(o.get('align', 'left'), Qt.AlignLeft))
        cur.setBlockFormat(bf); blk = blk.next()
    pad = o.get('pad', 8) if o['type'] == 'text' else 0
    doc.setTextWidth(max(10, o['w'] - 2 * pad))
    return doc

TEXT_PROPS = {
    'font': ('FontFamilies', 'FontFamily'), 'size': ('FontPixelSize', 'FontPointSize'), 'color': ('ForegroundBrush',),
    'bold': ('FontWeight',), 'italic': ('FontItalic',), 'underline': ('FontUnderline', 'TextUnderlineStyle'),
}

def _prop_ids(keys):
    from PySide6.QtGui import QTextFormat
    return [getattr(QTextFormat.Property, n) for k in keys for n in TEXT_PROPS[k]]

def _doc_body(doc):
    m = re.search(r'<body[^>]*>(.*)</body>', doc.toHtml(), re.S)
    return m.group(1).strip() if m else doc.toHtml()

def clear_text_format(o, keys):
    """Remove formatting set on individual words for these settings, so the frame's own setting applies.
    Links keep their colour and underline."""
    if not o.get('html'): return o.get('html')
    doc = make_doc(o); ids = _prop_ids(keys); changed = False
    link_keep = set(_prop_ids([k for k in ('color', 'underline') if k in keys]))
    # read everything first: changing the text while stepping through it is not safe
    blocks, frags = [], []
    blk = doc.begin()
    while blk.isValid():
        bcf = blk.charFormat()
        if any(bcf.hasProperty(i) for i in ids):
            for i in ids: bcf.clearProperty(i)
            blocks.append((blk.position(), bcf))
        it = blk.begin()
        while not it.atEnd():
            f = it.fragment(); cf = f.charFormat()
            drop = [i for i in ids if cf.hasProperty(i) and not (cf.isAnchor() and i in link_keep)]
            if drop:
                for i in drop: cf.clearProperty(i)
                frags.append((f.position(), f.length(), cf))
            it += 1
        blk = blk.next()
    if not blocks and not frags: return o['html']
    cur = QTextCursor(doc)
    for pos, bcf in blocks:
        cur.setPosition(pos); cur.setBlockCharFormat(bcf)
    for pos, ln, cf in frags:
        cur.setPosition(pos); cur.setPosition(pos + ln, QTextCursor.KeepAnchor); cur.setCharFormat(cf)
    return _doc_body(doc)

def lift_text_format(o):
    """If every word shares one size / colour / font set on the words themselves, make it the frame's
    setting instead, so the toolbar shows and changes what you actually see."""
    if not o.get('html') or o['type'] not in ('text', 'artistic', 'button'): return False
    from PySide6.QtGui import QTextFormat
    P = QTextFormat.Property
    doc = make_doc(o); seen = {'size': set(), 'color': set(), 'font': set()}; n = 0
    blk = doc.begin()
    while blk.isValid():
        it = blk.begin()
        while not it.atEnd():
            f = it.fragment(); cf = f.charFormat()
            if f.text().strip() and not cf.isAnchor():
                n += 1
                seen['size'].add(cf.intProperty(P.FontPixelSize) if cf.hasProperty(P.FontPixelSize) else
                                 (round(cf.doubleProperty(P.FontPointSize) * 4 / 3) if cf.hasProperty(P.FontPointSize) else None))
                seen['color'].add(cf.foreground().color().name() if cf.hasProperty(P.ForegroundBrush) else None)
                fam = cf.fontFamilies() if cf.hasProperty(P.FontFamilies) else None
                seen['font'].add(fam[0] if fam else None)
            it += 1
        blk = blk.next()
    if not n: return False
    lift = {k: next(iter(v)) for k, v in seen.items() if len(v) == 1 and next(iter(v))}
    if not lift: return False
    for k, v in lift.items(): o[k] = v
    o['html'] = clear_text_format(o, list(lift))
    return True

def obj_pen(o):
    if o.get('strokeW', 0) > 0 and o.get('stroke'):
        pn = QPen(QColor(o['stroke']), o['strokeW']); pn.setStyle(DASH.get(o.get('dash', 'solid'), Qt.SolidLine))
        pn.setJoinStyle(Qt.MiterJoin); return pn
    return QPen(Qt.NoPen)

def obj_brush(o):
    return QBrush(QColor(o['fill'])) if o.get('fill') else QBrush(Qt.NoBrush)

def nav_items(site, o=None):
    if o and o.get('pages'):
        byid = {q['id']: q for q in site['pages']}
        return [(byid[i], []) for i in o['pages'] if i in byid]
    out = []
    for q in site['pages']:
        if not q.get('nav', True): continue
        if q.get('level'):
            if out: out[-1][1].append(q)
        else:
            out.append((q, []))
    return out

def paint_obj(p, o, site, page, hide_text=False, edit=True):
    t, w, h = o['type'], o['w'], o['h']
    r = QRectF(0, 0, w, h)
    rad = o.get('radius', 0)
    def box():
        sw = o.get('strokeW', 0) if o.get('stroke') else 0
        rr = r.adjusted(sw / 2, sw / 2, -sw / 2, -sw / 2)
        p.setPen(obj_pen(o)); p.setBrush(obj_brush(o))
        if rad: p.drawRoundedRect(rr, rad, rad)
        else: p.drawRect(rr)
    if t == 'shape':
        sw = o.get('strokeW', 0); rr = r.adjusted(sw / 2, sw / 2, -sw / 2, -sw / 2)
        p.setPen(obj_pen(o)); p.setBrush(obj_brush(o))
        if o.get('shape') == 'ellipse': p.drawEllipse(rr)
        else: p.drawRoundedRect(rr, rad, rad) if rad else p.drawRect(rr)
    elif t == 'line':
        pw = max(1, o.get('strokeW', 2))
        pn = QPen(QColor(o.get('stroke', '#000')), pw); pn.setStyle(DASH.get(o.get('dash', 'solid'))); pn.setCapStyle(Qt.FlatCap)
        p.setPen(pn)
        if h <= pw + 2: p.drawLine(QPointF(0, h / 2), QPointF(w, h / 2))
        elif w <= pw + 2: p.drawLine(QPointF(w / 2, 0), QPointF(w / 2, h))
        elif o.get('flip'): p.drawLine(QPointF(0, h), QPointF(w, 0))
        else: p.drawLine(QPointF(0, 0), QPointF(w, h))
    elif t == 'picture':
        path = QPainterPath(); path.addRoundedRect(r, rad, rad)
        p.save(); p.setClipPath(path)
        pm = pixmap_for(site, o.get('src')) if o.get('src') else None
        if pm and not pm.isNull():
            pw_, ph_ = pm.width(), pm.height(); fit = o.get('fit', 'cover')
            if fit == 'stretch':
                p.drawPixmap(r, pm, QRectF(0, 0, pw_, ph_))
            elif fit == 'contain':
                sc = min(w / pw_, h / ph_); tw, th = pw_ * sc, ph_ * sc
                if o.get('fill'): p.fillRect(r, QColor(o['fill']))
                p.drawPixmap(QRectF((w - tw) / 2, (h - th) / 2, tw, th), pm, QRectF(0, 0, pw_, ph_))
            else:
                sc = max(w / pw_, h / ph_); sw_, sh_ = w / sc, h / sc
                p.drawPixmap(r, pm, QRectF((pw_ - sw_) / 2, (ph_ - sh_) / 2, sw_, sh_))
        else:
            p.fillRect(r, QColor('#dde2e5')); p.setPen(QPen(QColor('#b5bdc2'), 1))
            p.drawLine(r.topLeft(), r.bottomRight()); p.drawLine(r.topRight(), r.bottomLeft())
            if edit:
                f = QFont(); f.setPixelSize(13); p.setFont(f); p.setPen(QColor('#4b555b'))
                lbl = QRectF(0, h / 2 - 14, w, 28); p.fillRect(lbl.adjusted(w * .15, 0, -w * .15, 0), QColor('#dde2e5'))
                p.drawText(lbl, Qt.AlignCenter, 'Double-click to add a picture')
        p.restore()
        if o.get('strokeW', 0) > 0:
            p.setPen(obj_pen(o)); p.setBrush(Qt.NoBrush); p.drawRoundedRect(r, rad, rad)
    elif t == 'gallery':
        imgs = o.get('images') or []
        pm = pixmap_for(site, imgs[0]) if imgs else None
        path = QPainterPath(); path.addRoundedRect(r, rad, rad)
        p.save(); p.setClipPath(path)
        if pm and not pm.isNull():
            pw_, ph_ = pm.width(), pm.height(); sc = max(w / pw_, h / ph_); sw_, sh_ = w / sc, h / sc
            p.drawPixmap(r, pm, QRectF((pw_ - sw_) / 2, (ph_ - sh_) / 2, sw_, sh_))
        else:
            p.fillRect(r, QColor('#dde2e5'))
        if edit:
            f = QFont(); f.setPixelSize(12); p.setFont(f)
            label = f'▶ Photo gallery · {len(imgs)} photo' + ('' if len(imgs) == 1 else 's') if imgs else 'Double-click to add photos'
            fm = QFontMetrics(f); lw = fm.horizontalAdvance(label) + 16
            lr = QRectF(8, h - 30, lw, 22) if imgs else QRectF((w - lw) / 2, h / 2 - 11, lw, 22)
            p.setPen(Qt.NoPen); p.setBrush(QColor(0, 0, 0, 150)); p.drawRoundedRect(lr, 4, 4)
            p.setPen(QColor('#ffffff')); p.drawText(lr, Qt.AlignCenter, label)
        p.restore()
    elif t in ('text', 'artistic', 'button'):
        box()
        if not hide_text:
            doc = make_doc(o)
            pad = o.get('pad', 8) if t == 'text' else 0
            y = pad
            if t == 'button': y = (h - doc.size().height()) / 2
            ctx = QAbstractTextDocumentLayout.PaintContext()
            ctx.palette.setColor(QPalette.Text, QColor(o.get('color', '#000')))
            p.save(); p.setClipRect(r); p.translate(pad, y)
            doc.documentLayout().draw(p, ctx); p.restore()
    elif t == 'nav':
        if o.get('fill'): p.fillRect(r, QColor(o['fill']))
        f = qfont(o); p.setFont(f); fm = QFontMetrics(f)
        items = nav_items(site, o); padx, gap = int(o.get('pad', 14)), int(o.get('gap', 6))
        ih = fm.height() + 16
        acc, ink = QColor(o.get('accent', '#2a7d6b')), QColor(o.get('accentInk', '#ffffff'))
        style = o.get('style', 'pills')
        rects = []
        if o.get('orient') == 'v':
            y = 0
            for q, kids in items:
                rects.append((q, QRectF(0, y, w, ih))); y += ih + gap
        else:
            rows, row, rw = [], [], 0
            for q, _ in items:
                wi = fm.horizontalAdvance(q['title']) + 2 * padx
                if row and rw + gap + wi > w: rows.append((row, rw)); row, rw = [], 0
                rw += (gap if row else 0) + wi; row.append((q, wi))
            if row: rows.append((row, rw))
            y0 = (h - ih) / 2 if len(rows) == 1 else 0
            for row, rw in rows:
                x = {'center': (w - rw) / 2, 'right': w - rw}.get(o.get('align', 'left'), 0)
                for q, wi in row:
                    rects.append((q, QRectF(x, y0, wi, ih))); x += wi + gap
                y0 += ih + gap
        for q, rr in rects:
            on = page is not None and q['id'] == page['id']
            col = QColor(o.get('color', '#000'))
            p.setPen(Qt.NoPen)
            if style == 'tabs':
                path = QPainterPath(); path.addRoundedRect(rr, 6, 6)
                p.fillPath(path, acc if on else QColor(0, 0, 0, 16))
                if on: col = ink
            elif style == 'pills' and on:
                p.setBrush(acc); p.drawRoundedRect(rr, ih / 2, ih / 2); col = ink
            elif style == 'underline' and on:
                p.fillRect(QRectF(rr.left(), rr.bottom() - 2, rr.width(), 2), acc)
            elif style == 'plain' and on:
                col = acc
            p.setPen(col); p.drawText(rr, Qt.AlignCenter, q['title'])
    elif t == 'table':
        cells = o.get('cells') or [['']]
        n, mcols = len(cells), max(len(rw) for rw in cells)
        rh, cw = h / n, w / mcols
        p.fillRect(r, QColor(o.get('fill') or '#ffffff'))
        p.fillRect(QRectF(0, 0, w, rh), QColor(o.get('head', '#eeeeee')))
        f = qfont(o); fb = QFont(f); fb.setBold(True)
        p.setPen(QPen(QColor(o.get('stroke', '#cccccc')), 1))
        for i in range(n + 1): p.drawLine(QPointF(0, min(i * rh, h - .5)), QPointF(w, min(i * rh, h - .5)))
        for j in range(mcols + 1): p.drawLine(QPointF(min(j * cw, w - .5), 0), QPointF(min(j * cw, w - .5), h))
        p.setPen(QColor(o.get('color', '#000')))
        for i, row in enumerate(cells):
            p.setFont(fb if i == 0 else f)
            for j, txt in enumerate(row):
                cr = QRectF(j * cw + 10, i * rh, cw - 20, rh)
                p.drawText(cr, Qt.AlignVCenter | Qt.AlignLeft, QFontMetrics(p.font()).elidedText(re.sub('<[^>]+>', '', str(txt)), Qt.ElideRight, int(cr.width())))
    elif t == 'form':
        f = qfont(o); p.setFont(f); fm = QFontMetrics(f)
        y, col = 0, QColor(o.get('color', '#222'))
        for fld in o.get('fields', []):
            p.setPen(col); p.drawText(QRectF(0, y, w, fm.height()), Qt.AlignLeft, fld); y += fm.height() + 4
            big = any(k in fld.lower() for k in ('message', 'help', 'comment', 'enquiry', 'details'))
            fh = 84 if big else fm.height() + 16
            p.setPen(QPen(QColor('#c9d1d6'), 1)); p.setBrush(QColor('#ffffff'))
            p.drawRoundedRect(QRectF(.5, y + .5, w - 1, fh), 6, 6); y += fh + 10
        bw = fm.horizontalAdvance(o.get('submit', 'Send')) + 40
        p.setPen(Qt.NoPen); p.setBrush(QColor(o.get('accent', '#2a7d6b')))
        br = QRectF(0, y, bw, fm.height() + 20); p.drawRoundedRect(br, 6, 6)
        fb = QFont(f); fb.setBold(True); p.setFont(fb); p.setPen(QColor('#ffffff'))
        p.drawText(br, Qt.AlignCenter, o.get('submit', 'Send'))
    elif t == 'share':
        f = qfont(dict(o, bold=True)); p.setFont(f); fm = QFontMetrics(f)
        x, bh, gap = 0, fm.height() + 18, o.get('gap', 8)
        for nid in o.get('nets', []):
            if nid not in NET: continue
            _, label, col, _ = NET[nid]; bw = fm.horizontalAdvance(label) + 28
            br = QRectF(x, (h - bh) / 2, bw, bh)
            if o.get('style') == 'outline':
                p.setPen(QPen(QColor(col), 1.5)); p.setBrush(Qt.NoBrush); p.drawRoundedRect(br.adjusted(.75, .75, -.75, -.75), o.get('radius', 6), o.get('radius', 6))
                p.setPen(QColor(col))
            else:
                p.setPen(Qt.NoPen); p.setBrush(QColor(col)); p.drawRoundedRect(br, o.get('radius', 6), o.get('radius', 6)); p.setPen(QColor('#ffffff'))
            p.drawText(br, Qt.AlignCenter, label); x += bw + gap
    elif t == 'html':
        p.setPen(QPen(QColor('#7a858b'), 1, Qt.DashLine)); p.setBrush(QColor(240, 243, 245, 230)); p.drawRect(r.adjusted(.5, .5, -.5, -.5))
        f = QFont('monospace'); f.setPixelSize(12); p.setFont(f); p.setPen(QColor('#3b454b'))
        first = (o.get('code', '').strip().splitlines() or [''])[0]
        p.drawText(r.adjusted(10, 8, -10, -8), Qt.AlignLeft | Qt.AlignTop, '</> HTML fragment (shows when you preview or publish)\n' + first)

def placed(o, site, page_h):
    """A master object set to stay at the bottom of the page keeps its distance from the bottom edge."""
    if o.get('anchor') == 'bottom':
        return dict(o, y=o['y'] + (page_h - site['height']))
    return o

def page_objects(site, page):
    m = next((x for x in site['masters'] if x['id'] == page['master']), site['masters'][0])
    ph = page.get('height') or site['height']
    return [placed(o, site, ph) for o in m['objects']] + page['objects']

def render_page_image(site, page, width=240, crop=None):
    W, Hh = site['width'], page.get('height') or site['height']
    if crop: Hh = min(Hh, crop)
    sc = width / W
    img = QImage(int(width), int(Hh * sc), QImage.Format_ARGB32_Premultiplied)
    m = next((x for x in site['masters'] if x['id'] == page['master']), site['masters'][0])
    img.fill(QColor(page.get('bg') or m.get('bg') or site.get('bg') or '#ffffff'))
    p = QPainter(img); p.setRenderHint(QPainter.Antialiasing); p.setRenderHint(QPainter.SmoothPixmapTransform); p.scale(sc, sc)
    for o in page_objects(site, page):
        if o.get('hidden'): continue
        p.save(); p.translate(o['x'], o['y'])
        if o.get('rot'):
            p.translate(o['w'] / 2, o['h'] / 2); p.rotate(o['rot']); p.translate(-o['w'] / 2, -o['h'] / 2)
        p.setOpacity(o.get('opacity', 1)); paint_obj(p, o, site, page, edit=False); p.restore()
    p.end()
    return img

# ----------------------------------------------------------------------------
# Publishing to HTML
# ----------------------------------------------------------------------------

GOOGLE = {'Noto Sans', 'Noto Serif', 'Lora', 'Work Sans', 'Playfair Display', 'Montserrat', 'Merriweather',
          'Source Sans 3', 'Open Sans', 'Roboto', 'Lato', 'Raleway', 'Oswald', 'PT Serif', 'PT Sans'}

def css_font(f):
    lf = f.lower()
    fb = 'Georgia, serif' if any(k in lf for k in ('serif', 'lora', 'playfair', 'merriweather', 'georgia', 'times')) and 'sans' not in lf \
        else 'monospace' if ('mono' in lf or 'courier' in lf) else 'Arial, sans-serif'
    return f"'{f}', {fb}"

PUBLISH_CSS = """*{box-sizing:border-box}
body{margin:0;padding:0}
.pf-page{position:relative;margin:0 auto;overflow:hidden;font-family:Arial,sans-serif;color:#222;font-size:16px}
.obj{position:absolute;margin:0;display:block}
a.obj{color:inherit;text-decoration:none}
.obj-text{overflow-wrap:break-word}
.obj-artistic,.obj-button{overflow:hidden;overflow-wrap:break-word}
.obj p{margin:0}
.obj-text p{margin:0 0 calc(var(--pg,.6)*1em)}
.obj-text p:last-child{margin-bottom:0}
.obj-artistic{white-space:nowrap}
.obj-button{display:flex;flex-direction:column;justify-content:center}
.obj-picture img{width:100%;height:100%;display:block}
.obj-nav{display:flex;flex-wrap:wrap;gap:6px;align-items:center;align-content:center;z-index:50}
.obj-nav.v{flex-direction:column;flex-wrap:nowrap;align-items:stretch}
.obj-nav .nv{position:relative}
.obj-nav a{display:block;text-decoration:none;color:inherit;padding:8px var(--nvpad,14px);white-space:nowrap;text-align:center;line-height:1.2}
.obj-nav .sub{display:none;position:absolute;top:100%;left:0;min-width:100%;background:#fff;box-shadow:0 6px 18px rgba(0,0,0,.15);border-radius:6px;padding:4px;z-index:60}
.obj-nav .sub a{color:#222;text-align:left;border-radius:4px}
.obj-nav .sub a:hover{background:rgba(0,0,0,.06)}
.obj-nav .nv:hover .sub{display:block}
.nav-pills a.on{background:var(--na);color:var(--nai);border-radius:999px}
.nav-underline a.on{box-shadow:inset 0 -2px 0 var(--na)}
.nav-tabs>.nv>a{background:rgba(0,0,0,.06);border-radius:6px}
.nav-tabs>.nv>a.on{background:var(--na);color:var(--nai)}
.nav-plain a.on{color:var(--na)}
.obj-table table{width:100%;height:100%;border-collapse:collapse;table-layout:fixed}
.obj-table td{border:1px solid var(--tb);padding:0 10px}
.obj-table tr:first-child td{background:var(--th);font-weight:700}
.obj-form{display:flex;flex-direction:column;gap:4px}
.obj-form label{display:block}
.obj-form input,.obj-form textarea{display:block;width:100%;font:inherit;padding:8px 10px;margin:4px 0 10px;border:1px solid #c9d1d6;border-radius:6px;background:#fff;color:#222}
.obj-form textarea{height:84px;resize:vertical}
.obj-form button{align-self:flex-start;font:inherit;font-weight:700;padding:10px 20px;border:0;border-radius:6px;background:var(--na);color:#fff;cursor:pointer}
"""

def esc(s): return H.escape(str(s), quote=True)

def text_css(o):
    return (f"font-family:{css_font(o.get('font', SANS))};font-size:{o.get('size', 16)}px;color:{o.get('color', '#222')};"
            f"text-align:{o.get('align', 'left')};font-weight:{700 if o.get('bold') else 400};"
            f"font-style:{'italic' if o.get('italic') else 'normal'};text-decoration:{'underline' if o.get('underline') else 'none'};"
            f"line-height:{o.get('lh', 1.4)};")

def box_css(o):
    s = ''
    if o.get('fill'): s += f"background:{o['fill']};"
    if o.get('strokeW', 0) > 0 and o.get('stroke'): s += f"border:{o['strokeW']}px {o.get('dash', 'solid')} {o['stroke']};"
    if o.get('radius'): s += f"border-radius:{o['radius']}px;"
    return s

def clean_html(fragment, site=None, asset=None):
    # Qt adds editor-only properties; drop them for the web.
    if site is not None:
        def repl(m):
            kind, val = m.group(1), m.group(2)
            if kind == 'page':
                pg = next((q for q in site['pages'] if q['id'] == val), None)
                return f'href="{esc(pg["file"]) if pg else "#"}"'
            return f'href="{esc(asset(val))}" target="_blank"' if asset and val in site.get('assets', {}) else 'href="#"'
        fragment = re.sub(r'href="wc(page|file):([^"]+)"', repl, fragment)
    fragment = re.sub(r'-qt-[a-z-]+:[^;"]*;?', '', fragment)
    fragment = re.sub(r'\s*style="\s*"', '', fragment)
    return fragment.strip()

def obj_html(o, site, page, img):
    t = o['type']
    st = f"left:{o['x']:g}px;top:{o['y']:g}px;width:{o['w']:g}px;height:{o['h']:g}px;"
    if o.get('rot'): st += f"transform:rotate({o['rot']:g}deg);"
    if o.get('opacity', 1) < 1: st += f"opacity:{o['opacity']:g};"
    tag, attrs = 'div', ''
    L = o.get('link')
    if L and t not in ('nav', 'form'):
        href = '#'
        if L['type'] == 'page':
            pg = next((q for q in site['pages'] if q['id'] == L.get('target')), None); href = pg['file'] if pg else '#'
        elif L['type'] == 'url': href = L['target']; attrs += ' target="_blank" rel="noopener"'
        elif L['type'] == 'email': href = 'mailto:' + L['target']
        elif L['type'] == 'file': href = img(L['target']) if L['target'] in site.get('assets', {}) else '#'; attrs += ' target="_blank"'
        tag, attrs = 'a', f' href="{esc(href)}"' + attrs
    inner = ''
    if t in ('text', 'artistic', 'button'):
        st += text_css(o) + box_css(o)
        if t == 'text': st += f"padding:{o.get('pad', 8)}px;--pg:{o.get('pgap', .6)};"
        inner = clean_html(o.get('html', ''), site, img)
    elif t == 'shape':
        st += box_css(o)
        if o.get('shape') == 'ellipse': st += 'border-radius:50%;'
    elif t == 'line':
        pw = max(1, o.get('strokeW', 2)); w, h = o['w'], o['h']
        if h <= pw + 2: x1, y1, x2, y2 = 0, h / 2, w, h / 2
        elif w <= pw + 2: x1, y1, x2, y2 = w / 2, 0, w / 2, h
        elif o.get('flip'): x1, y1, x2, y2 = 0, h, w, 0
        else: x1, y1, x2, y2 = 0, 0, w, h
        da = {'dashed': f' stroke-dasharray="{pw * 4} {pw * 2}"', 'dotted': f' stroke-dasharray="{pw} {pw}"'}.get(o.get('dash'), '')
        inner = (f'<svg width="{w:g}" height="{h:g}" style="overflow:visible;display:block"><line x1="{x1:g}" y1="{y1:g}" x2="{x2:g}" y2="{y2:g}" '
                 f'stroke="{o.get("stroke")}" stroke-width="{pw}"{da}/></svg>')
    elif t == 'picture':
        st += box_css(o) + 'overflow:hidden;'
        fit = {'cover': 'cover', 'contain': 'contain', 'stretch': 'fill'}[o.get('fit', 'cover')]
        if o.get('src'): inner = f'<img src="{img(o["src"])}" alt="" style="object-fit:{fit}">'
        else: st += 'background:#dde2e5;'
    elif t == 'nav':
        st += text_css(o) + f"--na:{o.get('accent')};--nai:{o.get('accentInk', '#fff')};"
        # Editable item spacing: gap between items, and horizontal padding inside each item.
        st += f"gap:{int(o.get('gap', 6))}px;--nvpad:{int(o.get('pad', 14))}px;"
        if o.get('fill'): st += f"background:{o['fill']};"
        st += 'justify-content:' + {'center': 'center', 'right': 'flex-end'}.get(o.get('align'), 'flex-start') + ';'
        cls = f" nav-{o.get('style', 'pills')}" + (' v' if o.get('orient') == 'v' else '')
        parts = []
        for q, kids in nav_items(site, o):
            on = ' class="on"' if page and q['id'] == page['id'] or (page and page['id'] in [k['id'] for k in kids]) else ''
            sub = ''
            if kids:
                sub = '<div class="sub">' + ''.join(f'<a href="{esc(k["file"])}">{esc(k["title"])}</a>' for k in kids) + '</div>'
            parts.append(f'<div class="nv"><a href="{esc(q["file"])}"{on}>{esc(q["title"])}</a>{sub}</div>')
        return f'<nav class="obj obj-nav{cls}" style="{st}">' + ''.join(parts) + '</nav>'
    elif t == 'table':
        st += text_css(o) + f"--tb:{o.get('stroke')};--th:{o.get('head')};background:{o.get('fill') or '#fff'};"
        rows = ''.join('<tr>' + ''.join(f'<td>{c}</td>' for c in row) + '</tr>' for row in o.get('cells', []))
        inner = f'<table>{rows}</table>'
    elif t == 'form':
        st += text_css(o) + f"--na:{o.get('accent')};"
        fl = ''
        for i, fld in enumerate(o.get('fields', [])):
            big = any(k in fld.lower() for k in ('message', 'help', 'comment', 'enquiry', 'details'))
            nm = re.sub(r'[^a-z0-9]+', '_', fld.lower()).strip('_') or f'field{i}'
            ctl = f'<textarea name="{nm}"></textarea>' if big else f'<input name="{nm}" type="{"email" if "email" in fld.lower() else "text"}">'
            fl += f'<label>{esc(fld)}{ctl}</label>'
        return (f'<form class="obj obj-form" style="{st}" method="post" action="#" onsubmit="alert(\'Connect this form to a form handler on your web host.\');return false">'
                f'{fl}<button type="submit">{esc(o.get("submit", "Send"))}</button></form>')
    elif t == 'html':
        inner = o.get('code', '')
    elif t == 'share':
        st += text_css(dict(o, bold=True)) + 'display:flex;flex-wrap:wrap;align-items:center;' + f"gap:{o.get('gap', 8)}px;"
        rad = o.get('radius', 6); links = ''
        for nid in o.get('nets', []):
            if nid not in NET: continue
            _, label, col, _ = NET[nid]
            look = (f'border:1.5px solid {col};color:{col};background:transparent' if o.get('style') == 'outline' else f'background:{col};color:#fff')
            ext = '' if nid == 'email' else ' target="_blank" rel="noopener"'
            links += f'<a data-net="{nid}" style="{look};padding:9px 14px;border-radius:{rad}px;text-decoration:none;line-height:1"{ext}>{esc(label)}</a>'
        tpl = json.dumps({n[0]: n[3] for n in SHARE_NETS})
        script = ('<script>(function(g){var u=encodeURIComponent(location.href),t=encodeURIComponent(document.title),m=' + tpl +
                  ';g.querySelectorAll("a[data-net]").forEach(function(a){a.href=m[a.dataset.net].replace("{u}",u).replace("{t}",t)})})(document.currentScript.parentNode)</script>')
        return f'<div class="obj obj-share" style="{st}">{links}{script}</div>'
    elif t == 'gallery':
        st += box_css(o) + 'overflow:hidden;'
        fade = o.get('fade', .5)
        fit = {'cover': 'cover', 'contain': 'contain', 'stretch': 'fill'}.get(o.get('fit', 'cover'), 'cover')
        keys = [k for k in o.get('images', []) if k in site.get('assets', {})]
        inner = ''.join(f'<img src="{img(k)}" alt="" style="position:absolute;left:0;top:0;width:100%;height:100%;object-fit:{fit};'
                        f'opacity:{1 if i == 0 else 0};transition:opacity {fade}s">' for i, k in enumerate(keys))
        if len(keys) > 1:
            inner += ('<script>(function(g){var s=g.querySelectorAll("img"),i=0;setInterval(function(){s[i].style.opacity=0;'
                      f'i=(i+1)%s.length;s[i].style.opacity=1}},{int(o.get("interval", 5) * 1000)})}})(document.currentScript.parentNode)</script>')
    return f'<{tag} class="obj obj-{t}" style="{st}"{attrs}>{inner}</{tag}>'

def _page_text(page):
    """Plain text of a page's text objects (tags stripped, whitespace tidied)."""
    return re.sub(r'\s+', ' ', H.unescape(re.sub(r'<[^>]+>', ' ',
                  ' '.join(o.get('html', '') for o in page.get('objects', []) if o.get('type') == 'text')))).strip()

# Small stop-word set for deriving a focus keyword from page text.
_SEO_STOP = set('the a an and or but of to in on at for with from by as is are was were be been '
                'this that these those it its it\'s you your we our they their he she his her i me my '
                'not no do does did can could will would should may might must have has had about into '
                'over under more most some any all each if then than so such up out off down who whom '
                'which what when where why how here there page site also them then just like get got one '
                'two will can’t don’t'.split())

def _seo_strip_meta(body):
    """Strip the Google-Sites 'posted <date> by <name> [ updated … ]' byline that
    begins most of the imported news pages, so the auto description starts on the
    real article text."""
    b = re.sub(r'^\s*posted\b[^\]]*\]\s*', '', body, flags=re.I)          # posted … [ updated … ]
    b = re.sub(r'^\s*posted\b.*?\bby\b\s+\S+(?:\s+\S+){0,3}\s*', '', b, flags=re.I)  # posted … by Name
    b = re.sub(r'^\s*(contributed by|by)\s+\S+(?:\s+\S+){0,3}\s*', '', b, flags=re.I)
    return b.strip()

def _auto_seo_fields(title, body, site_name, keep_title=''):
    """Heuristic SEO (no AI, instant): compelling title, a 120–160 char meta
    description from the page's own text, and a focus keyword. keep_title lets a
    caller preserve an existing hand-written title."""
    from collections import Counter
    # Drop a leading repeat of the page heading first, then strip any byline, so
    # the description doesn't start by echoing the title or the 'posted … by …'
    # metadata (which sits just under the title in reading order).
    clean = body
    t = title.strip()
    if t and clean[:len(t)].lower() == t.lower():
        clean = clean[len(t):].lstrip(' -–—:·|.').strip()
    clean = _seo_strip_meta(clean)
    # Description: first ~155 chars, cut at a word boundary, tidy trailing punctuation.
    desc = clean[:300].strip()
    if len(clean) > 155:
        cut = desc[:155]
        sp = cut.rfind(' ')
        if sp > 110: cut = cut[:sp]
        desc = cut.rstrip(' ,;:-') + '…'
    else:
        desc = desc.rstrip()
    # SEO title: page title, plus " | Site" when it still fits in ~60 chars.
    seo_title = (keep_title or '').strip()
    if not seo_title:
        seo_title = title.strip()
        if site_name and len(seo_title) + len(site_name) + 3 <= 60 and site_name.lower() not in seo_title.lower():
            seo_title = f'{seo_title} | {site_name}'
    # Focus keyword: most salient content word (title words weighted up).
    words = re.findall(r"[a-zA-Z][a-zA-Z'\-]{3,}", f'{title} {title} {clean}'.lower())
    freq = Counter(w for w in words if w not in _SEO_STOP and "'" not in w)
    keyword = freq.most_common(1)[0][0] if freq else ''
    return {'title': seo_title, 'description': desc, 'keyword': keyword}

def _ai_seo_fields(key, title, body, site_name, timeout=40):
    """AI SEO via OpenAI chat (needs an OpenAI key). Returns the same dict shape
    as _auto_seo_fields, or raises on any network/parse error so the caller can
    fall back to the heuristic."""
    import urllib.request, json as _json, ssl
    ctx = ssl.create_default_context()
    sysmsg = ('You are an SEO assistant. Given a web page, reply with ONLY a JSON object with keys '
              '"title", "description", "keyword". title = a compelling SEO title under 60 characters. '
              'description = a meta description between 120 and 160 characters, plain prose, no quotes. '
              'keyword = the single best focus keyphrase (1-4 words). No commentary.')
    usermsg = f'Website name: {site_name}\nPage heading: {title}\nPage text:\n{_seo_strip_meta(body)[:2000]}'
    payload = _json.dumps({'model': 'gpt-4o-mini',
                           'messages': [{'role': 'system', 'content': sysmsg},
                                        {'role': 'user', 'content': usermsg}],
                           'temperature': 0.4,
                           'response_format': {'type': 'json_object'}}).encode()
    req = urllib.request.Request('https://api.openai.com/v1/chat/completions', data=payload,
                                 headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        out = _json.loads(r.read())
    obj = _json.loads(out['choices'][0]['message']['content'])
    return {'title': (obj.get('title') or '').strip(),
            'description': (obj.get('description') or '').strip(),
            'keyword': (obj.get('keyword') or '').strip()}

def seo_head(site, page, img):
    """The page's SEO <head> block: effective title + all meta/OG/Twitter/
    canonical/robots/JSON-LD tags. Returns (effective_title, head_html).
    Falls back to the auto word-derived description so empty SEO publishes
    byte-for-byte as before (bar the title now coming from here)."""
    sseo = site.get('seo', {}) or {}
    pseo = page.get('seo', {}) or {}
    base = (sseo.get('base_url') or '').strip().rstrip('/')
    # Effective title: page override, else "{title} | {site name}"
    title = (pseo.get('title') or '').strip() or f'{page["title"]} | {site["name"]}'
    # Description: override, else auto from page words (same rule as before)
    desc = (pseo.get('description') or '').strip()
    if not desc:
        words = _page_text(page)
        if len(words) > 155: words = words[:152].rsplit(' ', 1)[0] + '…'
        desc = words
    out = []
    if desc: out.append(f'<meta name="description" content="{esc(desc)}">')
    # Byte-for-byte guard: when NOTHING SEO-related is configured (no site seo,
    # no page seo), emit only the description meta exactly as the old code did,
    # so unconfigured sites publish identically.
    configured = bool(sseo) or bool(pseo)
    if not configured:
        head = '\n'.join(out)
        return title, (head + '\n' if head else '')
    # Absolute OG image (needs a base_url to be absolute; skip otherwise)
    ogkey = (pseo.get('og_image') or sseo.get('og_image') or '').strip()
    og_abs = ''
    if ogkey:
        if re.match(r'https?://', ogkey):
            og_abs = ogkey
        elif base and ogkey in site.get('assets', {}):
            og_abs = base + '/' + img(ogkey).lstrip('/')
    page_url = (base + '/' + page['file']) if base else ''
    # Open Graph
    out.append('<meta property="og:type" content="website">')
    out.append(f'<meta property="og:title" content="{esc(title)}">')
    if desc: out.append(f'<meta property="og:description" content="{esc(desc)}">')
    if page_url: out.append(f'<meta property="og:url" content="{esc(page_url)}">')
    if base and site.get('name'): out.append(f'<meta property="og:site_name" content="{esc(site["name"])}">')
    if og_abs: out.append(f'<meta property="og:image" content="{esc(og_abs)}">')
    # Twitter card
    out.append('<meta name="twitter:card" content="summary_large_image">')
    tw = (sseo.get('twitter_site') or '').strip()
    if tw:
        if not tw.startswith('@'): tw = '@' + tw
        out.append(f'<meta name="twitter:site" content="{esc(tw)}">')
    out.append(f'<meta name="twitter:title" content="{esc(title)}">')
    if desc: out.append(f'<meta name="twitter:description" content="{esc(desc)}">')
    if og_abs: out.append(f'<meta name="twitter:image" content="{esc(og_abs)}">')
    # Canonical: explicit override, else base_url + file
    canon = (pseo.get('canonical') or '').strip() or page_url
    if canon: out.append(f'<link rel="canonical" href="{esc(canon)}">')
    # robots noindex
    if pseo.get('noindex'): out.append('<meta name="robots" content="noindex,nofollow">')
    # JSON-LD WebSite + Organization (home page only, needs org_name)
    org = (sseo.get('org_name') or '').strip()
    if org and page is site['pages'][0]:
        ld = {'@context': 'https://schema.org', '@graph': []}
        if base:
            ld['@graph'].append({'@type': 'WebSite', 'name': site.get('name', ''), 'url': base + '/'})
        ld['@graph'].append({'@type': (sseo.get('org_type') or 'Organization').strip() or 'Organization',
                             'name': org, **({'url': base + '/'} if base else {})})
        out.append(f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>')
    head = '\n'.join(out)
    return title, (head + '\n' if head else '')

def page_html(site, page, img):
    m = next((x for x in site['masters'] if x['id'] == page['master']), site['masters'][0])
    objs = [o for o in page_objects(site, page) if not o.get('hidden')]
    fams = sorted({o.get('font') for o in objs if o.get('font') in GOOGLE})
    flink = ''
    if fams:
        q = '&'.join('family=' + f.replace(' ', '+') + ':ital,wght@0,400;0,700;1,400;1,700' for f in fams)
        flink = f'<link rel="preconnect" href="https://fonts.googleapis.com">\n<link rel="stylesheet" href="https://fonts.googleapis.com/css2?{q}&display=swap">\n'
    bg = page.get('bg') or m.get('bg') or site.get('bg') or '#fff'
    Hh = page.get('height') or site['height']
    body = '\n'.join(obj_html(o, site, page, img) for o in objs)
    # tidy: move each object's styling into the page's style block, keep the markup plain
    rules, n = [], [0]
    def lift(mm):
        n[0] += 1; rules.append(f'#o{n[0]}{{{mm.group(3)}}}')
        return f'<{mm.group(1)} id="o{n[0]}" class="{mm.group(2)}"'
    body = re.sub(r'<(div|a|nav|form) class="(obj [^"]*)" style="([^"]*)"', lift, body)
    body = re.sub(r'<a>(.*?)</a>', r'\1', body, flags=re.S)                      # links that lead nowhere
    body = re.sub(r'<span>(.*?)</span>', r'\1', body, flags=re.S)
    body = body.replace('<img src=', '<img loading="lazy" decoding="async" src=')
    # SEO head block (title + description/OG/Twitter/canonical/robots/JSON-LD).
    # seo_head preserves the old auto word-derived description as its fallback,
    # so an unconfigured site publishes the same meta description as before.
    seo_title, seo = seo_head(site, page, img)
    bgpic = f' url({img(site["bgimage"])}) top left repeat' if site.get('bgimage') in site.get('assets', {}) else ''
    # --- Responsive publish (opt-in via site['responsive']) ---------------
    # The design stays a fixed-width, absolutely-positioned page; responsive
    # mode makes that whole page SCALE to fit any screen (so phones show the
    # full design shrunk-to-fit instead of a zoomed-in slice needing side-
    # scroll). Static mode is unchanged, byte-for-byte, when the flag is off.
    responsive = bool(site.get('responsive'))
    if responsive:
        viewport = 'width=device-width, initial-scale=1'
        # .pf-wrap is a full-width band; .pf-page is the fixed design, scaled by
        # JS to ALWAYS fill the window width — shrinking on narrow screens and
        # growing on wide ones — and horizontally centred.
        css = (f'html,body{{margin:0}}\nbody{{background:{site.get("bg") or bg}{bgpic}}}\n'
               f'.pf-wrap{{width:100%;overflow-x:hidden}}\n'
               f'.pf-page{{width:{site["width"]}px;height:{Hh}px;background:{bg};'
               f'transform-origin:top left;margin:0 auto}}\n'
               + '\n'.join(rules))
        scale_js = (f'<script>(function(){{var W={site["width"]},p=document.querySelector(".pf-page"),'
                    f'w=document.querySelector(".pf-wrap");function fit(){{var vw=w.clientWidth,'
                    f's=vw/W;p.style.transform="scale("+s+")";w.style.height=(p.offsetHeight*s)+"px"}}'
                    f'window.addEventListener("resize",fit);fit();}})();</script>')
        return (f'<!doctype html>\n<html lang="en-GB">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="{viewport}">\n'
                f'<title>{esc(seo_title)}</title>\n{seo}<meta name="generator" content="{APP} {VERSION}">\n'
                f'{flink}<link rel="stylesheet" href="style.css">\n<style>\n{css}\n</style>\n</head>\n<body>\n'
                f'<div class="pf-wrap">\n<div class="pf-page">\n{body}\n</div>\n</div>\n{scale_js}\n</body>\n</html>\n')
    # --- Static publish (default, fixed width) ----------------------------
    css = (f'body{{background:{site.get("bg") or bg}{bgpic}}}\n.pf-page{{width:{site["width"]}px;height:{Hh}px;background:{bg}}}\n'
           + '\n'.join(rules))
    return (f'<!doctype html>\n<html lang="en-GB">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width={site["width"]}">\n'
            f'<title>{esc(seo_title)}</title>\n{seo}<meta name="generator" content="{APP} {VERSION}">\n'
            f'{flink}<link rel="stylesheet" href="style.css">\n<style>\n{css}\n</style>\n</head>\n<body>\n'
            f'<div class="pf-page">\n{body}\n</div>\n</body>\n</html>\n')

WEBSAFE_FONTS = {'arial', 'helvetica', 'helvetica neue', 'times new roman', 'times', 'georgia',
                 'courier new', 'courier', 'verdana', 'tahoma', 'trebuchet ms', 'segoe ui',
                 'sans-serif', 'serif', 'monospace', 'system-ui', 'ui-sans-serif'}

def _norm_fam(s):
    return re.sub(r'[^a-z0-9]', '', (s or '').lower())

def _fc_match(spec):
    """Resolve a fontconfig pattern to (family, file) via fc-match; None on failure."""
    try:
        out = subprocess.run(['fc-match', '-f', '%{family}|%{file}', spec],
                             capture_output=True, text=True, timeout=5).stdout
    except Exception:
        return None
    if '|' not in out:
        return None
    fam, path = out.split('|', 1)
    return fam.strip(), path.strip()

def font_faces(site, folder, write_if_changed, written):
    """Self-host every installed, non-web-safe font the site uses, so the page looks the
    same in a visitor's browser. Returns the @font-face CSS ('' if none). A font that
    isn't installed on this machine has no file to ship, so it is skipped (keeps its
    fallback) and recorded in font_faces.skipped. Google families keep their <link>."""
    fams = set()
    for cont in site.get('masters', []) + site.get('pages', []):
        for o in cont.get('objects', []):
            if isinstance(o, dict) and o.get('font'):
                fams.add(o['font'])
    faces, skipped = [], []
    websafe = {_norm_fam(w) for w in WEBSAFE_FONTS}
    for fam in sorted(fams):
        if _norm_fam(fam) in websafe or fam in GOOGLE:
            continue
        base = _fc_match(fam)
        if not base or _norm_fam(base[0]) != _norm_fam(fam):
            skipped.append(fam); continue          # not installed here — nothing to ship
        os.makedirs(os.path.join(folder, 'fonts'), exist_ok=True)
        seen = set()
        for weight, style, spec in (('400', 'normal', fam), ('700', 'normal', fam + ':bold'),
                                    ('400', 'italic', fam + ':italic'), ('700', 'italic', fam + ':bold:italic')):
            r = _fc_match(spec)
            if not r or _norm_fam(r[0]) != _norm_fam(fam) or r[1] in seen:
                continue                            # missing or faux variant — the browser synthesises it
            seen.add(r[1])
            ext = (os.path.splitext(r[1])[1].lstrip('.') or 'ttf').lower()
            fmt = {'ttf': 'truetype', 'otf': 'opentype', 'ttc': 'truetype',
                   'woff2': 'woff2', 'woff': 'woff'}.get(ext, 'truetype')
            safe = re.sub(r'[^A-Za-z0-9._-]+', '-', fam).strip('-') + '-' + weight + ('i' if style == 'italic' else '') + '.' + ext
            try:
                with open(r[1], 'rb') as fh: blob = fh.read()
            except OSError:
                continue
            write_if_changed(os.path.join(folder, 'fonts', safe), blob, binary=True)
            written.append('fonts/' + safe)
            faces.append("@font-face{font-family:'%s';font-weight:%s;font-style:%s;font-display:swap;"
                         "src:url('fonts/%s') format('%s');}" % (fam, weight, style, safe, fmt))
    font_faces.skipped = skipped
    return '\n'.join(faces)

def publish_site(site, folder):
    os.makedirs(folder, exist_ok=True)
    written, imgs = [], {}
    def img(key):
        if key in imgs: return imgs[key]
        src = site['assets'].get(key, '')
        mt = re.match(r'data:image/([a-z0-9+]+);base64,', src)
        orig = site.get('assetnames', {}).get(key)
        if mt:
            ext = {'jpeg': 'jpg', 'svg+xml': 'svg'}.get(mt.group(1), mt.group(1))
            sub = 'images'; base = re.sub(r'[^A-Za-z0-9._-]+', '-', os.path.splitext(orig)[0]).strip('-') if orig else key
            name = f'images/{base or key}.{ext}'
        else:
            sub = 'files'; name = 'files/' + re.sub(r'[^A-Za-z0-9._-]+', '-', orig or key)
        if name in imgs.values():
            stem, ext2 = os.path.splitext(name); name = f'{stem}-{key[:6]}{ext2}'
        os.makedirs(os.path.join(folder, sub), exist_ok=True)
        blob = base64.b64decode(src.split(',', 1)[1])
        dest = os.path.join(folder, name)
        try:
            with open(dest, 'rb') as fh: same = (fh.read() == blob)
        except FileNotFoundError:
            same = False
        if not same:
            with open(dest, 'wb') as fh: fh.write(blob)
        written.append(name); imgs[key] = name; return name
    # Incremental publish: only (re)write a file whose content has actually
    # changed. First publish writes everything; later ones touch only edits,
    # so re-uploading/syncing the folder transfers just the changes.
    def write_if_changed(path, text, binary=False):
        data = text if binary else text.encode('utf-8')
        try:
            with open(path, 'rb') as fh:
                if fh.read() == data: return False   # unchanged — leave it
        except FileNotFoundError:
            pass
        mode = 'wb'
        with open(path, mode) as fh: fh.write(data)
        return True

    changed_files = []
    faces = font_faces(site, folder, write_if_changed, written)
    css_path = os.path.join(folder, 'style.css')
    full_css = (faces + '\n' + PUBLISH_CSS) if faces else PUBLISH_CSS
    if write_if_changed(css_path, full_css): changed_files.append('style.css')
    written.append('style.css')
    pages_total = len(site['pages']); pages_changed = 0
    for p in site['pages']:
        fp = os.path.join(folder, p['file'])
        if write_if_changed(fp, page_html(site, p, img)):
            changed_files.append(p['file']); pages_changed += 1
        written.append(p['file'])
    # --- SEO site files: sitemap.xml (only with a base URL) + robots.txt -----
    base = ((site.get('seo') or {}).get('base_url') or '').strip().rstrip('/')
    if base:
        urls = ''.join(f'  <url><loc>{esc(base + "/" + p["file"])}</loc></url>\n' for p in site['pages'])
        sm = ('<?xml version="1.0" encoding="UTF-8"?>\n'
              '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + urls + '</urlset>\n')
        if write_if_changed(os.path.join(folder, 'sitemap.xml'), sm): changed_files.append('sitemap.xml')
        written.append('sitemap.xml')
    robots = 'User-agent: *\nAllow: /\n' + (f'Sitemap: {base}/sitemap.xml\n' if base else '')
    if write_if_changed(os.path.join(folder, 'robots.txt'), robots): changed_files.append('robots.txt')
    written.append('robots.txt')
    publish_site.last_stats = {'pages_total': pages_total, 'pages_changed': pages_changed,
                               'changed_files': changed_files}
    return written

# ----------------------------------------------------------------------------
# Importing an existing website folder
# (Google Sites downloads, and ordinary HTML sites as a fallback)
# ----------------------------------------------------------------------------
from urllib.parse import unquote, urlsplit, parse_qs

FONT_SIZES = {'1': 10, '2': 13, '3': 16, '4': 18, '5': 24, '6': 32, '7': 48}
CSS_SIZES = {'xx-small': 9, 'x-small': 10, 'small': 13, 'medium': 16, 'large': 18, 'x-large': 24, 'xx-large': 32, 'smaller': 12, 'larger': 18}
SKIP_FILE = re.compile(r'^(google[0-9a-f]{6,}\.html|dewslider\.html|.*\.sitemap\.xml)$', re.I)
SKIP_DIRS = {'pagetemplates', 'system', '_files', 'css', 'js'}
ICON_WORDS = [('linkedin', 'LinkedIn'), ('facebook', 'Facebook'), ('twitter', 'Twitter'), ('youtube', 'YouTube'),
              ('google', 'Google'), ('rss', 'RSS'), ('feed', 'RSS'), ('mail', 'Email'), ('windows', 'Windows')]
MIME = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png', 'gif': 'image/gif', 'webp': 'image/webp',
        'svg': 'image/svg+xml', 'pdf': 'application/pdf', 'zip': 'application/zip', 'doc': 'application/msword',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'mp3': 'audio/mpeg', 'mp4': 'video/mp4',
        'bmp': 'image/bmp', 'tif': 'image/tiff', 'tiff': 'image/tiff', 'ico': 'image/x-icon'}

def css_px(v):
    v = (v or '').strip().lower().replace('!important', '').strip()
    if v in CSS_SIZES: return CSS_SIZES[v]
    m = re.match(r'^([\d.]+)\s*(px|pt|em|rem|%)?$', v)
    if not m: return None
    n = float(m.group(1)); u = m.group(2) or 'px'
    return max(6, round({'px': n, 'pt': n * 4 / 3, 'em': n * 16, 'rem': n * 16, '%': n * .16}[u]))

def parse_style(s):
    d = {}
    for part in (s or '').split(';'):
        if ':' in part:
            k, v = part.split(':', 1); d[k.strip().lower()] = v.strip()
    return d

def norm_color(v):
    v = (v or '').strip().lower()
    m = re.match(r'rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)', v)
    if m: return '#%02x%02x%02x' % tuple(min(255, int(x)) for x in m.groups())
    if re.match(r'^#[0-9a-f]{3}([0-9a-f]{3})?$', v): return v
    if re.match(r'^[a-z]+$', v) and v not in ('inherit', 'initial', 'transparent', 'currentcolor', 'none'): return v
    return None


class HtmlToBlocks:
    """Turns flowing HTML into blocks WEBcreator can lay out:
    ('text', html) · ('img', key, w, h, link, align) · ('hr',) · ('html', code, w, h)."""
    INLINE = {'span', 'font', 'b', 'strong', 'i', 'em', 'u', 'a', 'sub', 'sup', 'small', 'big', 'abbr', 'code', 'cite',
              'q', 's', 'strike', 'mark', 'label', 'nobr', 'wbr'}
    SKIP = {'script', 'style', 'noscript', 'object', 'embed', 'button', 'input', 'select', 'textarea', 'svg', 'head',
            'title', 'meta', 'link', 'map', 'area', 'canvas', 'audio', 'video', 'param'}

    def __init__(self, imgfn, linkfn):
        self.imgfn, self.linkfn = imgfn, linkfn
        self.blocks, self.paras, self.cur, self.stack, self.links = [], [], [], [], []
        self.align = None; self.ol = []

    def _open(self):
        if not self.cur: self.cur.append(''.join(o for o, _ in self.stack))

    def text(self, s):
        s = re.sub(r'\s+', ' ', s)
        if not self.cur:
            s = s.lstrip()
            if not s: return
        self._open(); self.cur.append(H.escape(s, quote=False))

    def inline(self, html):
        self._open(); self.cur.append(html)

    def flush_para(self):
        if not self.cur: return
        self.cur.append(''.join(c for _, c in reversed(self.stack)))
        h = ''.join(self.cur); self.cur = []
        h = re.sub(r'(?:\s*<br>)+\s*((?:</[a-z]+>\s*)*)$', r'\1', h)
        visible = re.sub(r'<[^>]+>|&nbsp;|\s', '', h)
        self.paras.append((self.align, h if visible else ''))

    def flush_text(self):
        self.flush_para()
        out, blank = [], True
        for al, h in self.paras:
            if not h:
                if not blank: out.append('<p>&nbsp;</p>')
                blank = True; continue
            blank = False
            out.append(f'<p align="{al}">{h}</p>' if al in ('center', 'right', 'justify') else f'<p>{h}</p>')
        while out and out[-1] == '<p>&nbsp;</p>': out.pop()
        if out: self.blocks.append(('text', ''.join(out)))
        self.paras = []

    def wrapper(self, el):
        st = parse_style(el.get('style')); css = []
        name = el.name; size = None
        if name == 'font' and el.get('size'): size = FONT_SIZES.get(el.get('size').strip().lstrip('+'))
        if 'font-size' in st: size = css_px(st['font-size']) or size
        if name == 'small': size = size or 12
        if name == 'big': size = size or 19
        if size: css.append(f'font-size:{size}px')
        col = norm_color(st.get('color') or (el.get('color') if name == 'font' else None))
        if col: css.append(f'color:{col}')
        fw = st.get('font-weight', '')
        if name in ('b', 'strong') or fw in ('bold', 'bolder', '600', '700', '800', '900'): css.append('font-weight:700')
        elif fw in ('normal', '400'): css.append('font-weight:400')
        if name in ('i', 'em', 'cite') or st.get('font-style') == 'italic': css.append('font-style:italic')
        if name == 'u' or 'underline' in st.get('text-decoration', ''): css.append('text-decoration:underline')
        if name in ('s', 'strike') or 'line-through' in st.get('text-decoration', ''): css.append('text-decoration:line-through')
        if name == 'sub': css.append('vertical-align:sub')
        if name == 'sup': css.append('vertical-align:super')
        return css

    def walk(self, el):
        from bs4 import NavigableString, Comment
        for ch in el.children:
            if isinstance(ch, Comment): continue
            if isinstance(ch, NavigableString): self.text(str(ch)); continue
            self.element(ch)

    def element(self, el):
        n = el.name
        st = parse_style(el.get('style'))
        if n in self.SKIP or st.get('display') == 'none': return
        if n == 'br': self.inline('<br>'); return
        if n == 'img': return self.image(el)
        if n == 'hr':
            self.flush_text(); self.blocks.append(('hr',)); return
        if n == 'iframe': return self.iframe(el)
        if n in self.INLINE:
            pushed = 0
            if n == 'a':
                href, link = self.linkfn(el.get('href'))
                self.links.append(link)
                if href:
                    self.stack.append((f'<a href="{H.escape(href)}">', '</a>')); pushed += 1
                    if self.cur: self.cur.append(self.stack[-1][0])
            css = self.wrapper(el)
            if css:
                self.stack.append((f'<span style="{";".join(css)}">', '</span>')); pushed += 1
                if self.cur: self.cur.append(self.stack[-1][0])
            self.walk(el)
            for _ in range(pushed):
                o, c = self.stack.pop()
                if self.cur: self.cur.append(c)
            if n == 'a': self.links.pop()
            return
        # block-level element
        self.flush_para()
        saved = self.align
        al = (st.get('text-align') or el.get('align') or '').lower()
        if al in ('left', 'center', 'right', 'justify'): self.align = None if al == 'left' else al
        if n == 'center': self.align = 'center'
        css = self.wrapper(el)
        hsize = {'h1': 32, 'h2': 26, 'h3': 21, 'h4': 18, 'h5': 16, 'h6': 14}.get(n)
        if hsize:
            css = [c for c in css if not c.startswith('font-size')] + [f'font-size:{hsize}px', 'font-weight:700']
        pushed = 0
        if css: self.stack.append((f'<span style="{";".join(css)}">', '</span>')); pushed = 1
        if n in ('ol', 'ul'): self.ol.append(0 if n == 'ol' else None)
        if n == 'li':
            if self.ol and self.ol[-1] is not None:
                self.ol[-1] += 1; self.text(f'{self.ol[-1]}. ')
            else: self.text('• ')
        if n == 'blockquote': self.stack.append(('<span style="font-style:italic">', '</span>')); pushed += 1
        self.walk(el)
        self.flush_para()
        if n in ('ol', 'ul'): self.ol.pop()
        for _ in range(pushed): self.stack.pop()
        if hsize: self.paras.append((None, ''))
        self.align = saved

    def image(self, el):
        key, w, h = self.imgfn(el.get('src'))
        st = parse_style(el.get('style'))
        aw = css_px(st.get('width')) or (int(el['width']) if (el.get('width') or '').isdigit() else None)
        ah = css_px(st.get('height')) or (int(el['height']) if (el.get('height') or '').isdigit() else None)
        if aw and ah: w, h = aw, ah
        elif aw and w and h: w, h = aw, round(h * aw / w)
        elif ah and w and h: w, h = round(w * ah / h), ah
        w, h = w or aw or 320, h or ah or 220
        link = next((l for l in reversed(self.links) if l), None)
        if w <= 72 and h <= 72:
            src = (el.get('src') or '').lower()
            label = next((lbl for k, lbl in ICON_WORDS if k in src), None) or (el.get('alt') or '').strip()
            if link and label: self.text(f' {label} ')
            return
        self.flush_text()
        self.blocks.append(('img', key, w, h, link, self.align))

    def iframe(self, el):
        src = el.get('src') or ''
        if 'gadgets/ifr' in src:
            q = parse_qs(urlsplit(src).fragment)
            src = (q.get('up_iframeURL') or [''])[0]
        if not src.startswith(('http://', 'https://', '//')): return
        w = int(el['width']) if (el.get('width') or '').isdigit() else 560
        h = int(el['height']) if (el.get('height') or '').isdigit() else 315
        self.flush_text()
        self.blocks.append(('html', f'<iframe src="{H.escape(src)}" width="{w}" height="{h}" style="border:0" allowfullscreen></iframe>', w, h))

    def convert(self, root):
        self.walk(root); self.flush_text(); return self.blocks


def import_site_folder(folder, progress=None, render=None):
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        raise RuntimeError('Importing needs Beautiful Soup.\nInstall it with:\n'
                           '  Arch/CachyOS:        sudo pacman -S --needed python-beautifulsoup4\n'
                           '  Debian/Ubuntu/Mint:  sudo apt install python3-bs4\n'
                           '  Fedora/openSUSE:     sudo dnf install python3-beautifulsoup4  (zypper on openSUSE)')
    folder = os.path.abspath(folder)
    paths = []
    for dp, dns, fns in os.walk(folder):
        dns[:] = sorted(d for d in dns if d.lower() not in SKIP_DIRS and not d.startswith('.'))
        for f in sorted(fns):
            if f.lower().endswith(('.html', '.htm')) and not SKIP_FILE.match(f): paths.append(os.path.join(dp, f))
    if not paths: raise RuntimeError('No web pages (.html files) were found in that folder.')

    def read(p):
        with open(p, 'rb') as fh: return BeautifulSoup(fh.read(), 'html.parser')

    def tick(i, n, msg):
        if progress and progress(i, n, msg) is False: raise RuntimeError('Import cancelled.')

    # first pass: titles and structure
    info = {}
    for i, p in enumerate(paths):
        tick(i, len(paths) * 2, f'Reading {os.path.relpath(p, folder)}')
        soup = read(p)
        main = soup.find(id='sites-canvas-main-content') or soup.find('main') or soup.find(id='content') or soup.body
        if main is None: continue
        pt = soup.find(id='sites-page-title')
        title = pt.get_text(' ', strip=True) if pt else ''
        full = soup.title.get_text(' ', strip=True) if soup.title else ''
        if not title: title = full.rsplit(' - ', 1)[0] if ' - ' in full else full
        if not title:
            h1 = soup.find('h1'); title = h1.get_text(' ', strip=True) if h1 else os.path.splitext(os.path.basename(p))[0]
        title = re.sub(r'\s+', ' ', title).strip()
        if not main.get_text(strip=True) and not main.find('img') and title.lower() not in ('home', 'index'): continue
        info[p] = dict(title=title, full=re.sub(r'\s+', ' ', full), soup=soup, main=main)
    if not info: raise RuntimeError('No pages with content were found in that folder.')

    def rel(src, href):
        path = unquote(urlsplit(href or '').path)
        if not path: return None
        return os.path.normpath(os.path.join(os.path.dirname(src), path))

    suffixes = [d['full'].rsplit(' - ', 1)[1] for d in info.values() if ' - ' in d['full']]
    name = max(set(suffixes), key=suffixes.count) if suffixes else os.path.basename(folder)
    home = next((p for p in (os.path.join(folder, 'home.html'), os.path.join(folder, 'index.html'))
                 if p in info and info[p]['title'].lower() != 'index'), None) \
        or next((p for p, d in info.items() if d['title'].lower() == 'home'), None) or next(iter(info))
    hs = info[home]['soup']
    top_nav = [rel(home, a.get('href')) for a in hs.select('.sites-header-nav a, #sites-chrome-header-horizontal-nav-container a') if a.get('href')]
    side_nav = [rel(home, a.get('href')) for a in hs.select('#sites-chrome-sidebar-left .sites-navigation a, #sites-chrome-sidebar-left .sites-sidebar-nav a') if a.get('href')]
    if not top_nav and not side_nav:
        nav_el = hs.find('nav')
        if nav_el: top_nav = [rel(home, a.get('href')) for a in nav_el.find_all('a', href=True)]
    top_nav = list(dict.fromkeys(p for p in top_nav if p in info))
    side_nav = list(dict.fromkeys(p for p in side_nav if p in info))
    logo_img = hs.select_one('#sites-header-title img, #logo-img-id')
    logo_src = logo_img.get('src') if logo_img else None

    # page order: menu pages first, each followed by its own sub-pages
    def parent_of(p):
        cand = os.path.dirname(p) + '.html'
        return cand if cand in info else None
    children = {p: [] for p in info}
    for p in info:
        par = parent_of(p)
        if par: children[par].append(p)
    order, placed = [], set()
    def place(p, level, nav):
        if p not in placed: order.append((p, level, nav)); placed.add(p)
    def place_sub(p):
        for c in sorted(children[p], key=lambda c: info[c]['title'].lower()):
            if c not in placed and c not in top_nav and c not in side_nav:
                place(c, 1, False); place_sub(c)
    for p in dict.fromkeys([home] + top_nav + side_nav):
        place(p, 0, True)
        if p != home: place_sub(p)
    for p in info:
        if p not in placed:
            par = parent_of(p)
            place(p, 1 if par and par in placed and par != home else 0, False); place_sub(p)

    s = base_site(name, width=960, height=900, bg='#eef1f4',
                  palette=['#3d85c6', '#1f4e79', '#eef1f4', '#ffffff', '#222222', '#e69138'])
    s['pages'] = []; s['assetnames'] = {}
    pid, used = {}, set()
    for p, level, nav in order:
        if p == home: fn = 'index.html'
        else:
            stem = re.sub(r'^home[/\\]', '', os.path.splitext(os.path.relpath(p, folder))[0])
            fn = slug(stem.replace(os.sep, '-'), used | {'index.html'})
        used.add(fn)
        pg = add_page(s, info[p]['title'], level, file=fn); pg['nav'] = nav; pid[p] = pg['id']

    file_cache = {}
    def add_file(path):
        if path in file_cache: return file_cache[path]
        try:
            with open(path, 'rb') as fh: data = fh.read()
        except OSError:
            file_cache[path] = None; return None
        ext = os.path.splitext(path)[1].lower().lstrip('.')
        key = add_asset(s, f'data:{MIME.get(ext, "application/octet-stream")};base64,' + base64.b64encode(data).decode())
        s['assetnames'][key] = os.path.basename(path); file_cache[path] = key; return key

    img_cache, missing = {}, set()
    def imgfn_for(src_page):
        def imgfn(src):
            if not src or src.startswith('data:') or re.match(r'^(https?:)?//', src): return None, 0, 0
            path = rel(src_page, src)
            if path in img_cache: return img_cache[path]
            res = (None, 0, 0)
            if path and os.path.isfile(path):
                from PySide6.QtGui import QImageReader
                sz = QImageReader(path).size()
                res = (add_file(path), sz.width() if sz.isValid() else 0, sz.height() if sz.isValid() else 0)
            else: missing.add(os.path.relpath(path, folder) if path else src)
            img_cache[path] = res; return res
        return imgfn

    def linkfn_for(src_page):
        def linkfn(href):
            if not href: return None, None
            href = href.strip()
            if href.startswith('#') or href.lower().startswith('javascript:'): return None, None
            if href.lower().startswith('mailto:'): return href, {'type': 'email', 'target': href[7:].split('?')[0]}
            if href.startswith('//'): href = 'https:' + href
            if re.match(r'^[a-z][a-z0-9+.-]*:', href, re.I): return href, {'type': 'url', 'target': href}
            path = rel(src_page, href)
            if not path: return None, None
            if path in pid: return 'wcpage:' + pid[path], {'type': 'page', 'target': pid[path]}
            if os.path.isfile(path):
                key = add_file(path)
                if key: return 'wcfile:' + key, {'type': 'file', 'target': key}
            return None, None
        return linkfn

    if render:
        layout_rendered(s, order, info, pid, home, imgfn_for, linkfn_for, render, lambda i, msg: tick(len(paths) + i * len(paths) // max(1, len(order)), len(paths) * 2, msg))
        s['_import_missing'] = sorted(missing)
        return s

    # master page laid out like the original: logo, top menu, side menu
    m = s['masters'][0]; m['bg'] = '#ffffff'
    y = 16
    key, lw, lh = imgfn_for(home)(logo_src) if logo_src else (None, 0, 0)
    if key and lw and lh:
        sc = min(1, 928 / lw, 220 / lh)
        m['objects'].append(mk('picture', 16, y, round(lw * sc), round(lh * sc), src=key, fit='contain',
                               link={'type': 'page', 'target': pid[home]}))
        y += round(lh * sc) + 12
    else:
        m['objects'].append(mk('artistic', 24, y + 8, 700, 48, html=f'<p>{H.escape(name)}</p>', size=34, color='#1f4e79'))
        y += 72
    if top_nav:
        ids = [pid[home]] + [pid[p] for p in top_nav if p != home]
        titles = [info[home]['title']] + [info[p]['title'] for p in top_nav if p != home]
        size, rows = 14, 1
        for size in (14, 13, 12):
            fm = QFontMetrics(qfont(dict(font=SANS, size=size)))
            if sum(fm.horizontalAdvance(t) + 28 for t in titles) + 6 * (len(titles) - 1) <= 928: break
        else:
            fm = QFontMetrics(qfont(dict(font=SANS, size=size))); rw, rows = 0, 1
            for t in titles:
                wi = fm.horizontalAdvance(t) + 28
                if rw and rw + 6 + wi > 928: rows += 1; rw = 0
                rw += (6 if rw else 0) + wi
        nh = rows * (fm.height() + 16) + (rows - 1) * 6
        m['objects'].append(mk('nav', 16, y, 928, max(40, nh), style='tabs', size=size, color='#1f4e79', accent='#3d85c6', pages=ids))
        y += max(40, nh) + 12
    content_x, content_w, side_bottom = 24, 912, y
    if side_nav:
        ids = [pid[p] for p in side_nav]
        nh = len(ids) * (QFontMetrics(qfont(dict(font=SANS, size=13))).height() + 22)
        m['objects'].append(mk('shape', 16, y, 196, nh + 24, fill='#eef1f4', radius=6))
        m['objects'].append(mk('nav', 28, y + 12, 172, nh, style='pills', orient='v', size=13, color='#1f4e79', accent='#3d85c6', pages=ids))
        content_x, content_w, side_bottom = 236, 700, y + nh + 40
    top = y + 8

    for i, (p, level, nav) in enumerate(order):
        tick(len(paths) + i * len(paths) // max(1, len(order)), len(paths) * 2, f'Laying out “{info[p]["title"]}”')
        pg = next(q for q in s['pages'] if q['id'] == pid[p])
        objs = pg['objects']; cy = top
        objs.append(mk('artistic', content_x, cy, content_w, 40, html=f'<p>{H.escape(info[p]["title"])}</p>', size=28, color='#3d85c6', bold=False))
        cy += 52
        for b in HtmlToBlocks(imgfn_for(p), linkfn_for(p)).convert(info[p]['main']):
            if b[0] == 'text':
                o = mk('text', content_x, cy, content_w, 40, html=b[1], size=15, color='#222222', lh=1.4, pad=0, pgap=0)
                o['h'] = max(20, math.ceil(make_doc(o).size().height()) + 6)
                objs.append(o); cy += o['h'] + 12
            elif b[0] == 'img':
                _, key, w, h, link, al = b
                if w > content_w: w, h = content_w, round(h * content_w / w)
                x = content_x + {'center': (content_w - w) // 2, 'right': content_w - w}.get(al, 0)
                objs.append(mk('picture', x, cy, w, h, src=key, fit='contain', link=link)); cy += h + 14
            elif b[0] == 'hr':
                objs.append(mk('line', content_x, cy + 4, content_w, 2, stroke='#c9d1d6', strokeW=1)); cy += 18
            elif b[0] == 'html':
                _, code, w, h = b
                w = min(w, content_w); objs.append(mk('html', content_x, cy, w, h, code=code)); cy += h + 14
        pg['height'] = max(700, cy + 60, side_bottom + 40)
    s['_import_missing'] = sorted(missing)
    return s


# --- Faithful import: lay pages out exactly where a browser draws them ---------

CAPTURE_JS = r"""(function () {
  // Records the rendered layout of a page: coloured boxes, pictures, embedded frames
  // and runs of text, with positions relative to the page's main wrapper.
  const root = document.getElementById('sites-chrome-everything') || document.body;
  const R = root.getBoundingClientRect();
  const sx = window.scrollX, sy = window.scrollY;
  const ox = R.left + sx, oy = R.top + sy;
  const EXCL = '#sites-chrome-adminfooter-container, .sites-adminfooter, #sites-canvas-bottom-panel, #sites-chrome-onebar-footer, #sites-chrome-main-wrapper-top-row script';
  const excluded = new Set(document.querySelectorAll(EXCL));
  function isExcluded(el) {
    for (let e = el; e; e = e.parentElement) if (excluded.has(e)) return true;
    return false;
  }
  function vis(el) {
    const cs = getComputedStyle(el);
    return cs.display !== 'none' && cs.visibility !== 'hidden' && parseFloat(cs.opacity || '1') > 0.05;
  }
  function visDeep(el) {
    for (let e = el; e && e !== document.documentElement; e = e.parentElement) if (!vis(e)) return false;
    return true;
  }
  function box(r) {
    return { x: Math.round(r.left + sx - ox), y: Math.round(r.top + sy - oy), w: Math.round(r.width), h: Math.round(r.height) };
  }
  const where = el => (el.closest('#sites-canvas') ? 'page' : 'master');
  const out = { width: Math.round(R.width), height: Math.round(Math.max(root.scrollHeight, R.height)),
                bodyBg: getComputedStyle(document.body).backgroundColor, rootBg: getComputedStyle(root).backgroundColor,
                items: [] };
  const cvEl = document.getElementById('sites-canvas') || document.querySelector('main') || root;
  out.canvas = box(cvEl.getBoundingClientRect());
  const bgOf = el => { const m = /url\(["']?([^"')]+)["']?\)/.exec(getComputedStyle(el).backgroundImage || ''); return m ? m[1] : ''; };
  out.bodyImg = bgOf(document.body) || bgOf(document.documentElement) || bgOf(root);

  // coloured boxes
  for (const el of root.querySelectorAll('*')) {
    if (isExcluded(el) || !visDeep(el)) continue;
    const cs = getComputedStyle(el);
    const bg = cs.backgroundColor;
    const bw = parseFloat(cs.borderTopWidth) || 0;
    const hasBg = bg && bg !== 'rgba(0, 0, 0, 0)' && bg !== 'transparent';
    const hasBorder = bw > 0 && cs.borderTopStyle !== 'none' && cs.borderTopColor !== 'rgba(0, 0, 0, 0)';
    if (!hasBg && !hasBorder) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 6 || r.height < 2) continue;
    if (el.tagName === 'A' || el.tagName === 'IMG' || el.tagName === 'SPAN' || el.tagName === 'FONT') continue;
    out.items.push(Object.assign({ kind: 'box', where: where(el), bg: hasBg ? bg : '', border: hasBorder ? cs.borderTopColor : '',
      bw: hasBorder ? bw : 0, radius: parseFloat(cs.borderTopLeftRadius) || 0, tag: el.tagName }, box(r)));
  }

  // pictures
  for (const img of root.querySelectorAll('img')) {
    if (isExcluded(img) || !visDeep(img)) continue;
    const r = img.getBoundingClientRect();
    if (r.width < 3 || r.height < 3) continue;
    const a = img.closest('a');
    out.items.push(Object.assign({ kind: 'img', where: where(img), src: img.getAttribute('src') || '',
      href: a ? a.getAttribute('href') : null, alt: img.getAttribute('alt') || '',
      nw: img.naturalWidth, nh: img.naturalHeight }, box(r)));
  }

  // embedded frames
  for (const f of root.querySelectorAll('iframe')) {
    if (isExcluded(f) || !visDeep(f)) continue;
    const r = f.getBoundingClientRect();
    if (r.width < 20 || r.height < 20) continue;
    out.items.push(Object.assign({ kind: 'iframe', where: where(f), src: f.getAttribute('src') || '' }, box(r)));
  }

  // runs of text
  const BLOCK = new Set(['block', 'table-cell', 'list-item', 'table', 'flex', 'grid', 'table-row', 'table-caption',
                         'table-row-group', 'flow-root', 'inline-block', 'inline-table']);
  const isBlockEl = el => BLOCK.has(getComputedStyle(el).display) || el.tagName === 'TABLE';
  function hasBlockDesc(el) {
    for (const d of el.querySelectorAll('*')) if (isBlockEl(d) && vis(d)) return true;
    return false;
  }
  function inlineNode(n) {
    if (n.nodeType === 3) return true;
    if (n.nodeType !== 1) return false;
    if (['SCRIPT', 'STYLE', 'NOSCRIPT', 'IFRAME'].includes(n.tagName)) return false;
    if (!vis(n)) return false;
    return !isBlockEl(n) && !hasBlockDesc(n);
  }
  const pxs = v => Math.round(parseFloat(v));
  function styleDiff(cs, base) {
    const d = [];
    if (pxs(cs.fontSize) !== base.size) d.push('font-size:' + pxs(cs.fontSize) + 'px');
    if (cs.color !== base.color) d.push('color:' + cs.color);
    const bold = parseInt(cs.fontWeight) >= 600;
    if (bold !== base.bold) d.push('font-weight:' + (bold ? 700 : 400));
    const it = cs.fontStyle === 'italic';
    if (it !== base.italic) d.push('font-style:' + (it ? 'italic' : 'normal'));
    return d;
  }
  function decorated(el) {
    for (let e = el; e; e = e.parentElement) {
      const t = getComputedStyle(e).textDecorationLine || '';
      if (t.includes('underline')) return true;
      if (isBlockEl(e)) break;
    }
    return false;
  }
  const esc = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  function ser(n, base) {
    if (n.nodeType === 3) {
      const t = n.textContent.replace(/\s+/g, ' ');
      if (!t) return '';
      const p = n.parentElement, cs = getComputedStyle(p);
      const d = styleDiff(cs, base);
      if (decorated(p) && !p.closest('a')) d.push('text-decoration:underline');
      return d.length ? '<span style="' + d.join(';') + '">' + esc(t) + '</span>' : esc(t);
    }
    if (n.nodeType !== 1 || !vis(n)) return '';
    const tag = n.tagName;
    if (tag === 'BR') return '<br>';
    if (tag === 'IMG') {
      const r = n.getBoundingClientRect();
      if (r.width <= 72 && r.height <= 72 && n.closest('a')) {
        const s = (n.getAttribute('src') || '').toLowerCase();
        const words = [['linkedin', 'LinkedIn'], ['facebook', 'Facebook'], ['twitter', 'Twitter'], ['youtube', 'YouTube'],
                       ['google', 'Google+'], ['rss', 'RSS'], ['feed', 'RSS'], ['mail', 'Email']];
        const w = words.find(x => s.includes(x[0]));
        return w ? ' ' + w[1] + ' ' : '';
      }
      return '';
    }
    let inner = '';
    for (const c of n.childNodes) inner += ser(c, base);
    if (tag === 'A' && n.getAttribute('href')) return '<a href="' + esc(n.getAttribute('href')) + '">' + inner + '</a>';
    return inner;
  }
  function runRect(nodes) {
    const rg = document.createRange();
    rg.setStartBefore(nodes[0]); rg.setEndAfter(nodes[nodes.length - 1]);
    let L = 1e9, T = 1e9, Rr = -1e9, B = -1e9;
    for (const q of rg.getClientRects()) {
      if (q.width < 1 || q.height < 1) continue;
      L = Math.min(L, q.left); T = Math.min(T, q.top); Rr = Math.max(Rr, q.right); B = Math.max(B, q.bottom);
    }
    if (L > Rr) return null;
    return { left: L, top: T, width: Rr - L, height: B - T };
  }
  const containers = [root, ...root.querySelectorAll('*')].filter(el =>
    !isExcluded(el) && visDeep(el) && !['SCRIPT', 'STYLE', 'NOSCRIPT', 'IFRAME', 'SELECT', 'TEXTAREA', 'BUTTON'].includes(el.tagName) &&
    (isBlockEl(el) || hasBlockDesc(el)));
  for (const el of containers) {
    const cs = getComputedStyle(el);
    const base = { size: pxs(cs.fontSize), color: cs.color, bold: parseInt(cs.fontWeight) >= 600, italic: cs.fontStyle === 'italic' };
    let run = [];
    const flush = () => {
      const nodes = run; run = [];
      if (!nodes.length) return;
      const text = nodes.map(n => n.textContent).join('').trim();
      const imgOnly = !text;
      if (imgOnly) return;
      const r = runRect(nodes);
      if (!r || r.width < 1) return;
      let html = nodes.map(n => ser(n, base)).join('').trim().replace(/^(<br>\s*)+|(\s*<br>)+$/g, '');
      if (!html) return;
      const lh = cs.lineHeight === 'normal' ? 'normal' : Math.round(parseFloat(cs.lineHeight) / base.size * 100) / 100;
      const blockW = el.getBoundingClientRect().width;
      out.items.push(Object.assign({ kind: 'text', where: where(el), html, size: base.size, color: cs.color, bold: base.bold,
        italic: base.italic, family: cs.fontFamily, align: cs.textAlign, lh, blockW: Math.round(blockW),
        blockX: Math.round(el.getBoundingClientRect().left + sx - ox) }, box(r)));
    };
    for (const c of el.childNodes) {
      if (inlineNode(c)) run.push(c);
      else flush();
    }
    flush();
  }

  // menus
  const nav = sel => [...document.querySelectorAll(sel)].filter(a => visDeep(a)).map(a => {
    const r = a.getBoundingClientRect(), cs = getComputedStyle(a);
    return Object.assign({ href: a.getAttribute('href'), text: a.textContent.trim().replace(/\s+/g, ' '), size: pxs(cs.fontSize),
      color: cs.color, family: cs.fontFamily, bold: parseInt(cs.fontWeight) >= 600 }, box(r));
  });
  out.topnav = nav('.sites-header-nav a, #sites-chrome-header-horizontal-nav-container a');
  out.sidenav = nav('#sites-chrome-sidebar-left .sites-navigation a, #sites-chrome-sidebar-left .sites-sidebar-nav a');
  return JSON.stringify(out);
})();
"""

def css_hex(v):
    if not v: return ''
    m = re.match(r'rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+))?', v)
    if m:
        if m.group(4) is not None and float(m.group(4)) < .05: return ''
        return '#%02x%02x%02x' % tuple(int(x) for x in m.groups()[:3])
    return v if v.startswith('#') else ''

def font_family(css):
    first = (css or '').split(',')[0].strip().strip('"\'').lower()
    table = {'arial': 'Arial', 'helvetica': 'Arial', 'sans-serif': 'Arial', 'verdana': 'Verdana', 'georgia': 'Georgia',
             'times new roman': 'Times New Roman', 'times': 'Times New Roman', 'serif': 'Times New Roman',
             'trebuchet ms': 'Trebuchet MS', 'tahoma': 'Tahoma', 'courier new': 'Courier New', 'monospace': 'Courier New',
             'open sans': 'Open Sans', 'roboto': 'Roboto', 'lato': 'Lato'}
    return table.get(first, first.title() if first else 'Arial')


class PageRenderer:
    """Loads a local page in Qt's web engine (offline: internet requests are blocked)
    and returns the measured layout from CAPTURE_JS."""
    def __init__(self, width=1280):
        from PySide6.QtWebEngineWidgets import QWebEngineView
        from PySide6.QtWebEngineCore import QWebEngineUrlRequestInterceptor, QWebEngineProfile, QWebEnginePage

        class Offline(QWebEngineUrlRequestInterceptor):
            def interceptRequest(self, info):
                if info.requestUrl().scheme() not in ('file', 'data', 'qrc', 'blob'): info.block(True)
        self.profile = QWebEngineProfile()
        self.interceptor = Offline(); self.profile.setUrlRequestInterceptor(self.interceptor)
        self.view = QWebEngineView(); self.view.setPage(QWebEnginePage(self.profile, self.view))
        self.view.setAttribute(Qt.WA_DontShowOnScreen, True)
        self.view.resize(width, 1000); self.view.show()

    def __call__(self, path):
        from PySide6.QtCore import QEventLoop
        loop = QEventLoop(); res = {}
        def done(ok): res['ok'] = ok; loop.quit()
        self.view.loadFinished.connect(done)
        QTimer.singleShot(20000, loop.quit)
        self.view.load(QUrl.fromLocalFile(path)); loop.exec()
        self.view.loadFinished.disconnect(done)
        QTimer.singleShot(600, loop.quit); loop.exec()
        def got(v): res['data'] = v; loop.quit()
        self.view.page().runJavaScript(CAPTURE_JS, 0, got)
        QTimer.singleShot(20000, loop.quit); loop.exec()
        try: return json.loads(res.get('data') or 'null')
        except ValueError: return None

    def close(self):
        self.view.close(); self.view.deleteLater()


def layout_rendered(s, order, info, pid, home, imgfn_for, linkfn_for, render, tick):
    m = s['masters'][0]; first = True
    for i, (p, level, nav) in enumerate(order):
        tick(i, f'Laying out “{info[p]["title"]}”')
        cap = render(p)
        pg = next(q for q in s['pages'] if q['id'] == pid[p])
        if not cap:
            pg['objects'].append(mk('text', 40, 40, 600, 40, html='<p>This page could not be read.</p>')); continue
        W, Hp = cap['width'], cap['height']
        pagebg = css_hex(cap.get('rootBg')) or css_hex(cap.get('bodyBg')) or '#ffffff'
        if cap.get('bodyImg') and not cap['bodyImg'].startswith(('http:', 'https:', '//', 'data:')):
            bp = os.path.normpath(os.path.join(os.path.dirname(p), unquote(cap['bodyImg'])))
            im = QImage(bp)
            if not im.isNull():
                small = im.scaled(1, 1, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                pagebg = QColor(small.pixel(0, 0)).name()
        if first:
            xs = [it for it in cap['items'] if it['w'] < W - 4]
            L = min((it['x'] for it in xs), default=0); Rr = max((it['x'] + it['w'] for it in xs), default=W)
            shift = max(0, L - 16) if L > 40 else 0
            newW = min(W, Rr - shift + 16) if shift else W
            s['width'] = newW; s['height'] = Hp
            root_bg = css_hex(cap.get('rootBg'))
            m['bg'] = root_bg or pagebg; s['bg'] = pagebg
        for it in cap['items'] + (cap.get('topnav') or []) + (cap.get('sidenav') or []):
            it['x'] -= shift
            if 'blockX' in it: it['blockX'] -= shift
        cv = dict(cap.get('canvas') or {'x': 0, 'y': 0, 'w': W, 'h': Hp}); cv['x'] -= shift
        W = s['width']
        def is_master(it):
            return it['where'] == 'master' and (it['y'] + it['h'] <= cv['y'] + 4 or it['x'] + it['w'] <= cv['x'] + 4)
        def bounds(links):
            if not links: return None
            l = min(a['x'] for a in links); t = min(a['y'] for a in links)
            return (l, t, max(a['x'] + a['w'] for a in links), max(a['y'] + a['h'] for a in links))
        navboxes = [b for b in (bounds(cap.get('topnav')), bounds(cap.get('sidenav'))) if b]
        def in_nav(it):
            return any(it['x'] >= b[0] - 4 and it['y'] >= b[1] - 4 and it['x'] + it['w'] <= b[2] + 4 and it['y'] + it['h'] <= b[3] + 4 for b in navboxes)
        imgfn, linkfn = imgfn_for(p), linkfn_for(p)
        for it in cap['items']:
            master = is_master(it)
            if master and not first: continue
            target = m['objects'] if master else pg['objects']
            k = it['kind']
            if k == 'box':
                fill, border = css_hex(it['bg']), css_hex(it['border'])
                if not border and (not fill or fill == (m['bg'] if master else pagebg)): continue
                if it['w'] >= W - 2 and it['h'] >= Hp - 2: continue
                target.append(mk('shape', it['x'], it['y'], it['w'], it['h'], fill=fill, stroke=border or '#000000',
                                 strokeW=round(it['bw']) if border else 0, radius=round(it['radius'])))
            elif k == 'img':
                key = imgfn(it['src'])[0]
                link = linkfn(it['href'])[1] if it.get('href') else None
                if master and in_nav(it): continue
                target.append(mk('picture', it['x'], it['y'], it['w'], it['h'], src=key, fit='stretch', link=link))
            elif k == 'iframe':
                src = it['src']
                if 'gadgets/ifr' in src:
                    src = (parse_qs(urlsplit(src).fragment).get('up_iframeURL') or [''])[0]
                if not src.startswith(('http://', 'https://', '//')): continue
                target.append(mk('html', it['x'], it['y'], it['w'], it['h'],
                                 code=f'<iframe src="{H.escape(src)}" width="{it["w"]}" height="{it["h"]}" style="border:0" allowfullscreen></iframe>'))
            elif k == 'text':
                if master and in_nav(it): continue
                html = re.sub(r'rgba?\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*(?:,\s*[\d.]+)?\)', lambda mm: css_hex(mm.group(0)) or 'transparent', it['html'])
                def fix(mm):
                    href = H.unescape(mm.group(1)); new, _ = linkfn(href)
                    return f'<a href="{H.escape(new)}">' if new else '<a>'
                html = re.sub(r'<a href="([^"]*)">', fix, html)
                al = {'start': 'left', 'left': 'left', 'center': 'center', '-webkit-center': 'center', 'right': 'right',
                      'end': 'right', 'justify': 'justify'}.get(it['align'], 'left')
                lhv = 1.2 if it['lh'] == 'normal' else float(it['lh'])
                multi = it['h'] > it['size'] * max(1.0, lhv) * 1.6
                if al != 'left' or multi: x, w = it['blockX'], it['blockW']
                else: x, w = it['x'], max(it['w'] + 12, it['blockX'] + it['blockW'] - it['x'])
                w = max(10, min(w, W - x))
                o = mk('text', x, it['y'], w, it['h'] + 4, html=f'<p>{html}</p>', font=font_family(it['family']),
                       size=it['size'], color=css_hex(it['color']) or '#000000', bold=it['bold'], italic=it['italic'],
                       align=al, lh=it['lh'], pad=0, pgap=0)
                o['h'] = max(o['h'], math.ceil(make_doc(o).size().height()) + 2)
                target.append(o)
        if first:
            for key, orient in (('topnav', 'h'), ('sidenav', 'v')):
                links = cap.get(key) or []
                ids = []
                for a in links:
                    _, lk = linkfn(a['href'])
                    if lk and lk['type'] == 'page' and lk['target'] not in ids: ids.append(lk['target'])
                b = bounds(links)
                if not ids or not b: continue
                a0 = links[0]; col = css_hex(a0['color']) or '#1f4e79'
                m['objects'].append(mk('nav', b[0] - 14 if orient == 'h' else b[0] - 4, b[1] - 4, b[2] - b[0] + 28, b[3] - b[1] + 8,
                                       style='plain', orient=orient, font=font_family(a0['family']), size=a0['size'],
                                       bold=a0['bold'], color=col, accent=QColor(col).darker(170).name(), pages=ids))
        pg['height'] = max(Hp, 400)
        first = False

# ----------------------------------------------------------------------------
# Opening a Serif WebPlus site (.wpp)
#
# WebPlus never published its file format, so the reading is not done here: it
# is done by the `serif` package of Serif-for-Linux, which parses the SerifXML
# inside the .wpp and hands back pages, master pages, the site tree and every
# object on every page. This section is only the translation — WebPlus's model
# into this app's page/object dictionaries — so that a site Jan built in 2008
# opens here as pages he can edit, not as a read-only picture of itself.
#
# Two differences in the models are worth knowing, because they are the two
# places the translation approximates rather than copies:
#
#   * WebPlus measures in points and this app in pixels, so everything is
#     scaled by 96/72. Each WebPlus page may have its own width; this app has
#     one width for the site, so the widest page sets it.
#   * The Site Structure tree can be any depth. This app's tree is two deep,
#     so deeper pages keep their order and sit at the second level.
# ----------------------------------------------------------------------------

WPP_EXT = '.wpp'
WPP_PX = 96.0 / 72.0            # WebPlus works in points, this app in pixels

#: Picture formats no browser and no Qt build will open, which WebPlus happily
#: embedded. Counted and reported rather than written as bytes nothing can draw.
WPP_UNDISPLAYABLE = {'.wdp', '.hdp', '.jxr', '.smf'}

#: Where a Serif-for-Linux checkout usually is. The installed `webwriter`
#: launcher is a symlink into the checkout, so that is tried first and is the
#: one that keeps working when the checkout moves.
WPP_READER_DIRS = ('~/src/serif-linux', '~/Documents/Development/serif-linux',
                   '~/serif-linux', '~/.local/opt/serif-linux')


def wpp_reader_root(hint=None, only_hint=False):
    """The Serif-for-Linux checkout that can read a .wpp, or None.

    ``only_hint`` checks nothing but the folder given, which is what the
    "where is it?" dialog needs: falling back to somewhere else after Jan has
    pointed at a folder would use a reader he did not choose and say nothing.
    """
    import shutil
    tried = [hint] if hint else []
    if not only_hint:
        launcher = shutil.which('webwriter')
        if launcher:
            tried.append(os.path.dirname(os.path.dirname(os.path.realpath(launcher))))
        tried += [os.path.expanduser(p) for p in WPP_READER_DIRS]
    for root in tried:
        if root and os.path.isfile(os.path.join(root, 'serif', 'webplus.py')):
            return os.path.realpath(root)
    return None


def wpp_reader(root):
    if root not in sys.path:
        sys.path.insert(0, root)
    from serif import webplus
    from serif.serifxml import SerifContainer
    return webplus, SerifContainer


def _wpp_box(obj):
    """Where a WebPlus object sits, in this app's pixels, and its rotation.

    WebPlus stores a box plus a 2x2 matrix about the box's own centre — the
    same convention CSS and QGraphicsItem use — so the rotation comes straight
    out of the matrix and any scale in it is folded into the width and height.
    """
    a, b, c, d, e, f = obj.transform
    left, top, right, bottom = obj.render_bbox
    e += obj.edit_move[0]
    f += obj.edit_move[1]
    sx = math.hypot(a, b) or 1.0
    sy = math.hypot(c, d) or 1.0
    w = max(right - left, 0.0) * sx
    h = max(bottom - top, 0.0) * sy
    cx, cy = (left + right) / 2 + e, (top + bottom) / 2 + f
    return (round((cx - w / 2) * WPP_PX, 1), round((cy - h / 2) * WPP_PX, 1),
            max(1, round(w * WPP_PX)), max(1, round(h * WPP_PX)),
            round(math.degrees(math.atan2(b, a)), 2))


def _wpp_text_html(obj):
    """A WebPlus story as the HTML subset this app's text objects use."""
    scale = obj.text_scale or 1.0
    paras = []
    for para in (obj.story.paragraphs if obj.story else []):
        spans = []
        for run in para.runs:
            if run.inline is not None or not run.text:
                continue
            css = []
            if run.font: css.append(f"font-family:'{run.font}'")
            if run.size_pt: css.append(f'font-size:{max(1, round(run.size_pt * scale * WPP_PX))}px')
            if run.colour: css.append(f'color:{run.colour}')
            if run.weight: css.append(f'font-weight:{run.weight}')
            if run.italic: css.append('font-style:italic')
            if run.underline: css.append('text-decoration:underline')
            body = esc(run.text).replace('\n', '<br>')
            spans.append(f'<span style="{";".join(css)}">{body}</span>' if css else body)
        align = para.align if para.align in ALIGN else 'left'
        paras.append(f'<p style="text-align:{align}">{"".join(spans) or "&nbsp;"}</p>')
    return ''.join(paras) or '<p></p>'


def _wpp_text_face(obj):
    """The font, size, colour and leading to put on the object itself.

    Whichever face covers the most characters wins, so the object's own
    properties — the ones the Character tab shows and a click edits — describe
    the frame rather than whichever run happened to come first.
    """
    scale = obj.text_scale or 1.0
    weight = {}
    for para in (obj.story.paragraphs if obj.story else []):
        for run in para.runs:
            if run.inline is not None:
                continue
            key = (run.font, run.size_pt, run.colour, run.weight, run.italic, run.underline)
            weight[key] = weight.get(key, 0) + max(1, len(run.text))
    font, size, colour, wgt, italic, under = max(weight, key=weight.get) if weight else (None,) * 6
    first = next((p for p in (obj.story.paragraphs if obj.story else []) if p.runs), None)
    size_px = max(1, round((size or 12) * scale * WPP_PX))
    if first is None:
        lh = 1.3
    elif first.leading_is_relative:
        lh = round(first.rel_leading or 1.0, 3)
    else:
        lh = round((first.abs_leading * scale * WPP_PX) / size_px, 3) if first.abs_leading else 1.3
    return dict(font=font or SANS, size=size_px, color=colour or '#000000',
                bold=bool(wgt and wgt >= 600), italic=bool(italic), underline=bool(under),
                align=first.align if first and first.align in ALIGN else 'left',
                lh=max(0.6, min(4.0, lh)), pgap=0)


def _wpp_nav_style(obj):
    st = obj.nav_style or {}
    colour = st.get('colour') or '#1f4e79'
    accent = st.get('border') or QColor(colour).darker(150).name()
    return dict(style='tabs', orient='h' if st.get('horizontal', True) else 'v',
                font=st.get('font') or SANS,
                size=max(9, round((st.get('size_pt') or 11) * WPP_PX)),
                color=colour, accent=accent, accentInk='#ffffff',
                fill=st.get('background') or '')


def import_webplus_file(path, root, progress=None):
    """Read a WebPlus .wpp and return it as one of this app's sites.

    Everything the reader could not bring across is counted into the returned
    site's ``_wpp_notes``, because a silent gap in somebody's own 208-page site
    is worse than a sentence saying what is missing.
    """
    webplus, SerifContainer = wpp_reader(root)
    notes = dict(skipped={}, placeholder={}, missing=0, undisplayable=0, linked=0, deep=0,
                 backgrounds=0, warnings=[])

    def tick(i, n, msg):
        if progress and progress(i, n, msg) is False:
            raise RuntimeError('Opening the WebPlus site was cancelled.')

    tick(0, 100, f'Reading {os.path.basename(path)}…')
    wp = webplus.read(path)
    notes['warnings'] = list(wp.warnings)
    if not wp.pages:
        raise RuntimeError(f'{os.path.basename(path)} holds no pages, so there is no site in it '
                           'to open. A WebPlus file can also hold saved objects or design assets '
                           'rather than a website, and Serif’s own “My Designs.wpp” is one.')

    # --- the pages, in Site Structure order -------------------------------
    flat = []

    def walk(nodes, depth):
        for n in nodes:
            flat.append((n, depth))
            walk(n.children, depth + 1)
    walk(wp.tree, 0)
    seen = {id(n) for n, _ in flat}
    flat += [(p, 0) for p in wp.pages if id(p) not in seen]   # never drop a page
    if wp.home is not None:
        flat.sort(key=lambda it: 0 if it[0] is wp.home else 1)

    width_pt = max((p.page.width for p in wp.pages if p.page), default=595.0)
    site = base_site(wp.title or os.path.splitext(os.path.basename(path))[0],
                     width=max(320, round(width_pt * WPP_PX)),
                     height=max(200, round(max((p.page.height for p in wp.pages if p.page), default=842.0) * WPP_PX)),
                     palette=[c for c in (wp.document.scheme_colours or []) if c][:18])
    site['pages'] = []
    site['masters'] = []
    site['assetnames'] = {}

    masters = {}                                   # MasterPage letter -> master dict
    for m in wp.masters:
        d = dict(id=uid(), name=m.name or f'Master {m.letter}', bg='#ffffff', objects=[])
        masters[m.letter] = d
        site['masters'].append(d)
    none_master = dict(id=uid(), name='(None)', bg='#ffffff', objects=[])
    site['masters'].append(none_master)

    used_files, pages = set(), {}
    for sp, depth in flat:
        stem = sp.path.replace('/', '-') or (sp.name or 'page')
        file = stem if stem.lower().endswith(('.html', '.htm')) else stem + '.html'
        if file in used_files:
            file = slug(os.path.splitext(stem)[0], used_files)
        used_files.add(file)
        notes['deep'] = max(notes['deep'], depth)
        pg = add_page(site, sp.name or os.path.splitext(file)[0], depth, file=file,
                      master=(masters[sp.master.letter]['id'] if sp.master else none_master['id']))
        pg['nav'] = not sp.search_exclude and not sp.directory.startswith('_hidden')
        pg['bg'] = sp.background.colour or ''
        pg['height'] = max(200, round((sp.page.height if sp.page else 842.0) * WPP_PX))
        pages[id(sp)] = pg
    by_index = {i: pages[id(p)]['id'] for i, p in enumerate(wp.pages) if id(p) in pages}
    top_level = [p['id'] for p in site['pages'] if not p.get('level')]

    # --- the pictures ------------------------------------------------------
    assets = {}

    def asset_for(part, name=None):
        """One embedded picture, as a data URI this app can keep in the site."""
        if not part:
            return None
        if part in assets:
            return assets[part]
        assets[part] = None
        if os.path.splitext(part)[1].lower() in WPP_UNDISPLAYABLE:
            notes['undisplayable'] += 1
            return None
        if not container.has(part):
            notes['missing'] += 1
            return None
        data = container.binary(part)
        mime = MIME.get(os.path.splitext(part)[1].lower().lstrip('.'), 'application/octet-stream')
        key = add_asset(site, f'data:{mime};base64,' + base64.b64encode(data).decode())
        site['assetnames'][key] = os.path.basename((name or part).replace('\\', '/'))
        assets[part] = key
        return key

    def file_asset(path_on_disk):
        try:
            data = open(path_on_disk, 'rb').read()
        except OSError:
            notes['missing'] += 1
            return None
        ext = os.path.splitext(str(path_on_disk))[1].lower().lstrip('.')
        key = add_asset(site, f'data:{MIME.get(ext, "application/octet-stream")};base64,'
                        + base64.b64encode(data).decode())
        site['assetnames'][key] = os.path.basename(str(path_on_disk))
        return key

    def link_for(link):
        if link is None:
            return None
        if link.page_index is not None and link.page_index in by_index:
            return {'type': 'page', 'target': by_index[link.page_index]}
        url = (link.url or '').strip()
        if not url:
            return None
        if url.lower().startswith('mailto:'):
            return {'type': 'email', 'target': url[7:].split('?')[0]}
        return {'type': 'url', 'target': url}

    # --- one object --------------------------------------------------------
    def convert(obj, out):
        """Translate one WebPlus object onto ``out``, a list of page objects."""
        if obj.kind == 'group':
            # A group's children carry page coordinates of their own — Serif's
            # own exporter emits them with no positioned wrapper — so a group
            # flattens by simply converting its children where they are.
            for child in obj.children:
                convert(child, out)
            return
        x, y, w, h, rot = _wpp_box(obj)
        common = dict(rot=rot, opacity=round(obj.fill_opacity, 3), link=link_for(obj.link),
                      hidden=bool(obj.hidden))
        stroke = dict(stroke=obj.stroke or '#333333',
                      strokeW=round((obj.stroke_width or 0) * WPP_PX, 2) if obj.stroke else 0)

        if obj.kind == 'text':
            kind = 'artistic' if obj.serif_class == 'ArtTextObject' else 'text'
            face = _wpp_text_face(obj)
            o = mk(kind, x, y, w, h, html=_wpp_text_html(obj), fill=obj.fill or '',
                   **face, **stroke, **common)
            if kind == 'text':
                o['pad'] = 0
            out.append(o)
        elif obj.kind == 'image':
            key = asset_for(obj.image_part, obj.image_name)
            if key is None and obj.image_name and not obj.image_part:
                notes['linked'] += 1
            out.append(mk('picture', x, y, w, h, src=key, fit='stretch', **stroke, **common))
        elif obj.kind in ('shape', 'ellipse', 'line'):
            if obj.kind == 'line' or (h <= 2 and obj.fill is None):
                out.append(mk('line', x, y, w, max(1, h),
                              stroke=obj.stroke or obj.fill or '#333333',
                              strokeW=max(1, round((obj.stroke_width or 1) * WPP_PX)), **common))
            else:
                out.append(mk('shape', x, y, w, h, shape='ellipse' if obj.kind == 'ellipse' else 'rect',
                              fill=obj.fill or '', **stroke, **common))
        elif obj.kind == 'nav':
            ids = [by_index[n.link.page_index] for n in obj.nav
                   if n.link is not None and n.link.page_index in by_index]
            style = _wpp_nav_style(obj)
            # WebPlus built most bars from the site tree when it published. Where
            # that is what this bar is, leave it automatic so it keeps up with
            # pages Jan adds; where it is a hand-picked list, pin the list.
            if ids and ids != top_level:
                style['pages'] = ids
            out.append(mk('nav', x, y, w, h, **style, **common))
        elif obj.kind == 'gallery':
            keys = [k for k in (asset_for(g.part, g.filename) for g in obj.gallery) if k]
            out.append(mk('gallery', x, y, w, h, images=keys, **stroke, **common))
        elif obj.kind == 'html':
            out.append(mk('html', x, y, w, h, code=obj.html or '', **common))
        elif obj.kind == 'link':
            # A hotspot: an invisible clickable region. It keeps its click and
            # becomes something Jan can see and move, rather than vanishing.
            out.append(mk('shape', x, y, w, h, fill='', stroke='', strokeW=0, **common))
        elif obj.kind in ('iframe', 'video', 'map', 'widget'):
            # Most of WebPlus's iframes point at another page of the same site,
            # and that target is on the object's link, not its external URL.
            name = obj.widget or 'Embedded page'
            inner = None
            if obj.link is not None and obj.link.page_index in by_index:
                target = next(q for q in site['pages'] if q['id'] == by_index[obj.link.page_index])
                inner = target['file']
            elif obj.external_url:
                inner = obj.external_url
            if inner:
                out.append(mk('html', x, y, w, h, **dict(common, link=None), code=(
                    f'<iframe src="{esc(inner)}" title="{esc(name)}" '
                    f'style="width:100%;height:100%;border:0" loading="lazy"></iframe>')))
            else:
                # Nothing to embed, but the object was somewhere and was some
                # size: keep the hole rather than silently closing it up.
                out.append(mk('html', x, y, w, h, **common,
                              code=f'<!-- WebPlus {esc(name)}: this object carried no address -->'))
                notes['placeholder'][name] = notes['placeholder'].get(name, 0) + 1
        elif obj.kind == 'form':
            fields, submit = [], 'Send'
            def fields_of(o):
                nonlocal submit
                for c in o.children:
                    if c.kind == 'input':
                        if c.input_kind in ('submit', 'button'):
                            submit = c.input_value or submit
                        else:
                            fields.append(c.input_placeholder or c.input_name or 'Field')
                    fields_of(c)
            fields_of(obj)
            out.append(mk('form', x, y, w, h, fields=fields or ['Name', 'Email', 'Message'],
                          submit=submit, **common))
        else:
            name = obj.widget or obj.serif_class or obj.kind
            notes['skipped'][name] = notes['skipped'].get(name, 0) + 1

    def backgrounds(sp, pg):
        """A WebPlus page background, as pictures behind everything else."""
        out = []
        for bg in sp.background.images:
            key = asset_for(bg.part, bg.filename) if bg.part else (
                file_asset(bg.theme_asset) if bg.theme_asset else None)
            if not key:
                continue
            pm = pixmap_for(site, key)
            iw = pm.width() if pm and not pm.isNull() else site['width']
            ih = pm.height() if pm and not pm.isNull() else 100
            w = site['width'] if bg.repeat in ('x', 'both') else iw
            h = pg['height'] if bg.repeat in ('y', 'both') else ih
            x = {'centre': (site['width'] - w) / 2, 'right': site['width'] - w}.get(bg.position_x, 0)
            y = {'centre': (pg['height'] - h) / 2, 'bottom': pg['height'] - h}.get(bg.position_y, 0)
            if bg.position_x == 'custom': x = bg.offset_x * WPP_PX
            if bg.position_y == 'custom': y = bg.offset_y * WPP_PX
            out.append(mk('picture', round(x, 1), round(y, 1), max(1, round(w)), max(1, round(h)),
                          src=key, fit='stretch', locked=True))
            notes['backgrounds'] += 1
        return out

    # --- walk the publication ---------------------------------------------
    filled = set()
    with SerifContainer.open(wp.path) as container:
        for i, (sp, _) in enumerate(flat):
            tick(i + 1, len(flat) + 1, f'Laying out “{sp.name}”')
            pg = pages[id(sp)]
            pg['objects'] = backgrounds(sp, pg)
            if sp.page is None:
                continue
            master = masters[sp.master.letter] if sp.master else none_master
            for layer in sp.page.layers:
                if not layer.visible:
                    continue
                if layer.is_master:
                    # Master objects are inherited into every page that uses the
                    # master, so the first page to use one fills it and the rest
                    # of them already show it.
                    if master['id'] in filled:
                        continue
                    for obj in layer.objects:
                        convert(obj, master['objects'])
                else:
                    for obj in layer.objects:
                        convert(obj, pg['objects'])
            filled.add(master['id'])

    site['masters'] = [m for m in site['masters']
                       if m['objects'] or any(p['master'] == m['id'] for p in site['pages'])]
    if not site['masters']:
        site['masters'] = [none_master]
    site['bg'] = next((p['bg'] for p in site['pages'] if p.get('bg')), '#ffffff')
    site['_wpp_notes'] = notes
    site['_wpp_source'] = os.path.abspath(path)
    return site


def wpp_summary(site, path, notes):
    """What came across, and what did not, in words."""
    pages, objects = len(site['pages']), sum(len(p['objects']) for p in site['pages'])
    objects += sum(len(m['objects']) for m in site['masters'])
    lines = [f'Opened “{os.path.basename(path)}”: {pages} page'
             f'{"" if pages == 1 else "s"}, {len(site["masters"])} master page'
             f'{"" if len(site["masters"]) == 1 else "s"}, {objects} objects, '
             f'{len(site.get("assets", {}))} pictures.', '']
    lines.append('Every page is editable here — WebPlus\'s own page order, master pages, '
                 'text, pictures and navigation bars. The original .wpp is only read and is '
                 f'never written to. Save this as a {EXT} file (File ▸ Save As) to keep your changes.')
    if notes.get('deep', 0) > 1:
        lines += ['', f'The Site Structure tree is {notes["deep"] + 1} levels deep and is shown '
                      'as WebPlus had it, in the Site tab.']
    gaps = []
    if notes.get('missing'):
        gaps.append(f'{notes["missing"]} picture(s) the publication names but does not carry')
    if notes.get('linked'):
        gaps.append(f'{notes["linked"]} picture(s) were linked rather than embedded, so only the '
                    'original path survives')
    if notes.get('undisplayable'):
        gaps.append(f'{notes["undisplayable"]} picture(s) are in a format nothing on Linux opens '
                    '(JPEG XR or a Serif metafile)')
    if notes.get('placeholder'):
        worst = sorted(notes['placeholder'].items(), key=lambda kv: -kv[1])[:4]
        gaps.append('objects that had nothing to embed are kept as empty placeholders at their own '
                    'size and position: ' + ', '.join(f'{n} × {c}' for n, c in worst))
    if notes.get('skipped'):
        worst = sorted(notes['skipped'].items(), key=lambda kv: -kv[1])[:4]
        gaps.append('objects with no equivalent here were left out: '
                    + ', '.join(f'{n} × {c}' for n, c in worst))
    if gaps:
        lines += ['', 'What did not come across:'] + [f'• {g}' for g in gaps]
    return '\n'.join(lines)


# ----------------------------------------------------------------------------
# Icons — taken from your icon theme, with drawn fallbacks
# ----------------------------------------------------------------------------

def ticon(names, glyph='?'):
    for n in names:
        if QIcon.hasThemeIcon(n): return QIcon.fromTheme(n)
    if not glyph: return QIcon()  # no themed icon: toolbars show the action's text instead
    pm = QPixmap(32, 32); pm.fill(Qt.transparent)
    p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QApplication.palette().color(QPalette.WindowText))
    f = QFont(); f.setPixelSize(17 if len(glyph) < 2 else 12); f.setBold(True); p.setFont(f)
    p.drawText(pm.rect(), Qt.AlignCenter, glyph); p.end()
    return QIcon(pm)

def swatch_icon(col, size=16):
    pm = QPixmap(size, size); pm.fill(Qt.transparent); p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing)
    pal = QApplication.palette()
    p.setPen(QPen(pal.color(QPalette.Mid), 1))
    if col:
        p.setBrush(QColor(col)); p.drawRoundedRect(QRectF(.5, .5, size - 1, size - 1), 3, 3)
    else:
        p.setBrush(pal.color(QPalette.Base)); p.drawRoundedRect(QRectF(.5, .5, size - 1, size - 1), 3, 3)
        p.setPen(QPen(QColor('#d03b3b'), 1.5)); p.drawLine(QPointF(2, size - 2), QPointF(size - 2, 2))
    p.end(); return QIcon(pm)


class SpectrumBar(QWidget):
    """A 2-D colour spectrum (hue across, brightness down) like Serif's Colour tab.
    Click or drag to pick; on_pick gets a '#rrggbb' string, on_release ends the gesture."""
    def __init__(self, on_pick, on_release=None, parent=None):
        super().__init__(parent)
        self.on_pick, self.on_release = on_pick, on_release
        self.setMinimumHeight(160); self.setCursor(Qt.CrossCursor)  # TV-screen proportions

    def paintEvent(self, e):
        p = QPainter(self); r = self.rect(); w, h = self.width(), self.height()
        hue = QLinearGradient(0, 0, w, 0)
        for i in range(7): hue.setColorAt(i / 6, QColor.fromHsv((i * 60) % 360, 255, 255))
        p.fillRect(r, hue)
        wg = QLinearGradient(0, 0, 0, h); wg.setColorAt(0, QColor(255, 255, 255, 255)); wg.setColorAt(.5, QColor(255, 255, 255, 0))
        p.fillRect(r, wg)
        bg = QLinearGradient(0, 0, 0, h); bg.setColorAt(.5, QColor(0, 0, 0, 0)); bg.setColorAt(1, QColor(0, 0, 0, 255))
        p.fillRect(r, bg)
        p.setPen(QPen(QApplication.palette().color(QPalette.Mid), 1)); p.drawRect(0, 0, w - 1, h - 1); p.end()

    def _emit(self, e):
        img = self.grab().toImage()
        x = min(max(0, int(e.position().x())), self.width() - 1)
        y = min(max(0, int(e.position().y())), self.height() - 1)
        self.on_pick(QColor(img.pixel(x, y)).name())

    def mousePressEvent(self, e): self._emit(e)
    def mouseMoveEvent(self, e):
        if e.buttons(): self._emit(e)
    def mouseReleaseEvent(self, e):
        if self.on_release: self.on_release()


class ThumbGrid(QListWidget):
    """Icon grid whose thumbnails grow with the panel and reflow between columns:
    two columns at the default width, one when narrowed, more (and larger) when widened.
    Thumbnails can be dragged OUT onto the page to place them, and picture files dragged
    IN from another app are imported (emitted via `filesDropped`)."""
    filesDropped = Signal(list)   # list of local picture file paths dropped onto the panel

    def __init__(self, min_cell=86, max_cell=170, parent=None):
        super().__init__(parent)
        self._min, self._max = min_cell, max_cell
        self.setViewMode(QListWidget.IconMode); self.setResizeMode(QListWidget.Adjust)
        self.setMovement(QListWidget.Static); self.setUniformItemSizes(True)
        self.setWordWrap(False); self.setSpacing(2)
        # Pin the vertical scrollbar on so the viewport width never changes when the
        # scrollbar would otherwise appear/disappear. That toggling was what made the
        # column count oscillate between 3 and 4 (and the thumbnails jitter in size).
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # Drag a thumbnail out to place it; accept picture files dropped in from elsewhere.
        # (Scrolling is by the wheel and the always-on scrollbar, not by dragging the body.)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.CopyAction)
        self.setAcceptDrops(True)
        self._press = None

    # Start the drag ourselves from the mouse handlers rather than relying on
    # QListView's built-in dispatch: in IconMode with Movement.Static the view
    # often never calls startDrag on real input, so dragging a thumbnail out did
    # nothing. Driving QDrag manually makes it work regardless of that quirk.
    def mousePressEvent(self, e):
        self._press = e.position().toPoint() if e.button() == Qt.LeftButton else None
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if ((e.buttons() & Qt.LeftButton) and self._press is not None
                and (e.position().toPoint() - self._press).manhattanLength() >= QApplication.startDragDistance()):
            it = self.itemAt(self._press); self._press = None
            if it and it.data(Qt.UserRole):
                self._begin_drag(it); return
        super().mouseMoveEvent(e)

    def _begin_drag(self, it):
        key = it.data(Qt.UserRole)
        md = QMimeData(); md.setData(ASSET_MIME, QByteArray(str(key).encode()))
        drag = QDrag(self); drag.setMimeData(md)
        pm = it.icon().pixmap(self.iconSize())
        if not pm.isNull():
            drag.setPixmap(pm); drag.setHotSpot(QPoint(pm.width() // 2, pm.height() // 2))
        drag.exec(Qt.CopyAction)

    def startDrag(self, actions):   # fallback if the view ever dispatches it
        it = self.currentItem()
        if it and it.data(Qt.UserRole): self._begin_drag(it)

    @staticmethod
    def _moz_url(md):
        """URL out of Firefox/Chrome's text/x-moz-url (UTF-16 'URL\\nTitle'), or None."""
        if not md.hasFormat('text/x-moz-url'): return None
        raw = bytes(md.data('text/x-moz-url'))
        for enc in ('utf-16', 'utf-8'):
            try:
                s = raw.decode(enc).split('\n', 1)[0].strip()
                if s.lower().startswith(('http://', 'https://')): return s
            except Exception:
                pass
        return None

    @staticmethod
    def _html_img(md):
        """First <img src="http…"> inside dropped text/html (how some browsers drag), or None."""
        if not md.hasHtml(): return None
        m = re.search(r'<img[^>]+src\s*=\s*["\']?(https?://[^"\'> ]+)', md.html(), re.I)
        return m.group(1) if m else None

    @staticmethod
    def _can_drop(md):
        """Cheap test (safe to call on every drag-move) for a droppable picture: a local
        image file, ANY web URL (dragged from a browser — extensionless CDN URLs included;
        validated as an image only on drop), an <img> in dropped HTML, or an embedded
        bitmap. Our own thumbnail drags (ASSET_MIME) are not 'drops in'."""
        if md.hasFormat(ASSET_MIME): return False
        if md.hasImage(): return True
        if md.hasUrls():
            for u in md.urls():
                if u.isLocalFile():
                    if os.path.splitext(u.toLocalFile())[1].lower() in IMG_DROP_EXTS: return True
                elif u.scheme() in ('http', 'https'):
                    return True
        return bool(ThumbGrid._html_img(md) or ThumbGrid._moz_url(md))

    @staticmethod
    def _image_sources(md):
        """Resolve a drop into picture sources, called once at drop time. Each is a
        tuple ('file', path) | ('url', http-url) | ('img', QImage). Local files win over
        remote URLs, which win over an embedded bitmap, so a single browser image isn't
        imported twice. Remote URLs keep ALL web links (not just .png/.jpg ones) — the
        downloader keeps a result only if the bytes actually decode as a picture."""
        if md.hasFormat(ASSET_MIME): return []
        files, remote = [], []
        if md.hasUrls():
            for u in md.urls():
                if u.isLocalFile():
                    p = u.toLocalFile()
                    if os.path.splitext(p)[1].lower() in IMG_DROP_EXTS: files.append(('file', p))
                elif u.scheme() in ('http', 'https'):
                    remote.append(('url', u.toString()))
        if files: return files
        if not remote:   # browsers that drag an <img> as HTML or a text/x-moz-url
            u = ThumbGrid._html_img(md) or ThumbGrid._moz_url(md)
            if u: remote.append(('url', u))
        if remote: return remote
        img = md.imageData()
        if isinstance(img, QImage) and not img.isNull(): return [('img', img)]
        return []

    def dragEnterEvent(self, e):
        (e.acceptProposedAction() if self._can_drop(e.mimeData()) else e.ignore())

    def dragMoveEvent(self, e):
        (e.acceptProposedAction() if self._can_drop(e.mimeData()) else e.ignore())

    def dropEvent(self, e):
        srcs = self._image_sources(e.mimeData())
        if srcs:
            e.acceptProposedAction(); self.filesDropped.emit(srcs)
        else:
            e.ignore()

    def resizeEvent(self, e):
        super().resizeEvent(e); self.relayout()

    def relayout(self):
        vw = self.viewport().width()
        cols = max(1, vw // self._min)
        cell = max(40, min(self._max, vw // cols - 2 * self.spacing() - 2))
        self.setIconSize(QSize(cell - 10, cell - 10)); self.setGridSize(QSize(cell, cell))
        for i in range(self.count()): self.item(i).setSizeHint(QSize(cell - 4, cell - 4))


TOOLS = [
    # id, label, theme icon names, fallback glyph, hint
    ('pointer', 'Pointer', ['tool-pointer', 'edit-select'], '↖', 'Click to select an object. Shift-click adds to the selection. Drag on empty space to select several.'),
    ('hand', 'Hand', ['transform-browse', 'tool-hand', 'hand'], '✋', 'Drag to scroll the page.'),
    ('zoom', 'Zoom', ['zoom-select', 'zoom-in'], '⌕', 'Click to zoom in. Shift-click to zoom out.'),
    (None,),
    ('artistic', 'Artistic Text', ['draw-text', 'format-text-bold'], 'A', 'Click to type artistic text, or drag to set its size. Resizing artistic text scales it.'),
    ('text', 'Creative Frame Text', ['insert-text-frame', 'text-frame-link', 'insert-text'], '¶', 'Drag to create a text frame, then type. Text wraps inside the frame.'),
    ('table', 'Table', ['insert-table', 'table'], '▦', 'Drag to place a table. Double-click a table to edit its cells.'),
    (None,),
    ('picture', 'Picture', ['insert-image', 'image-x-generic'], '▣', 'Drag to place a picture frame and choose a picture.'),
    ('gallery', 'Photo Gallery', ['view-presentation', 'folder-pictures', 'view-preview'], '▤', 'Drag to place a photo gallery, then choose the photos it shows in turn.'),
    ('rect', 'Rectangle', ['draw-rectangle'], '□', 'Drag to draw a rectangle. Hold Shift for a square.'),
    ('ellipse', 'Ellipse', ['draw-ellipse'], '○', 'Drag to draw an ellipse. Hold Shift for a circle.'),
    ('line', 'Line', ['draw-line'], '╱', 'Drag to draw a straight line.'),
    (None,),
    ('nav', 'Navigation Bar', ['application-menu', 'view-list-details'], '☰', 'Drag to place a navigation bar. It lists the pages in your site automatically.'),
    ('button', 'Button', ['insert-button', 'dialog-ok'], '⬭', 'Drag to place a button, then give it a hyperlink.'),
    ('form', 'Form', ['view-form', 'document-edit'], '✎', 'Drag to place a contact form.'),
    ('share', 'Share Buttons', ['document-share', 'emblem-shared-symbolic', 'mail-forward'], '⇪', 'Drag to place a row of buttons that let visitors share the page on social media.'),
    ('html', 'HTML Code', ['text-html', 'code-context'], '</>', 'Drag to place an HTML fragment.'),
]

class LinelessTree(QTreeWidget):
    """A tree that draws ONLY a ▸/▾ expand arrow for parent rows and NO connector lines
    (no vertical line through the arrows, no branch stubs). The arrow stays clickable."""
    def drawBranches(self, painter, rect, index):
        if not self.model().hasChildren(index):
            return  # leaf row: nothing (no line)
        from PySide6.QtGui import QPolygon
        from PySide6.QtCore import QPoint
        painter.save(); painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen); painter.setBrush(self.palette().text().color())
        cx = rect.right() - 10; cy = rect.center().y(); a = 4
        if self.isExpanded(index):
            tri = QPolygon([QPoint(cx - a, cy - a + 1), QPoint(cx + a, cy - a + 1), QPoint(cx, cy + a)])
        else:
            tri = QPolygon([QPoint(cx - a + 1, cy - a), QPoint(cx - a + 1, cy + a), QPoint(cx + a, cy)])
        painter.drawPolygon(tri); painter.restore()


# ----------------------------------------------------------------------------
# Canvas
# ----------------------------------------------------------------------------

class ObjItem(QGraphicsItem):
    def __init__(self, o, win, master=False):
        super().__init__()
        self.o, self.win, self.master, self.editing = o, win, master, False
        self.dy = 0
        self.sync()

    def sync(self):
        o = self.o
        self.prepareGeometryChange()
        self.setPos(o['x'], o['y'] + self.dy)
        self.setTransformOriginPoint(o['w'] / 2, o['h'] / 2)
        self.setRotation(o.get('rot', 0))
        self.setOpacity(o.get('opacity', 1))
        self.update()

    def boundingRect(self):
        pad = self.o.get('strokeW', 0) / 2 + 2
        if self.o['type'] == 'nav': pad += 40
        return QRectF(-pad, -pad, self.o['w'] + 2 * pad, self.o['h'] + 2 * pad)

    def shape(self):
        path = QPainterPath(); path.addRect(QRectF(0, 0, self.o['w'], self.o['h'])); return path

    def paint(self, p, opt, widget=None):
        page = None if self.win.edit_master else self.win.page()
        paint_obj(p, self.o, self.win.site, page, hide_text=self.editing, edit=True)


class TextEditor(QGraphicsTextItem):
    def __init__(self, parent, win):
        super().__init__(parent); self.win = win

    def focusOutEvent(self, e):
        super().focusOutEvent(e)
        if e.reason() in (Qt.PopupFocusReason, Qt.ActiveWindowFocusReason): return
        QTimer.singleShot(0, self.win.finish_edit)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.win.finish_edit(); return
        super().keyPressEvent(e)


class Canvas(QGraphicsView):
    HANDLES = ['nw', 'n', 'ne', 'e', 'se', 's', 'sw', 'w']

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setScene(QGraphicsScene(self))
        self.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform)
        self.setMouseTracking(True)
        self.setTransformationAnchor(QGraphicsView.NoAnchor)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setFrameShape(QFrame.NoFrame)
        self.setFocusPolicy(Qt.StrongFocus)
        self.zoom = 1.0
        self.drag = None
        self.marq = None
        self.ghost = None
        self.horizontalScrollBar().valueChanged.connect(lambda *_: win.update_rulers())
        self.verticalScrollBar().valueChanged.connect(lambda *_: win.update_rulers())
        self.setAcceptDrops(True); self.viewport().setAcceptDrops(True)   # drop assets or picture files onto the page

    # -- drag & drop onto the page
    def _accepts(self, md):
        return md.hasFormat(ASSET_MIME) or ThumbGrid._can_drop(md)

    def dragEnterEvent(self, e):
        (e.acceptProposedAction() if self._accepts(e.mimeData()) else e.ignore())

    def dragMoveEvent(self, e):
        (e.acceptProposedAction() if self._accepts(e.mimeData()) else e.ignore())

    def dropEvent(self, e):
        md = e.mimeData()
        pt = self.mapToScene(e.position().toPoint())
        if md.hasFormat(ASSET_MIME):
            self.win.place_asset_at(bytes(md.data(ASSET_MIME)).decode(), pt)
            e.acceptProposedAction(); return
        srcs = ThumbGrid._image_sources(md)
        if srcs:
            self.win.import_asset_files(srcs, place_at=pt); e.acceptProposedAction(); return
        e.ignore()

    # -- geometry
    def page_rect(self):
        return QRectF(0, 0, self.win.site['width'], self.win.page_h())

    def set_zoom(self, z, anchor=None):
        z = max(.1, min(8.0, z))
        if anchor is None: anchor = self.viewport().rect().center()
        before = self.mapToScene(anchor)
        self.zoom = z
        self.setTransform(QTransform.fromScale(z, z))
        after = self.mapToScene(anchor)
        d = (after - before)
        self.translate(d.x(), d.y())
        self.win.zoom_changed()

    def fit_width(self):
        # Never magnify past actual size: if the page is NARROWER than the viewport
        # (a wide/maximised window), show it at 100% — fixed width — instead of blowing
        # the 970px design up to 2-3× just to fill the canvas. Only shrink to fit when
        # the page is wider than the viewport.
        z = min(1.0, (self.viewport().width() - 60) / self.win.site['width'])
        self.set_zoom(z)
        self.centerOn(QPointF(self.win.site['width'] / 2, self.mapToScene(self.viewport().rect().center()).y()))

    # -- painting
    def drawBackground(self, p, rect):
        pal = self.palette()
        base = pal.color(QPalette.Window)
        paste = base.darker(118) if base.lightness() > 128 else base.darker(150)
        p.fillRect(rect, paste)
        pr = self.page_rect()
        p.fillRect(pr.translated(4 / self.zoom, 6 / self.zoom), QColor(0, 0, 0, 50))
        p.fillRect(pr, QColor(self.win.page_bg()))
        if self.win.show_grid:
            g = 20
            lum = QColor(self.win.page_bg()).lightness()
            col = QColor(0, 0, 0, 22) if lum > 128 else QColor(255, 255, 255, 26)
            pen = QPen(col, 0); p.setPen(pen)
            x = 0
            while x <= pr.width():
                p.drawLine(QPointF(x, 0), QPointF(x, pr.height())); x += g
            y = 0
            while y <= pr.height():
                p.drawLine(QPointF(0, y), QPointF(pr.width(), y)); y += g

    def handle_points(self, item):
        o = item.o; w, h = o['w'], o['h']
        loc = {'nw': (0, 0), 'n': (w / 2, 0), 'ne': (w, 0), 'e': (w, h / 2), 'se': (w, h), 's': (w / 2, h), 'sw': (0, h), 'w': (0, h / 2)}
        pts = {k: item.mapToScene(QPointF(*v)) for k, v in loc.items()}
        pts['rot'] = item.mapToScene(QPointF(w / 2, -22 / self.zoom))
        return pts

    def drawForeground(self, p, rect):
        win = self.win
        hi = self.palette().color(QPalette.Highlight)
        cos = QPen(hi, 0); cos.setCosmetic(True)
        sel = win.sel_items()
        for it in sel:
            poly = it.mapToScene(QRectF(0, 0, it.o['w'], it.o['h']))
            pn = QPen(hi, 1.5); pn.setCosmetic(True)
            if it.o.get('locked'): pn.setStyle(Qt.DashLine)
            p.setPen(pn); p.setBrush(Qt.NoBrush); p.drawPolygon(poly)
        if len(sel) == 1 and not sel[0].o.get('locked') and not win.editor:
            pts = self.handle_points(sel[0]); s = 4.5 / self.zoom
            p.setPen(cos)
            p.drawLine(pts['n'], pts['rot'])
            for k, pt in pts.items():
                p.setBrush(self.palette().color(QPalette.Base) if k != 'rot' else hi)
                pn = QPen(hi, 1.5); pn.setCosmetic(True); p.setPen(pn)
                if k == 'rot': p.drawEllipse(pt, s, s)
                else: p.drawRect(QRectF(pt.x() - s, pt.y() - s, 2 * s, 2 * s))
        for r_ in (self.marq, self.ghost):
            if r_:
                c = QColor(hi); c.setAlpha(40); p.setBrush(c); pn = QPen(hi, 1, Qt.DashLine); pn.setCosmetic(True); p.setPen(pn)
                p.drawRect(r_)
        # Grab grip at the page bottom edge: a short centred bar the user can drag to make
        # the page taller or shorter. Only on a normal page (not while editing a master).
        if not win.editor and not win.cur_master():
            pr = self.page_rect(); gw = 54 / self.zoom; th = 4 / self.zoom
            grip = QRectF(pr.width() / 2 - gw / 2, pr.height() - th / 2, gw, th)
            gc = QColor(hi); gc.setAlpha(150); p.setPen(Qt.NoPen); p.setBrush(gc)
            p.drawRoundedRect(grip, th / 2, th / 2)

    # -- hit testing
    def handle_at(self, vpos):
        sel = self.win.sel_items()
        if len(sel) != 1 or sel[0].o.get('locked'): return None
        for k, pt in self.handle_points(sel[0]).items():
            v = self.mapFromScene(pt)
            if abs(v.x() - vpos.x()) <= 6 and abs(v.y() - vpos.y()) <= 6: return k
        return None

    def obj_at(self, vpos, include_master=True):
        for it in self.items(vpos):
            if isinstance(it, ObjItem):
                return it
        return None

    def on_page_bottom(self, vpos):
        """True when the viewport point is on the page's bottom edge — the grab zone for
        dragging the page taller/shorter. Only on a normal page with the Pointer tool."""
        if self.win.editor or self.win.tool != 'pointer': return False
        pr = self.page_rect()
        bl = self.mapFromScene(QPointF(0, pr.height())); br = self.mapFromScene(QPointF(pr.width(), pr.height()))
        return abs(vpos.y() - bl.y()) <= 6 and (bl.x() - 12) <= vpos.x() <= (br.x() + 12)

    def snap(self, v):
        return round(v / 10) * 10 if self.win.snap_grid else round(v)

    # -- mouse
    def mousePressEvent(self, e):
        win = self.win; vpos = e.position().toPoint(); sp = self.mapToScene(vpos)
        if win._eyedrop:
            if e.button() == Qt.LeftButton:
                img = self.viewport().grab().toImage()
                r = img.devicePixelRatio() or 1
                win.eyedropped(img.pixelColor(int(vpos.x() * r), int(vpos.y() * r)).name())
            else:
                win.cancel_eyedropper()
            e.accept(); return
        if win.editor:
            if win.editor.sceneBoundingRect().contains(sp) and win.editor.isVisible():
                super().mousePressEvent(e); return
            win.finish_edit()
        self.setFocus()
        if e.button() == Qt.MiddleButton or (e.button() == Qt.LeftButton and win.tool == 'hand'):
            self.drag = dict(mode='pan', start=e.position(), h=self.horizontalScrollBar().value(), v=self.verticalScrollBar().value())
            self.viewport().setCursor(Qt.ClosedHandCursor); return
        if e.button() == Qt.RightButton:
            it = self.obj_at(vpos)
            if it and not it.master and it.o['id'] not in win.sel:
                win.select([it.o['id']])
            win.context_menu(e.globalPosition().toPoint()); return
        if e.button() != Qt.LeftButton: return
        if win.tool == 'pointer' and e.modifiers() & Qt.ControlModifier:
            it = self.obj_at(vpos)
            L = win.link_at(it, sp) if it else None
            if L: win.follow_link(L); return
        if win.tool == 'zoom':
            self.set_zoom(self.zoom / 1.25 if e.modifiers() & (Qt.ShiftModifier | Qt.AltModifier) else self.zoom * 1.25, vpos); return
        hk = self.handle_at(vpos)
        if hk and win.tool == 'pointer':
            it = win.sel_items()[0]
            self.drag = dict(mode='rot' if hk == 'rot' else 'resize', dir=hk, item=it, start=dict(it.o), pt=sp, snap=win.snapshot(), moved=False)
            return
        if win.tool == 'pointer' and self.on_page_bottom(vpos):
            self.drag = dict(mode='pageh', pt=sp, start_h=win.page_h(), snap=win.snapshot(), moved=False)
            return
        if win.tool == 'pointer':
            it = self.obj_at(vpos)
            if it and it.master:
                win.hint(f"That object belongs to the master page “{win.master_of(win.page())['name']}”. Edit the master page to change it.")
                it = None
            if it:
                oid = it.o['id']
                if e.modifiers() & Qt.ShiftModifier:
                    win.select([x for x in win.sel if x != oid] if oid in win.sel else win.sel + [oid]); return
                if oid not in win.sel: win.select([oid])
                movers = [x for x in win.sel_items() if not x.o.get('locked')]
                self.drag = dict(mode='move', pt=sp, starts=[(x, x.o['x'], x.o['y']) for x in movers], snap=win.snapshot(), moved=False)
            else:
                if not e.modifiers() & Qt.ShiftModifier: win.select([])
                self.drag = dict(mode='marq', pt=sp, base=list(win.sel))
        else:
            self.drag = dict(mode='create', pt=sp, tool=win.tool)

    def mouseMoveEvent(self, e):
        win = self.win; vpos = e.position().toPoint(); sp = self.mapToScene(vpos)
        win.set_pos_label(sp)
        d = self.drag
        if not d:
            if win.editor: super().mouseMoveEvent(e); return
            if win.tool == 'pointer':
                it = self.obj_at(vpos, include_master=True)
                L = win.link_at(it, sp) if it else None
                if L:
                    words, ok = win.describe_link(L)
                    win.hint(('⚠ Broken link: ' if ok is False else 'Link → ') + words + '   (Ctrl+click to follow it)')
                    self._over_link = L
                    if e.modifiers() & Qt.ControlModifier: self.viewport().setCursor(Qt.PointingHandCursor); return
                elif getattr(self, '_over_link', None):
                    self._over_link = None; win.update_hint()
            hk = self.handle_at(vpos) if win.tool == 'pointer' else None
            cur = {'nw': Qt.SizeFDiagCursor, 'se': Qt.SizeFDiagCursor, 'ne': Qt.SizeBDiagCursor, 'sw': Qt.SizeBDiagCursor,
                   'n': Qt.SizeVerCursor, 's': Qt.SizeVerCursor, 'e': Qt.SizeHorCursor, 'w': Qt.SizeHorCursor}.get(hk)
            if hk == 'rot': cur = Qt.CrossCursor
            if cur is None:
                cur = {'pointer': Qt.ArrowCursor, 'hand': Qt.OpenHandCursor, 'zoom': Qt.PointingHandCursor}.get(win.tool, Qt.CrossCursor)
                if win.tool == 'pointer':
                    it = self.obj_at(vpos)
                    if it and not it.master and not it.o.get('locked'): cur = Qt.SizeAllCursor
            if not hk and self.on_page_bottom(vpos): cur = Qt.SizeVerCursor   # page-height grip wins over empty-space
            self.viewport().setCursor(cur)
            return
        if d['mode'] == 'pan':
            delta = e.position() - d['start']
            self.horizontalScrollBar().setValue(int(d['h'] - delta.x())); self.verticalScrollBar().setValue(int(d['v'] - delta.y())); return
        dx, dy = sp.x() - d['pt'].x(), sp.y() - d['pt'].y()
        if d['mode'] == 'move':
            if not d['moved'] and abs(dx) + abs(dy) < 2 / self.zoom: return
            if not d['moved']: win.push_undo(d['snap']); d['moved'] = True
            if e.modifiers() & Qt.ShiftModifier:
                if abs(dx) > abs(dy): dy = 0
                else: dx = 0
            for it, x0, y0 in d['starts']:
                it.o['x'], it.o['y'] = self.snap(x0 + dx), self.snap(y0 + dy); it.sync()
            win.live_update()
        elif d['mode'] == 'resize':
            it, s0, k = d['item'], d['start'], d['dir']
            if not d['moved']: win.push_undo(d['snap']); d['moved'] = True
            a = math.radians(-s0.get('rot', 0))
            lx, ly = dx * math.cos(a) - dy * math.sin(a), dx * math.sin(a) + dy * math.cos(a)
            x, y, w, h = s0['x'], s0['y'], s0['w'], s0['h']
            if 'e' in k: w = s0['w'] + lx
            if 'w' in k: w = s0['w'] - lx; x = s0['x'] + lx
            if 's' in k: h = s0['h'] + ly
            if 'n' in k: h = s0['h'] - ly; y = s0['y'] + ly
            keep = (e.modifiers() & Qt.ShiftModifier) or (s0['type'] == 'artistic' and len(k) == 2) or (s0['type'] == 'picture' and len(k) == 2 and not e.modifiers() & Qt.ControlModifier)
            if keep and len(k) == 2 and s0['h']:
                ratio = s0['w'] / s0['h']
                if abs(w / ratio) > abs(h): h = w / ratio
                else: w = h * ratio
                if 'w' in k: x = s0['x'] + s0['w'] - w
                if 'n' in k: y = s0['y'] + s0['h'] - h
            minv = 2 if s0['type'] == 'line' else 8
            if w < minv:
                if 'w' in k: x -= (minv - w)
                w = minv
            if h < minv:
                if 'n' in k: y -= (minv - h)
                h = minv
            o = it.o
            o['x'], o['y'], o['w'], o['h'] = self.snap(x), self.snap(y), max(minv, self.snap(w) or minv), max(minv, self.snap(h) or minv)
            if o['type'] == 'artistic':
                o['size'] = max(4, round(s0['size'] * o['h'] / s0['h']))
            it.sync(); win.live_update()
        elif d['mode'] == 'rot':
            it = d['item']; c = it.mapToScene(QPointF(it.o['w'] / 2, it.o['h'] / 2))
            if not d['moved']: win.push_undo(d['snap']); d['moved'] = True
            ang = math.degrees(math.atan2(sp.y() - c.y(), sp.x() - c.x())) + 90
            if e.modifiers() & Qt.ShiftModifier: ang = round(ang / 15) * 15
            it.o['rot'] = round(((ang + 180) % 360) - 180, 1); it.sync(); win.live_update()
        elif d['mode'] == 'pageh':
            if not d['moved']: win.push_undo(d['snap']); d['moved'] = True
            newh = int(self.snap(max(200, d['start_h'] + dy)))
            win.set_page_height(newh)
            W = win.site['width']; self.scene().setSceneRect(QRectF(-300, -200, W + 600, newh + 400))
            win.live_update()
        elif d['mode'] in ('marq', 'create'):
            r_ = QRectF(d['pt'], sp).normalized()
            if d['mode'] == 'create' and e.modifiers() & Qt.ShiftModifier and d['tool'] in ('rect', 'ellipse', 'picture'):
                s_ = max(r_.width(), r_.height()); r_ = QRectF(r_.topLeft(), QSizeF(s_, s_))
            if d['mode'] == 'marq': self.marq = r_
            else: self.ghost = r_
            self.viewport().update()

    def mouseReleaseEvent(self, e):
        win = self.win; d = self.drag; self.drag = None
        if win.editor and not d: super().mouseReleaseEvent(e); return
        if not d: return
        sp = self.mapToScene(e.position().toPoint())
        if d['mode'] == 'pan':
            self.viewport().setCursor(Qt.OpenHandCursor if win.tool == 'hand' else Qt.ArrowCursor); return
        if d['mode'] == 'marq':
            r_ = self.marq; self.marq = None
            if r_ and r_.width() > 2:
                ids = [it.o['id'] for it in win.layer_items() if r_.contains(it.sceneBoundingRect().adjusted(2, 2, -2, -2)) and not it.o.get('hidden')]
                win.select(list(dict.fromkeys(d['base'] + ids)))
            else:
                self.viewport().update()
            return
        if d['mode'] == 'create':
            self.ghost = None
            r_ = QRectF(d['pt'], sp).normalized()
            win.create_object(d['tool'], d['pt'], sp, r_, e.modifiers() & Qt.ShiftModifier)
            return
        if d.get('moved'):
            win.dirty = True; win.refresh()

    def mouseDoubleClickEvent(self, e):
        win = self.win
        if win.editor: super().mouseDoubleClickEvent(e); return
        if win.tool != 'pointer': return
        it = self.obj_at(e.position().toPoint())
        if it and it.master:
            win.hint('This object is on the master page. Use Site ▸ Master Pages ▸ Edit to change it.'); return
        if it: win.edit_object(it.o)

    def wheelEvent(self, e):
        if e.modifiers() & Qt.ControlModifier:
            self.set_zoom(self.zoom * (1.15 if e.angleDelta().y() > 0 else 1 / 1.15), e.position().toPoint()); return
        super().wheelEvent(e)

    def keyPressEvent(self, e):
        win = self.win
        if win._eyedrop and e.key() == Qt.Key_Escape:
            win.cancel_eyedropper(); return
        if win.editor: super().keyPressEvent(e); return
        k = e.key()
        if k in (Qt.Key_Delete, Qt.Key_Backspace): win.delete_sel(); return
        if k == Qt.Key_Escape:
            win.set_tool('pointer'); win.select([]); return
        if k in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down) and win.sel:
            step = 10 if e.modifiers() & Qt.ShiftModifier else 1
            dx = {Qt.Key_Left: -step, Qt.Key_Right: step}.get(k, 0); dy = {Qt.Key_Up: -step, Qt.Key_Down: step}.get(k, 0)
            win.commit()
            for o in win.sel_objs():
                if not o.get('locked'): o['x'] += dx; o['y'] += dy
            win.refresh(); return
        if k in (Qt.Key_Return, Qt.Key_Enter) and len(win.sel) == 1:
            win.edit_object(win.sel_objs()[0]); return
        super().keyPressEvent(e)

    def resizeEvent(self, e):
        super().resizeEvent(e); self.win.update_rulers()


class Ruler(QWidget):
    def __init__(self, view, horiz):
        super().__init__()
        self.view, self.horiz, self.mouse = view, horiz, None
        if horiz: self.setFixedHeight(20)
        else: self.setFixedWidth(20)

    def paintEvent(self, ev):
        p = QPainter(self); pal = self.palette()
        bg = pal.color(QPalette.Window); fg = pal.color(QPalette.WindowText); dim = QColor(fg); dim.setAlpha(140)
        p.fillRect(self.rect(), bg)
        v = self.view; z = v.zoom
        o = v.mapFromScene(QPointF(0, 0))
        origin = o.x() if self.horiz else o.y()
        length = self.width() if self.horiz else self.height()
        major = next((m for m in (10, 20, 50, 100, 200, 500, 1000, 2000) if m * z >= 70), 2000)
        minor = major / (10 if major * z >= 100 else 5)
        # selection extent
        sel = v.win.sel_items()
        if sel:
            br = sel[0].sceneBoundingRect()
            for it in sel[1:]: br = br.united(it.sceneBoundingRect())
            a, b = (br.left(), br.right()) if self.horiz else (br.top(), br.bottom())
            hc = pal.color(QPalette.Highlight); hc.setAlpha(60)
            if self.horiz: p.fillRect(QRectF(origin + a * z, 0, (b - a) * z, 20), hc)
            else: p.fillRect(QRectF(0, origin + a * z, 20, (b - a) * z), hc)
        f = QFont(); f.setPixelSize(9); p.setFont(f)
        start = math.floor((-origin / z) / minor) * minor
        val = start
        while True:
            px = origin + val * z
            if px > length: break
            is_major = abs(val / major - round(val / major)) < 1e-6
            ln = 10 if is_major else 4
            p.setPen(dim)
            if self.horiz:
                p.drawLine(QPointF(px, 20 - ln), QPointF(px, 20))
                if is_major: p.setPen(fg); p.drawText(QPointF(px + 3, 9), f'{int(val)}')
            else:
                p.drawLine(QPointF(20 - ln, px), QPointF(20, px))
                if is_major:
                    p.save(); p.setPen(fg); p.translate(9, px + 3); p.rotate(90); p.drawText(QPointF(0, 0), f'{int(val)}'); p.restore()
            val += minor
        if self.mouse is not None:
            p.setPen(QPen(pal.color(QPalette.Highlight), 1))
            m = origin + self.mouse * z
            if self.horiz: p.drawLine(QPointF(m, 0), QPointF(m, 20))
            else: p.drawLine(QPointF(0, m), QPointF(20, m))
        p.setPen(pal.color(QPalette.Mid))
        if self.horiz: p.drawLine(0, 19, self.width(), 19)
        else: p.drawLine(19, 0, 19, self.height())

# ----------------------------------------------------------------------------
# Small widgets & dialogs
# ----------------------------------------------------------------------------

class ColorButton(QToolButton):
    def __init__(self, color, on_pick, title='Colour', allow_none=False, parent=None):
        super().__init__(parent)
        self.color, self.on_pick, self.title, self.allow_none = color, on_pick, title, allow_none
        self.setToolTip(title); self.setIcon(swatch_icon(color, 18)); self.setAutoRaise(True)
        # Every colour button gets a dropdown: choose in a dialog, pick from the
        # screen (eyedropper), and — when allowed — clear to None. The plain click
        # still opens the colour dialog, so existing behaviour is unchanged.
        m = QMenu(self)
        m.addAction('Choose colour…', self.pick)
        m.addAction(ticon(['color-picker', 'gtk-color-picker', 'tool-measure', 'input-tablet'], '⊙'),
                    'Pick from screen', self.pick_screen)
        if allow_none:
            m.addAction(swatch_icon('', 16), 'None', lambda: self.on_pick(''))
        self.setMenu(m); self.setPopupMode(QToolButton.MenuButtonPopup)
        self.clicked.connect(self.pick)

    def pick(self):
        # Build the colour dialog non-statically so we can drop an eyedropper
        # button right into it — "Pick from screen" sits in the popup itself,
        # next to the usual colour choices, not hidden in a menu.
        dlg = QColorDialog(QColor(self.color or '#ffffff'), self.window())
        dlg.setWindowTitle(self.title)
        dlg.setOption(QColorDialog.DontUseNativeDialog, True)   # so our button is shown
        eye = QPushButton(ticon(['color-picker', 'gtk-color-picker', 'tool-measure', 'input-tablet'], '⊙'),
                          '  Pick from screen')
        eye.setToolTip('Pick a colour from anywhere on your screen')
        def from_screen():
            hx = self._screen_hex()
            if hx:
                dlg.setCurrentColor(QColor(hx)); dlg.accept()
        eye.clicked.connect(from_screen)
        lay = dlg.layout()
        if lay is not None: lay.addWidget(eye)
        if dlg.exec() == QDialog.Accepted:
            c = dlg.currentColor()
            if c.isValid(): self.on_pick(c.name())

    @staticmethod
    def _screen_hex():
        """Grab one colour from anywhere on screen and return it as #rrggbb, or None.
        On Wayland (Hyprland) Qt's own eyedropper is unreliable, so shell out to a
        desktop picker: hyprpicker first, then grim+slurp."""
        if shutil.which('hyprpicker'):
            try:
                r = subprocess.run(['hyprpicker', '-a', '-f', 'hex'],
                                   capture_output=True, text=True, timeout=30)
                hx = ColorButton._valid_hex(r.stdout.strip())
                if hx: return hx
            except Exception:
                pass
        if shutil.which('grim') and shutil.which('slurp'):
            try:
                g = subprocess.run(['slurp', '-p'], capture_output=True, text=True, timeout=30)
                geom = g.stdout.strip()
                if geom:
                    f = os.path.join(tempfile.gettempdir(), 'webcreator_pick.png')
                    subprocess.run(['grim', '-g', geom, f], timeout=30, check=True)
                    img = QImage(f)
                    try: os.remove(f)
                    except OSError: pass
                    if not img.isNull():
                        return ColorButton._valid_hex(QColor(img.pixel(0, 0)).name())
            except Exception:
                pass
        return None

    def pick_screen(self):
        """Menu entry: pick a colour from the screen and apply it directly."""
        hx = self._screen_hex()
        if hx:
            self.on_pick(hx)

    @staticmethod
    def _valid_hex(s):
        s = (s or '').strip()
        if not s.startswith('#'): s = '#' + s
        return s.lower() if re.fullmatch(r'#[0-9a-fA-F]{6}', s) else None


def form_dialog(parent, title, rows, extra=None):
    dlg = QDialog(parent); dlg.setWindowTitle(title)
    lay = QVBoxLayout(dlg); form = QFormLayout(); lay.addLayout(form)
    for label, w in rows: form.addRow(label, w)
    if extra: lay.addWidget(extra)
    bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); bb.accepted.connect(dlg.accept); bb.rejected.connect(dlg.reject)
    lay.addWidget(bb)
    return dlg


class StartupAssistant(QDialog):
    def __init__(self, win):
        super().__init__(win)
        self.win = win; self.result_site = None; self.result_path = None; self.result_import = False; self.result_update = False
        self.result_webplus = None
        self.setWindowTitle(f'{APP} — Startup Assistant'); self.resize(1040, 660)
        root = QVBoxLayout(self)
        self.upd = QFrame(); self.upd.setAutoFillBackground(True)
        pal = self.upd.palette(); pal.setColor(QPalette.Window, pal.color(QPalette.Highlight))
        pal.setColor(QPalette.WindowText, pal.color(QPalette.HighlightedText)); self.upd.setPalette(pal)
        ul = QHBoxLayout(self.upd); ul.setContentsMargins(12, 8, 8, 8)
        ic = QLabel(); ic.setPixmap(ticon(['system-software-update', 'update-none', 'download'], '↓').pixmap(22, 22)); ul.addWidget(ic)
        self.upd_label = QLabel(); self.upd_label.setWordWrap(True); ul.addWidget(self.upd_label, 1)
        self.upd_btn = QPushButton(); self.upd_btn.clicked.connect(self.do_update); ul.addWidget(self.upd_btn)
        self.upd.hide(); root.addWidget(self.upd)
        top = QHBoxLayout(); root.addLayout(top, 1)
        self.nav = QListWidget(); self.nav.setFixedWidth(210); self.nav.setIconSize(QSize(32, 32)); self.nav.setSpacing(4)
        for icon, text in ((ticon(['template', 'folder-templates', 'document-new-from-template'], 'T'), 'Use Design Template'),
                           (ticon(['document-new'], '+'), 'Start New Site'),
                           (ticon(['document-open'], '↥'), 'Open Saved Site')):
            self.nav.addItem(QListWidgetItem(icon, text))
        top.addWidget(self.nav)
        self.stack = QStackedWidget(); top.addWidget(self.stack, 1)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)

        # Templates — Serif's five steps: pick a branch, pick a template,
        # pick a colour scheme, untick the pages you don't want, open it.
        tp = QWidget(); tl = QVBoxLayout(tp)
        h = QLabel('<b>Choose a design template</b><br>Pick a design, choose a colour scheme, '
                   'untick any pages you don’t want, then open it.')
        h.setWordWrap(True); tl.addWidget(h)
        row = QHBoxLayout(); tl.addLayout(row, 1)

        left = QVBoxLayout(); row.addLayout(left)
        self.tfind = QLineEdit(); self.tfind.setPlaceholderText('Find a template…')
        self.tfind.setClearButtonEnabled(True); self.tfind.setFixedWidth(240)
        self.tfind.textChanged.connect(self.filter_templates); left.addWidget(self.tfind)
        self.ttree = QTreeWidget(); self.ttree.setHeaderHidden(True); self.ttree.setFixedWidth(240)
        left.addWidget(self.ttree, 1)
        self.tsites = {}            # (what, which, scheme) -> built site, built once
        self.build_template_tree()

        mid = QVBoxLayout(); row.addLayout(mid, 1)
        self.tprev = QLabel(); self.tprev.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.tprev.setMinimumSize(QSize(300, 280)); self.tprev.setFrameShape(QFrame.StyledPanel)
        # Ignored, so the preview fits the pane rather than the pane growing to
        # fit the preview: these are 480 and 960px pages in the same dialog.
        self.tprev.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self._tprev_img = None
        mid.addWidget(self.tprev, 1)
        self.tcap = QLabel(); self.tcap.setWordWrap(True); self.tcap.setTextFormat(Qt.RichText)
        mid.addWidget(self.tcap)

        pc = QVBoxLayout(); row.addLayout(pc)
        pc.addWidget(QLabel('Colour scheme:'))
        self.tscheme = QComboBox(); self.tscheme.setFixedWidth(210)
        self.tscheme.currentIndexChanged.connect(self.scheme_changed); pc.addWidget(self.tscheme)
        pc.addWidget(QLabel('Pages to include:'))
        self.plist = QListWidget(); self.plist.setFixedWidth(210); pc.addWidget(self.plist, 1)
        ob = QPushButton(ticon(['document-open'], ''), 'Open Template')
        ob.setDefault(True); ob.clicked.connect(self.open_template); pc.addWidget(ob)
        self.ttree.currentItemChanged.connect(lambda *_: self.show_template())
        self.ttree.itemDoubleClicked.connect(lambda *_: self.open_template())
        self.stack.addWidget(tp)

        # New
        npg = QWidget(); nl = QFormLayout(npg)
        nl.addRow(QLabel('<b>Start a new, blank site</b>'))
        self.nname = QLineEdit('My Site'); nl.addRow('Site name:', self.nname)
        # Defaults come from the last site made (stored in settings), falling back to 960x1100.
        def_w = str(win.settings.value('defaultWidth', '960'))
        def_h = int(win.settings.value('defaultHeight', 1100))
        self.nwidth = QComboBox(); self.nwidth.addItems(['960', '1000', '1200']); self.nwidth.setEditable(True)
        if self.nwidth.findText(def_w) < 0: self.nwidth.addItem(def_w)
        self.nwidth.setCurrentText(def_w); nl.addRow('Page width (px):', self.nwidth)
        self.nheight = QSpinBox(); self.nheight.setRange(200, 20000); self.nheight.setValue(def_h); nl.addRow('Page height (px):', self.nheight)
        self.nlayout = QComboBox()
        self.nlayout.addItem('Full width (one column)', 'full')
        self.nlayout.addItem('Two columns', '2col')
        self.nlayout.addItem('Three columns', '3col')
        self.nlayout.setToolTip('Lays guide text frames on the first page so you can drop content into columns.')
        nl.addRow('Column layout:', self.nlayout)
        self.nresp = QCheckBox('Responsive — scales to fit any screen (phones, tablets, desktop)')
        self.nresp.setToolTip('Off = classic fixed-width static site. On = the whole design shrinks to fit narrow screens.\nYou can also change this at Publish time.')
        nl.addRow('Screen:', self.nresp)
        cb = QPushButton(ticon(['document-new'], ''), 'Create Site'); cb.clicked.connect(self.create_new); nl.addRow('', cb)
        self.stack.addWidget(npg)

        # Open
        op = QWidget(); ol = QVBoxLayout(op)
        ol.addWidget(QLabel('<b>Open a saved site</b>'))
        self.rlist = QListWidget(); ol.addWidget(self.rlist, 1)
        for path in win.recent_files():
            it = QListWidgetItem(ticon(['application-x-webc', 'text-html', 'document-open'], ''), f'{os.path.basename(path)}\n{os.path.dirname(path)}')
            it.setData(Qt.UserRole, path); self.rlist.addItem(it)
        if not self.rlist.count(): self.rlist.addItem('No recent sites yet.')
        self.rlist.itemDoubleClicked.connect(self.open_recent)
        bh = QHBoxLayout(); ol.addLayout(bh)
        b2 = QPushButton(ticon(['document-open-folder', 'folder-open'], ''), 'Browse…'); b2.clicked.connect(self.browse); bh.addWidget(b2)
        b3 = QPushButton(ticon(['document-import'], ''), 'Import Website Folder…'); b3.clicked.connect(self.import_site); bh.addWidget(b3)
        b4 = QPushButton(ticon(['document-open', 'document-import'], ''), 'Open WebPlus Site…')
        b4.setToolTip('Open a WebPlus .wpp publication as an editable site'); b4.clicked.connect(self.open_wpp)
        bh.addWidget(b4); bh.addStretch()
        self.stack.addWidget(op)

        bottom = QHBoxLayout(); root.addLayout(bottom)
        self.show_cb = QCheckBox('Show the Startup Assistant when the app opens')
        self.show_cb.setChecked(win.settings.value('showStartup', True, type=bool)); bottom.addWidget(self.show_cb); bottom.addStretch()
        openb = QPushButton(ticon(['document-open'], ''), 'Open')
        openb.setToolTip('Open the highlighted recent site (or Browse if none is selected)')
        openb.clicked.connect(self.open_highlighted)
        bottom.addWidget(openb)
        close = QPushButton('Close'); close.clicked.connect(self.reject); bottom.addWidget(close)
        self.nav.setCurrentRow(0); self.show_template()

        if getattr(win, 'update_source', None): self.show_update(win.update_version)

    def show_update(self, version):
        self.upd_label.setText(f'<b>A new version is available.</b> You have {VERSION}; version {version} is ready to install.')
        self.upd_btn.setText(f'Update to {version}'); self.upd.show()

    def do_update(self):
        self.result_update = True; self.accept()

    def done(self, r):
        self.win.settings.setValue('showStartup', self.show_cb.isChecked())
        if self.win.startup_dlg is self: self.win.startup_dlg = None
        super().done(r)

    # --- the template chooser ----------------------------------------------

    def build_template_tree(self):
        """The left-hand pane: our own designs, then Serif's own tree."""
        self.ttree.clear()
        ours = QTreeWidgetItem(self.ttree, ['Basic Templates'])
        for i, (name, kind, _fn) in enumerate(TEMPLATES):
            leaf = QTreeWidgetItem(ours, [f'{name} — {kind}'])
            leaf.setData(0, Qt.UserRole, ('ours', i))
        ours.setExpanded(True)
        for category, surfaces in serif_tree(chooser_only=False):
            node = QTreeWidgetItem(self.ttree, [category_label(category)])
            if not any(r.get('in_chooser') for _s, rows in surfaces for r in rows):
                node.setToolTip(0, 'Sample documents. Serif catalogued these but '
                                   'never offered them as something to start from.')
            for surface, rows in surfaces:
                under = QTreeWidgetItem(node, [surface or 'All']) if surface else node
                for r in rows:
                    leaf = QTreeWidgetItem(under, [r['name']])
                    leaf.setData(0, Qt.UserRole, ('serif', r['key']))
                    leaf.setToolTip(0, f"{len(r['pages'])} pages · {category_label(r['category'])}"
                                       + (f" · {r['surface']}" if r['surface'] else ''))
            node.setExpanded(category == 'Theme Layouts')
        first = ours.child(0)
        if first: self.ttree.setCurrentItem(first)

    def filter_templates(self, text):
        want = (text or '').strip().lower()
        it = QTreeWidgetItemIterator(self.ttree)
        while it.value():
            node = it.value()
            if node.data(0, Qt.UserRole):
                node.setHidden(bool(want) and want not in node.text(0).lower())
            it += 1
        for i in range(self.ttree.topLevelItemCount()):
            self.prune_branch(self.ttree.topLevelItem(i), bool(want))

    def prune_branch(self, node, searching):
        """Hide a branch with nothing left under it; open the ones with hits."""
        kids = [node.child(i) for i in range(node.childCount())]
        if not kids:
            return not node.isHidden()
        alive = [self.prune_branch(k, searching) for k in kids]
        node.setHidden(searching and not any(alive))
        if searching and any(alive): node.setExpanded(True)
        return any(alive)

    def chosen_template(self):
        it = self.ttree.currentItem()
        return it.data(0, Qt.UserRole) if it else None

    def template_site(self, what, which, scheme=None):
        """Build it once and keep it: 89 of these is too many to build eagerly."""
        key = (what, which, scheme)
        if key not in self.tsites:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                self.tsites[key] = (TEMPLATES[which][2]() if what == 'ours'
                                    else serif_site(serif_row(which), scheme))
            finally:
                QApplication.restoreOverrideCursor()
        return self.tsites[key]

    def show_template(self, keep_scheme=False):
        chosen = self.chosen_template()
        self.plist.clear()
        if not chosen:
            self.tprev.clear(); self.tcap.clear(); self.tscheme.clear(); return
        what, which = chosen
        if not keep_scheme:
            self.tscheme.blockSignals(True); self.tscheme.clear()
            if what == 'serif':
                self.tscheme.addItems(serif_schemes(serif_row(which)))
            self.tscheme.setEnabled(what == 'serif')
            self.tscheme.blockSignals(False)
        scheme = self.tscheme.currentText() if what == 'serif' else None
        s = self.template_site(what, which, scheme or None)
        self._tprev_img = render_page_image(s, s['pages'][0], 560,
                                            crop=int(s['width'] * 1.45))
        self.fit_preview()
        if what == 'serif':
            r = serif_row(which)
            self.tcap.setText(
                f"<b>{H.escape(r['name'])}</b> — {H.escape(category_label(r['category']))}, "
                f"{H.escape(r['surface'])}<br>{len(r['pages'])} pages, "
                f"{s['width']}px wide, in {H.escape(scheme or '')}.")
        else:
            name, kind, _ = TEMPLATES[which]
            self.tcap.setText(f"<b>{H.escape(name)}</b> — {H.escape(kind)}<br>"
                              f"{len(s['pages'])} pages, {s['width']}px wide.")
        for i, p in enumerate(s['pages']):
            it = QListWidgetItem('    ' * min(3, p.get('level') or 0) + p['title'])
            it.setData(Qt.UserRole, p['id']); it.setCheckState(Qt.Checked)
            if i == 0:          # a site with no home page is not a site
                it.setFlags(Qt.ItemIsEnabled)
                it.setToolTip('Every site has a home page.')
            else:
                it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            self.plist.addItem(it)

    def fit_preview(self):
        # resize() is called in __init__, before this pane exists.
        if getattr(self, '_tprev_img', None) is None:
            if hasattr(self, 'tprev'): self.tprev.clear()
            return
        pm = QPixmap.fromImage(self._tprev_img)
        box = self.tprev.contentsRect().size() - QSize(12, 12)
        if box.width() > 40 and box.height() > 40:
            pm = pm.scaled(box, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.tprev.setPixmap(pm)

    def resizeEvent(self, ev):
        super().resizeEvent(ev); self.fit_preview()

    def scheme_changed(self, *_):
        if self.tscheme.isEnabled(): self.show_template(keep_scheme=True)

    def open_template(self):
        chosen = self.chosen_template()
        if not chosen: return
        what, which = chosen
        scheme = self.tscheme.currentText() if what == 'serif' else None
        s = copy.deepcopy(self.template_site(what, which, scheme or None))
        ticked = {self.plist.item(j).data(Qt.UserRole) for j in range(self.plist.count())
                  if self.plist.item(j).checkState() == Qt.Checked}
        ticked.add(s['pages'][0]['id'])
        # Unticking a page takes its sub-pages with it. The alternative is a
        # sub-page with no parent — in the Site tree, in the breadcrumb and in
        # every navigation bar on the site, which is where it would be seen.
        keep, dropped_at = set(), None
        for p in s['pages']:
            level = p.get('level') or 0
            if dropped_at is not None and level > dropped_at:
                continue
            dropped_at = None
            if p['id'] in ticked: keep.add(p['id'])
            else: dropped_at = level
        if not keep:
            QMessageBox.information(self, APP, 'Tick at least one page to include.'); return
        s['pages'] = [p for p in s['pages'] if p['id'] in keep]
        for o in [o for p in s['pages'] for o in p['objects']] + [o for m in s['masters'] for o in m['objects']]:
            if o.get('link') and o['link']['type'] == 'page' and o['link']['target'] not in keep: o['link'] = None
        if s['pages'] and not any(p['file'] == 'index.html' for p in s['pages']): s['pages'][0]['file'] = 'index.html'
        if s['pages'][0].get('level'): s['pages'][0]['level'] = 0
        self.result_site = s; self.accept()

    def create_new(self):
        try: w = max(320, min(4000, int(self.nwidth.currentText())))
        except ValueError: w = 960
        h = self.nheight.value()
        s = tpl_blank(self.nname.text().strip() or 'My Site', w, h)
        s['responsive'] = self.nresp.isChecked()
        # remember the size as the default for next time
        self.win.settings.setValue('defaultWidth', str(w)); self.win.settings.setValue('defaultHeight', h)
        # column layout: drop guide text frames on the first page
        layout = self.nlayout.currentData()
        ncol = {'2col': 2, '3col': 3}.get(layout, 1)
        if ncol > 1:
            margin, gap, top = 40, 24, 120
            colw = (w - 2 * margin - gap * (ncol - 1)) // ncol
            page = s['pages'][0]
            page.setdefault('objects', [])
            for i in range(ncol):
                x = margin + i * (colw + gap)
                page['objects'].append(mk('text', x, top, colw, max(300, h - top - 60),
                                          html=f'<p>Column {i + 1} — click to edit, or drag other items into place.</p>'))
        self.result_site = s
        self.accept()

    def open_recent(self, it):
        if it and it.data(Qt.UserRole): self.result_path = it.data(Qt.UserRole); self.accept()

    def open_highlighted(self):
        """Open the highlighted recent site. If none is selected, fall back to Browse."""
        it = self.rlist.currentItem()
        if it and it.data(Qt.UserRole):
            self.open_recent(it)
        else:
            self.browse()

    def import_site(self):
        self.result_import = True; self.accept()

    def open_wpp(self):
        root = self.win.webplus_root()
        if not root: return
        last = self.win.settings.value('wppDir', os.path.expanduser('~'))
        path, _ = QFileDialog.getOpenFileName(self, 'Open WebPlus Site', last,
                                              f'WebPlus publications (*{WPP_EXT});;All files (*)')
        if not path: return
        self.win.settings.setValue('wppDir', os.path.dirname(path))
        self.result_webplus = (path, root); self.accept()

    def browse(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Open Site', os.path.expanduser('~'), f'WEBcreator sites (*{EXT});;All files (*)')
        if path: self.result_path = path; self.accept()

# ----------------------------------------------------------------------------
# Main window
# ----------------------------------------------------------------------------

STANDARD = ['#000000', '#3a3a3a', '#757575', '#b0b0b0', '#e0e0e0', '#ffffff', '#7f1d1d', '#c0392b', '#e67e22', '#f1c40f',
            '#27ae60', '#16a085', '#2980b9', '#2c3e50', '#8e44ad', '#d35400', '#f5e6c8', '#dfe8e1']


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings(ORG, 'WEBcreator')
        self.site = tpl_blank()
        self.path = None; self.dirty = False
        self.undo, self.redo = [], []
        self.cur_page = self.site['pages'][0]['id']
        self.edit_master = None
        self.sel = []
        self.tool = 'pointer'
        self.show_grid = self.settings.value('grid', False, type=bool)
        self.snap_grid = self.settings.value('snap', True, type=bool)
        self.editor = None; self.edit_id = None; self.edit_snap = None
        self._eyedrop = False
        self.clip = []
        self.items = {}
        self._ui_pending = False; self._updating = False
        self.sw_mode = 'fill'
        self.preview_dir = tempfile.mkdtemp(prefix='webcreator-preview-')
        self.startup_dlg = None

        self.setWindowIcon(ticon(['applications-development-web', 'text-html', 'applications-internet'], 'W'))
        self.resize(1360, 860)
        self.build_canvas_area()
        self.build_actions()
        self.build_menus()
        self.build_toolbars()
        self.build_studio()
        self.build_status()
        self.restore_layout()
        self.style_separators()
        self.flatten_dock_tabs()
        self.refresh()
        QTimer.singleShot(0, self.flatten_dock_tabs)   # again once the tab bars are realised
        QTimer.singleShot(0, self.after_show)

    # ------------------------------------------------------------ helpers
    def page(self):
        return next((p for p in self.site['pages'] if p['id'] == self.cur_page), self.site['pages'][0])

    def master_of(self, p):
        return next((m for m in self.site['masters'] if m['id'] == p.get('master')), self.site['masters'][0])

    def cur_master(self):
        return next((m for m in self.site['masters'] if m['id'] == self.edit_master), None) if self.edit_master else None

    def layer(self):
        m = self.cur_master()
        return m['objects'] if m else self.page()['objects']

    def page_h(self):
        return self.site['height'] if self.edit_master else (self.page().get('height') or self.site['height'])

    def set_page_height(self, h):
        """Set the height of the current page (or the site default when editing a master).
        Used by dragging the page's bottom edge."""
        h = int(max(200, h))
        if self.edit_master: self.site['height'] = h
        else: self.page()['height'] = h

    def palette_accent(self):
        """Pick the most saturated 'accent' colour from the site palette (skipping
        whites/greys/near-black) for call-to-action buttons. Falls back to the app teal."""
        best, bs = '#2a7d6b', -1
        for hx in self.site.get('palette', []):
            c = QColor(hx)
            if not c.isValid(): continue
            _, s, v, _ = c.getHsv()
            if s < 60 or v < 40: continue
            if s > bs: best, bs = hx, s
        return best

    def ink_for(self, hx):
        """Black or white text, whichever reads better on the given background colour."""
        c = QColor(hx); lum = 0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()
        return '#ffffff' if lum < 150 else '#222222'

    def page_bg(self):
        m = self.cur_master()
        if m: return m.get('bg') or self.site.get('bg') or '#ffffff'
        p = self.page(); return p.get('bg') or self.master_of(p).get('bg') or self.site.get('bg') or '#ffffff'

    def find(self, oid):
        for o in self.layer():
            if o['id'] == oid: return o
        return None

    def sel_objs(self):
        return [o for o in self.layer() if o['id'] in self.sel]

    def sel_items(self):
        return [self.items[i] for i in self.sel if i in self.items and not self.items[i].master]

    def layer_items(self):
        return [it for it in self.items.values() if not it.master]

    def snapshot(self):
        return json.dumps({k: v for k, v in self.site.items() if k != 'assets'})

    def push_undo(self, snap):
        self.undo.append(snap); self.undo = self.undo[-120:]; self.redo.clear(); self.dirty = True

    def commit(self):
        self.push_undo(self.snapshot())

    def restore(self, snap):
        assets = self.site.get('assets', {}); self.site = json.loads(snap); self.site['assets'] = assets

    def hint(self, text):
        self.hint_label.setText(text)

    # ------------------------------------------------------------ build UI
    def build_canvas_area(self):
        self.view = Canvas(self)
        self.rx, self.ry = Ruler(self.view, True), Ruler(self.view, False)
        corner = QWidget(); corner.setFixedSize(20, 20)
        self.banner = QFrame(); bl = QHBoxLayout(self.banner); bl.setContentsMargins(10, 6, 10, 6)
        self.banner.setAutoFillBackground(True)
        pal = self.banner.palette(); pal.setColor(QPalette.Window, pal.color(QPalette.Highlight)); pal.setColor(QPalette.WindowText, pal.color(QPalette.HighlightedText))
        self.banner.setPalette(pal)
        self.banner_label = QLabel(); bl.addWidget(self.banner_label, 1)
        bb = QPushButton('Back to page'); bb.clicked.connect(lambda: self.goto_page(self.cur_page)); bl.addWidget(bb)
        self.banner.hide()
        w = QWidget(); g = QGridLayout(w); g.setContentsMargins(0, 0, 0, 0); g.setSpacing(0)
        g.addWidget(self.banner, 0, 0, 1, 2)
        g.addWidget(corner, 1, 0); g.addWidget(self.rx, 1, 1); g.addWidget(self.ry, 2, 0); g.addWidget(self.view, 2, 1)
        self.ruler_widgets = [corner, self.rx, self.ry]
        # An HTML source view that the toolbar toggle can swap in for the canvas.
        self.html_view = QPlainTextEdit(); self.html_view.setReadOnly(True)
        self.html_view.setLineWrapMode(QPlainTextEdit.NoWrap)
        mono = QFont('monospace'); mono.setStyleHint(QFont.Monospace); mono.setPointSize(10)
        self.html_view.setFont(mono)
        self.stack = QStackedWidget(); self.stack.addWidget(w); self.stack.addWidget(self.html_view)
        self.setCentralWidget(self.stack)
        self.view.setFocus()

    def toggle_html_view(self):
        """Swap the design canvas for a read-only view of the current page's HTML."""
        showing_html = self.stack.currentIndex() == 1
        if showing_html:
            self.stack.setCurrentIndex(0); self.view.setFocus()
            if 'htmlview' in self.a: self.a['htmlview'].setChecked(False)
            return
        if self.editor: self.finish_edit()
        p = self.page()
        if not p:
            self.hint('Open a page first.');
            if 'htmlview' in self.a: self.a['htmlview'].setChecked(False)
            return
        # Render the page's HTML exactly as it would publish.
        try:
            imgs = {}
            def img(key): return 'images/' + (self.site.get('assetnames', {}).get(key) or key)
            src = page_html(self.site, p, img)
        except Exception as ex:
            self.hint(f'Could not render HTML: {ex}'); return
        self.html_view.setPlainText(src)
        self.stack.setCurrentIndex(1)
        if 'htmlview' in self.a: self.a['htmlview'].setChecked(True)

    def act(self, text, slot, shortcut=None, icon=None, checkable=False, tip=None):
        a = QAction(text, self)
        if icon: a.setIcon(ticon(icon if isinstance(icon, list) else [icon], ''))
        if shortcut: a.setShortcut(QKeySequence(shortcut))
        if checkable: a.setCheckable(True)
        if tip: a.setStatusTip(tip)
        a.triggered.connect(slot)
        return a

    def build_actions(self):
        A = self.act
        self.a = dict(
            new=A('&New Site…', self.startup, QKeySequence.New, 'document-new'),
            open=A('&Open…', self.open_dialog, QKeySequence.Open, 'document-open'),
            save=A('&Save', self.save, QKeySequence.Save, 'document-save'),
            saveas=A('Save &As…', self.save_as, QKeySequence.SaveAs, 'document-save-as'),
            import_=None,
            siteprops=A('Settings…', self.site_props, None, ['configure', 'preferences-system', 'document-properties']),
            checklinks=A('Check &Links…', self.check_links, None, ['tools-check-spelling', 'insert-link', 'link']),
            prevpage=A('Preview &Page in Browser', self.preview_page, 'F12', ['document-preview', 'view-preview']),
            prevsite=A('Preview &Site in Browser', self.preview_site, 'Shift+F12', ['internet-web-browser', 'applications-internet']),
            publish=A('&Publish…', self.publish_disk, None, ['document-export', 'folder-publicshare']),
            quit=A('&Quit', self.close, QKeySequence.Quit, 'application-exit'),
            undo=A('&Undo', self.do_undo, QKeySequence.Undo, 'edit-undo'),
            redo=A('&Redo', self.do_redo, QKeySequence.Redo, 'edit-redo'),
            cut=A('Cu&t', self.cut, QKeySequence.Cut, 'edit-cut'),
            copy=A('&Copy', self.copy, QKeySequence.Copy, 'edit-copy'),
            paste=A('&Paste', self.paste, QKeySequence.Paste, 'edit-paste'),
            dup=A('D&uplicate', self.duplicate, 'Ctrl+D', 'edit-duplicate'),
            delete=A('&Delete\tDel', self.delete_sel, None, 'edit-delete'),
            selall=A('Select &All', self.select_all, QKeySequence.SelectAll, 'edit-select-all'),
            rulers=A('&Rulers', self.toggle_rulers, None, None, True),
            grid=A('&Grid', self.toggle_grid, None, 'view-grid', True),
            snap=A('&Snap to Grid', self.toggle_snap, None, 'snap-to-grid', True),
            zin=A('Zoom &In', lambda: self.view.set_zoom(self.view.zoom * 1.25), QKeySequence.ZoomIn, 'zoom-in'),
            zout=A('Zoom &Out', lambda: self.view.set_zoom(self.view.zoom / 1.25), QKeySequence.ZoomOut, 'zoom-out'),
            z100=A('&Actual Size', lambda: self.view.set_zoom(1.0), 'Ctrl+1', 'zoom-original'),
            zfit=A('&Fit Page Width', self.view.fit_width, 'Ctrl+0', 'zoom-fit-width'),
            newpage=A('&Page…', self.insert_page_dialog, 'Ctrl+Shift+N', 'document-new'),
            index_page=A('&Index Page', self.insert_index_page, None, ['view-list-tree', 'view-list-text', 'format-list-unordered']),
            link=A('&Hyperlink…', self.hyperlink_dialog, 'Ctrl+K', ['insert-link', 'link']),
            pageprops=A('Page P&roperties…', lambda: self.page_props(self.page()), None, 'document-properties'),
            bold=A('&Bold', lambda: self.text_style('bold'), QKeySequence.Bold, 'format-text-bold', True),
            italic=A('&Italic', lambda: self.text_style('italic'), QKeySequence.Italic, 'format-text-italic', True),
            underline=A('&Underline', lambda: self.text_style('underline'), QKeySequence.Underline, 'format-text-underline', True),
            aleft=A('Align &Left', lambda: self.set_prop('align', 'left'), None, 'format-justify-left'),
            acenter=A('Align &Centre', lambda: self.set_prop('align', 'center'), None, 'format-justify-center'),
            aright=A('Align &Right', lambda: self.set_prop('align', 'right'), None, 'format-justify-right'),
            ajust=A('&Justify', lambda: self.set_prop('align', 'justify'), None, 'format-justify-fill'),
            list_disc=A('• Bullet (disc)', lambda: self.text_list('disc'), None, 'format-list-unordered'),
            list_circle=A('◦ Bullet (circle)', lambda: self.text_list('circle'), None, 'format-list-unordered'),
            list_square=A('▪ Bullet (square)', lambda: self.text_list('square'), None, 'format-list-unordered'),
            list_decimal=A('1. 2. 3. (numbers)', lambda: self.text_list('decimal'), None, 'format-list-ordered'),
            list_loweralpha=A('a. b. c. (lower letters)', lambda: self.text_list('lower-alpha'), None, 'format-list-ordered'),
            list_upperalpha=A('A. B. C. (upper letters)', lambda: self.text_list('upper-alpha'), None, 'format-list-ordered'),
            list_lowerroman=A('i. ii. iii. (lower roman)', lambda: self.text_list('lower-roman'), None, 'format-list-ordered'),
            list_upperroman=A('I. II. III. (upper roman)', lambda: self.text_list('upper-roman'), None, 'format-list-ordered'),
            list_none=A('Remove list', lambda: self.text_list('none'), None, 'edit-clear'),
            front=A('Bring to &Front', lambda: self.order('front'), 'Ctrl+Shift+]', 'object-order-front'),
            fwd=A('Forward &One', lambda: self.order('fwd'), 'Ctrl+]', 'object-order-raise'),
            back1=A('Back O&ne', lambda: self.order('back1'), 'Ctrl+[', 'object-order-lower'),
            back=A('Send to &Back', lambda: self.order('back'), 'Ctrl+Shift+[', 'object-order-back'),
            about=A(f'&About {APP}', self.about, None, 'help-about'),
        )
        self.a['delete'].setIconText('Delete')
        self.a['import'] = self.act('&Import Website Folder…', self.import_folder, 'Ctrl+Shift+I', ['document-import', 'folder-download'])
        self.a['openwpp'] = self.act('Open &WebPlus Site…', self.open_webplus, 'Ctrl+Shift+O',
                                     ['document-open', 'document-import'],
                                     tip='Open a WebPlus .wpp publication as an editable site')
        del self.a['import_']
        self.a['rulers'].setChecked(self.settings.value('rulers', True, type=bool))
        self.a['grid'].setChecked(self.show_grid); self.a['snap'].setChecked(self.snap_grid)
        for k in ('cut', 'copy', 'paste', 'undo', 'redo', 'selall', 'bold', 'italic', 'underline'):
            self.a[k].setShortcutContext(Qt.WindowShortcut)

    def build_menus(self):
        mb = self.menuBar(); a = self.a
        def menu(title, items):
            m = mb.addMenu(title)
            for it in items:
                if it is None: m.addSeparator()
                elif isinstance(it, tuple): sub = m.addMenu(it[0]); [sub.addAction(x) if x else sub.addSeparator() for x in it[1]]
                else: m.addAction(it)
            return m
        menu('&File', [a['new'], a['open'], self.recent_menu_action(), a['openwpp'], a['import'], None, a['save'], a['saveas'], None, a['checklinks'], None,
                       a['prevpage'], a['prevsite'], a['publish'], None, a['quit']])
        menu('&Edit', [a['undo'], a['redo'], None, a['cut'], a['copy'], a['paste'], a['dup'], a['delete'], None, a['selall']])
        self.view_menu = menu('&View', [a['rulers'], a['grid'], a['snap'], None, a['zin'], a['zout'], a['z100'], a['zfit'], None])
        ins = []
        for tid, label, *_ in [t for t in TOOLS if t[0] and t[0] not in ('pointer', 'hand', 'zoom')]:
            ins.append(self.act(label, lambda _=False, t=tid: self.insert_default(t), None, None))
        # Contact-details submenu: drops a text frame showing a field from Site Properties
        contact_acts = [self.act(lbl, lambda _=False, fk=fld: self.insert_contact(fk), None, None)
                        for fld, lbl in (('name', 'Author / Name'), ('email', 'Email'), ('phone', 'Phone'),
                                         ('address', 'Address'), ('website', 'Website'), ('all', 'All contact details'))]
        menu('&Insert', [a['newpage'], a['index_page'], None] + ins + [None, ('Contact details', contact_acts), None, a['link']])
        list_sub = [a['list_disc'], a['list_circle'], a['list_square'], None,
                    a['list_decimal'], a['list_loweralpha'], a['list_upperalpha'],
                    a['list_lowerroman'], a['list_upperroman'], None, a['list_none']]
        menu('F&ormat', [a['bold'], a['italic'], a['underline'], None, a['aleft'], a['acenter'], a['aright'], a['ajust'],
                         None, ('Lists / Bullets', list_sub), None, a['pageprops']])
        al = [self.act(n, lambda _=False, k=k: self.align(k), None, ic) for k, n, ic in (
            ('left', 'Align Left Edges', 'align-horizontal-left'), ('hcenter', 'Align Centres Horizontally', 'align-horizontal-center'),
            ('right', 'Align Right Edges', 'align-horizontal-right'), ('top', 'Align Top Edges', 'align-vertical-top'),
            ('vcenter', 'Align Middles Vertically', 'align-vertical-center'), ('bottom', 'Align Bottom Edges', 'align-vertical-bottom'),
            ('page', 'Centre on Page Horizontally', 'align-horizontal-center'))]
        self.a['lock'] = self.act('&Lock / Unlock', self.toggle_lock, 'Ctrl+L', ['object-locked', 'lock'])
        self.a['tomaster'] = self.act('Move Repeated Objects to &Master Page…', self.move_common_to_master, None, ['document-multiple', 'edit-copy'])
        menu('&Arrange', [a['front'], a['fwd'], a['back1'], a['back'], None, ('Align', al), None, self.a['lock'], None, self.a['tomaster']])
        self.a['seo_page'] = self.act('&This Page’s SEO…', self.seo_dialog, None, ['text-html', 'find', 'edit-find'])
        self.a['seo_page'].setToolTip('Search-engine title, description, focus keyword and social preview for this page')
        self.a['seo_site'] = self.act('&Site-wide SEO…', self.site_seo_dialog, None, ['configure', 'preferences-system'])
        self.a['seo_site'].setToolTip('Base web address, default social image, Twitter handle and organisation details')
        self.a['seo_auto'] = self.act('&Auto-generate SEO for all pages…', self.auto_seo, None, ['tools-wizard', 'system-run', 'text-html'])
        self.a['seo_auto'].setToolTip('Fill in titles, descriptions and keywords for every page automatically, then publish')
        menu('&SEO', [self.a['seo_auto'], None, self.a['seo_page'], None, self.a['seo_site']])
        self.a['htmlview'] = self.act('View &HTML', self.toggle_html_view, None, ['text-html', 'code-context', 'view-source'], checkable=True)
        self.a['htmlview'].setToolTip('Show the HTML source of this page (toggle)')
        self.a['update'] = self.act('Update Available', self.install_update, None, ['system-software-update', 'update-none', 'download'])
        self.a['update'].setVisible(False)
        self.a['checkupdate'] = self.act('Check for &Updates…', lambda: self.check_updates(quiet=False), None, ['system-software-update', 'view-refresh'])
        self.a['updatesettings'] = self.act('&Settings…', self.update_settings, None, ['configure', 'preferences-system'])
        self.a['donate'] = self.act('&Buy Me a Coffee  ☕', lambda: open_external('https://buymeacoffee.com/janszafranski'),
                                    None, ['help-donate', 'emblem-favorite', 'face-smile-big'])
        self.a['donate'].setToolTip('Enjoying WEBcreator? Buy its maker a coffee — opens buymeacoffee.com in your browser')
        menu('&Help', [self.a['update'], self.a['checkupdate'], self.a['updatesettings'], None, a['about'], None, self.a['donate']])

    def recent_menu_action(self):
        self.recent_menu = QMenu('Open &Recent', self)
        self.recent_menu.aboutToShow.connect(self.fill_recent)
        return self.recent_menu.menuAction()

    def fill_recent(self):
        self.recent_menu.clear()
        for p in self.recent_files():
            self.recent_menu.addAction(os.path.basename(p), lambda _=False, p=p: self.maybe_save() and self.load_path(p))
        if not self.recent_files(): self.recent_menu.addAction('(none)').setEnabled(False)

    def build_toolbars(self):
        # Standard toolbar
        tb = QToolBar('Standard'); tb.setObjectName('standard'); tb.setIconSize(QSize(20, 20)); self._std_toolbar = tb
        for k in ('new', 'open', 'save', None, 'undo', 'redo', None, 'cut', 'copy', 'paste', None, 'prevsite', 'publish', 'htmlview', None, 'update'):
            tb.addAction(self.a[k]) if k else tb.addSeparator()
        hw = tb.widgetForAction(self.a['htmlview'])
        if hw: hw.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.a['htmlview'].setIconText('HTML')
        uw = tb.widgetForAction(self.a['update'])
        if uw:
            uw.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            f = uw.font(); f.setBold(True); uw.setFont(f)
        tb.widgetForAction(self.a['prevsite']).setToolButtonStyle(Qt.ToolButtonTextBesideIcon) if tb.widgetForAction(self.a['prevsite']) else None
        self.a['prevsite'].setIconText('Preview'); self.a['publish'].setIconText('Publish')
        for k in ('prevsite', 'publish'):
            w = tb.widgetForAction(self.a[k])
            if w: w.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.addToolBar(Qt.TopToolBarArea, tb)
        # Insert toolbar sits alongside Standard on row 1. Only non-duplicate actions —
        # the object-insert icons already live on the left tool rail.
        ins = QToolBar('Insert'); ins.setObjectName('insert'); ins.setIconSize(QSize(20, 20))
        ss = QAction(ticon(['view-list-tree', 'gnumeric-object-matrix', 'view-sort-ascending'], '⊞'), 'Site Structure', self)
        ss.setToolTip('Site Structure — show the Site / Pages panel'); ss.triggered.connect(self.show_site_structure)
        ins.addAction(ss); ins.widgetForAction(ss).setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        ins.addSeparator()
        for k in ('aleft', 'acenter', 'aright'): ins.addAction(self.a[k])
        coffee = QAction(ticon(['help-donate', 'emblem-favorite', 'face-smile-big'], '☕'), 'Buy Me a Coffee', self)
        coffee.setToolTip('Insert a “Buy me a coffee” button, matched to the site palette (asks for your page link the first time)')
        coffee.triggered.connect(self.insert_coffee_button); self.a['coffee'] = coffee
        ins.addSeparator(); ins.addAction(coffee)
        cw = ins.widgetForAction(coffee)
        if cw: cw.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.addToolBar(Qt.TopToolBarArea, ins)
        # Context toolbar — same row; all top toolbars wrap onto more rows only when
        # the window is too narrow to hold them.
        self.ctx = QToolBar('Context'); self.ctx.setObjectName('context'); self.ctx.setIconSize(QSize(18, 18))
        self.addToolBar(Qt.TopToolBarArea, self.ctx)
        # Tools toolbar
        tt = QToolBar('Tools'); tt.setObjectName('tools'); tt.setIconSize(QSize(22, 22)); tt.setOrientation(Qt.Vertical)
        self.tool_group = QActionGroup(self); self.tool_actions = {}
        for t in TOOLS:
            if t[0] is None: tt.addSeparator(); continue
            tid, label, names, glyph, tip = t
            a = QAction(ticon(names, glyph), label, self); a.setCheckable(True); a.setToolTip(f'{label}\n{tip}')
            a.triggered.connect(lambda _=False, tid=tid: self.set_tool(tid))
            self.tool_group.addAction(a); tt.addAction(a); self.tool_actions[tid] = a
        self.tool_actions['pointer'].setChecked(True)
        self.addToolBar(Qt.LeftToolBarArea, tt)
        # Serif-suite toolbar — separate Serif programs (PhotoPlus / PhotoLab /
        # Cutout Studio) with no Linux equivalent, so the buttons explain they're unavailable.
        photo = QToolBar('Photo tools'); photo.setObjectName('phototools'); photo.setIconSize(QSize(20, 20))
        for name, icons, glyph in (
            ('Edit Properties', ['document-properties', 'document-edit'], '≡'),
            ('PhotoLab', ['darktable', 'applications-graphics'], '◉'),
            ('Cutout Studio', ['edit-cut', 'gimp-tool-scissors'], '✂'),
            ('Position Image', ['transform-move', 'object-align-horizontal-center'], '✥')):
            pa = QAction(ticon(icons, glyph), name, self); pa.setToolTip(f'{name} — part of the Serif suite, not available in this clone')
            pa.triggered.connect(lambda _=False, n=name: self.serif_stub(n)); photo.addAction(pa)
            w = photo.widgetForAction(pa)
            if w: w.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.addToolBar(Qt.TopToolBarArea, photo)
        # Placeholder tools in the left rail, mirroring WebPlus's fuller tool set.
        tt.addSeparator()
        for name, glyph in (('Rotate', '⟳'), ('Node Edit', '✎'), ('Crop', '⌗'), ('Pen / Curve', '✐'), ('Hotspot', '⬚'), ('Rollover', '◳')):
            pt = QAction(ticon([], glyph), name, self); pt.setToolTip(f'{name} — not available in this clone yet')
            pt.triggered.connect(lambda _=False, n=name: self.hint(f'The {n} tool isn’t available in this clone yet.')); tt.addAction(pt)
        for t in (tb, ins, self.ctx, photo, tt):
            t.setMovable(True); self.view_menu.addAction(t.toggleViewAction())

    def build_status(self):
        sb = self.statusBar()
        self.hint_label = QLabel(); self.hint_label.setTextInteractionFlags(Qt.NoTextInteraction)
        sb.addWidget(self.hint_label, 1)
        self.pos_label = QLabel(); self.pos_label.setMinimumWidth(130)
        f = self.pos_label.font(); f.setFamily('monospace'); f.setStyleHint(QFont.Monospace); self.pos_label.setFont(f)
        sb.addPermanentWidget(self.pos_label)
        self.page_label = QLabel(); sb.addPermanentWidget(self.page_label)
        zo = QToolButton(); zo.setDefaultAction(self.a['zout']); zo.setAutoRaise(True); sb.addPermanentWidget(zo)
        self.zoom_box = QComboBox(); self.zoom_box.setEditable(True); self.zoom_box.setFixedWidth(84)
        self.zoom_box.addItems(['25%', '50%', '75%', '100%', '150%', '200%', '400%', 'Page width'])
        self.zoom_box.activated.connect(self.zoom_box_chosen)
        self.zoom_box.lineEdit().returnPressed.connect(lambda: self.zoom_box_chosen())
        sb.addPermanentWidget(self.zoom_box)
        zi = QToolButton(); zi.setDefaultAction(self.a['zin']); zi.setAutoRaise(True); sb.addPermanentWidget(zi)

    def zoom_box_chosen(self, *_):
        t = self.zoom_box.currentText().strip()
        if t.lower().startswith('page'): self.view.fit_width(); return
        try: self.view.set_zoom(float(t.rstrip('%')) / 100)
        except ValueError: self.zoom_changed()

    def zoom_changed(self):
        self.zoom_box.blockSignals(True); self.zoom_box.setEditText(f'{round(self.view.zoom * 100)}%'); self.zoom_box.blockSignals(False)
        self.update_rulers()

    def set_pos_label(self, sp):
        self.pos_label.setText(f'X {sp.x():6.0f}  Y {sp.y():6.0f}')
        self.rx.mouse, self.ry.mouse = sp.x(), sp.y(); self.rx.update(); self.ry.update()

    def update_rulers(self):
        self.rx.update(); self.ry.update()

    # ------------------------------------------------------------ Studio
    def dock(self, title, widget, name):
        d = QDockWidget(title, self); d.setObjectName(name); d.setWidget(widget)
        d.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.addDockWidget(Qt.RightDockWidgetArea, d); return d

    def _hide_dock_title(self, d):
        """Drop a dock's visible title. windowTitle='' clears the tab label (for a
        tabified dock); the empty title-bar widget hides the title strip when the dock
        is shown untabbed. Panel stays fully usable/resizable."""
        d.setWindowTitle(''); d.setTitleBarWidget(QWidget())

    def style_separators(self):
        """Deliberately set NO stylesheet on the main window. A QMainWindow stylesheet (even just
        for ::separator or QTabBar::tab) can collapse/hide tabbed dock panels — that is what made
        the Site file-list panel disappear — so the resize edge is provided only by the thin border
        on the Assets panel itself (set where that panel is built), and docks/tabs keep their native
        look."""
        self.setStyleSheet('')

    def _enable_hdrag(self, lst):
        """Let the list scroll by dragging the body (or the scrollbar) sideways/up-down, instead of
        moving items. Icon grids (IconMode) otherwise let you drag the icons around, and item views
        start a drag on press — both stop a drag from panning, so turn them off."""
        from PySide6.QtWidgets import QScroller, QListView
        lst.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        lst.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        lst.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        lst.setDragEnabled(False)
        lst.setDragDropMode(QAbstractItemView.NoDragDrop)
        try: lst.setMovement(QListView.Static)   # don't let icons be dragged out of place
        except Exception: pass
        QScroller.grabGesture(lst.viewport(), QScroller.LeftMouseButtonGesture)

    def _triangle_button(self, point_right, height=24, width=16, size=5, opaque=False):
        """A small button that PAINTS a plain filled triangle. '<' before a row, '>' after it.
        Auto-repeats when held; brightens on hover. `size` is the triangle half-height (bigger =
        bolder). `opaque=True` fills the button with the window colour first, so it cleanly sits
        'in front of' a tab instead of letting the tab show through. A disabled arrow stays clearly
        visible (just dimmed), not near-invisible, so it reads as an affordance even when idle."""
        from PySide6.QtWidgets import QAbstractButton
        from PySide6.QtGui import QPainter, QPolygon, QColor
        from PySide6.QtCore import QPoint
        win = self
        class TriangleButton(QAbstractButton):
            def __init__(self):
                super().__init__(); self._right = point_right; self._hover = False; self._opaque = opaque
                self.setFixedWidth(width); self.setFixedHeight(height)
                self.setAutoRepeat(True); self.setAutoRepeatInterval(60); self.setAutoRepeatDelay(300)
                self.setCursor(Qt.PointingHandCursor)
                self.setToolTip('Scroll ' + ('right' if point_right else 'left'))
            def enterEvent(self, _): self._hover = True; self.update()
            def leaveEvent(self, _): self._hover = False; self.update()
            def paintEvent(self, _):
                p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
                pal = self.palette()
                if self._opaque: p.fillRect(self.rect(), pal.window().color())
                if not self.isEnabled():
                    col = QColor(pal.text().color()); col.setAlpha(150)   # dimmed but still clearly there
                elif self._hover: col = pal.highlight().color()
                else: col = pal.text().color()
                r = self.rect(); cy = r.center().y(); x0 = r.left() + 4; x1 = r.right() - 4; a = size
                tri = (QPolygon([QPoint(x0, cy - a), QPoint(x0, cy + a), QPoint(x1, cy)]) if self._right
                       else QPolygon([QPoint(x1, cy - a), QPoint(x1, cy + a), QPoint(x0, cy)]))
                p.setPen(Qt.NoPen); p.setBrush(col); p.drawPolygon(tri)
        return TriangleButton()

    def _hscroll_row(self, widgets, step=90, spacing=4):
        """Lay a row of widgets inside a horizontal scroll area flanked by a '<' button
        on the LEFT and a '>' button on the RIGHT. The words keep their full text; when
        they don't all fit, clicking (or holding) an arrow scrolls the row. Arrows grey
        out at each end. Returns a container widget to drop into a layout."""
        from PySide6.QtWidgets import QScrollArea
        inner = QWidget(); il = QHBoxLayout(inner); il.setContentsMargins(0, 0, 0, 0); il.setSpacing(spacing)
        for w in widgets: il.addWidget(w)
        il.addStretch()
        area = QScrollArea(); area.setWidgetResizable(True); area.setFrameShape(QScrollArea.NoFrame)
        area.setWidget(inner)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        sb = area.horizontalScrollBar()
        left = self._triangle_button(False); right = self._triangle_button(True)
        left.clicked.connect(lambda: sb.setValue(sb.value() - step))
        right.clicked.connect(lambda: sb.setValue(sb.value() + step))
        box = QWidget(); row = QHBoxLayout(box); row.setContentsMargins(0, 0, 0, 0); row.setSpacing(2)
        row.addWidget(left); row.addWidget(area, 1); row.addWidget(right)
        def refresh():
            left.setEnabled(sb.value() > sb.minimum())
            right.setEnabled(sb.value() < sb.maximum())
        sb.rangeChanged.connect(lambda *_: refresh()); sb.valueChanged.connect(lambda *_: refresh())
        refresh()
        return box

    def flatten_dock_tabs(self):
        """Flatten the docked-panel tab bars (Site / Swatches / Line / Transform / Layers …) so the
        tabs read as flat text with a highlight on the current one, not raised buttons on a bar.
        Styled on each QTabBar widget DIRECTLY — never on the main window — because a QMainWindow
        stylesheet collapses dock panels (which is what hid the file-list earlier)."""
        from PySide6.QtWidgets import QTabBar
        css = ('QTabBar::tab{background:transparent;border:0;padding:5px 7px;margin:0;color:palette(text);}'
               'QTabBar::tab:selected{background:palette(highlight);color:palette(highlighted-text);border-radius:4px;}'
               'QTabBar::tab:hover{background:palette(midlight);border-radius:4px;}'
               # reserve a strip of space inside the first and last tab so our ◀ / ▶ scroll
               # triangles sit cleanly BEFORE 'Site' and AFTER 'Layers' without covering the text.
               'QTabBar::tab:first{padding-left:26px;}'
               'QTabBar::tab:last{padding-right:26px;}'
               # the ◀ ▶ scroll buttons the tab bar shows when its tabs overflow: make them
               # flat plain triangles (transparent background, no box), not Qt's boxed default.
               'QTabBar QToolButton{background:transparent;border:none;width:16px;}'
               'QTabBar QToolButton:hover{background:palette(midlight);border-radius:3px;}')
        for tb in self.findChildren(QTabBar):
            tb.setStyleSheet(css)
            tb.setUsesScrollButtons(False)  # we add our OWN ◀ ▶ arrows (left and right), not Qt's boxed pair
            tb.setElideMode(Qt.ElideNone)   # keep the full tab name; scroll to the hidden ones
            tb.setExpanding(False)
            self._label_blank_tabs(tb)
            self._add_tabbar_arrows(tb)

    def _label_blank_tabs(self, tb):
        """A tabified dock whose title was blanked (to hide its untabbed title bar) shows
        up here as an empty tab — rendered as a featureless highlighted block ('the blue
        square'). Give any blank tab a readable label so the row reads as normal tabs."""
        for i in range(tb.count()):
            if not tb.tabText(i).strip():
                tip = tb.tabToolTip(i).strip()
                tb.setTabText(i, tip or 'Site')

    def _add_tabbar_arrows(self, tb):
        """Flank a dock tab bar with a ◀ before the first tab and a ▶ after the last (the same
        plain painted triangles used elsewhere). They scroll the tab row left/right when it is
        wider than the panel. Both stay visible as a scroll affordance and simply grey out when
        there is nothing to scroll that way. Implemented as child widgets pinned to the bar."""
        if getattr(tb, '_arrowed', False): return
        tb._arrowed = True
        aw = 20
        left = self._triangle_button(False, height=tb.height() or 26, width=aw, size=6, opaque=True)
        right = self._triangle_button(True, height=tb.height() or 26, width=aw, size=6, opaque=True)
        left.setParent(tb); right.setParent(tb)

        def scroll_tabs(step):
            # Move the selection toward the hidden end so the bar scrolls it into view.
            i = tb.currentIndex() + step
            if 0 <= i < tb.count(): tb.setCurrentIndex(i)
        left.clicked.connect(lambda: scroll_tabs(-1))
        right.clicked.connect(lambda: scroll_tabs(+1))

        def reposition():
            h = tb.height()
            left.setFixedHeight(h); right.setFixedHeight(h)
            last = tb.count() - 1
            overflow = tb.sizeHint().width() > tb.width()
            # ◀ sits in the reserved pad before 'Site'; ▶ sits in the reserved pad just after the
            # last tab's text. If the row spills past the panel edge, pin ▶ to the right edge.
            left.move(0, 0)
            rx = tb.tabRect(last).right() - aw if last >= 0 else tb.width() - aw
            right.move(min(max(aw, rx), tb.width() - aw - 2), 0)
            # Only shown when a tab is actually hidden off either end — otherwise they're redundant.
            left.setVisible(overflow); right.setVisible(overflow)
            left.setEnabled(overflow and tb.currentIndex() > 0)
            right.setEnabled(overflow and tb.currentIndex() < last)
            left.raise_(); right.raise_()
        tb._reposition_arrows = reposition
        # Reposition on resize/selection changes via an event filter + signals.
        tb.currentChanged.connect(lambda *_: reposition())
        orig_resize = tb.resizeEvent
        def resizeEvent(ev):
            orig_resize(ev); reposition()
        tb.resizeEvent = resizeEvent
        QTimer.singleShot(0, reposition)

    def _plainify(self, w):
        """Flat 'just a list' look — NO border box (they never had one), roomier rows than
        the original, and no text elision so long item names keep their full text."""
        w.setStyleSheet(
            'QListWidget,QTreeWidget{background:transparent;border:none;}'
            'QAbstractItemView::item{border:none;background:transparent;padding:6px 8px;min-height:22px;}'
            'QAbstractItemView::item:selected{background:palette(highlight);color:palette(highlighted-text);}')
        try: w.setTextElideMode(Qt.ElideNone)   # show the whole label, don't truncate to '…'
        except Exception: pass

    def build_studio(self):
        # Site
        sw = QWidget(); sl = QVBoxLayout(sw); sl.setContentsMargins(4, 4, 4, 4)
        # generous top+bottom margins → a clear gap separating the tab row above and the page list below
        self.site_name_label = QLabel(); self.site_name_label.setContentsMargins(0, 28, 0, 18)
        sl.addWidget(self.site_name_label)
        self.tree = LinelessTree(); self.tree.setHeaderHidden(True); self.tree.setColumnCount(1); self.tree.setIndentation(16)
        self.tree.itemClicked.connect(lambda it, _: self.goto_page(it.data(0, Qt.UserRole)))
        self.tree.itemDoubleClicked.connect(lambda it, _: self.page_props(self.page_by_id(it.data(0, Qt.UserRole))))
        self._plainify(self.tree); self._enable_hdrag(self.tree)
        sl.addWidget(self.tree, 3)
        ptb = QToolBar(); ptb.setIconSize(QSize(16, 16))
        for text, icon, slot in (('New page', 'document-new', self.insert_page_dialog), ('Delete page', 'edit-delete', self.delete_page),
                                 ('Move up', 'go-up', lambda: self.move_page(-1)), ('Move down', 'go-down', lambda: self.move_page(1)),
                                 ('Make sub-page', 'format-indent-more', lambda: self.indent_page(+1)),
                                 ('Promote one level', 'format-indent-less', lambda: self.indent_page(-1)),
                                 ('Page properties', 'document-properties', lambda: self.page_props(self.page()))):
            ptb.addAction(self.act(text, slot, None, icon))
        sl.addWidget(ptb)
        sl.addWidget(QLabel('<b>Master pages</b>'))
        self.mlist = QListWidget(); self.mlist.itemDoubleClicked.connect(lambda it: self.goto_master(it.data(Qt.UserRole)))
        self._plainify(self.mlist); self._enable_hdrag(self.mlist)
        sl.addWidget(self.mlist, 1)
        mtb = QToolBar(); mtb.setIconSize(QSize(16, 16))
        mtb.addAction(self.act('New master page', self.new_master, None, 'document-new'))
        mtb.addAction(self.act('Edit master page', lambda: self.mlist.currentItem() and self.goto_master(self.mlist.currentItem().data(Qt.UserRole)), None, 'document-edit'))
        mtb.addAction(self.act('Master properties', self.master_props, None, 'document-properties'))
        mtb.addAction(self.act('Delete master page', self.delete_master, None, 'edit-delete'))
        sl.addWidget(mtb)
        self.d_site = self.dock('Site', sw, 'site')
        # Keep the 'Site' windowTitle so its TAB reads 'Site' (not a blank blue square),
        # but still suppress the untabbed title strip with an empty title-bar widget.
        self.d_site.setTitleBarWidget(QWidget())

        # Swatches — sections spread out vertically; bigger swatch chips.
        SW = 28  # swatch chip size (px)
        cw = QWidget(); cl = QVBoxLayout(cw); cl.setContentsMargins(8, 10, 8, 8); cl.setSpacing(10)
        mrow = QHBoxLayout(); self.sw_group = QButtonGroup(self)
        for i, (k, lbl) in enumerate((('fill', 'Fill'), ('line', 'Line'), ('text', 'Text'))):
            b = QToolButton(); b.setText(lbl); b.setCheckable(True); b.setChecked(k == 'fill'); b.setToolButtonStyle(Qt.ToolButtonTextOnly)
            self.sw_group.addButton(b, i); mrow.addWidget(b)
        self.sw_group.idClicked.connect(lambda i: self.set_sw_mode(('fill', 'line', 'text')[i]))
        mrow.addStretch(); cl.addLayout(mrow)
        cl.addSpacing(10)   # gap between the Fill/Line/Text row and the swatch sections below
        cl.addWidget(QLabel('Site palette')); self.pal_grid = QGridLayout(); self.pal_grid.setSpacing(4); cl.addLayout(self.pal_grid)
        cl.addWidget(QLabel('Standard')); sg = QGridLayout(); sg.setSpacing(4); cl.addLayout(sg)
        none_b = QToolButton(); none_b.setIcon(swatch_icon('', SW)); none_b.setIconSize(QSize(SW, SW)); none_b.setToolTip('None'); none_b.setAutoRaise(True)
        none_b.clicked.connect(lambda: self.apply_swatch('')); sg.addWidget(none_b, 0, 0)
        for i, c in enumerate(STANDARD, 1):
            b = QToolButton(); b.setIcon(swatch_icon(c, SW)); b.setIconSize(QSize(SW, SW)); b.setToolTip(c); b.setAutoRaise(True)
            b.clicked.connect(lambda _=False, c=c: self.apply_swatch(c)); sg.addWidget(b, i // 7, i % 7)
        cb = QPushButton('Custom colour…'); cb.clicked.connect(self.custom_swatch); cl.addWidget(cb)
        ab = QPushButton('Add selected colour to site palette'); ab.clicked.connect(self.add_to_palette); cl.addWidget(ab)
        cl.addStretch()
        self.d_swatch = self.dock('Swatches', cw, 'swatches')

        # Colour — a live RGB / HSL mixer with spectrum, matching Serif's Colour tab.
        self._col_gesture = False; self._updating_col = False
        # bottom margin kept generous so the colour spectrum isn't jammed flush against the
        # Site / Swatches tab bar that sits directly below this dock — gives the tabs breathing room.
        cow = QWidget(); co = QVBoxLayout(cow); co.setContentsMargins(6, 6, 6, 18); co.setSpacing(7)
        crow = QHBoxLayout(); self.col_group = QButtonGroup(self)
        for i, (k, lbl) in enumerate((('fill', 'Fill'), ('line', 'Line'), ('text', 'Text'))):
            b = QToolButton(); b.setText(lbl); b.setCheckable(True); b.setChecked(k == 'fill'); b.setToolButtonStyle(Qt.ToolButtonTextOnly)
            self.col_group.addButton(b, i); crow.addWidget(b)
        self.col_group.idClicked.connect(lambda i: self.set_sw_mode(('fill', 'line', 'text')[i]))
        self.col_mode = QComboBox(); self.col_mode.addItems(['RGB', 'HSL']); self.col_mode.currentIndexChanged.connect(self.col_mode_changed)
        crow.addStretch(); crow.addWidget(self.col_mode); co.addLayout(crow)
        self.col_labels, self.col_sliders, self.col_spins = [], [], []
        cgrid = QGridLayout(); cgrid.setSpacing(5)
        for r in range(3):
            lab = QLabel(); s = QSlider(Qt.Horizontal); s.setRange(0, 255); sp = QSpinBox(); sp.setRange(0, 255); sp.setFixedWidth(56)
            s.valueChanged.connect(sp.setValue); sp.valueChanged.connect(s.setValue)
            s.valueChanged.connect(self.col_from_sliders)
            s.sliderReleased.connect(self.colour_end); sp.editingFinished.connect(self.colour_end)
            cgrid.addWidget(lab, r, 0); cgrid.addWidget(s, r, 1); cgrid.addWidget(sp, r, 2)
            self.col_labels.append(lab); self.col_sliders.append(s); self.col_spins.append(sp)
        co.addLayout(cgrid)
        hrow = QHBoxLayout(); hrow.addWidget(QLabel('Hex')); self.col_hex = QLineEdit(); self.col_hex.setMaxLength(7); self.col_hex.setFixedWidth(84)
        self.col_hex.editingFinished.connect(self.col_from_hex); hrow.addWidget(self.col_hex)
        self.col_preview = QFrame(); self.col_preview.setFixedSize(46, 24); self.col_preview.setFrameShape(QFrame.StyledPanel); hrow.addWidget(self.col_preview)
        self.eyedrop_btn = QToolButton(); self.eyedrop_btn.setCheckable(True)
        self.eyedrop_btn.setIcon(ticon(['color-picker', 'gtk-color-picker', 'tool-measure'], '⦿'))
        self.eyedrop_btn.setToolTip('Eyedropper — click the page to pick up a colour')
        self.eyedrop_btn.clicked.connect(self.start_eyedropper); hrow.addWidget(self.eyedrop_btn); hrow.addStretch()
        co.addLayout(hrow)
        self.spectrum = SpectrumBar(self.spectrum_pick, self.colour_end)
        self.spectrum.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        co.addWidget(self.spectrum, 1)  # fill the space below instead of wasting it on a stretch
        self.col_mode_changed()
        self.d_colour = self.dock('Colour', cow, 'colour'); self._hide_dock_title(self.d_colour)

        # Line — a gap above the first row and roomier spacing between rows
        lw = QWidget(); lf = QFormLayout(lw); lf.setContentsMargins(8, 16, 8, 8); lf.setVerticalSpacing(12)
        self.ln_w = QDoubleSpinBox(); self.ln_w.setRange(0, 60); self.ln_w.setSuffix(' px'); self.ln_w.setDecimals(1)
        self.ln_w.valueChanged.connect(lambda v: self.studio_set('strokeW', v))
        self.ln_style = QComboBox(); self.ln_style.addItems(['solid', 'dashed', 'dotted'])
        self.ln_style.currentTextChanged.connect(lambda v: self.studio_set('dash', v))
        self.ln_rad = QSpinBox(); self.ln_rad.setRange(0, 400); self.ln_rad.setSuffix(' px')
        self.ln_rad.valueChanged.connect(lambda v: self.studio_set('radius', v))
        lf.addRow('Width:', self.ln_w); lf.addRow('Style:', self.ln_style); lf.addRow('Corner radius:', self.ln_rad)
        self.d_line = self.dock('Line', lw, 'line')

        # Transparency — dropped down a little from the top
        tw = QWidget(); tl = QFormLayout(tw); tl.setContentsMargins(8, 22, 8, 8); tl.setVerticalSpacing(10)
        self.op_slider = QSlider(Qt.Horizontal); self.op_slider.setRange(0, 100)
        self.op_spin = QSpinBox(); self.op_spin.setRange(0, 100); self.op_spin.setSuffix(' %')
        self.op_slider.valueChanged.connect(self.op_spin.setValue)
        self.op_spin.valueChanged.connect(self.op_slider.setValue)
        self.op_spin.valueChanged.connect(lambda v: self.studio_set('opacity', 1 - v / 100))
        tl.addRow('Transparency:', self.op_slider); tl.addRow('', self.op_spin)
        self.d_trans = self.dock('Transparency', tw, 'transparency')

        # Transform — rows spread out vertically with a gap above
        xw = QWidget(); xf = QFormLayout(xw); xf.setContentsMargins(8, 12, 8, 8); xf.setVerticalSpacing(12); self.tf = {}
        for k, lbl, lo, hi, suf in (('x', 'X:', -5000, 20000, ' px'), ('y', 'Y:', -5000, 20000, ' px'), ('w', 'Width:', 1, 20000, ' px'),
                                    ('h', 'Height:', 1, 20000, ' px'), ('rot', 'Rotation:', -180, 180, '°')):
            sp = QDoubleSpinBox(); sp.setRange(lo, hi); sp.setSuffix(suf); sp.setDecimals(0 if k != 'rot' else 1)
            sp.valueChanged.connect(lambda v, k=k: self.studio_set(k, v)); xf.addRow(lbl, sp); self.tf[k] = sp
        self.anchor_cb = QCheckBox('Keep at bottom of every page')
        self.anchor_cb.setToolTip('For master page objects such as a footer: they stay the same distance from the bottom on pages of any height.')
        self.anchor_cb.toggled.connect(self.anchor_toggled)
        xf.addRow('', self.anchor_cb)
        self.d_xform = self.dock('Transform', xw, 'transform')

        # Layers
        yw = QWidget(); yl = QVBoxLayout(yw); yl.setContentsMargins(4, 4, 4, 4)
        self.layers = QListWidget(); self.layers.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.layers.itemSelectionChanged.connect(self.layers_selected)
        self.layers.itemDoubleClicked.connect(lambda it: self.edit_object(self.find(it.data(Qt.UserRole))) if self.find(it.data(Qt.UserRole)) else None)
        self._plainify(self.layers); self._enable_hdrag(self.layers)
        yl.addWidget(self.layers)
        ytb = QToolBar(); ytb.setIconSize(QSize(16, 16))
        ytb.addAction(self.act('Show / hide', self.toggle_hidden, None, ['view-visible', 'visibility']))
        ytb.addAction(self.a['lock'])
        ytb.addAction(self.a['fwd']); ytb.addAction(self.a['back1'])
        yl.addWidget(ytb)
        self.d_layers = self.dock('Layers', yw, 'layers')

        # Assets — a thumbnail library of every picture in the site (uploaded + AI-made).
        aw = QWidget(); aw.setObjectName('assetpanel'); aw.setMinimumWidth(104); al = QVBoxLayout(aw); al.setContentsMargins(4, 4, 4, 4); al.setSpacing(4)
        # a single thin edge on this panel's right side (same Mid colour as the rulers draw), so the
        # resize edge is visible on the left without putting a line beside the right-hand docks
        aw.setStyleSheet('#assetpanel{border-right:1px solid palette(mid);}')
        # Panel header: a proper 'Assets' title inside the panel (not the tiny top-left dock
        # title-bar text) — larger, with a little left/top padding so it reads as a heading.
        asset_title = QLabel('Assets')
        asset_title.setStyleSheet('font-size:15px; font-weight:bold; color:palette(text); padding:28px 2px 4px 8px;')
        al.addWidget(asset_title)
        browse = QPushButton(ticon(['folder-open', 'document-open'], ''), 'Browse…'); browse.setToolTip('Add every picture from a folder'); browse.clicked.connect(self.asset_browse_folder)
        add_file = QPushButton(ticon(['document-open'], ''), 'Open…'); add_file.clicked.connect(self.asset_add_file)
        add_ai = QPushButton(ticon(['applications-graphics'], ''), 'AI image…'); add_ai.clicked.connect(self.asset_add_ai)
        paint = QPushButton(ticon(['draw-brush', 'krita', 'applications-graphics'], '🖌'), 'IMAGEpainter')
        paint.setToolTip('Open IMAGEpainter (set in Settings) to paint or edit an image')
        paint.clicked.connect(self.launch_imagepainter)
        for b in (browse, add_file, add_ai, paint): b.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        # full words, no truncation — scroll the row with the < > arrows when it overflows
        al.addWidget(self._hscroll_row([browse, add_file, add_ai, paint]))
        self.asset_filter = 'all'; self.asset_cat_group = QButtonGroup(self); crow = QHBoxLayout(); crow.setSpacing(3)
        for i, (fk, lbl) in enumerate((('all', 'All'), ('pictures', 'Pictures'), ('graphics', 'Graphics'))):
            b = QToolButton(); b.setText(lbl); b.setCheckable(True); b.setChecked(fk == 'all'); b.setToolButtonStyle(Qt.ToolButtonTextOnly)
            b.clicked.connect(lambda _=False, fk=fk: (setattr(self, 'asset_filter', fk), self.refresh_assets()))
            self.asset_cat_group.addButton(b, i); crow.addWidget(b)
        crow.addStretch(); al.addLayout(crow)
        # Thumbnails sit in uniform framed boxes with no caption (the name is the tooltip).
        # ThumbGrid grows the icons with the panel and reflows between one and two columns.
        self.asset_list = ThumbGrid()
        self.asset_list.setStyleSheet(
            'QListWidget{background:transparent; border:none;}'
            'QListWidget::item{margin:3px;}'
            'QListWidget::item:selected{border:1px solid palette(highlight);}')
        self.asset_list.itemDoubleClicked.connect(self.asset_insert)
        self.asset_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.asset_list.customContextMenuRequested.connect(self.asset_context_menu)
        self.asset_list.filesDropped.connect(self.import_asset_files)
        al.addWidget(self.asset_list, 1)
        al.addWidget(QLabel('<span style="color:gray">Double-click or drag onto the page · drop pictures here to add · hover for the name.</span>'))
        self.d_assets = self.dock('Assets', aw, 'assets')
        self.d_assets.setWindowTitle('')   # keep windowTitle blank
        # Hide the empty dock title strip entirely: the in-panel 'Assets' heading is the title now, so
        # that strip only left 'Assets' stranded below it and wasted height the thumbnail list can use.
        self.d_assets.setTitleBarWidget(QWidget())

        # Right side: Colour sits on top; below it, one tabbed group — the original
        # studio (Site / Swatches / Line / Transparency / Transform / Layers) that you
        # switch with its tabs, defaulting to Site.
        self.setTabPosition(Qt.RightDockWidgetArea, QTabWidget.North)
        self.splitDockWidget(self.d_colour, self.d_site, Qt.Vertical)
        for d in (self.d_swatch, self.d_line, self.d_trans, self.d_xform, self.d_layers):
            self.tabifyDockWidget(self.d_site, d)
            # Suppress each panel's own title strip: the tab above it already names the panel,
            # so the in-panel title is redundant. windowTitle is kept so the TAB stays labelled.
            d.setTitleBarWidget(QWidget())
        # Assets lives on the left, as a flyout tab, like Serif's Assets studio.
        self.addDockWidget(Qt.LeftDockWidgetArea, self.d_assets)
        self.d_colour.raise_(); self.d_site.raise_()
        self.resizeDocks([self.d_colour, self.d_site], [320, 410], Qt.Vertical)
        self.resizeDocks([self.d_assets], [196], Qt.Horizontal)  # two columns; narrow for one
        self.view_menu.addSeparator()
        sm = self.view_menu.addMenu('Studio')
        for d, lbl in ((self.d_site, 'Site'), (self.d_assets, 'Assets'), (self.d_swatch, 'Swatches'),
                       (self.d_colour, 'Colour'), (self.d_line, 'Line'), (self.d_trans, 'Transparency'),
                       (self.d_xform, 'Transform'), (self.d_layers, 'Layers')):
            a = d.toggleViewAction()
            if not a.text(): a.setText(lbl)  # d_site/d_colour have a blank windowTitle (hidden dock title)
            sm.addAction(a)
        # A visible, obvious way to show/hide the Assets panel: a checkable 'Assets' button
        # on the Standard toolbar (the panel itself has no title bar to close it from).
        assets_toggle = self.d_assets.toggleViewAction()
        assets_toggle.setText('Assets'); assets_toggle.setIcon(ticon(['folder-pictures', 'image-x-generic', 'view-preview'], '🖼'))
        assets_toggle.setToolTip('Show or hide the Assets panel')
        if getattr(self, '_std_toolbar', None):
            self._std_toolbar.addSeparator()
            self._std_toolbar.addAction(assets_toggle)
            w = self._std_toolbar.widgetForAction(assets_toggle)
            if w: w.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.resizeDocks([self.d_site], [300], Qt.Horizontal)

    def restore_layout(self):
        g = self.settings.value('geometry'); s = self.settings.value('state')
        if g: self.restoreGeometry(g)
        if s: self.restoreState(s, LAYOUT_VERSION)
        self.toggle_rulers()
        # A restored layout can collapse the right-hand studio group to zero size, which hides the
        # Site file-list AND its toolbar buttons together. Self-heal once sizes are realised — twice,
        # since a single pass at t=0 can run before the dock sizes have settled and miss the collapse.
        QTimer.singleShot(0, self._ensure_studio_visible)
        QTimer.singleShot(200, self._ensure_studio_visible)

    def _ensure_studio_visible(self):
        """If the Site / Colour studio group came back hidden or collapsed to near-zero, give it a
        sane size and show it, so the Site file-list and its page buttons can never disappear."""
        for d in (self.d_colour, self.d_site, self.d_assets):
            try:
                if not d.isFloating() and not d.isVisible():
                    d.setVisible(True)
            except Exception:
                pass
        try:
            if self.d_site.height() < 60 or self.d_colour.height() < 60:
                self.resizeDocks([self.d_colour, self.d_site], [320, 410], Qt.Vertical)
                self.d_site.raise_()
            if self.d_assets.width() < 40:
                self.resizeDocks([self.d_assets], [196], Qt.Horizontal)
        except Exception:
            pass

    # ------------------------------------------------------------ refresh
    def refresh(self):
        if self.editor: self.finish_edit(); return
        if not any(p['id'] == self.cur_page for p in self.site['pages']): self.cur_page = self.site['pages'][0]['id']
        if self.edit_master and not self.cur_master(): self.edit_master = None
        ids = {o['id'] for o in self.layer()}
        self.sel = [i for i in self.sel if i in ids]
        self.rebuild_scene()
        self.schedule_ui()

    def rebuild_scene(self):
        sc = self.view.scene(); sc.clear(); self.items = {}
        W, Hh = self.site['width'], self.page_h()
        sc.setSceneRect(QRectF(-300, -200, W + 600, Hh + 400))
        z = 0
        if not self.edit_master:
            for o in self.master_of(self.page())['objects']:
                if o.get('hidden'): continue
                it = ObjItem(o, self, master=True)
                if o.get('anchor') == 'bottom': it.dy = Hh - self.site['height']; it.sync()
                it.setZValue(z); z += 1; sc.addItem(it); self.items['m:' + o['id']] = it
        for o in self.layer():
            if o.get('hidden'): continue
            it = ObjItem(o, self); it.setZValue(1000 + z); z += 1; sc.addItem(it); self.items[o['id']] = it
        self.view.viewport().update()

    def schedule_ui(self):
        if not self._ui_pending:
            self._ui_pending = True; QTimer.singleShot(0, self.update_ui)

    def update_ui(self):
        self._ui_pending = False
        self.update_title(); self.build_ctx(); self.refresh_site_tab(); self.refresh_palette(); self.refresh_colour(); self.refresh_props(); self.refresh_layers(); self.refresh_assets()
        self.update_rulers(); self.update_hint()
        m = self.cur_master()
        self.banner.setVisible(bool(m))
        if m: self.banner_label.setText(f'Editing master page “{m["name"]}”. Changes appear on every page that uses it.')
        p = self.page()
        self.page_label.setText(f'Master: {m["name"]}' if m else f'Page {self.site["pages"].index(p) + 1} of {len(self.site["pages"])}: {p["title"]}')
        self.a['undo'].setEnabled(bool(self.undo)); self.a['redo'].setEnabled(bool(self.redo))
        has = bool(self.sel)
        for k in ('cut', 'copy', 'dup', 'delete', 'front', 'fwd', 'back1', 'back', 'link', 'lock'): self.a[k].setEnabled(has)
        self.a['paste'].setEnabled(bool(self.clip))

    def live_update(self):
        self.view.viewport().update(); self.update_rulers(); self.refresh_props()

    def update_title(self):
        if self.path:
            folder = os.path.dirname(self.path); home = os.path.expanduser('~')
            if folder == home or folder.startswith(home + os.sep): folder = '~' + folder[len(home):]
            name = f'{os.path.basename(self.path)} ({folder})'
        else:
            name = f'{self.site["name"]} (not saved yet)'
        self.setWindowTitle(f'{"● " if self.dirty else ""}{name} — {APP}')

    def update_hint(self):
        if self.sel:
            os_ = self.sel_objs()
            if len(os_) == 1:
                o = os_[0]
                extra = ' Double-click to edit the text.' if o['type'] in ('text', 'artistic', 'button') else \
                        ' Double-click to replace the picture.' if o['type'] == 'picture' else \
                        ' Double-click to edit the cells.' if o['type'] == 'table' else \
                        ' Double-click to choose its photos and timing.' if o['type'] == 'gallery' else \
                        ' Each button shares whichever page it is on. Double-click to choose the sites.' if o['type'] == 'share' else \
                        ' It updates automatically when you add or rename pages.' if o['type'] == 'nav' else ''
                self.hint(f'{TYPE_NAMES[o["type"]]} selected.{extra}' + (' (Locked)' if o.get('locked') else ''))
            else:
                self.hint(f'{len(os_)} objects selected. Drag to move them together.')
        else:
            t = next((x for x in TOOLS if x[0] == self.tool), None)
            self.hint(t[4] if t else '')

    # ------------------------------------------------------------ context toolbar
    def build_ctx(self):
        tb = self.ctx; tb.clear()
        objs = self.sel_objs(); o = objs[0] if objs else None
        def add(w): tb.addWidget(w); return w
        def label(t): l = QLabel(f' {t} '); add(l)
        def btn(icon, tip, slot, checked=None, glyph=''):
            a = QAction(ticon(icon if isinstance(icon, list) else [icon], glyph), tip, tb); a.triggered.connect(slot)
            if checked is not None: a.setCheckable(True); a.setChecked(checked)
            tb.addAction(a); return a
        if not o:
            m = self.cur_master()
            if m:
                label(f'Master page: {m["name"]}'); tb.addSeparator()
                label('Background'); add(ColorButton(m.get('bg'), lambda c: self.set_bg(c), 'Master page background'))
            else:
                p = self.page(); label(f'Page: {p["title"]}'); tb.addSeparator()
                label('Background'); add(ColorButton(self.page_bg(), lambda c: self.set_bg(c), 'Page background'))
                tb.addAction(self.a['pageprops']); tb.addAction(self.a['siteprops'])
            tb.addSeparator(); tb.addAction(self.a['grid']); tb.addAction(self.a['snap'])
            return
        types = {x['type'] for x in objs}
        label(TYPE_NAMES[o['type']] if len(objs) == 1 else f'{len(objs)} objects'); tb.addSeparator()
        textish = types & {'text', 'artistic', 'button', 'table', 'nav', 'form'}
        if textish and len(types) == 1 or (types <= {'text', 'artistic', 'button'}):
            fc = QFontComboBox(); fc.setCurrentFont(QFont(o.get('font', SANS))); fc.setMaximumWidth(190)
            fc.currentFontChanged.connect(lambda f: self.set_prop('font', f.family())); add(fc)
            sz = QSpinBox(); sz.setRange(4, 400); sz.setValue(int(o.get('size', 16))); sz.setSuffix(' px'); sz.setToolTip('Font size')
            sz.editingFinished.connect(lambda: self.set_prop('size', sz.value())); add(sz)
            for k in ('bold', 'italic', 'underline'):
                a = self.a[k]; a.setChecked(bool(o.get(k))); tb.addAction(a)
            if types & {'text', 'artistic', 'button'}:
                tb.addSeparator()
                for k in ('aleft', 'acenter', 'aright', 'ajust'): tb.addAction(self.a[k])
            add(ColorButton(o.get('color'), lambda c: self.set_prop('color', c), 'Text colour'))
            tb.addSeparator()
        if types & {'shape', 'text', 'artistic', 'button', 'picture'}:
            label('Fill'); add(ColorButton(o.get('fill'), lambda c: self.set_prop('fill', c), 'Fill colour', allow_none=True))
        if types & {'shape', 'text', 'button', 'picture', 'line'}:
            label('Line'); add(ColorButton(o.get('stroke'), lambda c: self.set_prop('stroke', c), 'Line colour'))
            lw = QSpinBox(); lw.setRange(0, 60); lw.setValue(int(o.get('strokeW', 0))); lw.setSuffix(' px'); lw.setToolTip('Line width')
            lw.editingFinished.connect(lambda: self.set_prop('strokeW', lw.value())); add(lw)
            tb.addSeparator()
        if len(objs) == 1:
            t = o['type']
            if t == 'shape':
                cb = QComboBox(); cb.addItems(['Rectangle', 'Ellipse']); cb.setCurrentIndex(1 if o.get('shape') == 'ellipse' else 0)
                cb.activated.connect(lambda i: self.set_prop('shape', 'ellipse' if i else 'rect')); add(cb)
            if t in ('shape', 'button', 'picture', 'text'):
                rd = QSpinBox(); rd.setRange(0, 400); rd.setValue(int(o.get('radius', 0))); rd.setPrefix('Corners '); rd.setSuffix(' px')
                rd.editingFinished.connect(lambda: self.set_prop('radius', rd.value())); add(rd)
            if t == 'picture':
                btn(['insert-image', 'document-open'], 'Replace Picture…', lambda: self.pick_picture(o))
                cb = QComboBox(); cb.addItems(['Fill frame (crop)', 'Fit inside frame', 'Stretch'])
                cb.setCurrentIndex(['cover', 'contain', 'stretch'].index(o.get('fit', 'cover')))
                cb.activated.connect(lambda i: self.set_prop('fit', ['cover', 'contain', 'stretch'][i])); add(cb)
            if t == 'line':
                btn(['object-flip-vertical'], 'Flip line', lambda: self.set_prop('flip', not o.get('flip')), glyph='⇅')
            if t == 'nav':
                cb = QComboBox(); cb.addItems(['Pills', 'Underline', 'Tabs', 'Plain']); styles = ['pills', 'underline', 'tabs', 'plain']
                cb.setCurrentIndex(styles.index(o.get('style', 'pills'))); cb.activated.connect(lambda i: self.set_prop('style', styles[i])); add(cb)
                ob = QComboBox(); ob.addItems(['Horizontal', 'Vertical']); ob.setCurrentIndex(1 if o.get('orient') == 'v' else 0)
                ob.activated.connect(lambda i: self.set_prop('orient', 'v' if i else 'h')); add(ob)
                al = QComboBox(); al.addItems(['Left', 'Centre', 'Right']); als = ['left', 'center', 'right']
                al.setCurrentIndex(als.index(o.get('align', 'left'))); al.activated.connect(lambda i: self.set_prop('align', als[i])); add(al)
                label('Current page'); add(ColorButton(o.get('accent'), lambda c: self.set_prop('accent', c), 'Current page highlight'))
                add(ColorButton(o.get('accentInk'), lambda c: self.set_prop('accentInk', c), 'Current page text'))
                label('Bar'); add(ColorButton(o.get('fill'), lambda c: self.set_prop('fill', c), 'Bar background', allow_none=True))
            if t == 'table':
                btn(['document-edit'], 'Edit Table…', lambda: self.edit_object(o))
                label('Header'); add(ColorButton(o.get('head'), lambda c: self.set_prop('head', c), 'Header row colour'))
                label('Grid'); add(ColorButton(o.get('stroke'), lambda c: self.set_prop('stroke', c), 'Grid colour'))
            if t == 'form':
                btn(['document-edit'], 'Edit Form…', lambda: self.edit_object(o))
                label('Button'); add(ColorButton(o.get('accent'), lambda c: self.set_prop('accent', c), 'Button colour'))
            if t == 'html':
                btn(['document-edit'], 'Edit HTML…', lambda: self.edit_object(o))
            if t == 'share':
                btn(['document-edit'], 'Choose Sites…', lambda: self.edit_object(o))
            if t == 'gallery':
                btn(['document-edit'], 'Edit Gallery…', lambda: self.edit_object(o))
            tb.addSeparator()
        tb.addAction(self.a['link'])
        tb.addSeparator()
        for k in ('front', 'back'): tb.addAction(self.a[k])
        tb.addAction(self.a['delete'])

    # ------------------------------------------------------------ Studio refresh
    def page_by_id(self, pid):
        return next((p for p in self.site['pages'] if p['id'] == pid), None)

    def show_site_structure(self):
        self.d_site.show(); self.d_site.raise_()

    def toggle_assets_pin(self, on):
        if on:
            self.d_assets.setFeatures(QDockWidget.NoDockWidgetFeatures)
            self.hint('Assets panel pinned open — it won’t move, float or close.')
        else:
            self.d_assets.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetClosable)
            self.hint('Assets panel unpinned.')

    def serif_stub(self, name):
        self.hint(f'{name} is part of the Serif suite and isn’t available in this clone.')
        QMessageBox.information(self, name,
                               f'{name} is part of the Serif suite (PhotoPlus / PhotoLab / Cutout Studio).\n\n'
                               'Those are separate Serif programs with no Linux equivalent, so this button '
                               'is here for parity with WebPlus but does not do anything.')

    def launch_imagepainter(self):
        """Open the image editor set in Settings (defaults to 'IMAGEpainter'). If it isn't on the
        system yet, offer to install it."""
        cmd = (self.settings.value('imagePainterCmd', '') or 'IMAGEpainter').strip()
        exe = shutil.which(cmd) or shutil.which(cmd.lower()) or shutil.which('imagepainter')
        if exe:
            try:
                subprocess.Popen([exe])
                self.hint(f'Opening {cmd}…')
            except Exception as e:
                QMessageBox.warning(self, cmd, f'Could not start {cmd}:\n{e}')
            return
        r = QMessageBox.question(
            self, 'Install IMAGEpainter',
            f'“{cmd}” isn’t installed on this system yet.\n\n'
            'IMAGEpainter is the companion image editor — paint and edit pictures, then drop them '
            'straight into your site. Would you like to install it?',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if r == QMessageBox.Yes:
            open_external('https://janszafranski.github.io/just-a-collection-of-apps/')

    def refresh_site_tab(self):
        self.site_name_label.setText(f'<b>{H.escape(self.site["name"])}</b> &nbsp;·&nbsp; {self.site["width"]} px wide')
        self.tree.clear(); cur = None
        # A page's level is its depth in the site, to any depth: a site imported
        # from WebPlus is commonly four deep, and showing it two deep would put
        # 168 of Woldingham Panto's 208 pages in one flat list.
        stack = []
        for p in self.site['pages']:
            it = QTreeWidgetItem([p['title'] + ('' if p.get('nav', True) else '  (not in navigation)')])
            it.setToolTip(0, f"{p['file']} · master: {self.master_of(p)['name']}")
            it.setIcon(0, ticon(['text-html', 'document-new'], ''))
            it.setData(0, Qt.UserRole, p['id'])
            lvl = min(int(p.get('level') or 0), len(stack))
            del stack[lvl:]
            if stack: stack[-1].addChild(it)
            else: self.tree.addTopLevelItem(it)
            stack.append(it)
            if p['id'] == self.cur_page and not self.edit_master: cur = it
        self.tree.expandAll()
        if cur: self.tree.setCurrentItem(cur)
        self.mlist.clear()
        for m in self.site['masters']:
            n = sum(1 for p in self.site['pages'] if p['master'] == m['id'])
            it = QListWidgetItem(ticon(['document-multiple', 'edit-copy'], ''), f"{m['name']}  ({n} page{'s' if n != 1 else ''})")
            it.setData(Qt.UserRole, m['id']); self.mlist.addItem(it)
            if m['id'] == self.edit_master: self.mlist.setCurrentItem(it)

    def refresh_palette(self):
        while self.pal_grid.count():
            w = self.pal_grid.takeAt(0).widget()
            if w: w.deleteLater()
        for i, c in enumerate(self.site.get('palette', [])):
            b = QToolButton(); b.setIcon(swatch_icon(c, 28)); b.setIconSize(QSize(28, 28)); b.setToolTip(c); b.setAutoRaise(True)
            b.clicked.connect(lambda _=False, c=c: self.apply_swatch(c)); self.pal_grid.addWidget(b, i // 7, i % 7)

    def refresh_props(self):
        self._updating = True
        objs = self.sel_objs(); o = objs[0] if objs else None
        for w in list(self.tf.values()) + [self.ln_w, self.ln_style, self.ln_rad, self.op_spin, self.op_slider]: w.setEnabled(bool(o))
        if o:
            for k, sp in self.tf.items(): sp.setValue(o.get(k, 0))
            self.ln_w.setValue(o.get('strokeW', 0)); self.ln_style.setCurrentText(o.get('dash', 'solid')); self.ln_rad.setValue(int(o.get('radius', 0)))
            v = round((1 - o.get('opacity', 1)) * 100); self.op_spin.setValue(v); self.op_slider.setValue(v)
            self.anchor_cb.setChecked(o.get('anchor') == 'bottom')
        self.anchor_cb.setVisible(bool(self.edit_master)); self.anchor_cb.setEnabled(bool(o))
        self._updating = False

    def refresh_layers(self):
        self.layers.blockSignals(True); self.layers.clear()
        for o in reversed(self.layer()):
            snippet = re.sub('<[^>]+>', ' ', o.get('html', '')).strip()
            snippet = re.sub(r'\s+', ' ', H.unescape(snippet))[:28]
            name = TYPE_NAMES[o['type']] + (f' — “{snippet}”' if snippet else '')
            flags = (' 🔒' if o.get('locked') else '') + (' (hidden)' if o.get('hidden') else '')
            it = QListWidgetItem(name + flags); it.setData(Qt.UserRole, o['id'])
            if o.get('hidden'): it.setForeground(self.palette().color(QPalette.PlaceholderText))
            self.layers.addItem(it)
            if o['id'] in self.sel: it.setSelected(True)
        if not self.edit_master:
            m = self.master_of(self.page())
            if m['objects']:
                sep = QListWidgetItem(f'Shown from master page “{m["name"]}” (edit the master to change)'); sep.setFlags(Qt.NoItemFlags)
                f = sep.font(); f.setItalic(True); sep.setFont(f); self.layers.addItem(sep)
                for o in reversed(m['objects']):
                    it = QListWidgetItem('    🔒 ' + TYPE_NAMES[o['type']]); it.setFlags(Qt.NoItemFlags)
                    it.setForeground(self.palette().color(QPalette.PlaceholderText)); self.layers.addItem(it)
        self.layers.blockSignals(False)

    def layers_selected(self):
        ids = [it.data(Qt.UserRole) for it in self.layers.selectedItems() if it.data(Qt.UserRole)]
        self.select(ids, from_layers=True)

    # ------------------------------------------------------------ selection & tools
    def select(self, ids, from_layers=False):
        self.sel = ids
        self.view.viewport().update()
        if from_layers:
            self.build_ctx(); self.refresh_props(); self.update_hint(); self.update_rulers()
            for k in ('cut', 'copy', 'dup', 'delete', 'front', 'fwd', 'back1', 'back', 'link', 'lock'): self.a[k].setEnabled(bool(ids))
        else:
            self.schedule_ui()

    def set_tool(self, tid):
        if self.editor: self.finish_edit()
        self.tool = tid; self.tool_actions[tid].setChecked(True)
        self.view.viewport().setCursor({'pointer': Qt.ArrowCursor, 'hand': Qt.OpenHandCursor, 'zoom': Qt.PointingHandCursor}.get(tid, Qt.CrossCursor))
        self.update_hint()

    def select_all(self):
        if self.editor:
            c = self.editor.textCursor(); c.select(QTextCursor.Document); self.editor.setTextCursor(c); return
        self.select([o['id'] for o in self.layer() if not o.get('hidden')])

    # ------------------------------------------------------------ creating objects
    def create_object(self, tool, a, b, r_, shift):
        small = r_.width() < 6 and r_.height() < 6
        kind = {'rect': 'shape', 'ellipse': 'shape'}.get(tool, tool)
        if kind == 'line':
            if small: return
            w, h = abs(b.x() - a.x()), abs(b.y() - a.y())
            if shift:
                if w > h * 2: h = 0
                elif h > w * 2: w = 0
            o = mk('line', min(a.x(), b.x()), min(a.y(), b.y()), max(2, w), max(2, h), flip=(b.x() - a.x()) * (b.y() - a.y()) < 0)
            if h == 0: o['y'] = a.y() - 1
            if w == 0: o['x'] = a.x() - 1
        else:
            o = mk(kind, 0, 0)
            if kind == 'shape': o['shape'] = 'ellipse' if tool == 'ellipse' else 'rect'
            if small:
                o['x'], o['y'] = a.x(), a.y()
            else:
                o['x'], o['y'], o['w'], o['h'] = r_.x(), r_.y(), r_.width(), r_.height()
                if kind == 'artistic': o['size'] = max(6, round(r_.height() * .8))
        snap = self.view.snap
        o['x'], o['y'] = snap(o['x']), snap(o['y'])
        self.add_object(o)
        self.set_tool('pointer')
        if kind in ('text', 'artistic', 'button'): self.start_edit(o, select_all=True)
        elif kind == 'picture': self.pick_picture(o)
        elif kind == 'gallery': self.gallery_dialog(o)

    def insert_default(self, tool):
        c = self.view.mapToScene(self.view.viewport().rect().center())
        kind = {'rect': 'shape', 'ellipse': 'shape'}.get(tool, tool)
        o = mk(kind, 0, 0)
        if tool == 'ellipse': o['shape'] = 'ellipse'
        o['x'] = self.view.snap(max(0, c.x() - o['w'] / 2)); o['y'] = self.view.snap(max(0, c.y() - o['h'] / 2))
        self.add_object(o)
        if kind == 'picture': self.pick_picture(o)
        elif kind == 'gallery': self.gallery_dialog(o)

    def insert_coffee_button(self):
        """Toolbar one-click: drop a 'Buy me a coffee' button, coloured to match the
        site palette and linked to the user's page. The link is asked for once and
        remembered (in settings) so it works across sites too."""
        from PySide6.QtWidgets import QInputDialog
        url = (self.settings.value('bmcUrl', '') or '').strip()
        if not url:
            txt, ok = QInputDialog.getText(self, 'Buy Me a Coffee',
                'Your Buy Me a Coffee page — paste the link or just your username\n'
                '(e.g. https://buymeacoffee.com/janszafranski  or  janszafranski):')
            if not ok or not txt.strip(): return
            url = txt.strip()
        if not url.lower().startswith('http'):
            url = 'https://buymeacoffee.com/' + url.strip().strip('/').split('/')[-1]
        self.settings.setValue('bmcUrl', url)
        accent = self.palette_accent()
        c = self.view.mapToScene(self.view.viewport().rect().center())
        o = mk('button', 0, 0, w=200, h=44)
        o.update(html='<p>☕ Buy me a coffee</p>', font='Arial', size=14, bold=True,
                 align='center', radius=6, fill=accent, color=self.ink_for(accent),
                 link={'type': 'url', 'target': url})
        o['x'] = self.view.snap(max(0, c.x() - o['w'] / 2)); o['y'] = self.view.snap(max(0, c.y() - o['h'] / 2))
        self.add_object(o)
        self.hint(f'Added a Buy Me a Coffee button → {url}. Drag it where you like; the link is saved for next time.')

    def insert_contact(self, field):
        """Drop a text frame showing a contact detail from Site Properties.
        Email becomes a clickable mailto: link; website a clickable link."""
        c = self.site.get('contact', {})
        if not any(c.values()):
            QMessageBox.information(self, APP, 'No contact details yet.\n\nAdd them first in '
                                    'Help ▸ Settings (the “Contact details” fields).')
            return
        def esc_(s): return H.escape(s or '')
        rows = []
        if field == 'all':
            if c.get('name'): rows.append(f'<p><b>{esc_(c["name"])}</b></p>')
            if c.get('email'): rows.append(f'<p><a href="mailto:{esc_(c["email"])}">{esc_(c["email"])}</a></p>')
            if c.get('phone'): rows.append(f'<p>{esc_(c["phone"])}</p>')
            if c.get('address'): rows.append(f'<p>{esc_(c["address"])}</p>')
            if c.get('website'):
                u = c['website']; u = u if u.startswith('http') else 'https://' + u
                rows.append(f'<p><a href="{esc_(u)}">{esc_(c["website"])}</a></p>')
        else:
            v = c.get(field, '')
            if not v:
                QMessageBox.information(self, APP, f'The “{field}” field is empty in Settings (Help ▸ Settings).'); return
            if field == 'email': rows.append(f'<p><a href="mailto:{esc_(v)}">{esc_(v)}</a></p>')
            elif field == 'website':
                u = v if v.startswith('http') else 'https://' + v
                rows.append(f'<p><a href="{esc_(u)}">{esc_(v)}</a></p>')
            else: rows.append(f'<p>{esc_(v)}</p>')
        html = '\n'.join(rows)
        cc = self.view.mapToScene(self.view.viewport().rect().center())
        o = mk('text', 0, 0, 300, 40 + 22 * max(0, len(rows) - 1), html=html)
        o['x'] = self.view.snap(max(0, cc.x() - o['w'] / 2)); o['y'] = self.view.snap(max(0, cc.y() - o['h'] / 2))
        self.add_object(o)

    def add_object(self, o):
        self.commit(); self.layer().append(o); self.sel = [o['id']]; self.refresh()

    # ------------------------------------------------------------ editing objects
    def edit_object(self, o):
        if not o or o.get('locked'): return
        t = o['type']
        if t in ('text', 'artistic', 'button'): self.start_edit(o)
        elif t == 'picture': self.pick_picture(o)
        elif t == 'table': self.table_dialog(o)
        elif t == 'html': self.html_dialog(o)
        elif t == 'form': self.form_dialog(o)
        elif t == 'gallery': self.gallery_dialog(o)
        elif t == 'share': self.share_dialog(o)
        elif t == 'nav': self.nav_dialog(o)

    def start_edit(self, o, select_all=False):
        it = self.items.get(o['id'])
        if not it: return
        self.select([o['id']])
        self.edit_snap = self.snapshot(); self.edit_id = o['id']
        ed = TextEditor(it, self); doc = make_doc(o); ed._doc = doc; ed.setDocument(doc)
        ed.setDefaultTextColor(QColor(o.get('color', '#000')))
        pad = o.get('pad', 8) if o['type'] == 'text' else 0
        ed.setTextWidth(max(10, o['w'] - 2 * pad))
        ed.setPos(pad, (o['h'] - doc.size().height()) / 2 if o['type'] == 'button' else pad)
        ed.setTextInteractionFlags(Qt.TextEditorInteraction)
        it.editing = True; it.update(); self.editor = ed
        self.set_sw_mode('text')   # so the Colour mixer / swatches land on the text you're editing
        ed.setFocus()
        c = ed.textCursor()
        if select_all: c.select(QTextCursor.Document)
        else: c.movePosition(QTextCursor.End)
        ed.setTextCursor(c)
        self.view.viewport().update()
        self.hint('Typing. Click outside the text or press Esc to finish.')

    def finish_edit(self):
        ed = self.editor
        if not ed: return
        self.editor = None
        o = self.find(self.edit_id); it = self.items.get(self.edit_id)
        html = ed.document().toHtml()
        m = re.search(r'<body[^>]*>(.*)</body>', html, re.S)
        frag = m.group(1).strip() if m else html
        if o and frag != o.get('html'):
            plain = ed.document().toPlainText().strip()
            self.push_undo(self.edit_snap)
            if not plain and o['type'] in ('text', 'artistic'):
                self.layer().remove(o); self.sel = []
            else:
                o['html'] = frag
                if o['type'] == 'artistic':
                    o['w'] = max(o['w'], math.ceil(ed.document().idealWidth()) + 4)
            self.dirty = True
        if it: it.editing = False
        try: ed.setParentItem(None); self.view.scene().removeItem(ed)
        except RuntimeError: pass
        self.refresh()

    def text_style(self, key):
        if self.editor:
            c = self.editor.textCursor(); fmt = QTextCharFormat(); cur = c.charFormat()
            if key == 'bold': fmt.setFontWeight(QFont.Normal if cur.fontWeight() > QFont.Normal else QFont.Bold)
            elif key == 'italic': fmt.setFontItalic(not cur.fontItalic())
            else: fmt.setFontUnderline(not cur.fontUnderline())
            c.mergeCharFormat(fmt); self.editor.setTextCursor(c); return
        objs = [o for o in self.sel_objs() if o['type'] in ('text', 'artistic', 'button', 'nav', 'table', 'form')]
        if not objs: return
        val = not objs[0].get(key)
        self.commit()
        for o in objs:
            o[key] = val
            if o.get('html'): o['html'] = clear_text_format(o, [key])
        self.refresh()

    def text_list(self, style):
        """Turn the selected paragraphs into a bulleted/numbered list.
        style: 'disc', 'circle', 'square', 'decimal', 'lower-alpha', 'upper-alpha',
               'lower-roman', 'upper-roman', or 'none' to remove the list."""
        if not self.editor:
            self.hint('Double-click a text frame to edit it, then choose a list style.')
            return
        from PySide6.QtGui import QTextListFormat
        c = self.editor.textCursor()
        if style == 'none':
            lst = c.currentList()
            if lst:
                # unwrap: remove each block from the list
                blk = c.block()
                fmt = blk.blockFormat(); fmt.setObjectIndex(-1)
                c.setBlockFormat(fmt)
            self.editor.setTextCursor(c); return
        STYLES = {'disc': QTextListFormat.ListDisc, 'circle': QTextListFormat.ListCircle,
                  'square': QTextListFormat.ListSquare, 'decimal': QTextListFormat.ListDecimal,
                  'lower-alpha': QTextListFormat.ListLowerAlpha, 'upper-alpha': QTextListFormat.ListUpperAlpha,
                  'lower-roman': QTextListFormat.ListLowerRoman, 'upper-roman': QTextListFormat.ListUpperRoman}
        lf = QTextListFormat(); lf.setStyle(STYLES.get(style, QTextListFormat.ListDisc)); lf.setIndent(1)
        c.createList(lf)
        self.editor.setTextCursor(c)

    def set_prop(self, key, val):
        if self.editor and key in ('font', 'size', 'color'):
            c = self.editor.textCursor()
            if c.hasSelection():          # change only the selected words
                fmt = QTextCharFormat()
                if key == 'font': fmt.setFontFamilies([val])
                elif key == 'size': fmt.setProperty(QTextFormat.Property.FontPixelSize, int(val))
                else: fmt.setForeground(QColor(val))
                c.mergeCharFormat(fmt); self.editor.setTextCursor(c); self.editor.setFocus(); return
        if self.editor: self.finish_edit()
        objs = self.sel_objs()
        if not objs: return
        self.commit()
        for o in objs:
            if o.get('locked'): continue
            o[key] = val
            if key in TEXT_PROPS and o.get('html'):
                o['html'] = clear_text_format(o, [key])
                if o['type'] == 'text':   # grow the frame so bigger text isn't cut off
                    o['h'] = max(o['h'], math.ceil(make_doc(o).size().height()) + 2 * o.get('pad', 8) + 2)
            if key == 'align' and 'html' in o:
                o['html'] = re.sub(r'\s+align="\w+"', '', o['html'])
            if key == 'size' and o['type'] == 'artistic':
                o['h'] = max(o['h'], round(val * 1.35))
        self.refresh()

    def studio_set(self, key, val):
        if self._updating: return
        objs = self.sel_objs()
        if not objs: return
        self.commit()
        for o in objs:
            if o.get('locked'): continue
            if key == 'h' and o['type'] == 'artistic' and o['h']: o['size'] = max(4, round(o['size'] * val / o['h']))
            o[key] = val
        for o in objs:
            it = self.items.get(o['id'])
            if it: it.sync()
        self.view.viewport().update(); self.update_rulers()
        self.update_title()

    def set_bg(self, c):
        self.commit()
        m = self.cur_master()
        if m: m['bg'] = c
        else: self.page()['bg'] = c
        self.refresh()

    def apply_swatch(self, c):
        objs = self.sel_objs()
        if not objs:
            if self.sw_mode == 'fill': self.set_bg(c)
            return
        self.commit()
        self._apply_colour(objs, c)
        self.refresh()

    def _apply_colour(self, objs, c):
        """Set the current swatch colour (fill / line / text) on objs. No undo or refresh."""
        key = {'fill': 'fill', 'line': 'stroke', 'text': 'color'}[self.sw_mode]
        for o in objs:
            if o.get('locked'): continue
            if key == 'fill' and o['type'] == 'nav' and o.get('style') != 'plain' and c: o['accent'] = c
            elif key == 'fill' and o['type'] == 'form': o['accent'] = c or o['accent']
            elif key == 'stroke' and c and o['type'] != 'line' and not o.get('strokeW'): o['stroke'] = c; o['strokeW'] = 2
            elif key == 'color' and not c: continue
            else: o[key] = c

    # ------------------------------------------------------------ Colour mixer
    def _col_is_hsl(self):
        return self.col_mode.currentText() == 'HSL'

    def col_mode_changed(self, *_):
        self._updating_col = True
        caps = ('H', 'S', 'L') if self._col_is_hsl() else ('R', 'G', 'B')
        rng = (359, 100, 100) if self._col_is_hsl() else (255, 255, 255)
        for lab, cap, s, sp, hi in zip(self.col_labels, caps, self.col_sliders, self.col_spins, rng):
            lab.setText(cap); s.setRange(0, hi); sp.setRange(0, hi)
        self._updating_col = False
        self.refresh_colour()

    def _set_sliders_from(self, c):
        self._updating_col = True
        if self._col_is_hsl():
            vals = [max(0, c.hslHue()), round(c.hslSaturation() * 100 / 255), round(c.lightness() * 100 / 255)]
        else:
            vals = [c.red(), c.green(), c.blue()]
        for s, sp, v in zip(self.col_sliders, self.col_spins, vals): s.setValue(v); sp.setValue(v)
        self._updating_col = False
        self.col_hex.setText(c.name())
        self.col_preview.setStyleSheet(f'background:{c.name()}; border:1px solid #888;')

    def _sliders_colour(self):
        a, b, c = [s.value() for s in self.col_sliders]
        return QColor.fromHsl(a, round(b * 255 / 100), round(c * 255 / 100)) if self._col_is_hsl() else QColor(a, b, c)

    def col_from_sliders(self, *_):
        if self._updating_col: return
        self.colour_live(self._sliders_colour().name())

    def col_from_hex(self):
        t = self.col_hex.text().strip()
        if not t.startswith('#'): t = '#' + t
        c = QColor(t)
        if c.isValid():
            self._set_sliders_from(c); self.colour_live(c.name()); self.colour_end()

    def spectrum_pick(self, hexc):
        self._set_sliders_from(QColor(hexc)); self.colour_live(hexc)

    def set_sw_mode(self, mode):
        """Point the swatches/mixer at fill, line or text — keep both toggle rows in step."""
        self.sw_mode = mode
        i = ('fill', 'line', 'text').index(mode)
        for grp in (getattr(self, 'sw_group', None), getattr(self, 'col_group', None)):
            if grp and grp.button(i): grp.button(i).setChecked(True)
        self.refresh_colour()

    def _text_colour_target(self):
        """True when a colour should land on the text being edited, not the whole frame."""
        return self.editor is not None and self.sw_mode == 'text'

    def refresh_colour(self):
        if not hasattr(self, 'col_sliders'): return
        if self._text_colour_target():
            self._set_sliders_from(self.editor.textCursor().charFormat().foreground().color()); return
        objs = self.sel_objs(); key = {'fill': 'fill', 'line': 'stroke', 'text': 'color'}[self.sw_mode]
        c = objs[0].get(key) if objs else None
        if not c and not objs and self.sw_mode == 'fill':
            m = self.cur_master(); c = m.get('bg') if m else self.page_bg()
        self._set_sliders_from(QColor(c) if c else QColor('#000000'))

    def colour_live(self, hexc):
        """Apply a colour from the mixer, coalescing a drag into one undo step."""
        self.col_hex.setText(hexc); self.col_preview.setStyleSheet(f'background:{hexc}; border:1px solid #888;')
        if self._text_colour_target():       # colour the selected words (or the next ones typed)
            ed = self.editor; c = ed.textCursor()
            fmt = QTextCharFormat(); fmt.setForeground(QColor(hexc))
            c.mergeCharFormat(fmt); ed.setTextCursor(c)
            return
        objs = self.sel_objs()
        if not objs: return
        if not self._col_gesture: self.commit(); self._col_gesture = True
        self._apply_colour(objs, hexc)
        for o in objs:
            it = self.items.get(o['id'])
            if it: it.sync()
        self.view.viewport().update()

    def colour_end(self, *_):
        if self._text_colour_target():
            self._col_gesture = False; return
        objs = self.sel_objs()
        if not objs:
            if self.sw_mode == 'fill': self.apply_swatch(self.col_hex.text())
            self._col_gesture = False; return
        if self._col_gesture:
            self._col_gesture = False; self.refresh()

    # ------------------------------------------------------------ eyedropper
    def start_eyedropper(self, *_):
        self._eyedrop = True
        if hasattr(self, 'eyedrop_btn'): self.eyedrop_btn.setChecked(True)
        self.view.viewport().setCursor(Qt.CrossCursor)
        self.hint('Eyedropper: click anywhere on the page to pick up that colour. Esc to cancel.')

    def cancel_eyedropper(self):
        self._eyedrop = False
        if hasattr(self, 'eyedrop_btn'): self.eyedrop_btn.setChecked(False)
        self.view.viewport().setCursor(Qt.ArrowCursor)

    def eyedropped(self, hexc):
        """A pixel was sampled from the canvas — load it into the mixer and apply to the current target."""
        self.cancel_eyedropper()
        self._set_sliders_from(QColor(hexc))
        if self.editor or self.sel_objs():
            self.colour_live(hexc); self.colour_end()
        self.hint(f'Picked {hexc}')

    def custom_swatch(self):
        c = QColorDialog.getColor(QColor('#2a7d6b'), self, 'Custom colour')
        if c.isValid(): self.apply_swatch(c.name())

    def add_to_palette(self):
        objs = self.sel_objs()
        if not objs: self.hint('Select an object first. Its fill (or text) colour is added to the site palette.'); return
        key = {'fill': 'fill', 'line': 'stroke', 'text': 'color'}[self.sw_mode]
        c = objs[0].get(key)
        if c and c not in self.site['palette']:
            self.commit(); self.site['palette'].append(c); self.refresh()

    # ------------------------------------------------------------ dialogs for objects
    def pick_picture(self, o):
        # Offer a file OR an AI-generated image.
        box = QMessageBox(self); box.setWindowTitle('Add a picture'); box.setIcon(QMessageBox.Question)
        box.setText('Where should the picture come from?')
        bf = box.addButton('From a file…', QMessageBox.AcceptRole)
        ba_ = box.addButton('Create with AI…', QMessageBox.AcceptRole)
        box.addButton(QMessageBox.Cancel)
        box.exec()
        if box.clickedButton() is ba_:
            self.ai_picture(o); return
        if box.clickedButton() is not bf: return
        path, _ = QFileDialog.getOpenFileName(self, 'Choose a picture', os.path.expanduser('~/Pictures'),
                                              'Pictures (*.png *.jpg *.jpeg *.gif *.webp *.svg);;All files (*)')
        if not path: return
        ext = os.path.splitext(path)[1].lower().lstrip('.')
        mime = {'jpg': 'jpeg', 'jpeg': 'jpeg', 'png': 'png', 'gif': 'gif', 'webp': 'webp', 'svg': 'svg+xml'}.get(ext)
        with open(path, 'rb') as fh: data = fh.read()
        if not mime or mime == 'svg+xml':
            img = QImage(path)
            if img.isNull(): QMessageBox.warning(self, APP, "That file couldn't be read as a picture."); return
            ba = QByteArray(); buf = QBuffer(ba); buf.open(QIODevice.WriteOnly); img.save(buf, 'PNG'); data = bytes(ba); mime = 'png'
        uri = f'data:image/{mime};base64,' + base64.b64encode(data).decode()
        self._apply_picture(o, uri)

    def _apply_picture(self, o, uri):
        self.commit(); o['src'] = add_asset(self.site, uri)
        pm = pixmap_for(self.site, o['src'])
        if pm and not pm.isNull() and o['w'] == DEF['picture']['w'] and o['h'] == DEF['picture']['h']:
            o['h'] = round(o['w'] * pm.height() / pm.width())
        self.refresh()

    # ------------------------------------------------------------ Assets panel
    def refresh_assets(self):
        """Fill the Assets panel with a thumbnail of every image in the site."""
        if not hasattr(self, 'asset_list'): return
        self.asset_list.clear()
        names = self.site.get('assetnames', {})
        flt = getattr(self, 'asset_filter', 'all')
        for key, uri in self.site.get('assets', {}).items():
            if not isinstance(uri, str) or not uri.startswith('data:image'): continue
            is_svg = 'svg' in uri[:20]
            if flt == 'graphics' and not is_svg: continue
            if flt == 'pictures' and is_svg: continue
            pm = pixmap_for(self.site, key)
            icon = QIcon(pm.scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation)) if pm and not pm.isNull() else QIcon()
            it = QListWidgetItem(icon, '')
            it.setData(Qt.UserRole, key); it.setToolTip(names.get(key, key))
            self.asset_list.addItem(it)
        if hasattr(self.asset_list, 'relayout'): self.asset_list.relayout()

    def asset_browse_folder(self):
        d = QFileDialog.getExistingDirectory(self, 'Add every picture from a folder', os.path.expanduser('~/Pictures'))
        if not d: return
        exts = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg')
        files = [os.path.join(d, f) for f in sorted(os.listdir(d)) if f.lower().endswith(exts)]
        if not files: self.hint('No pictures found in that folder.'); return
        self.commit(); added = 0
        for path in files:
            uri = self.picture_uri(path)
            if not uri: continue
            k = add_asset(self.site, uri); self.site.setdefault('assetnames', {})[k] = os.path.basename(path); added += 1
        self.refresh_assets(); self.hint(f'Added {added} picture(s) to Assets — double-click one to place it.')

    def asset_add_file(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Add a picture to assets', os.path.expanduser('~/Pictures'),
                                              'Pictures (*.png *.jpg *.jpeg *.gif *.webp *.svg)')
        if not path: return
        uri = self.picture_uri(path)
        if not uri: QMessageBox.warning(self, APP, "That file couldn't be read as a picture."); return
        self.commit(); k = add_asset(self.site, uri)
        self.site.setdefault('assetnames', {})[k] = os.path.basename(path)
        self.refresh_assets(); self.hint('Added to Assets — double-click it to place it on the page.')

    def asset_add_ai(self):
        o = {'type': 'picture', 'x': 0, 'y': 0, 'w': DEF['picture']['w'], 'h': DEF['picture']['h']}
        # Reuse the AI generation flow, but only to register the asset (not place it).
        from PySide6.QtWidgets import QProgressDialog
        c = self.site.get('contact', {})  # noqa (keeps behaviour parallel to ai_picture)
        self.ai_picture(o)
        self.refresh_assets()

    def asset_insert(self, it):
        key = it.data(Qt.UserRole) if it else None
        if not key: return
        cc = self.view.mapToScene(self.view.viewport().rect().center())
        self.place_asset_at(key, cc)

    def _picture_at(self, key, scene_pt, off=0):
        """Build (but don't add) a picture object for `key`, sized to the asset's aspect
        ratio and centred on `scene_pt` (snapped to the grid). `off` cascades multiples."""
        o = mk('picture', 0, 0)
        pm = pixmap_for(self.site, key)
        if pm and not pm.isNull():
            o['h'] = round(o['w'] * pm.height() / pm.width())
        o['src'] = key
        o['x'] = self.view.snap(max(0, scene_pt.x() - o['w'] / 2 + off))
        o['y'] = self.view.snap(max(0, scene_pt.y() - o['h'] / 2 + off))
        return o

    def place_asset_at(self, key, scene_pt):
        """Place an existing asset as a picture on the current page at `scene_pt`.
        Used by double-click (page centre) and by dragging a thumbnail onto the page."""
        if not key or key not in self.site.get('assets', {}): return
        self.add_object(self._picture_at(key, scene_pt))

    def _download(self, url):
        """Fetch bytes from an http(s) URL for a picture dragged in from a web browser.
        Deliberately uses urllib (not QNetworkAccessManager + a nested QEventLoop): a
        nested event loop is unsafe while QtWebEngine — which the preview uses — is live,
        and could freeze the app. This blocks the GUI thread briefly under a wait cursor
        instead. Returns the raw bytes (capped at 25 MB), or None on any error/timeout."""
        import urllib.request
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'WEBcreator'})
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.read(25 * 1024 * 1024) or None
        except Exception:
            return None

    def _source_uri(self, src):
        """Turn a dropped picture source into (data_uri, display_name), or (None, None).
        `src` is ('file', path) | ('url', http-url) | ('img', QImage)."""
        kind, val = src
        if kind == 'file':
            return self.picture_uri(val), os.path.basename(val)
        if kind == 'img':
            ba = QByteArray(); buf = QBuffer(ba); buf.open(QIODevice.WriteOnly); val.save(buf, 'PNG')
            return 'data:image/png;base64,' + bytes(ba.toBase64()).decode(), 'image'
        if kind == 'url':
            data = self._download(val)
            if not data: return None, None
            from urllib.parse import urlparse, unquote
            path = urlparse(val).path
            name = os.path.basename(unquote(path)) or 'image'
            ext = os.path.splitext(path)[1].lower().lstrip('.')
            mime = {'jpg': 'jpeg', 'jpeg': 'jpeg', 'png': 'png', 'gif': 'gif', 'webp': 'webp', 'svg': 'svg+xml'}.get(ext)
            if mime:
                return f'data:image/{mime};base64,' + base64.b64encode(data).decode(), name
            img = QImage()
            if img.loadFromData(data):
                ba = QByteArray(); buf = QBuffer(ba); buf.open(QIODevice.WriteOnly); img.save(buf, 'PNG')
                return 'data:image/png;base64,' + bytes(ba.toBase64()).decode(), name
            return None, None
        return None, None

    def import_asset_files(self, sources, place_at=None):
        """Register dropped pictures as assets. `sources` is a list of ('file', path) /
        ('url', http-url) / ('img', QImage) — a bare string is treated as a local file
        path (so the file picker can reuse this). If `place_at` (a scene point) is given,
        also drop each onto the current page; the whole import+placement is one undo step."""
        norm = [('file', s) if isinstance(s, str) else tuple(s) for s in sources]
        remote = any(k == 'url' for k, _ in norm)
        if remote: QApplication.setOverrideCursor(Qt.WaitCursor)
        added = []
        try:
            for src in norm:
                uri, name = self._source_uri(src)
                if not uri: continue
                if not added: self.commit()   # one undo snapshot before the first change
                k = add_asset(self.site, uri)
                self.site.setdefault('assetnames', {})[k] = name or 'image'
                added.append(k)
        finally:
            if remote: QApplication.restoreOverrideCursor()
        if not added:
            QMessageBox.warning(self, APP, "No pictures could be read from that drop."); return
        self.refresh_assets()
        if place_at is None:
            self.hint(f'Added {len(added)} picture(s) to Assets — double-click one to place it.'); return
        off, ids = 0, []
        for k in added:
            o = self._picture_at(k, place_at, off); self.layer().append(o); ids.append(o['id']); off += 24
        self.sel = ids; self.refresh()
        self.hint(f'Added {len(added)} picture(s) and placed them on the page.')

    def asset_context_menu(self, pos):
        """Right-click a thumbnail in the Assets panel: insert it, or delete the asset
        from the site (with a warning if it's currently used on a page)."""
        it = self.asset_list.itemAt(pos)
        if not it: return
        key = it.data(Qt.UserRole)
        if not key: return
        name = self.site.get('assetnames', {}).get(key, key)
        m = QMenu(self)
        m.addAction(ticon(['insert-image', 'gtk-add'], ''), 'Insert on page', lambda: self.asset_insert(it))
        m.addSeparator()
        m.addAction(ticon(['edit-delete', 'trash-empty'], ''), 'Delete asset…', lambda: self.delete_asset(key))
        m.exec(self.asset_list.viewport().mapToGlobal(pos))

    def _asset_usage(self, key):
        """How many objects (across all pages and masters) reference this asset key."""
        n = 0
        for coll in (self.site.get('pages', []), self.site.get('masters', [])):
            for pg in coll:
                for o in pg.get('objects', []):
                    if o.get('src') == key or (o.get('srcs') and key in o.get('srcs')):
                        n += 1
        return n

    def delete_asset(self, key):
        """Remove an image from the site's asset library. Warns first if it's in use."""
        name = self.site.get('assetnames', {}).get(key, key)
        used = self._asset_usage(key)
        if used:
            msg = (f'“{name}” is used {used} time(s) on your pages.\n\n'
                   'Deleting it will leave those picture boxes empty. Delete it anyway?')
        else:
            msg = f'Delete “{name}” from your assets? This cannot be undone.'
        if QMessageBox.question(self, APP, msg, QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        self.commit()
        self.site.get('assets', {}).pop(key, None)
        self.site.get('assetnames', {}).pop(key, None)
        self.dirty = True
        self.refresh_assets()
        self.hint(f'Deleted “{name}” from assets.')

    def ai_picture(self, o):
        """Generate an image from a text prompt. Provider is set in Site Properties;
        default is Pollinations (free, no account). OpenAI/Stability need an API key."""
        dlg = QDialog(self); dlg.setWindowTitle('Create an image with AI'); dlg.setMinimumWidth(460)
        v = QVBoxLayout(dlg)
        v.addWidget(QLabel('<b>Describe the picture you want:</b>'))
        prompt = QPlainTextEdit(); prompt.setPlaceholderText('e.g. a calm watercolour of a lighthouse at dawn, soft colours')
        prompt.setFixedHeight(80); v.addWidget(prompt)
        prov = self.settings.value('aiProvider', 'pollinations')
        v.addWidget(QLabel(f'<span style="color:gray">Using: <b>{prov}</b> — change in Help ▸ Settings.</span>'))
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText('Generate')
        bb.accepted.connect(dlg.accept); bb.rejected.connect(dlg.reject); v.addWidget(bb)
        if dlg.exec() != QDialog.Accepted: return
        text = prompt.toPlainText().strip()
        if not text: return
        from PySide6.QtWidgets import QProgressDialog
        prog = QProgressDialog('Generating image…', None, 0, 0, self)
        prog.setWindowModality(Qt.ApplicationModal); prog.setMinimumDuration(0); prog.show()
        QApplication.processEvents()
        try:
            data, mime = ai_generate_image(text, prov, self.settings)
        except Exception as ex:
            prog.close(); QMessageBox.warning(self, APP, f'Image generation failed.\n{ex}'); return
        prog.close()
        if not data:
            QMessageBox.warning(self, APP, 'No image was returned. Try a different description, or check your internet / API key.')
            return
        uri = f'data:image/{mime};base64,' + base64.b64encode(data).decode()
        self._apply_picture(o, uri)

    def table_dialog(self, o):
        cells = o.get('cells') or [['']]
        dlg = QDialog(self); dlg.setWindowTitle('Edit Table'); dlg.resize(620, 380); lay = QVBoxLayout(dlg)
        top = QHBoxLayout(); lay.addLayout(top)
        rs = QSpinBox(); rs.setRange(1, 60); rs.setValue(len(cells)); cs = QSpinBox(); cs.setRange(1, 20); cs.setValue(max(len(r) for r in cells))
        top.addWidget(QLabel('Rows:')); top.addWidget(rs); top.addWidget(QLabel('Columns:')); top.addWidget(cs); top.addStretch()
        tw = QTableWidget(len(cells), cs.value()); lay.addWidget(tw)
        for i, row in enumerate(cells):
            for j, v in enumerate(row): tw.setItem(i, j, QTableWidgetItem(re.sub('<[^>]+>', '', str(v))))
        rs.valueChanged.connect(tw.setRowCount); cs.valueChanged.connect(tw.setColumnCount)
        lay.addWidget(QLabel('The first row is the header row.'))
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); bb.accepted.connect(dlg.accept); bb.rejected.connect(dlg.reject); lay.addWidget(bb)
        if dlg.exec():
            self.commit()
            o['cells'] = [[H.escape(tw.item(i, j).text()) if tw.item(i, j) else '' for j in range(tw.columnCount())] for i in range(tw.rowCount())]
            self.refresh()

    def picture_uri(self, path):
        ext = os.path.splitext(path)[1].lower().lstrip('.')
        mime = {'jpg': 'jpeg', 'jpeg': 'jpeg', 'png': 'png', 'gif': 'gif', 'webp': 'webp'}.get(ext)
        if mime:
            with open(path, 'rb') as fh: return f'data:image/{mime};base64,' + base64.b64encode(fh.read()).decode()
        img = QImage(path)
        if img.isNull(): return None
        ba = QByteArray(); buf = QBuffer(ba); buf.open(QIODevice.WriteOnly); img.save(buf, 'PNG')
        return 'data:image/png;base64,' + bytes(ba.toBase64()).decode()

    def share_dialog(self, o):
        dlg = QDialog(self); dlg.setWindowTitle('Share Buttons'); lay = QVBoxLayout(dlg)
        lab = QLabel('Visitors click a button to share the page they are on. Tick the sites to show; drag to change the order.')
        lab.setWordWrap(True); lay.addWidget(lab)
        lst = QListWidget(); lst.setDragDropMode(QAbstractItemView.InternalMove); lay.addWidget(lst)
        order = list(o.get('nets', [])) + [n[0] for n in SHARE_NETS if n[0] not in o.get('nets', [])]
        for nid in order:
            it = QListWidgetItem(swatch_icon(NET[nid][2], 16), NET[nid][1]); it.setData(Qt.UserRole, nid)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable); it.setCheckState(Qt.Checked if nid in o.get('nets', []) else Qt.Unchecked)
            lst.addItem(it)
        form = QFormLayout(); lay.addLayout(form)
        style = QComboBox(); style.addItems(['Coloured buttons', 'Outlined buttons']); style.setCurrentIndex(1 if o.get('style') == 'outline' else 0)
        size = QSpinBox(); size.setRange(9, 32); size.setSuffix(' px'); size.setValue(int(o.get('size', 14)))
        form.addRow('Look:', style); form.addRow('Text size:', size)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); bb.accepted.connect(dlg.accept); bb.rejected.connect(dlg.reject); lay.addWidget(bb)
        if dlg.exec():
            self.commit()
            o['nets'] = [lst.item(i).data(Qt.UserRole) for i in range(lst.count()) if lst.item(i).checkState() == Qt.Checked]
            o['style'] = 'outline' if style.currentIndex() else 'colour'; o['size'] = size.value()
            self.refresh()

    def nav_dialog(self, o):
        """Edit the navigation bar's spacing, size and look. Lower the spacing/size
        or widen the bar if the items wrap onto a second line."""
        dlg = QDialog(self); dlg.setWindowTitle('Navigation Bar'); lay = QVBoxLayout(dlg)
        lab = QLabel('The bar lists your pages automatically (add or remove pages in the Site panel). '
                     'If the items wrap onto a second line, reduce the spacing or text size below, '
                     'or make the bar wider.')
        lab.setWordWrap(True); lay.addWidget(lab)
        form = QFormLayout(); lay.addLayout(form)
        style = QComboBox(); style.addItems(['Plain', 'Pills', 'Underline', 'Tabs'])
        style.setCurrentIndex({'plain': 0, 'pills': 1, 'underline': 2, 'tabs': 3}.get(o.get('style', 'pills'), 1))
        align = QComboBox(); align.addItems(['Left', 'Centre', 'Right'])
        align.setCurrentIndex({'left': 0, 'center': 1, 'right': 2}.get(o.get('align', 'left'), 0))
        size = QSpinBox(); size.setRange(8, 32); size.setSuffix(' px'); size.setValue(int(o.get('size', 15)))
        gap = QSpinBox(); gap.setRange(0, 60); gap.setSuffix(' px'); gap.setValue(int(o.get('gap', 6)))
        pad = QSpinBox(); pad.setRange(0, 40); pad.setSuffix(' px'); pad.setValue(int(o.get('pad', 14)))
        bold = QCheckBox('Bold'); bold.setChecked(bool(o.get('bold')))
        form.addRow('Look:', style); form.addRow('Align:', align)
        form.addRow('Text size:', size); form.addRow('Space between items:', gap)
        form.addRow('Padding inside items:', pad); form.addRow('', bold)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept); bb.rejected.connect(dlg.reject); lay.addWidget(bb)
        if dlg.exec():
            self.commit()
            o['style'] = ['plain', 'pills', 'underline', 'tabs'][style.currentIndex()]
            o['align'] = ['left', 'center', 'right'][align.currentIndex()]
            o['size'] = size.value(); o['gap'] = gap.value(); o['pad'] = pad.value(); o['bold'] = bold.isChecked()
            self.refresh()

    def gallery_dialog(self, o):
        dlg = QDialog(self); dlg.setWindowTitle('Photo Gallery'); dlg.resize(560, 460); lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel('The photos are shown one after another, in this order.'))
        lst = QListWidget(); lst.setIconSize(QSize(96, 48)); lst.setDragDropMode(QAbstractItemView.InternalMove); lay.addWidget(lst)
        def add_item(key):
            pm = pixmap_for(self.site, key)
            it = QListWidgetItem(QIcon(pm.scaled(96, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation)) if pm else QIcon(),
                                 self.site.get('assetnames', {}).get(key, 'Photo'))
            it.setData(Qt.UserRole, key); lst.addItem(it)
        for k in o.get('images', []): add_item(k)
        row = QHBoxLayout(); lay.addLayout(row)
        def add():
            paths, _ = QFileDialog.getOpenFileNames(dlg, 'Add photos', os.path.expanduser('~/Pictures'), 'Pictures (*.png *.jpg *.jpeg *.gif *.webp)')
            for pth in paths:
                uri = self.picture_uri(pth)
                if uri:
                    key = add_asset(self.site, uri); self.site.setdefault('assetnames', {})[key] = os.path.basename(pth); add_item(key)
        def remove():
            for it in lst.selectedItems(): lst.takeItem(lst.row(it))
        def move(d):
            r_ = lst.currentRow(); n = r_ + d
            if 0 <= r_ < lst.count() and 0 <= n < lst.count():
                it = lst.takeItem(r_); lst.insertItem(n, it); lst.setCurrentRow(n)
        for text, icon, fn in (('Add Photos…', 'list-add', add), ('Remove', 'list-remove', remove),
                               ('Move Up', 'go-up', lambda: move(-1)), ('Move Down', 'go-down', lambda: move(1))):
            b = QPushButton(ticon([icon], ''), text); b.clicked.connect(fn); row.addWidget(b)
        row.addStretch()
        form = QFormLayout(); lay.addLayout(form)
        iv = QDoubleSpinBox(); iv.setRange(1, 60); iv.setSuffix(' s'); iv.setValue(o.get('interval', 5)); form.addRow('Show each photo for:', iv)
        fd = QDoubleSpinBox(); fd.setRange(0, 5); fd.setSingleStep(.1); fd.setSuffix(' s'); fd.setValue(o.get('fade', .5)); form.addRow('Fade between photos:', fd)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); bb.accepted.connect(dlg.accept); bb.rejected.connect(dlg.reject); lay.addWidget(bb)
        if lst.count() == 0: QTimer.singleShot(0, add)
        if dlg.exec():
            self.commit()
            o['images'] = [lst.item(i).data(Qt.UserRole) for i in range(lst.count())]
            o['interval'] = iv.value(); o['fade'] = fd.value()
            self.refresh()

    def html_dialog(self, o):
        ed = QPlainTextEdit(o.get('code', '')); f = ed.font(); f.setFamily('monospace'); f.setStyleHint(QFont.Monospace); ed.setFont(f)
        dlg = QDialog(self); dlg.setWindowTitle('Edit HTML Fragment'); dlg.resize(620, 400); lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel('This code is placed into the page exactly as written when you preview or publish.')); lay.addWidget(ed)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); bb.accepted.connect(dlg.accept); bb.rejected.connect(dlg.reject); lay.addWidget(bb)
        if dlg.exec(): self.commit(); o['code'] = ed.toPlainText(); self.refresh()

    def form_dialog(self, o):
        fields = QPlainTextEdit('\n'.join(o.get('fields', []))); fields.setMinimumHeight(140)
        sub = QLineEdit(o.get('submit', 'Send'))
        dlg = form_dialog(self, 'Edit Form', [('Fields (one per line):', fields), ('Button text:', sub)],
                          QLabel('Published forms need a form handler on your web host to send their contents.'))
        if dlg.exec():
            self.commit(); o['fields'] = [x.strip() for x in fields.toPlainText().splitlines() if x.strip()]; o['submit'] = sub.text() or 'Send'
            o['h'] = max(o['h'], 60 + 70 * len(o['fields'])); self.refresh()

    # ------------------------------------------------------------ hyperlinks
    def link_to_href(self, L):
        if not L: return ''
        return {'page': 'wcpage:', 'file': 'wcfile:', 'email': 'mailto:'}.get(L['type'], '') + L['target']

    def href_to_link(self, href):
        if not href: return None
        for pre, kind in (('wcpage:', 'page'), ('wcfile:', 'file'), ('mailto:', 'email')):
            if href.startswith(pre): return {'type': kind, 'target': href[len(pre):]}
        return {'type': 'url', 'target': href}

    def describe_link(self, L):
        """Where a link goes, in words, and whether it can work."""
        if not L: return 'No link', None
        t, v = L['type'], L.get('target', '')
        if t == 'page':
            pg = self.page_by_id(v)
            return (f'Page in this site: {pg["title"]}', True) if pg else ('Page that no longer exists', False)
        if t == 'file':
            name = self.site.get('assetnames', {}).get(v, 'document')
            return (f'Document: {name}', True) if v in self.site.get('assets', {}) else ('Document that is missing', False)
        if t == 'email': return f'Email: {v}', True
        return f'Website: {v}', None

    def documents(self):
        an = self.site.get('assetnames', {})
        return [(k, an.get(k, 'document')) for k, v in self.site.get('assets', {}).items() if not v.startswith('data:image/')]

    def ask_link(self, L, title='Hyperlink'):
        """Returns a link, None for 'no link', or False if cancelled."""
        L = L or {}
        dlg = QDialog(self); dlg.setWindowTitle(title); dlg.setMinimumWidth(560); lay = QVBoxLayout(dlg)
        grp = QButtonGroup(dlg); rbs = {}; form = QGridLayout(); lay.addLayout(form)
        pages = QComboBox(); [pages.addItem(('    ' if p.get('level') else '') + p['title'], p['id']) for p in self.site['pages']]
        url = QLineEdit(L.get('target', '') if L.get('type') == 'url' else ''); url.setPlaceholderText('https://www.example.org/page')
        mail = QLineEdit(L.get('target', '') if L.get('type') == 'email' else ''); mail.setPlaceholderText('name@example.org')
        docs = QComboBox()
        for k, n in sorted(self.documents(), key=lambda d: d[1].lower()): docs.addItem(n, k)
        docrow = QWidget(); dl = QHBoxLayout(docrow); dl.setContentsMargins(0, 0, 0, 0); dl.addWidget(docs, 1)
        add = QPushButton(ticon(['document-open'], ''), 'Add a File…'); dl.addWidget(add)
        def add_file():
            path, _ = QFileDialog.getOpenFileName(dlg, 'Choose a document to link to', os.path.expanduser('~/Documents'),
                                                  'Documents (*.pdf *.doc *.docx *.odt *.xls *.xlsx *.ods *.ppt *.pptx *.zip *.txt *.mp3 *.mp4 *.jpg *.png);;All files (*)')
            if not path: return
            ext = os.path.splitext(path)[1].lower().lstrip('.')
            with open(path, 'rb') as fh: data = fh.read()
            k = add_asset(self.site, f'data:{MIME.get(ext, "application/octet-stream")};base64,' + base64.b64encode(data).decode())
            self.site.setdefault('assetnames', {})[k] = os.path.basename(path)
            if docs.findData(k) < 0: docs.addItem(os.path.basename(path), k)
            docs.setCurrentIndex(docs.findData(k)); rbs['file'].setChecked(True)
        add.clicked.connect(add_file)
        rows = (('none', 'No link', None), ('page', 'A page in this site', pages), ('url', 'A website', url),
                ('file', 'A document (PDF, Word…)', docrow), ('email', 'An email address', mail))
        for i, (k, lbl, w) in enumerate(rows):
            rb = QRadioButton(lbl); grp.addButton(rb); rbs[k] = rb; form.addWidget(rb, i, 0)
            if w: form.addWidget(w, i, 1)
        if L.get('type') == 'page': pages.setCurrentIndex(max(0, pages.findData(L.get('target'))))
        if L.get('type') == 'file' and docs.findData(L.get('target')) >= 0: docs.setCurrentIndex(docs.findData(L.get('target')))
        rbs.get(L.get('type') or 'none', rbs['none']).setChecked(True)
        pages.activated.connect(lambda *_: rbs['page'].setChecked(True)); url.textEdited.connect(lambda *_: rbs['url'].setChecked(True))
        mail.textEdited.connect(lambda *_: rbs['email'].setChecked(True)); docs.activated.connect(lambda *_: rbs['file'].setChecked(True))
        if L.get('type') == 'url':
            tb = QPushButton(ticon(['internet-web-browser'], ''), 'Open in Browser')
            tb.clicked.connect(lambda: open_external(url.text().strip())); form.addWidget(tb, 2, 2)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); bb.accepted.connect(dlg.accept); bb.rejected.connect(dlg.reject); lay.addWidget(bb)
        if not dlg.exec(): return False
        if rbs['page'].isChecked(): return {'type': 'page', 'target': pages.currentData()}
        if rbs['url'].isChecked() and url.text().strip():
            u = url.text().strip(); return {'type': 'url', 'target': u if re.match(r'^[a-z]+:', u, re.I) else 'https://' + u}
        if rbs['file'].isChecked() and docs.currentData(): return {'type': 'file', 'target': docs.currentData()}
        if rbs['email'].isChecked() and mail.text().strip(): return {'type': 'email', 'target': mail.text().strip()}
        return None

    def hyperlink_dialog(self):
        if self.editor: return self.text_link_dialog()
        objs = [o for o in self.sel_objs() if o['type'] not in ('nav', 'form', 'share')]
        if not objs:
            self.hint('Select a picture, button or box to link it, or double-click into text and select some words.'); return
        link = self.ask_link(objs[0].get('link'), 'Hyperlink for ' + TYPE_NAMES[objs[0]['type']].lower())
        if link is False: return
        self.commit()
        for o in objs: o['link'] = link
        self.refresh()
        self.hint(('Link set: ' + self.describe_link(link)[0]) if link else 'Link removed.')

    def text_link_dialog(self):
        ed = self.editor; c = ed.textCursor()
        if not c.hasSelection():
            href = c.charFormat().anchorHref()
            if not href:
                self.hint('Select the words you want to turn into a link, then choose Hyperlink again (Ctrl+K).'); return
            # select the whole existing link around the cursor
            b = c.block(); it = b.begin()
            while not it.atEnd():
                f = it.fragment()
                if f.charFormat().anchorHref() == href and f.position() <= c.position() <= f.position() + f.length():
                    c.setPosition(f.position()); c.setPosition(f.position() + f.length(), QTextCursor.KeepAnchor); break
                it += 1
        cur = self.href_to_link(c.charFormat().anchorHref() if c.charFormat().isAnchor() else '')
        link = self.ask_link(cur, 'Link selected text')
        ed.setFocus()
        if link is False: ed.setTextCursor(c); return
        o = self.find(self.edit_id)
        fmt = QTextCharFormat()
        if link:
            fmt.setAnchor(True); fmt.setAnchorHref(self.link_to_href(link))
            fmt.setForeground(QColor('#1155cc')); fmt.setFontUnderline(True)
        else:
            fmt.setAnchor(False); fmt.setAnchorHref('')
            fmt.setForeground(QColor((o or {}).get('color', '#000000'))); fmt.setFontUnderline(False)
        c.mergeCharFormat(fmt); ed.setTextCursor(c)
        self.hint(('Link set: ' + self.describe_link(link)[0]) if link else 'Link removed.')

    def link_at(self, it, sp):
        """The link under a point on the canvas: the object's own link, or a link inside its text."""
        o = it.o
        if o['type'] in ('text', 'artistic', 'button') and o.get('html') and 'href=' in o['html']:
            key = (o['id'], o['html'], o['w'], o.get('size'), o.get('font'))
            cache = self.__dict__.setdefault('_doc_cache', {})
            if key not in cache:
                if len(cache) > 200: cache.clear()
                cache[key] = make_doc(o)
            doc = cache[key]; pad = o.get('pad', 8) if o['type'] == 'text' else 0
            y0 = (o['h'] - doc.size().height()) / 2 if o['type'] == 'button' else pad
            lp = it.mapFromScene(sp) - QPointF(pad, y0)
            href = doc.documentLayout().anchorAt(lp)
            if href: return self.href_to_link(href)
        return o.get('link')

    def follow_link(self, L):
        if not L: return
        t, v = L['type'], L['target']
        if t == 'page' and self.page_by_id(v): self.goto_page(v)
        elif t == 'url': open_external(v)
        elif t == 'email': open_external('mailto:' + v)
        elif t == 'file' and v in self.site.get('assets', {}):
            name = re.sub(r'[^A-Za-z0-9._-]+', '-', self.site.get('assetnames', {}).get(v, v))
            path = os.path.join(self.preview_dir, name)
            with open(path, 'wb') as fh: fh.write(base64.b64decode(self.site['assets'][v].split(',', 1)[1]))
            open_external(path, is_file=True)

    # ------------------------------------------------------------ link checker
    def all_links(self):
        rows = []
        layers = [(p, p['title'], p['objects']) for p in self.site['pages']] + \
                 [(m, f'Master page: {m["name"]}', m['objects']) for m in self.site['masters']]
        for owner, where, objs in layers:
            for o in objs:
                if o.get('link'):
                    rows.append(dict(owner=owner, where=where, obj=o, kind='obj', link=o['link'], label=TYPE_NAMES[o['type']], n=0))
                seen = collections.Counter()
                for m in re.finditer(r'<a\s[^>]*href="([^"]*)"[^>]*>(.*?)</a>', o.get('html', ''), re.S):
                    href = H.unescape(m.group(1)); seen[href] += 1
                    txt = re.sub(r'\s+', ' ', H.unescape(re.sub('<[^>]+>', '', m.group(2)))).strip() or '(link)'
                    rows.append(dict(owner=owner, where=where, obj=o, kind='text', link=self.href_to_link(href), href=href,
                                     label=f'“{txt[:60]}”', n=seen[href] - 1))
        return rows

    def check_links(self):
        if self.editor: self.finish_edit()
        rows = self.all_links()
        dlg = QDialog(self); dlg.setWindowTitle('Check Links'); dlg.resize(1000, 600); lay = QVBoxLayout(dlg)
        summary = QLabel(); summary.setWordWrap(True); lay.addWidget(summary)
        top = QHBoxLayout(); lay.addLayout(top)
        show = QComboBox(); show.addItems(['All links', 'Problems only', 'Website links', 'Links to pages', 'Documents', 'Email'])
        top.addWidget(QLabel('Show:')); top.addWidget(show); top.addStretch()
        test = QPushButton(ticon(['network-connect', 'view-refresh'], ''), 'Test Website Links'); top.addWidget(test)
        tbl = QTableWidget(0, 4); tbl.setHorizontalHeaderLabels(['Page', 'Link', 'Goes to', 'Status'])
        tbl.setEditTriggers(QAbstractItemView.NoEditTriggers); tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        tbl.verticalHeader().hide(); tbl.setWordWrap(False)
        hh = tbl.horizontalHeader(); hh.setStretchLastSection(True)
        for i, wdt in enumerate((230, 250, 330)): tbl.setColumnWidth(i, wdt)
        lay.addWidget(tbl, 1)
        bot = QHBoxLayout(); lay.addLayout(bot)
        bot.addWidget(QLabel('Double-click a row to go to it.')); bot.addStretch()
        change = QPushButton(ticon(['insert-link', 'document-edit'], ''), 'Change Link…'); bot.addWidget(change)
        close = QPushButton('Close'); close.clicked.connect(dlg.accept); bot.addWidget(close)
        web = {}   # url -> (ok: True/False/None, words)
        good, bad, warn = QColor('#2e7d32'), QColor('#c62828'), QColor('#b26a00')

        def status(r):
            words, ok = self.describe_link(r['link'])
            if r['link'] and r['link']['type'] == 'url':
                res = web.get(r['link']['target'])
                if res: return words, res[1], res[0]
                return words, 'Not tested yet', None
            return words, ('Works' if ok else 'Broken'), ok

        def fill():
            mode = show.currentIndex(); tbl.setRowCount(0); n_bad = n_ok = n_unk = 0
            for r in rows:
                words, st, ok = status(r)
                if ok is False: n_bad += 1
                elif ok: n_ok += 1
                else: n_unk += 1
                t = (r['link'] or {}).get('type')
                if mode == 1 and ok is not False: continue
                if mode == 2 and t != 'url': continue
                if mode == 3 and t != 'page': continue
                if mode == 4 and t != 'file': continue
                if mode == 5 and t != 'email': continue
                i = tbl.rowCount(); tbl.insertRow(i)
                for j, v in enumerate((r['where'], r['label'], words, st)):
                    it = QTableWidgetItem(v); it.setToolTip(v); tbl.setItem(i, j, it)
                tbl.item(i, 0).setData(Qt.UserRole, rows.index(r))
                if ok is not None: tbl.item(i, 3).setForeground(good if ok else bad)
                elif st != 'Not tested yet': tbl.item(i, 3).setForeground(warn)
            untested = sum(1 for r in rows if r['link'] and r['link']['type'] == 'url' and r['link']['target'] not in web)
            summary.setText(f'<b>{len(rows)} links.</b> {n_ok} work, <span style="color:{bad.name()}">{n_bad} broken</span>, {n_unk} to check'
                            + (f' ({untested} website links not tested yet: click <i>Test Website Links</i>, it needs an internet connection).' if untested else '.'))
        show.currentIndexChanged.connect(fill)

        def current():
            i = tbl.currentRow()
            return rows[tbl.item(i, 0).data(Qt.UserRole)] if i >= 0 and tbl.item(i, 0) else None

        def go(*_):
            r = current()
            if not r: return
            if r['owner'] in self.site['masters']: self.goto_master(r['owner']['id'])
            else: self.goto_page(r['owner']['id'])
            self.select([r['obj']['id']])
            it = self.items.get(r['obj']['id'])
            if it: self.view.centerOn(it)
        tbl.cellDoubleClicked.connect(go)

        def change_link():
            r = current()
            if not r: return
            link = self.ask_link(r['link'], 'Change Link')
            if link is False: return
            self.commit(); o = r['obj']
            if r['kind'] == 'obj': o['link'] = link
            else:
                old = 'href="' + H.escape(r['href'], quote=True) + '"'
                parts = o['html'].split(old)
                if len(parts) > r['n'] + 1:
                    if link:
                        o['html'] = old.join(parts[:r['n'] + 1]) + 'href="' + H.escape(self.link_to_href(link), quote=True) + '"' + old.join(parts[r['n'] + 1:])
                    else:   # unlink: keep the words
                        m = re.compile(r'<a\s[^>]*' + re.escape(old) + r'[^>]*>(.*?)</a>', re.S)
                        hits = list(m.finditer(o['html']))
                        if len(hits) > r['n']:
                            h = hits[r['n']]; o['html'] = o['html'][:h.start()] + h.group(1) + o['html'][h.end():]
            rows[:] = self.all_links(); self.refresh(); fill()
        change.clicked.connect(change_link)

        def run_test():
            from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
            urls = sorted({r['link']['target'] for r in rows if r['link'] and r['link']['type'] == 'url' and r['link']['target'] not in web})
            if not urls: return
            nam = QNetworkAccessManager(dlg); queue = list(urls); live = [0]; total = len(urls)
            test.setEnabled(False); test.setText('Checking the internet connection…')
            def probe_done(pr):
                ok = pr.attribute(QNetworkRequest.HttpStatusCodeAttribute) is not None
                why = pr.errorString(); pr.deleteLater()
                if not ok:
                    test.setText('Test Website Links'); test.setEnabled(True)
                    QMessageBox.warning(dlg, 'Check Links', "Couldn't reach the internet, so website links can't be tested right now.\n\n" + why)
                    return
                start_next()
            pr = nam.get(QNetworkRequest(QUrl('https://www.wikipedia.org/')))
            pr.metaDataChanged.connect(lambda: pr.attribute(QNetworkRequest.HttpStatusCodeAttribute) and pr.abort())
            pr.finished.connect(lambda: probe_done(pr))
            def start_next():
                while queue and live[0] < 6:
                    u = queue.pop(0); live[0] += 1
                    req = QNetworkRequest(QUrl(u)); req.setTransferTimeout(15000)
                    req.setAttribute(QNetworkRequest.RedirectPolicyAttribute, QNetworkRequest.NoLessSafeRedirectPolicy)
                    req.setRawHeader(b'User-Agent', b'Mozilla/5.0 (X11; Linux x86_64) WEBcreator-link-check')
                    rep_ = nam.get(req); rep_.setProperty('u', u)
                    rep_.metaDataChanged.connect(lambda r_=rep_: r_.attribute(QNetworkRequest.HttpStatusCodeAttribute) and r_.abort())
                    rep_.finished.connect(lambda r_=rep_: done(r_))
            def done(r_):
                u = r_.property('u'); code = r_.attribute(QNetworkRequest.HttpStatusCodeAttribute); err = r_.error()
                if code:
                    code = int(code)
                    if code < 400: web[u] = (True, 'Works')
                    elif code in (404, 410): web[u] = (False, f'Broken: page not found ({code})')
                    elif code in (401, 403, 405, 429, 999): web[u] = (None, f'Site refused the check ({code}); open it to be sure')
                    else: web[u] = (False if code >= 500 else None, f'Site error ({code})')
                elif err == QNetworkReply.HostNotFoundError: web[u] = (False, 'Broken: website no longer exists')
                elif err in (QNetworkReply.TimeoutError, QNetworkReply.OperationCanceledError): web[u] = (None, 'No reply (site slow or down)')
                else: web[u] = (False, 'Broken: ' + r_.errorString()[:60])
                r_.deleteLater(); live[0] -= 1
                test.setText(f'Testing… {len([x for x in urls if x in web])} of {total}')
                if len([x for x in urls if x in web]) % 10 == 0 or not queue: fill()
                if queue: start_next()
                elif live[0] == 0: test.setText('Test Website Links'); test.setEnabled(True); fill()
        test.clicked.connect(run_test)
        fill(); dlg.exec()

    # ------------------------------------------------------------ pages
    def goto_page(self, pid):
        if self.editor: self.finish_edit()
        if not pid: return
        self.cur_page = pid; self.edit_master = None; self.sel = []; self.refresh()

    def goto_master(self, mid):
        if self.editor: self.finish_edit()
        self.edit_master = mid; self.sel = []; self.refresh()

    def insert_page_dialog(self):
        title = QLineEdit('New Page')
        pos = QComboBox(); pos.addItems(['After the current page', 'Before the current page', 'At the end of the site'])
        sub = QCheckBox('Make it a sub-page (shows in a drop-down menu)')
        mas = QComboBox(); [mas.addItem(m['name'], m['id']) for m in self.site['masters']]
        mas.setCurrentIndex(max(0, mas.findData(self.page()['master'])))
        dlg = form_dialog(self, 'Insert Page', [('Page name:', title), ('Position:', pos), ('Master page:', mas), ('', sub)])
        title.selectAll()
        if not dlg.exec(): return
        self.commit()
        i = self.site['pages'].index(self.page())
        idx = {0: i + 1, 1: i, 2: len(self.site['pages'])}[pos.currentIndex()]
        if idx == 1 and False: pass
        lvl = 1 if sub.isChecked() and idx > 0 else 0
        p = add_page(self.site, title.text().strip() or 'New Page', lvl, index=idx, master=mas.currentData())
        if idx == 0 and self.site['pages'][1]['file'] == 'index.html': pass
        self.goto_page(p['id'])

    def insert_index_page(self):
        # Auto-generate a grouped, hyperlinked index of every other page in the site.
        existing = next((p for p in self.site['pages']
                         if (p.get('title') or '').strip().lower() in ('index', 'sitemap')
                         or 'index' in (p.get('title') or '').lower()
                         or 'sitemap' in (p.get('file') or '').lower()
                         or p.get('file') == 'index-2.html'), None)
        target = None
        if existing:
            b = QMessageBox(self); b.setWindowTitle('Insert Index Page')
            b.setText(f'An index page (“{existing["title"]}”) already exists.')
            b.setInformativeText('Update that page, or create a new one?')
            upd = b.addButton('Update existing', QMessageBox.AcceptRole)
            new = b.addButton('Create new', QMessageBox.ActionRole)
            b.addButton(QMessageBox.Cancel); b.exec()
            if b.clickedButton() is upd: target = existing
            elif b.clickedButton() is new: target = None
            else: return
        self.commit()
        if target is None:
            target = add_page(self.site, 'Index', master=self.page()['master'])
        html, n = build_index_html(self.site, target['id'])
        txt = next((o for o in target['objects'] if o['type'] == 'text'), None)
        if txt is None:
            txt = mk('text', 28, 262, self.site['width'] - 56, 120)
            target['objects'].append(txt)
        txt['html'] = html
        h = 262 + 40 + n * 24 + sum(28 for _ in range(html.count('font-size:22px'))) + 40
        txt['w'] = self.site['width'] - 56
        txt['h'] = max(120, h - 262)
        target['height'] = max(self.site['height'], h)
        self.goto_page(target['id']); self.refresh()
        QMessageBox.information(self, APP, f'Index page {"updated" if existing and target is existing else "created"} with {n} links.')

    def delete_page(self):
        if len(self.site['pages']) < 2: QMessageBox.information(self, APP, 'A site needs at least one page.'); return
        p = self.page()
        if QMessageBox.question(self, 'Delete Page', f'Delete the page “{p["title"]}” and everything on it?') != QMessageBox.Yes: return
        self.commit(); i = self.site['pages'].index(p); self.site['pages'].remove(p)
        if p['file'] == 'index.html': self.site['pages'][0]['file'] = 'index.html'
        if self.site['pages'][0].get('level'): self.site['pages'][0]['level'] = 0
        for q in self.site['pages']:
            for o in q['objects']:
                if o.get('link') and o['link'].get('target') == p['id']: o['link'] = None
        self.cur_page = self.site['pages'][max(0, i - 1)]['id']; self.sel = []; self.refresh()

    def move_page(self, d):
        ps = self.site['pages']; p = self.page(); i = ps.index(p); j = i + d
        if not 0 <= j < len(ps): return
        self.commit(); ps[i], ps[j] = ps[j], ps[i]
        if ps[0].get('level'): ps[0]['level'] = 0
        self.refresh()

    def indent_page(self, step):
        """Move the current page one level in or out, not to a fixed level.

        An imported WebPlus site nests as deep as it likes, so "make sub-page"
        has to mean one step in from where this page already is.
        """
        ps = self.site['pages']; p = self.page(); i = ps.index(p)
        if step > 0 and i == 0: self.hint('The first page cannot be a sub-page.'); return
        ceiling = (int(ps[i - 1].get('level') or 0) + 1) if i else 0
        lvl = max(0, min(int(p.get('level') or 0) + step, ceiling))
        if lvl == int(p.get('level') or 0): return
        self.commit(); p['level'] = lvl; self.refresh()

    def page_props(self, p):
        if not p: return
        title = QLineEdit(p['title']); file = QLineEdit(p['file'])
        mas = QComboBox(); [mas.addItem(m['name'], m['id']) for m in self.site['masters']]; mas.setCurrentIndex(max(0, mas.findData(p['master'])))
        nav = QCheckBox('Include this page in navigation bars'); nav.setChecked(p.get('nav', True))
        hh = QSpinBox(); hh.setRange(0, 30000); hh.setSpecialValueText('Site default'); hh.setValue(p.get('height') or 0); hh.setSuffix(' px')
        bgc = [p.get('bg', '')]
        bgb = ColorButton(p.get('bg') or self.master_of(p).get('bg'), lambda c: (bgc.__setitem__(0, c), bgb.setIcon(swatch_icon(c or self.master_of(p).get('bg'), 18))), 'Page background', allow_none=True)
        bgb.setToolTip('Choose None to use the master page background')
        dlg = form_dialog(self, 'Page Properties', [('Page name:', title), ('File name:', file), ('Master page:', mas), ('Height:', hh),
                                                     ('Background:', bgb), ('', nav)])
        if not dlg.exec(): return
        fn = re.sub(r'[^A-Za-z0-9._-]+', '-', file.text().strip()) or slug(title.text(), set())
        if not fn.lower().endswith(('.html', '.htm')): fn += '.html'
        if any(q['file'] == fn and q is not p for q in self.site['pages']):
            QMessageBox.warning(self, APP, f'Another page already uses the file name {fn}.'); return
        self.commit()
        p.update(title=title.text().strip() or p['title'], file=fn, master=mas.currentData(), nav=nav.isChecked(),
                 height=hh.value() or None, bg=bgc[0])
        self.refresh()

    def site_props(self):
        # Site properties were merged into the single Settings dialog (Help ▸
        # Settings); this stays so the page toolbar's button still works.
        return self.update_settings()

    def seo_dialog(self):
        """Per-page SEO editor (Yoast-style) for the current page: title/description
        overrides, focus keyword, no-index, social image, plus a live readability
        check panel that grades the page against the focus keyword."""
        if self.editor: self.finish_edit()
        p = self.page()
        if not p: return
        seo = dict(p.get('seo', {}) or {})
        t = QLineEdit(seo.get('title', ''))
        t.setPlaceholderText(f'{p["title"]} | {self.site["name"]}  (default if blank)')
        d = QPlainTextEdit(seo.get('description', '')); d.setFixedHeight(80)
        d.setPlaceholderText('Blank = auto-generated from the page text')
        kw = QLineEdit(seo.get('keyword', ''))
        noindex = QCheckBox('Hide this page from search engines (noindex)')
        noindex.setChecked(bool(seo.get('noindex')))
        # OG image picker — reuse the Site Properties "choose picture" pattern.
        ogpic = [seo.get('og_image') or '']
        ogb = QPushButton(self.site.get('assetnames', {}).get(ogpic[0], ogpic[0] or 'Site default / none')
                          if ogpic[0] else 'Site default / none')
        ogm = QMenu(ogb)
        def choose_og():
            path, _ = QFileDialog.getOpenFileName(self, 'Social preview image', os.path.expanduser('~/Pictures'),
                                                  'Pictures (*.png *.jpg *.jpeg *.gif *.webp)')
            uri = self.picture_uri(path) if path else None
            if uri:
                k = add_asset(self.site, uri); self.site.setdefault('assetnames', {})[k] = os.path.basename(path)
                ogpic[0] = k; ogb.setText(os.path.basename(path))
        ogm.addAction('Choose picture…', choose_og)
        ogm.addAction('Use site default / none', lambda: (ogpic.__setitem__(0, ''), ogb.setText('Site default / none')))
        ogb.setMenu(ogm)
        dchars = QLabel(); kwlist = QLabel(); kwlist.setWordWrap(True); kwlist.setTextFormat(Qt.RichText)
        def analyse():
            txt = d.toPlainText().strip()
            eff_title = t.text().strip() or f'{p["title"]} | {self.site["name"]}'
            eff_desc = txt or _page_text(p)
            n = len(txt)
            colour = 'green' if 120 <= n <= 160 else ('orange' if n else 'gray')
            dchars.setText(f'<span style="color:{colour}">{n} characters</span> '
                           f'(Google shows about 120–160)')
            k = kw.text().strip().lower()
            body = _page_text(p).lower()
            first_para = (body.split('. ')[0] if body else '')
            def line(ok, warn, label):
                mark = '✓' if ok else ('⚠' if warn else '✗')
                col = 'green' if ok else ('orange' if warn else '#c0392b')
                return f'<span style="color:{col}">{mark} {esc(label)}</span>'
            if not k:
                kwlist.setText('<i style="color:gray">Enter a focus keyword to see the keyword checks.</i>')
                return
            tl, dl = len(eff_title), len(eff_desc)
            rows = [
                line(k in eff_title.lower(), False, 'Focus keyword is in the SEO title'),
                line(k in eff_desc.lower(), False, 'Focus keyword is in the meta description'),
                line(k in first_para, k in body, 'Focus keyword appears in the first paragraph'),
                line(30 <= tl <= 60, 0 < tl < 30 or 60 < tl <= 70, f'SEO title length is good (30–60) — now {tl}'),
                line(120 <= dl <= 160, 0 < dl < 120 or 160 < dl <= 180, f'Meta description length is good (120–160) — now {dl}'),
            ]
            kwlist.setText('<br>'.join(rows))
        d.textChanged.connect(analyse); t.textChanged.connect(analyse); kw.textChanged.connect(analyse)
        analyse()
        panel = QGroupBox('Readability & keyword check')
        pv = QVBoxLayout(panel); pv.addWidget(dchars); pv.addWidget(kwlist)
        dlg = form_dialog(self, f'SEO — {p["title"]}',
                          [('SEO title:', t), ('Meta description:', d), ('Focus keyword:', kw),
                           ('Social image:', ogb), ('', noindex)], panel)
        if not dlg.exec(): return
        self.commit()
        new = {'title': t.text().strip(), 'description': d.toPlainText().strip(),
               'keyword': kw.text().strip(), 'og_image': ogpic[0], 'noindex': noindex.isChecked()}
        # keep any canonical already stored; drop empty keys to stay tidy / byte-stable
        if p.get('seo', {}).get('canonical'): new['canonical'] = p['seo']['canonical']
        new = {k: v for k, v in new.items() if v}
        if new: p['seo'] = new
        else: p.pop('seo', None)
        self.dirty = True; self.hint('Page SEO saved.')

    def site_seo_dialog(self):
        """Site-wide SEO defaults: base web address (needed for canonical URLs,
        sitemap and absolute social images), default social image, Twitter handle
        and organisation details (for JSON-LD)."""
        if self.editor: self.finish_edit()
        seo = dict(self.site.get('seo', {}) or {})
        base = QLineEdit(seo.get('base_url', '')); base.setPlaceholderText('https://www.your-site.com')
        tw = QLineEdit(seo.get('twitter_site', '')); tw.setPlaceholderText('@yourhandle (optional)')
        org = QLineEdit(seo.get('org_name', ''))
        ot = QComboBox()
        for v in ('Organization', 'LocalBusiness', 'Person', 'Corporation', 'NGO', 'EducationalOrganization'):
            ot.addItem(v, v)
        ot.setCurrentIndex(max(0, ot.findData(seo.get('org_type', 'Organization'))))
        ogpic = [seo.get('og_image') or '']
        ogb = QPushButton(self.site.get('assetnames', {}).get(ogpic[0], ogpic[0] or 'Choose picture…')
                          if ogpic[0] else 'Choose picture…')
        ogm = QMenu(ogb)
        def choose_og():
            path, _ = QFileDialog.getOpenFileName(self, 'Default social image', os.path.expanduser('~/Pictures'),
                                                  'Pictures (*.png *.jpg *.jpeg *.gif *.webp)')
            uri = self.picture_uri(path) if path else None
            if uri:
                k = add_asset(self.site, uri); self.site.setdefault('assetnames', {})[k] = os.path.basename(path)
                ogpic[0] = k; ogb.setText(os.path.basename(path))
        ogm.addAction('Choose picture…', choose_og)
        ogm.addAction('No default image', lambda: (ogpic.__setitem__(0, ''), ogb.setText('Choose picture…')))
        ogb.setMenu(ogm)
        dlg = form_dialog(self, 'Site-wide SEO',
                          [('Web address (base URL):', base), ('Default social image:', ogb),
                           ('Twitter / X handle:', tw), ('Organisation name:', org), ('Organisation type:', ot)],
                          QLabel('A base web address lets the site build canonical links, a sitemap.xml and '
                                 'absolute social-preview image URLs when you publish.'))
        if not dlg.exec(): return
        self.commit()
        new = {'base_url': base.text().strip().rstrip('/'), 'og_image': ogpic[0],
               'twitter_site': tw.text().strip(), 'org_name': org.text().strip(), 'org_type': ot.currentData()}
        # Only keep org_type when there's an org_name; drop empties to stay byte-stable
        if not new['org_name']: new.pop('org_type', None)
        new = {k: v for k, v in new.items() if v}
        if new: self.site['seo'] = new
        else: self.site.pop('seo', None)
        self.dirty = True; self.hint('Site-wide SEO saved.')

    def auto_seo(self):
        """Fill in SEO (title + meta description + focus keyword) for every page
        automatically, from each page's own text — then offer to publish. If an
        OpenAI key is set in Settings, the text can be AI-written; otherwise a
        fast built-in generator is used. Existing hand-written SEO is kept unless
        the user asks to overwrite."""
        if self.editor: self.finish_edit()
        pages = self.site['pages']
        key = self.settings.value('aiOpenAIKey', '') or ''

        # One dialog gathers the choices: scope, overwrite, and (if available) AI.
        dlg = QDialog(self); dlg.setWindowTitle('Auto-generate SEO'); dlg.setMinimumWidth(480)
        v = QVBoxLayout(dlg)
        v.addWidget(QLabel('<b>Generate search-engine titles, descriptions and keywords '
                           'for your pages.</b>'))
        only_missing = QRadioButton('Only pages that have no SEO yet'); only_missing.setChecked(True)
        all_over = QRadioButton('Every page — overwrite what’s already there')
        v.addWidget(only_missing); v.addWidget(all_over)
        use_ai = QCheckBox('Write the text with AI (OpenAI) — slower, higher quality')
        if key:
            use_ai.setToolTip('Uses the OpenAI key from Settings')
        else:
            use_ai.setEnabled(False)
            use_ai.setText('Write the text with AI (OpenAI) — add an OpenAI key in Help ▸ Settings to enable')
        v.addWidget(use_ai)
        note = QLabel('The built-in generator writes a tidy description from each page’s own text — '
                      'no account needed, and it’s instant.')
        note.setWordWrap(True); note.setStyleSheet('color:gray'); v.addWidget(note)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText('Generate')
        bb.accepted.connect(dlg.accept); bb.rejected.connect(dlg.reject); v.addWidget(bb)
        if not dlg.exec(): return
        overwrite = all_over.isChecked()
        ai = use_ai.isChecked() and bool(key)

        self.commit()
        from PySide6.QtWidgets import QProgressDialog
        prog = QProgressDialog('Generating SEO…', 'Cancel', 0, len(pages), self)
        prog.setWindowTitle(APP); prog.setWindowModality(Qt.WindowModal); prog.setMinimumDuration(0)
        site_name = self.site.get('name', '')
        done = ai_used = ai_failed = 0
        for i, p in enumerate(pages):
            if prog.wasCanceled(): break
            prog.setValue(i); prog.setLabelText(f'Generating SEO… ({i + 1}/{len(pages)})\n{p["title"]}')
            QApplication.processEvents()
            cur = dict(p.get('seo', {}) or {})
            has_all = cur.get('title') and cur.get('description') and cur.get('keyword')
            if has_all and not overwrite:
                continue
            # Body in visual reading order (top-to-bottom, left-to-right) so the
            # description flows like the page, not in object-creation order.
            ordered = sorted((o for o in p['objects'] if o.get('type') == 'text'),
                             key=lambda o: (o.get('y', 0), o.get('x', 0)))
            body = re.sub(r'\s+', ' ', H.unescape(re.sub(r'<[^>]+>', ' ',
                          ' '.join(o.get('html', '') for o in ordered)))).strip()
            if not body.strip():
                continue
            fields = None
            if ai:
                try:
                    fields = _ai_seo_fields(key, p['title'], body, site_name); ai_used += 1
                except Exception:
                    ai_failed += 1
            if not fields:
                fields = _auto_seo_fields(p['title'], body, site_name,
                                          keep_title=('' if overwrite else cur.get('title', '')))
            # Keep any existing value unless overwriting (or the field is empty).
            merged = dict(cur)
            for k2, val in fields.items():
                if val and (overwrite or not cur.get(k2)):
                    merged[k2] = val
            merged = {k2: val for k2, val in merged.items() if val}
            if merged:
                p['seo'] = merged; done += 1
        prog.setValue(len(pages))

        self.dirty = True; self.update_title()
        msg = f'SEO generated for {done} page(s).'
        if ai: msg += f'\nAI wrote {ai_used}; '  + (f'{ai_failed} fell back to the built-in generator.' if ai_failed else 'no fallbacks needed.')
        if not (self.site.get('seo') or {}).get('base_url'):
            msg += ('\n\nTip: set your web address in SEO ▸ Site-wide SEO so the site can build a '
                    'sitemap.xml and proper links.')
        msg += '\n\nPublish the updated site now?'
        if QMessageBox.question(self, APP, msg, QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes) == QMessageBox.Yes:
            self.publish_disk()
        else:
            self.hint(f'SEO generated for {done} page(s). Publish when you’re ready.')

    def new_master(self):
        self.commit()
        n = len(self.site['masters'])
        m = dict(id=uid(), name=f'Master {chr(65 + n % 26)}', bg='#ffffff', objects=[])
        self.site['masters'].append(m); self.goto_master(m['id'])

    def master_props(self):
        it = self.mlist.currentItem()
        m = next((x for x in self.site['masters'] if it and x['id'] == it.data(Qt.UserRole)), None)
        if not m: return
        name = QLineEdit(m['name']); bgc = [m.get('bg', '#ffffff')]
        bgb = ColorButton(bgc[0], lambda c: (bgc.__setitem__(0, c), bgb.setIcon(swatch_icon(c, 18))), 'Background')
        dlg = form_dialog(self, 'Master Page Properties', [('Name:', name), ('Background:', bgb)])
        if dlg.exec(): self.commit(); m['name'] = name.text().strip() or m['name']; m['bg'] = bgc[0]; self.refresh()

    def delete_master(self):
        it = self.mlist.currentItem()
        if not it: return
        if len(self.site['masters']) < 2: QMessageBox.information(self, APP, 'A site needs at least one master page.'); return
        mid = it.data(Qt.UserRole); m = next(x for x in self.site['masters'] if x['id'] == mid)
        if QMessageBox.question(self, 'Delete Master Page', f'Delete “{m["name"]}”? Pages that use it will switch to another master page.') != QMessageBox.Yes: return
        self.commit(); self.site['masters'].remove(m)
        for p in self.site['pages']:
            if p['master'] == mid: p['master'] = self.site['masters'][0]['id']
        if self.edit_master == mid: self.edit_master = None
        self.refresh()

    # ------------------------------------------------------------ edit ops
    def do_undo(self):
        if self.editor: self.editor.document().undo(); return
        if not self.undo: return
        self.redo.append(self.snapshot()); self.restore(self.undo.pop()); self.dirty = True; self.refresh()

    def do_redo(self):
        if self.editor: self.editor.document().redo(); return
        if not self.redo: return
        self.undo.append(self.snapshot()); self.restore(self.redo.pop()); self.dirty = True; self.refresh()

    def copy(self):
        if self.editor: self.editor.textCursor().selection() and QApplication.clipboard().setText(self.editor.textCursor().selectedText()); return
        self.clip = copy.deepcopy(self.sel_objs()); self.a['paste'].setEnabled(bool(self.clip))

    def cut(self):
        if self.editor:
            c = self.editor.textCursor(); QApplication.clipboard().setText(c.selectedText()); c.removeSelectedText(); return
        self.copy(); self.delete_sel()

    def paste(self):
        if self.editor: self.editor.textCursor().insertText(QApplication.clipboard().text()); return
        if not self.clip: return
        self.commit(); new = []
        for o in copy.deepcopy(self.clip):
            o['id'] = uid(); o['x'] += 16; o['y'] += 16; self.layer().append(o); new.append(o['id'])
        self.clip = [dict(o, x=o['x'] + 16, y=o['y'] + 16) for o in self.clip]
        self.sel = new; self.refresh()

    def duplicate(self):
        if not self.sel: return
        self.commit(); new = []
        for o in copy.deepcopy(self.sel_objs()):
            o['id'] = uid(); o['x'] += 16; o['y'] += 16; o['locked'] = False; self.layer().append(o); new.append(o['id'])
        self.sel = new; self.refresh()

    def delete_sel(self):
        if self.editor: return
        objs = [o for o in self.sel_objs() if not o.get('locked')]
        if not objs: return
        self.commit()
        for o in objs: self.layer().remove(o)
        self.sel = []; self.refresh()

    def order(self, how):
        L = self.layer(); objs = self.sel_objs()
        if not objs: return
        self.commit()
        if how == 'front':
            for o in objs: L.remove(o); L.append(o)
        elif how == 'back':
            for o in reversed(objs): L.remove(o); L.insert(0, o)
        elif how == 'fwd':
            for o in reversed(objs):
                i = L.index(o)
                if i < len(L) - 1: L[i], L[i + 1] = L[i + 1], L[i]
        elif how == 'back1':
            for o in objs:
                i = L.index(o)
                if i > 0: L[i], L[i - 1] = L[i - 1], L[i]
        self.refresh()

    def align(self, how):
        objs = [o for o in self.sel_objs() if not o.get('locked')]
        if not objs: return
        self.commit()
        if how == 'page' or len(objs) == 1:
            W, Hh = self.site['width'], self.page_h()
            for o in objs:
                if how in ('page', 'hcenter'): o['x'] = round((W - o['w']) / 2)
                elif how == 'left': o['x'] = 0
                elif how == 'right': o['x'] = W - o['w']
                elif how == 'top': o['y'] = 0
                elif how == 'bottom': o['y'] = Hh - o['h']
                elif how == 'vcenter': o['y'] = round((Hh - o['h']) / 2)
        else:
            l = min(o['x'] for o in objs); r = max(o['x'] + o['w'] for o in objs)
            t = min(o['y'] for o in objs); b = max(o['y'] + o['h'] for o in objs)
            for o in objs:
                if how == 'left': o['x'] = l
                elif how == 'right': o['x'] = r - o['w']
                elif how == 'hcenter': o['x'] = round((l + r - o['w']) / 2)
                elif how == 'top': o['y'] = t
                elif how == 'bottom': o['y'] = b - o['h']
                elif how == 'vcenter': o['y'] = round((t + b - o['h']) / 2)
        self.refresh()

    def anchor_toggled(self, v):
        if self._updating: return
        self.studio_set('anchor', 'bottom' if v else None)
        if v: self.make_room_at_bottom()

    def make_room_at_bottom(self, quiet=False):
        """Pages grow where needed, so master objects kept at the bottom never cover page content."""
        grown = 0
        for m in self.site['masters']:
            anchored = [o for o in m['objects'] if o.get('anchor') == 'bottom' and not o.get('hidden')]
            if not anchored: continue
            need = self.site['height'] - min(o['y'] for o in anchored)        # depth of the bottom area
            for p in self.site['pages']:
                if p['master'] != m['id'] or not p['objects']: continue
                ph = p.get('height') or self.site['height']
                bottom = max(o['y'] + o['h'] for o in p['objects'] if not o.get('hidden')) if any(not o.get('hidden') for o in p['objects']) else 0
                extra = bottom + 16 - (ph - need)
                if extra > 0: p['height'] = round(ph + extra); grown += 1
        if grown:
            self.refresh()
            if not quiet: self.hint(f'Made {grown} page(s) taller so the bottom of the master page doesn\'t cover their content.')
        return grown

    def find_repeated(self, share=.8):
        """Objects that appear on most pages using the same master: same kind, same content, same
        horizontal place, and either the same distance from the top or from the bottom."""
        an = self.site.get('assetnames', {})
        def text(o): return re.sub(r'\s+', ' ', H.unescape(re.sub('<[^>]+>', '', o.get('html', '') or o.get('code', '')))).strip()
        def key(o): return (o['type'], o.get('src') or '', text(o), json.dumps(o.get('images')), o.get('shape'), o.get('fill', ''))
        found = []
        for m in self.site['masters']:
            pages = [p for p in self.site['pages'] if p['master'] == m['id']]
            if len(pages) < 2: continue
            groups = {}
            for p in pages:
                ph = p.get('height') or self.site['height']
                for o in p['objects']:
                    if o['type'] == 'shape' and not o.get('fill') and not o.get('strokeW'): continue
                    if o['type'] in ('text', 'artistic', 'button') and not text(o): continue
                    groups.setdefault(key(o), []).append((p, o, ph))
            have = {key(o) for o in m['objects']}
            for k, occ in groups.items():
                pg = {p['id'] for p, _, _ in occ}
                if len(pg) < max(2, share * len(pages)): continue
                geo = collections.Counter((round(o['x']), round(o['w']), round(o['h'])) for _, o, _ in occ).most_common(1)[0][0]
                tops = collections.Counter(round(o['y']) for _, o, _ in occ)
                bots = collections.Counter(round(ph - o['y']) for _, o, ph in occ)
                (top, nt), (bot, nb) = tops.most_common(1)[0], bots.most_common(1)[0]
                if max(nt, nb) < .8 * len(occ): continue          # not in a consistent place
                anchor = 'bottom' if nb > nt else None
                model = next(o for _, o, _ in occ if (round(o['x']), round(o['w']), round(o['h'])) == geo)
                label = an.get(k[1]) or k[2][:60] or TYPE_NAMES[k[0]]
                found.append(dict(master=m, objs=[(p, o) for p, o, _ in occ], model=model, anchor=anchor,
                                  y=top if not anchor else self.site['height'] - bot, pages=len(pg), total=len(pages),
                                  label=f'{TYPE_NAMES[k[0]]}: {label}', already=k in have))
        return found

    def move_common_to_master(self):
        if self.editor: self.finish_edit()
        found = self.find_repeated()
        if not found:
            QMessageBox.information(self, 'Move to Master Page', 'No object appears on most pages, so there is nothing to move.\n\n'
                                    'Objects already on a master page are shown on every page that uses it.'); return
        dlg = QDialog(self); dlg.setWindowTitle('Move Repeated Objects to Master Page'); dlg.resize(620, 360); lay = QVBoxLayout(dlg)
        lab = QLabel('These objects are repeated on most pages. Tick the ones to keep once, on the master page; '
                     'the copies on the individual pages are removed. Your existing master page is kept as it is.')
        lab.setWordWrap(True); lay.addWidget(lab)
        lst = QListWidget(); lay.addWidget(lst)
        for i, f in enumerate(found):
            where = 'kept at the bottom of every page' if f['anchor'] else 'same place on every page'
            extra = ' · already on the master page' if f['already'] else ''
            it = QListWidgetItem(f"{f['label']}\n    on {f['pages']} of {f['total']} pages · {where}{extra}")
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable); it.setCheckState(Qt.Checked); it.setData(Qt.UserRole, i); lst.addItem(it)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); bb.button(QDialogButtonBox.Ok).setText('Move to Master Page')
        bb.accepted.connect(dlg.accept); bb.rejected.connect(dlg.reject); lay.addWidget(bb)
        if not dlg.exec(): return
        chosen = [found[lst.item(i).data(Qt.UserRole)] for i in range(lst.count()) if lst.item(i).checkState() == Qt.Checked]
        if not chosen: return
        self.commit(); removed = 0
        for f in chosen:
            if not f['already']:
                o = copy.deepcopy(f['model']); o['id'] = uid(); o['y'] = f['y']; o['locked'] = False
                if f['anchor']: o['anchor'] = 'bottom'
                f['master']['objects'].append(o)
            for p, o in f['objs']:
                if o in p['objects']: p['objects'].remove(o); removed += 1
        self.sel = []; self.refresh(); self.make_room_at_bottom(quiet=True)
        self.hint(f'Moved {len(chosen)} object(s) to the master page and removed {removed} copies from the pages.')

    def toggle_lock(self):
        objs = self.sel_objs()
        if not objs: return
        self.commit(); v = not objs[0].get('locked')
        for o in objs: o['locked'] = v
        self.refresh()

    def toggle_hidden(self):
        ids = [it.data(Qt.UserRole) for it in self.layers.selectedItems() if it.data(Qt.UserRole)]
        objs = [o for o in self.layer() if o['id'] in ids]
        if not objs: return
        self.commit(); v = not objs[0].get('hidden')
        for o in objs: o['hidden'] = v
        if v: self.sel = []
        self.refresh()

    def context_menu(self, gpos):
        m = QMenu(self)
        if self.sel:
            for k in ('cut', 'copy', 'paste', 'dup', 'delete'): m.addAction(self.a[k])
            m.addSeparator(); m.addAction(self.a['link'])
            ar = m.addMenu('Arrange'); [ar.addAction(self.a[k]) for k in ('front', 'fwd', 'back1', 'back')]
            m.addAction(self.a['lock'])
            o = self.sel_objs()[0]
            if o['type'] in ('text', 'artistic', 'button'): m.addAction('Edit Text', lambda: self.start_edit(o))
            if o['type'] == 'picture': m.addAction('Replace Picture…', lambda: self.pick_picture(o))
            if o['type'] in ('table', 'form', 'html'): m.addAction('Edit…', lambda: self.edit_object(o))
        else:
            m.addAction(self.a['paste']); m.addSeparator(); m.addAction(self.a['pageprops']); m.addAction(self.a['newpage'])
        m.exec(gpos)

    def toggle_rulers(self):
        on = self.a['rulers'].isChecked()
        for w in self.ruler_widgets: w.setVisible(on)
        self.settings.setValue('rulers', on)

    def toggle_grid(self):
        self.show_grid = self.a['grid'].isChecked(); self.settings.setValue('grid', self.show_grid); self.view.viewport().update()

    def toggle_snap(self):
        self.snap_grid = self.a['snap'].isChecked(); self.settings.setValue('snap', self.snap_grid)

    # ------------------------------------------------------------ files
    def recent_files(self):
        r = self.settings.value('recent', [], type=list) or []
        return [p for p in r if isinstance(p, str) and os.path.exists(p)]

    def add_recent(self, path):
        r = [path] + [p for p in self.recent_files() if p != path]
        self.settings.setValue('recent', r[:10])

    def maybe_save(self):
        if self.editor: self.finish_edit()
        if not self.dirty: return True
        r = QMessageBox.question(self, APP, f'Save changes to “{self.site["name"]}” before closing it?',
                                 QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Save)
        if r == QMessageBox.Save: return self.save()
        return r == QMessageBox.Discard

    def set_site(self, site, path=None):
        _PIX.clear()   # drop the cached asset pixmaps so a reopened/updated file shows its current images
        for layer in [p['objects'] for p in site['pages']] + [m['objects'] for m in site['masters']]:
            for i, o in enumerate(layer):
                if o['type'] == 'html' and 'class="share"' in o.get('code', '') and 'data-net' in o.get('code', ''):
                    nets = [{'fb': 'facebook', 'li': 'linkedin', 'mail': 'email'}.get(n, n) for n in re.findall(r'data-net="(\w+)"', o['code'])]
                    n = mk('share', o['x'], o['y'], o['w'], o['h'], nets=[x for x in nets if x in NET]); n['id'] = o['id']
                    for k in ('anchor', 'locked', 'hidden'):
                        if o.get(k): n[k] = o[k]
                    layer[i] = n
        for layer in [p['objects'] for p in site['pages']] + [m['objects'] for m in site['masters']]:
            for o in layer:
                if o['type'] in ('text', 'artistic', 'button') and 'style=' in o.get('html', ''): lift_text_format(o)
        self.site = site; self.site.setdefault('assets', {}); self.path = path; self.dirty = False
        self.undo, self.redo = [], []; self.cur_page = site['pages'][0]['id']; self.edit_master = None; self.sel = []
        _PIX.clear(); self.refresh(); QTimer.singleShot(0, self.view.fit_width)

    def startup(self):
        if not self.maybe_save(): return
        dlg = StartupAssistant(self); self.startup_dlg = dlg
        if dlg.exec():
            if dlg.result_update: self.install_update(); return
            if dlg.result_site: self.set_site(dlg.result_site)
            elif dlg.result_path: self.load_path(dlg.result_path)
            elif dlg.result_webplus: self.load_webplus(*dlg.result_webplus)
            elif dlg.result_import: self.import_folder(skip_save_check=True)

    def import_folder(self, skip_save_check=False):
        if not skip_save_check and not self.maybe_save(): return
        last = self.settings.value('importDir', os.path.expanduser('~'))
        folder = QFileDialog.getExistingDirectory(self, 'Import Website Folder — choose the folder that holds the site', last)
        if not folder: return
        self.settings.setValue('importDir', os.path.dirname(folder))
        from PySide6.QtWidgets import QProgressDialog
        pd = QProgressDialog('Reading pages…', 'Cancel', 0, 100, self); pd.setWindowTitle('Import Website'); pd.setMinimumDuration(0)
        pd.setWindowModality(Qt.WindowModal)
        def progress(i, n, msg):
            pd.setMaximum(n); pd.setValue(i); pd.setLabelText(msg); QApplication.processEvents()
            return not pd.wasCanceled()
        renderer = None
        try:
            renderer = PageRenderer()
        except Exception:
            renderer = None   # web engine not installed: use the simpler flowing layout
        try:
            site = import_site_folder(folder, progress, render=renderer)
        except Exception as ex:
            if renderer: renderer.close()
            pd.close(); QMessageBox.warning(self, 'Import Website', str(ex)); return
        pd.close()
        if renderer: renderer.close()
        missing = site.pop('_import_missing', [])
        self.set_site(site); self.dirty = True; self.update_title()
        msg = (f'Imported {len(site["pages"])} pages from “{os.path.basename(folder)}”.\n\n'
               'Pages were rebuilt from the original layout: check each one and tidy anything that moved. '
               f'Save the site (File ▸ Save As) to keep it as a {EXT} file.')
        if missing: msg += f'\n\n{len(missing)} picture(s) referred to by the pages were not in the folder, for example: {missing[0]}'
        QMessageBox.information(self, 'Import Website', msg)

    def open_dialog(self):
        if not self.maybe_save(): return
        start = os.path.dirname(self.path) if self.path else os.path.expanduser('~')
        path, _ = QFileDialog.getOpenFileName(self, 'Open Site', start, f'WEBcreator sites (*{EXT});;All files (*)')
        if path: self.load_path(path)

    # ------------------------------------------------- Serif WebPlus (.wpp)
    def webplus_root(self, ask=True):
        """The Serif-for-Linux checkout that reads a .wpp, asking for it once."""
        root = wpp_reader_root(self.settings.value('serifRoot', '') or None)
        if root or not ask: return root
        QMessageBox.information(
            self, 'Open WebPlus Site',
            'Reading a WebPlus .wpp needs the Serif-for-Linux reader, which this app '
            "could not find.\n\nChoose the folder of the serif-linux checkout — the one "
            'that holds a “serif” folder with webplus.py in it.')
        folder = QFileDialog.getExistingDirectory(self, 'Where is the serif-linux checkout?',
                                                  os.path.expanduser('~'))
        if not folder: return None
        root = wpp_reader_root(folder, only_hint=True)
        if not root:
            QMessageBox.warning(self, 'Open WebPlus Site',
                                f'{folder} does not hold serif/webplus.py, so it cannot read a .wpp.')
            return None
        self.settings.setValue('serifRoot', root)
        return root

    def open_webplus(self, skip_save_check=False):
        if not skip_save_check and not self.maybe_save(): return
        root = self.webplus_root()
        if not root: return
        last = self.settings.value('wppDir', os.path.expanduser('~'))
        path, _ = QFileDialog.getOpenFileName(self, 'Open WebPlus Site', last,
                                              f'WebPlus publications (*{WPP_EXT});;All files (*)')
        if not path: return
        self.settings.setValue('wppDir', os.path.dirname(path))
        return self.load_webplus(path, root)

    def load_webplus(self, path, root=None):
        root = root or self.webplus_root()
        if not root: return False
        from PySide6.QtWidgets import QProgressDialog
        pd = QProgressDialog('Reading the publication…', 'Cancel', 0, 100, self)
        pd.setWindowTitle('Open WebPlus Site'); pd.setMinimumDuration(0)
        pd.setWindowModality(Qt.WindowModal)
        def progress(i, n, msg):
            pd.setMaximum(n); pd.setValue(i); pd.setLabelText(msg); QApplication.processEvents()
            return not pd.wasCanceled()
        try:
            site = import_webplus_file(path, root, progress)
        except Exception as ex:
            pd.close()
            QMessageBox.warning(self, 'Open WebPlus Site',
                                f"Couldn't open {os.path.basename(path)}.\n\n{ex}")
            return False
        pd.close()
        notes = site.pop('_wpp_notes', {})
        site.pop('_wpp_source', None)
        self.set_site(site); self.dirty = True; self.update_title()
        self.settings.setValue('serifRoot', root)
        QMessageBox.information(self, 'Open WebPlus Site', wpp_summary(site, path, notes))
        return True

    def load_path(self, path):
        try:
            with open(path, encoding='utf-8') as fh: data = json.load(fh)
            site = data.get('site', data)
            assert site.get('pages') and site.get('masters')
        except Exception as ex:
            QMessageBox.warning(self, APP, f"Couldn't open {os.path.basename(path)}.\nIt isn't a {APP} site file, or it is damaged.\n\n{ex}")
            return False
        self.set_site(site, path); self.add_recent(path); return True

    def save(self):
        if self.editor: self.finish_edit()
        if not self.path: return self.save_as()
        return self.write(self.path)

    def save_as(self):
        if self.editor: self.finish_edit()
        start = self.path or os.path.join(os.path.expanduser('~'), re.sub(r'[^\w -]+', '', self.site['name']).strip() + EXT)
        path, _ = QFileDialog.getSaveFileName(self, 'Save Site As', start, f'WEBcreator sites (*{EXT})')
        if not path: return False
        if not path.endswith(EXT): path += EXT
        return self.write(path)

    def write(self, path):
        try:
            used = set()
            for o in [o for p in self.site['pages'] for o in p['objects']] + [o for m in self.site['masters'] for o in m['objects']]:
                if o.get('src'): used.add(o['src'])
                used.update(o.get('images') or [])
                if o.get('link') and o['link'].get('type') == 'file': used.add(o['link'].get('target'))
                used.update(re.findall(r'wcfile:([0-9a-f]+)', o.get('html', '')))
            if self.site.get('bgimage'): used.add(self.site['bgimage'])
            out = dict(self.site); out['assets'] = {k: v for k, v in self.site['assets'].items() if k in used}
            tmp = path + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as fh: json.dump({'app': APP, 'version': VERSION, 'site': out}, fh)
            os.replace(tmp, path)
        except OSError as ex:
            QMessageBox.warning(self, APP, f"Couldn't save to {path}.\n{ex}"); return False
        self.path = path; self.dirty = False; self.add_recent(path); self.update_title()
        self.hint(f'Saved to {path}'); return True

    # ------------------------------------------------------------ preview & publish
    def preview_page(self):
        if self.editor: self.finish_edit()
        self._preview(self.page()['file'])

    def preview_site(self):
        if self.editor: self.finish_edit()
        self._preview(self.site['pages'][0]['file'])

    def _preview(self, file):
        try:
            for f in os.listdir(self.preview_dir):
                fp = os.path.join(self.preview_dir, f)
                if os.path.isfile(fp): os.remove(fp)
            publish_site(self.site, self.preview_dir)
        except Exception as ex:
            # Catch ANY build error (a bad image used to crash this and kill preview silently).
            QMessageBox.warning(self, APP, f"Couldn't build the preview.\n{ex}"); return
        target = os.path.join(self.preview_dir, file)
        if not os.path.exists(target):
            QMessageBox.warning(self, APP, "The preview page couldn't be found after building."); return
        if not open_external(target, is_file=True):
            QMessageBox.warning(self, APP, "Couldn't open a web browser to show the preview.")
            return
        self.hint('Preview opened in your web browser.')

    # ------------------------------------------------------------ Netlify CLI
    def _netlify_cli_token(self):
        """The auth token from an existing `netlify-cli login`
        (~/.config/netlify/config.json). Returns '' if not logged in.

        We read it ourselves and pass it on to the CLI as NETLIFY_AUTH_TOKEN so
        a deploy works no matter what minimal environment the app was launched
        in (a desktop/GUI launcher often has a different HOME/XDG_CONFIG_HOME, so
        the CLI can fail to find its own login and report 'Unauthorized: could
        not retrieve project' even though the user is signed in)."""
        try:
            with open(os.path.expanduser('~/.config/netlify/config.json')) as fh:
                cfg = json.load(fh)
        except (OSError, ValueError):
            return ''
        users = cfg.get('users') or {}
        # Prefer the active user id if the config names one, else any with a token.
        uid = cfg.get('userId')
        order = ([users[uid]] if uid in users else []) + [u for k, u in users.items() if k != uid]
        for info in order:
            tok = ((info or {}).get('auth') or {}).get('token')
            if tok: return tok.strip()
        return ''

    def netlify_token(self):
        """A Netlify access token: env NETLIFY_AUTH_TOKEN wins, then a stored
        ~/.config/webcreator/netlify_token, then an existing netlify-cli login."""
        tok = (os.environ.get('NETLIFY_AUTH_TOKEN') or '').strip()
        if tok: return tok
        try:
            with open(os.path.expanduser('~/.config/webcreator/netlify_token')) as fh:
                tok = fh.read().strip()
                if tok: return tok
        except OSError:
            pass
        return self._netlify_cli_token()

    def netlify_ready(self):
        """True if we can deploy without asking the user to sign in — a token
        from the env, a stored file, or an existing netlify-cli login."""
        return bool(self.netlify_token())

    def _netlify_env(self):
        env = dict(os.environ)
        tok = self.netlify_token()
        if tok: env['NETLIFY_AUTH_TOKEN'] = tok
        return env

    def _netlify_cmd(self):
        """The command to run the Netlify CLI. Prefer a globally installed
        binary (fast — no npx resolution), falling back to `npx --yes netlify-cli`."""
        for exe in ('netlify', 'netlify-cli', 'ntl'):
            p = shutil.which(exe)
            if p: return [p]
        return ['npx', '--yes', 'netlify-cli']

    def _run_netlify(self, args, timeout=300, busy_msg=None):
        """Run the Netlify CLI with <args>; return (ok, stdout, stderr). ok is
        False on a missing CLI, a timeout, a cancel or a non-zero exit.

        Runs via QProcess with a local event loop so the GUI stays alive while
        the deploy uploads: the 'please wait' dialog keeps animating (not frozen)
        and the user can Cancel. subprocess.run would block the UI thread and the
        dialog would look hung — which is exactly what made publishing feel stuck."""
        from PySide6.QtCore import QProcess, QProcessEnvironment, QEventLoop, QTimer
        from PySide6.QtWidgets import QProgressDialog
        cmd = self._netlify_cmd() + list(args)
        proc = QProcess(self)
        qenv = QProcessEnvironment.systemEnvironment()
        tok = self.netlify_token()
        if tok: qenv.insert('NETLIFY_AUTH_TOKEN', tok)
        proc.setProcessEnvironment(qenv)
        out, err = [], []
        proc.readyReadStandardOutput.connect(
            lambda: out.append(bytes(proc.readAllStandardOutput()).decode('utf-8', 'replace')))
        proc.readyReadStandardError.connect(
            lambda: err.append(bytes(proc.readAllStandardError()).decode('utf-8', 'replace')))
        loop = QEventLoop()
        st = {'cancelled': False, 'timed_out': False}
        proc.finished.connect(lambda *a: loop.quit())
        # Cancellable, animated busy dialog (indeterminate 0..0 range = spinning).
        dlg = QProgressDialog(busy_msg or 'Working with Netlify…', 'Cancel', 0, 0, self)
        dlg.setWindowTitle(APP); dlg.setWindowModality(Qt.WindowModal)
        dlg.setMinimumDuration(0); dlg.setAutoClose(False); dlg.setAutoReset(False); dlg.setValue(0)
        dlg.canceled.connect(lambda: (st.__setitem__('cancelled', True), proc.kill(), loop.quit()))
        dlg.show()
        tmr = QTimer(); tmr.setSingleShot(True)
        tmr.timeout.connect(lambda: (st.__setitem__('timed_out', True), proc.kill(), loop.quit()))
        tmr.start(int(timeout * 1000))
        proc.start(cmd[0], cmd[1:])
        if not proc.waitForStarted(5000):
            tmr.stop(); dlg.close()
            return False, '', ('Node.js / npx was not found. Install Node.js to deploy straight to Netlify, '
                               'or use the drag-and-drop option below.')
        loop.exec()
        tmr.stop(); dlg.close()
        if proc.state() != QProcess.NotRunning:
            proc.kill(); proc.waitForFinished(2000)
        out_s, err_s = ''.join(out), ''.join(err)
        if st['cancelled']:
            return False, out_s, 'Publishing was cancelled.'
        if st['timed_out']:
            return False, out_s, f'Netlify took longer than {timeout} seconds and was stopped.'
        ok = proc.exitStatus() == QProcess.NormalExit and proc.exitCode() == 0
        return ok, out_s, err_s

    def _netlify_not_authed(self, out, err):
        blob = (out + '\n' + err).lower()
        return ('not logged in' in blob or 'not authenticated' in blob or 'no auth' in blob
                or 'netlify_auth_token' in blob or 'login' in blob and 'netlify' in blob)

    def publish_netlify(self, folder, files=None):
        """Deploy the published folder to the SAME Netlify site every time (so
        re-publishing updates the live site instead of creating a duplicate).
        Links to a site first if we haven't got one stored. On success shows a
        short popup with how many pages/files changed, not the full guide."""
        import os as _os
        net = self.site.setdefault('netlify', {})
        if not self.netlify_ready():
            if QMessageBox.question(self, APP,
                    'To update your live Netlify site from here you need to connect your Netlify '
                    'account once.\n\nEither run “npx netlify-cli login” in a terminal, or paste a '
                    'Netlify personal access token now (it will be saved to '
                    '~/.config/webcreator/netlify_token).\n\nPaste a token now?') == QMessageBox.Yes:
                tok, ok = QInputDialog.getText(self, 'Netlify token', 'Netlify personal access token:',
                                               QLineEdit.Password)
                if ok and tok.strip():
                    cfg = _os.path.expanduser('~/.config/webcreator'); _os.makedirs(cfg, exist_ok=True)
                    with open(_os.path.join(cfg, 'netlify_token'), 'w') as fh: fh.write(tok.strip())
                    try: _os.chmod(_os.path.join(cfg, 'netlify_token'), 0o600)
                    except OSError: pass
                else:
                    return
            else:
                return
        if not net.get('site_id'):
            if not self.link_netlify(): return
        self.hint('Deploying to Netlify…')
        ok, out, err = self._run_netlify(
            ['deploy', '--prod', '--dir', folder, '--site', net['site_id']],
            busy_msg='Deploying to Netlify — uploading your site…\n\n'
                     'This can take a minute or two (longer the first time).\n'
                     'You can keep working, or Cancel to stop.')
        if not ok and 'cancelled' in err.lower():
            return
        if not ok and self._netlify_not_authed(out, err):
            QMessageBox.warning(self, APP, 'Netlify says you are not signed in.\n\nRun '
                                '“npx netlify-cli login” in a terminal once, then try again.')
            return
        m = re.search(r'https?://[^\s]+', out)
        live = m.group(0) if m else (net.get('url') or '')
        tail = '\n'.join((out + '\n' + err).strip().splitlines()[-12:])
        if ok:
            # Short, friendly confirmation: how much changed this publish.
            stats = getattr(publish_site, 'last_stats', None) or {}
            nch = stats.get('pages_changed'); tot = stats.get('pages_total')
            nfiles = len(stats.get('changed_files', []) or [])
            if tot is None:
                changed_line = ''
            elif nch == 0:
                changed_line = 'No pages had changed since last time — the live site is already up to date.'
            else:
                changed_line = (f'{nch} of {tot} page(s) changed'
                                + (f' ({nfiles} file(s) uploaded)' if nfiles else '')
                                + ' — only the changes were sent.')
            dlg = QDialog(self); dlg.setWindowTitle('Live site updated'); dlg.setMinimumWidth(460)
            dv = QVBoxLayout(dlg)
            head = QLabel('<b>Your live site was updated.</b>'
                          + (f'<br>{esc(live)}' if live else ''))
            head.setWordWrap(True); head.setTextFormat(Qt.RichText); dv.addWidget(head)
            if changed_line:
                cl = QLabel(changed_line); cl.setWordWrap(True); cl.setStyleSheet('color:gray'); dv.addWidget(cl)
            row = QHBoxLayout()
            if live:
                b = QPushButton('Open the live site'); b.clicked.connect(lambda: open_external(live)); row.addWidget(b)
            opt = QPushButton('Publishing options…')
            opt.setToolTip('Change which Netlify site to update, or see other ways to host (drag-drop, GitHub Pages…)')
            opt.clicked.connect(lambda: (dlg.accept(), self.go_online(folder, files if files is not None
                                                                      else publish_site(self.site, folder))))
            row.addWidget(opt); row.addStretch(); dv.addLayout(row)
            bb = QDialogButtonBox(QDialogButtonBox.Close); bb.rejected.connect(dlg.reject); bb.accepted.connect(dlg.accept)
            dv.addWidget(bb); dlg.exec()
        else:
            dlg = QDialog(self); dlg.setWindowTitle('Netlify deploy'); dlg.setMinimumWidth(600)
            dv = QVBoxLayout(dlg)
            dv.addWidget(QLabel('<b>The deploy did not finish.</b> Details below; the drag-and-drop '
                                'option still works as a fallback.'))
            log = QPlainTextEdit(tail); log.setReadOnly(True); log.setFixedHeight(180); dv.addWidget(log)
            row = QHBoxLayout()
            gb = QPushButton('Other ways to publish…')
            gb.clicked.connect(lambda: (dlg.accept(), self.go_online(folder, files if files is not None
                                                                     else publish_site(self.site, folder))))
            row.addWidget(gb); row.addStretch(); dv.addLayout(row)
            bb = QDialogButtonBox(QDialogButtonBox.Close); bb.rejected.connect(dlg.reject); bb.accepted.connect(dlg.accept)
            dv.addWidget(bb); dlg.exec()

    def link_netlify(self):
        """Pick an existing Netlify site to publish to (or create one), and store
        its id/name on the site so future publishes update that same site."""
        self.hint('Fetching your Netlify sites…')
        ok, out, err = self._run_netlify(['sites:list', '--json'], timeout=120)
        if not ok:
            if self._netlify_not_authed(out, err):
                QMessageBox.warning(self, APP, 'Netlify says you are not signed in.\n\nRun '
                                    '“npx netlify-cli login” in a terminal once, then try again.')
            else:
                QMessageBox.warning(self, APP, f'Could not list your Netlify sites.\n\n{err.strip() or out.strip()}')
            return False
        try:
            sites = json.loads(out[out.index('['):])
        except (ValueError, json.JSONDecodeError):
            sites = []
        names = [s.get('name', '(unnamed)') for s in sites]
        choices = names + ['➕ Create a new Netlify site…']
        pick, okp = QInputDialog.getItem(self, 'Link to Netlify',
                                         'Choose the Netlify site to publish to:', choices, 0, False)
        if not okp: return False
        if pick == choices[-1]:
            nm, okn = QInputDialog.getText(self, 'New Netlify site', 'Name for the new site (letters, numbers, dashes):')
            if not (okn and nm.strip()): return False
            cok, cout, cerr = self._run_netlify(['sites:create', '--name', nm.strip(), '--json'], timeout=120)
            if not cok:
                QMessageBox.warning(self, APP, f'Could not create the site.\n\n{cerr.strip() or cout.strip()}')
                return False
            try:
                s = json.loads(cout[cout.index('{'):])
            except (ValueError, json.JSONDecodeError):
                QMessageBox.warning(self, APP, 'The site was created but its details could not be read.'); return False
        else:
            s = sites[names.index(pick)]
        self.site['netlify'] = {'site_id': s.get('site_id') or s.get('id', ''),
                                'name': s.get('name', ''), 'url': s.get('ssl_url') or s.get('url', '')}
        self.dirty = True
        return bool(self.site['netlify']['site_id'])

    def publish_disk(self):
        """Publish = pick Static or Responsive, then show the 'put it online'
        guide. The site files are written automatically to a per-site folder —
        the user never has to think about folders or file browsers.
        """
        if self.editor: self.finish_edit()
        # Step 1: Static or Responsive. No folder browser, no 'to disk'.
        dlg = QDialog(self); dlg.setWindowTitle('Publish your site')
        dlg.setModal(True)
        dl = QVBoxLayout(dlg)
        dl.addWidget(QLabel('<b>Publish your site</b><br>How should it look on different screens?'))
        rb_static = QRadioButton('Static — fixed width (classic; best on desktop)')
        rb_resp = QRadioButton('Responsive — scales to fit any screen (phones, tablets, desktop)')
        (rb_resp if self.site.get('responsive') else rb_static).setChecked(True)
        dl.addWidget(rb_static); dl.addWidget(rb_resp)
        note = QLabel('Responsive keeps your exact design and shrinks the whole page to fit '
                      'narrow screens, so visitors see the full layout without side-scrolling.')
        note.setWordWrap(True); note.setStyleSheet('color:gray'); dl.addWidget(note)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText('Publish')
        bb.accepted.connect(dlg.accept); bb.rejected.connect(dlg.reject); dl.addWidget(bb)
        if dlg.exec() != QDialog.Accepted: return
        self.site['responsive'] = rb_resp.isChecked()
        # Step 2: write the files automatically to a stable per-site folder.
        base = re.sub(r'[^A-Za-z0-9 ._-]+', '', (self.site.get('name') or 'My Site')).strip() or 'My Site'
        folder = self.site.get('publishDir')
        if not folder:
            root = os.path.expanduser('~/Published Sites')
            folder = os.path.join(root, base)
            self.site['publishDir'] = folder
        from PySide6.QtWidgets import QProgressDialog
        _wait = QProgressDialog('Publishing site files…', None, 0, 0, self)
        _wait.setWindowTitle(APP); _wait.setWindowModality(Qt.WindowModal)
        _wait.setMinimumDuration(0); _wait.setValue(0)
        _wait.show(); QApplication.processEvents(); QApplication.processEvents()
        try:
            os.makedirs(folder, exist_ok=True)
            files = publish_site(self.site, folder)
        except OSError as ex:
            _wait.close()
            QMessageBox.warning(self, APP, f"Could not save the site files.\n{ex}"); return
        _wait.close()
        self.settings.setValue('publishDir', folder)
        # Step 3: where to go next.
        # If this site is ALREADY linked to a Netlify site, don't re-present the
        # whole "how to put it online" guide — the user has published before and
        # just wants the live site updated. Deploy straight away and show a short
        # "done" popup with how many pages/files changed. Only an unpublished
        # site (no stored Netlify link) gets the full first-time hosting guide.
        if (self.site.get('netlify') or {}).get('site_id') and self.netlify_ready():
            self.publish_netlify(folder, files)
        else:
            self.go_online(folder, files)

    def go_online(self, folder, files):
        """Guide a non-technical user from a published folder to a live website.

        We can't put the site online for them (that needs their own hosting
        account), so this explains the options in plain English and opens the
        right website for each. Netlify Drop is the recommended, no-account,
        drag-and-drop route; GitHub Pages is offered for people who use GitHub.
        """
        import os as _os
        first_page = _os.path.join(folder, self.site['pages'][0]['file'])
        dlg = QDialog(self); dlg.setWindowTitle('Your site is ready — put it online')
        dlg.setMinimumWidth(620)
        dlg.setModal(True)              # never let it hide behind the main window
        dlg.setWindowModality(Qt.ApplicationModal)
        root = QVBoxLayout(dlg)

        stats = getattr(publish_site, 'last_stats', None)
        if stats and stats['pages_changed'] < stats['pages_total']:
            nch = stats['pages_changed']
            summary = (f'<b>Your website is up to date.</b> '
                       f'{nch if nch else "No"} page(s) changed this time '
                       f'({stats["pages_total"]} total) — only the changes were written into:')
        else:
            summary = (f'<b>Your website is built.</b> '
                       f'{len(self.site["pages"])} page(s) were saved into:')
        head = QLabel(f'{summary}<br><code>{folder}</code>')
        head.setWordWrap(True); head.setTextFormat(Qt.RichText); root.addWidget(head)

        row0 = QHBoxLayout()
        b_view = QPushButton('Preview it now'); b_view.setToolTip('Open the site in your web browser to check it')
        b_view.clicked.connect(lambda: open_external(first_page, is_file=True))
        b_open = QPushButton('Open the folder'); b_open.setToolTip('Open the folder of files you will upload')
        b_open.clicked.connect(lambda: open_external(folder, is_file=True))
        row0.addWidget(b_view); row0.addWidget(b_open); row0.addStretch(); root.addLayout(row0)

        intro = QLabel('To put it on the internet so others can visit, you upload these files to a '
                       '<b>web host</b>. Here are three free ways, easiest first:')
        intro.setWordWrap(True); intro.setTextFormat(Qt.RichText); root.addWidget(intro)

        # --- Publish to Netlify (CLI) — updates the SAME live site every time ---
        net = self.site.get('netlify', {}) or {}
        g0 = QGroupBox('★  Publish to Netlify  —  update my live site (recommended)')
        v0 = QVBoxLayout(g0)
        if net.get('site_id'):
            linked = (f'Linked to your Netlify site <b>{esc(net.get("name", ""))}</b>'
                      + (f' — <code>{esc(net.get("url", ""))}</code>' if net.get('url') else '') + '.<br>')
        else:
            linked = 'Not linked to a Netlify site yet — the first time, you pick which site to update.<br>'
        t0 = QLabel(linked + 'This updates your <b>existing</b> live site in place (no duplicate sites), '
                    'and only the changed files are sent. Needs Node.js and a one-off Netlify sign-in.')
        t0.setWordWrap(True); t0.setTextFormat(Qt.RichText); v0.addWidget(t0)
        h0 = QHBoxLayout()
        pb = QPushButton('Update my live site' if net.get('site_id') else 'Link & publish to Netlify')
        pb.setDefault(True)
        pb.clicked.connect(lambda: self.publish_netlify(folder, files))
        lk = QPushButton('Change which site…')
        lk.clicked.connect(lambda: self.link_netlify())
        h0.addWidget(pb); h0.addWidget(lk); h0.addStretch(); v0.addLayout(h0)
        root.addWidget(g0)

        fb = QLabel('<i>No Netlify account yet? Use drag-and-drop instead:</i>')
        fb.setTextFormat(Qt.RichText); fb.setStyleSheet('color:gray'); root.addWidget(fb)

        # --- Netlify Drop (recommended) ---
        g1 = QGroupBox('1.  Netlify Drop  —  easiest, recommended')
        v1 = QVBoxLayout(g1)
        t1 = QLabel('No sign-up needed to start. You literally <b>drag the published folder</b> onto the '
                    'Netlify Drop page and your site is live in seconds, with a free web address like '
                    '<code>your-site.netlify.app</code>.<br><br>'
                    '<b>Steps:</b> 1) Click “Open Netlify Drop”.  2) Drag the folder (use “Open the folder” above) '
                    'onto the dotted box in the browser.  3) Wait a few seconds — it gives you your live link.')
        t1.setWordWrap(True); t1.setTextFormat(Qt.RichText); v1.addWidget(t1)
        h1 = QHBoxLayout()
        nb = QPushButton('Open Netlify Drop'); nb.setDefault(True)
        nb.clicked.connect(lambda: open_external('https://app.netlify.com/drop'))
        of = QPushButton('Open the folder to drag')
        of.clicked.connect(lambda: open_external(folder, is_file=True))
        h1.addWidget(nb); h1.addWidget(of); h1.addStretch(); v1.addLayout(h1)
        root.addWidget(g1)

        # --- GitHub Pages (for GitHub users) ---
        g2 = QGroupBox('2.  GitHub Pages  —  if you already use GitHub')
        v2 = QVBoxLayout(g2)
        t2 = QLabel('If you have a GitHub account, you can host the site free at '
                    '<code>yourname.github.io</code>. Create a new repository, upload these files, then turn on '
                    '“Pages” in the repository’s Settings. The button below opens the guide.')
        t2.setWordWrap(True); t2.setTextFormat(Qt.RichText); v2.addWidget(t2)
        h2 = QHBoxLayout()
        gb1 = QPushButton('New GitHub repository')
        gb1.clicked.connect(lambda: open_external('https://github.com/new'))
        gb2 = QPushButton('How to turn on Pages')
        gb2.clicked.connect(lambda: open_external('https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site'))
        h2.addWidget(gb1); h2.addWidget(gb2); h2.addStretch(); v2.addLayout(h2)
        root.addWidget(g2)

        # --- Cloudflare Pages (alternative) ---
        g3 = QGroupBox('3.  Cloudflare Pages  —  another free option')
        v3 = QVBoxLayout(g3)
        t3 = QLabel('Similar to Netlify. Free hosting at <code>your-site.pages.dev</code>; needs a free account.')
        t3.setWordWrap(True); t3.setTextFormat(Qt.RichText); v3.addWidget(t3)
        cb_ = QPushButton('Open Cloudflare Pages')
        cb_.clicked.connect(lambda: open_external('https://pages.cloudflare.com/'))
        hc = QHBoxLayout(); hc.addWidget(cb_); hc.addStretch(); v3.addLayout(hc)
        root.addWidget(g3)

        # --- Your own web address (domain) ---
        g4 = QGroupBox('Want your own name, like  www.your-name.co.uk ?')
        v4 = QVBoxLayout(g4)
        t4 = QLabel('The free addresses above work straight away. If you later want your <b>own</b> web address, '
                    'you <b>buy a domain name</b> (about £8–12 a year) from a registrar and point it at your host — '
                    'all three hosts above have a “custom domain” setting with instructions. You can always do this '
                    'later; your free address keeps working in the meantime.')
        t4.setWordWrap(True); t4.setTextFormat(Qt.RichText); v4.addWidget(t4)
        root.addWidget(g4)

        tip = QLabel('<i>Tip: whenever you change your site, just Publish again and re-upload (or re-drag) the '
                     'folder — your web address stays the same.</i>')
        tip.setWordWrap(True); tip.setTextFormat(Qt.RichText); tip.setStyleSheet('color:gray'); root.addWidget(tip)

        bb = QDialogButtonBox(QDialogButtonBox.Close); bb.rejected.connect(dlg.reject); bb.accepted.connect(dlg.accept)
        root.addWidget(bb)
        dlg.show(); dlg.raise_(); dlg.activateWindow()
        dlg.exec()

    # ------------------------------------------------------------ updates
    def update_repo(self):
        return (self.settings.value('updateRepo', '') or UPDATE_REPO).strip().strip('/')

    def update_url(self):
        repo, branch = self.update_repo(), (self.settings.value('updateBranch', '') or UPDATE_BRANCH)
        path = (self.settings.value('updatePath', '') or UPDATE_PATH).strip().strip('/')
        return f'https://raw.githubusercontent.com/{repo}/{branch}/{path}'

    def fetch_catalogue(self):
        """After an update, fetch serif-templates.json if it isn't here yet.

        Check for Updates replaces one file — this one. A machine that
        updated into a version which knows about the 89 templates would
        otherwise have the code and not the catalogue, and quietly offer
        three templates instead of ninety-two. It sits beside this file in
        the repository, so the URL is the update URL with the name swapped.
        """
        if os.path.exists(SERIF_CATALOGUE) or not self.update_repo():
            return
        from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
        if not hasattr(self, 'nam'): self.nam = QNetworkAccessManager(self)
        url = self.update_url().rsplit('/', 1)[0] + '/' + os.path.basename(SERIF_CATALOGUE)
        req = QNetworkRequest(QUrl(url)); req.setTransferTimeout(20000)
        reply = self.nam.get(req)

        def done():
            global _SERIF
            try:
                if reply.error() != QNetworkReply.NoError: return
                data = bytes(reply.readAll())
                json.loads(data)                     # don't write half a catalogue
                with open(SERIF_CATALOGUE, 'wb') as fh: fh.write(data)
                _SERIF = None
            except Exception:
                pass
            finally:
                reply.deleteLater()
        reply.finished.connect(done)

    def check_updates(self, quiet=True):
        if not self.update_repo():
            if not quiet: self.update_settings()
            return
        from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
        if not hasattr(self, 'nam'): self.nam = QNetworkAccessManager(self)
        req = QNetworkRequest(QUrl(self.update_url()))
        req.setAttribute(QNetworkRequest.CacheLoadControlAttribute, QNetworkRequest.AlwaysNetwork)
        req.setRawHeader(b'Cache-Control', b'no-cache'); req.setTransferTimeout(20000)
        reply = self.nam.get(req)
        if not quiet: self.hint('Checking for updates…')
        reply.finished.connect(lambda: self.update_checked(reply, quiet))

    def update_checked(self, reply, quiet):
        from PySide6.QtNetwork import QNetworkReply
        try:
            if reply.error() != QNetworkReply.NoError:
                if not quiet:
                    QMessageBox.warning(self, 'Check for Updates', f"Couldn't reach the update source:\n{self.update_url()}\n\n{reply.errorString()}\n\n"
                                        'Check the repository name in Help ▸ Update Settings, and that the repository is public.')
                return
            data = bytes(reply.readAll())
        finally:
            reply.deleteLater()
        m = re.search(rb'^VERSION = "([^"]+)"', data, re.M)
        if not m or APP.encode() not in data:
            if not quiet: QMessageBox.warning(self, 'Check for Updates', "The file in the repository isn't a copy of this app.")
            return
        latest = m.group(1).decode()
        vt = lambda v: tuple(int(x) for x in re.findall(r'\d+', v)[:4])
        if vt(latest) > vt(VERSION):
            self.update_source, self.update_version = data, latest
            self.a['update'].setText(f'Update to {latest}'); self.a['update'].setVisible(True)
            self.a['update'].setToolTip(f'Version {latest} is available (you have {VERSION}). Click to update.')
            self.hint(f'Version {latest} of {APP} is available. Click “Update to {latest}” in the toolbar.')
            if self.startup_dlg: self.startup_dlg.show_update(latest)
        else:
            self.a['update'].setVisible(False)
            if not quiet: QMessageBox.information(self, 'Check for Updates', f'You have the latest version ({VERSION}).')

    def install_update(self):
        data, ver = getattr(self, 'update_source', None), getattr(self, 'update_version', '')
        if not data: self.check_updates(quiet=False); return
        target = os.path.realpath(os.path.abspath(__file__))
        if QMessageBox.question(self, 'Update', f'Update {APP} from {VERSION} to {ver}?\n\nYour current version is kept as a backup.') != QMessageBox.Yes:
            return
        try:
            compile(data, 'webcreator.py', 'exec')
        except SyntaxError as ex:
            QMessageBox.warning(self, 'Update', f'The downloaded version is incomplete or damaged, so nothing was changed.\n{ex}'); return
        try:
            import shutil
            shutil.copy2(target, target + '.bak')
            tmp = target + '.new'
            with open(tmp, 'wb') as fh: fh.write(data)
            os.chmod(tmp, os.stat(target).st_mode)
            os.replace(tmp, target)
        except OSError as ex:
            QMessageBox.warning(self, 'Update', f"Couldn't replace {target}.\n{ex}"); return
        self.a['update'].setVisible(False); self.update_source = None
        self.fetch_catalogue()
        if QMessageBox.question(self, 'Update', f'Updated to {ver}. Restart now to use it?') == QMessageBox.Yes and self.maybe_save():
            self.dirty = False
            self.settings.setValue('geometry', self.saveGeometry()); self.settings.setValue('state', self.saveState(LAYOUT_VERSION))
            args = [a for a in sys.argv[1:]]
            if self.path and self.path not in args: args = [self.path]
            os.execv(sys.executable, [sys.executable, target] + args)
        else:
            self.hint(f'Updated to {ver}. The new version starts next time you open the app.')

    def update_settings(self):
        """The single Settings dialog (Help ▸ Settings). Merges what used to be a
        separate File ▸ Site Properties dialog: site design, contact details, AI
        image provider, image editor and the software-update source — all in one
        place, so there are no longer two overlapping 'settings' dialogs."""
        from PySide6.QtWidgets import QScrollArea
        s = self.site
        # --- Site design ---
        name = QLineEdit(s['name'])
        w = QSpinBox(); w.setRange(320, 4000); w.setValue(s['width']); w.setSuffix(' px')
        h = QSpinBox(); h.setRange(200, 30000); h.setValue(s['height']); h.setSuffix(' px')
        bgc = [s.get('bg', '#ffffff')]
        bgb = ColorButton(bgc[0], lambda c: (bgc.__setitem__(0, c), bgb.setIcon(swatch_icon(c, 18))), 'Browser background')
        pic = [s.get('bgimage')]
        picb = QPushButton(s.get('assetnames', {}).get(pic[0], 'Choose picture…') if pic[0] else 'Choose picture…')
        picm = QMenu(picb)
        def choose_pic():
            path, _ = QFileDialog.getOpenFileName(self, 'Background picture', os.path.expanduser('~/Pictures'), 'Pictures (*.png *.jpg *.jpeg *.gif *.webp)')
            uri = self.picture_uri(path) if path else None
            if uri:
                k = add_asset(s, uri); s.setdefault('assetnames', {})[k] = os.path.basename(path)
                pic[0] = k; picb.setText(os.path.basename(path))
        picm.addAction('Choose picture…', choose_pic)
        picm.addAction('No picture', lambda: (pic.__setitem__(0, None), picb.setText('Choose picture…')))
        picb.setMenu(picm)
        # --- Contact / author details ---
        c = s.get('contact', {})
        c_name = QLineEdit(c.get('name', '')); c_name.setPlaceholderText('Your name / the site author')
        c_email = QLineEdit(c.get('email', '')); c_email.setPlaceholderText('name@example.org')
        c_phone = QLineEdit(c.get('phone', ''))
        c_addr = QLineEdit(c.get('address', ''))
        c_web = QLineEdit(c.get('website', '')); c_web.setPlaceholderText('example.org')
        # --- AI image provider ---
        ai_prov = QComboBox()
        ai_prov.addItem('Pollinations (free, no account)', 'pollinations')
        ai_prov.addItem('OpenAI (DALL·E — needs API key)', 'openai')
        ai_prov.addItem('Stability (Stable Diffusion — needs API key)', 'stability')
        ai_prov.setCurrentIndex(max(0, ai_prov.findData(self.settings.value('aiProvider', 'pollinations'))))
        ai_key = QLineEdit(self.settings.value('aiOpenAIKey', '') or self.settings.value('aiStabilityKey', ''))
        ai_key.setEchoMode(QLineEdit.Password); ai_key.setPlaceholderText('Only needed for OpenAI / Stability')
        # --- Tools & software updates ---
        painter = QLineEdit(self.settings.value('imagePainterCmd', '') or 'IMAGEpainter'); painter.setPlaceholderText('IMAGEpainter')
        repo = QLineEdit(self.update_repo()); repo.setPlaceholderText('yourname/webcreator')
        branch = QLineEdit(self.settings.value('updateBranch', '') or UPDATE_BRANCH)
        path = QLineEdit(self.settings.value('updatePath', '') or UPDATE_PATH); path.setPlaceholderText('webcreator.py')
        auto = QCheckBox('Check for updates when the app starts'); auto.setChecked(self.settings.value('autoUpdate', True, type=bool))

        def section(txt, hint):
            lab = QLabel(hint); lab.setStyleSheet('color:gray'); return (f'— {txt} —', lab)
        rows = [section('Site', 'Name, size and background of this site'),
                ('Site name:', name), ('Page width:', w), ('Default page height:', h),
                ('Browser background:', bgb), ('Background picture:', picb),
                section('Contact details', 'Used by Insert ▸ Contact details'),
                ('Author / name:', c_name), ('Email:', c_email), ('Phone:', c_phone),
                ('Address:', c_addr), ('Website:', c_web),
                section('AI images', 'Used by Insert ▸ Picture ▸ Create with AI'),
                ('Image generator:', ai_prov), ('API key (if needed):', ai_key),
                section('Tools & updates', 'Image editor, and where app updates come from'),
                ('Image editor (IMAGEpainter button):', painter),
                ('GitHub repository:', repo), ('Branch:', branch), ('File in it:', path), ('', auto)]

        # The merged form is long, so make the dialog scrollable.
        dlg = QDialog(self); dlg.setWindowTitle('Settings'); dlg.resize(560, 660)
        outer = QVBoxLayout(dlg)
        area = QScrollArea(); area.setWidgetResizable(True); area.setFrameShape(QScrollArea.NoFrame)
        inner = QWidget(); form = QFormLayout(inner)
        for lbl, wdg in rows: form.addRow(lbl, wdg)
        area.setWidget(inner); outer.addWidget(area, 1)
        note = QLabel('The browser background (and picture, tiled) fills the window around your pages when '
                      f'published. App updates are read from the public repository above.\nNow: {self.update_url()}')
        note.setWordWrap(True); note.setStyleSheet('color:gray'); outer.addWidget(note)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept); bb.rejected.connect(dlg.reject); outer.addWidget(bb)
        if not dlg.exec(): return

        # --- Save: site design (incl. footer shift when the default height changes) ---
        self.commit()
        dh = h.value() - s['height']
        for m in s['masters']:
            for o in m['objects']:
                if o.get('anchor') == 'bottom': o['y'] += dh
        s.update(name=name.text().strip() or s['name'], width=w.value(), height=h.value(), bg=bgc[0], bgimage=pic[0])
        s['contact'] = {'name': c_name.text().strip(), 'email': c_email.text().strip(),
                        'phone': c_phone.text().strip(), 'address': c_addr.text().strip(),
                        'website': c_web.text().strip()}
        # --- Save: AI provider ---
        prov = ai_prov.currentData(); self.settings.setValue('aiProvider', prov)
        k = ai_key.text().strip()
        if prov == 'openai': self.settings.setValue('aiOpenAIKey', k)
        elif prov == 'stability': self.settings.setValue('aiStabilityKey', k)
        # --- Save: tools & updates ---
        self.settings.setValue('imagePainterCmd', painter.text().strip() or 'IMAGEpainter')
        self.settings.setValue('updateRepo', repo.text().strip()); self.settings.setValue('updateBranch', branch.text().strip() or UPDATE_BRANCH)
        self.settings.setValue('updatePath', path.text().strip() or UPDATE_PATH)
        self.settings.setValue('autoUpdate', auto.isChecked())
        self.dirty = True; self.update_title(); self.refresh()
        if repo.text().strip(): self.check_updates(quiet=False)

    def about(self):
        QMessageBox.about(self, f'About {APP}', f'<h3>{APP}</h3><p>Version {VERSION}</p>'
                          '<p>A desktop website designer. Lay out pages freely, share headers and footers on master pages, '
                          'preview in your browser and publish plain HTML to a folder.</p>'
                          f'<p>Built with Qt {QApplication.instance().applicationVersion() or ""} — it follows your desktop theme.</p>')

    # ------------------------------------------------------------ window
    def after_show(self):
        if self.settings.value('autoUpdate', True, type=bool) and self.update_repo():
            self.check_updates(quiet=True)
        self.view.fit_width(); self.view.verticalScrollBar().setValue(self.view.verticalScrollBar().minimum())
        self.view.centerOn(QPointF(self.site['width'] / 2, 300))
        args = [a for a in sys.argv[1:] if not a.startswith('-')]
        if args and os.path.exists(args[0]) and args[0].lower().endswith(WPP_EXT): self.load_webplus(args[0])
        elif args and os.path.exists(args[0]): self.load_path(args[0])
        elif self.settings.value('showStartup', True, type=bool) and '--no-startup' not in sys.argv:
            self.startup()

    def changeEvent(self, e):
        if e.type() == QEvent.PaletteChange:
            self.schedule_ui(); self.view.viewport().update()
        super().changeEvent(e)

    def closeEvent(self, e):
        if not self.maybe_save(): e.ignore(); return
        self.settings.setValue('geometry', self.saveGeometry()); self.settings.setValue('state', self.saveState(LAYOUT_VERSION))
        try:
            import shutil; shutil.rmtree(self.preview_dir, ignore_errors=True)
        except Exception: pass
        e.accept()


def main():
    QApplication.setDesktopFileName('webcreator')
    app = QApplication(sys.argv)
    app.setApplicationName('WEBcreator'); app.setApplicationDisplayName(APP); app.setOrganizationName(ORG)
    app.setApplicationVersion(VERSION)
    w = MainWindow(); w.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
