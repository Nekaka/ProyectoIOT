## Intalación de las librerias a utilizar

Para evitar errores instalar primero la siguiente libreria que esta subida aqui "dlib-19.22.99 etc.", tambien utilizar la versión de Python subida aquí también:

    pip install "ruta de la carpeta donde clonen el ropositorio" "nombre completo del archivo dlib-19.22.99 etc."

También puede ayudar a evitar errores pero no se que tan necesario sea después de haber hecho lo primero:

    pip install cmake

Opencv para el uso de la webcam:

    pip install opencv-python

Facerecognition para integrar el reconocimiento facial:

    pip install face_recognition

Pyserial para poder enviar datos al arduino:

    pip install pyserial

Actualizar pip en caso de algún error relacionado con las versiones:

    python -m pip install --upgrade pip

Instalar mediapipe para le mapeo de las manos

    pip install mediapipe

Actualizar las demás librerias en caso que no se hayan descargado las ultimas disponibles:

    pip install --upgrade numpy

    pip install --upgrade mediapipe

Instalar libreria de firebase para la conexion con la base de datos

    pip install firebase-admin

Actualizar dependencias por posibles errores en las versiones

    pip install --upgrade mediapipe firebase-admin protobuf grpcio

### El codigo de la carpeta sketch fue actualizado con las nuevas funcionalidades.
### Utilizar reconocimiento.py en VisualStudio Code preferentemente y cambiar en el codigo el puerto COM por el que este usando su arduino.
### Instalar la extension Live Server en VS Code para acceder a la pagina web, dar click derecho en index.html y seleccionar Open with Live Server.
