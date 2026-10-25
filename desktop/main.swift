import AppKit
import WebKit
import UniformTypeIdentifiers

final class OverlayPanel: NSPanel {
    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { false }
    var onDragEnd: (() -> Void)?
    private var pendingDown: NSEvent?
    private var initialMouse = NSPoint.zero
    private var initialOrigin = NSPoint.zero
    private var dragging = false

    override func sendEvent(_ event: NSEvent) {
        switch event.type {
        case .leftMouseDown where event.locationInWindow.x >= 0 && event.locationInWindow.x < 110:
            // Defer the web button press until release, so a drag never toggles capture.
            pendingDown = event
            initialMouse = convertPoint(toScreen:event.locationInWindow)
            initialOrigin = frame.origin
            dragging = false
            // Track explicitly: WKWebView has not received mouseDown during a possible drag.
            while pendingDown != nil,
                  let next = NSApp.nextEvent(matching:[.leftMouseDragged,.leftMouseUp],
                                             until:Date.distantFuture, inMode:.eventTracking, dequeue:true) {
                sendEvent(next)
            }
            return
        case .leftMouseDragged where pendingDown != nil:
            let mouse = convertPoint(toScreen:event.locationInWindow)
            let dx = mouse.x - initialMouse.x, dy = mouse.y - initialMouse.y
            if !dragging && hypot(dx, dy) >= 4 {
                dragging = true
                NSCursor.closedHand.push()
            }
            if dragging { setFrameOrigin(NSPoint(x: initialOrigin.x + dx, y: initialOrigin.y + dy)) }
            return
        case .leftMouseUp where pendingDown != nil:
            let down = pendingDown!
            pendingDown = nil
            if dragging {
                dragging = false
                NSCursor.pop()
                onDragEnd?()
            } else {
                super.sendEvent(down)
                super.sendEvent(event)
            }
            return
        default: break
        }
        super.sendEvent(event)
    }
}
final class HoverSurface: NSView {
    var onHover: ((Bool)->Void)?
    override func updateTrackingAreas() {
        super.updateTrackingAreas()
        for area in trackingAreas { removeTrackingArea(area) }
        addTrackingArea(NSTrackingArea(rect:bounds,options:[.mouseEnteredAndExited,.activeAlways,.inVisibleRect],owner:self,userInfo:nil))
    }
    override func mouseEntered(with event:NSEvent) { onHover?(true) }
    override func mouseExited(with event:NSEvent) { onHover?(false) }
}
final class DragHandle: NSView {
    var reveal: (()->Void)?
    override func mouseDown(with event: NSEvent) {
        if bounds.width < 100 { reveal?() } else { window?.performDrag(with:event) }
    }
    override func accessibilityPerformPress() -> Bool { reveal?(); return true }
    override func draw(_ dirtyRect: NSRect) {
        NSColor(calibratedWhite:0.68,alpha:1).setFill()
        NSBezierPath(roundedRect:NSRect(x:bounds.midX-16,y:bounds.midY-1.5,width:32,height:3),xRadius:2,yRadius:2).fill()
    }
}

final class WidgetApp: NSObject, NSApplicationDelegate, NSWindowDelegate, WKUIDelegate, WKNavigationDelegate, WKScriptMessageHandler {
    var window: NSWindow!
    var web: WKWebView!
    var statusItem: NSStatusItem!
    var server: Process?
    var attempts = 0
    var systemCapture: AnyObject?
    var expanded = false
    var hovered = false
    var capturing = false
    var hideWork: DispatchWorkItem?
    var handleHeight: NSLayoutConstraint!
    private let positionKey = "overlayPosition"
    func keepOverlayVisible() {
        guard window != nil else { return }
        let frame = window.frame
        let screens = NSScreen.screens.map { $0.visibleFrame }
        guard let screen = screens.max(by: {
            let a = $0.intersection(frame), b = $1.intersection(frame)
            return (a.isNull ? 0 : a.width*a.height) < (b.isNull ? 0 : b.width*b.height)
        }) else { return }
        window.setFrameOrigin(NSPoint(x: max(screen.minX, min(frame.minX, screen.maxX-frame.width)),
                                      y: max(screen.minY, min(frame.minY, screen.maxY-frame.height))))
    }
    func savePosition() {
        keepOverlayVisible()
        UserDefaults.standard.set(["x":window.frame.minX,"y":window.frame.minY], forKey:positionKey)
    }
    @objc func screensChanged() { keepOverlayVisible() }
    func resizeOverlay() {
        guard window != nil else { return }
        let revealed = true
        let size = NSSize(width:188,height:34)
        var frame = NSRect(x:window.frame.midX-size.width/2,y:window.frame.minY,width:size.width,height:size.height)
        if let visible = window.screen?.visibleFrame {
            frame.origin.x = max(visible.minX,min(frame.origin.x,visible.maxX-frame.width))
            frame.origin.y = max(visible.minY,min(frame.origin.y,visible.maxY-frame.height))
        }
        web.isHidden = !revealed
        handleHeight.constant = 0
        window.contentView?.layer?.cornerRadius = revealed ? 20 : 9
        if NSWorkspace.shared.accessibilityDisplayShouldReduceMotion {
            window.setFrame(frame,display:true,animate:false)
        } else {
            NSAnimationContext.runAnimationGroup { context in
                context.duration = 0.16
                window.animator().setFrame(frame,display:true)
            }
        }
    }
    func hover(_ inside:Bool) {
        hideWork?.cancel()
        if inside { hovered=true; resizeOverlay() }
        else {
            let work = DispatchWorkItem { [weak self] in self?.hovered=false; self?.resizeOverlay() }
            hideWork=work; DispatchQueue.main.asyncAfter(deadline:.now()+0.8,execute:work)
        }
    }

    func stopSystemAudio() {
        if #available(macOS 13.0, *), let capture = systemCapture as? SystemAudioCapture { capture.stop() }
    }
    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard message.frameInfo.isMainFrame, message.frameInfo.securityOrigin.host == "127.0.0.1",
              message.frameInfo.securityOrigin.port == 8765, let action = message.body as? String else { return }
        if action == "expand" || action == "collapse" {
            expanded = action == "expand"
            resizeOverlay()
            return
        }
        if action == "hide" { _ = windowShouldClose(window); return }
        if #available(macOS 13.0, *) {
            if systemCapture == nil {
                let capture = SystemAudioCapture()
                capture.onEvent = { [weak self] event in
                    let state = event["state"] as? String
                    if state != "levels" {
                        let next = state != "stopped" && state != "error"
                        if self?.capturing != next { self?.capturing = next; self?.resizeOverlay() }
                    }
                    guard let bytes = try? JSONSerialization.data(withJSONObject:event),
                          let json = String(data:bytes,encoding:.utf8) else { return }
                    self?.web.evaluateJavaScript("window.onSystemAudioEvent?.(" + json + ")",completionHandler:nil)
                }
                systemCapture = capture
            }
            let capture = systemCapture as! SystemAudioCapture
            if action == "start" { capture.start() } else if action == "stop" { capture.stop() }
        }
    }
    let address = URL(string: "http://127.0.0.1:8765/?widget=1")!

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
        statusItem.button?.image = NSImage(systemSymbolName: "waveform", accessibilityDescription: "Voice Check")
        let menu = NSMenu()
        menu.addItem(withTitle: "Show Voice Check", action: #selector(showWidget), keyEquivalent: "")
        menu.addItem(NSMenuItem.separator())
        menu.addItem(withTitle: "Quit Voice Check", action: #selector(quitWidget), keyEquivalent: "q")
        for item in menu.items { item.target = self }
        statusItem.menu = menu
        let mainMenu = NSMenu()
        let appMenuItem = NSMenuItem()
        let appMenu = NSMenu()
        let quit = NSMenuItem(title: "Quit Voice Check", action: #selector(quitWidget), keyEquivalent: "q")
        quit.target = self
        appMenu.addItem(quit)
        appMenuItem.submenu = appMenu
        mainMenu.addItem(appMenuItem)
        NSApp.mainMenu = mainMenu

        let config = WKWebViewConfiguration()
        config.mediaTypesRequiringUserActionForPlayback = []
        config.userContentController.add(self,name:"systemAudio")
        web = WKWebView(frame: .zero, configuration: config)
        web.uiDelegate = self
        web.navigationDelegate = self
        window = OverlayPanel(contentRect:NSRect(x:0,y:0,width:188,height:34),
                              styleMask:[.borderless,.nonactivatingPanel],backing:.buffered,defer:false)
        window.title = "Voice Check"
        window.level = .floating
        window.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        window.isReleasedWhenClosed = false
        window.isOpaque = false
        window.backgroundColor = .clear
        window.hasShadow = false
        (window as? NSPanel)?.hidesOnDeactivate = false
        window.delegate = self
        (window as? OverlayPanel)?.onDragEnd = { [weak self] in self?.savePosition() }
        NotificationCenter.default.addObserver(self, selector:#selector(screensChanged),
            name:NSApplication.didChangeScreenParametersNotification, object:nil)
        let surface = HoverSurface()
        // The whole pill is a click target; hovering never changes its size.
        surface.wantsLayer = true
        surface.layer?.backgroundColor = NSColor.clear.cgColor
        surface.layer?.cornerRadius = 20
        surface.layer?.masksToBounds = true
        window.contentView = surface
        let handle = DragHandle()
        handle.isHidden = true
        handle.reveal = { [weak self] in self?.hover(true) }
        handle.setAccessibilityElement(false)
        handle.setAccessibilityRole(.button)
        handle.setAccessibilityLabel("Show Voice Check controls; drag when expanded")
        handleHeight = handle.heightAnchor.constraint(equalToConstant:18)
        handle.translatesAutoresizingMaskIntoConstraints = false
        web.translatesAutoresizingMaskIntoConstraints = false
        web.setValue(false,forKey:"drawsBackground")
        surface.addSubview(handle); surface.addSubview(web)
        NSLayoutConstraint.activate([
            handle.topAnchor.constraint(equalTo:surface.topAnchor),
            handle.leadingAnchor.constraint(equalTo:surface.leadingAnchor),
            handle.trailingAnchor.constraint(equalTo:surface.trailingAnchor),
            handleHeight,
            web.topAnchor.constraint(equalTo:handle.bottomAnchor),
            web.leadingAnchor.constraint(equalTo:surface.leadingAnchor),
            web.trailingAnchor.constraint(equalTo:surface.trailingAnchor),
            web.bottomAnchor.constraint(equalTo:surface.bottomAnchor)
        ])
        if let screen = NSScreen.main {
            window.setFrameOrigin(NSPoint(x:screen.visibleFrame.midX-94,y:screen.visibleFrame.minY+5))
        }
        if let saved = UserDefaults.standard.dictionary(forKey:positionKey),
           let x = saved["x"] as? Double, let y = saved["y"] as? Double, x.isFinite, y.isFinite {
            window.setFrameOrigin(NSPoint(x:x,y:y))
            keepOverlayVisible()
        }
        resizeOverlay()
        showWidget()
        web.loadHTMLString("<html><body style='background:#171717;color:#eee;font:12px -apple-system;padding:8px'>Starting Voice Check…</body></html>", baseURL: address)
        checkServer(startIfMissing: true)
    }

    func checkServer(startIfMissing: Bool) {
        var request = URLRequest(url: URL(string: "http://127.0.0.1:8765/health")!)
        request.timeoutInterval = 2
        URLSession.shared.dataTask(with: request) { data, response, error in
            let ok = (response as? HTTPURLResponse)?.statusCode == 200 &&
                (data.flatMap { try? JSONSerialization.jsonObject(with: $0) } as? [String: Any])?["ready"] as? Bool == true
            DispatchQueue.main.async {
                if ok { self.web.load(URLRequest(url: self.address)); return }
                if startIfMissing { self.startServer() }
                self.attempts += 1
                if self.attempts < 60 {
                    DispatchQueue.main.asyncAfter(deadline: .now() + 1) { self.checkServer(startIfMissing: false) }
                } else {
                    self.web.loadHTMLString("<html><body style='font:15px -apple-system;padding:25px'><h2>Detector couldn’t start</h2><p>Run .venv/bin/python app.py in your project, then reopen Voice Check.</p><p>Details are in work/widget-server.log.</p></body></html>", baseURL: self.address)
                }
            }
        }.resume()
    }

    func startServer() {
        guard let root = Bundle.main.object(forInfoDictionaryKey: "VoiceCheckProjectPath") as? String else { return }
        let task = Process()
        task.executableURL = URL(fileURLWithPath: root + "/.venv/bin/python")
        task.arguments = [root + "/app.py"]
        var environment = ProcessInfo.processInfo.environment
        environment["PATH"] = root + "/.venv/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
        task.environment = environment
        task.currentDirectoryURL = URL(fileURLWithPath: root)
        let log = root + "/work/widget-server.log"
        FileManager.default.createFile(atPath: log, contents: nil)
        if let output = FileHandle(forWritingAtPath: log) { task.standardOutput = output; task.standardError = output }
        do { try task.run(); server = task } catch { NSLog("Voice Check backend: %@", error.localizedDescription) }
    }

    @objc func showWidget() { window?.orderFrontRegardless() }
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool { showWidget(); return true }
    @objc func quitWidget() { NSApp.terminate(nil) }
    func windowShouldClose(_ sender: NSWindow) -> Bool {
        stopSystemAudio()
        web.evaluateJavaScript("window.dispatchEvent(new Event('widget-hidden'))", completionHandler: nil)
        sender.orderOut(nil)
        return false
    }
    func applicationWillTerminate(_ notification: Notification) { stopSystemAudio(); if server?.isRunning == true { server?.terminate() } }

    func webView(_ webView: WKWebView, runOpenPanelWith parameters: WKOpenPanelParameters,
                 initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping ([URL]?) -> Void) {
        let panel = NSOpenPanel()
        panel.canChooseDirectories = false
        panel.allowsMultipleSelection = false
        panel.allowedContentTypes = [.audio, .movie]
        panel.beginSheetModal(for: window) { result in completionHandler(result == .OK ? panel.urls : nil) }
    }

    @available(macOS 12.0, *)
    func webView(_ webView: WKWebView, requestMediaCapturePermissionFor origin: WKSecurityOrigin,
                 initiatedByFrame frame: WKFrameInfo, type: WKMediaCaptureType,
                 decisionHandler: @escaping (WKPermissionDecision) -> Void) {
        // Keep the system/user permission prompt; never grant camera access.
        decisionHandler(origin.host == "127.0.0.1" && origin.port == 8765 && type == .microphone ? .prompt : .deny)
    }

    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = navigationAction.request.url else { decisionHandler(.cancel); return }
        decisionHandler((url.host == "127.0.0.1" && url.port == 8765) || url.absoluteString == "about:blank" ? .allow : .cancel)
    }
}

let app = NSApplication.shared
let delegate = WidgetApp()
app.delegate = delegate
app.run()
