// ====== CAPTEURS ANALOGIQUES ======
// A0 : capteur de flexion du majeur # vert 
// A1 : capteur de flexion de l'index # jaune 
// A2 : capteur FSR du pouce #bleu
// A3 : capteur FSR de l'index # blanc

#include <Arduino.h>
#include <Arduino_BMI270_BMM150.h>

// ---- BONUS : logging sur carte SD ----
// Mettre à 1 si tu as un module SD et que la bibliothèque SD est installée
#define ENABLE_SD_LOGGING 0

#if ENABLE_SD_LOGGING
  #include <SPI.h>
  #include <SD.h>
  const int SD_CS_PIN = 10;    // Pin CS de la carte SD (à adapter selon ton câblage)
  File logFile;
#endif

// Broches capteurs
const int FLEX_THUMB_PIN  = A0;
const int FLEX_INDEX_PIN  = A1;
const int FSR_THUMB_PIN   = A2;
const int FSR_INDEX_PIN   = A3;

// Période d'échantillonnage (ms) → 100 Hz
const unsigned long SAMPLE_INTERVAL_MS = 10;
unsigned long lastSampleTime = 0;

// Variables IMU
float ax = 0, ay = 0, az = 0;     // Accélération (g)
float gx = 0, gy = 0, gz = 0;     // Vitesse angulaire (deg/s)

// =====================================================================
// SETUP
// =====================================================================
void setup() {
  // Série
  Serial.begin(115200);
  while (!Serial) {
    ; // attendre que le port série s'ouvre (utile en USB)
  }

  // Entrées analogiques
  pinMode(FLEX_THUMB_PIN, INPUT);
  pinMode(FLEX_INDEX_PIN, INPUT);
  pinMode(FSR_THUMB_PIN, INPUT);
  pinMode(FSR_INDEX_PIN, INPUT);

  // IMU
  if (!IMU.begin()) {
    Serial.println("ERREUR : impossible d'initialiser l'IMU (Arduino_LSM9DS1) !");
    while (1) {
      // Bloqué ici si l'IMU ne démarre pas
    }
  }

#if ENABLE_SD_LOGGING
  // Initialisation carte SD
  if (!SD.begin(SD_CS_PIN)) {
    Serial.println("ERREUR : initialisation de la carte SD échouée.");
  } else {
    logFile = SD.open("log.csv", FILE_WRITE);
    if (!logFile) {
      Serial.println("ERREUR : impossible d'ouvrir log.csv pour écriture.");
    }
  }
#endif

  // En-tête CSV
  Serial.println("t_ms,flex_thumb,flex_index,fsr_thumb,fsr_index,ax_g,ay_g,az_g,gx_dps,gy_dps,gz_dps");

#if ENABLE_SD_LOGGING
  if (logFile) {
    logFile.println("t_ms,flex_thumb,flex_index,fsr_thumb,fsr_index,ax_g,ay_g,az_g,gx_dps,gy_dps,gz_dps");
    logFile.flush();
  }
#endif
}

// =====================================================================
// LOOP
// =====================================================================
void loop() {
  unsigned long now = millis();

  if (now - lastSampleTime >= SAMPLE_INTERVAL_MS) {
    lastSampleTime = now;

    // ---- Lecture analogique ----
    int flexThumb = analogRead(FLEX_THUMB_PIN);   // 0–1023
    int flexIndex = analogRead(FLEX_INDEX_PIN);   // 0–1023
    int fsrThumb  = analogRead(FSR_THUMB_PIN);    // 0–1023
    int fsrIndex  = analogRead(FSR_INDEX_PIN);    // 0–1023

    // ---- Accéléromètre ----
    if (IMU.accelerationAvailable()) {
      IMU.readAcceleration(ax, ay, az);          // en g
    }

    // ---- Gyroscope ----
    if (IMU.gyroscopeAvailable()) {
      IMU.readGyroscope(gx, gy, gz);             // en deg/s
    }

    // ---- Construction de la ligne CSV ----
    String line = String(now);           // t_ms
    line += ",";
    line += String(flexThumb);
    line += ",";
    line += String(flexIndex);
    line += ",";
    line += String(fsrThumb);
    line += ",";
    line += String(fsrIndex);
    line += ",";
    line += String(ax, 6);
    line += ",";
    line += String(ay, 6);
    line += ",";
    line += String(az, 6);
    line += ",";
    line += String(gx, 6);
    line += ",";
    line += String(gy, 6);
    line += ",";
    line += String(gz, 6);

    // ---- Envoi sur le port série ----
    Serial.println(line);

#if ENABLE_SD_LOGGING
    // ---- Écriture sur SD (bonus) ----
    if (logFile) {
      logFile.println(line);
      // flush à chaque échantillon pour simplifier (à optimiser si besoin de très haut débit)
      logFile.flush();
    }
#endif
  }
}
