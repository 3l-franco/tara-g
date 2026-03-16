# ui/staff/topbar.py

import os
import streamlit as st
from ui.components import get_logo_b64, esc


def _read_mobile_css():
    css_file = 'styles/mobile.css'
    if os.path.exists(css_file):
        with open(css_file, encoding='utf-8') as f:
            return f.read()
    return ''


def load_mobile_css():
    """Loads the staff mobile stylesheet + JS helpers."""
    css = _read_mobile_css()
    if css:
        st.markdown(f'<style>{css}</style>', unsafe_allow_html=True)

    # JS: pull-to-refresh block + dropdown dismiss + footer nuke
    st.markdown('''
    <script>
    (function(){

        /* ══════════════════════════════════════════════════════
           0. KILL TOP WHITE-SPACE
           Streamlit reserves padding-top for its hidden header.
           We forcibly zero it out via both CSS and JS.
        ══════════════════════════════════════════════════════ */
        function killTopGap() {
            // Target every container Streamlit might put padding-top on
            var padSelectors = [
                '[data-testid="stMain"]',
                '[data-testid="stAppViewContainer"]',
                '[data-testid="stMainBlockContainer"]',
                '[data-testid="stAppViewBlockContainer"]',
                'section.main',
                // Streamlit 1.55 uses emotion — first child div inside stMain
                '[data-testid="stMain"] > div',
                '[data-testid="stMainBlockContainer"] > div'
            ];
            padSelectors.forEach(function(sel) {
                document.querySelectorAll(sel).forEach(function(el) {
                    el.style.setProperty('padding-top', '0', 'important');
                    el.style.setProperty('margin-top', '0', 'important');
                });
            });
            // Forcibly zero height of header elements — they must not occupy space
            [
                'header[data-testid="stHeader"]',
                '[data-testid="stDecoration"]',
                '[data-testid="stToolbar"]'
            ].forEach(function(sel) {
                document.querySelectorAll(sel).forEach(function(el) {
                    el.style.setProperty('display', 'none', 'important');
                    el.style.setProperty('height', '0', 'important');
                    el.style.setProperty('min-height', '0', 'important');
                    el.style.setProperty('max-height', '0', 'important');
                    el.style.setProperty('overflow', 'hidden', 'important');
                    el.style.setProperty('position', 'absolute', 'important');
                    el.style.setProperty('top', '-9999px', 'important');
                });
            });
        }
        // Run immediately then poll every 150ms for 10s
        // Polling is necessary because React sets inline styles AFTER our JS runs
        // and MutationObserver childList doesn't fire for attribute (style) updates
        killTopGap();
        var _gapTimer = setInterval(killTopGap, 150);
        setTimeout(function(){ clearInterval(_gapTimer); }, 10000);
        // Also observe DOM insertions (for initial mount) only — NOT style attributes
        // (attribute observation fires on every Streamlit re-render and causes jank)
        new MutationObserver(function(mutations) {
            for (var i = 0; i < mutations.length; i++) {
                var m = mutations[i];
                if (m.type === 'childList') {
                    killTopGap();
                    return;
                }
            }
        }).observe(document.documentElement, {
            childList: true,
            subtree: true
            // No 'attributes' observation — firing on every style muation causes jank
        });

        /* ══════════════════════════════════════════════════════
           1. PULL-TO-REFRESH PREVENTION (comprehensive)
           Android Chrome triggers PTR when window OR the main
           scroll container is at scrollTop=0 and the user
           swipes finger downward.  We block it at every level.
        ══════════════════════════════════════════════════════ */
        var _startY = 0;

        // CSS safety net — applied immediately
        (function(){
            var style = document.createElement('style');
            style.textContent = [
                'html, body {',
                '  overscroll-behavior: none !important;',
                '  touch-action: pan-y !important;',
                '}',
                '[data-testid="stAppViewContainer"],',
                '[data-testid="stMain"],',
                'section.main {',
                '  overscroll-behavior: none !important;',
                '}'
            ].join('\n');
            (document.head || document.documentElement).appendChild(style);
        })();

        // Returns all possible scroll containers
        function getScrollers() {
            return [
                document.querySelector('[data-testid="stAppViewContainer"]'),
                document.querySelector('[data-testid="stMain"]'),
                document.querySelector('section.main'),
                document.documentElement,
                document.body
            ].filter(Boolean);
        }

        // Returns true if ANY scroller is not at the very top
        function anyScrolledDown() {
            return getScrollers().some(function(el){ return el.scrollTop > 0; });
        }

        document.addEventListener('touchstart', function(e){
            if (e.touches && e.touches.length >= 1) {
                _startY = e.touches[0].clientY;
            }
        }, {passive: true});

        document.addEventListener('touchmove', function(e){
            if (!e.touches || e.touches.length === 0) return;
            var currentY  = e.touches[0].clientY;
            var movingDown = currentY > _startY;   // downward finger swipe = scroll UP intent
            var winAtTop   = (window.scrollY || window.pageYOffset || 0) <= 0;
            var allAtTop   = !anyScrolledDown();    // all containers at top

            // PTR triggers when user swipes down while everything is at the top
            if (movingDown && winAtTop && allAtTop) {
                e.preventDefault();
            }
        }, {passive: false});   // MUST be non-passive to call preventDefault

        // Also attach directly to each scroll container when they appear
        function attachToContainer(el) {
            if (!el || el._ptrBlocked) return;
            el._ptrBlocked = true;
            el.addEventListener('touchmove', function(e){
                if (!e.touches || e.touches.length === 0) return;
                var movingDown = e.touches[0].clientY > _startY;
                if (movingDown && el.scrollTop <= 0) {
                    e.preventDefault();
                }
            }, {passive: false});
        }

        function attachToAll() {
            getScrollers().forEach(attachToContainer);
        }
        attachToAll();

        // Re-attach whenever Streamlit re-renders the DOM
        var _ptrObserver = new MutationObserver(attachToAll);
        _ptrObserver.observe(document.documentElement, {childList: true, subtree: true});

        /* ══════════════════════════════════════════════════════
           2. DROPDOWN COLLAPSE ON RE-TAP
        ══════════════════════════════════════════════════════ */
        document.addEventListener('click', function(e){
            var sel = e.target.closest('[data-baseweb="select"]');
            if (!sel) {
                document.querySelectorAll('[data-baseweb="select"] input').forEach(function(inp){
                    inp.blur();
                });
                var escEvt = new KeyboardEvent('keydown', {
                    key:'Escape', code:'Escape', keyCode:27, bubbles:true
                });
                document.querySelectorAll('[data-baseweb="popover"]').forEach(function(p){
                    p.dispatchEvent(escEvt);
                });
            }
        }, true);

        /* ══════════════════════════════════════════════════════
           3. NUKE STREAMLIT BRANDING
        ══════════════════════════════════════════════════════ */
        function nukeFooter(){
            var selectors = [
                'footer', '[data-testid="manage-app-button"]',
                '.viewerBadge_container__r5tak', '.stAppDeployButton',
                'iframe[title="streamlit_badge"]',
                '[data-testid="stStatusWidget"]',
                '[data-testid="stDecoration"]'
            ];
            document.querySelectorAll('a').forEach(function(a){
                var h = a.href || '';
                if (h.indexOf('streamlit.io') !== -1 || h.indexOf('github.com') !== -1) {
                    a.style.cssText = 'display:none!important;';
                    if (a.parentElement) a.parentElement.style.cssText = 'display:none!important;';
                }
            });
            selectors.forEach(function(s){
                document.querySelectorAll(s).forEach(function(el){
                    el.style.cssText = 'display:none!important;';
                });
            });
            // NOTE: the broad querySelectorAll('div, span') loop was removed —
            // it walked every DOM node on every MutationObserver callback causing jank.
            // The targeted selectors above are sufficient.
        }
        nukeFooter();
        setTimeout(nukeFooter, 500);
        setTimeout(nukeFooter, 1500);
        setTimeout(nukeFooter, 3000);
        new MutationObserver(nukeFooter).observe(document.body, {childList:true, subtree:true});

    })();
    </script>''', unsafe_allow_html=True)


def staff_topbar():
    """Compact gold header bar with brand + username badge."""
    b64      = get_logo_b64()
    username = st.session_state.get('username', '')
    # Detect mime from whichever logo file exists
    if os.path.exists('assets/App.png') or os.path.exists('assets/logo.png'):
        mime = 'image/png'
    else:
        mime = 'image/jpeg'

    logo_html = (
        f'<img src="data:{mime};base64,{b64}" alt="logo">'
        if b64 else '')

    st.markdown(
        f'<div class="m-header-anchor">'
        f'<div class="m-header">'
        f'<div class="m-brand">{logo_html} TARA G</div>'
        f'<span class="m-user-chip">@{esc(username)}</span>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True)