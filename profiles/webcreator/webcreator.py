#!/usr/bin/env python3
# just a... WEBcreator
# A desktop website designer for Linux, built on Qt 6 (PySide6).
# It follows your desktop theme: colours, accent, fonts and icons all come
# from the system (KDE Plasma colour scheme, Breeze/your icon theme, etc).

import sys, os, re, json, copy, uuid, base64, hashlib, math, tempfile, collections, html as H

try:
    from PySide6.QtCore import (Qt, QRectF, QPointF, QSizeF, QTimer, QSettings, QUrl,
                                QByteArray, QBuffer, QIODevice, QSize, QLineF, QEvent)
    from PySide6.QtGui import (QAction, QActionGroup, QIcon, QPixmap, QImage, QPainter, QColor,
                               QPen, QBrush, QFont, QFontMetrics, QPainterPath, QPalette, QTransform,
                               QTextDocument, QTextOption, QTextCursor, QTextCharFormat,
                               QTextBlockFormat, QAbstractTextDocumentLayout, QKeySequence,
                               QDesktopServices, QPolygonF, QCursor)
    from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QGraphicsView, QGraphicsScene,
                                   QGraphicsItem, QGraphicsTextItem, QToolBar, QDockWidget,
                                   QLabel, QComboBox, QFontComboBox, QSpinBox, QDoubleSpinBox,
                                   QToolButton, QPushButton, QVBoxLayout, QHBoxLayout, QGridLayout,
                                   QFormLayout, QDialog, QDialogButtonBox, QLineEdit, QCheckBox,
                                   QRadioButton, QButtonGroup, QListWidget, QListWidgetItem,
                                   QTreeWidget, QTreeWidgetItem, QTreeWidgetItemIterator,
                                   QStackedWidget, QFileDialog,
                                   QMessageBox, QColorDialog, QSlider, QPlainTextEdit,
                                   QTableWidget, QTableWidgetItem, QMenu, QFrame, QSizePolicy,
                                   QGroupBox, QAbstractItemView, QStyle)
except ImportError:
    print("just a... WEBcreator needs PySide6.\nOn CachyOS / Arch:  sudo pacman -S --needed pyside6")
    sys.exit(1)

APP = "just a... WEBcreator"
ORG = "justawebcreator"
EXT = ".webc"
VERSION = "1.7"

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
        items = nav_items(site, o); padx, gap = 14, 6
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
.obj-nav a{display:block;text-decoration:none;color:inherit;padding:8px 14px;white-space:nowrap;text-align:center;line-height:1.2}
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
    words = re.sub(r'\s+', ' ', H.unescape(re.sub(r'<[^>]+>', ' ', ' '.join(o.get('html', '') for o in page['objects'] if o['type'] == 'text')))).strip()
    if len(words) > 155: words = words[:152].rsplit(' ', 1)[0] + '…'
    desc = f'<meta name="description" content="{esc(words)}">\n' if words else ''
    bgpic = f' url({img(site["bgimage"])}) top left repeat' if site.get('bgimage') in site.get('assets', {}) else ''
    css = (f'body{{background:{site.get("bg") or bg}{bgpic}}}\n.pf-page{{width:{site["width"]}px;height:{Hh}px;background:{bg}}}\n'
           + '\n'.join(rules))
    return (f'<!doctype html>\n<html lang="en-GB">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width={site["width"]}">\n'
            f'<title>{esc(page["title"])} | {esc(site["name"])}</title>\n{desc}<meta name="generator" content="{APP} {VERSION}">\n'
            f'{flink}<link rel="stylesheet" href="style.css">\n<style>\n{css}\n</style>\n</head>\n<body>\n'
            f'<div class="pf-page">\n{body}\n</div>\n</body>\n</html>\n')

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
        with open(os.path.join(folder, name), 'wb') as fh: fh.write(base64.b64decode(src.split(',', 1)[1]))
        written.append(name); imgs[key] = name; return name
    with open(os.path.join(folder, 'style.css'), 'w') as fh: fh.write(PUBLISH_CSS)
    written.append('style.css')
    for p in site['pages']:
        with open(os.path.join(folder, p['file']), 'w', encoding='utf-8') as fh: fh.write(page_html(site, p, img))
        written.append(p['file'])
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
        raise RuntimeError('Importing needs Beautiful Soup.\nInstall it with:  sudo pacman -S --needed python-beautifulsoup4')
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
        z = (self.viewport().width() - 60) / self.win.site['width']
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

    def snap(self, v):
        return round(v / 10) * 10 if self.win.snap_grid else round(v)

    # -- mouse
    def mousePressEvent(self, e):
        win = self.win; vpos = e.position().toPoint(); sp = self.mapToScene(vpos)
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
        if allow_none:
            m = QMenu(self)
            m.addAction(swatch_icon('', 16), 'None', lambda: self.on_pick(''))
            m.addAction('Choose colour…', self.pick)
            self.setMenu(m); self.setPopupMode(QToolButton.MenuButtonPopup)
        self.clicked.connect(self.pick)

    def pick(self):
        c = QColorDialog.getColor(QColor(self.color or '#ffffff'), self.window(), self.title)
        if c.isValid(): self.on_pick(c.name())


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
        self.nwidth = QComboBox(); self.nwidth.addItems(['960', '1000', '1200']); self.nwidth.setEditable(True); nl.addRow('Page width (px):', self.nwidth)
        self.nheight = QSpinBox(); self.nheight.setRange(200, 20000); self.nheight.setValue(1100); nl.addRow('Page height (px):', self.nheight)
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
        b1 = QPushButton('Open Selected'); b1.clicked.connect(lambda: self.open_recent(self.rlist.currentItem())); bh.addWidget(b1)
        b2 = QPushButton(ticon(['document-open-folder', 'folder-open'], ''), 'Browse…'); b2.clicked.connect(self.browse); bh.addWidget(b2)
        b3 = QPushButton(ticon(['document-import'], ''), 'Import Website Folder…'); b3.clicked.connect(self.import_site); bh.addWidget(b3)
        b4 = QPushButton(ticon(['document-open', 'document-import'], ''), 'Open WebPlus Site…')
        b4.setToolTip('Open a WebPlus .wpp publication as an editable site'); b4.clicked.connect(self.open_wpp)
        bh.addWidget(b4); bh.addStretch()
        self.stack.addWidget(op)

        bottom = QHBoxLayout(); root.addLayout(bottom)
        self.show_cb = QCheckBox('Show the Startup Assistant when the app opens')
        self.show_cb.setChecked(win.settings.value('showStartup', True, type=bool)); bottom.addWidget(self.show_cb); bottom.addStretch()
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
        self.result_site = tpl_blank(self.nname.text().strip() or 'My Site', w, self.nheight.value()); self.accept()

    def open_recent(self, it):
        if it and it.data(Qt.UserRole): self.result_path = it.data(Qt.UserRole); self.accept()

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
        self.refresh()
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
        self.setCentralWidget(w)
        self.view.setFocus()

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
            siteprops=A('Site &Properties…', self.site_props, None, 'document-properties'),
            checklinks=A('Check &Links…', self.check_links, None, ['tools-check-spelling', 'insert-link', 'link']),
            prevpage=A('Preview &Page in Browser', self.preview_page, 'F12', ['document-preview', 'view-preview']),
            prevsite=A('Preview &Site in Browser', self.preview_site, 'Shift+F12', ['internet-web-browser', 'applications-internet']),
            publish=A('Publish to &Disk…', self.publish_disk, None, ['document-export', 'folder-publicshare']),
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
            link=A('&Hyperlink…', self.hyperlink_dialog, 'Ctrl+K', ['insert-link', 'link']),
            pageprops=A('Page P&roperties…', lambda: self.page_props(self.page()), None, 'document-properties'),
            bold=A('&Bold', lambda: self.text_style('bold'), QKeySequence.Bold, 'format-text-bold', True),
            italic=A('&Italic', lambda: self.text_style('italic'), QKeySequence.Italic, 'format-text-italic', True),
            underline=A('&Underline', lambda: self.text_style('underline'), QKeySequence.Underline, 'format-text-underline', True),
            aleft=A('Align &Left', lambda: self.set_prop('align', 'left'), None, 'format-justify-left'),
            acenter=A('Align &Centre', lambda: self.set_prop('align', 'center'), None, 'format-justify-center'),
            aright=A('Align &Right', lambda: self.set_prop('align', 'right'), None, 'format-justify-right'),
            ajust=A('&Justify', lambda: self.set_prop('align', 'justify'), None, 'format-justify-fill'),
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
        menu('&File', [a['new'], a['open'], self.recent_menu_action(), a['openwpp'], a['import'], None, a['save'], a['saveas'], None, a['siteprops'], a['checklinks'], None,
                       a['prevpage'], a['prevsite'], a['publish'], None, a['quit']])
        menu('&Edit', [a['undo'], a['redo'], None, a['cut'], a['copy'], a['paste'], a['dup'], a['delete'], None, a['selall']])
        self.view_menu = menu('&View', [a['rulers'], a['grid'], a['snap'], None, a['zin'], a['zout'], a['z100'], a['zfit'], None])
        ins = []
        for tid, label, *_ in [t for t in TOOLS if t[0] and t[0] not in ('pointer', 'hand', 'zoom')]:
            ins.append(self.act(label, lambda _=False, t=tid: self.insert_default(t), None, None))
        menu('&Insert', [a['newpage'], None] + ins + [None, a['link']])
        menu('F&ormat', [a['bold'], a['italic'], a['underline'], None, a['aleft'], a['acenter'], a['aright'], a['ajust'], None, a['pageprops']])
        al = [self.act(n, lambda _=False, k=k: self.align(k), None, ic) for k, n, ic in (
            ('left', 'Align Left Edges', 'align-horizontal-left'), ('hcenter', 'Align Centres Horizontally', 'align-horizontal-center'),
            ('right', 'Align Right Edges', 'align-horizontal-right'), ('top', 'Align Top Edges', 'align-vertical-top'),
            ('vcenter', 'Align Middles Vertically', 'align-vertical-center'), ('bottom', 'Align Bottom Edges', 'align-vertical-bottom'),
            ('page', 'Centre on Page Horizontally', 'align-horizontal-center'))]
        self.a['lock'] = self.act('&Lock / Unlock', self.toggle_lock, 'Ctrl+L', ['object-locked', 'lock'])
        self.a['tomaster'] = self.act('Move Repeated Objects to &Master Page…', self.move_common_to_master, None, ['document-multiple', 'edit-copy'])
        menu('&Arrange', [a['front'], a['fwd'], a['back1'], a['back'], None, ('Align', al), None, self.a['lock'], None, self.a['tomaster']])
        self.a['update'] = self.act('Update Available', self.install_update, None, ['system-software-update', 'update-none', 'download'])
        self.a['update'].setVisible(False)
        self.a['checkupdate'] = self.act('Check for &Updates…', lambda: self.check_updates(quiet=False), None, ['system-software-update', 'view-refresh'])
        self.a['updatesettings'] = self.act('Update &Settings…', self.update_settings, None, ['configure', 'preferences-system'])
        menu('&Help', [self.a['update'], self.a['checkupdate'], self.a['updatesettings'], None, a['about']])

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
        tb = QToolBar('Standard'); tb.setObjectName('standard'); tb.setIconSize(QSize(20, 20))
        for k in ('new', 'open', 'save', None, 'undo', 'redo', None, 'cut', 'copy', 'paste', None, 'prevsite', 'publish', None, 'update'):
            tb.addAction(self.a[k]) if k else tb.addSeparator()
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
        self.addToolBarBreak()
        # Context toolbar
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
        for t in (tb, self.ctx, tt): self.view_menu.addAction(t.toggleViewAction())

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

    def build_studio(self):
        # Site
        sw = QWidget(); sl = QVBoxLayout(sw); sl.setContentsMargins(4, 4, 4, 4)
        self.site_name_label = QLabel(); sl.addWidget(self.site_name_label)
        self.tree = QTreeWidget(); self.tree.setHeaderHidden(True); self.tree.setColumnCount(1); self.tree.setIndentation(16)
        self.tree.itemClicked.connect(lambda it, _: self.goto_page(it.data(0, Qt.UserRole)))
        self.tree.itemDoubleClicked.connect(lambda it, _: self.page_props(self.page_by_id(it.data(0, Qt.UserRole))))
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
        sl.addWidget(self.mlist, 1)
        mtb = QToolBar(); mtb.setIconSize(QSize(16, 16))
        mtb.addAction(self.act('New master page', self.new_master, None, 'document-new'))
        mtb.addAction(self.act('Edit master page', lambda: self.mlist.currentItem() and self.goto_master(self.mlist.currentItem().data(Qt.UserRole)), None, 'document-edit'))
        mtb.addAction(self.act('Master properties', self.master_props, None, 'document-properties'))
        mtb.addAction(self.act('Delete master page', self.delete_master, None, 'edit-delete'))
        sl.addWidget(mtb)
        self.d_site = self.dock('Site', sw, 'site')

        # Swatches
        cw = QWidget(); cl = QVBoxLayout(cw); cl.setContentsMargins(6, 6, 6, 6)
        mrow = QHBoxLayout(); self.sw_group = QButtonGroup(self)
        for i, (k, lbl) in enumerate((('fill', 'Fill'), ('line', 'Line'), ('text', 'Text'))):
            b = QToolButton(); b.setText(lbl); b.setCheckable(True); b.setChecked(k == 'fill'); b.setToolButtonStyle(Qt.ToolButtonTextOnly)
            self.sw_group.addButton(b, i); mrow.addWidget(b)
        self.sw_group.idClicked.connect(lambda i: setattr(self, 'sw_mode', ('fill', 'line', 'text')[i]))
        mrow.addStretch(); cl.addLayout(mrow)
        cl.addWidget(QLabel('Site palette')); self.pal_grid = QGridLayout(); self.pal_grid.setSpacing(3); cl.addLayout(self.pal_grid)
        cl.addWidget(QLabel('Standard')); sg = QGridLayout(); sg.setSpacing(3); cl.addLayout(sg)
        none_b = QToolButton(); none_b.setIcon(swatch_icon('', 20)); none_b.setToolTip('None'); none_b.setAutoRaise(True)
        none_b.clicked.connect(lambda: self.apply_swatch('')); sg.addWidget(none_b, 0, 0)
        for i, c in enumerate(STANDARD, 1):
            b = QToolButton(); b.setIcon(swatch_icon(c, 20)); b.setToolTip(c); b.setAutoRaise(True)
            b.clicked.connect(lambda _=False, c=c: self.apply_swatch(c)); sg.addWidget(b, i // 7, i % 7)
        cb = QPushButton('Custom colour…'); cb.clicked.connect(self.custom_swatch); cl.addWidget(cb)
        ab = QPushButton('Add selected colour to site palette'); ab.clicked.connect(self.add_to_palette); cl.addWidget(ab)
        cl.addStretch()
        self.d_swatch = self.dock('Swatches', cw, 'swatches')

        # Line
        lw = QWidget(); lf = QFormLayout(lw)
        self.ln_w = QDoubleSpinBox(); self.ln_w.setRange(0, 60); self.ln_w.setSuffix(' px'); self.ln_w.setDecimals(1)
        self.ln_w.valueChanged.connect(lambda v: self.studio_set('strokeW', v))
        self.ln_style = QComboBox(); self.ln_style.addItems(['solid', 'dashed', 'dotted'])
        self.ln_style.currentTextChanged.connect(lambda v: self.studio_set('dash', v))
        self.ln_rad = QSpinBox(); self.ln_rad.setRange(0, 400); self.ln_rad.setSuffix(' px')
        self.ln_rad.valueChanged.connect(lambda v: self.studio_set('radius', v))
        lf.addRow('Width:', self.ln_w); lf.addRow('Style:', self.ln_style); lf.addRow('Corner radius:', self.ln_rad)
        self.d_line = self.dock('Line', lw, 'line')

        # Transparency
        tw = QWidget(); tl = QFormLayout(tw)
        self.op_slider = QSlider(Qt.Horizontal); self.op_slider.setRange(0, 100)
        self.op_spin = QSpinBox(); self.op_spin.setRange(0, 100); self.op_spin.setSuffix(' %')
        self.op_slider.valueChanged.connect(self.op_spin.setValue)
        self.op_spin.valueChanged.connect(self.op_slider.setValue)
        self.op_spin.valueChanged.connect(lambda v: self.studio_set('opacity', 1 - v / 100))
        tl.addRow('Transparency:', self.op_slider); tl.addRow('', self.op_spin)
        self.d_trans = self.dock('Transparency', tw, 'transparency')

        # Transform
        xw = QWidget(); xf = QFormLayout(xw); self.tf = {}
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
        yl.addWidget(self.layers)
        ytb = QToolBar(); ytb.setIconSize(QSize(16, 16))
        ytb.addAction(self.act('Show / hide', self.toggle_hidden, None, ['view-visible', 'visibility']))
        ytb.addAction(self.a['lock'])
        ytb.addAction(self.a['fwd']); ytb.addAction(self.a['back1'])
        yl.addWidget(ytb)
        self.d_layers = self.dock('Layers', yw, 'layers')

        self.tabifyDockWidget(self.d_site, self.d_swatch); self.tabifyDockWidget(self.d_swatch, self.d_line)
        self.tabifyDockWidget(self.d_line, self.d_trans); self.tabifyDockWidget(self.d_trans, self.d_xform)
        self.tabifyDockWidget(self.d_xform, self.d_layers)
        self.d_site.raise_()
        self.view_menu.addSeparator()
        sm = self.view_menu.addMenu('Studio')
        for d in (self.d_site, self.d_swatch, self.d_line, self.d_trans, self.d_xform, self.d_layers):
            sm.addAction(d.toggleViewAction())
        self.resizeDocks([self.d_site], [300], Qt.Horizontal)

    def restore_layout(self):
        g = self.settings.value('geometry'); s = self.settings.value('state')
        if g: self.restoreGeometry(g)
        if s: self.restoreState(s)
        self.toggle_rulers()

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
        self.update_title(); self.build_ctx(); self.refresh_site_tab(); self.refresh_palette(); self.refresh_props(); self.refresh_layers()
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
            b = QToolButton(); b.setIcon(swatch_icon(c, 20)); b.setToolTip(c); b.setAutoRaise(True)
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
        elif t == 'nav': self.hint('The navigation bar lists your pages. Change pages in the Site tab; change its look on the context toolbar.')

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
        for o in objs: o[key] = val
        self.refresh()

    def set_prop(self, key, val):
        if self.editor: self.finish_edit()
        objs = self.sel_objs()
        if not objs: return
        self.commit()
        for o in objs:
            if o.get('locked'): continue
            o[key] = val
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
        key = {'fill': 'fill', 'line': 'stroke', 'text': 'color'}[self.sw_mode]
        self.commit()
        for o in objs:
            if o.get('locked'): continue
            if key == 'fill' and o['type'] == 'nav' and o.get('style') != 'plain' and c: o['accent'] = c
            elif key == 'fill' and o['type'] == 'form': o['accent'] = c or o['accent']
            elif key == 'stroke' and c and o['type'] != 'line' and not o.get('strokeW'): o['stroke'] = c; o['strokeW'] = 2
            elif key == 'color' and not c: continue
            else: o[key] = c
        self.refresh()

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
        self.commit(); o['src'] = add_asset(self.site, uri)
        pm = pixmap_for(self.site, o['src'])
        if pm and not pm.isNull() and o['w'] == DEF['picture']['w'] and o['h'] == DEF['picture']['h']:
            o['h'] = round(o['w'] * pm.height() / pm.width())
        self.refresh()

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
            tb.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(url.text().strip()))); form.addWidget(tb, 2, 2)
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
        elif t == 'url': QDesktopServices.openUrl(QUrl(v))
        elif t == 'email': QDesktopServices.openUrl(QUrl('mailto:' + v))
        elif t == 'file' and v in self.site.get('assets', {}):
            name = re.sub(r'[^A-Za-z0-9._-]+', '-', self.site.get('assetnames', {}).get(v, v))
            path = os.path.join(self.preview_dir, name)
            with open(path, 'wb') as fh: fh.write(base64.b64decode(self.site['assets'][v].split(',', 1)[1]))
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

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
        name = QLineEdit(self.site['name'])
        w = QSpinBox(); w.setRange(320, 4000); w.setValue(self.site['width']); w.setSuffix(' px')
        h = QSpinBox(); h.setRange(200, 30000); h.setValue(self.site['height']); h.setSuffix(' px')
        bgc = [self.site.get('bg', '#ffffff')]
        bgb = ColorButton(bgc[0], lambda c: (bgc.__setitem__(0, c), bgb.setIcon(swatch_icon(c, 18))), 'Browser background')
        pic = [self.site.get('bgimage')]
        picb = QPushButton(self.site.get('assetnames', {}).get(pic[0], 'Choose picture…') if pic[0] else 'Choose picture…')
        picm = QMenu(picb)
        def choose_pic():
            path, _ = QFileDialog.getOpenFileName(self, 'Background picture', os.path.expanduser('~/Pictures'), 'Pictures (*.png *.jpg *.jpeg *.gif *.webp)')
            uri = self.picture_uri(path) if path else None
            if uri:
                k = add_asset(self.site, uri); self.site.setdefault('assetnames', {})[k] = os.path.basename(path)
                pic[0] = k; picb.setText(os.path.basename(path))
        picm.addAction('Choose picture…', choose_pic); picm.addAction('No picture', lambda: (pic.__setitem__(0, None), picb.setText('Choose picture…')))
        picb.setMenu(picm)
        dlg = form_dialog(self, 'Site Properties', [('Site name:', name), ('Page width:', w), ('Default page height:', h),
                                                     ('Browser background:', bgb), ('Background picture:', picb)],
                          QLabel('The browser background (and picture, tiled) fills the window around your pages when published.'))
        if not dlg.exec(): return
        self.commit()
        dh = h.value() - self.site['height']
        for m in self.site['masters']:
            for o in m['objects']:
                if o.get('anchor') == 'bottom': o['y'] += dh
        self.site.update(name=name.text().strip() or self.site['name'], width=w.value(), height=h.value(), bg=bgc[0], bgimage=pic[0])
        self.refresh()

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
        for layer in [p['objects'] for p in site['pages']] + [m['objects'] for m in site['masters']]:
            for i, o in enumerate(layer):
                if o['type'] == 'html' and 'class="share"' in o.get('code', '') and 'data-net' in o.get('code', ''):
                    nets = [{'fb': 'facebook', 'li': 'linkedin', 'mail': 'email'}.get(n, n) for n in re.findall(r'data-net="(\w+)"', o['code'])]
                    n = mk('share', o['x'], o['y'], o['w'], o['h'], nets=[x for x in nets if x in NET]); n['id'] = o['id']
                    for k in ('anchor', 'locked', 'hidden'):
                        if o.get(k): n[k] = o[k]
                    layer[i] = n
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
        except OSError as ex:
            QMessageBox.warning(self, APP, f"Couldn't build the preview.\n{ex}"); return
        QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.join(self.preview_dir, file)))
        self.hint('Preview opened in your web browser.')

    def publish_disk(self):
        if self.editor: self.finish_edit()
        last = self.settings.value('publishDir', os.path.expanduser('~/Public'))
        folder = QFileDialog.getExistingDirectory(self, 'Publish to Disk — choose a folder', last)
        if not folder: return
        clash = [p['file'] for p in self.site['pages'] if os.path.exists(os.path.join(folder, p['file']))]
        if clash and QMessageBox.question(self, 'Publish to Disk', f'{len(clash)} file(s) in this folder will be replaced, including {clash[0]}. Continue?') != QMessageBox.Yes:
            return
        try: files = publish_site(self.site, folder)
        except OSError as ex: QMessageBox.warning(self, APP, f"Publishing failed.\n{ex}"); return
        self.settings.setValue('publishDir', folder)
        mb = QMessageBox(self); mb.setWindowTitle('Publish to Disk'); mb.setIcon(QMessageBox.Information)
        mb.setText(f'Published {len(self.site["pages"])} pages ({len(files)} files) to\n{folder}')
        mb.setInformativeText('Upload the contents of this folder to your web host to put the site online.')
        ob = mb.addButton('Open Folder', QMessageBox.ActionRole); vb = mb.addButton('View Site', QMessageBox.ActionRole); mb.addButton(QMessageBox.Close)
        mb.exec()
        if mb.clickedButton() is ob: QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
        elif mb.clickedButton() is vb: QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.join(folder, self.site['pages'][0]['file'])))

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
            self.settings.setValue('geometry', self.saveGeometry()); self.settings.setValue('state', self.saveState())
            args = [a for a in sys.argv[1:]]
            if self.path and self.path not in args: args = [self.path]
            os.execv(sys.executable, [sys.executable, target] + args)
        else:
            self.hint(f'Updated to {ver}. The new version starts next time you open the app.')

    def update_settings(self):
        repo = QLineEdit(self.update_repo()); repo.setPlaceholderText('yourname/webcreator')
        branch = QLineEdit(self.settings.value('updateBranch', '') or UPDATE_BRANCH)
        path = QLineEdit(self.settings.value('updatePath', '') or UPDATE_PATH); path.setPlaceholderText('webcreator.py')
        auto = QCheckBox('Check for updates when the app starts'); auto.setChecked(self.settings.value('autoUpdate', True, type=bool))
        dlg = form_dialog(self, 'Update Settings',
                          [('GitHub repository:', repo), ('Branch:', branch), ('File in it:', path), ('', auto)],
                          QLabel('Updates are read from that file in that repository, which must be public.\n'
                                 f'Now: {self.update_url()}'))
        if not dlg.exec(): return
        self.settings.setValue('updateRepo', repo.text().strip()); self.settings.setValue('updateBranch', branch.text().strip() or UPDATE_BRANCH)
        self.settings.setValue('updatePath', path.text().strip() or UPDATE_PATH)
        self.settings.setValue('autoUpdate', auto.isChecked())
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
        self.settings.setValue('geometry', self.saveGeometry()); self.settings.setValue('state', self.saveState())
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
