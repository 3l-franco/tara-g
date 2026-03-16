package com.tarag.staff;

import android.annotation.SuppressLint;
import android.content.SharedPreferences;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.net.ConnectivityManager;
import android.net.NetworkInfo;
import android.os.Build;
import android.os.Bundle;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;
import android.webkit.CookieManager;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.ProgressBar;
import android.widget.TextView;
import androidx.appcompat.app.AppCompatActivity;
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout;

public class MainActivity extends AppCompatActivity {

    // ============================================================
    // CHANGE THIS TO YOUR STREAMLIT CLOUD URL
    // ============================================================
    private static final String APP_URL = "https://tgbackops.streamlit.app";
    // ============================================================

    private WebView webView;
    private ProgressBar progressBar;
    private SwipeRefreshLayout swipeRefresh;
    private View offlineView;
    private static final String PREFS_NAME  = "TaraGPrefs";
    private static final String KEY_LAST_URL = "lastUrl";

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        setTheme(R.style.Theme_TaraGStaff);  // switch from splash to normal
        super.onCreate(savedInstanceState);

        // Edge-to-edge: extend content behind system bars
        Window window = getWindow();
        window.addFlags(WindowManager.LayoutParams.FLAG_DRAWS_SYSTEM_BAR_BACKGROUNDS);
        window.setStatusBarColor(Color.parseColor("#F5C518"));
        window.setNavigationBarColor(Color.parseColor("#F5C518"));
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            window.setDecorFitsSystemWindows(true);
        }
        // Light status bar icons (dark icons on gold bar)
        View decorView = window.getDecorView();
        decorView.setSystemUiVisibility(
            View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR |
            View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR
        );

        setContentView(R.layout.activity_main);

        webView = findViewById(R.id.webview);
        progressBar = findViewById(R.id.progressBar);
        swipeRefresh = findViewById(R.id.swipeRefresh);
        offlineView = findViewById(R.id.offlineView);
        TextView retryButton = findViewById(R.id.retryButton);

        // --- Cookie persistence (keeps user logged in) ---
        CookieManager cookieManager = CookieManager.getInstance();
        cookieManager.setAcceptCookie(true);
        cookieManager.setAcceptThirdPartyCookies(webView, true);

        // --- WebView settings ---
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setCacheMode(WebSettings.LOAD_DEFAULT);
        settings.setDatabaseEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setGeolocationEnabled(false);

        // Mobile-native feel
        settings.setUseWideViewPort(true);
        settings.setLoadWithOverviewMode(true);
        settings.setSupportZoom(false);
        settings.setBuiltInZoomControls(false);
        settings.setDisplayZoomControls(false);
        settings.setTextZoom(100);   // prevent system font-size from inflating layout

        // Performance
        settings.setRenderPriority(WebSettings.RenderPriority.HIGH);
        settings.setEnableSmoothTransition(true);

        // Explicit mobile user-agent so Streamlit serves mobile-friendly content
        String ua = settings.getUserAgentString();
        if (!ua.contains("Mobile")) {
            settings.setUserAgentString(ua + " Mobile");
        }

        // Match WebView background to app surface color — prevents white flash
        webView.setBackgroundColor(Color.parseColor("#FFFDF5"));

        // Disable long-press selection menu (no "open in new tab", "save image", etc.)
        webView.setOnLongClickListener(v -> true);
        webView.setLongClickable(false);

        // Keep links inside the app
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageStarted(WebView view, String url, Bitmap favicon) {
                progressBar.setVisibility(View.VISIBLE);
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                progressBar.setVisibility(View.GONE);
                swipeRefresh.setRefreshing(false);

                // Flush cookies to disk so they survive app restarts
                CookieManager.getInstance().flush();

                // Persist the URL if it contains the auth token so the user
                // stays logged in when the app is closed and reopened.
                if (url != null && url.contains("?t=")) {
                    SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
                    prefs.edit().putString(KEY_LAST_URL, url).apply();
                }

                // Inject JS: ensure viewport + hide Streamlit chrome + remove top gap
                view.evaluateJavascript(
                    "(function(){" +
                    // 1. Force mobile viewport meta
                    "var m=document.querySelector('meta[name=\"viewport\"]');" +
                    "if(!m){m=document.createElement('meta');m.name='viewport';document.head.appendChild(m);}" +
                    "m.content='width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no';" +
                    // 2. Hide Streamlit branding
                    "var s='display:none!important;visibility:hidden!important;height:0!important;';" +
                    "['footer','[data-testid=\"manage-app-button\"]','.viewerBadge_container__r5tak'," +
                    "'.stAppDeployButton','iframe[title=\"streamlit_badge\"]'," +
                    "'[data-testid=\"stStatusWidget\"]','[data-testid=\"stDecoration\"]'," +
                    "'header[data-testid=\"stHeader\"]','[data-testid=\"stToolbar\"]'].forEach(function(q){" +
                    "document.querySelectorAll(q).forEach(function(e){e.style.cssText=s;});});" +
                    "document.querySelectorAll('a').forEach(function(a){var h=a.href||'';" +
                    "if(h.indexOf('streamlit.io')!==-1||h.indexOf('github.com')!==-1)" +
                    "{a.style.cssText=s;if(a.parentElement)a.parentElement.style.cssText='display:none!important;';}});" +
                    // 3. Remove top white space
                    "['[data-testid=\"stMain\"]','[data-testid=\"stAppViewContainer\"]'," +
                    "'[data-testid=\"stMainBlockContainer\"]','.block-container','section.main'].forEach(function(q){" +
                    "document.querySelectorAll(q).forEach(function(e){" +
                    "e.style.setProperty('padding-top','0','important');" +
                    "e.style.setProperty('margin-top','0','important');});});" +
                    "})();", null);
            }

            @Override
            public void onReceivedError(WebView view, int errorCode,
                                        String description, String failingUrl) {
                if (failingUrl.equals(APP_URL) || failingUrl.equals(APP_URL + "/")) {
                    showOffline();
                }
            }
        });

        // Progress bar tracks loading percentage
        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onProgressChanged(WebView view, int newProgress) {
                progressBar.setProgress(newProgress);
            }
        });

        // Pull-to-refresh disabled — prevents accidental page reload when scrolling back to top
        swipeRefresh.setEnabled(false);

        // Retry button (shown when offline)
        retryButton.setOnClickListener(v -> {
            if (isOnline()) {
                showWebView();
                webView.loadUrl(APP_URL);
            }
        });

        // Load the app — restore token URL if previously saved
        if (isOnline()) {
            SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
            String savedUrl = prefs.getString(KEY_LAST_URL, null);
            webView.loadUrl(savedUrl != null ? savedUrl : APP_URL);
        } else {
            showOffline();
        }
    }

    // Handle Android back button
    @Override
    public void onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        CookieManager.getInstance().setAcceptCookie(true);
        webView.onResume();
        webView.resumeTimers();
    }

    @Override
    protected void onPause() {
        super.onPause();
        webView.onPause();
        webView.pauseTimers();
    }

    @Override
    protected void onDestroy() {
        if (webView != null) {
            webView.stopLoading();
            webView.destroy();
        }
        super.onDestroy();
    }

    private boolean isOnline() {
        ConnectivityManager cm = (ConnectivityManager) getSystemService(CONNECTIVITY_SERVICE);
        NetworkInfo ni = cm.getActiveNetworkInfo();
        return ni != null && ni.isConnected();
    }

    private void showOffline() {
        webView.setVisibility(View.GONE);
        swipeRefresh.setVisibility(View.GONE);
        offlineView.setVisibility(View.VISIBLE);
    }

    private void showWebView() {
        offlineView.setVisibility(View.GONE);
        webView.setVisibility(View.VISIBLE);
        swipeRefresh.setVisibility(View.VISIBLE);
    }
}
