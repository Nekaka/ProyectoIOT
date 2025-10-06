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

Actualizar las demás librerias en caso que no se hayan descargado las ultimas disponibles:

    pip install --upgrade numpy

    pip install --upgrade mediapipe

### La carpeta sketch es un codigo básico para utilizar en el arduino que de momento solo enciende y apaga un led al abrir y cerrar el puño frente a la webcam.
### Utilizar reconocimiento.py en VisualStudio preferentemente y cambiar en el codigo el puerto COM por el que este usando su arduino.
