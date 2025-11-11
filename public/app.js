// --- CONFIGURACIÓN DE FIREBASE (FRONTEND) ---

const firebaseConfig = {
  apiKey: "AIzaSyC7WbDqOqwIqt2xRYSSuUMeOfBsfox0cKY",
  authDomain: "automatizacion-gestos.firebaseapp.com",
  databaseURL: "https://automatizacion-gestos-default-rtdb.firebaseio.com",
  projectId: "automatizacion-gestos",
  storageBucket: "automatizacion-gestos.firebasestorage.app",
  messagingSenderId: "1003330985067",
  appId: "1:1003330985067:web:d432a01fbe2fe7f8ed652e",
  measurementId: "G-2EE0JFT234"
};

// Inicializar Firebase
const app = firebase.initializeApp(firebaseConfig);
const database = firebase.database();

// Opcional: Inicializar Analytics
// const analytics = firebase.analytics(app);


// --- OBTENER REFERENCIAS A LOS ELEMENTOS HTML ---

const userStatusEl = document.getElementById('user-status');
const ledLivingStateEl = document.getElementById('led-living-state');
const ledCocinaStateEl = document.getElementById('led-cocina-state');
const ledDormitorioStateEl = document.getElementById('led-dormitorio-state');
const statusLivingBox = document.getElementById('status-living');
const statusCocinaBox = document.getElementById('status-cocina');
const statusDormitorioBox = document.getElementById('status-dormitorio');
const portonStateEl = document.getElementById('porton-state');
const statusPortonBox = document.getElementById('status-porton');
const logListEl = document.getElementById('log-list');
const unknownListEl = document.getElementById('unknown-list');

// --- ESCUCHAR DATOS EN TIEMPO REAL ---

// Función para actualizar un dispositivo (LED o Portón)
function updateDeviceStatus(element, box, state, onClass, offClass) {
    element.textContent = state;
    if (state === 'ON' || state === 'ABIERTO') {
        box.classList.remove(offClass);
        box.classList.add(onClass);
    } else {
        box.classList.remove(onClass);
        box.classList.add(offClass);
    }
}

// Escuchar cambios en el estado general
const statusRef = database.ref('status');
statusRef.on('value', (snapshot) => {
    const data = snapshot.val();
    if (data) {
        // Estado de autorización
        if (data.isAuthorized) {
            userStatusEl.textContent = `Autorizado: ${data.currentUser}`;
            userStatusEl.className = 'authorized';
        } else {
            userStatusEl.textContent = 'Sistema Bloqueado';
            userStatusEl.className = 'unauthorized';
        }
        
        // Actualizar dispositivos
        updateDeviceStatus(ledLivingStateEl, statusLivingBox, data.ledLiving, 'state-on', 'state-off');
        updateDeviceStatus(ledCocinaStateEl, statusCocinaBox, data.ledCocina, 'state-on', 'state-off');
        updateDeviceStatus(ledDormitorioStateEl, statusDormitorioBox, data.ledDormitorio, 'state-on', 'state-off');
        updateDeviceStatus(portonStateEl, statusPortonBox, data.porton, 'state-open', 'state-closed');
    }
});

function addLogToList(listElement, log, logClass) {
    // ... (código de la función) ...
}

// Escuchar nuevos logs (Gestos)
database.ref('logs').orderByChild('type').equalTo('gesture').limitToLast(20).on('child_added', (snapshot) => {
    const log = snapshot.val();
    const actionText = `[${log.timestamp}] ${log.user}: ${log.action}`;
    
    const li = document.createElement('li');
    li.textContent = actionText;
    li.className = 'log-gesture';
    
    if (logListEl.firstChild && logListEl.firstChild.textContent.startsWith('Esperando')) {
        logListEl.innerHTML = ''; // Limpiar el mensaje inicial
    }
    logListEl.prepend(li);
});

// Escuchar nuevos logs (Desconocidos)
database.ref('logs').orderByChild('type').equalTo('unknown_sighting').limitToLast(20).on('child_added', (snapshot) => {
    const log = snapshot.val();
    const actionText = `[${log.timestamp}] ${log.action}`;
    
    const li = document.createElement('li');
    li.textContent = actionText;
    li.className = 'log-unknown';
    
    if (unknownListEl.firstChild && unknownListEl.firstChild.textContent.startsWith('Sin detecciones')) {
        unknownListEl.innerHTML = ''; // Limpiar el mensaje inicial
    }
    unknownListEl.prepend(li);
});

// Limpiar mensaje inicial si no hay datos al cargar
logListEl.innerHTML = '<li class="initial-msg">Esperando datos...</li>';
unknownListEl.innerHTML = '<li class="initial-msg">Sin detecciones...</li>';