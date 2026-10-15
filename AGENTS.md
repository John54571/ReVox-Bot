# 🤖 Instrucciones para Agentes de IA (AGENTS.md)

Este documento contiene el protocolo automatizado que cualquier agente de inteligencia artificial (Claude Code, Cursor, Antigravity, GitHub Copilot CLI, Codex, etc.) debe seguir para instalar, configurar y verificar **ReVox** en la máquina del usuario.

---

## 🎯 Objetivo del Agente
Tu objetivo es dejar el entorno completamente funcional sin requerir que el usuario configure dependencias técnicas manualmente. Al finalizar, el usuario debe tener:
1. Las dependencias del sistema y de Python instaladas.
2. El entorno virtual `.venv` configurado con `requirements.txt`.
3. El archivo `.env` inicializado (con o sin token).
4. El acceso directo `ReVox Control Panel.lnk` creado en el Escritorio del usuario.
5. El panel web verificado y listo para usarse.

---

## 📋 Pasos de Ejecución para el Agente

### Paso 0: Clonar el Repositorio (si no estás dentro del proyecto)

Si el usuario te invocó en una carpeta vacía, cloná el repositorio oficial e ingresá a él:
```powershell
git clone https://github.com/John54571/ReVox-Bot.git
cd ReVox-Bot
```

### Paso 1: Verificación de Prerrequisitos del Sistema

1. **Python 3.11+:**
   - Ejecutá: `python --version`
   - Si no está instalado o es menor a 3.11, instalalo con:
     ```powershell
     winget install Python.Python.3.11
     ```

2. **FFmpeg:**
   - Ejecutá: `ffmpeg -version`
   - Si no está instalado, instalalo con:
     ```powershell
     winget install Gyan.FFmpeg
     ```
   - *Nota:* FFmpeg es indispensable para codificar el audio generado por VoiceStudio a paquetes Opus para Discord.

3. **VoiceStudio (Motor TTS Local):**
   - Verificá si la API local responde ejecutando:
     ```powershell
     try { (Invoke-WebRequest http://127.0.0.1:3900/.well-known/voicestudio-speech -UseBasicParsing -TimeoutSec 3).StatusCode } catch { "offline" }
     ```
   - Si está *offline*, advertí al usuario amistosamente: *"VoiceStudio no está abierto actualmente; recordá abrirlo antes de generar voz."*

---

### Paso 2: Creación del Entorno Virtual e Instalación de Dependencias

1. Creá el entorno virtual si no existe:
   ```powershell
   if (-not (Test-Path ".venv")) { python -m venv .venv }
   ```

2. Instalá las dependencias exactas con pip:
   ```powershell
   .\.venv\Scripts\pip install -r requirements.txt
   ```
   *(Incluye `discord.py[voice]>=2.7.1`, `davey>=0.1.7` para el protocolo E2EE DAVE de Discord, `aiohttp` y `python-dotenv`).*

---

### Paso 3: Configuración del Archivo `.env`

1. Si no existe el archivo `.env`, crealo a partir de la plantilla:
   ```powershell
   if (-not (Test-Path ".env")) { Copy-Item .env.example .env }
   ```
2. Si el usuario te proporcionó un token de Discord en su prompt, inyectalo directamente en `.env`:
   ```ini
   DISCORD_TOKEN=token_del_usuario
   ```
3. Si VoiceStudio está corriendo, podés consultar los perfiles de voz disponibles:
   ```powershell
   (Invoke-RestMethod http://127.0.0.1:3900/v1/audio/voices).voices | Where-Object type -eq "profile" | Select-Object voice_id, name
   ```
   Si el usuario pidió una voz específica (ej. `Dokuro`), asigná su `voice_id` (ej. `188d7f2b`) a `VOICESTUDIO_VOICE=` en `.env`.

---

### Paso 4: Generar Acceso Directo en el Escritorio

Ejecutá el script automatizado para crear el acceso directo con el icono oficial de ReVox:
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\crear_acceso_directo.ps1
```
Esto creará `ReVox Control Panel.lnk` en el Escritorio del usuario apuntando a `iniciar_panel.bat`.

---

### Paso 5: Prueba de Humo y Verificación

Verificá que los módulos principales importen sin errores:
```powershell
.\.venv\Scripts\python -c "import bot, panel; print('ReVox OK')"
```

---

## 📢 Mensaje Final al Usuario
Una vez completado el protocolo, informale al usuario:
- Que las dependencias (`.venv`, `FFmpeg`, paquetes) quedaron instaladas.
- Que tiene el acceso directo **ReVox Control Panel** listo en su Escritorio.
- Que puede abrir la interfaz en **http://127.0.0.1:5050** para configurar su token si aún no lo hizo y hacer clic en *"Iniciar Bot"*.
