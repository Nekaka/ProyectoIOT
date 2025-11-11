#include <Servo.h>

// --- Pines ---
const int ledLiving = 13;
const int ledCocina = 12;
const int ledDormitorio = 11;
const int pinServo = 9;

// --- Estados ---
bool estadoLiving = false;     // false = OFF, true = ON
bool estadoCocina = false;     // false = OFF, true = ON
bool estadoDormitorio = false; // false = OFF, true = ON
bool estadoPorton = false;     // false = CERRADO, true = ABIERTO

// --- Ángulos del Servo ---
const int anguloCerrado = 0;   // Ángulo del portón cerrado (grados)
const int anguloAbierto = 90;  // Ángulo del portón abierto (grados)

// --- Objetos ---
Servo portonServo;

void setup() {
  // Inicializar el puerto serie (debe coincidir con Python)
  Serial.begin(9600);

  // Configurar los pines de los LEDs como salida
  pinMode(ledLiving, OUTPUT);
  pinMode(ledCocina, OUTPUT);
  pinMode(ledDormitorio, OUTPUT);

  // Conectar el servo al pin 9
  portonServo.attach(pinServo);

  // Asegurarse de que todo esté en estado inicial (apagado/cerrado)
  digitalWrite(ledLiving, LOW);
  digitalWrite(ledCocina, LOW);
  digitalWrite(ledDormitorio, LOW);
  portonServo.write(anguloCerrado);
}

void loop() {
  // Si hay un comando entrante desde Python...
  if (Serial.available() > 0) {
    // ...leer el comando
    char comando = Serial.read();

    // --- Lógica de Control ---
    switch (comando) {
      
      case 'L': // Toggle Living
        estadoLiving = !estadoLiving; // Invierte el estado
        digitalWrite(ledLiving, estadoLiving ? HIGH : LOW);
        break;
        
      case 'K': // Toggle Cocina (Kitchen)
        estadoCocina = !estadoCocina;
        digitalWrite(ledCocina, estadoCocina ? HIGH : LOW);
        break;
        
      case 'B': // Toggle Dormitorio (Bedroom)
        estadoDormitorio = !estadoDormitorio;
        digitalWrite(ledDormitorio, estadoDormitorio ? HIGH : LOW);
        break;
        
      case 'S': // Toggle Servo (Portón)
        estadoPorton = !estadoPorton;
        if (estadoPorton) {
          portonServo.write(anguloAbierto);
        } else {
          portonServo.write(anguloCerrado);
        }
        break;
    }
  }
}
