import cv2
import face_recognition
import mediapipe as mp
import serial
import time
import os
from PIL import Image
import numpy as np
import firebase_admin
from firebase_admin import credentials, db

# --- CONFIGURACIÓN DE FIREBASE ---
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://automatizacion-gestos-default-rtdb.firebaseio.com/'
})
ref_logs = db.reference('logs')
ref_status = db.reference('status')
print("Conectado a Firebase")

# --- CONFIGURACIÓN DE ARDUINO ---
try:
    # !!! CAMBIA 'COM3' por tu puerto
    arduino = serial.Serial(port='COM3', baudrate=9600, timeout=.1) 
    time.sleep(2)
    print("Conexión con Arduino establecida.")
except serial.SerialException as e:
    print(f"Error al conectar con Arduino: {e}")
    arduino = None

# --- CONFIGURACIÓN DE MEDIAPIPE Y ESTADOS ---
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=2,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)
mp_drawing = mp.solutions.drawing_utils

# Variables de estado
led_living_state = "OFF"
led_cocina_state = "OFF"
led_dormitorio_state = "OFF"
porton_state = "CERRADO"

# Variables de Cooldown
last_action_time = 0
last_unknown_sighting_time = 0
COOLDOWN_SECONDS = 5
COOLDOWN_UNKNOWN = 10

# --- CARGA AUTOMÁTICA DE ROSTROS ---
RUTA_CARPETA_ROSTROS = "Fotos_Rostros"
codificaciones_conocidas = []
nombres_conocidos = []
print("Iniciando carga de rostros conocidos...")
if not os.path.exists(RUTA_CARPETA_ROSTROS):
    print(f"ERROR: No se encontró la carpeta '{RUTA_CARPETA_ROSTROS}'.")
else:
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
                print(f"  > Rostro de '{nombre_persona}' cargado.")
            except Exception as e:
                print(f"Error procesando {nombre_archivo}: {e}")
print(f"Carga finalizada. {len(nombres_conocidos)} rostros cargados.")

# --- FUNCIÓN DE RECONOCIMIENTO DE GESTOS ---
def recognize_gesture(hand_landmarks, handedness):
    landmarks = hand_landmarks.landmark
    
    # Lógica para los 4 dedos
    is_index_extended = landmarks[mp_hands.HandLandmark.INDEX_FINGER_TIP].y < landmarks[mp_hands.HandLandmark.INDEX_FINGER_MCP].y
    is_middle_extended = landmarks[mp_hands.HandLandmark.MIDDLE_FINGER_TIP].y < landmarks[mp_hands.HandLandmark.MIDDLE_FINGER_MCP].y
    is_ring_extended = landmarks[mp_hands.HandLandmark.RING_FINGER_TIP].y < landmarks[mp_hands.HandLandmark.RING_FINGER_MCP].y
    is_pinky_extended = landmarks[mp_hands.HandLandmark.PINKY_TIP].y < landmarks[mp_hands.HandLandmark.PINKY_MCP].y

    # Lógica para el pulgar (depende de la mano)
    if handedness == 'Right':
        is_thumb_extended = landmarks[mp_hands.HandLandmark.THUMB_TIP].x < landmarks[mp_hands.HandLandmark.THUMB_IP].x
    else: # 'Left'
        is_thumb_extended = landmarks[mp_hands.HandLandmark.THUMB_TIP].x > landmarks[mp_hands.HandLandmark.THUMB_IP].x
    
    # --- Lógica de Gestos Específicos ---
    if is_index_extended and not is_middle_extended and not is_ring_extended and not is_pinky_extended:
        return "Uno"
    if is_index_extended and is_middle_extended and not is_ring_extended and not is_pinky_extended:
        return "Dos"
    if is_index_extended and is_middle_extended and is_ring_extended and not is_pinky_extended:
        return "Tres"
    if all([is_thumb_extended, is_index_extended, is_middle_extended, is_ring_extended, is_pinky_extended]):
        return "Cinco"
    
    return "No reconocido"

# --- 6. FUNCIÓN PARA ENVIAR LOG A FIREBASE ---
def log_event(type, user, action, timestamp):
    print(f"LOG: {user} - {action}")
    ref_logs.push({
        'type': type,
        'user': user,
        'action': action,
        'timestamp': timestamp
    })

# --- BUCLE PRINCIPAL ---
webcam = cv2.VideoCapture(0)
print("Iniciando cámara... Presiona 'q' para salir.")

frame_counter = 0
FRAME_SKIP_FACE = 3
FRAME_SKIP_HANDS = 2
persona_autorizada = False
usuario_actual = "Nadie"

ubicaciones_rostros_actuales = []
nombres_rostros_actuales = []
gestos_actuales = []

# Estado inicial en Firebase
ref_status.set({
    'currentUser': usuario_actual,
    'isAuthorized': persona_autorizada,
    'ledLiving': led_living_state,
    'ledCocina': led_cocina_state,
    'ledDormitorio': led_dormitorio_state,
    'porton': porton_state
})

while True:
    ret, frame = webcam.read()
    if not ret: break
    frame = cv2.flip(frame, 1)
    frame_pequeno = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
    rgb_frame = cv2.cvtColor(frame_pequeno, cv2.COLOR_BGR2RGB)
    
    current_time = time.time()
    frame_counter += 1

    # --- PROCESAMIENTO DE ROSTROS ---
    if frame_counter % FRAME_SKIP_FACE == 0:
        ubicaciones_rostros_actuales = []
        nombres_rostros_actuales = []

        persona_autorizada = False
        usuario_actual = "Nadie"
        
        locations = face_recognition.face_locations(rgb_frame, model="hog")
        if locations:
            encodings = face_recognition.face_encodings(rgb_frame, locations)
            for face_encoding in encodings:
                coincidencias = face_recognition.compare_faces(codificaciones_conocidas, face_encoding)
                nombre = "Desconocido"
                
                if True in coincidencias:
                    nombre = nombres_conocidos[coincidencias.index(True)]
                    if nombre != "Desconocido":
                        persona_autorizada = True
                        usuario_actual = nombre
                else:
                    if (current_time - last_unknown_sighting_time) > COOLDOWN_UNKNOWN:
                        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                        log_event('unknown_sighting', 'Nadie', 'Persona desconocida detectada', timestamp)
                        last_unknown_sighting_time = current_time

                nombres_rostros_actuales.append(nombre)

            for (top, right, bottom, left) in locations:
                 ubicaciones_rostros_actuales.append((top*2, right*2, bottom*2, left*2))
        
        # Actualizar estado en Firebase (se hace aquí para que sea constante)
        ref_status.set({
            'currentUser': usuario_actual,
            'isAuthorized': persona_autorizada,
            'ledLiving': led_living_state,
            'ledCocina': led_cocina_state,
            'ledDormitorio': led_dormitorio_state,
            'porton': porton_state
        })

    # --- PROCESAMIENTO DE MANOS (SOLO SI ESTÁ AUTORIZADO) ---
    if frame_counter % FRAME_SKIP_HANDS == 0:
        # Siempre borramos los gestos anteriores para que no se queden "pegados"
        gestos_actuales = []

        if persona_autorizada:
            results_hands = hands.process(rgb_frame)
            if results_hands.multi_hand_landmarks:
                for idx, hand_landmarks in enumerate(results_hands.multi_hand_landmarks):
                    mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
                    handedness_obj = results_hands.multi_handedness[idx]
                    handedness_label = handedness_obj.classification[0].label
                    gesture_name = recognize_gesture(hand_landmarks, handedness_label)
                    
                    # Comprobar si ha pasado el cooldown
                    if (current_time - last_action_time) > COOLDOWN_SECONDS:
                        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                        
                        # --- LÓGICA DE MANO DERECHA ---
                        if handedness_label == 'Right':
                            if gesture_name == "Uno":
                                led_living_state = "ON" if led_living_state == "OFF" else "OFF"
                                log_event('gesture', usuario_actual, f"Luz Living -> {led_living_state}", timestamp)
                                if arduino: arduino.write(b'L')
                                last_action_time = current_time
                                
                            elif gesture_name == "Dos":
                                led_cocina_state = "ON" if led_cocina_state == "OFF" else "OFF"
                                log_event('gesture', usuario_actual, f"Luz Cocina -> {led_cocina_state}", timestamp)
                                if arduino: arduino.write(b'K')
                                last_action_time = current_time

                            elif gesture_name == "Tres":
                                led_dormitorio_state = "ON" if led_dormitorio_state == "OFF" else "OFF"
                                log_event('gesture', usuario_actual, f"Luz Dormitorio -> {led_dormitorio_state}", timestamp)
                                if arduino: arduino.write(b'B')
                                last_action_time = current_time

                        # --- LÓGICA DE MANO IZQUIERDA ---
                        elif handedness_label == 'Left':
                            if gesture_name == "Cinco":
                                porton_state = "ABIERTO" if porton_state == "CERRADO" else "CERRADO"
                                log_event('gesture', usuario_actual, f"Portón -> {porton_state}", timestamp)
                                if arduino: arduino.write(b'S')
                                last_action_time = current_time

                wrist = hand_landmarks.landmark[mp_hands.HandLandmark.WRIST]
                coords = (int(wrist.x * frame_pequeno.shape[1]), int(wrist.y * frame_pequeno.shape[0]))
                # Re-escalamos por 2 para el frame grande
                gestos_actuales.append((handedness_label, gesture_name, (coords[0]*2, coords[1]*2)))

    # --- SECCIÓN DE DIBUJO ---
    # Dibujamos los rostros (sean conocidos o no)
    for (top, right, bottom, left), nombre in zip(ubicaciones_rostros_actuales, nombres_rostros_actuales):
        # Cambiamos el color del cuadro si es conocido
        color = (0, 255, 0) if nombre != "Desconocido" else (0, 0, 255) # Verde si es conocido, Rojo si no
        
        cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
        cv2.rectangle(frame, (left, bottom - 35), (right, bottom), color, cv2.FILLED)
        cv2.putText(frame, nombre, (left + 6, bottom - 6), cv2.FONT_HERSHEY_DUPLEX, 1.0, (255, 255, 255), 1)

    # Dibujamos los gestos (solo si la lista 'gestos_actuales' tiene algo)
    for (etiqueta_mano, nombre_gesto, (x, y)) in gestos_actuales:
        cv2.putText(frame, f"{etiqueta_mano} - {nombre_gesto}", (x - 50, y - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    if frame_counter > 100:
        frame_counter = 0

    # --- NUEVO TEXTO DE ESTADO ---
    # Añadimos un indicador visual del estado del sistema
    if persona_autorizada:
        estado_texto = "SISTEMA: AUTORIZADO"
        color_estado = (0, 255, 0) # Verde
    else:
        estado_texto = "SISTEMA: BLOQUEADO"
        color_estado = (0, 0, 255) # Rojo

    cv2.putText(frame, f"Estado LED Living: {led_living_state}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
    cv2.putText(frame, f"Estado LED Cocina: {led_cocina_state}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
    cv2.putText(frame, f"Estado LED Dormitorio: {led_dormitorio_state}", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
    cv2.putText(frame, f"Estado Porton: {porton_state}", (10, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
    cv2.putText(frame, estado_texto, (10, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color_estado, 2)
    
    cv2.imshow('Control con Vision Artificial', frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# --- LIBERAR RECURSOS ---
print("Cerrando programa...")
# Limpiar estado en Firebase
ref_status.set({'currentUser': 'Nadie', 'isAuthorized': False, 'ledLiving': 'OFF', 'ledCocina': 'OFF', 'ledDormitorio': 'OFF', 'porton': 'CERRADO'})
webcam.release()
cv2.destroyAllWindows()
hands.close()
if arduino:
    arduino.close()