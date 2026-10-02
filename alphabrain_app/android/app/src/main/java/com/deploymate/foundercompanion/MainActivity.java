package com.deploymate.foundercompanion;

import android.os.Bundle;
import android.content.pm.PackageManager;
import android.webkit.PermissionRequest;
import android.webkit.WebChromeClient;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.core.graphics.Insets;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // 1. Runtime request for CAMERA and AUDIO permissions
        if (checkSelfPermission(android.Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{
                android.Manifest.permission.CAMERA,
                android.Manifest.permission.RECORD_AUDIO
            }, 101);
        }

        // Enable Chrome DevTools inspection of WebView
        android.webkit.WebView.setWebContentsDebuggingEnabled(true);

        // 2. Auto-grant WebView WebRTC video/audio capture requests for physical QR scanning
        if (getBridge() != null && getBridge().getWebView() != null) {
            getBridge().getWebView().setWebChromeClient(new WebChromeClient() {
                @Override
                public void onPermissionRequest(final PermissionRequest request) {
                    runOnUiThread(() -> {
                        request.grant(request.getResources());
                    });
                }
            });
        }

        // 3. Measure dynamic system bar insets (Top Status Bar/Punch-Hole & Bottom 3-Button vs Gesture Navigation)
        ViewCompat.setOnApplyWindowInsetsListener(getWindow().getDecorView(), (view, windowInsets) -> {
            Insets insets = windowInsets.getInsets(WindowInsetsCompat.Type.systemBars());
            float density = getResources().getDisplayMetrics().density;
            int topDp = Math.round(insets.top / density);
            int bottomDp = Math.round(insets.bottom / density);

            if (getBridge() != null && getBridge().getWebView() != null) {
                String js = String.format(
                    "document.documentElement.style.setProperty('--android-safe-top', '%dpx');" +
                    "document.documentElement.style.setProperty('--android-safe-bottom', '%dpx');",
                    topDp, bottomDp
                );
                getBridge().getWebView().evaluateJavascript(js, null);
            }
            return windowInsets;
        });
    }
}
