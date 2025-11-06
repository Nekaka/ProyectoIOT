import cv2
import face_recognition
import mediapipe as mp
import serial
import time
import os
from PIL import Image  # Para manejar la conversión de imágenes
import numpy as np     # Para convertir la imagen a un formato que face_recognition entienda

try:
    arduino = serial.Serial(port='COM8', baudrate=9600, timeout=.1)
    time.sleep(2)
    print("Conexión con Arduino establecida")
except serial.SerialException as e:
    print(f"Error al conectar con Arduino: {e}")
    print("El programa continuara sin el control del LED.")
    arduino = None

led_state = 'OFF'
last_action_time = 0  # Tiempo en que se realizó la última acción
COOLDOWN_SECONDS = 5  # 5 segundos de enfriamiento entre acciones

mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=2,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)
mp_drawing = mp.solutions.drawing_utils

# --- 2. NUEVA SECCIÓN: CARGA AUTOMÁTICA DE ROSTROS ---
# Define la ruta a la carpeta que contiene las imágenes de los rostros
RUTA_CARPETA_ROSTROS = "Fotos_Rostros"

codificaciones_conocidas = []
nombres_conocidos = []

print("Iniciando carga de rostros conocidos...")

for nombre_archivo in os.listdir(RUTA_CARPETA_ROSTROS):

    if nombre_archivo.endswith(".jpg") or nombre_archivo.endswith(".png"):

        ruta_imagen = os.path.join(RUTA_CARPETA_ROSTROS, nombre_archivo)

        try:

            pil_image = Image.open(ruta_imagen)

            rgb_image = pil_image.convert('RGB')

            imagen_conocida = np.array(rgb_image)

            codificacion_rostro = face_recognition.face_encodings(imagen_conocida)[0]

            nombre_persona = os.path.splitext(nombre_archivo)[0]

            codificaciones_conocidas.append(codificacion_rostro)
            nombres_conocidos.append(nombre_persona)

            print(f" > Rostro de '{nombre_persona}' cargado correctamente.")
        except IndexError:
            print(f"Advertencia: No se pudo encontrar un rostro en {nombre_archivo}. Archivo omitido.")
        except Exception as e:
            print(f"Error procesando {nombre_archivo}: {e}")

print(f"Carga finalizada. {len(nombres_conocidos)} rostros cargados.")

# --- 3. FUNCIONES PARA EL RECONOCIMIENTO DE GESTOS ---
def is_finger_extended(finger_tip, finger_pip, finger_mcp):
    """Comprueba si un dedo está extendido comparando las coordenadas Y."""
    # En coordenadas de imagen, un valor Y más pequeño significa que está más arriba.
    return finger_tip.y < finger_pip.y and finger_pip.y < finger_mcp.y

def recognize_gesture(hand_landmarks, handedness):

    landmarks = hand_landmarks.landmark
    
    # La lógica para los dedos índice, medio, anular y meñique 
    is_index_extended = landmarks[mp_hands.HandLandmark.INDEX_FINGER_TIP].y < landmarks[mp_hands.HandLandmark.INDEX_FINGER_MCP].y
    is_middle_extended = landmarks[mp_hands.HandLandmark.MIDDLE_FINGER_TIP].y < landmarks[mp_hands.HandLandmark.MIDDLE_FINGER_MCP].y
    is_ring_extended = landmarks[mp_hands.HandLandmark.RING_FINGER_TIP].y < landmarks[mp_hands.HandLandmark.RING_FINGER_MCP].y
    is_pinky_extended = landmarks[mp_hands.HandLandmark.PINKY_TIP].y < landmarks[mp_hands.HandLandmark.PINKY_MCP].y

    # Si es la mano DERECHA, la punta del pulgar debe tener una X menor que la base.
    if handedness == 'Right':
        is_thumb_extended = landmarks[mp_hands.HandLandmark.THUMB_TIP].x < landmarks[mp_hands.HandLandmark.THUMB_IP].x
    # Si es la mano IZQUIERDA, la punta del pulgar debe tener una X MAYOR que la base.
    else: # 'Left'
        is_thumb_extended = landmarks[mp_hands.HandLandmark.THUMB_TIP].x > landmarks[mp_hands.HandLandmark.THUMB_IP].x
    
    # Declaración de los gestos a utilizar
    if all([is_thumb_extended, is_index_extended, is_middle_extended, is_ring_extended, is_pinky_extended]):
        return "Cinco"
    elif not any([is_index_extended, is_middle_extended, is_ring_extended, is_pinky_extended]):
        return "Puño"
    
    return "No reconocido"

# --- 4. BUCLE PRINCIPAL DE CAPTURA DE VIDEO Y PROCESAMIENTO ---
# Variables para el salto de frames
frame_counter = 0
FRAME_SKIP_FACE = 3  # <-- Reducido a 3. 'hog' es rápido.
FRAME_SKIP_HANDS = 2  # <-- Mantenido en 2.

ubicaciones_rostros_actuales = []
nombres_rostros_actuales = []
gestos_actuales = [] 

webcam = cv2.VideoCapture(0)
print("Iniciando cámara optimizada (Modo HOG)... Presiona 'q' para salir.")

while True:
    ret, frame = webcam.read()
    if not ret: 
        print("Error de cámara")
        break
    
    frame = cv2.flip(frame, 1)
    frame_pequeno = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
    rgb_frame = cv2.cvtColor(frame_pequeno, cv2.COLOR_BGR2RGB)

    frame_counter += 1

    # --- Procesamiento de Rostros (con 'hog', mucho más rápido) ---
    if frame_counter % FRAME_SKIP_FACE == 0:
        ubicaciones_rostros_actuales = []
        nombres_rostros_actuales = []
        
        locations = face_recognition.face_locations(rgb_frame, model="hog")
        
        if locations: # Si 'hog' encontró algo
            encodings = face_recognition.face_encodings(rgb_frame, locations)
            for face_encoding, (top, right, bottom, left) in zip(encodings, locations):
                coincidencias = face_recognition.compare_faces(codificaciones_conocidas, face_encoding)
                nombre = "Desconocido"
                if True in coincidencias:
                    nombre = nombres_conocidos[coincidencias.index(True)]
                
                ubicaciones_rostros_actuales.append((top*2, right*2, bottom*2, left*2))
                nombres_rostros_actuales.append(nombre)
        # Si 'hog' no encontró nada, las listas simplemente quedarán vacías (no hay error)

    # --- Procesamiento de Manos ---
    if frame_counter % FRAME_SKIP_HANDS == 0:
        gestos_actuales = []
        results_hands = hands.process(rgb_frame)
        
        if results_hands.multi_hand_landmarks:
            for idx, hand_landmarks in enumerate(results_hands.multi_hand_landmarks):
                handedness_obj = results_hands.multi_handedness[idx]
                handedness_label = handedness_obj.classification[0].label
                gesture_name = recognize_gesture(hand_landmarks, handedness_label)
                
                current_time = time.time()
                if gesture_name == "Cinco" and (current_time - last_action_time) > COOLDOWN_SECONDS:
                    # ... (lógica del LED) ...
                    if handedness_label == 'Left':
                        led_state = 'ON' if led_state == 'OFF' else 'OFF'
                        print(f"ACCIÓN (Izquierda): LED {led_state}")
                        last_action_time = current_time
                
                # ... (resto de la lógica de gestos y guardado) ...
                wrist = hand_landmarks.landmark[mp_hands.HandLandmark.WRIST]
                coords = (int(wrist.x * frame_pequeno.shape[1]), int(wrist.y * frame_pequeno.shape[0]))
                gestos_actuales.append((handedness_label, gesture_name, (coords[0]*2, coords[1]*2)))
                mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

    # --- SECCIÓN DE DIBUJO ---
    for (top, right, bottom, left), nombre in zip(ubicaciones_rostros_actuales, nombres_rostros_actuales):
        cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
        cv2.rectangle(frame, (left, bottom - 35), (right, bottom), (0, 255, 0), cv2.FILLED)
        cv2.putText(frame, nombre, (left + 6, bottom - 6), cv2.FONT_HERSHEY_DUPLEX, 1.0, (255, 255, 255), 1)

    for (handedness_label, gesture_name, (x, y)) in gestos_actuales:
        cv2.putText(frame, f"{handedness_label} - {gesture_name}", (x - 50, y - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    if frame_counter > 100:
        frame_counter = 0

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