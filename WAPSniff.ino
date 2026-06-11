/*  ESP32 WAP + BLE Radar  ─  companion sketch for esp32_radar_gui.py
 *
 *  Outputs one line per discovered device:
 *   TYPE:WIFI | SSID:<name>  | MAC:<xx:xx:xx:xx:xx:xx> | RSSI:<-nn>
 *   TYPE:BLE  | NAME:<name>  | MAC:<xx:xx:xx:xx:xx:xx> | RSSI:<-nn>
 *
 *  Board  : Any ESP32 (WROOM-32, S3, etc.)
 *  Baud   : 115200
 *  Library: NimBLE-Arduino 2.x  (h2zero, install via Library Manager)
 */

#include <Arduino.h>
#include <WiFi.h>
#include <NimBLEDevice.h>

// ── Configuration ────────────────────────────────────────────────────────────
#define WIFI_SCAN_INTERVAL_MS  5000
#define BLE_SCAN_DURATION_SEC  4
#define SERIAL_BAUD            115200

// ── Globals ───────────────────────────────────────────────────────────────────
static unsigned long lastWifiScan = 0;

// ── BLE scan callback (NimBLE 2.x API) ───────────────────────────────────────
void onBLEResult(const NimBLEAdvertisedDevice* dev) {
    String mac = dev->getAddress().toString().c_str();
    mac.toUpperCase();
    int rssi = dev->getRSSI();

    String name = "";
    if (dev->haveName()) {
        name = dev->getName().c_str();
        name.trim();
    }

    Serial.printf("TYPE:BLE | NAME:%s | MAC:%s | RSSI:%d\n",
                  name.c_str(), mac.c_str(), rssi);
}

// ── Setup ─────────────────────────────────────────────────────────────────────
void setup() {
    Serial.begin(SERIAL_BAUD);
    delay(500);
    Serial.println("# ESP32 WAP+BLE Radar starting...");

    // WiFi in station mode for scanning
    WiFi.mode(WIFI_STA);
    WiFi.disconnect();
    delay(100);

    // BLE
    NimBLEDevice::init("");
    NimBLEScan* pScan = NimBLEDevice::getScan();
    pScan->setScanCallbacks(nullptr, false); // clear any old callbacks
    pScan->setActiveScan(true);   // fetch scan-response packets → more names
    pScan->setInterval(100);
    pScan->setWindow(99);

    Serial.println("# Ready.");
}

// ── Loop ──────────────────────────────────────────────────────────────────────
void loop() {
    unsigned long now = millis();

    // ── WiFi scan ────────────────────────────────────────────────────────────
    if (now - lastWifiScan >= WIFI_SCAN_INTERVAL_MS) {
        lastWifiScan = now;

        int n = WiFi.scanNetworks(false, true);   // sync, include hidden
        for (int i = 0; i < n; i++) {
            String ssid = WiFi.SSID(i);
            String mac  = WiFi.BSSIDstr(i);
            mac.toUpperCase();
            int rssi = WiFi.RSSI(i);

            if (ssid.isEmpty()) ssid = "<hidden>";

            Serial.printf("TYPE:WIFI | SSID:%s | MAC:%s | RSSI:%d\n",
                          ssid.c_str(), mac.c_str(), rssi);
        }
        WiFi.scanDelete();
    }

    // ── BLE scan (blocking) ───────────────────────────────────────────────────
    NimBLEScan* pScan = NimBLEDevice::getScan();
    NimBLEScanResults results = pScan->getResults(BLE_SCAN_DURATION_SEC, false);

    for (int i = 0; i < results.getCount(); i++) {
        onBLEResult(results.getDevice(i));
    }
    pScan->clearResults();
}
