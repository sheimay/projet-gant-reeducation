#include <Arduino.h>

void setup() {
  Serial.begin(115200);       // Démarre la communication
  while (!Serial) {           // Attends l'ouverture du Serial Monitor
    ;  
  }

  Serial.println("Serial OK !");
}

void loop() {
  Serial.println("Hello !");
  delay(1000);
}