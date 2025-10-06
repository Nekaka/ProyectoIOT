import cv2
import face_recognition
import mediapipe as mp
import serial
import time

try:
    arduino = serial.Serial(port='COM8', baudrate=9600, timeout=.1)
    time.sleep(2)
    print("Conexión con Arduino establecida")
except serial.SerialException as e:
    print(f"Error al conectar con Arduino: {e}")
    print("El programa continuara sin el control del LED.")
    arduino = None

led_state = 'OFF'

mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=2,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)
mp_drawing = mp.solutions.drawing_utils

try:
    imagen_referencia = face_recognition.load_image_file("foto.jpg") #Cambiar despues por una foto de la persona
    codificacion_referencia = face_recognition.face_encodings(imagen_referencia)[0]
    codificaciones_conocidas = [codificacion_referencia]
    nombres_conocidos = ["Inserte nombre"] #Cambiar luego por el nombre de la persona
except FileNotFoundError:
    print("Advertencia: No se encontro ninguna imagen, el reconocimiento facial estara desactivado")
    codificaciones_conocidas = []
    nombres_conocidos = [0]

# --- 3. FUNCIONES PARA EL RECONOCIMIENTO DE GESTOS ---
def is_finger_extended(finger_tip, finger_pip, finger_mcp):
    """Comprueba si un dedo está extendido comparando las coordenadas Y."""
    # En coordenadas de imagen, un valor Y más pequeño significa que está más arriba.
    return finger_tip.y < finger_pip.y and finger_pip.y < finger_mcp.y

def recognize_gesture(hand_landmarks):
    """Identifica un gesto basado en los dedos extendidos y devuelve un nombre y un valor."""
    landmarks = hand_landmarks.landmark
    
    # Comprobar si los dedos están extendidos
    is_thumb_extended = landmarks[mp_hands.HandLandmark.THUMB_TIP].x < landmarks[mp_hands.HandLandmark.THUMB_IP].x
    is_index_extended = is_finger_extended(landmarks[mp_hands.HandLandmark.INDEX_FINGER_TIP], landmarks[mp_hands.HandLandmark.INDEX_FINGER_PIP], landmarks[mp_hands.HandLandmark.INDEX_FINGER_MCP])
    is_middle_extended = is_finger_extended(landmarks[mp_hands.HandLandmark.MIDDLE_FINGER_TIP], landmarks[mp_hands.HandLandmark.MIDDLE_FINGER_PIP], landmarks[mp_hands.HandLandmark.MIDDLE_FINGER_MCP])
    is_ring_extended = is_finger_extended(landmarks[mp_hands.HandLandmark.RING_FINGER_TIP], landmarks[mp_hands.HandLandmark.RING_FINGER_PIP], landmarks[mp_hands.HandLandmark.RING_FINGER_MCP])
    is_pinky_extended = is_finger_extended(landmarks[mp_hands.HandLandmark.PINKY_TIP], landmarks[mp_hands.HandLandmark.PINKY_PIP], landmarks[mp_hands.HandLandmark.PINKY_MCP])

    # Lógica para identificar el gesto
    if all([is_thumb_extended, is_index_extended, is_middle_extended, is_ring_extended, is_pinky_extended]):
        return "Cinco", 5
    elif not any([is_index_extended, is_middle_extended, is_ring_extended, is_pinky_extended]):
        return "Puño", 0
    
    return "No reconocido", -1

# --- 4. BUCLE PRINCIPAL DE CAPTURA DE VIDEO Y PROCESAMIENTO ---
webcam = cv2.VideoCapture(0)
print("Iniciando cámara... Presiona 'q' para salir.")

while True:
    ret, frame = webcam.read()
    if not ret:
        print("Error al capturar el fotograma.")
        break
    
    # Para una vista de espejo, volteamos el fotograma
    frame = cv2.flip(frame, 1)
    
    # Convertir a RGB para el procesamiento
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # Procesamiento de manos y gestos
    results_hands = hands.process(rgb_frame)
    if results_hands.multi_hand_landmarks:
        for hand_landmarks in results_hands.multi_hand_landmarks:
            mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
            gesture_name, gesture_value = recognize_gesture(hand_landmarks)
            
            # Lógica para enviar comandos al Arduino
            if arduino is not None:
                if gesture_value == 5 and led_state == 'OFF':
                    arduino.write(b'H') # Enviar 'H' para encender (High)
                    led_state = 'ON'
                    print("Comando enviado: ENCENDER LED")
                elif gesture_value == 0 and led_state == 'ON':
                    arduino.write(b'L') # Enviar 'L' para apagar (Low)
                    led_state = 'OFF'
                    print("Comando enviado: APAGAR LED")

            # Mostrar información del gesto en pantalla
            wrist = hand_landmarks.landmark[mp_hands.HandLandmark.WRIST]
            cv2.putText(frame, f"Gesto: {gesture_name}", (int(wrist.x * frame.shape[1]), int(wrist.y * frame.shape[0]) - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    # Procesamiento de rostros (si las imágenes se cargaron)
    if codificaciones_conocidas:
        ubicaciones_rostros = face_recognition.face_locations(rgb_frame)
        codificaciones_rostros = face_recognition.face_encodings(rgb_frame, ubicaciones_rostros)
        for (top, right, bottom, left), face_encoding in zip(ubicaciones_rostros, codificaciones_rostros):
            matches = face_recognition.compare_faces(codificaciones_conocidas, face_encoding)
            nombre = "Desconocido"
            if True in matches:
                nombre = nombres_conocidos[matches.index(True)]
            cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
            cv2.putText(frame, nombre, (left, bottom + 20), cv2.FONT_HERSHEY_DUPLEX, 0.6, (255, 255, 255), 1)

    # Mostrar estado del LED en pantalla
    cv2.putText(frame, f"Estado LED: {led_state}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
    
    # Mostrar el fotograma resultante
    cv2.imshow('Control con Vision Artificial', frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# --- 5. LIBERAR RECURSOS ---
print("Cerrando programa...")
webcam.release()
cv2.destroyAllWindows()
hands.close()
if arduino is not None:
    # Apagar el LED antes de cerrar por seguridad
    if led_state == 'ON':
        arduino.write(b'L')
    arduino.close()
    print("Conexión con Arduino cerrada.")