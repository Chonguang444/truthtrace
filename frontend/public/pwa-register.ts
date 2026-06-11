// Register PWA Service Worker
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").then(reg => {
      console.log("[PWA] Service Worker registered: ", reg.scope);
    }).catch(err => {
      console.log("[PWA] SW registration failed: ", err);
    });
  });

  // Install prompt
  let deferredPrompt: any = null;
  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    deferredPrompt = e;
    // Show install button after 30s of engagement
    setTimeout(() => {
      if (deferredPrompt) {
        const btn = document.getElementById("pwa-install-btn");
        if (btn) { btn.style.display = "flex"; btn.onclick = () => { deferredPrompt.prompt(); deferredPrompt = null; }; }
      }
    }, 30000);
  });
}

export {};
