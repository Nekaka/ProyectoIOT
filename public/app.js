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

const app = firebase.initializeApp(firebaseConfig);
const database = firebase.database();

const refs = {
    status: database.ref('status'),
    commands: database.ref('commands'),
    devices: database.ref('devices'),
    gestures: database.ref('available_gestures'),
    pins: database.ref('available_pins'),
    logs: database.ref('logs')
};

// DOM Elements
const els = {
    status: document.getElementById('user-status'),
    grid: document.getElementById('devices-grid-container'),
    log: document.getElementById('log-list'),
    modal: {
        backdrop: document.getElementById('admin-modal-backdrop'),
        id: document.getElementById('modal-device-id'),
        name: document.getElementById('modal-name'),
        key: document.getElementById('modal-state-key'),
        type: document.getElementById('modal-type'),
        pin: document.getElementById('modal-pin'),
        gesture: document.getElementById('modal-gesture'),
        servoOpen: document.getElementById('modal-servo-open'),
        servoClosed: document.getElementById('modal-servo-closed'),
        lcdAddr: document.getElementById('modal-lcd-addr'),
        l1on: document.getElementById('modal-l1-on'),
        l2on: document.getElementById('modal-l2-on'),
        l1off: document.getElementById('modal-l1-off'),
        l2off: document.getElementById('modal-l2-off'),
        panelServo: document.getElementById('params-servo'),
        panelLcd: document.getElementById('params-lcd'),
        btnDelete: document.getElementById('modal-delete-btn'),
        title: document.getElementById('modal-title')
    }
};

let appData = { devices: {}, status: {}, gestures: [], pins: {} };

// --- LISTENERS ---
refs.gestures.on('value', s => {
    const val = s.val();
    appData.gestures = Array.isArray(val) ? val : Object.values(val || {});
});
refs.pins.on('value', s => {
    appData.pins = s.val() || {};
    updatePinDropdown();
});

refs.devices.on('value', s => {
    appData.devices = s.val() || {};
    renderCards();
});
refs.status.on('value', s => {
    appData.status = s.val() || {};
    updateUI();
});

// --- LISTENER DE LOGS (CORREGIDO) ---
refs.logs.limitToLast(10).on('child_added', (snapshot) => {
    const log = snapshot.val();
    if (!log || typeof log !== 'object') return;
    
    const li = document.createElement('li');
    const hora = log.timestamp ? log.timestamp.split(' ')[1] : '??:??';
    const usuario = log.user || 'Sistema';
    const accion = log.action || 'Evento';
    
    li.innerHTML = `<strong>[${hora}]</strong> ${usuario}: ${accion}`;
    
    if (usuario === 'PWA') li.style.color = '#007bff';
    if (usuario === 'Nadie') li.style.color = '#dc3545';
    
    // Limpiar "Cargando" o "Esperando"
    const firstItem = els.log.querySelector('li');
    if (firstItem && (firstItem.textContent.includes('Cargando') || firstItem.textContent.includes('Esperando'))) {
        els.log.innerHTML = '';
    }
    
    els.log.prepend(li);
});


// --- RENDERIZADO ---
function renderCards() {
    els.grid.innerHTML = '';
    if (!appData.devices) return;

    Object.entries(appData.devices).forEach(([id, dev]) => {
        if (!dev.state_key) return;
        const state = appData.status[dev.state_key] || 'OFF';
        
        const card = document.createElement('div');
        card.className = `device-status ${getStyle(dev.type, state)}`;
        card.innerHTML = `
            <strong>${dev.name}</strong>
            <span>${state}</span>
            <a href="#" class="edit-btn">Editar</a>
        `;
        
        // Click en tarjeta = COMANDO (Instantáneo)
        card.addEventListener('click', (e) => {
            // IMPORTANTE: Si el clic fue en "Editar", NO enviar comando
            if (e.target.classList.contains('edit-btn')) return;
            
            sendCommand(dev.state_key);
        });

        // Click en editar
        card.querySelector('.edit-btn').addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation(); // Detiene la propagación al padre (la tarjeta)
            openModal(id, dev);
        });

        els.grid.appendChild(card);
    });
}

function updateUI() {
    // Lógica Visual Híbrida
    if (appData.status.isAuthorized) {
        els.status.innerHTML = `🟢 <strong>${appData.status.currentUser}</strong> detectado<br><small>Gestos ACTIVADOS</small>`;
        els.status.className = 'status-msg authorized';
    } else {
        els.status.innerHTML = `⚪ <strong>Modo Remoto</strong><br><small>Control Web: ACTIVO | Gestos: INACTIVOS</small>`;
        els.status.className = 'status-msg remote';
    }
    renderCards(); 
}

function getStyle(type, state) {
    const isOpen = (state === 'ON' || state === 'ABIERTO');
    if (type === 'servo') return isOpen ? 'state-open' : 'state-closed';
    return isOpen ? 'state-on' : 'state-off';
}

function sendCommand(key) {
    console.log("Comando PWA:", key);
    refs.commands.push({ 
        deviceKey: key, 
        timestamp: firebase.database.ServerValue.TIMESTAMP 
    });
}

// --- MODAL ---
function updatePinDropdown() {
    els.modal.pin.innerHTML = '';
    Object.entries(appData.pins).forEach(([name, val]) => {
        els.modal.pin.innerHTML += `<option value="${val}">${name}</option>`;
    });
}

function openModal(id, dev) {
    els.modal.gesture.innerHTML = '';
    appData.gestures.forEach(g => els.modal.gesture.innerHTML += `<option value="${g}">${g}</option>`);

    if (id) {
        els.modal.id.value = id;
        els.modal.name.value = dev.name;
        els.modal.key.value = dev.state_key;
        els.modal.key.disabled = true;
        els.modal.type.value = dev.type;
        els.modal.pin.value = dev.pin;
        els.modal.gesture.value = dev.gesture || "No Asignado";
        els.modal.btnDelete.style.display = 'block';
        els.modal.title.textContent = "Editar Dispositivo";
        
        if (dev.params) {
            if (dev.type === 'servo') {
                els.modal.servoOpen.value = dev.params.angle_open;
                els.modal.servoClosed.value = dev.params.angle_closed;
            } else if (dev.type === 'lcd') {
                els.modal.lcdAddr.value = dev.i2c_address;
                els.modal.l1on.value = dev.params.line1_on;
                els.modal.l2on.value = dev.params.line2_on;
                els.modal.l1off.value = dev.params.line1_off;
                els.modal.l2off.value = dev.params.line2_off;
            }
        }
    } else {
        els.modal.id.value = '';
        els.modal.name.value = '';
        els.modal.key.value = '';
        els.modal.key.disabled = false;
        els.modal.type.value = 'led';
        els.modal.gesture.value = 'No Asignado';
        els.modal.btnDelete.style.display = 'none';
        els.modal.title.textContent = "Nuevo Dispositivo";
        
        // Default params
        els.modal.servoOpen.value = 90; els.modal.servoClosed.value = 0;
        els.modal.lcdAddr.value = '0x27';
    }
    
    els.modal.type.dispatchEvent(new Event('change'));
    els.modal.backdrop.style.display = 'block';
}

els.modal.type.addEventListener('change', (e) => {
    const t = e.target.value;
    els.modal.panelServo.style.display = (t === 'servo') ? 'block' : 'none';
    els.modal.panelLcd.style.display = (t === 'lcd') ? 'block' : 'none';
});

document.getElementById('add-device-btn').addEventListener('click', () => openModal());
document.getElementById('modal-cancel-btn').addEventListener('click', () => els.modal.backdrop.style.display = 'none');

document.getElementById('modal-save-btn').addEventListener('click', () => {
    const id = els.modal.id.value;
    const type = els.modal.type.value;
    const data = {
        name: els.modal.name.value,
        state_key: els.modal.key.value,
        type: type,
        pin: parseInt(els.modal.pin.value),
        gesture: els.modal.gesture.value,
        params: {}
    };

    if (!data.name || !data.state_key) { alert("Faltan datos"); return; }

    if (type === 'servo') {
        data.params = { 
            angle_open: parseInt(els.modal.servoOpen.value),
            angle_closed: parseInt(els.modal.servoClosed.value)
        };
    } else if (type === 'lcd') {
        data.i2c_address = els.modal.lcdAddr.value;
        data.params = {
            line1_on: els.modal.l1on.value, line2_on: els.modal.l2on.value,
            line1_off: els.modal.l1off.value, line2_off: els.modal.l2off.value
        };
    }

    if (id) refs.devices.child(id).update(data);
    else {
        refs.devices.push(data);
        refs.status.update({ [data.state_key]: (type === 'servo' ? 'CERRADO' : 'OFF') });
    }
    els.modal.backdrop.style.display = 'none';
});

document.getElementById('modal-delete-btn').addEventListener('click', () => {
    const id = els.modal.id.value;
    if (id && confirm('¿Borrar?')) {
        refs.devices.child(id).remove();
        refs.status.child(els.modal.key.value).remove();
        els.modal.backdrop.style.display = 'none';
    }
});