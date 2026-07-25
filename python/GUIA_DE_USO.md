# 🚀 Guía de Uso — App Interactiva Muro NSR-10

Aplicación **web interactiva** para diseñar muros de contención según NSR-10.
Corre en tu navegador con dibujo en vivo del muro, tablas de resultados y
generación de reporte PDF profesional.

---

## ⚡ Instalación (la primera vez, solo una vez)

### 🪟 Windows

1. **Instala Python** (si no lo tienes):
   - Entra a **https://www.python.org/downloads/** y descarga la última versión.
   - ⚠️ Durante la instalación marca la casilla **"Add Python to PATH"**.

2. **Descomprime el ZIP** en una carpeta. Quedará algo así:

   ```
   Documentos/muro_app/
   ├── app.py
   ├── instalar.bat
   ├── iniciar.bat
   ├── retaining_wall/
   ├── templates/
   └── ...
   ```

3. **Instala las librerías:** haz **doble clic** sobre `instalar.bat`.
   Se abrirá una ventana negra que descargará Flask, matplotlib y reportlab.
   Cuando termine dirá "INSTALACION COMPLETADA".

### 🍎 Mac / 🐧 Linux

1. Instala Python 3 (con Homebrew: `brew install python`).
2. Abre la Terminal en la carpeta del proyecto.
3. Ejecuta: `bash instalar.sh`

---

## ▶️ Cómo ejecutar la app — DOS FORMAS

### ✨ Forma 1: Doble clic en `iniciar.bat` (la más fácil - Windows)

1. En la carpeta `muro_app`, haz **doble clic** sobre **`iniciar.bat`**.
2. Se abre una ventana negra (no la cierres) y automáticamente se abre el
   navegador en `http://localhost:5000`.
3. ¡Listo! Usa la app. Para cerrarla, cierra la ventana negra.

### 🎯 Forma 2: Botón Run (▶) en VSCode

1. Abre VSCode → **File → Open Folder** → selecciona la carpeta `muro_app`
   (⚠️ la que contiene `app.py`, **no** la carpeta `retaining_wall`).

2. En el explorador izquierdo haz **clic** sobre **`app.py`** para abrirlo.

3. Presiona el botón triángulo ▶️ en la **esquina superior derecha**.
   Si VSCode te muestra opciones, elige **"Run Python File"** (NO "Debug").

4. Abajo se abrirá una terminal mostrando:
   ```
   Running on http://localhost:5000
   ```

5. **Haz Ctrl+Clic** sobre ese enlace, o abre manualmente tu navegador
   (Chrome/Edge/Firefox) y escribe: **`http://localhost:5000`**

6. Para **detener** la app: en la terminal de VSCode presiona `Ctrl + C`.

> 💡 **¿Por qué no funcionaba antes el botón Run?** El archivo anterior
> (`muro_proyecto.py`) estaba **dentro** de la carpeta `retaining_wall/`.
> Para que Run funcione, el archivo a ejecutar debe estar **afuera** del
> paquete. Por eso aquí `app.py` está en la raíz y funciona perfecto.

---

## 🧭 Cómo usar la interfaz

La pantalla se divide en 3 zonas:

### 📝 Panel izquierdo — FORMULARIO (6 secciones plegables)

Haz clic en cada encabezado para abrir/cerrar la sección:

1. **Datos del proyecto** — empresa, ingeniero, etc. (van a la portada del PDF).
2. **Geometría del muro** — todas las dimensiones en metros.
3. **Suelo de relleno** — γ, φ, cohesión del material detrás del muro.
4. **Suelo de cimentación** — γ, φ, cohesión del material bajo la zapata.
5. **Cargas y condiciones** — inclinación del relleno, sobrecarga y ⭐ **SISMO**.
   - Al marcar "Incluir sismo" aparecen:
     - `Aa` y `Av` (coeficientes NSR-10 A.2)
     - Perfil de suelo (A, B, C, D, E)
     - Método (con/sin desplazamiento)
   - En tiempo real verás **Fa, Fv, kh, kv** calculados automáticamente.
6. **Materiales** — f'c, fy del concreto y acero.

### 🖼️ Panel derecho superior — VISTA GRÁFICA DEL MURO

- Muestra el muro dibujado a escala con cotas y empujes.
- El botón "↻ Regenerar" actualiza el dibujo con las dimensiones actuales.
- Se actualiza automáticamente tras ejecutar un análisis.

### 📊 Panel derecho inferior — RESULTADOS (5 pestañas)

Aparecen vacías hasta que ejecutes el análisis.

- **Resumen** — KPIs y estado final APROBADO/NO APROBADO.
- **Cargas** — todas las cargas características con su categoría NSR-10.
- **Combinaciones** — tablas ELU (B.2.4) y ELS (B.2.3).
- **Estabilidad** — los 4 factores de seguridad y presiones bajo la zapata.
- **Diseño estructural** — refuerzo requerido para vástago, punta y talón.

### 🎯 Barra superior (botones de acción)

- **◈ Actualizar vista** — solo redibuja el muro sin calcular nada.
- **▶ Ejecutar análisis** — corre TODOS los cálculos y llena las pestañas.
- **⬇ Generar PDF** — (se habilita tras ejecutar un análisis)
  Abre un diálogo de confirmación con los datos del proyecto y al aceptar
  descarga el reporte PDF completo.

---

## 📋 Flujo típico de trabajo

```
1. Abrir app (doble clic en iniciar.bat o botón Run sobre app.py)
          ↓
2. Llenar "Datos del proyecto" (panel 1 del formulario)
          ↓
3. Editar "Geometría del muro" (panel 2)
          ↓
4. Ajustar propiedades de los suelos (paneles 3 y 4)
          ↓
5. Si hay sismo → marcar casilla y llenar Aa, Av, perfil
          ↓
6. Clic en ▶ "Ejecutar análisis"
          ↓
7. Revisar los resultados en las pestañas
          ↓
8. ¿CUMPLE? → Clic en ⬇ "Generar PDF"
   ¿NO cumple? → Ajustar dimensiones (ej. aumentar talón) y repetir desde 6.
```

---

## 🔴 Errores comunes

### "No module named 'flask'"
No instalaste las dependencias. Ejecuta `instalar.bat` (Windows) o
`bash instalar.sh` (Mac/Linux).

### "No module named 'retaining_wall'"
Abriste la carpeta equivocada en VSCode. Asegúrate de abrir la carpeta que
**contiene** `app.py`, no su subcarpeta.

### El botón Run no funciona / abre otra cosa
- Verifica que tengas la extensión **Python de Microsoft** instalada.
- Debes tener abierto `app.py` (no otro archivo) al presionar Run.
- Si te da opciones, elige "Run Python File" (sin "Debug").

### "Port 5000 is already in use"
La app ya está corriendo en otra ventana. Cierra la terminal anterior y
vuelve a intentar, o cambia el puerto editando la última línea de `app.py`:
`app.run(port=5001)`.

### El navegador no se abre solo
Ábrelo manualmente y escribe la dirección: **`http://localhost:5000`**

### La app corre pero no veo nada
Espera unos segundos. Si sigue vacío, abre la consola del navegador
(`F12` → Console) y revisa si hay errores.

---

## 🧯 Resumen mínimo (para tenerlo a mano)

| Acción                          | Cómo                                          |
|---------------------------------|-----------------------------------------------|
| Instalar (primera vez)          | Doble clic en `instalar.bat`                  |
| Iniciar la app                  | Doble clic en `iniciar.bat` **O** ▶ sobre `app.py` |
| Abrir en navegador              | `http://localhost:5000`                       |
| Detener la app                  | Cerrar ventana negra **O** `Ctrl+C` en terminal |
| Cambiar puerto (si 5000 ocupado) | Editar última línea de `app.py`              |
