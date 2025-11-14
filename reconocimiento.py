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
import logging

# --- 0. CONFIGURACIÓN INICIAL ---
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
logging.getLogger('tensorflow').setLevel(logging.ERROR)

# --- 1. CONFIGURACIÓN DE FIREBASE ---
try:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://automatizacion-gestos-default-rtdb.firebaseio.com/'
    })
    ref_logs = db.reference('logs')
    ref_status = db.reference('status')
    print("✅ Conectado a Firebase")
except Exception as e:
    print(f"❌ Error al conectar con Firebase: {e}")
    ref_logs, ref_status = None, None

# --- 2. CONFIGURACIÓN DE ARDUINO ---
try:
    # Asegúrate de que COM5 sea el puerto de tu NUEVO Arduino
    arduino = serial.Serial(port='COM5', baudrate=9600, timeout=.1) 
    time.sleep(2)
    print("✅ Conexión con Arduino establecida.")
except serial.SerialException as e:
    print(f"❌ Error al conectar con Arduino: {e}")
    arduino = None

# --- 3. CONFIGURACIÓN DE MEDIAPIPE (Detector de Manos y Rostros) ---
print("Cargando modelos de MediaPipe...")
mp_solutions = mp.solutions
mp_hands = mp_solutions.hands
mp_drawing = mp_solutions.drawing_utils
mp_face_detection = mp_solutions.face_detection

hands = mp_hands.Hands(min_detection_confidence=0.7) 
face_detector = mp_face_detection.FaceDetection(min_detection_confidence=0.5)
print("Modelos de MediaPipe cargados.")

# --- 4. CARGA AUTOMÁTICA DE ROSTROS (face_recognition) ---
RUTA_CARPETA_ROSTROS = "Fotos_Rostros"
codificaciones_conocidas = []
nombres_conocidos = []
print("Iniciando carga de rostros conocidos...")
if not os.path.exists(RUTA_CARPETA_ROSTROS):
    print(f"❌ ERROR: No se encontró la carpeta '{RUTA_CARPETA_ROSTROS}'.")
else:
    for nombre_archivo in os.listdir(RUTA_CARPETA_ROSTROS):
        if nombre_archivo.endswith(".jpg") or nombre_archivo.endswith(".png"):
            ruta_imagen = os.path.join(RUTA_CARPETA_ROSTROS, nombre_archivo)
            try:
                pil_image = Image.open(ruta_imagen)
                rgb_image = pil_image.convert('RGB')
                imagen_conocida = np.array(rgb_image)
                # Usamos 'cnn' al cargar (lento pero solo se hace una vez)
                codificacion_rostro = face_recognition.face_encodings(imagen_conocida, model="cnn")[0]
                nombre_persona = os.path.splitext(nombre_archivo)[0]
                codificaciones_conocidas.append(codificacion_rostro)
                nombres_conocidos.append(nombre_persona)
                print(f"  > Rostro de '{nombre_persona}' cargado.")
            except Exception as e:
                print(f"⚠️ Error procesando {nombre_archivo}: {e}")
print(f"Carga finalizada. {len(nombres_conocidos)} rostros cargados.")

# --- 5. ESTADOS Y VARIABLES GLOBALES ---
led_living_state = "OFF"
led_cocina_state = "OFF"
led_dormitorio_state = "OFF"
porton_state = "CERRADO"
last_action_time = 0
last_unknown_sighting_time = 0
COOLDOWN_SECONDS = 5
COOLDOWN_UNKNOWN = 10
PROC_WIDTH = 640 # Ancho de procesamiento

# --- 6. FUNCIÓN DE RECONOCIMIENTO DE GESTOS (Sin cambios) ---
def recognize_gesture(hand_landmarks, handedness):
    # ... (Tu código de gestos es perfecto) ...
    landmarks = hand_landmarks.landmark
    is_index_extended = landmarks[mp_hands.HandLandmark.INDEX_FINGER_TIP].y < landmarks[mp_hands.HandLandmark.INDEX_FINGER_MCP].y
    is_middle_extended = landmarks[mp_hands.HandLandmark.MIDDLE_FINGER_TIP].y < landmarks[mp_hands.HandLandmark.MIDDLE_FINGER_MCP].y
    is_ring_extended = landmarks[mp_hands.HandLandmark.RING_FINGER_TIP].y < landmarks[mp_hands.HandLandmark.RING_FINGER_MCP].y
    is_pinky_extended = landmarks[mp_hands.HandLandmark.PINKY_TIP].y < landmarks[mp_hands.HandLandmark.PINKY_MCP].y
    if handedness == 'Right':
        is_thumb_extended = landmarks[mp_hands.HandLandmark.THUMB_TIP].x < landmarks[mp_hands.HandLandmark.THUMB_IP].x
    else: # 'Left'
        is_thumb_extended = landmarks[mp_hands.HandLandmark.THUMB_TIP].x > landmarks[mp_hands.HandLandmark.THUMB_IP].x
    if is_index_extended and not is_middle_extended and not is_ring_extended and not is_pinky_extended: return "Uno"
    if is_index_extended and is_middle_extended and not is_ring_extended and not is_pinky_extended: return "Dos"
    if is_index_extended and is_middle_extended and is_ring_extended and not is_pinky_extended: return "Tres"
    if all([is_thumb_extended, is_index_extended, is_middle_extended, is_ring_extended, is_pinky_extended]): return "Cinco"
    if not any([is_index_extended, is_middle_extended, is_ring_extended, is_pinky_extended]): return "Puño"
    return "No reconocido"


# --- 7. FUNCIÓN PARA ENVIAR LOG A FIREBASE (Sin cambios) ---
def log_event(type, user, action, timestamp):
    print(f"LOG: {user} - {action}")
    if ref_logs:
        ref_logs.push({
            'type': type, 'user': user, 'action': action, 'timestamp': timestamp
        })

# --- 8. FUNCIÓN SEGURA PARA ESCRIBIR EN ARDUINO ---
def write_to_arduino(comando_byte):
    global arduino
    try:
        if arduino:
            arduino.write(comando_byte)
            return True
    except Exception as e:
        print(f"❌ ERROR DE ARDUINO (al escribir '{comando_byte}'): {e}. Desconectando.")
        arduino = None
        return False

# --- 9. BUCLE PRINCIPAL (¡LA VERSIÓN OPTIMIZADA!) ---
webcam = cv2.VideoCapture(0)
print("Iniciando cámara... Presiona 'q' para salir.")
frame_counter = 0
persona_autorizada = False
usuario_actual = "Nadie"
ubicaciones_rostros_actuales = []
nombres_rostros_actuales = []
gestos_actuales = []

if ref_status:
    ref_status.set({
        'currentUser': usuario_actual, 'isAuthorized': persona_autorizada,
        'ledLiving': led_living_state, 'ledCocina': led_cocina_state,
        'ledDormitorio': led_dormitorio_state, 'porton': porton_state
    })

while True:
    ret, frame = webcam.read()
    if not ret: 
        print("Error: No se puede leer el frame.")
        break
    frame = cv2.flip(frame, 1)

    # Redimensión
    h, w, _ = frame.shape
    ratio = PROC_WIDTH / float(w)
    PROC_HEIGHT = int(h * ratio)
    frame_pequeno = cv2.resize(frame, (PROC_WIDTH, PROC_HEIGHT))
    
    rgb_frame = None
    current_time = time.time()
    frame_counter += 1

    # --- CICLO DE TRABAJO DE 4 FRAMES ---

    # --- A. PROCESAMIENTO DE MANOS (Frame 1) ---
    if frame_counter % 4 == 1:
        gestos_actuales = [] 
        if persona_autorizada: 
            if rgb_frame is None: rgb_frame = cv2.cvtColor(frame_pequeno, cv2.COLOR_BGR2RGB)
            results_hands = hands.process(rgb_frame)
            
            if results_hands.multi_hand_landmarks:
                for idx, hand_landmarks in enumerate(results_hands.multi_hand_landmarks):
                    # ARREGLADO: Dibujamos en el frame_pequeno
                    mp_drawing.draw_landmarks(frame_pequeno, hand_landmarks, mp_hands.HAND_CONNECTIONS)
                    
                    handedness_obj = results_hands.multi_handedness[idx]
                    handedness_label = handedness_obj.classification[0].label
                    gesture_name = recognize_gesture(hand_landmarks, handedness_label)
                    
                    if (current_time - last_action_time) > COOLDOWN_SECONDS:
                        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                        # Mano Derecha (Luces)
                        if handedness_label == 'Right':
                            if gesture_name == "Uno":
                                led_living_state = "ON" if led_living_state == "OFF" else "OFF"
                                log_event('gesture', usuario_actual, f"Luz Living -> {led_living_state}", timestamp)
                                write_to_arduino(b'L')
                                last_action_time = current_time
                            elif gesture_name == "Dos":
                                led_cocina_state = "ON" if led_cocina_state == "OFF" else "OFF"
                                log_event('gesture', usuario_actual, f"Luz Cocina -> {led_cocina_state}", timestamp)
                                write_to_arduino(b'K')
                                last_action_time = current_time
                            elif gesture_name == "Tres":
                                led_dormitorio_state = "ON" if led_dormitorio_state == "OFF" else "OFF"
                                log_event('gesture', usuario_actual, f"Luz Dormitorio -> {led_dormitorio_state}", timestamp)
                                write_to_arduino(b'B')
                                last_action_time = current_time
                        # Mano Izquierda (Portón)
                        elif handedness_label == 'Left':
                            if gesture_name == "Cinco":
                                porton_state = "ABIERTO" if porton_state == "CERRADO" else "CERRADO"
                                log_event('gesture', usuario_actual, f"Portón -> {porton_state}", timestamp)
                                write_to_arduino(b'S')
                                last_action_time = current_time
                            # --- BLOQUE NUEVO PARA "PUÑO IZQUIERDO" ---
                            elif gesture_name == "Puño":
                                print("¡Gesto de Apagado Total detectado!")
                                action_taken = False # Para saber si registramos el evento
                                
                                # Apagar Living SI ESTÁ encendido
                                if led_living_state == "ON":
                                    led_living_state = "OFF"
                                    write_to_arduino(b'L') # Envía el toggle para apagar
                                    action_taken = True
                                
                                # Apagar Cocina SI ESTÁ encendida
                                if led_cocina_state == "ON":
                                    led_cocina_state = "OFF"
                                    write_to_arduino(b'K') # Envía el toggle para apagar
                                    action_taken = True
                                
                                # Apagar Dormitorio SI ESTÁ encendido
                                if led_dormitorio_state == "ON":
                                    led_dormitorio_state = "OFF"
                                    write_to_arduino(b'B') # Envía el toggle para apagar
                                    action_taken = True

                                # Solo registramos y reiniciamos el cooldown si se apagó algo
                                if action_taken:
                                    log_event('gesture', usuario_actual, "Apagado Total de Luces", timestamp)
                                    last_action_time = current_time
                                else:
                                    # Si no se hizo nada (luces ya estaban apagadas),
                                    # no reiniciamos el cooldown.
                                    pass 
                            # --- FIN DEL BLOQUE NUEVO ---
                    
                    wrist = hand_landmarks.landmark[mp_hands.HandLandmark.WRIST]
                    coords = (int(wrist.x * PROC_WIDTH), int(wrist.y * PROC_HEIGHT))
                    gestos_actuales.append((handedness_label, gesture_name, coords))

    # --- B. PROCESAMIENTO DE ROSTROS (Frame 3) ---
    # (Usando el detector rápido de MediaPipe + el reconocedor de face_recognition)
    elif frame_counter % 4 == 3:
        ubicaciones_rostros_actuales = []
        nombres_rostros_actuales = []
        persona_autorizada = False
        usuario_actual = "Nadie"
        
        if rgb_frame is None: rgb_frame = cv2.cvtColor(frame_pequeno, cv2.COLOR_BGR2RGB)
        
        # 1. DETECCIÓN RÁPIDA con MediaPipe
        results_faces = face_detector.process(rgb_frame)
        
        face_locations_hog = [] 
        if results_faces.detections:
            for detection in results_faces.detections:
                bboxC = detection.location_data.relative_bounding_box
                ih, iw = frame_pequeno.shape[:2]
                left = int(bboxC.xmin * iw); top = int(bboxC.ymin * ih)
                right = int((bboxC.xmin + bboxC.width) * iw); bottom = int((bboxC.ymin + bboxC.height) * ih)
                top, right, bottom, left = max(0, top), min(iw - 1, right), min(ih - 1, bottom), max(0, left)
                face_locations_hog.append((top, right, bottom, left)) # Formato (t,r,b,l)

        if face_locations_hog:
            # 2. RECONOCIMIENTO RÁPIDO con face_recognition
            # (Nos saltamos el detector HOG y solo codificamos)
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
                'currentUser': usuario_actual, 'isAuthorized': persona_autorizada,
                'ledLiving': led_living_state, 'ledCocina': led_cocina_state,
                'ledDormitorio': led_dormitorio_state, 'porton': porton_state
            })

    # --- C. FRAMES DE DESCANSO (Frames 0, 2) ---
    # No se hace nada, solo se dibuja
    
    # --- 3. SECCIÓN DE DIBUJO (En CADA frame) ---
    # ARREGLADO: Dibujamos en 'frame_pequeno'
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

    # --- 4. TEXTO DE ESTADO ---
    if persona_autorizada:
        estado_texto = "SISTEMA: AUTORIZADO"
        color_estado = (0, 255, 0)
    else:
        estado_texto = "SISTEMA: BLOQUEADO"
        color_estado = (0, 0, 255)
    
    # ARREGLADO: Dibujamos texto en 'frame_pequeno'
    cv2.putText(frame_pequeno, f"Living: {led_living_state}", (5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
    cv2.putText(frame_pequeno, f"Cocina: {led_cocina_state}", (5, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
    cv2.putText(frame_pequeno, f"Dormitorio: {led_dormitorio_state}", (5, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
    cv2.putText(frame_pequeno, f"Porton: {porton_state}", (5, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
    cv2.putText(frame_pequeno, estado_texto, (5, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_estado, 2)
    
    # ARREGLADO: Mostramos 'frame_pequeno' para máxima fluidez
    cv2.imshow('Control con Vision Artificial', frame_pequeno)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# --- 10. LIBERAR RECURSOS ---
print("Cerrando programa...")
if ref_status:
    ref_status.set({'currentUser': 'Nadie', 'isAuthorized': False, 'ledLiving': 'OFF', 'ledCocina': 'OFF', 'ledDormitorio': 'OFF', 'porton': 'CERRADO'})
webcam.release()
cv2.destroyAllWindows()
hands.close()
try:
    if arduino:
        arduino.close()
        print("Conexión con Arduino cerrada.")
except Exception as e:
    print(f"Error al cerrar el puerto de Arduino: {e}")

print("Programa finalizado.")