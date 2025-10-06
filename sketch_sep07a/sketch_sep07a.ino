const int ledPin = 13;

void setup() {
  // Inicializa la comunicación serial a una velocidad de 9600 baudios.
  // Esta velocidad debe ser la misma que la configurada en el script de Python.
  Serial.begin(9600);
  
  // Configura el pin del LED como una salida digital.
  pinMode(ledPin, OUTPUT);
  
  // Opcional: Apagar el LED al iniciar para asegurar un estado conocido.
  digitalWrite(ledPin, LOW);
}

void loop() {
  // Comprueba si hay datos disponibles en el búfer de entrada del puerto serie.
  if (Serial.available() > 0) {
    
    // Lee el primer byte (carácter) disponible.
    char comando = Serial.read();
    
    // Compara el comando recibido y actúa en consecuencia.
    if (comando == 'H') {
      // Si el comando es 'H' (High), enciende el LED.
      digitalWrite(ledPin, HIGH);
    } 
    else if (comando == 'L') {
      // Si el comando es 'L' (Low), apaga el LED.
      digitalWrite(ledPin, LOW);
    }
    // Si se recibe cualquier otro carácter, se ignora.
  }
}
