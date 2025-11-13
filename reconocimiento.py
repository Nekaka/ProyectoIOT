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
try:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://automatizacion-gestos-default-rtdb.firebaseio.com/'
    })
    ref_logs = db.reference('logs')
    ref_status = db.reference('status')
    print("Conectado a Firebase")
except Exception as e:
    print(f"Error al conectar con Firebase: {e}")
    ref_logs = None
    ref_status = None

# --- CONFIGURACIÓN DE ARDUINO ---
try:
    # !!! CAMBIA 'COM3' por el puerto que este usando tu arduino
    arduino = serial.Serial(port='COM3', baudrate=9600, timeout=.1) 
    time.sleep(2)
    print("Conexión con Arduino establecida.")
except serial.SerialException as e:
    print(f"Error al conectar con Arduino: {e}")
    arduino = None

# --- CONFIGURACIÓN DE MEDIAPIPE Y ESTADOS ---
print("Cargando modelos de MediaPipe...")
mp_solutions = mp.solutions
mp_hands = mp_solutions.hands
mp_drawing = mp_solutions.drawing_utils
mp_face_detection = mp_solutions.face_detection

# Objeto para MANOS
hands = mp_hands.Hands(min_detection_confidence=0.7) 
# Objeto para ROSTROS
face_detector = mp_face_detection.FaceDetection(min_detection_confidence=0.5)
print("Modelos de MediaPipe cargados.")

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
                codificacion_rostro = face_recognition.face_encodings(imagen_conocida, model="cnn")[0]
                nombre_persona = os.path.splitext(nombre_archivo)[0]
                codificaciones_conocidas.append(codificacion_rostro)
                nombres_conocidos.append(nombre_persona)
                print(f"  > Rostro de '{nombre_persona}' cargado (usando CNN).")
            except Exception as e:
                print(f"Error procesando {nombre_archivo}: {e}")
print(f"Carga finalizada. {len(nombres_conocidos)} rostros cargados.")

# --- FUNCIÓN DE RECONOCIMIENTO DE GESTOS (ACTUALIZADA) ---
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

# --- FUNCIÓN PARA ENVIAR LOG A FIREBASE ---
def log_event(type, user, action, timestamp):
    print(f"LOG: {user} - {action}")
    if ref_logs:
        ref_logs.push({
            'type': type,
            'user': user,
            'action': action,
            'timestamp': timestamp
        })

# --- BUCLE PRINCIPAL ---
webcam = cv2.VideoCapture(0)
print("Iniciando cámara... Presiona 'q' para salir.")

PROC_WIDTH = 640

frame_counter = 0
persona_autorizada = False
usuario_actual = "Nadie"

ubicaciones_rostros_actuales = []
nombres_rostros_actuales = []
gestos_actuales = []

# Estado inicial en Firebase
if ref_status:
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
    if not ret: 
        print("Error: No se puede leer el frame de la cámara.")
        break
    frame = cv2.flip(frame, 1)

    # --- Lógica de Redimensión Fija ---
    h, w, _ = frame.shape
    ratio = PROC_WIDTH / float(w)
    PROC_HEIGHT = int(h * ratio)
    frame_pequeno = cv2.resize(frame, (PROC_WIDTH, PROC_HEIGHT))
    
    rgb_frame = None
    current_time = time.time()
    frame_counter += 1

    # --- CICLO DE TRABAJO DE 4 FRAMES ---

    # --- PROCESAMIENTO DE MANOS ---
    if frame_counter % 4 == 1:
        gestos_actuales = [] # Limpiamos gestos
        if persona_autorizada: 
            rgb_frame = cv2.cvtColor(frame_pequeno, cv2.COLOR_BGR2RGB)
            results_hands = hands.process(rgb_frame)
            
            if results_hands.multi_hand_landmarks:
                for idx, hand_landmarks in enumerate(results_hands.multi_hand_landmarks):
                    mp_drawing.draw_landmarks(frame_pequeno, hand_landmarks, mp_hands.HAND_CONNECTIONS)
                    
                    handedness_obj = results_hands.multi_handedness[idx]
                    handedness_label = handedness_obj.classification[0].label
                    gesture_name = recognize_gesture(hand_landmarks, handedness_label)
                    
                    if (current_time - last_action_time) > COOLDOWN_SECONDS:
                        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                        # --- Lógica de Mano Derecha ---
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
                        # --- Lógica de Mano Izquierda ---
                        elif handedness_label == 'Left':
                            if gesture_name == "Cinco":
                                porton_state = "ABIERTO" if porton_state == "CERRADO" else "CERRADO"
                                log_event('gesture', usuario_actual, f"Portón -> {porton_state}", timestamp)
                                if arduino: arduino.write(b'S')
                                last_action_time = current_time
                    
                    # Guardamos el gesto para dibujarlo en los frames de descanso
                    wrist = hand_landmarks.landmark[mp_hands.HandLandmark.WRIST]
                    coords = (int(wrist.x * PROC_WIDTH), int(wrist.y * PROC_HEIGHT))
                    gestos_actuales.append((handedness_label, gesture_name, coords))

    # --- PROCESAMIENTO DE ROSTROS ---
    elif frame_counter % 4 == 3:
        ubicaciones_rostros_actuales = []
        nombres_rostros_actuales = []
        persona_autorizada = False
        usuario_actual = "Nadie"
        
        rgb_frame = cv2.cvtColor(frame_pequeno, cv2.COLOR_BGR2RGB)
        results_faces = face_detector.process(rgb_frame)
        
        face_locations_hog = [] 
        if results_faces.detections:
            for detection in results_faces.detections:
                bboxC = detection.location_data.relative_bounding_box
                ih, iw = frame_pequeno.shape[:2]
                left = int(bboxC.xmin * iw); top = int(bboxC.ymin * ih)
                right = int((bboxC.xmin + bboxC.width) * iw); bottom = int((bboxC.ymin + bboxC.height) * ih)
                top, right, bottom, left = max(0, top), min(iw - 1, right), min(ih - 1, bottom), max(0, left)
                face_locations_hog.append((top, right, bottom, left))

        if face_locations_hog:
            encodings = face_recognition.face_encodings(rgb_frame, face_locations_hog)
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
            
            ubicaciones_rostros_actuales = face_locations_hog
        
        # Actualizar estado en Firebase
        if ref_status:
            ref_status.set({
                'currentUser': usuario_actual,
                'isAuthorized': persona_autorizada,
                'ledLiving': led_living_state,
                'ledCocina': led_cocina_state,
                'ledDormitorio': led_dormitorio_state,
                'porton': porton_state
            })

    # --- SECCIÓN DE DIBUJO ---
    
    for (top, right, bottom, left), nombre in zip(ubicaciones_rostros_actuales, nombres_rostros_actuales):
        color = (0, 255, 0) if nombre != "Desconocido" else (0, 0, 255)
        cv2.rectangle(frame_pequeno, (left, top), (right, bottom), color, 2)
        cv2.rectangle(frame_pequeno, (left, bottom - 25), (right, bottom), color, cv2.FILLED)
        cv2.putText(frame_pequeno, nombre, (left + 6, bottom - 6), cv2.FONT_HERSHEY_DUPLEX, 0.7, (255, 255, 255), 1)

    for (etiqueta_mano, nombre_gesto, (x, y)) in gestos_actuales:
        cv2.putText(frame_pequeno, f"{etiqueta_mano} - {nombre_gesto}", (x - 40, y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

    if frame_counter > 100:
        frame_counter = 0

    # --- TEXTO DE ESTADO ---
    if persona_autorizada:
        estado_texto = "SISTEMA: AUTORIZADO"
        color_estado = (0, 255, 0) # Verde
    else:
        estado_texto = "SISTEMA: BLOQUADO"
        color_estado = (0, 0, 255) # Rojo

    cv2.putText(frame_pequeno, f"Living: {led_living_state}", (5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
    cv2.putText(frame_pequeno, f"Cocina: {led_cocina_state}", (5, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
    cv2.putText(frame_pequeno, f"Dormitorio: {led_dormitorio_state}", (5, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
    cv2.putText(frame_pequeno, f"Porton: {porton_state}", (5, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
    cv2.putText(frame_pequeno, estado_texto, (5, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_estado, 2)

    cv2.imshow('Control con Vision Artificial', frame_pequeno)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# --- LIBERAR RECURSOS ---
print("Cerrando programa...")
# Limpiar estado en Firebase
if ref_status:
    ref_status.set({'currentUser': 'Nadie', 'isAuthorized': False, 'ledLiving': 'OFF', 'ledCocina': 'OFF', 'ledDormitorio': 'OFF', 'porton': 'CERRADO'})
webcam.release()
cv2.destroyAllWindows()
hands.close()
if arduino:
    arduino.close()
print("Programa finalizado.")