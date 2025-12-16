#include <Arduino.h>
const int FLEX_PIN = A0;

void setup() {
  Serial.begin(115200);
  while (!Serial) delay(10);
}

void loop() {
  static int prev = analogRead(FLEX_PIN);
  int raw = analogRead(FLEX_PIN);

  Serial.print("raw=");
  Serial.print(raw);
  Serial.print("  trend=");
  Serial.println(raw > prev ? "UP" : (raw < prev ? "DOWN" : "STABLE"));

  prev = raw;
  delay(100);
}
