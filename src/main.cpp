#include <Arduino.h>

// Broches des capteurs
const int PIN_VELOSTAT = A0;
const int PIN_FSR      = A1;

// Référence ADC de la Nano 33 BLE Sense
const float VREF = 3.3f;  // 3,3 V

void setup() {
  // Résolution ADC : 10 bits (0..1023)
  analogReadResolution(10);

  Serial.begin(115200);
  while (!Serial) {
    ; // attendre l'ouverture du port série
  }

  Serial.println("Demarrage mesure : Velostat (A0) + FSR (A1)");
  Serial.println("Colonnes : brut_velostat, V_velostat, brut_FSR, V_FSR");
}

void loop() {
  // --- Lecture brute ---
  int rawVelostat = analogRead(PIN_VELOSTAT);
  int rawFSR      = analogRead(PIN_FSR);

  // --- Conversion en tension ---
  float vVelostat = (rawVelostat * VREF) / 1023.0f;
  float vFSR      = (rawFSR      * VREF) / 1023.0f;

  // Affichage lisible (debug humain)
  Serial.print("Velostat -> brut: ");
  Serial.print(rawVelostat);
  Serial.print("  |  V: ");
  Serial.print(vVelostat, 3);
  Serial.print(" V   ||   ");

  Serial.print("FSR -> brut: ");
  Serial.print(rawFSR);
  Serial.print("  |  V: ");
  Serial.print(vFSR, 3);
  Serial.println(" V");

  // Si tu veux un format "données" (pour un logger Python), tu peux
  // ajouter en plus une ligne du type :
  // Serial.print(vVelostat, 4);
  // Serial.print(" ");
  // Serial.println(vFSR, 4);

  delay(20); // ~50 Hz
}
