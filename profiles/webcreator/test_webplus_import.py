"""Tests for File ▸ Open WebPlus Site…

    cd ~/.local/share/webcreator && python3 -m unittest -v test_webplus_import

Every test here is about Jan's own publications rather than a fixture: the
point of this feature is that *his* 208-page Woldingham Panto site opens and
can be edited, and a synthetic .wpp would not have caught the three things
these tests do catch -- an iframe whose target is on its link rather than on
its URL, a site tree five levels deep, and a background image wider than its
page.

A publication that is not on this machine is skipped rather than failed, so
the file still runs on a machine without the archive beside it. ``unittest``
and not pytest, because that is what Serif-for-Linux's own suite uses and it
needs nothing installed.
"""

import json
import os
import sys
import tempfile
import unittest
from collections import Counter

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication                            # noqa: E402

APP = QApplication.instance() or QApplication([])

import webcreator as W                                                # noqa: E402

ARCHIVE = os.path.expanduser('~/Documents/Development/serif-archive/documents/webwriter')
PANTO = os.path.join(ARCHIVE, 'panto/panto.wpp')
LADYSTELLA = os.path.join(ARCHIVE, 'ladystella/ladystella2020.wpp')
ITLTD = os.path.join(ARCHIVE, 'idea-technology/IT-Ltd2.wpp')
BEFOREAFTER = os.path.join(ARCHIVE, 'beforeandafter/beforeandafter-2021.wpp')
DESIGNS = os.path.join(ARCHIVE, 'serif-design-gallery/My Designs.wpp')

ROOT = W.wpp_reader_root()
_CACHE = {}


def opened(path):
    """One publication, imported once however many tests ask for it."""
    if ROOT is None:
        raise unittest.SkipTest('no Serif-for-Linux checkout on this machine')
    if not os.path.exists(path):
        raise unittest.SkipTest(f'{os.path.basename(path)} is not on this machine')
    if path not in _CACHE:
        _CACHE[path] = W.import_webplus_file(path, ROOT)
    return _CACHE[path]


def read(path):
    """The same publication through the reader, to compare the import against."""
    if ROOT is None:
        raise unittest.SkipTest('no Serif-for-Linux checkout on this machine')
    if not os.path.exists(path):
        raise unittest.SkipTest(f'{os.path.basename(path)} is not on this machine')
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from serif import webplus
    return webplus.read(path)


def saveable(site):
    return {k: v for k, v in site.items() if not k.startswith('_')}


class TheReader(unittest.TestCase):
    def test_it_is_found_without_being_told_where(self):
        if ROOT is None:
            self.skipTest('no Serif-for-Linux checkout on this machine')
        self.assertTrue(os.path.isfile(os.path.join(ROOT, 'serif', 'webplus.py')))

    def test_a_folder_the_user_chose_is_not_quietly_swapped_for_another(self):
        """When Jan points at a folder, a different checkout must not answer."""
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(W.wpp_reader_root(tmp, only_hint=True))

    def test_a_stale_saved_folder_still_falls_back(self):
        if ROOT is None:
            self.skipTest('no Serif-for-Linux checkout on this machine')
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(W.wpp_reader_root(tmp), ROOT)


class TheSiteThatComesOut(unittest.TestCase):
    def test_panto_opens_as_every_page_it_has(self):
        site = opened(PANTO)
        self.assertEqual(len(site['pages']), 208)
        self.assertEqual(site['pages'][0]['title'], 'Home')

    def test_every_page_points_at_a_master_that_exists(self):
        for site in (opened(PANTO), opened(LADYSTELLA)):
            ids = {m['id'] for m in site['masters']}
            for p in site['pages']:
                self.assertIn(p['master'], ids)

    def test_no_link_points_at_a_page_that_is_not_there(self):
        for site in (opened(PANTO), opened(LADYSTELLA)):
            ids = {p['id'] for p in site['pages']}
            objects = [o for p in site['pages'] for o in p['objects']]
            objects += [o for m in site['masters'] for o in m['objects']]
            for o in objects:
                if o.get('link') and o['link']['type'] == 'page':
                    self.assertIn(o['link']['target'], ids)
                for pid in o.get('pages') or []:
                    self.assertIn(pid, ids)

    def test_every_page_has_its_own_file_name(self):
        files = [p['file'] for p in opened(PANTO)['pages']]
        self.assertEqual(len(set(files)), len(files))

    def test_it_survives_being_saved_and_read_back(self):
        site = saveable(opened(PANTO))
        back = json.loads(json.dumps({'app': W.APP, 'site': site}))['site']
        self.assertEqual(len(back['pages']), len(site['pages']))
        self.assertTrue(back['masters'] and back['assets'])


class NothingIsDropped(unittest.TestCase):
    """Every object the reader finds on a page has to arrive on that page."""

    def one(self, path):
        wp = read(path)
        site = opened(path)

        def leaves(objects):
            n = 0
            for o in objects:
                if o.kind == 'group':
                    n += leaves(o.children)                  # groups are flattened
                elif o.kind in ('input', 'search', 'search-results'):
                    pass                                     # folded in, or reported
                else:
                    n += 1
            return n

        want = Counter()
        for sp in wp.pages:
            if sp.page is None:
                continue
            want[sum(leaves(l.objects) for l in sp.page.layers
                     if not l.is_master and l.visible)] += 1
        # Compared as a histogram and not page by page because Woldingham Panto
        # has four pairs of pages with the same name, which a comparison keyed
        # on the name silently collapsed while this was being written.
        got = Counter(len([o for o in p['objects'] if not o.get('locked')])
                      for p in site['pages'])
        self.assertEqual(want, got)

    def test_panto(self):
        self.one(PANTO)

    def test_ladystella(self):
        self.one(LADYSTELLA)

    def test_it_ltd(self):
        self.one(ITLTD)

    def test_before_and_after(self):
        self.one(BEFOREAFTER)

    def test_a_master_is_filled_once_not_once_per_page(self):
        """A master's objects are inherited into every page that uses it.

        125 of Woldingham Panto's pages use Master A, so an import that copies
        them onto each page puts those seven objects on the canvas 125 times.
        """
        wp, site = read(PANTO), opened(PANTO)
        master_a = next(m for m in site['masters'] if m['name'] == 'Master A')
        first = next(sp for sp in wp.pages if sp.master and sp.master.letter == 'A')
        expected = sum(len(l.objects) for l in first.page.layers
                       if l.is_master and l.visible)
        self.assertEqual(len(master_a['objects']), expected)
        self.assertEqual(sum(1 for p in site['pages'] if p['master'] == master_a['id']), 125)


class TheThingsThatWereWrongFirstTime(unittest.TestCase):
    def test_the_site_structure_tree_keeps_its_real_depth(self):
        self.assertEqual(max(p.get('level', 0) for p in opened(PANTO)['pages']), 4)
        self.assertEqual(max(p.get('level', 0) for p in opened(LADYSTELLA)['pages']), 3)

    def test_the_site_tab_draws_the_tree_to_that_depth(self):
        site = opened(PANTO)
        win = W.MainWindow()
        try:
            win.set_site(json.loads(json.dumps(saveable(site))))
            win.update_ui()
            tops = [win.tree.topLevelItem(i) for i in range(win.tree.topLevelItemCount())]

            def deepest(item, d=0):
                return max([deepest(item.child(i), d + 1)
                            for i in range(item.childCount())] or [d])

            self.assertEqual(len(tops), sum(1 for p in site['pages'] if not p.get('level')))
            self.assertEqual(max(deepest(t) for t in tops), 4)
        finally:
            win.close()

    def test_an_iframe_finds_its_target_on_its_link_not_its_url(self):
        """57 of Woldingham Panto's iframes point at another page of the site.

        WebPlus puts that target on the object's *link*; ``external_url`` is
        empty for every one of them, so keying off the URL dropped all 57.
        """
        site = opened(PANTO)
        files = {p['file'] for p in site['pages']}
        frames = [o for p in site['pages'] for o in p['objects']
                  if o['type'] == 'html' and '<iframe' in o.get('code', '')]
        self.assertGreaterEqual(len(frames), 50)
        internal = [o for o in frames if any(f'src="{f}"' in o['code'] for f in files)]
        self.assertGreaterEqual(len(internal), 50)

    def test_a_background_image_is_placed_the_way_css_places_it(self):
        """Centred horizontally, clipped by the page, never squashed into it."""
        site = opened(LADYSTELLA)
        page = next(p for p in site['pages'] if any(o.get('locked') for o in p['objects']))
        bg = next(o for o in page['objects'] if o.get('locked'))
        self.assertGreater(bg['w'], site['width'])                   # wider than the page
        self.assertAlmostEqual(bg['x'], (site['width'] - bg['w']) / 2, delta=1)
        self.assertEqual(bg['fit'], 'stretch')                       # its own pixels
        self.assertIs(page['objects'][0], bg)                        # behind everything

    def test_a_hotspot_keeps_its_click(self):
        """IT-Ltd2 has five hotspots: invisible shapes that are only a link."""
        site = opened(ITLTD)
        spots = [o for p in site['pages'] for o in p['objects']
                 if o['type'] == 'shape' and not o['fill'] and not o['strokeW'] and o.get('link')]
        self.assertGreaterEqual(len(spots), 5)

    def test_a_rotated_object_keeps_its_angle(self):
        """WebPlus's 2x2 matrix is about the box's centre, like CSS and Qt.

        Counted against the reader rather than against a number typed here:
        the 125 rotated objects the reader reports are one master object
        inherited by 125 pages, plus eleven on pages of their own.
        """
        import math
        wp, site = read(PANTO), opened(PANTO)

        def leaves(objects):
            for o in objects:
                if o.kind == 'group':
                    yield from leaves(o.children)
                else:
                    yield o

        def turned(objects):
            return sum(1 for o in leaves(objects)
                       if abs(math.degrees(math.atan2(o.transform[1], o.transform[0]))) > 1)

        want = sum(turned(l.objects) for sp in wp.pages if sp.page
                   for l in sp.page.layers if not l.is_master and l.visible)
        got = sum(1 for p in site['pages'] for o in p['objects'] if abs(o.get('rot', 0)) > 1)
        self.assertEqual(want, got)
        self.assertEqual(got, 11)


class WhatItSaysItDid(unittest.TestCase):
    def test_the_summary_says_what_did_not_come_across(self):
        site = opened(PANTO)
        text = W.wpp_summary(site, PANTO, site['_wpp_notes'])
        self.assertIn('208 pages', text)
        self.assertIn('never written to', text)                 # the .wpp is read-only
        self.assertIn('5 levels deep', text)
        self.assertIn('linked rather than embedded', text)      # 22 of them

    def test_a_wpp_with_no_pages_says_so_rather_than_crashing(self):
        if ROOT is None or not os.path.exists(DESIGNS):
            self.skipTest('Serif’s design gallery is not on this machine')
        with self.assertRaisesRegex(RuntimeError, 'no pages'):
            W.import_webplus_file(DESIGNS, ROOT)


class ItPublishes(unittest.TestCase):
    def test_an_opened_site_publishes_every_page(self):
        site = saveable(opened(LADYSTELLA))
        with tempfile.TemporaryDirectory() as out:
            W.publish_site(site, out)
            for p in site['pages']:
                self.assertTrue(os.path.exists(os.path.join(out, p['file'])), p['file'])
            with open(os.path.join(out, site['pages'][0]['file']), encoding='utf-8') as fh:
                home = fh.read()
        self.assertIn('<img', home)
        self.assertIn('class="obj', home)

    def test_a_vertical_navigation_bar_does_not_wrap_into_columns(self):
        """A nav with a fixed height and flex-wrap becomes two short columns.

        LadyStella's seven-item sidebar did exactly that when published.
        """
        self.assertIn('.obj-nav.v{flex-direction:column;flex-wrap:nowrap', W.PUBLISH_CSS)


class WhereTheCommandIs(unittest.TestCase):
    def test_it_is_on_the_file_menu_above_save(self):
        win = W.MainWindow()
        try:
            items = [a.text() for a in win.menuBar().actions()[0].menu().actions()]
            self.assertIn('Open &WebPlus Site…', items)
            self.assertLess(items.index('Open &WebPlus Site…'), items.index('&Save'))
            self.assertTrue(win.a['openwpp'].isEnabled())
        finally:
            win.close()

    def test_it_is_on_the_startup_assistant(self):
        win = W.MainWindow()
        try:
            from PySide6.QtWidgets import QPushButton
            dlg = W.StartupAssistant(win)
            labels = [b.text() for b in dlg.findChildren(QPushButton)]
            self.assertIn('Open WebPlus Site…', labels)
            dlg.deleteLater()
        finally:
            win.close()


if __name__ == '__main__':
    unittest.main()
