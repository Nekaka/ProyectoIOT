import cv2
import face_recognition
import mediapipe as mp
import time
import os
import numpy as np
import firebase_admin
from firebase_admin import credentials, db
import logging
import threading
from PIL import Image

# --- CONFIGURACIÓN ---
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
logging.getLogger('tensorflow').setLevel(logging.ERROR)

try:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://automatizacion-gestos-default-rtdb.firebaseio.com/'
    })
    ref_status = db.reference('status')
    ref_commands = db.reference('commands')
    ref_devices = db.reference('devices')
    ref_logs = db.reference('logs')
    print("✅ Firebase OK")
except Exception as e:
    print(f"❌ Error: {e}"); exit()

# --- MEDIAPIPE ---
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
hands = mp_hands.Hands(min_detection_confidence=0.7) 

# --- VARIABLES ---
global_device_states = {}
gesture_map = {}
device_name_map = {}
device_type_map = {}
last_action_time = 0
COOLDOWN = 3

# --- CARGA ROSTROS ---
RUTA_CARPETA_ROSTROS = "Fotos_Rostros"
codificaciones_conocidas = []
nombres_conocidos = []
if os.path.exists(RUTA_CARPETA_ROSTROS):
    print("Cargando rostros...")
    for f in os.listdir(RUTA_CARPETA_ROSTROS):
        if f.endswith((".jpg", ".png")):
            try:
                img = np.array(Image.open(os.path.join(RUTA_CARPETA_ROSTROS, f)).convert('RGB'))
                enc = face_recognition.face_encodings(img)[0]
                codificaciones_conocidas.append(enc)
                nombres_conocidos.append(os.path.splitext(f)[0])
            except: pass
print(f"Rostros: {len(nombres_conocidos)}")

# --- FUNCIONES ---
def recognize_gesture(lm, handedness):
    fingers = []
    tips = [8, 12, 16, 20]
    if handedness == 'Right': fingers.append(lm.landmark[4].x < lm.landmark[3].x)
    else: fingers.append(lm.landmark[4].x > lm.landmark[3].x)
    for tip in tips: fingers.append(lm.landmark[tip].y < lm.landmark[tip-2].y)
    if all(fingers): return "Cinco"
    if not any(fingers): return "Puño"
    if fingers == [0, 1, 0, 0, 0]: return "Uno"
    if fingers == [0, 1, 1, 0, 0]: return "Dos"
    if fingers == [0, 1, 1, 1, 0]: return "Tres"
    return "No reconocido"

def toggle_state(key):
    curr = global_device_states.get(key, "OFF")
    type = device_type_map.get(key, "led")
    if type == "servo": new = "ABIERTO" if curr == "CERRADO" else "CERRADO"
    else: new = "ON" if curr == "OFF" else "OFF"
    global_device_states[key] = new
    return new

def log_event(user, action):
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    print(f"LOG: {user} -> {action}")
    try: ref_logs.push({'timestamp': ts, 'user': user, 'action': action})
    except: pass

# --- LISTENER PWA (HILO PARALELO) ---
def pwa_listener(event):
    if not event.data: return
    key = event.data.get('deviceKey')
    # La PWA funciona SIEMPRE, sin importar 'persona_autorizada'
    if key in global_device_states:
        new_val = toggle_state(key)
        log_event("PWA", f"{device_name_map.get(key, key)} -> {new_val}")
        ref_status.update({key: new_val})
        try: ref_commands.child(event.path).remove()
        except: pass

threading.Thread(target=lambda: ref_commands.listen(pwa_listener), daemon=True).start()

# --- CONFIGURACIÓN INICIAL ---
devs = ref_devices.get()
if devs:
    for k, v in devs.items():
        s_key = v['state_key']
        if 'gesture' in v: gesture_map[v['gesture']] = s_key
        device_name_map[s_key] = v['name']
        device_type_map[s_key] = v['type']
        global_device_states[s_key] = "CERRADO" if v['type'] == 'servo' else "OFF"
    curr = ref_status.get()
    if curr:
        for k, v in curr.items():
            if k in global_device_states: global_device_states[k] = v

# --- BUCLE ---
cap = cv2.VideoCapture(0)
fc = 0
is_auth = False
auth_user = "Nadie"

while True:
    ret, frame = cap.read()
    if not ret: break
    frame = cv2.flip(frame, 1)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    fc += 1
    
    # A. RECONOCIMIENTO (Cada 4 frames para no laggear)
    if fc % 4 == 0:
        small = cv2.resize(rgb, (0,0), fx=0.25, fy=0.25)
        locs = face_recognition.face_locations(small, model="hog")
        is_auth = False
        auth_user = "Nadie"
        
        if locs:
            encs = face_recognition.face_encodings(small, locs)
            for enc in encs:
                matches = face_recognition.compare_faces(codificaciones_conocidas, enc)
                if True in matches:
                    auth_user = nombres_conocidos[matches.index(True)]
                    is_auth = True
                    break
        
        # Actualizar estado de seguridad en Firebase
        ref_status.update({'isAuthorized': is_auth, 'currentUser': auth_user})

    # B. GESTOS (Solo si hay cara conocida)
    if is_auth:
        res = hands.process(rgb)
        if res.multi_hand_landmarks:
            for idx, lm in enumerate(res.multi_hand_landmarks):
                mp_drawing.draw_landmarks(frame, lm, mp_hands.HAND_CONNECTIONS)
                h_lbl = res.multi_handedness[idx].classification[0].label
                gst = recognize_gesture(lm, h_lbl)
                
                if time.time() - last_action_time > COOLDOWN:
                    full_gst = f"{gst}-{h_lbl}"
                    target = gesture_map.get(full_gst)
                    
                    if target:
                        new_val = toggle_state(target)
                        log_event(auth_user, f"{device_name_map.get(target)} -> {new_val}")
                        ref_status.update({target: new_val})
                        last_action_time = time.time()
                    
                    # Apagado Total
                    if full_gst == "Puño-Left":
                        for k in global_device_states:
                            val = global_device_states[k]
                            if val == "ON" or val == "ABIERTO":
                                global_device_states[k] = "OFF" if val == "ON" else "CERRADO"
                                ref_status.update({k: global_device_states[k]})
                        log_event(auth_user, "Apagado Total")
                        last_action_time = time.time()

    # GUI
    color = (0, 255, 0) if is_auth else (0, 0, 255)
    cv2.putText(frame, f"Usuario: {auth_user}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
    cv2.imshow("IoT", frame)
    if cv2.waitKey(1) == ord('q'): break

cap.release()
cv2.destroyAllWindows()