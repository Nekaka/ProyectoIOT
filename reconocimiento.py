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

            rgb_frame = pil_image.convert('RGB')

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


# try:
#     imagen_referencia = face_recognition.load_image_file("foto.jpg") #Cambiar despues por una foto de la persona
#     codificacion_referencia = face_recognition.face_encodings(imagen_referencia)[0]
#     codificaciones_conocidas = [codificacion_referencia]
#     nombres_conocidos = ["Inserte nombre"] #Cambiar luego por el nombre de la persona
# except FileNotFoundError:
#     print("Advertencia: No se encontro ninguna imagen, el reconocimiento facial estara desactivado")
#     codificaciones_conocidas = []
#     nombres_conocidos = [0]

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
webcam = cv2.VideoCapture(0)
print("Iniciando cámara... Presiona 'q' para salir.")

while True:
    ret, frame = webcam.read()
    if not ret: break
    frame = cv2.flip(frame, 1)
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    results_hands = hands.process(rgb_frame)
    if results_hands.multi_hand_landmarks:
        for idx, hand_landmarks in enumerate(results_hands.multi_hand_landmarks):
            # Obtenemos la etiqueta 'Left' o 'Right'
            handedness_obj = results_hands.multi_handedness[idx]
            handedness_label = handedness_obj.classification[0].label

            # Dibujamos los puntos en la mano
            mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
            
            # Pasamos la lateralidad a nuestra función de reconocimiento
            gesture_name = recognize_gesture(hand_landmarks, handedness_label)
            
            current_time = time.time()
            if gesture_name == "Cinco" and (current_time - last_action_time) > COOLDOWN_SECONDS:
                if handedness_label == 'Left':
                    # ACCIÓN PARA LA MANO IZQUIERDA: Controlar el LED
                    if led_state == 'OFF':
                        if arduino: arduino.write(b'H')
                        led_state = 'ON'
                        print(f"ACCIÓN (Mano Izquierda): Encendiendo LED")
                    else:
                        if arduino: arduino.write(b'L')
                        led_state = 'OFF'
                        print(f"ACCIÓN (Mano Izquierda): Apagando LED")
                    last_action_time = current_time # Iniciar cooldown
                
                elif handedness_label == 'Right':
                    # ACCIÓN PARA LA MANO DERECHA: Imprimir un mensaje (o lo que quieras)
                    print(f"ACCIÓN (Mano Derecha): ¡Hola desde la mano derecha!")
                    last_action_time = current_time # Iniciar cooldown
            if gesture_name == "Puño" and (current_time - last_action_time) > COOLDOWN_SECONDS:
                if handedness_label == 'Left':
                    if led_state == 'OFF':
                        if arduino: arduino.write(b'H')
                        led_state = 'ON'
                        print(f"ACCIÓN (Mano Izquierda): Encendiendo LED")
                    else:
                        if arduino: arduino.write(b'L')
                        led_state = 'OFF'
                        print(f"ACCIÓN (Mano Izquierda): Apagando LED")
                    last_action_time = current_time # Iniciar cooldown
                elif handedness_label == 'Right':
                    print(f"Despues pensare que ponerle a este gesto XD")
                    last_action_time = current_time # Iniciar cooldown

            # Mostramos en pantalla qué mano y qué gesto se detectó
            wrist = hand_landmarks.landmark[mp_hands.HandLandmark.WRIST]
            cv2.putText(frame, f"{handedness_label} - Gesto: {gesture_name}", (int(wrist.x * frame.shape[1]) - 50, int(wrist.y * frame.shape[0]) - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            
    # Procesamiento de rostros (si las imágenes se cargaron)
    if nombres_conocidos:
        ubicaciones_rostros = face_recognition.face_locations(rgb_frame)
        codificaciones_rostros = face_recognition.face_encodings(rgb_frame, ubicaciones_rostros)
        for (top, right, bottom, left), face_encoding in zip(ubicaciones_rostros, codificaciones_rostros):
            coincidencias = face_recognition.compare_faces(codificaciones_conocidas, face_encoding)
            nombre = "Desconocido"
            if True in coincidencias:
                primer_indice = coincidencias.index(True)
                nombre = nombres_conocidos[primer_indice]

            # Dibujar el rectangulo y el nombre
            cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
            cv2.rectangle(frame, (left, bottom - 35), (right, bottom), (0, 255, 0), cv2.FILLED)
            cv2.putText(frame, nombre, (left + 6, bottom - 6), cv2.FONT_HERSHEY_DUPLEX, 1.0, (255, 255, 255), 1)

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